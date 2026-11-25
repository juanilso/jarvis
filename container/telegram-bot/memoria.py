"""Memória contínua do Jarvis: o que ele aprende nas conversas, guardado para sempre e lido em todo trabalho.

Duas camadas, dentro da base de conhecimento (sincronizada com o GitHub):
- memoria/geral.md: vale para todos os projetos (preferências, hospedagem, forma de deploy, padrões, contas usadas…)
- memoria/projetos/<projeto>.md: o escopo e o que foi configurado/decidido em cada projeto

Cada linha é um fato com uma chave: "- **hospedagem**: … _(2026-11-25)_". Quando um fato muda, a versão antiga
vai para memoria/historico.md (nada se perde). Senhas, tokens e chaves nunca são guardados.
"""
import datetime
import json
import os
import re
import subprocess
import sys
import threading

import kb

DIR = os.path.join(kb.KB_DIR, "memoria")
LINHA = re.compile(r"^- \*\*(.+?)\*\*: (.*?)(?: _\((\d{4}-\d\d-\d\d)\)_)?\s*$")
LIMITE_CTX = 7000  # caracteres de cada camada que entram no prompt (os fatos mais novos têm prioridade)
_trava = threading.Lock()

CABECALHO = {
    None: "# Memória geral do Jarvis\n\nFatos que valem para todos os projetos. O Jarvis lê isto antes de cada trabalho.\n\n",
    "projeto": "# Memória do projeto {p}\n\nEscopo, configurações e decisões deste projeto. O Jarvis lê isto antes de cada trabalho.\n\n",
}


class Recusado(Exception):
    pass


def _slug(t):
    return kb.slug(t or "", 40)


def _arq(projeto=None):
    return os.path.join(DIR, "projetos", _slug(projeto) + ".md") if projeto else os.path.join(DIR, "geral.md")


def ler(projeto=None):
    """Fatos em ordem: {chave: {"texto", "data"}}."""
    fatos = {}
    try:
        with open(_arq(projeto), encoding="utf-8") as f:
            for ln in f:
                m = LINHA.match(ln.rstrip("\n"))
                if m:
                    fatos[m.group(1)] = {"texto": m.group(2), "data": m.group(3) or ""}
    except FileNotFoundError:
        pass
    return fatos


def _gravar(projeto, fatos):
    caminho = _arq(projeto)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    cab = CABECALHO[None] if not projeto else CABECALHO["projeto"].format(p=projeto)
    corpo = "".join(f"- **{k}**: {v['texto']} _({v['data']})_\n" for k, v in fatos.items())
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(cab + corpo)
    os.replace(tmp, caminho)


def _historico(projeto, chave, antigo, novo):
    os.makedirs(DIR, exist_ok=True)
    hoje = datetime.date.today().isoformat()
    with open(os.path.join(DIR, "historico.md"), "a", encoding="utf-8") as f:
        f.write(f"- {hoje} [{projeto or 'geral'}] **{chave}**: {antigo} → {novo or '(esquecido)'}\n")


def _limpar(texto):
    """Nunca guarda segredos: apaga tokens/senhas; recusa chave privada."""
    texto = " ".join((texto or "").split())[:600]
    try:
        import ajudantes
        texto, _ = ajudantes.redigir(texto)
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001  (ajudantes.Recusado: chave privada)
        raise Recusado(str(e))
    texto = re.sub(r"(?i)\b(senha|password|token|api[_ -]?key|segredo)\s*[:=]\s*\S+", r"\1: [apagado]", texto)
    if len(re.sub(r"\[[^\]]*\]|\b(senha|password|token|api[_ -]?key|segredo)\b|[^\w]", "", texto, flags=re.I)) < 8:
        raise Recusado("sobrou só dado sensível: isso não vai para a memória")
    return texto


def anotar(texto, chave=None, projeto=None, sincronizar=True):
    """Guarda (ou atualiza) um fato. Devolve {"chave", "novo", "antigo"}."""
    texto = _limpar(texto)
    if len(texto) < 3:
        raise ValueError("texto vazio")
    chave = " ".join((chave or "").split())[:60] or " ".join(texto.split()[:5])[:60]
    chave = chave.strip(" :*").lower()
    with _trava:
        fatos = ler(projeto)
        antigo = fatos.get(chave, {}).get("texto")
        if antigo == texto:
            return {"chave": chave, "novo": False, "antigo": None}
        if antigo:
            _historico(projeto, chave, antigo, texto)
            fatos.pop(chave)
        fatos[chave] = {"texto": texto, "data": datetime.date.today().isoformat()}  # o mais novo vai para o fim
        _gravar(projeto, fatos)
    if sincronizar:
        _sincronizar()
    return {"chave": chave, "novo": not antigo, "antigo": antigo}


def esquecer(chave, projeto=None):
    chave = chave.strip().lower()
    with _trava:
        fatos = ler(projeto)
        alvo = chave if chave in fatos else next((k for k in fatos if chave in k), None)
        if not alvo:
            return None
        _historico(projeto, alvo, fatos.pop(alvo)["texto"], None)
        _gravar(projeto, fatos)
    _sincronizar()
    return alvo


