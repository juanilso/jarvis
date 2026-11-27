"""Agente de atendimento do WhatsApp: um agente que você TREINA conversando (painel → 📱 Atendente, ou /atendente).

Ele não é só "um prompt": tem memória da conversa com você (sessão própria, igual nos dois lugares), lê as conversas
reais do robô, guarda cada decisão que você tomou (decisoes.md) e mantém os PROCEDIMENTOS (como agir em cada situação,
com prioridade sobre a base). Quando você ensina algo, ele procura conflito com o que você já disse (e te lembra),
escreve a mudança, testa como o robô responderia antes/depois e só aplica quando você confirma. Backup e desfazer sempre.

Arquivos (por número de WhatsApp): <pasta do atendimento>/agente/
  procedimentos.md · decisoes.md · pendente.json · versoes/ · conversa.jsonl (o chat com você)
O robô lê: procedimentos.md (prioridade) + a base de respostas de sempre.
"""
import datetime
import difflib
import json
import os
import re
import shutil
import sys
import threading
import time

_ocupado = {}
_trava = threading.Lock()

CABECALHO_PROC = """# Procedimentos do atendimento

Como agir em cada situação, ensinado pelo dono (prioridade sobre a base de respostas).
Formato: "## Situação" e, embaixo, o que fazer, em frases curtas e diretas.

"""

NOME = "Juliana"
AGENTE = """Você é a JULIANA, a agente de atendimento do WhatsApp do usuário (número {linha}); você é mulher e fala
no feminino. Você não atende os clientes
diretamente: quem atende é o robô, que segue os PROCEDIMENTOS e a BASE que você mantém. Seu papel é ser o
supervisor/treinador desse robô junto com o dono: conversar com ele, entender como ele quer que o atendimento seja,
transformar isso em procedimentos claros e acompanhar as conversas reais para melhorar sempre.

Ferramenta (rode no terminal): jarvis-atendimento --linha {linha} <ação>
  ver procedimentos | ver base | ver decisoes      → o que o robô segue hoje e o que o dono já decidiu
  conversas [--dias 3] [--busca termo]            → conversas reais recentes (telefones ocultos)
  propor procedimentos|base <arquivo.md> --motivo "…"  → guarda a nova versão COMPLETA como proposta e mostra o diff
  simular "mensagem do cliente" [--historico "cliente: …|robô: …"] [--proposta]  → como o robô responderia
  pendente | aplicar | descartar | desfazer        → aplicar SÓ depois do "ok" do dono (backup automático)
  decisao "o que o dono definiu"                   → registra a decisão (data + texto)
  assumir <número> | devolver <número>             → cala o robô numa conversa (o dono atende) / devolve ao robô
  responder <número> "texto"                       → manda ao cliente EXATAMENTE o que o dono pediu para dizer

Como trabalhar quando o dono ensina ou corrige algo:
1. Entenda a intenção (ex.: "na renovação não pergunte o app: todos usam o mesmo login").
2. Confira `ver decisoes`, `ver procedimentos` e `ver base`. Se algo contradiz (inclusive algo que ele disse antes),
   LEMBRE com data: "Em 12/11 você definiu X; agora é Y? Troco?" e espere a resposta.
3. Escreva a mudança mínima: COMO AGIR vai em procedimentos (## Situação + passos curtos); INFORMAÇÃO (preços, apps,
   horários) vai na base. Copie o arquivo atual para um arquivo de trabalho, edite, e use `propor` com ele completo.
4. Rode `simular` com 1 ou 2 mensagens típicas de cliente, com e sem --proposta, para mostrar a diferença.
5. Mostre ao dono, curto: o que muda (2-4 linhas), a resposta antes → depois, e pergunte "Posso aplicar?".
6. Com o "ok/pode/aplica", rode `aplicar` e `decisao "…"`. Se ele pedir para voltar: `desfazer`.

Quando ele perguntar como está o atendimento, leia `conversas`, aponte com exemplos curtos onde o robô foi longo,
perguntou demais, não entendeu ou fugiu do procedimento, e PROPONHA ajustes (sem aplicar). Sugira também o que você
notar sozinho: perguntas que se repetem, informação que falta na base, algo que ele disse diferente em momentos
diferentes.

Estilo do robô que você deve buscar: direto, humano, curto; pergunta só o necessário para o PRÓXIMO passo; nunca
coleta dado "por garantia"; uma pergunta por vez; sem menu quando o cliente já disse o que quer.

Conversa por voz: quando a mensagem começar com [POR VOZ], o dono está falando com você por áudio e a sua resposta
vai virar áudio (com a mesma voz do atendimento). Responda como numa conversa falada: natural, calorosa, frases
curtas, sem listas, sem diff, sem códigos e sem emojis; no máximo umas 5 frases. Se precisar mostrar detalhes (o
trecho que muda, o teste antes/depois), diga em uma frase que deixou os detalhes por escrito e coloque-os depois de
uma linha com apenas "---" (o que vem depois do --- não é falado).

Conversa pelo WhatsApp: quando a mensagem começar com [Você está falando com o dono pelo WhatsApp…], ele está te
respondendo no WhatsApp, muitas vezes sobre um aviso seu ("cliente X precisa de você"). Lá você pode agir pela ferramenta:
"assume" → `assumir <número>`; "devolve" → `devolver <número>`; "diz pra ele que…" → `responder <número> "texto"` com
o texto já pronto para o cliente (curto, educado, no estilo do atendimento) e confirme em uma linha o que mandou.
Se não der para saber de qual cliente ele fala, pergunte. Responda curto, como mensagem de WhatsApp.

Regras: responda ao dono em português do Brasil, curto e organizado. Nunca invente preço, prazo ou política: pergunte
a ele. Você só manda mensagem a um cliente quando o dono pedir (com `responder`), nunca por conta própria. Não repita
telefones de clientes sem necessidade. Mexa só nos arquivos do atendimento
(pela ferramenta); não altere código nem outros projetos."""


