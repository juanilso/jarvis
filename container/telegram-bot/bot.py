#!/usr/bin/env python3
"""Jarvis Telegram: conversa com o Claude Code da VPS pelo Telegram.

Funciona com qualquer autenticação (assinatura, API key ou gateway com ANTHROPIC_BASE_URL),
porque executa o próprio Claude Code em modo não interativo (claude -p).
Usa long polling: nenhuma porta é aberta na VPS.

Variáveis de ambiente:
  TELEGRAM_BOT_TOKEN   token do @BotFather (obrigatório)
  TELEGRAM_CHAT_ID     IDs autorizados, separados por vírgula (obrigatório para usar)
  JARVIS_WORKSPACE     pasta dos projetos (padrão /workspace)
  JARVIS_TIMEOUT_MIN   tempo máximo por pedido, em minutos (padrão 120)
"""
import json
import os
import subprocess
import threading
import time
import urllib.parse
import urllib.request

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED = {c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()}
WORKSPACE = os.environ.get("JARVIS_WORKSPACE", "/workspace")
TIMEOUT = int(os.environ.get("JARVIS_TIMEOUT_MIN", "120")) * 60
STATE_FILE = os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude") + "/telegram-state.json")
API = f"https://api.telegram.org/bot{TOKEN}/"

lock = threading.Lock()
job = {"proc": None, "inicio": None, "pedido": None}

AJUDA = (
    "🤖 Jarvis no Telegram\n\n"
    "/projetos: lista os projetos\n"
    "/projeto <nome>: escolhe o projeto de trabalho\n"
    "/status: mostra o que está rodando\n"
    "/novo: começa uma conversa nova no projeto atual\n"
    "/parar: interrompe o trabalho em andamento\n\n"
    "Qualquer outra mensagem vai direto para o Claude/Jarvis no projeto atual.\n"
    "Ex.: /jarvis:status   ou   corrige o erro da renovação duplicada"
)


def tg(method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(API + method, data=data, timeout=70) as r:
        return json.loads(r.read().decode())


def enviar(chat_id, texto):
    texto = texto or "(sem resposta)"
    for i in range(0, len(texto), 3900):
        try:
            tg("sendMessage", chat_id=chat_id, text=texto[i:i + 3900])
        except Exception as e:  # noqa: BLE001
            print("erro ao enviar:", e, flush=True)


def ler_estado():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {"projeto": None, "sessoes": {}}


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


def rodar_claude(chat_id, texto):
    est = ler_estado()
    projeto = est.get("projeto")
    pasta = os.path.join(WORKSPACE, projeto)
    cmd = ["claude", "-p", texto, "--output-format", "json", "--dangerously-skip-permissions"]
    sessao = est.get("sessoes", {}).get(projeto)
    if sessao:
        cmd += ["--resume", sessao]
    enviar(chat_id, f"⏳ Trabalhando em {projeto}… aviso quando terminar.")
    try:
        with lock:
            job.update(proc=subprocess.Popen(cmd, cwd=pasta, stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE, text=True),
                       inicio=time.time(), pedido=texto[:80])
        out, err = job["proc"].communicate(timeout=TIMEOUT)
        code = job["proc"].returncode
    except subprocess.TimeoutExpired:
        job["proc"].kill()
        enviar(chat_id, f"⌛ Passou de {TIMEOUT // 60} min e foi interrompido. Peça para continuar.")
        return
    finally:
        with lock:
            job.update(proc=None, inicio=None, pedido=None)

    if code == -9 or code == -15:
        enviar(chat_id, "⛔ Interrompido.")
        return
    try:
        res = json.loads(out)
        if res.get("session_id"):
            est = ler_estado()
            est.setdefault("sessoes", {})[projeto] = res["session_id"]
            salvar_estado(est)
        resposta = res.get("result") or ""
        custo = res.get("total_cost_usd")
        if custo:
            resposta += f"\n\n💲 custo estimado: US$ {custo:.4f}"
        if res.get("is_error"):
            resposta = "⚠️ " + resposta
        enviar(chat_id, resposta)
    except json.JSONDecodeError:
        enviar(chat_id, "⚠️ Erro ao executar o Claude:\n" + (err or out)[-3000:])


def tratar(msg):
    chat_id = str(msg["chat"]["id"])
    texto = (msg.get("text") or "").strip()
    if not texto:
        return
    if chat_id not in ALLOWED:
        enviar(chat_id, f"Acesso não autorizado. Seu chat ID é {chat_id}. "
                        "Coloque-o em TELEGRAM_CHAT_ID no .env.claude da VPS.")
        print("chat não autorizado:", chat_id, flush=True)
        return

    est = ler_estado()
    cmd, _, arg = texto.partition(" ")
    cmd = cmd.split("@")[0].lower()

    if cmd in ("/start", "/ajuda", "/help"):
        enviar(chat_id, AJUDA + f"\n\nProjeto atual: {est.get('projeto') or 'nenhum'}")
    elif cmd == "/projetos":
        ps = listar_projetos()
        enviar(chat_id, "📁 Projetos:\n" + "\n".join(f"• {p}" for p in ps) if ps else "Nenhum projeto em /workspace.")
    elif cmd == "/projeto":
        nome = arg.strip()
        if nome not in listar_projetos():
            enviar(chat_id, "Projeto não encontrado. Use /projetos para ver os nomes.")
        else:
            est["projeto"] = nome
            salvar_estado(est)
            enviar(chat_id, f"✅ Projeto atual: {nome}")
    elif cmd == "/status":
        if job["proc"]:
            mins = int((time.time() - job["inicio"]) // 60)
            enviar(chat_id, f"🔄 Rodando há {mins} min em {est.get('projeto')}: “{job['pedido']}”")
        else:
            enviar(chat_id, f"💤 Livre. Projeto atual: {est.get('projeto') or 'nenhum'}")
    elif cmd == "/novo":
        est.get("sessoes", {}).pop(est.get("projeto"), None)
        salvar_estado(est)
        enviar(chat_id, "🆕 A próxima mensagem começa uma conversa nova.")
    elif cmd == "/parar":
        if job["proc"]:
            job["proc"].terminate()
            enviar(chat_id, "Parando…")
        else:
            enviar(chat_id, "Nada rodando.")
    else:
        if not est.get("projeto"):
            enviar(chat_id, "Escolha um projeto antes: /projetos e depois /projeto <nome>")
        elif job["proc"]:
            enviar(chat_id, "Ainda estou trabalhando no pedido anterior. Use /status ou /parar.")
        else:
            threading.Thread(target=rodar_claude, args=(chat_id, texto), daemon=True).start()


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
