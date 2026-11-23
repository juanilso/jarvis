"""Vigia do atendimento do WhatsApp: testa a corrente inteira de tempos em tempos, conserta o que der e avisa você.

Corrente: WhatsApp → WAHA (sessão conectada, webhook gravado) → n8n (fluxo publicado) → Jarvis (atender) → resposta.

A cada JARVIS_VIGIA_MIN minutos (padrão 5), no serviço do painel (que tem a chave do WAHA):
1. Sessão: WORKING? Se FAILED/STOPPED/travada: reinicia. Se pede QR: avisa e manda o QR no Telegram.
2. Webhook e histórico na sessão: grava se faltar (sem QR).
3. n8n: manda um teste pelo mesmo caminho das mensagens. 404 = fluxo despublicado → publica de novo pela API do n8n
   (se N8N_API_KEY estiver configurada; só o fluxo do webhook "whatsapp-waha") ou avisa você.
4. Mensagens perdidas: compara as últimas conversas do WhatsApp com o que chegou ao Jarvis. Cliente escreveu e não
   chegou → regrava o webhook, reinicia a sessão e te manda a lista de quem ficou sem resposta.
Avisa uma vez por problema e avisa quando voltar ao normal.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

import atendimento as at

INTERVALO = max(2, int(os.environ.get("JARVIS_VIGIA_MIN", "5"))) * 60
N8N_URL = os.environ.get("N8N_URL", "http://n8n:5678").rstrip("/")
ARQ = os.path.join(at.DIR, "vigia.json")
_lock = threading.Lock()
_rodando = {"ativo": False}


def _ler():
    try:
        return json.load(open(ARQ, encoding="utf-8"))
    except (OSError, ValueError):
        return {"ligado": True, "desde": time.time()}


def _salvar(d):
    os.makedirs(at.DIR, exist_ok=True)
    tmp = ARQ + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, ARQ)


def ultimo():
    return _ler().get("ultimo") or {"passos": [], "quando": "", "ok": None}


def ligar(valor):
    d = _ler()
    d["ligado"] = bool(valor)
    _salvar(d)


def _avisar(texto):
    try:
        at._avisar_dono(texto)
    except Exception as e:  # noqa: BLE001
        print("vigia: aviso falhou", e, flush=True)


# ------------------------------------------------------------------ n8n
def _n8n_api(metodo, caminho, corpo=None):
    chave = os.environ.get("N8N_API_KEY", "")
    if not chave:
        raise RuntimeError("sem N8N_API_KEY")
    req = urllib.request.Request(N8N_URL + "/api/v1" + caminho, method=metodo,
                                 data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"X-N8N-API-KEY": chave, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        t = r.read().decode()
        return json.loads(t) if t else {}


def republicar_fluxo():
    """Publica de novo o fluxo do atendimento (o que tem o webhook whatsapp-waha). Devolve (ok, texto)."""
    caminho = at.N8N_WEBHOOK.rstrip("/").rsplit("/", 1)[-1]
    try:
        fluxos = _n8n_api("GET", "/workflows?limit=200").get("data", [])
    except RuntimeError:
        return False, "configure a chave da API do n8n (./n8n-api-configurar.sh) para eu republicar sozinho"
    except Exception as e:  # noqa: BLE001
        return False, f"não falei com a API do n8n ({type(e).__name__})"
    for f in fluxos:
        try:
            nos = _n8n_api("GET", f"/workflows/{f['id']}").get("nodes", [])
        except Exception:  # noqa: BLE001
            continue
        if any(n.get("type", "").endswith(".webhook") and str((n.get("parameters") or {}).get("path", "")).strip("/") == caminho
               for n in nos):
            try:
                _n8n_api("POST", f"/workflows/{f['id']}/activate")
                return True, f"fluxo “{f.get('name')}” publicado de novo"
            except Exception as e:  # noqa: BLE001
                return False, f"achei o fluxo “{f.get('name')}” mas não consegui publicar ({type(e).__name__})"
    return False, f"não achei no n8n um fluxo com o webhook “{caminho}”"


def _testar_n8n():
    """Manda o evento de teste pelo caminho do WhatsApp. Devolve (codigo, texto): 'ok' | 'inativo' | 'nao_repassou' | 'fora'."""
    e = at._ler_estado()
    antes = e.get("diag", 0)
    corpo = {"event": "message.any", "session": at.SESSAO, "payload": {
        "id": f"vigia-{int(time.time())}", "from": "diagnostico@c.us", "fromMe": False, "body": at.DIAG,
        "timestamp": int(time.time()), "_data": {"notifyName": "vigia"}}}
    try:
        req = urllib.request.Request(at.N8N_WEBHOOK, data=json.dumps(corpo).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            return "inativo", "o fluxo do atendimento no n8n está despublicado"
        return "fora", f"n8n respondeu HTTP {erro.code}"
    except Exception as erro:  # noqa: BLE001
        return "fora", f"n8n fora do ar ({type(erro).__name__})"
    fim = time.time() + 15
    while time.time() < fim:
        if at._ler_estado().get("diag", 0) > antes:
            return "ok", "n8n recebeu e repassou ao Jarvis"
        time.sleep(0.5)
    return "nao_repassou", "o n8n recebeu mas não chamou o Jarvis (veja Executions do fluxo)"


# ------------------------------------------------------------------ mensagens que não chegaram
def _mesmo_id(a, b):
    return a == b or (len(a) > 12 and len(b) > 12 and (a.endswith(b) or b.endswith(a) or a.split("_")[-1] == b.split("_")[-1]))


def perdidas(desde, ja_avisadas=()):
    """Conversas em que o cliente escreveu por último (há 3 min a 6 h) e a mensagem não chegou ao Jarvis.
    Devolve (lista, aviso). lista: [{"chat","nome","numero","texto","min"}]; None se o WhatsApp não informa."""
    try:
        conversas = at.waha(f"/api/{at.SESSAO}/chats/overview?limit=40", tempo=30)
    except Exception as e:  # noqa: BLE001
        return None, f"a lista de conversas do WhatsApp não está disponível ({type(e).__name__})"
    if isinstance(conversas, dict):
        conversas = conversas.get("data") or conversas.get("chats") or []
    vistos = [x[0] for x in at._ler_estado().get("ids_clientes", [])]
    agora, lista = time.time(), []
    for c in conversas or []:
        chat = str(c.get("id") or "")
        m = c.get("lastMessage") or {}
        if not chat or not m or m.get("fromMe") or chat.endswith("@g.us") or chat.startswith("status@") \
                or "@newsletter" in chat or "@broadcast" in chat:
            continue
        ts = float(m.get("timestamp") or 0)
        ts = ts / 1000 if ts > 1e12 else ts
        if not (agora - 6 * 3600 < ts < agora - 180) or ts < desde:
            continue
        mid = str(m.get("id") or "")
        if mid and any(_mesmo_id(mid, v) for v in vistos):
            continue
        if (mid or f"{chat}:{int(ts)}") in ja_avisadas:  # já avisada: não reinicia a sessão de novo por ela
            continue
        numero = re.sub(r"\D", "", chat.split("@")[0])
        lista.append({"chave": mid or f"{chat}:{int(ts)}", "chat": chat, "nome": c.get("name") or "", "numero": numero,
                      "texto": str(m.get("body") or "(mídia)")[:80], "min": int((agora - ts) // 60)})
    return lista, ""


# ------------------------------------------------------------------ verificação completa
def checar(consertar=True, avisar=True):
    """Roda a verificação. Retorna {"ok", "passos", "quando", "consertos", "perdidas"}."""
    with _lock:
        d = _ler()
        passos, consertos = [], []

        def item(ok, titulo, detalhe=""):
            passos.append({"ok": ok, "titulo": titulo, "detalhe": detalhe})
            return ok

        if not at.WAHA_KEY:
            item(False, "WhatsApp configurado", "rode ./whatsapp-configurar.sh")
            return _fechar(d, passos, consertos, None, avisar)
        w = at.status_whatsapp()
        st = w.get("status")
        if st in ("FAILED", "STOPPED", "SEM_SESSAO") or (st == "STARTING" and (d.get("starting_desde") or time.time()) < time.time() - 300):
            if consertar:
                ok, t = at.reiniciar_sessao()
                consertos.append(f"sessão {st}: {t}")
                time.sleep(8)
                w = at.status_whatsapp()
                st = w.get("status")
        d["starting_desde"] = d.get("starting_desde") or time.time() if st == "STARTING" else None
        if st == "SCAN_QR_CODE":
            item(False, "WhatsApp conectado", "o WhatsApp foi desconectado: escaneie o QR code (📱 no painel)")
            return _fechar(d, passos, consertos, None, avisar, qr=True)
        if not item(st == "WORKING", "WhatsApp conectado", f"{st}" + (f" · {w.get('erro')}" if w.get("erro") else "")):
            return _fechar(d, passos, consertos, None, avisar)

        ok, t = at.garantir_webhook()
        item(ok, "Webhook e histórico na sessão", t)
        if ok and "agora" in t:
            consertos.append("webhook/histórico gravados de novo na sessão")

        cod, t = _testar_n8n()
        if cod == "inativo" and consertar:
            ok2, t2 = republicar_fluxo()
            consertos.append(t2)
            if ok2:
                time.sleep(3)
                cod, t = _testar_n8n()
        item(cod == "ok", "n8n recebe e repassa ao Jarvis", t)

        # mensagens de clientes que chegaram muito atrasadas desde o último teste (sintoma de recebimento travado)
        ult = d.get("ultimo_teste_t", time.time() - INTERVALO)
        atrasadas = [x for x in at._ler_estado().get("atrasadas", []) if x["t"] > ult]
        if atrasadas:
            pior = max(x["atraso"] for x in atrasadas) // 60
            dica = (" O motor NOWEB tem esse defeito: troque para o GOWS (./whatsapp-trocar-motor.sh)."
                    if at.motor() == "NOWEB" else "")
            item(False, "Mensagens chegando na hora",
                 f"{len(atrasadas)} mensagem(ns) de cliente chegaram até {pior} min atrasadas (o robô não responde mensagem "
                 f"antiga).{dica}")
            if consertar:
                _, t5 = at.reiniciar_sessao()
                consertos.append("reconexão da sessão para destravar o recebimento: " + t5)
        else:
            item(True, "Mensagens chegando na hora", "sem atrasos desde o último teste")
        d["ultimo_teste_t"] = time.time()

        corte = time.time() - 12 * 3600
        d["ja_avisadas"] = {k: t for k, t in (d.get("ja_avisadas") or {}).items() if t > corte}
        lista, aviso = perdidas(d.get("desde", time.time()), d["ja_avisadas"])
        for x in atrasadas:
            if x["k"] not in d["ja_avisadas"] and not any(y.get("chave") == x["k"] for y in lista or []):
                lista = (lista or []) + [{"chave": x["k"], "chat": x["chat"], "nome": x.get("nome", ""), "numero": x["numero"],
                                          "texto": x["texto"] or "(mídia)", "min": int((time.time() - x["t"] + x["atraso"]) // 60)}]
        if lista is None:
            item(True, "Mensagens de clientes chegando", aviso + " (verificação parcial)")
        elif lista and any(not str(x["chave"]) in {a["k"] for a in atrasadas} for x in lista):
            item(False, "Mensagens de clientes chegando",
                 f"{len(lista)} conversa(s) com mensagem que não chegou ao Jarvis")
            if consertar and cod == "ok":
                ok3, t3 = at.garantir_webhook(forcar=True)
                consertos.append("webhook regravado: " + t3)
                if not ok3:
                    _, t4 = at.reiniciar_sessao()
                    consertos.append(t4)
        else:
            item(True, "Mensagens de clientes chegando", "todas as últimas mensagens de clientes chegaram")
        return _fechar(d, passos, consertos, lista, avisar)


def _fechar(d, passos, consertos, lista, avisar, qr=False):
    for x in lista or []:
        d.setdefault("ja_avisadas", {})[x["chave"]] = time.time()
    ok = all(p["ok"] for p in passos)
    r = {"ok": ok, "passos": passos, "consertos": consertos, "perdidas": lista or [],
         "quando": time.strftime("%d/%m %H:%M")}
    problema = " | ".join(p["titulo"] for p in passos if not p["ok"])
    if avisar:
        if not ok and problema != d.get("problema"):
            linhas = ["🚨 Atendimento do WhatsApp com problema"] + \
                     [f"❌ {p['titulo']}: {p['detalhe']}" for p in passos if not p["ok"]]
            if consertos:
                linhas += ["", "🔧 Já tentei:"] + [f"• {c}" for c in consertos]
            if lista:
                linhas += ["", "📵 Clientes que escreveram e não receberam resposta (responda por você):"] + \
                          [f"• {x['nome'] or x['numero']} ({x['numero']}) há {x['min']} min: “{x['texto']}”" for x in lista[:15]]
            linhas.append("\n/whatsapp testar · /whatsapp reiniciar · /whatsapp reconectar")
            _avisar("\n".join(linhas))
            if qr:
                mandar_qr_depois(0)
            d["problema"], d["problema_desde"] = problema, time.time()
        elif ok and d.get("problema"):
            mins = int((time.time() - d.get("problema_desde", time.time())) // 60)
            _avisar(f"✅ Atendimento do WhatsApp voltou ao normal (ficou {mins} min com problema)."
                    + (f"\n🔧 {'; '.join(consertos)}" if consertos else ""))
            d["problema"] = None
        elif ok and consertos:
            _avisar("🔧 Vigia do WhatsApp consertou sozinho: " + "; ".join(consertos))
    d["ultimo"] = r
    _salvar(d)
    return r


def texto(r):
    if not r or not r.get("passos"):
        return "🛡 Vigia do WhatsApp: ainda não rodou."
    linhas = [f"🛡 Vigia do WhatsApp ({r.get('quando')}): {'✅ tudo funcionando' if r.get('ok') else '❌ com problema'}"]
    linhas += [f"{'✅' if p['ok'] else '❌'} {p['titulo']}" + (f" — {p['detalhe']}" if p.get("detalhe") else "") for p in r["passos"]]
    if r.get("consertos"):
        linhas.append("🔧 " + "; ".join(r["consertos"]))
    for x in (r.get("perdidas") or [])[:10]:
        linhas.append(f"📵 {x['nome'] or x['numero']} ({x['numero']}) há {x['min']} min: “{x['texto']}”")
    return "\n".join(linhas)


def mandar_qr_depois(espera=6):
    """Manda o QR code no Telegram e avisa quando conectar (acompanha por até 5 minutos)."""
    def _ir():
        time.sleep(espera)
        import rotinas
        enviado = False
        for _ in range(30):
            st = at.status_whatsapp().get("status")
            if st == "WORKING":
                if enviado:
                    _avisar("✅ WhatsApp conectado de novo. O atendimento voltou.")
                    at.garantir_webhook()
                return
            if st == "SCAN_QR_CODE" and not enviado:
                try:
                    caminho = os.path.join(at.DIR, "qr.png")
                    open(caminho, "wb").write(at.qr_png())
                    rotinas.avisar_telegram_foto(caminho, "📲 Escaneie no WhatsApp do celular da empresa: Aparelhos "
                                                          "conectados → Conectar aparelho. Se expirar, abra 📱 no painel.")
                    enviado = True
                except Exception as e:  # noqa: BLE001
                    _avisar(f"📲 Abra 📱 no painel para escanear o QR code ({type(e).__name__}).")
                    enviado = True
            time.sleep(10)
    threading.Thread(target=_ir, daemon=True).start()


def iniciar():
    """Laço do vigia (chamado na subida do painel)."""
    if _rodando["ativo"] or not at.WAHA_KEY:
        return
    _rodando["ativo"] = True
    d = _ler()
    d.setdefault("desde", time.time())
    _salvar(d)

    def laco():
        time.sleep(60)
        while True:
            try:
                if _ler().get("ligado", True) and at._ler_estado().get("ligado", True):
                    checar()
            except Exception as e:  # noqa: BLE001
                print("vigia:", type(e).__name__, e, flush=True)
            time.sleep(INTERVALO)
    threading.Thread(target=laco, daemon=True).start()
