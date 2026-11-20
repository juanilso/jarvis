"""Núcleo compartilhado entre o bot do Telegram e a página web do Jarvis.

- Estado por interface (projeto atual, sessão do Claude por projeto, preferências)
- Execução do Claude Code em modo não interativo com eventos dos agentes (stream-json)
- Transcrição local (faster-whisper) e voz (edge-tts)
"""
import json
import os
import re
import subprocess
import threading
import time

WORKSPACE = os.environ.get("JARVIS_WORKSPACE", "/workspace")
TIMEOUT = int(os.environ.get("JARVIS_TIMEOUT_MIN", "120")) * 60
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
TTS_VOICE = os.environ.get("TTS_VOICE", "pt-BR-AntonioNeural")
CONFIG_DIR = os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))

EMOJI = {"arquiteto": "🏛️", "explorador": "🔎", "desenvolvedor": "💻", "dba": "🗄️", "android": "🤖",
         "testador": "🧪", "revisor": "🧐", "deploy": "🚀", "documentador": "📝"}

MARCA_RESUMO = "RESUMO_FALADO:"
INSTRUCAO_AUDIO = (
    f"\n\n[Instrução da interface: a resposta também será ouvida em áudio. No FINAL, escreva uma linha "
    f"começando com '{MARCA_RESUMO}' com 2 a 4 frases curtas, em português, sem código, sem caminhos "
    f"de arquivo e sem markdown, resumindo o resultado e o próximo passo.]"
)

_whisper = {"model": None, "lock": threading.Lock()}


# ------------------------------------------------------------------ estado
class Estado:
    def __init__(self, nome, padrao=None):
        self.arquivo = os.path.join(CONFIG_DIR, f"{nome}-state.json")
        self.padrao = {"projeto": None, "sessoes": {}, "audio": "auto", "agentes": True, **(padrao or {})}

    def ler(self):
        try:
            with open(self.arquivo) as f:
                est = json.load(f)
        except Exception:  # noqa: BLE001
            est = {}
        for k, v in self.padrao.items():
            est.setdefault(k, v if not isinstance(v, dict) else dict(v))
        return est

    def salvar(self, est):
        os.makedirs(os.path.dirname(self.arquivo), exist_ok=True)
        with open(self.arquivo, "w") as f:
            json.dump(est, f, indent=2)


def listar_projetos():
    try:
        return sorted(d for d in os.listdir(WORKSPACE)
                      if os.path.isdir(os.path.join(WORKSPACE, d)) and not d.startswith("."))
    except FileNotFoundError:
        return []


# ------------------------------------------------------------------ áudio
def _carregar_audio(caminho):
    """Converte qualquer áudio (ogg, webm, mp4, mp3) para 16 kHz mono via ffmpeg.
    Evita depender do PyAV, cujas versões novas quebram o faster-whisper."""
    import numpy as np
    bruto = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", caminho,
                            "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                           capture_output=True, check=True, timeout=180).stdout
    return np.frombuffer(bruto, dtype=np.float32)


def transcrever(caminho):
    audio = _carregar_audio(caminho)
    if audio.size < 1600:  # menos de 0,1 s
        return ""
    with _whisper["lock"]:
        if _whisper["model"] is None:
            from faster_whisper import WhisperModel  # carregado só quando necessário
            _whisper["model"] = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        segmentos, _ = _whisper["model"].transcribe(audio, language="pt", vad_filter=True)
        return " ".join(s.text.strip() for s in segmentos).strip()


