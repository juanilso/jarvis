#!/usr/bin/env python3
"""Jarvis Web: página de chat com microfone e respostas faladas, no navegador.

Mesmo motor do bot do Telegram (jarvis_core). Acesse pelo Tailscale (HTTPS) ou túnel SSH.
Variáveis: JARVIS_WEB_PASSWORD (ou PASSWORD), JARVIS_WEB_PORT (padrão 8090) e as do núcleo.
"""
import hmac
import re
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jarvis_core as core  # noqa: E402
import projetos  # noqa: E402
import kb  # noqa: E402

SENHA = os.environ.get("JARVIS_WEB_PASSWORD") or os.environ.get("PASSWORD", "")
PORTA = int(os.environ.get("JARVIS_WEB_PORT", "8090"))
HTML = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "web.html"), encoding="utf-8").read()

estado = core.Estado("web")
pool = core.Execucoes()
tokens = set()
eventos, ev_lock = [], threading.Lock()
VOZ_DIR = tempfile.mkdtemp(prefix="jarvis-voz-")


HIST_DIR = os.path.join(core.CONFIG_DIR, "historico-web")
PERSISTIR = {"usuario", "resposta", "info", "erro", "agente_inicio", "agente_fim", "sistema"}
_contador = [0]


def _arquivo_hist(projeto):
    return os.path.join(HIST_DIR, re.sub(r"[^A-Za-z0-9._-]", "_", projeto or "_geral") + ".jsonl")


def publicar(ev, projeto=None):
    """Registra um evento no histórico do projeto (cada projeto tem o seu, salvo em disco)."""
    with ev_lock:
        _contador[0] += 1
        ev["id"] = _contador[0]
        ev["hora"] = ev.get("hora") or time.strftime("%d/%m %H:%M")
        ev["projeto"] = ev.get("projeto") or projeto or estado.ler()["projeto"] or "_geral"
        eventos.append(ev)
        del eventos[:-3000]
        if ev["tipo"] in PERSISTIR:
            try:
                os.makedirs(HIST_DIR, exist_ok=True)
                with open(_arquivo_hist(ev["projeto"]), "a", encoding="utf-8") as f:
                    f.write(json.dumps({k: v for k, v in ev.items() if k not in ("id", "voz")}, ensure_ascii=False) + "\n")
            except OSError as e:
                print("erro ao salvar histórico:", e, flush=True)


def carregar_historico(limite=150):
    if not os.path.isdir(HIST_DIR):
        return
    for nome in sorted(os.listdir(HIST_DIR)):
        try:
            linhas = open(os.path.join(HIST_DIR, nome), encoding="utf-8").read().splitlines()[-limite:]
        except OSError:
            continue
        for l in linhas:
            try:
                ev = json.loads(l)
            except json.JSONDecodeError:
                continue
            _contador[0] += 1
            ev["id"] = _contador[0]
            eventos.append(ev)


def rodar(texto, responder_audio, compactar=False, proj=None):
    proj = proj or estado.ler()["projeto"]
    def ao_evento(ev):
        if ev["tipo"] == "resposta" and ev.get("audio"):
            nome = secrets.token_hex(8) + ".mp3"
            try:
                if core.gerar_mp3(ev["resumo"], os.path.join(VOZ_DIR, nome)):
                    ev["voz"] = "/voz/" + nome
            except Exception as e:  # noqa: BLE001
                print("erro no áudio:", e, flush=True)
        publicar(ev, proj)

    pool.de(proj).rodar(estado, texto, responder_audio, ao_evento, compactar=compactar, projeto=proj)


PREVIA = {"proc": None, "projeto": None}
PORTA_PREVIA = int(os.environ.get("JARVIS_PREVIA_PORT", "8081"))


