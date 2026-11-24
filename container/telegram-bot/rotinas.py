"""Gatilho seguro para rotinas automáticas (n8n ou qualquer agendador) e registro das execuções.

POST /api/gatilho  (cabeçalho: Authorization: Bearer <JARVIS_GATILHO_TOKEN>)
{
  "rotina":  "Pesquisa semanal",          nome que aparece no escritório e nos avisos
  "acao":    "hermes" | "jarvis" | "pesquisar" | "tendencias" | "ideia" | "avisar" | "status" | "atender"
             | "pagamento" (texto) | "painel_consultar" (login) | "painel_teste" (telefone)
             | "previa" (liga a prévia do projeto e devolve o link)
             | "site_testar" (testa o site do projeto ou "url"; "so_se_problema": true só avisa se houver falha),
  "texto":   "o pedido",
  "projeto": "pasta do projeto" (opcional; padrão: o projeto atual do painel),
  "avisar":  true                          manda o resultado no Telegram
  "esperar": false                         true = devolve o resultado na resposta HTTP (até 15 min)
}

Regras: o Jarvis em rotina só analisa/testa/relata (edição e comandos perigosos bloqueados);
o Hermes continua só-leitura; nada de deploy, push ou banco de produção.
"""
import hmac
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

import jarvis_core as core

TOKEN = os.environ.get("JARVIS_GATILHO_TOKEN", "").strip()
ARQ = os.path.join(core.CONFIG_DIR, "rotinas.jsonl")
ACOES = {"hermes", "jarvis", "pesquisar", "tendencias", "ideia", "avisar", "status", "atender",
         "pagamento", "painel_consultar", "painel_teste", "atendimento_cmd", "jogos",
         "previa", "site_testar"}
_lock = threading.Lock()


def autorizado(cabecalho):
    if not TOKEN:
        return False
    enviado = (cabecalho or "").removeprefix("Bearer ").strip()
    return hmac.compare_digest(enviado, TOKEN)


def registrar(item):
    item = dict(item, quando=item.get("quando") or time.strftime("%Y-%m-%d %H:%M:%S"))
    with _lock:
        try:
            os.makedirs(os.path.dirname(ARQ), exist_ok=True)
            with open(ARQ, "a", encoding="utf-8") as f:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        except OSError as e:
            print("erro ao registrar rotina:", e, flush=True)


def listar(limite=30):
    try:
        linhas = open(ARQ, encoding="utf-8").read().splitlines()[-limite * 3:]
    except OSError:
        return []
    saida, vistos = [], set()
    for l in reversed(linhas):  # cada execução tem início e fim: mostra só o registro mais recente
        try:
            item = json.loads(l)
        except json.JSONDecodeError:
            continue
        if item.get("id") in vistos:
            continue
        vistos.add(item.get("id"))
        saida.append(item)
    return saida[:limite]


def avisar_telegram(texto):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chats = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]
    if not token or not chats:
        return False
    ok = False
    for chat in chats:
        for i in range(0, len(texto), 3900):
            dados = urllib.parse.urlencode({"chat_id": chat, "text": texto[i:i + 3900]}).encode()
            try:
                urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=dados, timeout=20)
                ok = True
            except Exception as e:  # noqa: BLE001
                print("erro ao avisar no Telegram:", e, flush=True)
    return ok


def avisar_telegram_video(caminho, legenda=""):
    """Manda um MP4 para o seu Telegram (até 50 MB)."""
    return avisar_telegram_foto(caminho, legenda, tipo="video")


