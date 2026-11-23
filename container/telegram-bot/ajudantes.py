"""Ajudantes: outras IAs (Gemini, Grok, OpenRouter, Groq…) como mão de obra barata do Jarvis.

O Jarvis (Claude) continua o chefe: manda tarefas de TEXTO (rascunhos, traduções, textos de SEO, resumos, ideias,
segunda opinião) e revisa o que volta. Os ajudantes não têm ferramentas, não leem arquivos e não mexem no projeto.

Proteções:
- Tudo que sai passa por `redigir()`: e-mails, telefones, CPF/CNPJ, tokens/chaves, senhas e links com token viram
  [REMOVIDO]. Conteúdo com chave privada é recusado.
- Planos gratuitos costumam usar o que você envia para treinar os modelos: nunca mande dados de clientes.
- Cota diária por ajudante (JARVIS_AJUDANTE_<NOME>_DIA) e troca automática quando um recusa (429/402/cota).

Configuração (arquivo .env.ajudantes, criado pelo ./ajudantes-configurar.sh):
  GEMINI_API_KEY=…  XAI_API_KEY=…  OPENROUTER_API_KEY=…  GROQ_API_KEY=…
  JARVIS_AJUDANTES=gemini,grok,openrouter,groq   (ordem de preferência)
  JARVIS_AJUDANTE_GEMINI_MODELO=…                 (opcional: senão escolhe sozinho pela lista do provedor)
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

CONFIG_DIR = os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude"))
PASTA = os.path.join(CONFIG_DIR, "ajudantes")
UA = "jarvis-ajudantes/1.0"
TEMPO = int(os.environ.get("JARVIS_AJUDANTE_TIMEOUT", "180"))

# nome: (variável da chave, URL base no formato OpenAI, preferências de modelo em ordem, cota diária padrão, aviso)
PROVEDORES = {
    "gemini": ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai",
               [r"gemini-[\d.]+-flash(?!-lite)(?!.*(image|tts|audio|live|thinking-exp))", r"gemini-[\d.]+-flash-lite", r"gemini.*flash"],
               200, "plano grátis: o Google usa o conteúdo para melhorar os produtos"),
    "grok": ("XAI_API_KEY", "https://api.x.ai/v1",
             [r"grok-[\d.]+-fast(?!.*(image|vision))", r"grok-[\d.]+-mini", r"grok-[\d.]+(?!.*(image|vision))"],
             300, "créditos grátis/compartilhamento de dados conforme a sua conta xAI"),
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1",
                   [r":free$"], 50, "modelos :free têm limite diário baixo e podem registrar o conteúdo"),
    "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1",
             [r"llama-3\.3-70b", r"llama.*70b", r"qwen", r"llama"], 300, "plano grátis com limite por minuto"),
}

PAPEL = (
    "Você é um ajudante do Jarvis, um orquestrador de projetos. Faça exatamente a tarefa pedida, em português do "
    "Brasil (a menos que a tarefa peça outro idioma), sem enrolação e sem repetir o pedido. Você não tem acesso a "
    "arquivos nem à internet: trabalhe só com o que veio na mensagem. Se faltar informação, diga o que falta. "
    "Trechos [REMOVIDO] foram apagados de propósito: não tente adivinhar.")


# ------------------------------------------------------------ proteção de dados
_PADROES = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), None),  # recusa
    (re.compile(r"(?i)\b(senha|password|passwd|pwd|token|api[_-]?key|secret|segredo|bearer)\b\s*[:=]\s*\S+"), r"\1=[REMOVIDO]"),
    (re.compile(r"(?i)([?&](token|key|api_key|apikey|senha|password|secret|sig|signature)=)[^&\s\"']+"), r"\1[REMOVIDO]"),
    (re.compile(r"\b(sk-(ant-|or-|proj-)?[A-Za-z0-9_-]{16,}|xai-[A-Za-z0-9]{16,}|gsk_[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_-]{30,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "[REMOVIDO]"),
    (re.compile(r"\b[a-fA-F0-9]{32,}\b"), "[REMOVIDO]"),
    (re.compile(r"\b[A-Za-z0-9+/_-]{40,}={0,2}"), "[REMOVIDO]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[REMOVIDO-EMAIL]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[REMOVIDO-CPF]"),
    (re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"), "[REMOVIDO-CNPJ]"),
    (re.compile(r"(?<![\w.])(\+?55[\s-]?)?\(?\d{2}\)?[\s-]?9?\d{4}[\s-]?\d{4}(?![\w.])"), "[REMOVIDO-TELEFONE]"),
]


class Recusado(Exception):
    pass


def redigir(texto):
    """Apaga dados sensíveis. Retorna (texto_limpo, quantidade_removida)."""
    n = 0
    for rx, troca in _PADROES:
        if troca is None:
            if rx.search(texto):
                raise Recusado("o conteúdo tem uma chave privada: não envio isso para ajudantes")
            continue
        texto, k = rx.subn(troca, texto)
        n += k
    return texto, n


# ------------------------------------------------------------ uso e cotas
def _arq_uso():
    return os.path.join(PASTA, "uso-" + time.strftime("%Y-%m-%d") + ".json")


def uso():
    try:
        return json.load(open(_arq_uso(), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _registrar(nome, campo, valor=1):
    os.makedirs(PASTA, exist_ok=True)
    u = uso()
    u.setdefault(nome, {"pedidos": 0, "falhas": 0, "removidos": 0})
    u[nome][campo] = u[nome].get(campo, 0) + valor
    tmp = _arq_uso() + ".tmp"
    json.dump(u, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, _arq_uso())
    for velho in os.listdir(PASTA):  # guarda 14 dias
        if velho.startswith("uso-") and velho < "uso-" + time.strftime("%Y-%m-%d", time.localtime(time.time() - 14 * 86400)):
            os.remove(os.path.join(PASTA, velho))


def _pausar(nome, segundos, motivo):
    u = uso()
    u.setdefault(nome, {})["pausado_ate"] = time.time() + segundos
    u[nome]["motivo"] = motivo
    os.makedirs(PASTA, exist_ok=True)
    json.dump(u, open(_arq_uso(), "w", encoding="utf-8"), indent=1)


def cota(nome):
    return int(os.environ.get(f"JARVIS_AJUDANTE_{nome.upper()}_DIA", PROVEDORES[nome][3]))


def disponivel(nome):
    """(ok, motivo)"""
    if nome not in PROVEDORES:
        return False, "desconhecido"
    if not os.environ.get(PROVEDORES[nome][0]):
        return False, "sem chave"
    u = uso().get(nome, {})
    if u.get("pausado_ate", 0) > time.time():
        return False, u.get("motivo", "pausado")
    if u.get("pedidos", 0) >= cota(nome):
        return False, f"cota do dia ({cota(nome)}) usada"
    return True, "ok"


def configurados():
    ordem = [n.strip() for n in os.environ.get("JARVIS_AJUDANTES", "gemini,grok,openrouter,groq").split(",") if n.strip()]
    return [n for n in ordem if n in PROVEDORES and os.environ.get(PROVEDORES[n][0])]


# ------------------------------------------------------------ chamadas
def _http(nome, caminho, corpo=None):
    var, base = PROVEDORES[nome][0], os.environ.get(f"JARVIS_AJUDANTE_{nome.upper()}_URL", PROVEDORES[nome][1])
    req = urllib.request.Request(base.rstrip("/") + caminho, data=json.dumps(corpo).encode() if corpo else None,
                                 headers={"Authorization": "Bearer " + os.environ[var], "Content-Type": "application/json",
                                          "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TEMPO) as r:
        return json.loads(r.read().decode())


def _cache_modelos():
    try:
        return json.load(open(os.path.join(PASTA, "modelos.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def modelo(nome):
    """Modelo do ajudante: o configurado, ou o melhor da lista do provedor (atualizada 1x por dia)."""
    fixo = os.environ.get(f"JARVIS_AJUDANTE_{nome.upper()}_MODELO", "").strip()
    if fixo:
        return fixo
    c = _cache_modelos()
    if c.get(nome) and time.time() - c[nome]["quando"] < 86400:
        return c[nome]["modelo"]
    ids = [m.get("id", "") for m in (_http(nome, "/models") or {}).get("data", [])]
    ids = [i.split("/", 1)[1] if i.startswith("models/") else i for i in ids]
    escolhido = None
    for padrao in PROVEDORES[nome][2]:
        cands = sorted([i for i in ids if re.search(padrao, i)], key=_chave_versao, reverse=True)
        cands = [i for i in cands if not re.search(r"preview|exp|\d{4}-\d{2}|latest", i)] or cands
        if cands:
            escolhido = cands[0]
            break
    if not escolhido:
        raise RuntimeError(f"não achei modelo adequado em {nome} ({len(ids)} disponíveis)")
    c[nome] = {"modelo": escolhido, "quando": time.time()}
    os.makedirs(PASTA, exist_ok=True)
    json.dump(c, open(os.path.join(PASTA, "modelos.json"), "w", encoding="utf-8"), indent=1)
    return escolhido


def _chave_versao(i):
    return [int(x) for x in re.findall(r"\d+", i)[:3]] or [0]


def perguntar(tarefa, contexto="", ia="auto", maximo=4000):
    """Manda uma tarefa de texto a um ajudante. Retorna dict: ok, texto, ia, modelo, removidos, tentativas."""
    limpo, removidos = redigir((tarefa + ("\n\n--- MATERIAL ---\n" + contexto if contexto else ""))[:120000])
    fila = [ia] if ia != "auto" else configurados()
    if not fila:
        return {"ok": False, "texto": "Nenhum ajudante configurado. Rode ./ajudantes-configurar.sh na VPS.", "tentativas": []}
    tentativas = []
    for nome in fila:
        ok, motivo = disponivel(nome)
        if not ok:
            tentativas.append(f"{nome}: {motivo}")
            continue
        try:
            mod = modelo(nome)
            r = _http(nome, "/chat/completions", {"model": mod, "max_tokens": maximo, "temperature": 0.4,
                                                    "messages": [{"role": "system", "content": PAPEL},
                                                                 {"role": "user", "content": limpo}]})
            texto = ((r.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            if isinstance(texto, list):
                texto = "".join(p.get("text", "") for p in texto if isinstance(p, dict))
            if not texto.strip():
                raise RuntimeError("resposta vazia")
            _registrar(nome, "pedidos")
            if removidos:
                _registrar(nome, "removidos", removidos)
            return {"ok": True, "texto": texto.strip(), "ia": nome, "modelo": mod, "removidos": removidos,
                    "tentativas": tentativas}
        except urllib.error.HTTPError as e:
            corpo = e.read().decode(errors="replace")[:200]
            _registrar(nome, "falhas")
            if e.code in (429, 402, 403) or re.search(r"quota|exhaust|credit|billing|rate", corpo, re.I):
                _pausar(nome, 3600 if e.code == 429 else 6 * 3600, f"sem cota/crédito (HTTP {e.code})")
            elif e.code in (400, 404) and "model" in corpo.lower():
                c = _cache_modelos()
                c.pop(nome, None)  # modelo saiu de linha: escolhe outro na próxima
                json.dump(c, open(os.path.join(PASTA, "modelos.json"), "w", encoding="utf-8"))
            tentativas.append(f"{nome}: HTTP {e.code} {corpo[:80]}")
        except Exception as e:  # noqa: BLE001
            _registrar(nome, "falhas")
            tentativas.append(f"{nome}: {type(e).__name__} {str(e)[:80]}")
    return {"ok": False, "texto": "Nenhum ajudante conseguiu responder.", "tentativas": tentativas, "removidos": removidos}


def status():
    linhas = ["🧑‍🔧 Ajudantes (outras IAs como mão de obra do Jarvis)"]
    u = uso()
    for nome, (var, _b, _p, _c, aviso) in PROVEDORES.items():
        if not os.environ.get(var):
            linhas.append(f"• {nome}: não configurado")
            continue
        ok, motivo = disponivel(nome)
        x = u.get(nome, {})
        mod = _cache_modelos().get(nome, {}).get("modelo") or os.environ.get(f"JARVIS_AJUDANTE_{nome.upper()}_MODELO", "automático")
        linhas.append(f"• {nome}: {'✅' if ok else '⏸ ' + motivo} · hoje {x.get('pedidos', 0)}/{cota(nome)}"
                      f" · falhas {x.get('falhas', 0)} · dados removidos {x.get('removidos', 0)} · modelo {mod}\n  ⚠️ {aviso}")
    if not configurados():
        linhas.append("\nPara ligar: ./ajudantes-configurar.sh na VPS (chaves grátis: aistudio.google.com, console.x.ai, openrouter.ai, console.groq.com).")
    return "\n".join(linhas)
