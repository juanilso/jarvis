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

URL = os.environ.get("PAINEL_API_URL", "https://pg.tvdc.site/api.php")
TOKEN = os.environ.get("PAINEL_API_TOKEN", "")
ACAO_RENOVAR = os.environ.get("PAINEL_ACAO_RENOVAR", "").strip()
TESTE_HORAS = os.environ.get("PAINEL_TESTE_HORAS", "4")
UA = os.environ.get("JARVIS_USER_AGENT", "Jarvis-Atendimento/1.13 (+https://github.com/juanilso/jarvis)")


class ErroPainel(Exception):
    pass


def configurado():
    return bool(TOKEN and URL)


def _limpar(texto):
    """Nunca deixa o token aparecer em mensagens de erro."""
    return str(texto).replace(TOKEN, "XXXX") if TOKEN else str(texto)


def _chamar(acao, **params):
    if not configurado():
        raise ErroPainel("API do painel não configurada (./painel-configurar.sh)")
    if not acao:
        raise ErroPainel("ação vazia")  # a API cria teste quando a action falta: nunca chamar sem action
    q = {"action": acao, "token": TOKEN}
    q.update({k: v for k, v in params.items() if v not in (None, "")})
    req = urllib.request.Request(URL + "?" + urllib.parse.urlencode(q),
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
    j = _chamar("create_test", phone=tel, duration=TESTE_HORAS)
    msg = _achar(j, "message") if isinstance(j.get("client"), dict) and j["client"].get("message") else None
    if not msg:
        u, p = _achar(j, "username"), _achar(j, "password")
        venc = _achar(j, "exp_date_formatted") or ""
        msg = f"✅ Seu teste foi criado!\nUsuário: {u}\nSenha: {p}\nVálido até: {venc}"
    return {"login": _achar(j, "username"), "mensagem": str(msg)[:3000],
            "vencimento": _achar(j, "exp_date_formatted") or ""}


def renovar(login, meses=1, referencia=""):
    """Renova pela API, se a action de renovação estiver configurada. Senão, avisa que precisa ser manual."""
    if not ACAO_RENOVAR:
        raise ErroPainel("renovação pela API ainda não disponível (PAINEL_ACAO_RENOVAR vazio)")
    j = _chamar(ACAO_RENOVAR, username=login, months=str(int(meses)), reference=referencia)
    try:
        return consultar(login)
    except ErroPainel:
        return {"login": login, "vencimento": _achar(j, "exp_date_formatted") or "?", "status": "active"}