def buscar(termo):
    """Procura em todas as memórias (geral e de todos os projetos)."""
    termo = termo.lower()
    achados = []
    for projeto in [None] + projetos():
        for k, v in ler(projeto).items():
            if termo in k.lower() or termo in v["texto"].lower():
                achados.append({"projeto": projeto, "chave": k, **v})
    return achados


def projetos():
    pasta = os.path.join(DIR, "projetos")
    try:
        return sorted(n[:-3] for n in os.listdir(pasta) if n.endswith(".md"))
    except FileNotFoundError:
        return []


def _bloco(fatos, limite):
    linhas = [f"- {k}: {v['texto']}" for k, v in fatos.items()]
    saida, total = [], 0
    for ln in reversed(linhas):  # os mais novos primeiro, até o limite
        if total + len(ln) > limite:
            break
        saida.insert(0, ln)
        total += len(ln) + 1
    return "\n".join(saida)


REGRA = """MEMÓRIA CONTÍNUA (sua memória de longo prazo, entre conversas e entre projetos):
- Acima está o que você já sabe. Parta disso: não pergunte de novo o que já está na memória. Se o pedido parecer
  diferente do que está guardado (outra hospedagem, outro padrão, outro escopo), pergunte em uma linha antes de seguir:
  "Na memória está X; agora é Y?". Confirmada a mudança, atualize o fato com a MESMA chave.
- Sempre que a conversa trouxer algo durável, anote na hora, sem pedir licença:
  `jarvis-memoria anotar --geral --chave "<assunto curto>" "<fato em uma frase>"` → vale para todos os projetos
  (preferências do usuário, hospedagem, forma de deploy, padrões de código, serviços/contas usados, como ele gosta
  das respostas).
  `jarvis-memoria anotar --projeto "<projeto>" --chave "<assunto>" "<fato>"` → só deste projeto (escopo, regras de
  negócio, configurações feitas, integrações, decisões, problemas resolvidos e a causa).
  Use chaves estáveis e curtas (ex.: "hospedagem", "deploy", "banco de dados", "login", "cores da marca").
- Não anote o passageiro (status de uma tarefa, conversa fiada) e NUNCA anote senhas, tokens, chaves ou dados
  pessoais de clientes. Na resposta final, se anotou algo, diga em uma linha: "🧠 Anotei: …"."""


def contexto(projeto=None):
    """Texto que entra no prompt de cada execução."""
    partes = []
    g = _bloco(ler(None), LIMITE_CTX)
    if g:
        partes.append("## O que você já sabe (memória geral, todos os projetos)\n" + g)
    if projeto:
        p = _bloco(ler(projeto), LIMITE_CTX)
        partes.append(f"## Memória do projeto {projeto}\n" + (p or "(ainda vazia: este projeto é novo para você)"))
        outros = [x for x in projetos() if x != _slug(projeto)]
        if outros:
            partes.append("Outros projetos com memória (consulte com `jarvis-memoria ver --projeto <nome>` quando o "
                          "pedido for parecido e der para reaproveitar): " + ", ".join(outros[:40]))
    return "\n\n".join(partes + [REGRA])


# ------------------------------------------------------------ revisão automática ao fim da conversa

PEDIDO_REVISAO = """Você cuida da memória de longo prazo de um assistente de desenvolvimento (o Jarvis).
Abaixo estão a memória atual e a última troca de mensagens. Extraia SÓ fatos duráveis que ainda não estão na memória
ou que mudaram: preferências do usuário, hospedagem, deploy, padrões, serviços usados, escopo do projeto,
configurações feitas, decisões e problemas resolvidos (com a causa). Ignore o passageiro e NUNCA inclua senhas,
tokens ou dados pessoais de clientes.
Responda APENAS com JSON: [{"escopo": "geral"|"projeto", "chave": "assunto curto", "texto": "fato em uma frase"}]
Use a MESMA chave de um fato existente quando ele mudou. Nada novo: []

# Projeto atual: {projeto}
# Memória atual
{memoria}

# Mensagem do usuário
{pedido}

# Resposta do assistente
{resposta}"""