def avisar_telegram_foto(caminho, legenda="", tipo="photo"):
    """Manda uma imagem (PNG/JPG) para o seu Telegram."""
    import uuid
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chats = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]
    if not token or not chats or not os.path.isfile(caminho) or os.path.getsize(caminho) > 49 * 1024 * 1024:
        return False
    dados = open(caminho, "rb").read()
    ok = False
    for chat in chats:
        b = uuid.uuid4().hex
        corpo = b"".join([
            f"--{b}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat}\r\n".encode(),
            f"--{b}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{legenda[:1000]}\r\n".encode(),
            f"--{b}\r\nContent-Disposition: form-data; name=\"{tipo}\"; filename=\"{os.path.basename(caminho)}\"\r\n"
            f"Content-Type: {'video/mp4' if tipo == 'video' else 'image/png'}\r\n\r\n".encode(), dados, f"\r\n--{b}--\r\n".encode()])
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{'sendVideo' if tipo == 'video' else 'sendPhoto'}", data=corpo,
                                     headers={"Content-Type": f"multipart/form-data; boundary={b}"})
        try:
            urllib.request.urlopen(req, timeout=60)
            ok = True
        except Exception as e:  # noqa: BLE001
            print("erro ao mandar foto no Telegram:", e, flush=True)
    return ok


def _limpar_nome(nome):
    return re.sub(r"[^\w .:-]", "", str(nome or "rotina"))[:60] or "rotina"


