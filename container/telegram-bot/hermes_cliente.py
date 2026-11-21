"""Cliente do Hermes Agent (Nous Research) para o Jarvis.

O Hermes roda num contêiner separado (serviço `hermes`, perfil `hermes` do docker compose) e expõe uma API
no formato OpenAI em http://hermes:8642/v1. Ele enxerga /workspace só para leitura: quem altera código é o Jarvis.
"""
import json
import os
import re
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
    "Se o pedido exigir mudar código, descreva o que mudar e o Jarvis executa. "
    "Arquivos que o usuário pedir (zip, relatório, planilha) você salva em /saida (ele vê em /workspace/.hermes-saida). "
    "Faça o que foi pedido usando as suas ferramentas antes de pesquisar na internet."
)
LEMBRETE = "[Responda SEMPRE em português do Brasil, mesmo que as fontes estejam em inglês.]\n\n"
_EN = set("the and is are of to for with this that you your can not there these which from have has be by on as it".split())
_PT = set("o a os as de do da dos das para com que não é são um uma você seu sua por no na nos se mais como".split())


def em_ingles(texto):
    """Heurística simples: mais palavras comuns do inglês que do português."""
    pal = re.findall(r"[a-zA-ZÀ-ú]+", texto.lower())[:400]
    en, pt = sum(p in _EN for p in pal), sum(p in _PT for p in pal)
    return en >= 8 and en > pt * 1.5
_ocupado = threading.Lock()
MARCA = "/tmp/jarvis-hermes.ocupado"  # visível para o painel quando um agente chama o jarvis-hermes


def ocupado():
    """True se o Hermes está atendendo um pedido (deste processo ou de um agente via jarvis-hermes)."""
    if _ocupado.locked():
        return True
    try:
        pid = int(open(MARCA).read().strip() or 0)
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


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
        open(MARCA, "w").write(str(os.getpid()))
    except OSError:
        pass
    try:
        try:
            modelos = _pedir("/v1/models").get("data", [])
            modelo = (modelos[0].get("id") if modelos and isinstance(modelos[0], dict) else None) or "hermes-agent"
        except ErroHermes:
            modelo = "hermes-agent"
        contexto = f"\nProjeto atual: /workspace/{projeto} (somente leitura)." if projeto else ""
        j = _pedir("/v1/chat/completions", {
            "model": modelo, "stream": False,
            "messages": [{"role": "system", "content": REGRAS + contexto}, {"role": "user", "content": LEMBRETE + texto}],
        }, tempo=TEMPO)
        try:
            resposta = j["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ErroHermes(f"resposta inesperada: {str(j)[:300]}")
        if isinstance(resposta, list):  # alguns servidores devolvem partes
            resposta = "".join(p.get("text", "") for p in resposta if isinstance(p, dict))
        resposta = (resposta or "").strip() or "(o Hermes respondeu vazio)"
        if em_ingles(resposta):  # o Hermes às vezes segue o idioma das fontes; pede a tradução uma vez
            try:
                t = _pedir("/v1/chat/completions", {"model": modelo, "stream": False, "messages": [
                    {"role": "user", "content": "Traduza para português do Brasil, mantendo links, listas e código. "
                                                "Responda só com a tradução:\n\n" + resposta}]}, tempo=300)
                traducao = (t["choices"][0]["message"]["content"] or "").strip()
                if traducao:
                    resposta = traducao
            except (ErroHermes, KeyError, IndexError, TypeError):
                pass
        return resposta
    finally:
        _ocupado.release()
        try:
            os.remove(MARCA)
        except OSError:
            pass