def limpar_para_fala(texto):
    texto = re.sub(r"```.*?```", " ", texto or "", flags=re.S)
    texto = re.sub(r"`[^`]*`", " ", texto)
    texto = re.sub(r"https?://\S+", " ", texto)
    texto = re.sub(r"[#*_>|\[\]]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()[:900]


def gerar_mp3(texto, destino):
    """Gera a fala em MP3. Retorna True se conseguiu."""
    texto = limpar_para_fala(texto)
    if not texto:
        return False
    subprocess.run(["edge-tts", "--voice", TTS_VOICE, "--text", texto, "--write-media", destino],
                   check=True, capture_output=True, timeout=120)
    return True


# ------------------------------------------------------------------ claude
class Execucao:
    """Um pedido ao Claude rodando em segundo plano, com eventos para a interface."""

    def __init__(self):
        self.proc = None
        self.inicio = None
        self.pedido = None
        self.projeto = None
        self._lock = threading.Lock()

    @property
    def ocupado(self):
        return self.proc is not None

    def parar(self):
        if self.proc:
            self.proc.terminate()
            return True
        return False

    def rodar(self, estado, texto, responder_audio, ao_evento):
        """Executa (bloqueante). ao_evento(dict) recebe:
        {"tipo": "agente_inicio"|"agente_fim"|"resposta"|"erro", ...}"""
        est = estado.ler()
        projeto = est["projeto"]
        cmd = ["claude", "-p", texto + (INSTRUCAO_AUDIO if responder_audio else ""),
               "--output-format", "stream-json", "--verbose", "--dangerously-skip-permissions"]
        if est["sessoes"].get(projeto):
            cmd += ["--resume", est["sessoes"][projeto]]
        agentes, resultado, code, erro = {}, None, None, ""
        try:
            with self._lock:
                self.proc = subprocess.Popen(cmd, cwd=os.path.join(WORKSPACE, projeto), stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE, text=True, bufsize=1)
                self.inicio, self.pedido, self.projeto = time.time(), texto[:80], projeto
            timer = threading.Timer(TIMEOUT, self.proc.kill)
            timer.start()
            for linha in self.proc.stdout:
                try:
                    ev = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                conteudo = (ev.get("message") or {}).get("content") or []
                if ev.get("type") == "assistant" and est["agentes"]:
                    for c in conteudo:
                        if c.get("type") == "tool_use" and c.get("name") in ("Task", "Agent"):
                            ent = c.get("input") or {}
                            nome = (ent.get("subagent_type") or "agente").split(":")[-1]
                            agentes[c.get("id")] = (nome, time.time())
                            ao_evento({"tipo": "agente_inicio", "agente": nome, "emoji": EMOJI.get(nome, "🧩"),
                                       "descricao": ent.get("description", "")})
                elif ev.get("type") == "user" and est["agentes"]:
                    for c in conteudo:
                        if c.get("type") == "tool_result" and c.get("tool_use_id") in agentes:
                            nome, ini = agentes.pop(c["tool_use_id"])
                            ao_evento({"tipo": "agente_fim", "agente": nome, "emoji": EMOJI.get(nome, "🧩"),
                                       "erro": bool(c.get("is_error")), "segundos": int(time.time() - ini)})
                elif ev.get("type") == "result":
                    resultado = ev
            self.proc.wait()
            timer.cancel()
            erro, code = self.proc.stderr.read(), self.proc.returncode
        finally:
            with self._lock:
                self.proc = self.inicio = self.pedido = self.projeto = None

        if resultado is None:
            msg = "Interrompido (parar ou tempo limite)." if code in (-9, -15) else \
                "Erro ao executar o Claude: " + (erro or "sem detalhes")[-3000:]
            ao_evento({"tipo": "erro", "texto": msg})
            return
        if resultado.get("session_id"):
            est = estado.ler()
            est["sessoes"][projeto] = resultado["session_id"]
            estado.salvar(est)
        resposta, resumo = resultado.get("result") or "", ""
        if MARCA_RESUMO in resposta:
            resposta, _, resumo = resposta.rpartition(MARCA_RESUMO)
            resposta, resumo = resposta.strip(), resumo.strip()
        ao_evento({"tipo": "resposta", "texto": resposta, "resumo": resumo or resposta,
                   "custo": resultado.get("total_cost_usd"), "erro": bool(resultado.get("is_error")),
                   "audio": responder_audio})


# ------------------------------------------------------------------ painel do projeto
def _ler(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def painel_projeto(projeto):
    """Resumo dos docs do Jarvis para o painel: perfil, estado, backlog e decisões pendentes."""
    vazio = {"perfil": None, "estado": [], "contagem": {}, "proximas": [], "decisoes": [], "adotado": False}
    if not projeto:
        return vazio
    docs = os.path.join(WORKSPACE, projeto, "docs")
    if not os.path.isdir(docs):
        return vazio
    res = dict(vazio, adotado=True)
    m = re.search(r"Perfil ativo:\s*(\w+)", _ler(os.path.join(docs, "ORQUESTRACAO.md")))
    res["perfil"] = m.group(1) if m else None
    res["estado"] = [l.strip("- ").strip() for l in _ler(os.path.join(docs, "ESTADO.md")).splitlines()
                     if l.strip().startswith("-")][:6]
    for linha in _ler(os.path.join(docs, "BACKLOG.md")).splitlines():
        cols = [c.strip() for c in linha.strip().strip("|").split("|")]
        if len(cols) >= 3 and re.match(r"T-\d+", cols[0]):
            st = (cols[1].split()[0] if cols[1] else "pendente").lower()
            res["contagem"][st] = res["contagem"].get(st, 0) + 1
            if st in ("pendente", "em_andamento") and len(res["proximas"]) < 5:
                res["proximas"].append({"id": cols[0], "status": st, "titulo": cols[2]})
    titulo = None
    for linha in _ler(os.path.join(docs, "DECISOES-PENDENTES.md")).splitlines():
        h = re.match(r"##\s*(D-\d+)\s*[—-]\s*(.+)", linha)
        if h:
            titulo = (h.group(1), h.group(2).strip())
        elif titulo and re.search(r"Status:\s*pendente", linha):
            res["decisoes"].append({"id": titulo[0], "titulo": titulo[1]})
            titulo = None
    return res
