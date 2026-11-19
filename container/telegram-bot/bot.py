#!/usr/bin/env python3
"""Jarvis Telegram: conversa com o Claude Code da VPS pelo Telegram (texto e áudio).

- Funciona com qualquer autenticação (assinatura, API key ou gateway), pois roda o próprio
  Claude Code em modo não interativo (claude -p), retomando a conversa de cada projeto.
- Áudio recebido: transcrito na VPS com faster-whisper (sem custo de API).
- Resposta em áudio: resumo falado gerado com edge-tts (vozes pt-BR) e enviado como mensagem de voz.
- Mostra no chat o que cada agente do Jarvis está fazendo (stream-json do Claude Code).
- Long polling: nenhuma porta aberta na VPS.

Variáveis de ambiente:
  TELEGRAM_BOT_TOKEN   token do @BotFather (obrigatório)
  TELEGRAM_CHAT_ID     IDs autorizados, separados por vírgula
  JARVIS_WORKSPACE     pasta dos projetos (padrão /workspace)
  JARVIS_TIMEOUT_MIN   tempo máximo por pedido (padrão 120)
  WHISPER_MODEL        tiny | base | small | medium (padrão small)
  TTS_VOICE            voz do edge-tts (padrão pt-BR-AntonioNeural; ex. pt-BR-FranciscaNeural)
"""
import json
import mimetypes
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED = {c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()}
WORKSPACE = os.environ.get("JARVIS_WORKSPACE", "/workspace")
TIMEOUT = int(os.environ.get("JARVIS_TIMEOUT_MIN", "120")) * 60
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
TTS_VOICE = os.environ.get("TTS_VOICE", "pt-BR-AntonioNeural")
STATE_FILE = os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude") + "/telegram-state.json")
API = f"https://api.telegram.org/bot{TOKEN}/"
FILE_API = f"https://api.telegram.org/file/bot{TOKEN}/"

lock = threading.Lock()
job = {"proc": None, "inicio": None, "pedido": None}
_whisper = {"model": None}

EMOJI = {"arquiteto": "🏛️", "explorador": "🔎", "desenvolvedor": "💻", "dba": "🗄️", "android": "🤖",
         "testador": "🧪", "revisor": "🧐", "deploy": "🚀", "documentador": "📝"}

AJUDA = (
    "🤖 Jarvis no Telegram\n\n"
    "/projetos: lista os projetos\n"
    "/projeto <nome>: escolhe o projeto\n"
    "/status: o que está rodando\n"
    "/novo: conversa nova no projeto atual\n"
    "/parar: interrompe o trabalho\n"
    "/audio auto|sempre|nunca: resposta em áudio (auto = quando você manda áudio)\n"
    "/agentes on|off: avisos de cada agente trabalhando\n\n"
    "Mande texto ou ÁUDIO com a demanda. Ex.: “corrige o erro da renovação duplicada”."
)

MARCA_RESUMO = "RESUMO_FALADO:"
INSTRUCAO_AUDIO = (
    f"\n\n[Instrução do bot: a resposta também será ouvida em áudio. No FINAL, escreva uma linha "
    f"começando com '{MARCA_RESUMO}' com 2 a 4 frases curtas, em português, sem código, sem caminhos "
    f"de arquivo e sem markdown, resumindo o resultado e o próximo passo.]"
)


# ---------------------------------------------------------------- Telegram
def tg(method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(API + method, data=data, timeout=70) as r:
        return json.loads(r.read().decode())


def tg_upload(method, campo, caminho, **params):
    boundary = uuid.uuid4().hex
    partes = []
    for k, v in params.items():
        partes.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    tipo = mimetypes.guess_type(caminho)[0] or "application/octet-stream"
    with open(caminho, "rb") as f:
        conteudo = f.read()
    partes.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{campo}"; filename="{os.path.basename(caminho)}"\r\n'
        f"Content-Type: {tipo}\r\n\r\n".encode() + conteudo + b"\r\n")
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


def baixar_arquivo(file_id, destino):
    info = tg("getFile", file_id=file_id)
    urllib.request.urlretrieve(FILE_API + info["result"]["file_path"], destino)


# ---------------------------------------------------------------- Estado
def ler_estado():
    try:
        with open(STATE_FILE) as f:
            est = json.load(f)
    except Exception:  # noqa: BLE001
        est = {}
    est.setdefault("projeto", None)
    est.setdefault("sessoes", {})
    est.setdefault("audio", "auto")
    est.setdefault("agentes", True)
    return est


def salvar_estado(est):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(est, f, indent=2)