def previa(acao):
    """Servidor de prévia (php -S) do projeto atual, para ver o site em construção."""
    if PREVIA["proc"] and PREVIA["proc"].poll() is None:
        PREVIA["proc"].terminate()
        PREVIA["proc"].wait(timeout=5)
    PREVIA.update(proc=None, projeto=None)
    if acao != "iniciar":
        return "Prévia desligada."
    proj = estado.ler()["projeto"]
    if not proj:
        raise projetos.Erro("Escolha um projeto primeiro.")
    pasta = os.path.join(core.WORKSPACE, proj)
    raiz = next((os.path.join(pasta, d) for d in ("public", "public_html", "www", "dist", "build")
                 if os.path.isdir(os.path.join(pasta, d))), pasta)
    PREVIA["proc"] = subprocess.Popen(["php", "-S", f"0.0.0.0:{PORTA_PREVIA}", "-t", raiz], cwd=pasta,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    PREVIA["projeto"] = proj
    return f"👁 Prévia de {proj} ligada (pasta {os.path.relpath(raiz, core.WORKSPACE)})."


def pesquisar(tema):
    proj = estado.ler()["projeto"]
    destino, prompt = kb.prompt_pesquisa(tema)
    pool.de("_pesquisa").rodar(estado, prompt, False, lambda ev: publicar(ev, proj), cwd=kb.KB_DIR, usar_sessao=False,
                               projeto=proj)
    kb.sincronizar()
    if os.path.exists(destino):
        publicar({"tipo": "info", "texto": f"📚 Pesquisa salva na base de conhecimento: {os.path.relpath(destino, kb.KB_DIR)}"}, proj)


def iniciar(texto, veio_de_audio):
    if texto.startswith("/"):
        resposta, acao = core.comando(estado, pool, texto)
        if resposta is not None:
            publicar({"tipo": "usuario", "texto": texto})
            publicar({"tipo": "info", "texto": resposta})
            if acao == "compactar":
                threading.Thread(target=rodar, args=("", False, True, estado.ler()["projeto"]), daemon=True).start()
            elif acao == "pesquisar":
                threading.Thread(target=pesquisar, args=(texto.partition(" ")[2].strip(),), daemon=True).start()
            elif acao == "hermes":
                proj = estado.ler()["projeto"]
                threading.Thread(target=core.rodar_hermes, args=(texto.partition(" ")[2].strip(), proj,
                                 lambda tipo, t: publicar({"tipo": tipo, "texto": t}, proj)), daemon=True).start()
            return None
    est = estado.ler()
    if not est["projeto"]:
        return "Escolha um projeto primeiro."
    ok, motivo = pool.pode_iniciar(est["projeto"])
    if not ok:
        return motivo
    audio = est["audio"] == "sempre" or (est["audio"] == "auto" and veio_de_audio)
    publicar({"tipo": "usuario", "texto": texto, "projeto": est["projeto"]})
    threading.Thread(target=rodar, args=(texto, audio, False, est["projeto"]), daemon=True).start()
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
                               "ocupado": pool.de(est["projeto"]).ocupado, "pedido": pool.de(est["projeto"]).pedido,
                               "rodando": pool.resumo(), "limite": pool.limite,
                               "previa": PREVIA["projeto"] if PREVIA["proc"] and PREVIA["proc"].poll() is None else None,
                               "porta_previa": PORTA_PREVIA})
        if url.path in ("/api/github/repos", "/api/github/status"):
            try:
                if url.path.endswith("repos"):
                    return self._json({"repos": projetos.gh_repos()})
                proj = estado.ler()["projeto"]
                return self._json(projetos.status(proj) if proj else {"git": False, "gh": projetos.gh_ok()})
            except projetos.Erro as e:
                return self._json({"erro": str(e)}, 400)
        if url.path.startswith("/api/kb/"):
            q = urllib.parse.parse_qs(url.query)
            try:
                if url.path == "/api/kb/recentes":
                    return self._json({"notas": kb.recentes(q.get("tipo", [None])[0], 40)})
                if url.path == "/api/kb/buscar":
                    return self._json({"notas": kb.buscar(q.get("q", [""])[0], 20)})
                if url.path == "/api/kb/ler":
                    return self._json({"texto": kb.ler(q.get("c", [""])[0])})
            except projetos.Erro as e:
                return self._json({"erro": str(e)}, 400)
        if url.path == "/api/modelos":
            forcar = urllib.parse.parse_qs(url.query).get("atualizar", [""])[0] == "1"
            return self._json({"texto": core.texto_modelos_gateway(forcar)})
        if url.path == "/api/comandos":
            return self._json([{"cmd": c, "desc": d} for c, d in core.COMANDOS])
        if url.path == "/api/painel":
            return self._json(core.painel_projeto(estado.ler()["projeto"]))
        if url.path == "/api/eventos":
            q = urllib.parse.parse_qs(url.query)
            desde = int(q.get("desde", ["0"])[0])
            proj = q.get("projeto", [""])[0] or estado.ler()["projeto"] or "_geral"
            with ev_lock:
                novos = [e for e in eventos if e["id"] > desde and e.get("projeto") == proj]
                ultimo = _contador[0]
            ex = pool.de(proj)
            return self._json({"eventos": novos, "ultimo": ultimo, "ocupado": ex.ocupado, "projeto_ocupado": proj if ex.ocupado else None,
                               "pedido": ex.pedido, "rodando": pool.resumo(),
                               "desde_inicio": int(time.time() - ex.inicio) if ex.inicio else 0})
        if url.path == "/api/mapa":
            proj = estado.ler()["projeto"]
            caminho = os.path.join(core.WORKSPACE, proj or "", "docs", "mapa.html")
            if not proj or not os.path.isfile(caminho):
                return self._html("<body style='font-family:sans-serif;background:#05090f;color:#d6f1ff;padding:30px'>"
                                  "<h2>Mapa ainda não gerado</h2><p>No painel, envie <b>/jarvis:mapa</b> para gerar o "
                                  "mapa deste projeto (requer o Floorplan, instalado pelo <code>jarvis-extras</code>).</p></body>", 404)
            with open(caminho, encoding="utf-8") as f:
                return self._html(f.read())
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

        if url.path == "/api/upload":
            q = urllib.parse.parse_qs(url.query)
            try:
                msg = projetos.receber_upload(q.get("projeto", [""])[0], q.get("arquivo", ["arquivo"])[0], self._corpo())
                est = estado.ler()
                est["projeto"] = q.get("projeto", [""])[0]
                estado.salvar(est)
                publicar({"tipo": "info", "texto": "📦 " + msg})
                return self._json({"ok": True, "msg": msg})
            except projetos.Erro as e:
                return self._json({"erro": str(e)}, 400)
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
        if url.path.startswith("/api/projeto/novo") or url.path.startswith("/api/github/"):
            try:
                est = estado.ler()
                if url.path == "/api/projeto/novo":
                    nome = (dados.get("nome") or "").strip()
                    projetos.criar(nome)
                    est["projeto"] = nome
                    estado.salvar(est)
                    msg = f"✅ Projeto {nome} criado"
                    if dados.get("github"):
                        projetos.criar_repo(nome, privado=dados.get("privado", True))
                        msg += " e repositório criado no GitHub"
                elif url.path == "/api/github/clonar":
                    nome = projetos.clonar((dados.get("repo") or "").strip())
                    est["projeto"] = nome
                    estado.salvar(est)
                    msg = f"⬇️ {dados.get('repo')} clonado em {nome}"
                elif not est["projeto"]:
                    return self._json({"erro": "Escolha um projeto primeiro."}, 400)
                elif url.path == "/api/github/criar":
                    projetos.criar_repo(est["projeto"], privado=dados.get("privado", True))
                    msg = f"✅ Repositório {est['projeto']} criado no GitHub"
                elif url.path == "/api/github/enviar":
                    msg = "⬆️ " + projetos.enviar(est["projeto"], dados.get("mensagem", ""))
                elif url.path == "/api/github/atualizar":
                    msg = "🔄 " + projetos.atualizar(est["projeto"])
                else:
                    return self._json({"erro": "não encontrado"}, 404)
                publicar({"tipo": "info", "texto": msg})
                return self._json({"ok": True, "msg": msg})
            except projetos.Erro as e:
                return self._json({"erro": str(e)}, 400)
        if url.path == "/api/previa":
            try:
                msg = previa(dados.get("acao", "iniciar"))
                publicar({"tipo": "sistema", "texto": msg})
                return self._json({"ok": True, "msg": msg, "porta": PORTA_PREVIA})
            except projetos.Erro as e:
                return self._json({"erro": str(e)}, 400)
        if url.path == "/api/kb/ideia":
            texto = (dados.get("texto") or "").strip()
            if not texto:
                return self._json({"erro": "Escreva a ideia."}, 400)
            caminho = kb.salvar("ideias", texto.split("\n")[0][:70], texto, tags=["ideia"], projeto=estado.ler()["projeto"])
            publicar({"tipo": "info", "texto": f"💡 Ideia guardada: {caminho}"})
            return self._json({"ok": True, "caminho": caminho})
        if url.path == "/api/parar":
            return self._json({"ok": pool.de(estado.ler()["projeto"]).parar()})
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
    carregar_historico()
    threading.Thread(target=kb.garantir, daemon=True).start()
    kb.iniciar_sincronizacao_periodica(10)
    ThreadingHTTPServer(("0.0.0.0", PORTA), Handler).serve_forever()


if __name__ == "__main__":
    main()
