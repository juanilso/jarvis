#!/usr/bin/env python3
"""Jarvis Telegram: conversa com o Claude Code da VPS pelo Telegram (texto e áudio).

Variáveis: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (IDs autorizados, separados por vírgula),
JARVIS_WORKSPACE, JARVIS_TIMEOUT_MIN, WHISPER_MODEL, TTS_VOICE. Long polling: nenhuma porta aberta.
"""
import json
import re
import mimetypes
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jarvis_core as core  # noqa: E402
import kb  # noqa: E402

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED = {c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()}
API = f"https://api.telegram.org/bot{TOKEN}/"
FILE_API = f"https://api.telegram.org/file/bot{TOKEN}/"

estado = core.Estado("telegram")
pool = core.Execucoes()

AJUDA = (
    "🤖 Jarvis no Telegram\n\n"
    "/projetos: lista os projetos\n"
    "/projeto <nome>: escolhe o projeto\n"
    "/status: o que está rodando\n"
    "/novo: conversa nova no projeto atual\n"
    "/parar: interrompe o trabalho\n"
    "/audio auto|sempre|nunca: resposta em áudio (auto = quando você manda áudio)\n"
    "/agentes on|off: avisos de cada agente trabalhando\n\n"
    "Mande texto ou ÁUDIO com a demanda."
)


# ---------------------------------------------------------------- Telegram
def tg(method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(API + method, data=data, timeout=70) as r:
        return json.loads(r.read().decode())


def tg_upload(method, campo, caminho, **params):
    boundary = uuid.uuid4().hex
    partes = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
              for k, v in params.items()]
    tipo = mimetypes.guess_type(caminho)[0] or "application/octet-stream"
    with open(caminho, "rb") as f:
        conteudo = f.read()
    partes.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{campo}"; '
                  f'filename="{os.path.basename(caminho)}"\r\nContent-Type: {tipo}\r\n\r\n'.encode()
                  + conteudo + b"\r\n")
    partes.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(API + method, data=b"".join(partes),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def enviar(chat_id, texto):
    texto = texto or "(sem resposta)"
    for i in range(0, len(texto), 3900):
        try:
            tg("sendMessage", chat_id=chat_id, text=texto[i:i + 3900])
        except Exception as e:  # noqa: BLE001
            print("erro ao enviar:", e, flush=True)


def falar(chat_id, texto):
    with tempfile.TemporaryDirectory() as tmp:
        mp3, ogg = os.path.join(tmp, "r.mp3"), os.path.join(tmp, "resposta.ogg")
        try:
            if not core.gerar_mp3(texto, mp3):
                return
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-c:a", "libopus", "-b:a", "32k", ogg],
                           check=True, capture_output=True, timeout=120)
            tg_upload("sendVoice", "voice", ogg, chat_id=chat_id)
        except Exception as e:  # noqa: BLE001
            print("erro no áudio:", e, flush=True)
            enviar(chat_id, "(não consegui gerar o áudio desta vez)")


def baixar_arquivo(file_id, destino):
    info = tg("getFile", file_id=file_id)
    urllib.request.urlretrieve(FILE_API + info["result"]["file_path"], destino)


# ---------------------------------------------------------------- pedidos
class Progresso:
    """Uma única mensagem no Telegram, atualizada a cada poucos segundos com o que está acontecendo."""

    def __init__(self, chat_id, projeto):
        self.chat_id, self.projeto, self.linhas, self.inicio = chat_id, projeto, [], time.time()
        self.msg_id, self.ativo, self.mudou = None, True, True
        try:
            r = tg("sendMessage", chat_id=chat_id, text=f"⏳ Trabalhando em {projeto}…")
            self.msg_id = r["result"]["message_id"]
        except Exception as e:  # noqa: BLE001
            print("erro ao criar progresso:", e, flush=True)
        threading.Thread(target=self._laco, daemon=True).start()

    def add(self, linha):
        self.linhas = (self.linhas + [linha])[-5:]
        self.mudou = True

    def _texto(self, fim=None):
        s = int(time.time() - self.inicio)
        cab = fim or f"⏳ Trabalhando em {self.projeto} · {s // 60}m{s % 60:02d}s"
        return cab + ("\n\n" + "\n".join(self.linhas) if self.linhas else "")

    def _editar(self, texto):
        if self.msg_id:
            try:
                tg("editMessageText", chat_id=self.chat_id, message_id=self.msg_id, text=texto[:3900])
            except Exception:  # noqa: BLE001
                pass

    def _laco(self):
        ultimo = 0
        while self.ativo:
            time.sleep(1)
            if self.ativo and (self.mudou and time.time() - ultimo >= 4 or time.time() - ultimo >= 15):
                self._editar(self._texto())
                ultimo, self.mudou = time.time(), False

    def fim(self, ok=True):
        self.ativo = False
        s = int(time.time() - self.inicio)
        self._editar(self._texto(f"{'✅ Concluído' if ok else '⚠️ Terminou com problema'} em {s // 60}m{s % 60:02d}s"))