def listar_projetos():
    try:
        return sorted(d for d in os.listdir(WORKSPACE)
                      if os.path.isdir(os.path.join(WORKSPACE, d)) and not d.startswith("."))
    except FileNotFoundError:
        return []


# ---------------------------------------------------------------- Áudio
def transcrever(caminho):
    if _whisper["model"] is None:
        from faster_whisper import WhisperModel  # importado só quando necessário
        _whisper["model"] = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    segmentos, _ = _whisper["model"].transcribe(caminho, language="pt", vad_filter=True)
    return " ".join(s.text.strip() for s in segmentos).strip()


def limpar_para_fala(texto):
    texto = re.sub(r"```.*?```", " ", texto, flags=re.S)
    texto = re.sub(r"`[^`]*`", " ", texto)
    texto = re.sub(r"https?://\S+", " ", texto)
    texto = re.sub(r"[#*_>|\[\]]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()[:900]


def falar(chat_id, texto):
    texto = limpar_para_fala(texto)
    if not texto:
        return
    with tempfile.TemporaryDirectory() as tmp:
        mp3, ogg = os.path.join(tmp, "r.mp3"), os.path.join(tmp, "resposta.ogg")
        try:
            subprocess.run(["edge-tts", "--voice", TTS_VOICE, "--text", texto, "--write-media", mp3],
                           check=True, capture_output=True, timeout=120)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-c:a", "libopus", "-b:a", "32k", ogg],
                           check=True, capture_output=True, timeout=120)
            tg_upload("sendVoice", "voice", ogg, chat_id=chat_id)
        except Exception as e:  # noqa: BLE001
            print("erro no áudio:", e, flush=True)
            enviar(chat_id, "(não consegui gerar o áudio desta vez)")


# ---------------------------------------------------------------- Claude
def nome_agente(entrada):
    tipo = (entrada.get("subagent_type") or "agente").split(":")[-1]
    return tipo, EMOJI.get(tipo, "🧩")


def rodar_claude(chat_id, texto, responder_audio):
    est = ler_estado()
    projeto = est["projeto"]
    pasta = os.path.join(WORKSPACE, projeto)
    prompt = texto + (INSTRUCAO_AUDIO if responder_audio else "")
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--dangerously-skip-permissions"]
    if est["sessoes"].get(projeto):
        cmd += ["--resume", est["sessoes"][projeto]]
    mostrar_agentes = est["agentes"]
    enviar(chat_id, f"⏳ Trabalhando em {projeto}…")

    agentes = {}  # tool_use_id -> (nome, emoji, inicio)
    resultado = None
    erro = ""
    try:
        with lock:
            job.update(proc=subprocess.Popen(cmd, cwd=pasta, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                             text=True, bufsize=1),
                       inicio=time.time(), pedido=texto[:80])
        proc = job["proc"]
        timer = threading.Timer(TIMEOUT, proc.kill)
        timer.start()
        for linha in proc.stdout:
            try:
                ev = json.loads(linha)
            except json.JSONDecodeError:
                continue
            tipo = ev.get("type")
            conteudo = (ev.get("message") or {}).get("content") or []
            if tipo == "assistant" and mostrar_agentes:
                for c in conteudo:
                    if c.get("type") == "tool_use" and c.get("name") in ("Task", "Agent"):
                        nome, emo = nome_agente(c.get("input") or {})
                        desc = (c.get("input") or {}).get("description", "")
                        agentes[c.get("id")] = (nome, emo, time.time())
                        enviar(chat_id, f"{emo} {nome} começou: {desc}")
            elif tipo == "user" and mostrar_agentes:
                for c in conteudo:
                    if c.get("type") == "tool_result" and c.get("tool_use_id") in agentes:
                        nome, emo, ini = agentes.pop(c["tool_use_id"])
                        status = "⚠️ terminou com erro" if c.get("is_error") else "✅ concluiu"
                        enviar(chat_id, f"{emo} {nome} {status} ({int(time.time() - ini)}s)")
            elif tipo == "result":
                resultado = ev
        proc.wait()
        timer.cancel()
        erro = proc.stderr.read()
        code = proc.returncode
    finally:
        with lock:
            job.update(proc=None, inicio=None, pedido=None)

    if resultado is None:
        if code in (-9, -15):
            enviar(chat_id, "⛔ Interrompido (por /parar ou tempo limite).")
        else:
            enviar(chat_id, "⚠️ Erro ao executar o Claude:\n" + (erro or "sem detalhes")[-3000:])
        return

    if resultado.get("session_id"):
        est = ler_estado()
        est["sessoes"][projeto] = resultado["session_id"]
        salvar_estado(est)

    resposta = resultado.get("result") or ""
    resumo = ""
    if MARCA_RESUMO in resposta:
        resposta, _, resumo = resposta.rpartition(MARCA_RESUMO)
        resposta, resumo = resposta.strip(), resumo.strip()
    custo = resultado.get("total_cost_usd")
    rodape = f"\n\n💲 custo estimado: US$ {custo:.4f}" if custo else ""
    enviar(chat_id, ("⚠️ " if resultado.get("is_error") else "") + resposta + rodape)
    if responder_audio:
        falar(chat_id, resumo or resposta)


