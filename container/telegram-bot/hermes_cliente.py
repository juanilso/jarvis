"""Cliente do Hermes Agent (Nous Research) para o Jarvis.

O Hermes roda num contêiner separado (serviço `hermes`, perfil `hermes` do docker compose) e expõe uma API
no formato OpenAI em http://hermes:8642/v1. Ele enxerga /workspace só para leitura: quem altera código é o Jarvis.
"""
import json
import os
import threading
import urllib.error
import urllib.request

URL = os.environ.get("HERMES_URL", "http://hermes:8642").rstrip("/")
CHAVE = os.environ.get("HERMES_API_KEY", "")
TEMPO = int(os.environ.get("HERMES_TIMEOUT", "900"))
REGRAS = (
    "Você é o Hermes, ajudante do Jarvis (o orquestrador de projetos do usuário). Responda em português do Brasil, "
    "de forma objetiva. A pasta /workspace é somente leitura para você: não tente alterar projetos, só analise e "
    "devolva o resultado. Nunca exponha chaves, senhas ou tokens. Ao pesquisar na internet, liste as fontes (links). "
    "Se o pedido exigir mudar código, descreva o que mudar e o Jarvis executa."
)
_ocupado = threading.Lock()


class ErroHermes(Exception):
    pass


def _pedir(caminho, corpo=None, tempo=20):
    cab = {"Accept": "application/json", "Content-Type": "application/json"}
    if CHAVE:
        cab["Authorization"] = f"Bearer {CHAVE}"
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(URL + caminho, data=dados, headers=cab, method="POST" if dados else "GET")
    try:
        with urllib.request.urlopen(req, timeout=tempo) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:300]
        if e.code in (401, 403):
            raise ErroHermes("o Hermes recusou a chave (confira HERMES_API_KEY no .env.claude)") from e
        raise ErroHermes(f"HTTP {e.code}: {detalhe}") from e
    except urllib.error.URLError as e:
        raise ErroHermes(f"não consegui falar com o Hermes em {URL} ({e.reason}). "
                         "Ele está ligado? docker compose --profile hermes up -d") from e


def configurado():
    return bool(CHAVE)


def status():
    """Texto curto dizendo se o Hermes está disponível."""
    if not configurado():
        return ("🤝 Hermes não configurado. Na VPS, dentro de container/: ./hermes-configurar.sh "
                "(veja o LEIA-ME, seção Hermes).")
    try:
        j = _pedir("/v1/models")
        nomes = [m.get("id") for m in j.get("data", []) if isinstance(m, dict)]
        return f"🤝 Hermes ligado ({URL}) · perfil: {', '.join(nomes) or 'hermes-agent'}" + \
            (" · ocupado agora" if _ocupado.locked() else "")
    except ErroHermes as e:
        return f"⚠️ Hermes: {e}"


def perguntar(texto, projeto=None):
    """Manda um pedido ao Hermes e devolve a resposta em texto. Um pedido por vez."""
    if not configurado():
        raise ErroHermes("Hermes não configurado (falta HERMES_API_KEY). Rode ./hermes-configurar.sh na VPS.")
    if not _ocupado.acquire(blocking=False):
        raise ErroHermes("o Hermes já está trabalhando em outro pedido; tente quando ele terminar.")
    try:
        try:
            modelos = _pedir("/v1/models").get("data", [])
            modelo = (modelos[0].get("id") if modelos and isinstance(modelos[0], dict) else None) or "hermes-agent"
        except ErroHermes:
            modelo = "hermes-agent"
        contexto = f"\nProjeto atual: /workspace/{projeto} (somente leitura)." if projeto else ""
        j = _pedir("/v1/chat/completions", {
            "model": modelo, "stream": False,
            "messages": [{"role": "system", "content": REGRAS + contexto}, {"role": "user", "content": texto}],
        }, tempo=TEMPO)
        try:
            resposta = j["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ErroHermes(f"resposta inesperada: {str(j)[:300]}")
        if isinstance(resposta, list):  # alguns servidores devolvem partes
            resposta = "".join(p.get("text", "") for p in resposta if isinstance(p, dict))
        return (resposta or "").strip() or "(o Hermes respondeu vazio)"
    finally:
        _ocupado.release()
