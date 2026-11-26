"""Central de chaves do Jarvis: trocar, testar e remover as chaves pelo painel, sem editar arquivo na VPS.

- As chaves trocadas pelo painel ficam em <config do Claude>/jarvis-chaves.json (600, volume do Jarvis) e valem
  por cima do .env (.env.ajudantes). Remover pelo painel desliga a chave mesmo que ela esteja no .env.
- Vale na hora, em todos os contêineres (Telegram, painel, agentes): quem usa chama aplicar(), que relê o arquivo
  quando ele muda.
- O painel só mostra o final da chave (···abcd). Trocar ou remover pede a senha do painel de novo, fica registrado
  e avisa você no Telegram (sem a chave).
- Endereços (URL base) NÃO são editáveis por aqui: trocar o endereço desviaria tudo o que o Jarvis manda para outro
  servidor; isso continua só no .env da VPS.
"""
import json
import os
import re
import threading
import time

CONFIG_DIR = os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))
ARQ = os.path.join(CONFIG_DIR, "jarvis-chaves.json")
LOG = os.path.join(CONFIG_DIR, "jarvis-chaves.log")
_trava = threading.Lock()
_lido = {"mtime": None, "aplicadas": set()}
_original = {}  # valor do .env antes do painel (para "voltar ao .env")

# env: (nome, grupo, onde gerar)
CATALOGO = {
    "GEMINI_API_KEY": ("Google Gemini (ajudante, vídeos com IA, arte do banner)", "IAs", "aistudio.google.com/apikey"),
    "DEEPSEEK_API_KEY": ("DeepSeek", "IAs", "platform.deepseek.com/api_keys"),
    "OLLAMA_API_KEY": ("Ollama Cloud", "IAs", "ollama.com/settings/keys"),
    "GROQ_API_KEY": ("Groq", "IAs", "console.groq.com/keys"),
    "OPENROUTER_API_KEY": ("OpenRouter", "IAs", "openrouter.ai/keys"),
    "MISTRAL_API_KEY": ("Mistral", "IAs", "console.mistral.ai/api-keys"),
    "XAI_API_KEY": ("Grok (xAI)", "IAs", "console.x.ai"),
    "NVIDIA_API_KEY": ("NVIDIA", "IAs", "build.nvidia.com"),
    "CLOUDFLARE_API_TOKEN": ("Cloudflare Workers AI (token)", "IAs", "dash.cloudflare.com/profile/api-tokens"),
    "CLOUDFLARE_ACCOUNT_ID": ("Cloudflare Workers AI (ID da conta)", "IAs", "dash.cloudflare.com"),
}
TESTE_PROVEDOR = {"GEMINI_API_KEY": "gemini", "DEEPSEEK_API_KEY": "deepseek", "OLLAMA_API_KEY": "ollama",
                  "GROQ_API_KEY": "groq", "OPENROUTER_API_KEY": "openrouter", "MISTRAL_API_KEY": "mistral",
                  "XAI_API_KEY": "grok", "NVIDIA_API_KEY": "nvidia", "CLOUDFLARE_API_TOKEN": "cloudflare"}


def _ler():
    try:
        with open(ARQ, encoding="utf-8") as f:
            d = json.load(f)
        return {k: v for k, v in d.items() if k in CATALOGO and isinstance(v, str)}
    except (OSError, ValueError):
        return {}


def aplicar(forcar=False):
    """Põe as chaves do painel no ambiente deste processo (só relê quando o arquivo muda)."""
    try:
        mt = os.path.getmtime(ARQ)
    except OSError:
        mt = 0
    if not forcar and mt == _lido["mtime"]:
        return
    with _trava:
        dados = _ler()
        for k in _lido["aplicadas"] - set(dados):  # tirada do painel: volta ao valor do .env
            if k in _original:
                os.environ[k] = _original[k]
        for k, v in dados.items():
            _original.setdefault(k, os.environ.get(k, ""))
            os.environ[k] = v  # "" = desligada pelo painel
        _lido.update(mtime=mt, aplicadas=set(dados))


def _final(v):
    return ("···" + v[-4:]) if len(v) > 8 else ("definida" if v else "")


