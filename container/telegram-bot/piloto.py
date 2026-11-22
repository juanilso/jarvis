"""Piloto automático: roda /jarvis:entregar em rodadas até o projeto ficar pronto para a SUA validação.

Cada rodada é uma execução nova (o estado fica em docs/ do projeto, então o contexto não estoura).
Entre rodadas você recebe só 1 linha. O Jarvis só te chama quando:
  - PRONTO: o modelo declarou pronto E o teste do site passou (0 crítico, 0 alto, jornadas ok, nota ≥ 85);
  - BLOQUEADO: precisa de algo que só você tem (senha, publicar, pagamento…);
  - acabou o limite de rodadas/custo, ou 2 rodadas seguidas sem nenhuma mudança no código.
"""
import hashlib
import json
import os
import re
import subprocess
import threading
import time

import jarvis_core as core

PASTA = os.path.join(core.CONFIG_DIR, "piloto")
MAX_RODADAS = int(os.environ.get("JARVIS_PILOTO_RODADAS", "8"))
MAX_CUSTO = float(os.environ.get("JARVIS_PILOTO_CUSTO", "15"))  # US$ por piloto (estimativa do Claude Code)
NOTA_MINIMA = int(os.environ.get("JARVIS_PILOTO_NOTA", "85"))
_ativos = {}  # projeto -> {"parar": bool}
_lock = threading.Lock()

REGRAS_PILOTO = (
    "MODO PILOTO: o usuário só quer ser chamado quando o projeto estiver pronto para a validação dele. "
    "Não faça perguntas: decida o que for reversível pela opção recomendada e registre [piloto] em docs/DECISOES.md. "
    "Use conteúdo provisório marcado quando faltar material do usuário. Nunca faça push, deploy ou publicação. "
    "Termine SEMPRE com a última linha 'PILOTO: PRONTO', 'PILOTO: CONTINUAR — …' ou 'PILOTO: BLOQUEADO — …'.")

_MARCA = re.compile(r"PILOTO:\s*(PRONTO|CONTINUAR|BLOQUEADO)\s*(?:[—–-]\s*(.*))?", re.I)


def _arq(projeto):
    return os.path.join(PASTA, projeto + ".json")