def executar(dados, publicar, pool, estado):
    """Valida e executa um pedido do gatilho. Retorna (código_http, dict)."""
    if not isinstance(dados, dict):
        return 400, {"erro": "corpo deve ser JSON"}
    acao = str(dados.get("acao", "")).lower()
    if acao not in ACOES:
        return 400, {"erro": f"ação inválida; use uma de: {', '.join(sorted(ACOES))}"}
    if acao == "atender":  # WhatsApp: resposta rápida, sem registrar como rotina (seria ruído)
        import atendimento
        return 200, dict(atendimento.atender(dados), ok=True)
    if acao == "jogos":  # jogos do dia: gera (pesquisa canais) e, se pedido, manda imagem + texto no Telegram
        import jogos

        def _jogos():
            try:
                d = jogos.gerar(forcar=bool(dados.get("forcar", True)))
                if dados.get("avisar", True):
                    jogos.enviar_telegram(d)
                    try:  # e no grupo, se você ligou "mandar a lista do dia no grupo"
                        import jogos_alertas
                        jogos_alertas.lista_no_grupo(d)
                    except Exception as e:  # noqa: BLE001
                        print("lista no grupo:", e, flush=True)
                registrar({"id": f"jogos-{d['dia']}", "rotina": "Jogos do dia", "acao": "jogos", "projeto": "",
                           "ok": True, "resultado": f"{len(d['jogos'])} jogos · {d['canais_pesquisados']} canais pesquisados"})
            except Exception as e:  # noqa: BLE001
                avisar_telegram(f"⚽ Não consegui montar os jogos do dia: {type(e).__name__}: {e}"[:500])
        threading.Thread(target=_jogos, daemon=True).start()
        return 202, {"ok": True, "status": "gerando os jogos do dia (alguns minutos por causa da pesquisa de canais)"}
    if acao in ("previa", "site_testar"):
        import site_previa
        projeto = str(dados.get("projeto") or estado.ler()["projeto"] or "")
        if projeto not in core.listar_projetos():
            return 400, {"erro": f"projeto “{projeto}” não existe"}
        if acao == "previa":
            try:
                site_previa.garantir_previa(projeto)
            except ValueError as e:
                return 409, {"ok": False, "erro": str(e)}
            return 200, {"ok": True, "projeto": projeto, "url": site_previa.url_previa(str(dados.get("caminho") or "/"))}
        url = str(dados.get("url") or "").strip()
        if url and not url.lower().startswith(("http://", "https://")):
            return 400, {"erro": "url deve começar com http:// ou https://"}
        rotina = _limpar_nome(dados.get("rotina") or "Teste do site")
        so_problema, quer_aviso = bool(dados.get("so_se_problema")), bool(dados.get("avisar", True))

        def _testar():
            ok, saida, d = site_previa.rodar("testar", projeto, alvo=url or None)
            if not d:
                resultado = "o teste não terminou: " + saida[-400:]
                if quer_aviso:
                    avisar_telegram(f"🧪 {rotina} · {projeto}\n⚠️ {resultado}")
            else:
                c = d.get("contagem") or {}
                problema = c.get("CRÍTICO", 0) or c.get("ALTO", 0) or (d.get("jornadas") or {}).get("falhas", 0)
                resultado = f"nota {d.get('nota')}/100 · críticos {c.get('CRÍTICO', 0)} · altos {c.get('ALTO', 0)}"
                if quer_aviso and (problema or not so_problema):
                    avisar_telegram(f"🔁 {rotina} · {projeto}{' · ' + url if url else ''}\n\n" + site_previa.resumo_teste(d, 3500))
                    for cam in (d.get("prints_abs") or [])[:4]:
                        avisar_telegram_foto(cam, os.path.basename(cam))
            registrar({"id": f"{time.time():.3f}", "rotina": rotina, "acao": acao, "projeto": projeto,
                       "pedido": url or "pasta do projeto", "ok": bool(d), "resultado": resultado,
                       "quando": time.strftime("%Y-%m-%d %H:%M:%S")})
            publicar({"tipo": "info", "texto": f"🔁 Rotina “{rotina}”: {resultado}",
                      "prints": [x["arquivo"] for x in (d or {}).get("prints") or []]}, projeto)
        if dados.get("esperar"):
            _testar()
            d = site_previa.ultima(projeto) or {}
            return 200, {"ok": True, "nota": d.get("nota"), "contagem": d.get("contagem"), "jornadas": d.get("jornadas"),
                         "relatorio": d.get("relatorio_texto", "")[:8000]}
        threading.Thread(target=_testar, daemon=True).start()
        return 202, {"ok": True, "status": f"testando {url or projeto}; o resultado chega no Telegram"}
    if acao == "atendimento_cmd":  # /atendimento, /assumir, /devolver vindos do Telegram
        import atendimento
        cmd = str(dados.get("cmd") or "/atendimento")
        if cmd not in ("/atendimento", "/assumir", "/devolver", "/whatsapp"):
            return 400, {"erro": "comando inválido"}
        return 200, {"ok": True, "texto": atendimento.comando(cmd, str(dados.get("arg") or ""), local=True)}
    if acao == "pagamento":  # mensagem "PAGAMENTO FASTFLOW RECEBIDO" (Telegram ou n8n)
        import pagamentos
        r = pagamentos.processar(str(dados.get("texto", ""))[:4000], fonte=str(dados.get("fonte") or "gatilho"))
        return (200 if r.get("ok") or r.get("repetido") else 422), r
    if acao in ("painel_consultar", "painel_teste"):  # para fluxos do n8n
        import painel_api
        try:
            if acao == "painel_consultar":
                return 200, dict(painel_api.consultar(dados.get("login")), ok=True)
            return 200, dict(painel_api.criar_teste(dados.get("telefone")), ok=True)
        except painel_api.ErroPainel as e:
            return 422, {"ok": False, "erro": str(e)}
    rotina = _limpar_nome(dados.get("rotina"))
    texto = str(dados.get("texto", ""))[:4000].strip()
    projeto = str(dados.get("projeto") or estado.ler()["projeto"] or "")
    if projeto and projeto not in core.listar_projetos():
        return 400, {"erro": f"projeto “{projeto}” não existe"}
    quer_aviso, esperar = bool(dados.get("avisar")), bool(dados.get("esperar"))
    if acao not in ("status",) and not texto:
        return 400, {"erro": "falta o texto do pedido"}
    base = {"id": f"{time.time():.3f}", "rotina": rotina, "acao": acao, "projeto": projeto, "pedido": texto[:200],
            "quando": time.strftime("%Y-%m-%d %H:%M:%S")}

    def concluir(ok, resultado):
        registrar(dict(base, ok=ok, resultado=resultado[:1500], fim=time.strftime("%Y-%m-%d %H:%M:%S")))
        publicar({"tipo": "info" if ok else "erro", "texto": f"🔁 Rotina “{rotina}” ({acao}):\n\n{resultado}"}, projeto or None)
        if quer_aviso:
            avisar_telegram(f"🔁 {rotina}\n\n{resultado}")

    if acao == "status":
        ativos = pool.resumo()
        return 200, {"ok": True, "rodando": ativos, "rotinas": listar(5)}
    if acao == "avisar":
        ok = avisar_telegram(f"🔁 {rotina}\n\n{texto}")
        registrar(dict(base, ok=ok, resultado="aviso enviado" if ok else "Telegram não configurado"))
        return (200 if ok else 503), {"ok": ok}
    if acao == "ideia":
        import kb
        caminho = kb.salvar("ideias", texto.split("\n")[0][:70], texto, tags=["rotina", rotina], projeto=projeto)
        concluir(True, f"Nota salva: {caminho}")
        return 200, {"ok": True, "caminho": caminho}

    publicar({"tipo": "sistema", "texto": f"🔁 Rotina “{rotina}” recebida ({acao})"}, projeto or None)
    registrar(dict(base, ok=None, resultado="iniciada"))
    pronto, saida = threading.Event(), {}

    chave = projeto if acao == "jarvis" else "_pesquisa" if acao in ("pesquisar", "tendencias") else None

    def tarefa():
        try:
            if chave:  # projeto ocupado: espera a vez (até 30 min) em vez de falhar
                limite, avisado = time.time() + 1800, False
                while not pool.pode_iniciar(chave)[0]:
                    if time.time() > limite:
                        raise RuntimeError("o projeto ficou ocupado por mais de 30 minutos; rotina cancelada")
                    if not avisado:
                        publicar({"tipo": "sistema", "texto": f"🔁 Rotina “{rotina}” na fila: esperando o trabalho atual terminar"},
                                 projeto or None)
                        avisado = True
                    time.sleep(15)
            if acao == "hermes":
                import hermes_cliente as hermes
                try:
                    r = hermes.perguntar(texto, projeto or None)
                    saida.update(ok=True, resultado=r)
                except hermes.ErroHermes as e:
                    saida.update(ok=False, resultado=f"Hermes: {e}")
            elif acao in ("pesquisar", "tendencias"):
                import kb
                destino, prompt = (kb.prompt_tendencias if acao == "tendencias" else kb.prompt_pesquisa)(texto)
                final = {}
                pool.de("_pesquisa").rodar(estado, prompt, False, lambda ev: final.update(ev) if ev["tipo"] == "resposta" else None,
                                           cwd=kb.KB_DIR, usar_sessao=False, projeto=projeto or None)
                kb.sincronizar()
                saida.update(ok=not final.get("erro"), resultado=(final.get("texto") or "pesquisa concluída")
                             + (f"\n\nSalva em: {os.path.relpath(destino, kb.KB_DIR)}" if os.path.exists(destino) else ""))
            elif acao == "jarvis":
                final = {}

                def ao_evento(ev):
                    if ev["tipo"] == "resposta":
                        final.update(ev)
                    elif ev["tipo"] not in ("inicio",):
                        publicar(ev, projeto)
                pool.de(projeto).rodar(estado, texto, False, ao_evento, usar_sessao=False, projeto=projeto,
                                       sistema=core.REGRAS_ROTINA, extra=core.BLOQUEIOS_ROTINA)
                saida.update(ok=bool(final) and not final.get("erro"), resultado=final.get("texto") or "sem resposta")
        except Exception as e:  # noqa: BLE001
            saida.update(ok=False, resultado=f"falhou: {type(e).__name__}: {e}")
        finally:
            concluir(saida.get("ok", False), saida.get("resultado", ""))
            pronto.set()

    if acao == "jarvis" and not projeto:
        return 400, {"erro": "informe o projeto"}
    na_fila = bool(chave) and not pool.pode_iniciar(chave)[0]
    threading.Thread(target=tarefa, daemon=True).start()
    if esperar:
        pronto.wait(timeout=900)
        return 200, {"ok": saida.get("ok", False), "resultado": saida.get("resultado", "ainda rodando")}
    return 202, {"ok": True, "status": "na fila" if na_fila else "iniciada", "rotina": rotina}