def lista():
    aplicar()
    painel = _ler()
    itens = []
    for env, (nome, grupo, onde) in CATALOGO.items():
        v = os.environ.get(env, "")
        origem = "painel" if env in painel and painel[env] else "desligada no painel" if env in painel else \
            (".env" if v else "")
        itens.append({"env": env, "nome": nome, "grupo": grupo, "onde": onde, "final": _final(v),
                      "configurada": bool(v), "origem": origem, "testavel": env in TESTE_PROVEDOR})
    return itens


def _registrar(acao, env, quem="painel"):
    try:
        fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps({"quando": time.strftime("%Y-%m-%d %H:%M:%S"), "acao": acao, "chave": env,
                                "quem": quem}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _gravar(dados):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = ARQ + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
        json.dump(dados, f)
    os.replace(tmp, ARQ)


def definir(env, valor):
    if env not in CATALOGO:
        raise ValueError("chave desconhecida")
    valor = (valor or "").strip()
    if not valor:
        raise ValueError("cole a chave")
    if env == "CLOUDFLARE_ACCOUNT_ID":
        if not re.fullmatch(r"[0-9a-f]{32}", valor):
            raise ValueError("o ID da conta Cloudflare tem 32 caracteres (0-9, a-f)")
    elif not re.fullmatch(r"[A-Za-z0-9_\-.:/+=]{12,400}", valor):
        raise ValueError("formato inesperado (sem espaços; confira se copiou a chave inteira)")
    with _trava:
        d = _ler()
        d[env] = valor
        _gravar(d)
    _registrar("trocou", env)
    aplicar(forcar=True)
    return _final(valor)


def remover(env, voltar_env=False):
    """Desliga a chave (mesmo que esteja no .env). voltar_env=True: tira só a do painel e volta a valer a do .env."""
    if env not in CATALOGO:
        raise ValueError("chave desconhecida")
    with _trava:
        d = _ler()
        if voltar_env:
            d.pop(env, None)
        else:
            d[env] = ""
        _gravar(d)
    _registrar("voltou ao .env" if voltar_env else "removeu", env)
    aplicar(forcar=True)


def testar(env):
    aplicar()
    nome = TESTE_PROVEDOR.get(env)
    if not nome:
        return {"ok": False, "texto": "esta chave não tem teste automático"}
    if not os.environ.get(env):
        return {"ok": False, "texto": "chave não configurada"}
    import ajudantes
    try:
        r = ajudantes.perguntar("Responda só: ok", contexto="teste de chave", ia=nome, maximo=20)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "texto": f"{type(e).__name__}: {str(e)[:200]}"}
    if r.get("ok"):
        return {"ok": True, "texto": f"funcionando ({r.get('modelo', nome)})"}
    return {"ok": False, "texto": ("; ".join(r.get("tentativas", [])) or r.get("erro", "não respondeu"))[:300]}


def historico(n=12):
    try:
        with open(LOG, encoding="utf-8") as f:
            return [json.loads(x) for x in f.readlines()[-n:]][::-1]
    except (OSError, ValueError):
        return []


# ------------------------------------------------------------ conexões por login (Canva, Picsart…)

CONEXOES = {"canva": "Canva", "picsart-gen-ai": "Picsart"}


def conexoes():
    """Status das conexões MCP por login (OAuth), pelo `claude mcp list`."""
    import subprocess
    try:
        r = subprocess.run(["claude", "mcp", "list"], capture_output=True, text=True, timeout=60)
        saida = r.stdout + r.stderr
    except Exception as e:  # noqa: BLE001
        return [{"id": k, "nome": n, "status": f"não consegui verificar ({type(e).__name__})"} for k, n in CONEXOES.items()]
    res = []
    for k, n in CONEXOES.items():
        linha = next((ln for ln in saida.splitlines() if re.search(rf"(^|[:\s]){re.escape(k)}\b", ln, re.I)), "")
        if not linha:
            st = "não instalado"
        elif "✓" in linha or "connected" in linha.lower() and "not" not in linha.lower():
            st = "conectado"
        elif "auth" in linha.lower():
            st = "precisa entrar na conta"
        else:
            st = "com erro"
        res.append({"id": k, "nome": n, "status": st})
    return res
