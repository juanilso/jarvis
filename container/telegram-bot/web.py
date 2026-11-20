#!/usr/bin/env python3
"""Jarvis Web: página de chat com microfone e respostas faladas, no navegador.

Mesmo motor do bot do Telegram (jarvis_core). Acesse pelo Tailscale (HTTPS) ou túnel SSH.
Variáveis: JARVIS_WEB_PASSWORD (ou PASSWORD), JARVIS_WEB_PORT (padrão 8090) e as do núcleo.
"""
import hmac
import json
import os
import secrets
import sys
import tempfile
import threading
import time
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jarvis_core as core  # noqa: E402

SENHA = os.environ.get("JARVIS_WEB_PASSWORD") or os.environ.get("PASSWORD", "")
PORTA = int(os.environ.get("JARVIS_WEB_PORT", "8090"))
HTML = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "web.html"), encoding="utf-8").read()

estado = core.Estado("web")
execucao = core.Execucao()
tokens = set()
eventos, ev_lock = [], threading.Lock()
VOZ_DIR = tempfile.mkdtemp(prefix="jarvis-voz-")


def publicar(ev):
    with ev_lock:
        ev["id"] = len(eventos) + 1
        ev["hora"] = time.strftime("%H:%M")
        eventos.append(ev)
        del eventos[:-300]  # guarda só os últimos 300


def rodar(texto, responder_audio, compactar=False):
    def ao_evento(ev):
        if ev["tipo"] == "resposta" and ev.get("audio"):
            nome = secrets.token_hex(8) + ".mp3"
            try:
                if core.gerar_mp3(ev["resumo"], os.path.join(VOZ_DIR, nome)):
                    ev["voz"] = "/voz/" + nome
            except Exception as e:  # noqa: BLE001
                print("erro no áudio:", e, flush=True)
        publicar(ev)

    execucao.rodar(estado, texto, responder_audio, ao_evento, compactar=compactar)