def revisar(projeto, pedido, resposta, modelo="claude-haiku-5-5"):
    """Pega o que o Jarvis esqueceu de anotar. Roda em segundo plano, com modelo pequeno."""
    if not pedido or pedido.startswith("/") or len(pedido) < 12 or not resposta:
        return []
    mem = "\n".join(filter(None, [_bloco(ler(None), 3000), _bloco(ler(projeto), 3000) if projeto else ""])) or "(vazia)"
    try:
        import ajudantes
        p, _ = ajudantes.redigir(pedido[:3000])
        resp, _ = ajudantes.redigir(resposta[:4000])
    except Exception:  # noqa: BLE001  (chave privada no texto: não revisa)
        return []
    prompt = PEDIDO_REVISAO.replace("{projeto}", projeto or "(nenhum)").replace("{memoria}", mem) \
        .replace("{pedido}", p).replace("{resposta}", resp)
    try:
        r = subprocess.run(["claude", "-p", prompt, "--model", modelo, "--effort", "low", "--max-turns", "1",
                            "--output-format", "json"], capture_output=True, text=True, timeout=180,
                           env={**os.environ, "JARVIS_EXECUCAO": "memoria"}, cwd=kb.KB_DIR if os.path.isdir(kb.KB_DIR) else None)
        saida = json.loads(r.stdout or "{}").get("result") or ""
        m = re.search(r"\[.*\]", saida, re.S)
        itens = json.loads(m.group(0)) if m else []
    except Exception as e:  # noqa: BLE001
        print("memória: revisão falhou:", type(e).__name__, str(e)[:200], flush=True)
        return []
    feitos = []
    for it in itens[:8] if isinstance(itens, list) else []:
        if not isinstance(it, dict) or not it.get("texto"):
            continue
        try:
            alvo = projeto if it.get("escopo") == "projeto" and projeto else None
            res = anotar(it["texto"], it.get("chave"), alvo, sincronizar=False)
            if res["novo"] or res["antigo"]:
                feitos.append((alvo, res["chave"]))
        except (Recusado, ValueError):
            continue
    if feitos:
        _sincronizar()
    return feitos


def revisar_depois(projeto, pedido, resposta):
    import cerebro
    if cerebro.ler().get("memoria") != "auto":
        return
    threading.Thread(target=revisar, args=(projeto, pedido, resposta), daemon=True).start()


def _sincronizar():
    try:
        if os.path.isdir(os.path.join(kb.KB_DIR, ".git")):
            kb.sincronizar_depois()
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------ comando /memoria (Telegram e painel)

def comando(arg, projeto=None):
    arg = (arg or "").strip()
    acao, _, resto = arg.partition(" ")
    acao = acao.lower()
    if acao in ("esquecer", "apagar"):
        geral = resto.startswith("geral ")
        alvo = esquecer(resto[6:] if geral else resto, None if geral else projeto) or \
            (None if geral else esquecer(resto, None))
        return f"🧠 Esqueci “{alvo}” (fica no histórico)." if alvo else f"Não achei “{resto}” na memória."
    if acao in ("anotar", "lembre", "guardar"):
        geral = resto.startswith("geral ")
        try:
            r = anotar(resto[6:] if geral else resto, None, None if geral else projeto)
        except (Recusado, ValueError) as e:
            return f"Não guardei: {e}"
        return f"🧠 Anotado ({'geral' if geral or not projeto else projeto}): {r['chave']}"
    if acao in ("buscar", "procurar") or (arg and acao not in ("ver", "geral")):
        termo = resto if acao in ("buscar", "procurar") else arg
        ach = buscar(termo)
        if not ach:
            return f"Nada sobre “{termo}” na memória."
        return "🧠 Na memória:\n" + "\n".join(f"• [{a['projeto'] or 'geral'}] {a['chave']}: {a['texto']}" for a in ach[:15])
    g, p = ler(None), ler(projeto) if projeto else {}
    linhas = ["🧠 Memória do Jarvis", f"\nGeral ({len(g)}):"] + [f"• {k}: {v['texto']}" for k, v in list(g.items())[-20:]]
    if projeto:
        linhas += [f"\nProjeto {projeto} ({len(p)}):"] + [f"• {k}: {v['texto']}" for k, v in list(p.items())[-20:]]
    if not g and not p:
        linhas.append("(vazia: ela vai se enchendo sozinha conforme vocês conversam)")
    linhas.append("\n/memoria <termo> · /memoria anotar [geral] <fato> · /memoria esquecer [geral] <assunto>")
    return "\n".join(linhas)


# ------------------------------------------------------------ linha de comando (jarvis-memoria)

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="jarvis-memoria", description="Memória contínua do Jarvis")
    sub = ap.add_subparsers(dest="acao", required=True)
    for nome in ("ver", "contexto"):
        s = sub.add_parser(nome)
        s.add_argument("--projeto")
    s = sub.add_parser("anotar")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--geral", action="store_true")
    g.add_argument("--projeto")
    s.add_argument("--chave")
    s.add_argument("texto", nargs="+")
    s = sub.add_parser("esquecer")
    s.add_argument("--projeto")
    s.add_argument("chave", nargs="+")
    s = sub.add_parser("buscar")
    s.add_argument("termo", nargs="+")
    a = ap.parse_args(argv)
    if a.acao == "contexto":
        print(contexto(a.projeto))
    elif a.acao == "ver":
        print(comando("ver", a.projeto))
    elif a.acao == "anotar":
        try:
            r = anotar(" ".join(a.texto), a.chave, None if a.geral else a.projeto)
        except (Recusado, ValueError) as e:
            print("não guardei:", e)
            return 1
        print(("atualizado" if r["antigo"] else "anotado" if r["novo"] else "já estava igual") + f": {r['chave']}")
    elif a.acao == "esquecer":
        alvo = esquecer(" ".join(a.chave), a.projeto)
        print(f"esquecido: {alvo}" if alvo else "não encontrei")
    elif a.acao == "buscar":
        for x in buscar(" ".join(a.termo)):
            print(f"[{x['projeto'] or 'geral'}] {x['chave']}: {x['texto']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