def ler(projeto):
    try:
        return json.load(open(_arq(projeto), encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _salvar(projeto, d):
    os.makedirs(PASTA, exist_ok=True)
    tmp = _arq(projeto) + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, _arq(projeto))


def ativo(projeto):
    """Rodando aqui ou no outro contêiner (painel/Telegram): o arquivo é atualizado a cada rodada."""
    if projeto in _ativos:
        return True
    d = ler(projeto)
    try:
        recente = time.time() - os.path.getmtime(_arq(projeto)) < (core.TIMEOUT + 1800)
    except OSError:
        recente = False
    return bool(d and d.get("situacao") == "rodando" and recente)


def parar(projeto, pool=None):
    """Para depois da rodada atual; com pool, interrompe a rodada já."""
    d = ler(projeto)
    if projeto in _ativos:
        _ativos[projeto]["parar"] = True
        if pool:
            pool.de(projeto).parar()
    elif not ativo(projeto):
        return False
    if d:
        d["parar"] = True  # o contêiner que roda o piloto lê isto e para depois da rodada atual
        _salvar(projeto, d)
    return True


def ler_marca(texto):
    """('PRONTO'|'CONTINUAR'|'BLOQUEADO', motivo). Sem marca = CONTINUAR."""
    achados = list(_MARCA.finditer(texto or ""))
    if not achados:
        return "CONTINUAR", "a rodada terminou sem dizer o estado"
    m = achados[-1]
    return m.group(1).upper(), (m.group(2) or "").strip()[:300]


def assinatura(pasta):
    """Muda quando o código muda (commit novo ou arquivo alterado), para detectar rodada sem progresso."""
    try:
        head = subprocess.run(["git", "-C", pasta, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=20).stdout
        sujo = subprocess.run(["git", "-C", pasta, "status", "--porcelain"], capture_output=True, text=True, timeout=20).stdout
        return hashlib.sha1((head + sujo).encode()).hexdigest()
    except Exception:  # noqa: BLE001
        return str(time.time())


def tem_site(projeto):
    import site_previa
    raiz = site_previa.raiz_do_site(site_previa.pasta_projeto(projeto))
    return any(os.path.isfile(os.path.join(raiz, n)) for n in ("index.php", "index.html", "index.htm"))


def homologar(projeto):
    """Portão do Jarvis (não depende do modelo): o site precisa passar no teste. Retorna (ok, motivo, dados_teste)."""
    if not tem_site(projeto):
        return True, "sem site para testar", None
    import site_previa
    ok, saida, d = site_previa.rodar("testar", projeto)
    if not d:
        return False, "o teste do site não terminou: " + saida[-300:], None
    c, j = d.get("contagem") or {}, d.get("jornadas") or {}
    faltas = []
    if c.get("CRÍTICO"):
        faltas.append(f"{c['CRÍTICO']} crítico(s)")
    if c.get("ALTO"):
        faltas.append(f"{c['ALTO']} alto(s)")
    if j.get("falhas"):
        faltas.append(f"{j['falhas']} jornada(s) falhando")
    if not j.get("total"):
        faltas.append("nenhuma jornada em .jarvis/jornadas.json")
    if (d.get("nota") or 0) < NOTA_MINIMA:
        faltas.append(f"nota {d.get('nota')} (mínimo {NOTA_MINIMA})")
    return not faltas, ", ".join(faltas) or f"nota {d.get('nota')}", d


def iniciar(estado, pool, projeto, objetivo, avisar, ao_fim, max_rodadas=None, max_custo=None):
    """Começa o piloto em segundo plano. avisar(texto): 1 linha por rodada. ao_fim(situacao, texto, dados).
    Retorna (ok, mensagem)."""
    if not projeto or projeto not in core.listar_projetos():
        return False, "Escolha um projeto primeiro."
    with _lock:
        if projeto in _ativos or ativo(projeto):
            return False, f"O piloto já está rodando em {projeto}. /piloto para ver, /piloto parar para parar."
        _ativos[projeto] = {"parar": False}
    max_rodadas = max_rodadas or MAX_RODADAS
    max_custo = max_custo or MAX_CUSTO
    d = {"projeto": projeto, "objetivo": objetivo, "inicio": time.strftime("%Y-%m-%d %H:%M"), "rodada": 0,
         "max_rodadas": max_rodadas, "custo": 0.0, "max_custo": max_custo, "situacao": "rodando", "historico": []}
    _salvar(projeto, d)
    threading.Thread(target=_laco, args=(estado, pool, projeto, objetivo, avisar, ao_fim, d), daemon=True).start()
    return True, (f"🚀 Piloto ligado em {projeto}: vou construir, testar e corrigir sozinho (até {max_rodadas} rodadas "
                  f"ou US$ {max_custo:.0f}). Você recebe 1 linha por rodada e eu só te chamo quando estiver pronto para "
                  "a sua validação (ou se precisar de algo que só você tem). /piloto parar para interromper.")


def _quer_parar(projeto):
    return _ativos[projeto]["parar"] or bool((ler(projeto) or {}).get("parar"))


def _laco(estado, pool, projeto, objetivo, avisar, ao_fim, d):
    pasta = os.path.join(core.WORKSPACE, projeto)
    retorno, sem_mudanca, antes = "", 0, assinatura(pasta)
    reprovas = []  # motivos seguidos de reprovação na homologação
    situacao, texto_final, teste = "limite", "", None
    try:
        for n in range(1, d["max_rodadas"] + 1):
            if _quer_parar(projeto):
                situacao = "parado"
                break
            espera = 0
            while not pool.pode_iniciar(projeto)[0] and espera < 1800:  # você está usando o projeto: espera a vez
                time.sleep(15)
                espera += 15
            d["rodada"] = n
            _salvar(projeto, d)
            prompt = (f"/jarvis:entregar {objetivo}\n\n[PILOTO rodada {n} de {d['max_rodadas']}]"
                      + (f"\n\nRetorno da homologação automática do Jarvis (corrija antes de declarar PRONTO):\n{retorno}"
                         if retorno else ""))
            res = {}

            def ev(e, res=res):
                if e["tipo"] in ("resposta", "erro"):
                    res.update(e)
            pool.de(projeto).rodar(estado, prompt, False, ev, usar_sessao=False, projeto=projeto,
                                   sistema=core.ORQUESTRADOR + "\n" + REGRAS_PILOTO, custo_no_projeto=True)
            d["custo"] = round(d["custo"] + float(res.get("custo") or 0), 4)
            if _quer_parar(projeto):
                situacao = "parado"
                break
            if res.get("tipo") == "erro":
                marca, motivo = "ERRO", res.get("texto", "")[:300]
            else:
                marca, motivo = ler_marca(res.get("texto", ""))
            depois = assinatura(pasta)
            sem_mudanca = sem_mudanca + 1 if depois == antes else 0
            antes = depois
            linha = {"rodada": n, "marca": marca, "motivo": motivo, "custo": d["custo"], "quando": time.strftime("%H:%M")}

            if marca == "PRONTO":
                ok, porque, teste = homologar(projeto)
                linha["homologacao"] = porque
                if ok:
                    situacao, texto_final = "pronto", res.get("texto", "")
                    d["historico"].append(linha)
                    break
                reprovas.append(porque)
                if len(reprovas) >= 3 and len(set(reprovas[-3:])) == 1:
                    situacao, texto_final = "travado", f"Três rodadas seguidas com o mesmo problema no teste: {porque}."
                    d["historico"].append(linha)
                    break
                retorno = (f"O teste do site NÃO passou: {porque}.\n\n" + ((teste or {}).get("relatorio_texto") or "")[:4000])
                avisar(f"🚀 [{projeto}] rodada {n}: disse pronto, mas o teste reprovou ({porque}). Corrigindo…")
            elif marca == "BLOQUEADO":
                situacao, texto_final = "bloqueado", res.get("texto", "")
                d["historico"].append(linha)
                break
            elif marca == "ERRO":
                retorno = f"A rodada anterior falhou: {motivo}. Retome de onde parou (veja docs/PILOTO.md)."
                avisar(f"🚀 [{projeto}] rodada {n}: deu erro ({motivo[:120]}). Tentando de novo…")
                if sem_mudanca >= 2:
                    situacao, texto_final = "erro", motivo
                    d["historico"].append(linha)
                    break
            else:
                retorno, reprovas = "", []
                avisar(f"🚀 [{projeto}] rodada {n}/{d['max_rodadas']} ✔ {motivo[:160] or 'avançando'} · US$ {d['custo']:.2f}")
            d["historico"].append(linha)
            _salvar(projeto, d)
            if sem_mudanca >= 2:
                situacao, texto_final = "travado", "2 rodadas seguidas sem nenhuma mudança no código."
                break
            if d["custo"] >= d["max_custo"]:
                situacao, texto_final = "custo", f"Atingi o limite de US$ {d['max_custo']:.0f} deste piloto."
                break
    except Exception as e:  # noqa: BLE001
        situacao, texto_final = "erro", f"{type(e).__name__}: {e}"
    finally:
        d["situacao"], d["fim"] = situacao, time.strftime("%Y-%m-%d %H:%M")
        _salvar(projeto, d)
        _ativos.pop(projeto, None)
    if situacao in ("limite", "custo", "travado") and teste is None:
        _, _, teste = homologar(projeto) if tem_site(projeto) else (None, None, None)
    ao_fim(situacao, texto_final, {**d, "teste": teste})


TITULOS = {
    "pronto": "✅ PRONTO PARA A SUA VALIDAÇÃO",
    "bloqueado": "⛔ Preciso de você para continuar",
    "limite": "⏸ Parei no limite de rodadas (ainda não está pronto)",
    "custo": "⏸ Parei no limite de custo (ainda não está pronto)",
    "travado": "⏸ Parei: o piloto não estava avançando",
    "parado": "⏹ Piloto parado por você",
    "erro": "⚠️ O piloto parou com erro",
}


def mensagem_final(projeto, situacao, texto, d):
    """Texto do aviso final (Telegram/painel)."""
    cab = f"{TITULOS.get(situacao, situacao)} · {projeto}\n{d.get('rodada', 0)} rodada(s) · US$ {d.get('custo', 0):.2f}"
    teste = d.get("teste")
    if teste:
        c = teste.get("contagem") or {}
        cab += (f"\n🧪 teste: nota {teste.get('nota')}/100 · críticos {c.get('CRÍTICO', 0)} · altos {c.get('ALTO', 0)}"
                f" · jornadas {(teste.get('jornadas') or {}).get('total', 0) - (teste.get('jornadas') or {}).get('falhas', 0)}"
                f"/{(teste.get('jornadas') or {}).get('total', 0)} ok")
    marca, motivo = ler_marca(texto) if texto else ("", "")
    if situacao == "bloqueado" and motivo:
        cab += f"\n\n👉 {motivo}"
    corpo = re.sub(r"\n?PILOTO:\s*(PRONTO|CONTINUAR|BLOQUEADO).*$", "", (texto or "").strip(), flags=re.I | re.S).strip()
    if situacao == "pronto":
        cab += "\n\nRoteiro de validação completo em docs/HOMOLOGACAO.md. Me diga o que ajustar; para outra volta: /piloto <ajustes>."
    elif situacao in ("limite", "custo", "travado"):
        cab += "\n\nPara continuar de onde parou: /piloto continuar"
    return cab + ("\n\n" + corpo[:3000] if corpo else "")


def status_texto(projeto):
    d = ler(projeto)
    if not d:
        return f"Nenhum piloto em {projeto}. Para começar: /piloto <objetivo>"
    h = d.get("historico") or []
    ult = h[-1] if h else {}
    estado = "🚀 rodando" if ativo(projeto) else TITULOS.get(d.get("situacao"), d.get("situacao"))
    linhas = [f"{estado} · {projeto}", f"Objetivo: {d.get('objetivo')}",
              f"Rodada {d.get('rodada')}/{d.get('max_rodadas')} · US$ {d.get('custo', 0):.2f} de {d.get('max_custo', 0):.0f}"
              f" · desde {d.get('inicio')}"]
    for x in h[-5:]:
        linhas.append(f"• {x['quando']} r{x['rodada']} {x['marca']}: {(x.get('homologacao') or x.get('motivo') or '')[:120]}")
    if not ult and ativo(projeto):
        linhas.append("• primeira rodada em andamento…")
    return "\n".join(linhas)