def rodar(chat_id, texto, responder_audio, compactar=False, proj=None):
    proj = proj or estado.ler()["projeto"]
    prog = None if compactar else Progresso(chat_id, proj)

    def ao_evento(ev):
        if ev["tipo"] in ("acao", "pensando"):
            if prog:
                prog.add(f"{ev.get('emoji', '🧠')} {ev.get('agente', 'jarvis')} · {ev['texto'][:140]}")
            return
        if ev["tipo"] == "inicio":
            return
        if ev["tipo"] in ("resposta", "erro") and prog:
            prog.fim(ev["tipo"] == "resposta" and not ev.get("erro"))
        tag = f"[{proj}] "  # deixa claro de qual projeto é cada mensagem (vários podem rodar ao mesmo tempo)
        if ev["tipo"] == "agente_inicio":
            enviar(chat_id, f"{tag}{ev['emoji']} {ev['agente']} começou: {ev['descricao']}")
        elif ev["tipo"] == "agente_fim":
            st = "⚠️ terminou com erro" if ev["erro"] else "✅ concluiu"
            enviar(chat_id, f"{tag}{ev['emoji']} {ev['agente']} {st} ({ev['segundos']}s)")
        elif ev["tipo"] == "info":
            enviar(chat_id, tag + ev["texto"])
        elif ev["tipo"] == "erro":
            enviar(chat_id, f"{tag}⚠️ " + ev["texto"])
        elif ev["tipo"] == "resposta":
            rodape = f"\n\n💲 custo estimado: US$ {ev['custo']:.4f}" if ev.get("custo") else ""
            enviar(chat_id, f"📁 {proj}\n" + ("⚠️ " if ev["erro"] else "") + ev["texto"] + rodape)
            if ev["audio"]:
                falar(chat_id, ev["resumo"])

    pool.de(proj).rodar(estado, texto, responder_audio, ao_evento, compactar=compactar, projeto=proj)


def pesquisar(chat_id, tema):
    destino, prompt = kb.prompt_pesquisa(tema)

    def ao_evento(ev):
        if ev["tipo"] == "resposta":
            enviar(chat_id, ev["texto"] + (f"\n\n💲 custo estimado: US$ {ev['custo']:.4f}" if ev.get("custo") else ""))
        elif ev["tipo"] in ("erro", "info"):
            enviar(chat_id, ev["texto"])
    pool.de("_pesquisa").rodar(estado, prompt, False, ao_evento, cwd=kb.KB_DIR, usar_sessao=False)
    kb.sincronizar()
    if os.path.exists(destino):
        enviar(chat_id, f"📚 Pesquisa salva na base de conhecimento: {os.path.relpath(destino, kb.KB_DIR)}")


def iniciar_pedido(chat_id, texto, veio_de_audio):
    est = estado.ler()
    if not est["projeto"]:
        enviar(chat_id, "Escolha um projeto antes: /projetos e depois /projeto <nome>")
    elif not pool.pode_iniciar(est["projeto"])[0]:
        enviar(chat_id, pool.pode_iniciar(est["projeto"])[1])
    else:
        audio = est["audio"] == "sempre" or (est["audio"] == "auto" and veio_de_audio)
        threading.Thread(target=rodar, args=(chat_id, texto, audio, False, est["projeto"]), daemon=True).start()


