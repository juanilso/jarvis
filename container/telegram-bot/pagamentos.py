"""Pagamentos FastFlow (mensagem do Telegram) -> confere o login no painel -> confirma ou pede o login no WhatsApp.

Regras fixas (nada aqui é decidido pelo modelo de IA):
- cada pagamento (#id) é processado UMA vez;
- "Nome informado" só é tratado como login se o painel confirmar que o login existe;
- se o painel já mostra o acesso renovado, só confirma ao cliente; se não, renova pela API (quando disponível)
  ou avisa você para renovar manualmente;
- sem login, pergunta no WhatsApp e espera a resposta (o atendimento confere e conclui).
"""
import json
import os
import re
import threading
import time

import jarvis_core as core

ARQ = os.path.join(core.CONFIG_DIR, "atendimento", "pagamentos.json")
_lock = threading.Lock()
LOGIN_RE = re.compile(r"^[A-Za-z0-9._@-]{3,40}$")


def planos():
    """Valor pago -> meses. Ex.: PAINEL_PLANOS=25=1,30=1,70=3,130=6"""
    t = {}
    import painel_api
    for par in str(painel_api.config()["planos"]).split(","):
        if "=" in par:
            v, m = par.split("=", 1)
            try:
                t[round(float(v.replace(",", ".")), 2)] = int(m)
            except ValueError:
                pass
    return t


def _valor(txt):
    m = re.search(r"R\$\s*([\d.]+,\d{2}|\d+(?:[.,]\d{2})?)", txt or "")
    if not m:
        return None
    v = m.group(1)
    v = v.replace(".", "").replace(",", ".") if "," in v else v
    try:
        return round(float(v), 2)
    except ValueError:
        return None


def ler_mensagem(texto):
    """Extrai os dados de uma mensagem 'PAGAMENTO FASTFLOW RECEBIDO'. Devolve None se não for uma."""
    if not texto or "FASTFLOW" not in texto.upper() or "RECEBIDO" not in texto.upper():
        return None
    linha = lambda rotulo: (re.search(rf"{rotulo}\s*:?\s*(.+)", texto, re.I) or [None, None])[1]  # noqa: E731
    pid = re.search(r"FastFlow\s*#\s*(\d+)", texto, re.I)
    tel = re.sub(r"\D", "", linha(r"Telefone") or "")
    if not pid or len(tel) < 10:
        return None
    nome_inf = (linha(r"Nome informado") or "").strip().strip("*_ ")
    pagador = re.sub(r"\s*\(an[oô]nimo\)\s*$", "", (linha(r"Pagador") or "").strip().strip("*_ "), flags=re.I)
    return {"id": pid.group(1), "telefone": tel, "pagador": pagador, "nome_informado": nome_inf,
            "valor": _valor(linha(r"Valor") or ""), "data": (linha(r"Data") or "").strip()}


def _ler():
    try:
        return json.load(open(ARQ, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"processados": {}, "pendentes": {}}


def _salvar(d):
    os.makedirs(os.path.dirname(ARQ), exist_ok=True)
    d["processados"] = dict(list(d.get("processados", {}).items())[-2000:])
    tmp = ARQ + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, ARQ)


def pendente(chat):
    p = _ler().get("pendentes", {}).get(chat)
    return p if p and time.time() - p.get("ts", 0) < 3 * 86400 else None


def _primeiro_nome(nome):
    n = (nome or "").strip().split(" ")[0].capitalize()
    return n if n and not any(c.isdigit() for c in n) else ""


def liberar(login, pag, ja_conferido=None):
    """Confere/renova um login para um pagamento. Devolve (mensagem_cliente, resumo_para_voce, ok)."""
    import painel_api
    meses = planos().get(pag.get("valor"))
    valor = f"R$ {pag.get('valor'):.2f}".replace(".", ",") if pag.get("valor") else "o valor"
    info = ja_conferido or painel_api.consultar(login)
    if meses and info.get("dias") is not None and info["dias"] >= meses * 30 - 5:
        return (f"✅ Pagamento de {valor} recebido! Seu acesso *{login}* já está ativo até *{info['vencimento']}*. "
                "Obrigado! 🙌", f"já estava renovado até {info['vencimento']}", True)
    if not meses:
        return ("✅ Pagamento recebido! Já estou conferindo e libero seu acesso em instantes. 🙏",
                f"⚠️ valor {valor} não está na tabela PAINEL_PLANOS: renove manualmente", False)
    try:
        novo = painel_api.renovar(login, meses, referencia=f"fastflow-{pag['id']}")
        return (f"✅ Pagamento de {valor} recebido e acesso *{login}* renovado até *{novo['vencimento']}*! "
                "Obrigado! 🙌", f"renovado pela API até {novo['vencimento']}", True)
    except painel_api.ErroPainel as e:
        return ("✅ Pagamento recebido! Estou liberando seu acesso e confirmo por aqui em instantes. 🙏",
                f"⚠️ renove manualmente: {e} (vence {info.get('vencimento')})", False)


