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
        self.padrao = {"projeto": None, "sessoes": {}, "audio": "auto", "agentes": True, "modelo": None,
                       "resumos": {}, "custos": {}, **(padrao or {})}

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

    def rodar(self, estado, texto, responder_audio, ao_evento, compactar=False, cwd=None, usar_sessao=True):
        """Executa (bloqueante). ao_evento(dict) recebe:
        {"tipo": "agente_inicio"|"agente_fim"|"resposta"|"erro"|"info", ...}
        compactar=True: resume a conversa, encerra a sessão e guarda o resumo como contexto."""
        est = estado.ler()
        projeto = est["projeto"]
        if not usar_sessao:  # tarefa avulsa (ex.: pesquisa): sem retomar nem salvar a conversa do projeto
            est = dict(est, sessoes={}, resumos={})
        resumo_usado = None
        if compactar:
            if not est["sessoes"].get(projeto):
                ao_evento({"tipo": "info", "texto": "Não há conversa para compactar neste projeto."})
                return
            prompt = PROMPT_COMPACTAR
        else:
            prompt = texto + (INSTRUCAO_AUDIO if responder_audio else "")
            resumo_usado = est["resumos"].get(projeto) if not est["sessoes"].get(projeto) else None
            if resumo_usado and texto.startswith("/"):
                resumo_usado = "comando"  # comandos "/" rodam sem o resumo; ele fica guardado para a próxima mensagem
            elif resumo_usado:
                prompt = f"[Contexto resumido da conversa anterior]\n{resumo_usado}\n\n[Nova mensagem]\n{prompt}"
        cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--dangerously-skip-permissions"]
        if est.get("modelo"):
            cmd += ["--model", est["modelo"]]
        if est["sessoes"].get(projeto):
            cmd += ["--resume", est["sessoes"][projeto]]
        agentes, resultado, code, erro = {}, None, None, ""
        try:
            with self._lock:
                self.proc = subprocess.Popen(cmd, cwd=cwd or os.path.join(WORKSPACE, projeto), stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE, text=True, bufsize=1)
                self.inicio, self.pedido, self.projeto = time.time(), texto[:80], projeto or "conhecimento"
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
        est = estado.ler()
        if resultado.get("total_cost_usd"):
            chave = projeto if usar_sessao else "conhecimento"
            est["custos"][chave] = round(est["custos"].get(chave, 0) + resultado["total_cost_usd"], 6)
        if not usar_sessao:
            estado.salvar(est)
            resposta = resultado.get("result") or ""
            ao_evento({"tipo": "resposta", "texto": resposta, "resumo": resposta, "custo": resultado.get("total_cost_usd"),
                       "erro": bool(resultado.get("is_error")), "audio": responder_audio})
            return
        if compactar:
            resumo = (resultado.get("result") or "").strip()
            est["sessoes"].pop(projeto, None)
            est["resumos"][projeto] = resumo
            estado.salvar(est)
            ao_evento({"tipo": "info", "texto": "🗜️ Conversa compactada. A próxima mensagem começa uma sessão nova "
                                                "com este resumo como contexto:\n\n" + resumo})
            return
        if resultado.get("session_id") and resumo_usado != "comando":
            est["sessoes"][projeto] = resultado["session_id"]
            if resumo_usado:
                est["resumos"].pop(projeto, None)
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


# ------------------------------------------------------------------ comandos "/"
PROMPT_COMPACTAR = (
    "Resuma esta conversa para continuarmos depois numa sessão nova, em português, em no máximo 25 linhas: "
    "objetivo, o que já foi feito, decisões tomadas, arquivos importantes, pendências e próximo passo. "
    "Responda apenas com o resumo, sem executar nenhuma ação."
)
MODELOS = {"sonnet", "opus", "haiku", "padrao"}
COMANDOS = [
    ("/ajuda", "Lista os comandos"),
    ("/ideia", "Guarda uma ideia na base de conhecimento"),
    ("/lembrar", "Procura na base de conhecimento"),
    ("/pesquisar", "Pesquisa na internet e salva com as fontes"),
    ("/sincronizar", "Envia a base de conhecimento para o GitHub agora"),
    ("/projetos", "Lista os projetos"),
    ("/projeto", "Escolhe o projeto: /projeto <nome>"),
    ("/status", "O que está rodando agora"),
    ("/compactar", "Resume a conversa e libera contexto (economiza tokens)"),
    ("/novo", "Começa uma conversa nova, sem resumo"),
    ("/parar", "Interrompe o trabalho em andamento"),
    ("/modelo", "Modelo da sessão: sonnet, opus, haiku ou padrao"),
    ("/custo", "Gasto estimado do projeto atual"),
    ("/audio", "Resposta em áudio: auto, sempre ou nunca"),
    ("/agentes", "Avisos dos agentes: on ou off"),
    ("/jarvis:status", "Jarvis: resumo do projeto"),
    ("/jarvis:executar", "Jarvis: executa o backlog sozinho"),
    ("/jarvis:decidir", "Jarvis: responde decisões pendentes"),
    ("/jarvis:evoluir", "Jarvis: propõe uma mudança"),
    ("/jarvis:adotar", "Jarvis: estuda um projeto existente"),
    ("/jarvis:novo", "Jarvis: inicia um projeto novo"),
    ("/jarvis:modelos", "Jarvis: perfil de modelos dos agentes"),
    ("/jarvis:jarvis", "Jarvis: pedido livre"),
]
LOCAIS = {c for c, _ in COMANDOS if not c.startswith("/jarvis:")}