def iniciar(texto, veio_de_audio):
    if texto.startswith("/"):
        resposta, acao = core.comando(estado, execucao, texto)
        if resposta is not None:
            publicar({"tipo": "usuario", "texto": texto})
            publicar({"tipo": "info", "texto": resposta})
            if acao == "compactar":
                threading.Thread(target=rodar, args=("", False, True), daemon=True).start()
            return None
    est = estado.ler()
    if not est["projeto"]:
        return "Escolha um projeto primeiro."
    if execucao.ocupado:
        return "Ainda estou trabalhando no pedido anterior."
    audio = est["audio"] == "sempre" or (est["audio"] == "auto" and veio_de_audio)
    publicar({"tipo": "usuario", "texto": texto, "projeto": est["projeto"]})
    threading.Thread(target=rodar, args=(texto, audio), daemon=True).start()
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silencioso
        pass

    # -- utilidades
    def _json(self, obj, code=200):
        dados = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _corpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _logado(self):
        c = SimpleCookie(self.headers.get("Cookie", ""))
        return "jarvis" in c and c["jarvis"].value in tokens

    def _html(self, html, code=200):
        dados = html.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    # -- rotas
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/":
            return self._html(HTML if self._logado() else LOGIN)
        if url.path.startswith("/static/"):
            nome = os.path.basename(url.path)
            caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", nome)
            if not nome.endswith(".jpg") or not os.path.isfile(caminho):
                return self._json({"erro": "não encontrado"}, 404)
            with open(caminho, "rb") as f:
                dados = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "max-age=86400")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            return self.wfile.write(dados)
        if not self._logado():
            return self._json({"erro": "login"}, 401)
        if url.path == "/api/estado":
            est = estado.ler()
            return self._json({"projeto": est["projeto"], "projetos": core.listar_projetos(),
                               "audio": est["audio"], "agentes": est["agentes"],
                               "ocupado": execucao.ocupado, "pedido": execucao.pedido})
        if url.path == "/api/comandos":
            return self._json([{"cmd": c, "desc": d} for c, d in core.COMANDOS])
        if url.path == "/api/painel":
            return self._json(core.painel_projeto(estado.ler()["projeto"]))
        if url.path == "/api/eventos":
            desde = int(urllib.parse.parse_qs(url.query).get("desde", ["0"])[0])
            with ev_lock:
                novos = [e for e in eventos if e["id"] > desde]
                ultimo = eventos[-1]["id"] if eventos else 0
            return self._json({"eventos": novos, "ultimo": ultimo, "ocupado": execucao.ocupado})
        if url.path.startswith("/voz/"):
            nome = os.path.basename(url.path)
            caminho = os.path.join(VOZ_DIR, nome)
            if not os.path.isfile(caminho):
                return self._json({"erro": "não encontrado"}, 404)
            with open(caminho, "rb") as f:
                dados = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            return self.wfile.write(dados)
        return self._json({"erro": "não encontrado"}, 404)

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/login":
            senha = urllib.parse.parse_qs(self._corpo().decode()).get("senha", [""])[0]
            if SENHA and hmac.compare_digest(senha, SENHA):
                tok = secrets.token_urlsafe(32)
                tokens.add(tok)
                self.send_response(303)
                self.send_header("Set-Cookie", f"jarvis={tok}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000")
                self.send_header("Location", "/")
                return self.end_headers()
            time.sleep(1.5)
            return self._html(LOGIN.replace("<!--erro-->", "<p class='erro'>Senha incorreta.</p>"), 401)
        if not self._logado():
            return self._json({"erro": "login"}, 401)

        if url.path == "/api/audio":
            sufixo = ".mp4" if "mp4" in (self.headers.get("Content-Type") or "") else ".webm"
            with tempfile.NamedTemporaryFile(suffix=sufixo, delete=False) as f:
                f.write(self._corpo())
                caminho = f.name
            try:
                texto = core.transcrever(caminho)
            except Exception as e:  # noqa: BLE001
                print("erro na transcrição:", e, flush=True)
                return self._json({"erro": "Não consegui transcrever o áudio."}, 500)
            finally:
                os.unlink(caminho)
            if not texto:
                return self._json({"erro": "Não entendi o áudio. Pode repetir?"}, 400)
            erro = iniciar(texto, veio_de_audio=True)
            return self._json({"texto": texto, "erro": erro})

        dados = json.loads(self._corpo() or b"{}")
        if url.path == "/api/mensagem":
            texto = (dados.get("texto") or "").strip()
            if not texto:
                return self._json({"erro": "Escreva uma mensagem."}, 400)
            return self._json({"erro": iniciar(texto, veio_de_audio=False)})
        if url.path == "/api/config":
            est = estado.ler()
            if dados.get("projeto") in core.listar_projetos():
                est["projeto"] = dados["projeto"]
            if dados.get("audio") in ("auto", "sempre", "nunca"):
                est["audio"] = dados["audio"]
            if isinstance(dados.get("agentes"), bool):
                est["agentes"] = dados["agentes"]
            estado.salvar(est)
            return self._json({"ok": True})
        if url.path == "/api/parar":
            return self._json({"ok": execucao.parar()})
        if url.path == "/api/novo":
            est = estado.ler()
            est["sessoes"].pop(est["projeto"], None)
            estado.salvar(est)
            publicar({"tipo": "sistema", "texto": "Conversa nova iniciada neste projeto."})
            return self._json({"ok": True})
        return self._json({"erro": "não encontrado"}, 404)


LOGIN = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Jarvis</title>
<style>body{font-family:system-ui,sans-serif;background:#1e1e1e;color:#eee;display:flex;align-items:center;
justify-content:center;height:100vh;margin:0}form{background:#2a2a2a;padding:28px;border-radius:12px;width:280px}
input,button{width:100%;padding:10px;margin-top:10px;border-radius:8px;border:1px solid #444;background:#1e1e1e;
color:#eee;font-size:16px;box-sizing:border-box}button{background:#3b82f6;border:0;cursor:pointer}.erro{color:#f87171}
</style></head><body><form method="post" action="/login"><h2 style="margin:0">Jarvis</h2>
<input type="password" name="senha" placeholder="Senha" autofocus><button>Entrar</button><!--erro--></form></body></html>"""


def main():
    if not SENHA:
        raise SystemExit("Defina PASSWORD (ou JARVIS_WEB_PASSWORD) no .env.claude")
    print(f"Jarvis Web na porta {PORTA}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORTA), Handler).serve_forever()


if __name__ == "__main__":
    main()