def processar(texto, fonte="telegram"):
    """Processa a mensagem de pagamento. Devolve um dict com o que foi feito."""
    import atendimento
    import painel_api
    import rotinas
    pag = ler_mensagem(texto)
    if not pag:
        return {"ok": False, "erro": "não é uma mensagem de pagamento FastFlow reconhecida"}
    with _lock:
        d = _ler()
        if pag["id"] in d["processados"]:
            return {"ok": True, "repetido": True, "id": pag["id"]}
        d["processados"][pag["id"]] = time.time()
        _salvar(d)
    chat = atendimento.chat_do_telefone(pag["telefone"])
    nome = _primeiro_nome(pag["pagador"])
    login, info = None, None
    cand = pag["nome_informado"]
    if cand and LOGIN_RE.match(cand) and painel_api.configurado():
        try:
            info = painel_api.consultar(cand)
            login = cand
        except painel_api.ErroPainel:
            login = None  # "Nome informado" era um nome, não um login
    if login:
        msg, resumo, ok = liberar(login, pag, info)
        atendimento.lembrar_login(chat, login, pag["telefone"])
    else:
        with _lock:
            d = _ler()
            d["pendentes"][chat] = dict(pag, ts=time.time(), tentativas=0)
            _salvar(d)
        valor = f"R$ {pag['valor']:.2f}".replace(".", ",") if pag.get("valor") else "seu pagamento"
        msg = (f"Olá{(' ' + nome) if nome else ''}! ✅ Recebemos seu pagamento de {valor}. "
               "Para eu liberar seu acesso, me envia o seu *login (usuário)* do aplicativo, por favor.")
        resumo, ok = "pedi o login no WhatsApp", True
    try:
        atendimento.enviar_sistema(chat, msg)
        enviado = "WhatsApp enviado"
    except Exception as e:  # noqa: BLE001
        enviado, ok = f"⚠️ WhatsApp não enviado ({type(e).__name__})", False
    rotinas.avisar_telegram(f"💰 FastFlow #{pag['id']} · {pag['pagador']} · +{pag['telefone']} · "
                            f"R$ {pag.get('valor') or '?'}\nLogin: {login or '(não informado)'}\n{resumo} · {enviado}")
    rotinas.registrar({"id": f"pag-{pag['id']}", "rotina": f"Pagamento FastFlow #{pag['id']}", "acao": "pagamento",
                       "projeto": "", "ok": ok, "resultado": f"{resumo} · {enviado}"})
    return {"ok": ok, "id": pag["id"], "login": login, "resumo": resumo, "whatsapp": enviado}


def concluir_pendente(chat, texto):
    """Cliente respondeu enquanto esperamos o login. Devolve a resposta ao cliente, ou None se não havia pendência."""
    import painel_api
    import rotinas
    p = pendente(chat)
    if not p:
        return None
    candidatos = [t for t in re.findall(r"[A-Za-z0-9._@-]{3,40}", texto or "")
                  if any(c.isdigit() for c in t) or len((texto or "").split()) == 1]
    for cand in candidatos[:3]:
        try:
            info = painel_api.consultar(cand)
        except painel_api.ErroPainel:
            continue
        msg, resumo, ok = liberar(cand, p, info)
        with _lock:
            d = _ler()
            d["pendentes"].pop(chat, None)
            _salvar(d)
        import atendimento
        atendimento.lembrar_login(chat, cand, p.get("telefone"))  # RLock: seguro mesmo chamado de dentro do atendimento
        rotinas.avisar_telegram(f"💰 FastFlow #{p['id']} · login informado no WhatsApp: {cand}\n{resumo}")
        return msg
    with _lock:
        d = _ler()
        if chat in d["pendentes"]:
            d["pendentes"][chat]["tentativas"] = d["pendentes"][chat].get("tentativas", 0) + 1
            tent = d["pendentes"][chat]["tentativas"]
            _salvar(d)
        else:
            tent = 0
    if tent >= 3:
        with _lock:
            d = _ler()
            d["pendentes"].pop(chat, None)  # para de insistir; a conversa segue normal e você foi avisado
            _salvar(d)
        rotinas.avisar_telegram(f"💰 FastFlow #{p['id']}: o cliente (+{p.get('telefone')}) não informou um login válido "
                                f"em 3 tentativas. Última mensagem: {texto[:200]}")
        return "Não consegui achar esse login. 😕 Já avisei o atendente, ele te ajuda em instantes!"
    return ("Não encontrei esse login. 🤔 Confere e me manda só o *usuário* do aplicativo "
            "(do jeito que aparece no app), por favor.")