# ------------------------------------------------------------------ arquivos

def at_linha(linha=1):
    import linhas
    return linhas.modulos(linha)[0]


def pasta(at):
    p = os.path.join(at.DIR, "agente")
    os.makedirs(os.path.join(p, "versoes"), exist_ok=True)
    return p


def arq_proc(at):
    return os.path.join(pasta(at), "procedimentos.md")


def ler_proc(at):
    try:
        with open(arq_proc(at), encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _arquivo(at, qual):
    if qual in ("procedimentos", "proc"):
        return arq_proc(at)
    if qual == "base":
        return at.FAQ
    if qual in ("decisoes", "decisões"):
        return os.path.join(pasta(at), "decisoes.md")
    raise ValueError("use: procedimentos, base ou decisoes")


def _ler(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _escrever(caminho, texto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(tmp, caminho)


TELEFONE = re.compile(r"\b\d{10,13}\b")


def conversas(at, dias=3, busca="", limite=30000):
    import treinador
    blocos, total = treinador.conversas(at, dias=dias, limite_chars=10 ** 7)
    if busca:
        blocos = [b for b in blocos if busca.lower() in b.lower()]
    saida, n = [], 0
    for b in blocos:
        if n + len(b) > limite:
            break
        saida.append(TELEFONE.sub("[telefone]", b))
        n += len(b)
    return f"{len(saida)} de {total} conversa(s) dos últimos {dias} dia(s)" + (f" com “{busca}”" if busca else "") + \
        ":\n\n" + "\n\n".join(saida)


def propor(at, qual, novo_texto, motivo):
    caminho = _arquivo(at, qual)
    if qual in ("decisoes", "decisões"):
        raise ValueError("decisões entram com `decisao`, não com proposta")
    if qual in ("procedimentos", "proc") and not novo_texto.lstrip().startswith("# Procedimentos"):
        novo_texto = CABECALHO_PROC + novo_texto
    atual = _ler(caminho)
    _escrever(os.path.join(pasta(at), "pendente.json"),
              json.dumps({"qual": "procedimentos" if qual == "proc" else qual, "texto": novo_texto, "motivo": motivo,
                          "quando": time.strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False))
    diff = "".join(difflib.unified_diff(atual.splitlines(True), novo_texto.splitlines(True), "atual", "proposta", n=1))
    return diff or "(sem diferença)"


def pendente(at):
    try:
        return json.loads(_ler(os.path.join(pasta(at), "pendente.json")) or "null")
    except ValueError:
        return None


def aplicar(at):
    p = pendente(at)
    if not p:
        raise ValueError("não há proposta pendente")
    caminho = _arquivo(at, p["qual"])
    marca = time.strftime("%Y%m%d-%H%M%S")
    if os.path.exists(caminho):
        shutil.copy2(caminho, os.path.join(pasta(at), "versoes", f"{p['qual']}-{marca}.md"))
    else:  # não existia: o "desfazer" volta a não ter nada
        _escrever(os.path.join(pasta(at), "versoes", f"{p['qual']}-{marca}.md"), "")
    _escrever(caminho, p["texto"])
    os.remove(os.path.join(pasta(at), "pendente.json"))
    registrar_decisao(at, f"[aplicado em {p['qual']}] {p['motivo']}")
    return p


def descartar(at):
    try:
        os.remove(os.path.join(pasta(at), "pendente.json"))
        return True
    except FileNotFoundError:
        return False


def desfazer(at):
    vs = sorted(os.listdir(os.path.join(pasta(at), "versoes")))
    if not vs:
        raise ValueError("não há versão anterior guardada")
    ultima = vs[-1]
    qual = ultima.split("-", 1)[0]
    caminho = _arquivo(at, qual)
    shutil.copy2(os.path.join(pasta(at), "versoes", ultima), caminho)
    os.rename(os.path.join(pasta(at), "versoes", ultima), os.path.join(pasta(at), "versoes", "desfeito-" + ultima))
    registrar_decisao(at, f"[desfeito] voltou {qual} para a versão de {ultima[len(qual) + 1:-3]}")
    return qual


def registrar_decisao(at, texto):
    caminho = _arquivo(at, "decisoes")
    if not os.path.exists(caminho):
        _escrever(caminho, "# Decisões do dono sobre o atendimento\n\n")
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(f"- {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} — {' '.join(texto.split())}\n")


def simular(at, mensagem, historico="", proposta=False):
    """Como o robô responderia (sem mandar nada a ninguém)."""
    msgs = []
    for parte in [x.strip() for x in historico.split("|") if x.strip()]:
        quem, _, txt = parte.partition(":")
        msgs.append({"p": "bot" if quem.strip().lower() in ("robô", "robo", "bot", "atendente") else "cliente",
                     "x": txt.strip() or parte})
    msgs.append({"p": "cliente", "x": mensagem})
    proc, base = ler_proc(at), at.ler_faq()
    p = pendente(at) if proposta else None
    if p:
        if p["qual"] == "procedimentos":
            proc = p["texto"]
        elif p["qual"] == "base":
            base = p["texto"]
    bruto = at._perguntar_modelo(msgs, base, "", procedimentos=proc)
    resposta, _ficha = at.separar_saida(bruto)
    return (resposta or bruto).replace("[[HUMANO]]", "\n(→ chamaria você)").replace("[[AUDIO]]", "").strip()


# ------------------------------------------------------------------ conversa com o dono (painel e Telegram)

def _arq_conversa(at):
    return os.path.join(pasta(at), "conversa.jsonl")


def historico_chat(at, n=60):
    try:
        with open(_arq_conversa(at), encoding="utf-8") as f:
            linhas = f.readlines()[-n:]
        return [json.loads(x) for x in linhas]
    except (OSError, ValueError):
        return []


def _anotar_chat(at, quem, texto, origem, voz=False, audio=""):
    reg = {"t": time.time(), "quem": quem, "texto": texto, "origem": origem}
    if voz:
        reg["voz"] = True
    if audio:
        reg["audio"] = audio
    with open(_arq_conversa(at), "a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")


def ocupado(linha):
    return _ocupado.get(int(linha or 1), 0) > time.time()


def falar(at, texto):
    """Gera a voz da Juliana (mesma voz do atendimento) para a parte falada da resposta. Devolve o nome do mp3."""
    import elevenlabs
    falado = texto.split("\n---", 1)[0].strip()
    if not falado:
        return ""
    mp3, _ = elevenlabs.gerar_audio(falado, "mp3")
    nome = f"voz-{int(time.time() * 1000)}.mp3"
    pasta_voz = os.path.join(pasta(at), "voz")
    os.makedirs(pasta_voz, exist_ok=True)
    with open(os.path.join(pasta_voz, nome), "wb") as f:
        f.write(mp3)
    for velho in sorted(os.listdir(pasta_voz))[:-40]:  # guarda só os últimos 40 áudios
        os.remove(os.path.join(pasta_voz, velho))
    return nome


def arquivo_voz(linha, nome):
    at = at_linha(linha)
    c = os.path.join(pasta(at), "voz", os.path.basename(nome))
    return c if os.path.isfile(c) else ""


def conversar(texto, linha=1, origem="painel", avisar=None, voz=False, gerar_audio=True):
    """Manda a mensagem do dono para a Juliana (bloqueante). avisar(texto, audio_mp3_ou_vazio) recebe a resposta.
    voz=True: o dono falou por áudio e a resposta volta também em áudio."""
    import jarvis_core as core
    linha = int(linha or 1)
    at = at_linha(linha)
    with _trava:
        if ocupado(linha):
            raise RuntimeError("o agente ainda está respondendo a mensagem anterior")
        _ocupado[linha] = time.time() + 900
    _anotar_chat(at, "dono", texto, origem, voz=voz)
    resposta, erros = [], []

    def ev(e):
        if e.get("tipo") == "resposta" and e.get("texto"):
            resposta.append(e["texto"])
        elif e.get("tipo") == "erro":
            erros.append(e.get("texto", "erro"))
    try:
        est = core.Estado(f"atendente-{linha}")
        core.Execucao().rodar(est, ("[POR VOZ] " if voz else "") + texto, False, ev, cwd=pasta(at), projeto=f"atendente-{linha}",
                              sistema=AGENTE.format(linha=linha), orquestrador=False)
    finally:
        _ocupado.pop(linha, None)
    final = "\n\n".join(resposta).strip() or ("⚠ " + "; ".join(erros) if erros else "(sem resposta)")
    audio = ""
    if voz and resposta and gerar_audio:
        try:
            audio = falar(at, final)
        except Exception as e:  # noqa: BLE001
            print("juliana: não consegui gerar a voz:", type(e).__name__, str(e)[:150], flush=True)
    _anotar_chat(at, "agente", final.replace("\n---", "\n\n📋", 1), origem, audio=audio)
    if avisar:
        avisar(final.replace("\n---", "\n\n📋", 1), os.path.join(pasta(at), "voz", audio) if audio else "")
    return final


def comando(arg, origem="telegram", avisar=None):
    """/atendente [2] <mensagem>  ·  /atendente (status)"""
    arg = (arg or "").strip()
    linha = 1
    m = re.match(r"^([12])\s+(.*)$", arg, re.S)
    if m:
        linha, arg = int(m.group(1)), m.group(2).strip()
    at = at_linha(linha)
    if not arg or arg.lower() in ("status", "ajuda"):
        p = pendente(at)
        dec = [x for x in _ler(_arquivo(at, "decisoes")).splitlines() if x.startswith("- ")][-5:]
        return (f"📱 {NOME}, agente de atendimento" + (f" (número {linha})" if linha != 1 else "") + "\n"
                + ("⏳ Proposta esperando seu ok: " + p["motivo"] + "\n" if p else "")
                + ("Últimas decisões:\n" + "\n".join(dec) if dec else "Ainda não há decisões registradas.")
                + "\n\nConverse: /juliana (entra no modo conversa: texto ou ÁUDIO vão para ela, e ela responde por voz)"
                  "\nou /juliana <mensagem> · número 2: /juliana 2 … · sair do modo: /juliana sair"), None
    if ocupado(linha):
        return "⏳ O agente ainda está respondendo a sua mensagem anterior.", None
    threading.Thread(target=lambda: _seguro(conversar, arg, linha, origem, avisar), daemon=True).start()
    return f"📱 {NOME}: pensando…", None


def _seguro(f, *a, **k):
    try:
        f(*a, **k)
    except Exception as e:  # noqa: BLE001
        avisar = a[3] if len(a) >= 4 else k.get("avisar")
        if avisar:
            avisar(f"⚠ {type(e).__name__}: {str(e)[:200]}", "")


# ------------------------------------------------------------------ linha de comando (para o próprio agente)

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="jarvis-atendimento")
    ap.add_argument("--linha", type=int, default=1)
    sub = ap.add_subparsers(dest="acao", required=True)
    s = sub.add_parser("ver")
    s.add_argument("qual", choices=["procedimentos", "base", "decisoes"])
    s = sub.add_parser("conversas")
    s.add_argument("--dias", type=int, default=3)
    s.add_argument("--busca", default="")
    s = sub.add_parser("propor")
    s.add_argument("qual", choices=["procedimentos", "base"])
    s.add_argument("arquivo")
    s.add_argument("--motivo", required=True)
    s = sub.add_parser("simular")
    s.add_argument("mensagem")
    s.add_argument("--historico", default="")
    s.add_argument("--proposta", action="store_true")
    for n in ("pendente", "aplicar", "descartar", "desfazer"):
        sub.add_parser(n)
    s = sub.add_parser("decisao")
    s.add_argument("texto", nargs="+")
    for n in ("assumir", "devolver"):
        s = sub.add_parser(n)
        s.add_argument("numero")
    s = sub.add_parser("responder")
    s.add_argument("numero")
    s.add_argument("texto", nargs="+")
    a = ap.parse_args(argv)
    at = at_linha(a.linha)
    try:
        if a.acao == "ver":
            print(_ler(_arquivo(at, a.qual)) or "(vazio)")
        elif a.acao == "conversas":
            print(conversas(at, a.dias, a.busca))
        elif a.acao == "propor":
            print(propor(at, a.qual, _ler(a.arquivo), a.motivo))
            print("\nProposta guardada. Mostre ao dono e só rode `aplicar` depois do ok dele.")
        elif a.acao == "simular":
            print(simular(at, a.mensagem, a.historico, a.proposta))
        elif a.acao == "pendente":
            p = pendente(at)
            print(json.dumps(p, ensure_ascii=False, indent=1) if p else "nenhuma proposta pendente")
        elif a.acao == "aplicar":
            p = aplicar(at)
            print(f"aplicado em {p['qual']} (versão anterior guardada; `desfazer` volta)")
        elif a.acao == "descartar":
            print("proposta descartada" if descartar(at) else "não havia proposta")
        elif a.acao == "desfazer":
            print(f"{desfazer(at)} voltou para a versão anterior")
        elif a.acao == "decisao":
            registrar_decisao(at, " ".join(a.texto))
            print("decisão registrada")
        elif a.acao in ("assumir", "devolver", "responder"):
            import linhas
            mod = linhas.modulos(a.linha)[0]
            arg = a.numero + (" " + " ".join(a.texto) if a.acao == "responder" else "")
            print(linhas.comando("/" + a.acao, mod.CMD_LINHA + arg))
    except (ValueError, RuntimeError) as e:
        print("⛔", e, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