# ---------------------------------------------------------------- Mensagens
def iniciar_pedido(chat_id, texto, veio_de_audio):
    est = ler_estado()
    if not est["projeto"]:
        enviar(chat_id, "Escolha um projeto antes: /projetos e depois /projeto <nome>")
        return
    if job["proc"]:
        enviar(chat_id, "Ainda estou trabalhando no pedido anterior. Use /status ou /parar.")
        return
    modo = est["audio"]
    responder_audio = modo == "sempre" or (modo == "auto" and veio_de_audio)
    threading.Thread(target=rodar_claude, args=(chat_id, texto, responder_audio), daemon=True).start()


def tratar_audio(chat_id, msg):
    arq = msg.get("voice") or msg.get("audio")
    enviar(chat_id, "🎙️ Transcrevendo…")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "entrada.ogg")
            baixar_arquivo(arq["file_id"], caminho)
            texto = transcrever(caminho)
    except Exception as e:  # noqa: BLE001
        print("erro na transcrição:", e, flush=True)
        enviar(chat_id, "Não consegui transcrever o áudio. Pode mandar por texto?")
        return
    if not texto:
        enviar(chat_id, "Não entendi o áudio. Pode repetir?")
        return
    enviar(chat_id, f"📝 Entendi: “{texto}”")
    iniciar_pedido(chat_id, texto, veio_de_audio=True)


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
    texto = (msg.get("text") or "").strip()
    if not texto:
        return

    est = ler_estado()
    cmd, _, arg = texto.partition(" ")
    cmd, arg = cmd.split("@")[0].lower(), arg.strip().lower()

    if cmd in ("/start", "/ajuda", "/help"):
        enviar(chat_id, AJUDA + f"\n\nProjeto: {est['projeto'] or 'nenhum'} · áudio: {est['audio']} · "
                                f"agentes: {'on' if est['agentes'] else 'off'}")
    elif cmd == "/projetos":
        ps = listar_projetos()
        enviar(chat_id, "📁 Projetos:\n" + "\n".join(f"• {p}" for p in ps) if ps else "Nenhum projeto em /workspace.")
    elif cmd == "/projeto":
        nome = texto.partition(" ")[2].strip()
        if nome not in listar_projetos():
            enviar(chat_id, "Projeto não encontrado. Use /projetos para ver os nomes.")
        else:
            est["projeto"] = nome
            salvar_estado(est)
            enviar(chat_id, f"✅ Projeto atual: {nome}")
    elif cmd == "/status":
        if job["proc"]:
            mins = int((time.time() - job["inicio"]) // 60)
            enviar(chat_id, f"🔄 Rodando há {mins} min em {est['projeto']}: “{job['pedido']}”")
        else:
            enviar(chat_id, f"💤 Livre. Projeto atual: {est['projeto'] or 'nenhum'}")
    elif cmd == "/novo":
        est["sessoes"].pop(est["projeto"], None)
        salvar_estado(est)
        enviar(chat_id, "🆕 A próxima mensagem começa uma conversa nova.")
    elif cmd == "/parar":
        if job["proc"]:
            job["proc"].terminate()
            enviar(chat_id, "Parando…")
        else:
            enviar(chat_id, "Nada rodando.")
    elif cmd == "/audio":
        if arg not in ("auto", "sempre", "nunca"):
            enviar(chat_id, f"Áudio está em: {est['audio']}. Use /audio auto, /audio sempre ou /audio nunca.")
        else:
            est["audio"] = arg
            salvar_estado(est)
            enviar(chat_id, f"🔊 Resposta em áudio: {arg}")
    elif cmd == "/agentes":
        if arg not in ("on", "off"):
            enviar(chat_id, f"Avisos de agentes: {'on' if est['agentes'] else 'off'}. Use /agentes on ou off.")
        else:
            est["agentes"] = arg == "on"
            salvar_estado(est)
            enviar(chat_id, f"👥 Avisos de agentes: {arg}")
    else:
        iniciar_pedido(chat_id, texto, veio_de_audio=False)


def main():
    if not TOKEN:
        raise SystemExit("Defina TELEGRAM_BOT_TOKEN no .env.claude")
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
