"""Cliente da API do painel de revenda (XUI) usado pelo atendimento e pelos pagamentos.

Configuração (arquivo .env.atendimento, só no serviço do painel; criado pelo ./painel-configurar.sh):
  PAINEL_API_URL=https://pg.tvdc.site/api.php
  PAINEL_API_TOKEN=...                 (nunca vai para o GitHub, logs ou Telegram)
  PAINEL_ACAO_RENOVAR=                 nome da action de renovação, quando existir no api.php (ex.: renew_client)
  PAINEL_TESTE_HORAS=4                 duração do teste grátis
Ações conhecidas: check_validity (username) e create_test (phone, duration…).
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

# Configuração: valores do .env.atendimento, sobrepostos pelo que você salvar no painel (📱 → Painel / API).
# O arquivo fica num volume montado SÓ no serviço do painel (os agentes não enxergam o token).
CONFIG = os.environ.get("PAINEL_CONFIG", "/segredos/painel.json")
UA = os.environ.get("JARVIS_USER_AGENT", "Jarvis-Atendimento/1.14 (+https://github.com/juanilso/jarvis)")
PADRAO = {"url": os.environ.get("PAINEL_API_URL", "https://pg.tvdc.site/api.php"),
          "token": os.environ.get("PAINEL_API_TOKEN", ""),
          "acao_renovar": os.environ.get("PAINEL_ACAO_RENOVAR", "").strip(),
          "teste_horas": os.environ.get("PAINEL_TESTE_HORAS", "4"),
          "testes_dia": os.environ.get("PAINEL_TESTES_DIA", "20"),
          "planos": os.environ.get("PAINEL_PLANOS", "25=1,30=1"),
          "minutos_humano": os.environ.get("ATENDIMENTO_MINUTOS_HUMANO", "30")}


def config():
    c = dict(PADRAO)
    try:
        salvo = json.load(open(CONFIG, encoding="utf-8"))
        c.update({k: v for k, v in salvo.items() if k in PADRAO and v not in (None,)})
    except (OSError, json.JSONDecodeError):
        pass
    return c


def salvar_config(novos):
    """Salva só os campos conhecidos. Token vazio = mantém o atual."""
    c = config()
    for k in PADRAO:
        if k in novos and novos[k] is not None:
            v = str(novos[k]).strip()
            if k == "token" and not v:
                continue
            c[k] = v
    if not re.match(r"^https?://", c["url"]):
        raise ValueError("o endereço da API precisa começar com https://")
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    tmp = CONFIG + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False)
    os.replace(tmp, CONFIG)
    return publico()


def publico():
    """Configuração para mostrar no painel (sem o token)."""
    c = config()
    t = c.pop("token", "")
    c["token_definido"] = bool(t)
    c["token_final"] = t[-4:] if len(t) >= 8 else ""
    return c


class ErroPainel(Exception):
    pass


def configurado():
    c = config()
    return bool(c["token"] and c["url"])


def _limpar(texto):
    """Nunca deixa o token aparecer em mensagens de erro."""
    t = config()["token"]
    return str(texto).replace(t, "XXXX") if t else str(texto)


def _chamar(acao, **params):
    if not configurado():
        raise ErroPainel("API do painel não configurada (./painel-configurar.sh)")
    if not acao:
        raise ErroPainel("ação vazia")  # a API cria teste quando a action falta: nunca chamar sem action
    c = config()
    q = {"action": acao, "token": c["token"]}
    q.update({k: v for k, v in params.items() if v not in (None, "")})
    req = urllib.request.Request(c["url"] + ("&" if "?" in c["url"] else "?") + urllib.parse.urlencode(q),
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            bruto = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise ErroPainel(_limpar(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")) from None
    except Exception as e:  # noqa: BLE001
        raise ErroPainel(_limpar(f"{type(e).__name__}: {e}")) from None
    try:
        j = json.loads(bruto[bruto.find("{"):]) if "{" in bruto else {}
    except json.JSONDecodeError:
        raise ErroPainel(_limpar("resposta inválida: " + bruto[:200])) from None
    if not j.get("success", False):
        raise ErroPainel(_limpar(j.get("message") or j.get("error") or "a API recusou o pedido"))
    return j


def _achar(d, *nomes):
    """Procura um campo no JSON (no topo ou dentro de client/data/line)."""
    for bloco in (d, d.get("client") or {}, d.get("data") or {}, d.get("line") or {}):
        if isinstance(bloco, dict):
            for n in nomes:
                if bloco.get(n) not in (None, ""):
                    return bloco[n]
    return None


def consultar(login):
    """Vencimento de um login. Devolve só dados seguros para mostrar ao cliente (sem senha nem links)."""
    login = str(login or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._@-]{3,40}", login):
        raise ErroPainel("login inválido")
    j = _chamar("check_validity", username=login)
    exp = _achar(j, "exp_date", "expiration", "vencimento")
    try:
        exp = int(float(exp)) if exp not in (None, "") else None
    except (TypeError, ValueError):
        exp = None
    status = str(_achar(j, "status") or "").lower()
    if not status and exp:
        status = "active" if exp > time.time() else "expired"
    dias = round((exp - time.time()) / 86400, 1) if exp else None
    return {"login": login, "status": status or "?", "exp": exp,
            "vencimento": _achar(j, "exp_date_formatted", "vencimento_formatado")
            or (time.strftime("%d/%m/%Y %H:%M", time.localtime(exp)) if exp else "?"),
            "dias": dias}


def criar_teste(telefone):
    """Teste grátis para um telefone. Devolve a mensagem de boas-vindas do painel (com acesso) para o cliente."""
    tel = re.sub(r"\D", "", str(telefone or ""))
    if len(tel) < 10:
        raise ErroPainel("telefone inválido")
    j = _chamar("create_test", phone=tel, duration=config()["teste_horas"])
    msg = _achar(j, "message") if isinstance(j.get("client"), dict) and j["client"].get("message") else None
    if not msg:
        u, p = _achar(j, "username"), _achar(j, "password")
        venc = _achar(j, "exp_date_formatted") or ""
        msg = f"✅ Seu teste foi criado!\nUsuário: {u}\nSenha: {p}\nVálido até: {venc}"
    return {"login": _achar(j, "username"), "mensagem": str(msg)[:3000],
            "vencimento": _achar(j, "exp_date_formatted") or ""}


def renovar(login, meses=1, referencia=""):
    """Renova pela API, se a action de renovação estiver configurada. Senão, avisa que precisa ser manual."""
    acao = config()["acao_renovar"].strip()
    if not acao:
        raise ErroPainel("renovação pela API ainda não configurada (📱 → Painel / API → ação de renovar)")
    j = _chamar(acao, username=login, months=str(int(meses)), reference=referencia)
    try:
        return consultar(login)
    except ErroPainel:
        return {"login": login, "vencimento": _achar(j, "exp_date_formatted") or "?", "status": "active"}


def testar():
    """Confere se a API responde e se o token é aceito, sem criar nada (consulta um login que não existe)."""
    if not configurado():
        return {"ok": False, "msg": "falta o endereço ou o token"}
    try:
        _chamar("check_validity", username="jarvis-teste-conexao-0000")
        return {"ok": True, "msg": "✅ API respondeu e aceitou o token"}
    except ErroPainel as e:
        m = str(e)
        rede = any(x in m for x in ("URLError", "timeout", "Timeout", "Connection", "resposta inválida")) or m.startswith("HTTP ")
        if rede:
            return {"ok": False, "msg": f"❌ não consegui falar com a API: {m}"}
        if "token" in m.lower():
            return {"ok": False, "msg": f"❌ a API recusou o token: {m}"}
        return {"ok": True, "msg": f"✅ API respondeu e aceitou o token (para um login inexistente ela disse: {m})"}
