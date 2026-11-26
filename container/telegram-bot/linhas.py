"""Números de WhatsApp do atendimento ("linhas").

Linha 1: o WhatsApp de sempre (serviço whatsapp, n8n → Jarvis), módulos atendimento / vigia_whatsapp / atend_config.
Linha 2: um segundo WAHA (serviço whatsapp2), ligado com ./whatsapp2-configurar.sh (WHATSAPP2=1 no .env.atendimento).
  Usa CÓPIAS dos mesmos módulos, com pasta, base de respostas, configurações, vigia e estado próprios.
  As mensagens chegam direto do WAHA2 ao painel (/api/waha/2?k=…), sem passar pelo n8n.
"""
import importlib.util
import os
import re
import secrets
import sys
import threading

import jarvis_core as core

PASTA = os.path.dirname(os.path.abspath(__file__))
_cache = {}
_trava = threading.Lock()


def ativa(n):
    n = int(n)
    if n == 1:
        return True
    return n == 2 and os.environ.get("WHATSAPP2", "").strip().lower() in ("1", "sim", "true", "on")


def lista():
    return [n for n in (1, 2) if ativa(n)]


def nome(n):
    if int(n) == 1:
        return os.environ.get("WHATSAPP1_NOME", "Número 1")
    return os.environ.get("WHATSAPP2_NOME", "Número 2")


def _copia(nome_mod, arquivo, trocar):
    """Carrega uma cópia independente de um módulo, trocando temporariamente módulos que ele importa."""
    spec = importlib.util.spec_from_file_location(nome_mod, os.path.join(PASTA, arquivo))
    mod = importlib.util.module_from_spec(spec)
    antes = {k: sys.modules.get(k) for k in trocar}
    sys.modules.update(trocar)
    try:
        spec.loader.exec_module(mod)
    finally:
        for k, v in antes.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    sys.modules[nome_mod] = mod
    return mod


def chave_webhook(pasta):
    """Senha do endereço que o WAHA2 chama (fica só no servidor)."""
    arq = os.path.join(pasta, "webhook.key")
    try:
        k = open(arq, encoding="utf-8").read().strip()
        if len(k) >= 24:
            return k
    except OSError:
        pass
    os.makedirs(pasta, exist_ok=True)
    k = secrets.token_urlsafe(32)
    with open(arq, "w", encoding="utf-8") as f:
        f.write(k)
    os.chmod(arq, 0o600)
    return k


def modulos(n=1):
    """(atendimento, vigia, atend_config) do número n. Número desconhecido/desligado → o 1."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 1
    if n != 2 or not ativa(2):
        import atend_config
        import atendimento
        import vigia_whatsapp
        return atendimento, vigia_whatsapp, atend_config
    with _trava:
        if 2 in _cache:
            return _cache[2]
        pasta = os.path.join(core.CONFIG_DIR, "atendimento-2")
        os.makedirs(pasta, exist_ok=True)
        cfg = _copia("atend_config_2", "atend_config.py", {})
        cfg.ARQ = os.path.join(pasta, "config.json")
        cfg.ARQ_VAR = os.path.join(pasta, "variacoes.json")
        at = _copia("atendimento_2", "atendimento.py", {"atend_config": cfg})
        at.C = cfg
        at.LINHA = 2
        at.NOME = nome(2)
        at.CMD_LINHA = "2 "
        at.DIR = pasta
        at.ESTADO = os.path.join(pasta, "estado.json")
        at.FILA = os.path.join(pasta, "fila.json")
        at.FAQ = os.environ.get("ATENDIMENTO2_FAQ",
                                os.path.join(core.WORKSPACE, ".jarvis-atendimento", "atendimento-2.md"))
        at.WAHA_URL = os.environ.get("WAHA2_URL", "http://whatsapp2:3000").rstrip("/")
        at.WAHA_KEY = os.environ.get("WAHA2_API_KEY") or os.environ.get("WAHA_API_KEY", "")
        at.SESSAO = "default"
        base = os.environ.get("JARVIS_GATILHO_URL", "http://jarvisweb:8090/api/gatilho").split("/api/")[0]
        at.N8N_WEBHOOK = f"{base}/api/waha/2?k={chave_webhook(pasta)}"
        vig = _copia("vigia_whatsapp_2", "vigia_whatsapp.py", {"atendimento": at})
        vig.at = at
        vig.ARQ = os.path.join(pasta, "vigia.json")
        vig.USA_N8N = False
        _cache[2] = (at, vig, cfg)
        return _cache[2]


def linha_do_webhook(n, k):
    """Confere a senha do endereço do WAHA2. Devolve o módulo de atendimento ou None."""
    if int(n) != 2 or not ativa(2):
        return None
    at = modulos(2)[0]
    esperado = chave_webhook(at.DIR)
    return at if k and secrets.compare_digest(str(k), esperado) else None


def dados_do_waha(corpo):
    """Converte o evento do WAHA no formato que atender() espera (o mesmo que o fluxo do n8n monta)."""
    p = corpo.get("payload") or {}
    d = p.get("_data") or {}
    chave = d.get("key") or {}
    return {"acao": "atender", "evento": corpo.get("event"), "chat": p.get("from"),
            "nome": d.get("notifyName") or "", "texto": p.get("body") or "", "de_mim": bool(p.get("fromMe")),
            "tem_midia": bool(p.get("hasMedia")), "midia": p.get("media") or {}, "timestamp": p.get("timestamp"), "id": p.get("id"),
            "origem": p.get("source") or "", "telefone": chave.get("senderPn") or chave.get("remoteJidAlt") or ""}


def _separar(cmd, arg):
    """'/assumir 2 5521…' → (2, '5521…'). Sem número de linha: procura em qual linha a conversa está."""
    partes = (arg or "").split(maxsplit=1)
    if partes and partes[0] in ("1", "2") and (cmd != "/assumir" and cmd != "/devolver" or len(partes) > 1):
        return int(partes[0]), (partes[1] if len(partes) > 1 else "")
    if cmd in ("/assumir", "/devolver") and ativa(2):
        num = re.sub(r"\D", "", arg or "")
        if num:
            e = modulos(2)[0]._ler_estado()
            for c in list(e.get("humano", {})) + list(e.get("esperando", {})) + list(e.get("nomes", {})):
                if c.split("@")[0].endswith(num) or e.get("telefones", {}).get(c, "").endswith(num):
                    return 2, arg
    return 1, arg


def comando(cmd, arg, local=False):
    """Comandos do Telegram com número opcional: /atendimento 2 off · /whatsapp 2 testar · /assumir 2 5521…"""
    import atendimento
    if not atendimento.WAHA_KEY and not local:  # serviço do Telegram: quem executa é o painel
        r = atendimento._pelo_painel(cmd, arg)
        if r:
            return r
    n, resto = _separar(cmd, arg)
    if n == 2 and not ativa(2):
        return "O número 2 não está ligado. Na VPS: ./whatsapp2-configurar.sh"
    texto = modulos(n)[0].comando(cmd, resto, local=True)
    if ativa(2) and cmd in ("/atendimento", "/whatsapp") and not resto.strip():
        return f"【{nome(n)}】\n{texto}\n\n(número 2: /{cmd.strip('/')} 2)" if n == 1 else f"【{nome(n)}】\n{texto}"
    return texto