def comando(estado, execucao, texto):
    """Comandos do painel/Telegram. Retorna (resposta, acao) ou (None, None) se não for comando local.
    acao="compactar" pede para a interface rodar a compactação em segundo plano."""
    cmd, _, resto = texto.strip().partition(" ")
    cmd = cmd.split("@")[0].lower()
    if cmd not in LOCAIS:
        return None, None
    arg = resto.strip()
    est = estado.ler()
    proj = est["projeto"]
    if cmd in ("/ideia", "/lembrar", "/sincronizar", "/pesquisar"):
        import kb  # import tardio (kb depende deste módulo)
        if cmd == "/ideia":
            if not arg:
                return "Escreva a ideia depois do comando: /ideia app de agendamento para barbearias", None
            titulo = arg.split("\n")[0][:70]
            caminho = kb.salvar("ideias", titulo, arg, tags=["ideia"], projeto=proj)
            return f"💡 Ideia guardada: {caminho}", None
        if cmd == "/lembrar":
            if not arg:
                rec = kb.recentes(limite=8)
                return ("🧠 Últimas notas:\n" + "\n".join(f"• {r['titulo']} ({r['caminho']})" for r in rec)) if rec \
                    else "A base de conhecimento ainda está vazia. Use /ideia ou /pesquisar.", None
            res = kb.buscar(arg)
            if not res:
                return f"Não encontrei nada sobre “{arg}” na base de conhecimento.", None
            return "🧠 Encontrei:\n\n" + "\n\n".join(f"• {r['titulo']} ({r['caminho']})\n  …{r['trecho']}…" for r in res[:5]), None
        if cmd == "/sincronizar":
            kb.garantir()
            r = kb.sincronizar()
            return {"ok": "☁️ Base de conhecimento salva no GitHub.", "sem remoto": "Base salva localmente "
                    "(configure GH_TOKEN para ter cópia no GitHub)."}.get(r, f"Sincronização: {r}"), None
        if cmd == "/pesquisar":
            if not arg:
                return "Diga o tema: /pesquisar melhores gateways de pagamento PIX para PHP", None
            if execucao.ocupado:
                return "Espere o pedido atual terminar (ou use /parar) para pesquisar.", None
            return f"🔎 Pesquisando “{arg}”… aviso quando terminar.", "pesquisar"
    if cmd == "/ajuda":
        return "\n".join(f"{c} — {d}" for c, d in COMANDOS), None
    if cmd == "/projetos":
        ps = listar_projetos()
        return ("📁 Projetos:\n" + "\n".join(f"• {p}" for p in ps)) if ps else "Nenhum projeto em /workspace.", None
    if cmd == "/projeto":
        if arg not in listar_projetos():
            return "Projeto não encontrado. Use /projetos para ver os nomes.", None
        est["projeto"] = arg
        estado.salvar(est)
        return f"✅ Projeto atual: {arg}", None
    if cmd == "/status":
        if execucao.ocupado:
            mins = int((time.time() - execucao.inicio) // 60)
            return f"🔄 Rodando há {mins} min em {execucao.projeto}: “{execucao.pedido}”", None
        extra = " · conversa compactada (resumo pronto)" if est["resumos"].get(proj) else ""
        return f"💤 Livre · projeto: {proj or 'nenhum'} · modelo: {est.get('modelo') or 'padrão'}{extra}", None
    if cmd == "/novo":
        est["sessoes"].pop(proj, None)
        est["resumos"].pop(proj, None)
        estado.salvar(est)
        return "🆕 A próxima mensagem começa uma conversa nova, sem contexto anterior.", None
    if cmd == "/parar":
        return ("⛔ Parando…" if execucao.parar() else "Nada rodando."), None
    if cmd == "/compactar":
        if not proj:
            return "Escolha um projeto primeiro.", None
        if execucao.ocupado:
            return "Espere o pedido atual terminar (ou use /parar) para compactar.", None
        return "🗜️ Compactando a conversa…", "compactar"
    if cmd == "/modelo":
        a = arg.lower()
        if a not in MODELOS:
            return f"Modelo atual: {est.get('modelo') or 'padrão'}. Use /modelo sonnet, opus, haiku ou padrao.", None
        est["modelo"] = None if a == "padrao" else a
        estado.salvar(est)
        return f"🧠 Modelo da sessão: {est['modelo'] or 'padrão'} (os agentes do Jarvis seguem o perfil do projeto)", None
    if cmd == "/custo":
        c = est["custos"].get(proj, 0)
        tot = sum(est["custos"].values())
        return f"💲 {proj or 'nenhum projeto'}: US$ {c:.4f} · todos os projetos: US$ {tot:.4f} (estimativa deste canal)", None
    if cmd == "/audio":
        if arg.lower() not in ("auto", "sempre", "nunca"):
            return f"Áudio: {est['audio']}. Use /audio auto, sempre ou nunca.", None
        est["audio"] = arg.lower()
        estado.salvar(est)
        return f"🔊 Resposta em áudio: {est['audio']}", None
    if cmd == "/agentes":
        if arg.lower() not in ("on", "off"):
            return f"Avisos de agentes: {'on' if est['agentes'] else 'off'}. Use /agentes on ou off.", None
        est["agentes"] = arg.lower() == "on"
        estado.salvar(est)
        return f"👥 Avisos de agentes: {arg.lower()}", None
    return None, None
