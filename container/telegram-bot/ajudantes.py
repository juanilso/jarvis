"""Ajudantes: outras IAs (Gemini, Grok, OpenRouter, Groq…) como mão de obra barata do Jarvis.

O Jarvis (Claude) continua o chefe: manda tarefas de TEXTO (rascunhos, traduções, textos de SEO, resumos, ideias,
segunda opinião) e revisa o que volta. Os ajudantes não têm ferramentas, não leem arquivos e não mexem no projeto.

Proteções:
- Tudo que sai passa por `redigir()`: e-mails, telefones, CPF/CNPJ, tokens/chaves, senhas e links com token viram
  [REMOVIDO]. Conteúdo com chave privada é recusado.
- Planos gratuitos costumam usar o que você envia para treinar os modelos: nunca mande dados de clientes.
- Cota diária por ajudante (JARVIS_AJUDANTE_<NOME>_DIA) e troca automática quando um recusa (429/402/cota).

Configuração (arquivo .env.ajudantes, criado pelo ./ajudantes-configurar.sh):
  GEMINI_API_KEY=…  GROQ_API_KEY=…  MISTRAL_API_KEY=…  OPENROUTER_API_KEY=…  (XAI_API_KEY=… opcional)
  JARVIS_AJUDANTES=gemini,groq,mistral,openrouter   (ordem de preferência)
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
    "mistral": ("MISTRAL_API_KEY", "https://api.mistral.ai/v1",
                [r"^mistral-small(?!.*(ocr|embed|moderation))", r"^mistral-medium(?!.*(ocr|embed|moderation))",
                 r"^ministral-\d+b"], 300, "plano grátis Experiment: a Mistral pode usar o conteúdo para treinar"),
    "nvidia": ("NVIDIA_API_KEY", "https://integrate.api.nvidia.com/v1",
               [r"^meta/llama-[\d.]+-70b-instruct(?!.*(vision|guard))", r"^openai/gpt-oss-120b",
                r"^qwen/qwen[\d.]+-\d+b(?!.*(vision|vl|embed|coder))", r"^mistralai/mistral-(small|medium)(?!.*vision)",
                r"^(?!.*(vision|embed|guard|reward|safety|retriev|-vl)).*instruct"],
               500, "plano grátis de desenvolvedor (40 pedidos/minuto), para protótipo"),
    "cloudflare": ("CLOUDFLARE_API_TOKEN", "https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1",
                   [], 60, "cota grátis diária pequena (10.000 neurons); a Cloudflare não treina com o conteúdo"),
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1",
                   [r":free$"], 50, "modelos :free têm limite diário baixo e podem registrar o conteúdo"),
    "deepseek": ("DEEPSEEK_API_KEY", "https://api.deepseek.com",
                 [r"^deepseek-flash$", r"^deepseek-v4-pro", r"^deepseek"],
                 500, "DeepSeek: pago por uso e bem barato (o Flash custa centavos por milhão de tokens)"),
    "ollama": ("OLLAMA_API_KEY", "https://ollama.com/v1",
               [r"^gpt-oss:120b", r"^(qwen3|deepseek|kimi|glm)", r"^gpt-oss", r"^gemma"],
               300, "Ollama Cloud: limites conforme o plano da sua conta em ollama.com"),
    "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1",
             [r"llama-3\.3-70b", r"llama.*70b", r"qwen", r"llama"], 300, "plano grátis com limite por minuto"),
}

# se a lista de modelos do provedor falhar ou vier vazia
MODELOS_RESERVA = {"deepseek": ["deepseek-flash", "deepseek-v4-pro"], "ollama": ["gpt-oss:120b", "qwen3-coder:480b", "deepseek-v3.1:671b", "gpt-oss:20b"]}

# provedores sem lista de modelos no formato OpenAI: candidatos fixos (o primeiro que funcionar fica guardado)
MODELOS_FIXOS = {
    "cloudflare": ["@cf/openai/gpt-oss-120b", "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/openai/gpt-oss-20b"],
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
    u[nome]["chave"] = os.environ.get(PROVEDORES[nome][0], "")[-6:]  # chave nova = pausa não vale mais
    os.makedirs(PASTA, exist_ok=True)
    json.dump(u, open(_arq_uso(), "w", encoding="utf-8"), indent=1)


def liberar(nome=None):
    """Tira as pausas (todas ou de um ajudante). O contador do dia continua."""
    u = uso()
    for n in ([nome] if nome else list(u)):
        if n in u:
            for k in ("pausado_ate", "motivo", "chave"):
                u[n].pop(k, None)
    os.makedirs(PASTA, exist_ok=True)
    json.dump(u, open(_arq_uso(), "w", encoding="utf-8"), indent=1)


def cota(nome):
    return int(os.environ.get(f"JARVIS_AJUDANTE_{nome.upper()}_DIA", PROVEDORES[nome][3]))


def _chaves():
    try:  # chaves trocadas pelo painel (🔑 Chaves) valem por cima do .env, na hora
        import chaves
        chaves.aplicar()
    except Exception:  # noqa: BLE001
        pass


def disponivel(nome):
    """(ok, motivo)"""
    _chaves()
    if nome not in PROVEDORES:
        return False, "desconhecido"
    if not os.environ.get(PROVEDORES[nome][0]):
        return False, "sem chave"
    for falta in re.findall(r"\{(\w+)\}", PROVEDORES[nome][1]):
        if not os.environ.get(falta):
            return False, f"falta {falta}"
    u = uso().get(nome, {})
    if u.get("pausado_ate", 0) > time.time() and u.get("chave", "") == os.environ.get(PROVEDORES[nome][0], "")[-6:]:
        return False, u.get("motivo", "pausado")
    if u.get("pedidos", 0) >= cota(nome):
        return False, f"cota do dia ({cota(nome)}) usada"
    return True, "ok"


def configurados():
    _chaves()
    ordem = [n.strip() for n in os.environ.get("JARVIS_AJUDANTES", "gemini,groq,nvidia,cloudflare,deepseek,ollama,openrouter,mistral,grok").split(",") if n.strip()]
    return [n for n in ordem if n in PROVEDORES and os.environ.get(PROVEDORES[n][0])]


# ------------------------------------------------------------ chamadas
def _http(nome, caminho, corpo=None):
    var, base = PROVEDORES[nome][0], os.environ.get(f"JARVIS_AJUDANTE_{nome.upper()}_URL", PROVEDORES[nome][1])
    base = re.sub(r"\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), base)  # ex.: id da conta Cloudflare
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


def candidatos(nome, quantos=4):
    """Modelos do ajudante em ordem de preferência: o fixado, ou os melhores da lista do provedor (1x por dia)."""
    fixo = os.environ.get(f"JARVIS_AJUDANTE_{nome.upper()}_MODELO", "").strip()
    if fixo:
        return [fixo]
    c = _cache_modelos()
    if c.get(nome) and time.time() - c[nome]["quando"] < 86400 and c[nome].get("lista") and c[nome].get("v") == 2:
        return c[nome]["lista"]
    if nome in MODELOS_FIXOS:
        lista = list(MODELOS_FIXOS[nome])
        c[nome] = {"modelo": lista[0], "lista": lista, "quando": time.time(), "v": 2}
        _gravar_cache(c)
        return lista
    try:
        ids = [m.get("id", "") for m in (_http(nome, "/models") or {}).get("data", [])]
    except Exception:  # noqa: BLE001
        if nome not in MODELOS_RESERVA:
            raise
        ids = []
    if not ids and nome in MODELOS_RESERVA:
        ids = list(MODELOS_RESERVA[nome])
    ids = [i.split("/", 1)[1] if i.startswith("models/") else i for i in ids]
    lista = []
    for padrao in PROVEDORES[nome][2]:  # até 2 de cada tipo (ex.: 2 Flash + 2 Flash-Lite), para variar se um lotar
        cands = sorted([i for i in ids if re.search(padrao, i)], key=_chave_versao, reverse=True)
        estaveis = [i for i in cands if not re.search(r"preview|exp|\d{4}-\d{2}|latest", i)]
        novos = [i for i in estaveis + [i for i in cands if i not in estaveis] if i not in lista]
        lista += novos[:2]
    lista = lista[:quantos]
    if not lista:
        raise RuntimeError(f"não achei modelo adequado em {nome} ({len(ids)} disponíveis)")
    c[nome] = {"modelo": lista[0], "lista": lista, "quando": time.time(), "v": 2}
    _gravar_cache(c)
    return lista


_trava_cache = __import__("threading").Lock()


def _gravar_cache(c):
    """Grava inteiro e troca de uma vez (o conselho consulta várias IAs ao mesmo tempo)."""
    with _trava_cache:
        os.makedirs(PASTA, exist_ok=True)
        tmp = os.path.join(PASTA, f"modelos.json.{os.getpid()}.tmp")
        json.dump(c, open(tmp, "w", encoding="utf-8"), indent=1)
        os.replace(tmp, os.path.join(PASTA, "modelos.json"))


def _preferir(nome, mod):
    """Lembra o modelo que funcionou para tentar ele primeiro da próxima vez."""
    c = _cache_modelos()
    if c.get(nome) and c[nome].get("lista") and mod in c[nome]["lista"]:
        c[nome]["lista"] = [mod] + [m for m in c[nome]["lista"] if m != mod]
        c[nome]["modelo"] = mod
        _gravar_cache(c)


def modelo(nome):
    return candidatos(nome)[0]


def _msg_erro(corpo):
    """Texto legível do erro do provedor."""
    try:
        j = json.loads(corpo)
        if isinstance(j, list):
            j = j[0]
        e = j.get("error", j)
        msg = e.get("message") if isinstance(e, dict) else (e if isinstance(e, str) else j.get("message"))
        return str(msg or corpo)[:160]
    except (ValueError, AttributeError, IndexError, TypeError):
        return corpo[:160]


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
        if not ok and ia != "auto" and motivo not in ("sem chave", "desconhecido"):
            ok = True  # você pediu esta IA pelo nome: tenta mesmo pausada (para ver o erro atual)
        if not ok:
            tentativas.append(f"{nome}: {motivo}")
            continue
        try:
            modelos = candidatos(nome)
        except urllib.error.HTTPError as e:
            _registrar(nome, "falhas")
            msg = _msg_erro(e.read().decode(errors="replace"))
            if _chave_invalida(e.code, msg):
                _pausar(nome, 30 * 86400, "chave inválida: troque no painel (🧠 Cérebro → 🔑 Chaves)")
            elif _sem_credito(e.code, msg):
                _pausar(nome, 6 * 3600, "conta sem crédito/licença")
            tentativas.append(f"{nome}: {_explicar(nome, e.code, msg)}")
            continue
        except Exception as e:  # noqa: BLE001
            _registrar(nome, "falhas")
            tentativas.append(f"{nome}: {type(e).__name__} {str(e)[:100]}")
            continue
        for mod in modelos:
            try:
                corpo = {"model": mod, "max_tokens": maximo, "temperature": 0.4,
                         "messages": [{"role": "system", "content": PAPEL}, {"role": "user", "content": limpo}]}
                if nome == "gemini":  # modelos que "pensam": pensar pouco e dar folga para o texto final
                    corpo["max_tokens"] = max(maximo, 2048)
                    corpo["reasoning_effort"] = "low"
                if nome == "deepseek":  # sem "pensar" por padrão (mais rápido e barato); DEEPSEEK_PENSAR=1 liga
                    if os.environ.get("DEEPSEEK_PENSAR", "").lower() in ("1", "sim", "true"):
                        corpo.update(max_tokens=max(maximo, 4096), thinking={"type": "enabled"}, reasoning_effort="high")
                    else:
                        corpo["thinking"] = {"type": "disabled"}
                try:
                    r = _http(nome, "/chat/completions", corpo)
                except urllib.error.HTTPError as e1:
                    if e1.code != 400 or not ({"reasoning_effort", "thinking"} & set(corpo)):
                        raise
                    corpo.pop("reasoning_effort", None)  # modelo que não aceita o ajuste: tenta sem
                    corpo.pop("thinking", None)
                    r = _http(nome, "/chat/completions", corpo)
                texto = ((r.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                if isinstance(texto, list):
                    texto = "".join(p.get("text", "") for p in texto if isinstance(p, dict))
                texto = re.sub(r"(?s)<think>.*?</think>", "", texto).strip()  # modelos que mostram o raciocínio
                if not texto:
                    raise RuntimeError("resposta vazia (o modelo gastou o limite pensando)")
                _registrar(nome, "pedidos")
                if removidos:
                    _registrar(nome, "removidos", removidos)
                _preferir(nome, mod)
                return {"ok": True, "texto": texto, "ia": nome, "modelo": mod, "removidos": removidos,
                        "tentativas": tentativas}
            except urllib.error.HTTPError as e:
                msg = _msg_erro(e.read().decode(errors="replace"))
                _registrar(nome, "falhas")
                tentativas.append(f"{nome} ({mod}): {_explicar(nome, e.code, msg)}")
                if _chave_invalida(e.code, msg):
                    _pausar(nome, 30 * 86400, "chave inválida: troque no painel (🧠 Cérebro → 🔑 Chaves)")
                    break  # chave errada: outro modelo não resolve
                if _sem_credito(e.code, msg):
                    _pausar(nome, 6 * 3600, "conta sem crédito/licença")
                    break
                # 429/500/503 (modelo lotado), 404/400 de modelo: tenta o próximo modelo do mesmo provedor
                continue
            except Exception as e:  # noqa: BLE001
                _registrar(nome, "falhas")
                tentativas.append(f"{nome} ({mod}): {type(e).__name__} {str(e)[:100]}")
                continue
        else:
            if tentativas and all(("429" in t or "lotado" in t) for t in tentativas if t.startswith(nome)):
                _pausar(nome, 1800, "todos os modelos lotados (tenta de novo em 30 min)")
    return {"ok": False, "texto": "Nenhum ajudante conseguiu responder.", "tentativas": tentativas, "removidos": removidos}


PAPEL_CONSELHO = ("Você faz parte de um conselho de IAs que ajuda o Jarvis (orquestrador de projetos de software) a "
                  "decidir. Responda em português do Brasil: 1) sua recomendação em 1 frase; 2) por quê (até 5 itens); "
                  "3) riscos e o que testar; 4) uma alternativa. Seja específico e honesto sobre incertezas.")


def conselho(pergunta, material="", maximo=1500, limite=6, tempo=120):
    """Pergunta a TODAS as IAs ligadas e disponíveis ao mesmo tempo. Devolve [{ia, modelo, ok, texto}]."""
    import concurrent.futures as cf
    redigir(pergunta + "\n" + material)  # recusa logo se houver chave privada
    nomes = [n for n in configurados() if disponivel(n)[0]][:limite]
    if not nomes:
        return []
    respostas = []
    with cf.ThreadPoolExecutor(max_workers=len(nomes)) as ex:
        futuros = {ex.submit(perguntar, pergunta, (PAPEL_CONSELHO + ("\n\n" + material if material else "")),
                             n, maximo): n for n in nomes}
        try:
            for f in cf.as_completed(futuros, timeout=tempo):
                n = futuros[f]
                try:
                    r = f.result()
                    texto = r.get("texto") if r.get("ok") else "; ".join(r.get("tentativas", [])) or r.get("texto", "")
                    respostas.append({"ia": n, "modelo": r.get("modelo", ""), "ok": r.get("ok", False),
                                      "texto": (texto or "")[:6000]})
                except Exception as e:  # noqa: BLE001
                    respostas.append({"ia": n, "modelo": "", "ok": False, "texto": f"{type(e).__name__}: {str(e)[:150]}"})
        except cf.TimeoutError:
            for f, n in futuros.items():
                if not f.done():
                    respostas.append({"ia": n, "modelo": "", "ok": False, "texto": f"não respondeu em {tempo}s"})
    ordem = {n: i for i, n in enumerate(nomes)}
    return sorted(respostas, key=lambda r: ordem.get(r["ia"], 99))


def _sem_credito(code, msg):
    return code == 402 or bool(re.search(r"credit|licen[cs]e|purchase|billing|insufficient|spending.?limit|quota exceeded|payment", msg, re.I))


def _chave_invalida(code, msg):
    if _sem_credito(code, msg):
        return False
    return code == 401 or (code in (400, 403) and bool(re.search(r"api.?key|unauthori|invalid|incorrect|not found|revoked", msg, re.I)))


def _explicar(nome, code, msg):
    if _sem_credito(code, msg):
        return f"a conta não tem crédito/licença (HTTP {code}): {msg[:140]}"
    if _chave_invalida(code, msg):
        return f"chave inválida (HTTP {code}): {msg[:100]} · troque no painel (🧠 Cérebro → 🔑 Chaves)"
    if code == 403:
        return f"acesso negado (HTTP 403): {msg[:160]}"
    if code == 429:
        return f"lotado/limite por minuto (HTTP 429): {msg[:80]}"
    if code in (500, 502, 503, 504):
        return f"modelo lotado no provedor (HTTP {code}), tentando outro"
    if code == 402:
        return "sem crédito (HTTP 402)"
    return f"HTTP {code}: {msg[:100]}"


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
        linhas.append("\nPara ligar: ./ajudantes-configurar.sh na VPS (chaves grátis: aistudio.google.com, console.groq.com, build.nvidia.com, dash.cloudflare.com, openrouter.ai).")
    return "\n".join(linhas)