def tratar_audio(chat_id, msg):
    arq = msg.get("voice") or msg.get("audio")
    enviar(chat_id, "🎙️ Transcrevendo…")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "entrada.ogg")
            baixar_arquivo(arq["file_id"], caminho)
            texto = core.transcrever(caminho)
    except Exception as e:  # noqa: BLE001
        print("erro na transcrição:", e, flush=True)
        enviar(chat_id, "Não consegui transcrever o áudio. Pode mandar por texto?")
        return
    if not texto:
        enviar(chat_id, "Não entendi o áudio. Pode repetir?")
        return
    enviar(chat_id, f"📝 Entendi: “{texto}”")
    m = re.match(r"^\s*(ideia|anota|anote|anotar)\b[\s:,.-]*(.+)", texto, re.I | re.S)
    if m:  # "ideia: ..." por voz vira /ideia
        enviar(chat_id, core.comando(estado, pool, "/ideia " + m.group(2).strip())[0])
        return
    iniciar_pedido(chat_id, texto, veio_de_audio=True)


ANEXOS_DIR = os.path.join(core.WORKSPACE, ".jarvis-anexos")  # fora dos projetos: não entra no Git
grupos, grupos_lock = {}, threading.Lock()  # álbuns (várias fotos de uma vez)


def receber_anexo(chat_id, msg):
    """Fotos e arquivos: salva na VPS e manda o caminho para o Claude ler."""
    grupo = msg.get("media_group_id")
    if not grupo:
        threading.Thread(target=processar_anexos, args=(chat_id, [msg]), daemon=True).start()
        return
    with grupos_lock:  # espera o álbum chegar inteiro antes de processar
        if grupo not in grupos:
            grupos[grupo] = []
            threading.Timer(2.5, lambda: processar_anexos(chat_id, grupos.pop(grupo, []))).start()
        grupos[grupo].append(msg)


def processar_anexos(chat_id, msgs):
    est = estado.ler()
    if not est["projeto"]:
        enviar(chat_id, "Escolha um projeto antes de mandar arquivos: /projetos e depois /projeto <nome>")
        return
    ok, motivo = pool.pode_iniciar(est["projeto"])
    if not ok:
        enviar(chat_id, motivo + " Mande o arquivo de novo depois.")
        return
    os.makedirs(ANEXOS_DIR, exist_ok=True)
    caminhos, legenda = [], ""
    for i, m in enumerate(msgs):
        legenda = legenda or (m.get("caption") or "").strip()
        if m.get("photo"):
            arq, ext = m["photo"][-1], ".jpg"  # a última é a de maior resolução
        else:
            arq = m["document"]
            ext = os.path.splitext(arq.get("file_name") or "")[1] or ".bin"
        if (arq.get("file_size") or 0) > 20 * 1024 * 1024:
            enviar(chat_id, "Arquivo maior que 20 MB: o Telegram não deixa o bot baixar. Envie compactado ou divida.")
            continue
        destino = os.path.join(ANEXOS_DIR, time.strftime("%Y%m%d-%H%M%S") + f"-{uuid.uuid4().hex[:6]}{ext}")
        try:
            baixar_arquivo(arq["file_id"], destino)
            caminhos.append(destino)
        except Exception as e:  # noqa: BLE001
            print("erro ao baixar anexo:", e, flush=True)
            enviar(chat_id, "Não consegui baixar um dos arquivos.")
    if not caminhos:
        return
    lista = "\n".join(f"- {c}" for c in caminhos)
    pedido = legenda or "Analise o(s) anexo(s) e me diga o que você vê e o que sugere fazer neste projeto."
    texto = (f"{pedido}\n\n[Anexos enviados pelo usuário pelo Telegram. Abra cada um com a ferramenta Read "
             f"(imagens incluídas) antes de responder. Não faça commit destes arquivos.]\n{lista}")
    nomes = ", ".join(os.path.basename(c) for c in caminhos)
    enviar(chat_id, f"📎 Recebi {len(caminhos)} arquivo(s): {nomes}" +
           ("" if legenda else "\nDica: escreva a pergunta na legenda da imagem."))
    audio = est["audio"] == "sempre"
    threading.Thread(target=rodar, args=(chat_id, texto, audio, False, est["projeto"]), daemon=True).start()


