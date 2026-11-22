"""Mensagens automáticas, liga/desliga de recursos e proteção do número (editáveis no 📱)."""
import json
import os
import random
import re
import threading

import jarvis_core as core

ARQ = os.path.join(core.CONFIG_DIR, "atendimento", "config.json")
_lock = threading.Lock()

# Variáveis: {nome} {login} {valor} {vencimento} {falta}. Várias versões separadas por || (o robô sorteia uma).
MENSAGENS = {
    "pag_confirmado": ("✅ Pagamento de {valor} recebido! Seu acesso *{login}* já está ativo até *{vencimento}*. Obrigado! 🙌"
                       " || Recebemos seu pagamento de {valor}, {nome}! ✅ O acesso *{login}* está ativo até *{vencimento}*. 🙌"),
    "pag_renovado": "✅ Pagamento de {valor} recebido e acesso *{login}* renovado até *{vencimento}*! Obrigado! 🙌",
    "pag_liberando": "✅ Pagamento recebido! Estou liberando seu acesso e confirmo por aqui em instantes. 🙏",
    "pag_pedir_login": ("Olá {nome}! ✅ Recebemos seu pagamento de {valor}. Para eu liberar seu acesso, me envia o seu "
                        "*login (usuário)* do aplicativo, por favor."
                        " || Oi {nome}, tudo bem? Seu pagamento de {valor} chegou! ✅ Me passa o seu *usuário* do app "
                        "para eu liberar?"),
    "login_nao_encontrado": "Não encontrei esse login. 🤔 Confere e me manda só o *usuário* do aplicativo, por favor.",
    "consulta_ativo": "Seu acesso *{login}* está ativo até *{vencimento}* ({falta}). ✅",
    "consulta_vencido": ("Seu acesso *{login}* venceu em *{vencimento}*. 😕 Para renovar, é só fazer o pagamento "
                         "que a liberação é automática."),
    "teste_ja_fez": "Você já fez um teste nos últimos 30 dias. 🙂 Se quiser, te passo como assinar!",
}
NOMES_MENSAGENS = {
    "pag_confirmado": "Pagamento recebido (acesso já estava renovado)",
    "pag_renovado": "Pagamento recebido e renovado pelo Jarvis",
    "pag_liberando": "Pagamento recebido, renovação manual (você renova)",
    "pag_pedir_login": "Pagamento recebido sem login: pedir o login",
    "login_nao_encontrado": "Login informado não existe",
    "consulta_ativo": "Consulta: acesso ativo",
    "consulta_vencido": "Consulta: acesso vencido",
    "teste_ja_fez": "Teste: cliente já fez um",
}
RECURSOS = {"pagamentos": True, "teste": True, "consulta": True, "jogos": True,
            "calar_quando_respondo": True}  # False: o robô segue respondendo mesmo quando você responde (cale com #eu)
PROTECAO = {
    "digitando": True,           # marca como visto e mostra "digitando…" antes de responder
    "atraso_min": 2, "atraso_max": 6,   # segundos de pausa antes de responder (+ tempo de "digitar")
    "max_por_minuto": 12,        # respostas do robô por minuto (todas as conversas)
    "intervalo_proativas": 45,   # segundos entre mensagens que o robô inicia (pagamentos)
    "max_proativas_hora": 30,
    "silencio_inicio": "22:00", "silencio_fim": "08:00",  # mensagens que o robô inicia ficam na fila nesse horário
}


def carregar():
    try:
        salvo = json.load(open(ARQ, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        salvo = {}
    return {"mensagens": {**MENSAGENS, **{k: v for k, v in (salvo.get("mensagens") or {}).items() if k in MENSAGENS and v}},
            "recursos": {**RECURSOS, **{k: bool(v) for k, v in (salvo.get("recursos") or {}).items() if k in RECURSOS}},
            "protecao": {**PROTECAO, **{k: v for k, v in (salvo.get("protecao") or {}).items() if k in PROTECAO}}}


def salvar(novo):
    atual = carregar()
    for k, v in (novo.get("mensagens") or {}).items():
        if k in MENSAGENS:
            atual["mensagens"][k] = str(v)[:1500].strip() or MENSAGENS[k]
    for k, v in (novo.get("recursos") or {}).items():
        if k in RECURSOS:
            atual["recursos"][k] = bool(v)
    for k, v in (novo.get("protecao") or {}).items():
        if k not in PROTECAO:
            continue
        if isinstance(PROTECAO[k], bool):
            atual["protecao"][k] = bool(v)
        elif isinstance(PROTECAO[k], int):
            try:
                atual["protecao"][k] = max(0, min(int(float(v)), 3600))
            except (TypeError, ValueError):
                pass
        elif re.fullmatch(r"\d{1,2}:\d{2}", str(v)) or str(v) == "":
            atual["protecao"][k] = str(v)
    os.makedirs(os.path.dirname(ARQ), exist_ok=True)
    with _lock:
        tmp = ARQ + ".tmp"
        json.dump(atual, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, ARQ)
    return atual


def recurso(nome):
    return carregar()["recursos"].get(nome, True)


def protecao():
    return carregar()["protecao"]


class _Seguro(dict):
    def __missing__(self, k):
        return ""


def msg(chave, **v):
    """Escolhe uma das versões (separadas por ||) e preenche as variáveis. Variável sem valor fica vazia."""
    modelos = [m.strip() for m in carregar()["mensagens"].get(chave, MENSAGENS.get(chave, "")).split("||") if m.strip()]
    texto = random.choice(modelos) if modelos else ""
    texto = texto.format_map(_Seguro({k: ("" if x is None else x) for k, x in v.items()})) if "{" in texto else texto
    texto = re.sub(r"\s+([,!?.])", r"\1", texto)       # "Olá !" -> "Olá!" quando {nome} está vazio
    return re.sub(r"[ \t]{2,}", " ", texto).strip()