def tratar(msg):
    chat_id = str(msg["chat"]["id"])
    if chat_id not in ALLOWED:
        enviar(chat_id, f"Acesso não autorizado. Seu chat ID é {chat_id}. "
                        "Coloque-o em TELEGRAM_CHAT_ID no .env.claude da VPS.")
        print("chat não autorizado:", chat_id, flush=True)
        return
    if msg.get("voice") or msg.get("audio"):
        threading.Thread(target=tratar_audio, args=(chat_id, msg), daemon=True).start()
        return
    if msg.get("photo") or msg.get("document"):
        receber_anexo(chat_id, msg)
        return
    texto = (msg.get("text") or "").strip()
    if not texto:
        return
    if texto.startswith("/jarvis_"):
        texto = "/jarvis:" + texto[len("/jarvis_"):].split("@")[0]
    if texto.split()[0].split("@")[0].lower() in ("/compactar", "/modelo", "/custo", "/ajuda", "/novo", "/status",
                                                  "/ideia", "/lembrar", "/pesquisar", "/sincronizar", "/guia") \
            or texto.split()[0].split("@")[0].lower() in core.INTERATIVOS:
        resposta, acao = core.comando(estado, pool, texto)
        enviar(chat_id, resposta)
        if acao == "compactar":
            threading.Thread(target=rodar, args=(chat_id, "", False, True, estado.ler()["projeto"]), daemon=True).start()
        elif acao == "pesquisar":
            threading.Thread(target=pesquisar, args=(chat_id, texto.partition(" ")[2].strip()), daemon=True).start()
        return
    est = estado.ler()
    cmd, _, resto = texto.partition(" ")
    cmd, arg = cmd.split("@")[0].lower(), resto.strip().lower()

    if cmd in ("/start", "/ajuda", "/help"):
        enviar(chat_id, AJUDA + f"\n\nProjeto: {est['projeto'] or 'nenhum'} · áudio: {est['audio']} · "
                                f"agentes: {'on' if est['agentes'] else 'off'}")
    elif cmd == "/projetos":
        ps = core.listar_projetos()
        enviar(chat_id, "📁 Projetos:\n" + "\n".join(f"• {p}" for p in ps) if ps else "Nenhum projeto em /workspace.")
    elif cmd == "/projeto":
        nome = resto.strip()
        if nome not in core.listar_projetos():
            enviar(chat_id, "Projeto não encontrado. Use /projetos para ver os nomes.")
        else:
            est["projeto"] = nome
            estado.salvar(est)
            enviar(chat_id, f"✅ Projeto atual: {nome}")
    elif cmd == "/status":
        enviar(chat_id, core.comando(estado, pool, "/status")[0])
    elif cmd == "/novo":
        est["sessoes"].pop(est["projeto"], None)
        estado.salvar(est)
        enviar(chat_id, "🆕 A próxima mensagem começa uma conversa nova.")
    elif cmd == "/parar":
        enviar(chat_id, "Parando…" if pool.de(est["projeto"]).parar() else "Nada rodando neste projeto.")
    elif cmd == "/audio":
        if arg not in ("auto", "sempre", "nunca"):
            enviar(chat_id, f"Áudio está em: {est['audio']}. Use /audio auto, /audio sempre ou /audio nunca.")
        else:
            est["audio"] = arg
            estado.salvar(est)
            enviar(chat_id, f"🔊 Resposta em áudio: {arg}")
    elif cmd == "/agentes":
        if arg not in ("on", "off"):
            enviar(chat_id, f"Avisos de agentes: {'on' if est['agentes'] else 'off'}. Use /agentes on ou off.")
        else:
            est["agentes"] = arg == "on"
            estado.salvar(est)
            enviar(chat_id, f"👥 Avisos de agentes: {arg}")
    else:
        iniciar_pedido(chat_id, texto, veio_de_audio=False)


def main():
    if not TOKEN:
        raise SystemExit("Defina TELEGRAM_BOT_TOKEN no .env.claude")
    try:  # menu que aparece ao digitar "/" no Telegram (nomes sem ":" por regra do Telegram)
        cmds = [{"command": c[1:], "description": d[:60]} for c, d in core.COMANDOS if ":" not in c]
        cmds += [{"command": "jarvis_" + c.split(":")[1], "description": d[:60]} for c, d in core.COMANDOS if ":" in c]
        tg("setMyCommands", commands=json.dumps(cmds))
    except Exception as e:  # noqa: BLE001
        print("não consegui registrar o menu de comandos:", e, flush=True)
    print("Jarvis Telegram iniciado. Autorizados:", ALLOWED or "nenhum (configure TELEGRAM_CHAT_ID)", flush=True)
    offset = 0
    while True:
        try:
            r = tg("getUpdates", offset=offset, timeout=50)
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                if "message" in upd:
                    tratar(upd["message"])
        except Exception as e:  # noqa: BLE001
            print("erro no polling:", e, flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
