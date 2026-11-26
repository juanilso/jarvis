"""Alerta dos jogos X minutos antes (padrão 30) no seu Telegram e/ou num grupo, por um bot só de envio.

- O bot do grupo é OUTRO bot (criado no @BotFather): ele só envia; o bot do Jarvis (que controla tudo) fica só com você.
- Token e grupo ficam em /segredos/jogos_grupo.json (permissão 600, só no serviço do painel). O token nunca volta
  inteiro para a tela nem vai para logs.
- Jogos no mesmo horário saem num alerta só, com a imagem do(s) confronto(s) e o texto.
- Opcional: mandar no grupo também a lista do dia (quando ela é gerada, às 8h).
"""
import datetime as dt
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
import uuid

import jogos

SEGREDO = os.environ.get("JOGOS_GRUPO_CONFIG", "/segredos/jogos_grupo.json")
PADRAO = {"ligado": False, "minutos": 30, "para_mim": True, "para_grupo": False, "lista_no_grupo": False,
          "token": "", "grupo": "", "grupo_nome": "", "bot_nome": ""}
_lock = threading.Lock()
_rodando = {"ativo": False}
_cache = {}
API = os.environ.get("JARVIS_TELEGRAM_API", "https://api.telegram.org")


def config():
    try:
        d = json.load(open(SEGREDO, encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {**PADRAO, **d}


def publico():
    """O que pode aparecer no painel (token mascarado)."""
    c = config()
    t = c.get("token") or ""
    return {**{k: v for k, v in c.items() if k != "token"},
            "token_mascarado": (t.split(":")[0] + ":…" + t[-4:]) if t else "", "tem_token": bool(t)}


def salvar(novo):
    with _lock:
        c = config()
        for k in ("ligado", "para_mim", "para_grupo", "lista_no_grupo"):
            if k in novo:
                c[k] = bool(novo[k])
        if "minutos" in novo:
            c["minutos"] = max(5, min(180, int(novo.get("minutos") or 30)))
        token = str(novo.get("token") or "").strip()
        if token == "-":
            c.update(token="", bot_nome="")
        elif token:
            if not re.fullmatch(r"\d{5,}:[\w-]{30,}", token):
                raise ValueError("token inválido: copie do @BotFather (números:letras)")
            nome = _bot_nome(token)
            c.update(token=token, bot_nome=nome)
        if "grupo" in novo:
            g = str(novo.get("grupo") or "").strip()
            if g and not re.fullmatch(r"-?\d{5,}|@[\w]{4,}", g):
                raise ValueError("grupo inválido: use o número do grupo (ex.: -100123…) ou @canal")
            c["grupo"] = g
            if "grupo_nome" in novo:
                c["grupo_nome"] = str(novo.get("grupo_nome") or "")[:80]
        os.makedirs(os.path.dirname(SEGREDO), exist_ok=True)
        tmp = SEGREDO + ".tmp"
        with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False)
        os.replace(tmp, SEGREDO)
    return publico()


# ------------------------------------------------------------------ Telegram do bot do grupo
def _tg(token, metodo, dados=None, tempo=30):
    req = urllib.request.Request(f"{API}/bot{token}/{metodo}", data=json.dumps(dados or {}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=tempo) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except ValueError:
            return {"ok": False, "description": f"HTTP {e.code}"}


def _bot_nome(token):
    r = _tg(token, "getMe")
    if not r.get("ok"):
        raise ValueError("o Telegram não aceitou o token (" + str(r.get("description", ""))[:80] + ")")
    return "@" + r["result"].get("username", "")


def detectar_grupos():
    """Grupos/canais onde o bot foi colocado (precisa ter acontecido algo recente: adicionar o bot ou mandar
    uma mensagem no grupo). Devolve lista de {id, nome, tipo}."""
    c = config()
    if not c["token"]:
        raise ValueError("cadastre o token do bot do grupo primeiro")
    r = _tg(c["token"], "getUpdates", {"limit": 100, "allowed_updates": ["message", "my_chat_member", "channel_post"]})
    if not r.get("ok"):
        raise ValueError(str(r.get("description", "falhou"))[:120])
    vistos = {}
    for u in r.get("result", []):
        for chave in ("message", "my_chat_member", "channel_post"):
            chat = (u.get(chave) or {}).get("chat") or {}
            if chat.get("type") in ("group", "supergroup", "channel"):
                vistos[str(chat["id"])] = {"id": str(chat["id"]), "nome": chat.get("title", ""), "tipo": chat["type"]}
    return list(vistos.values())


def _foto_grupo(caminho, legenda, tipo="photo"):
    c = config()
    if not (c["token"] and c["grupo"]):
        return False, "bot do grupo não configurado"
    b = uuid.uuid4().hex
    dados = open(caminho, "rb").read()
    corpo = b"".join([
        f"--{b}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{c['grupo']}\r\n".encode(),
        f"--{b}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{legenda[:1000]}\r\n".encode(),
        f"--{b}\r\nContent-Disposition: form-data; name=\"{tipo}\"; filename=\"{'jogos.mp4' if tipo == 'video' else 'jogo.png'}\"\r\n"
        f"Content-Type: {'video/mp4' if tipo == 'video' else 'image/png'}\r\n\r\n".encode(),
        dados, f"\r\n--{b}--\r\n".encode()])
    req = urllib.request.Request(f"{API}/bot{c['token']}/{'sendVideo' if tipo == 'video' else 'sendPhoto'}", data=corpo,
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return bool(json.loads(r.read().decode()).get("ok")), "ok"
    except urllib.error.HTTPError as e:
        return False, _erro_grupo(e)
    except Exception as e:  # noqa: BLE001
        return False, type(e).__name__


def _texto_grupo(texto):
    c = config()
    if not (c["token"] and c["grupo"]):
        return False, "bot do grupo não configurado"
    r = _tg(c["token"], "sendMessage", {"chat_id": c["grupo"], "text": texto[:4000], "disable_web_page_preview": True})
    return bool(r.get("ok")), ("ok" if r.get("ok") else str(r.get("description", ""))[:150])


def _erro_grupo(e):
    try:
        d = json.loads(e.read().decode()).get("description", "")
    except ValueError:
        d = ""
    if "not enough rights" in d or "have no rights" in d:
        return "o bot não tem permissão de enviar no grupo (deixe-o como administrador ou libere mensagens)"
    if "chat not found" in d:
        return "grupo não encontrado: use Detectar grupo de novo"
    if "kicked" in d or "not a member" in d:
        return "o bot foi removido do grupo"
    return f"HTTP {e.code} {d[:100]}"


def testar():
    c = config()
    resultados = []
    if c["para_grupo"] or c["grupo"]:
        ok, t = _texto_grupo("✅ Teste do Jarvis: os alertas dos jogos vão chegar aqui.")
        resultados.append(("grupo", ok, t))
    if c["para_mim"]:
        import rotinas
        resultados.append(("você", bool(rotinas.avisar_telegram("✅ Teste: os alertas dos jogos vão chegar aqui.")), ""))
    return resultados


# ------------------------------------------------------------------ alertas
def _arq_enviados(dia):
    return os.path.join(jogos.DIR, f"{dia.isoformat()}-alertas.json")


def _enviados(dia):
    try:
        return set(json.load(open(_arq_enviados(dia), encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _marcar(dia, ids):
    os.makedirs(jogos.DIR, exist_ok=True)
    json.dump(sorted(_enviados(dia) | set(ids)), open(_arq_enviados(dia), "w", encoding="utf-8"))


def texto_alerta(lista, minutos):
    linhas = [f"⏰ Faltam {minutos} min!" if len(lista) == 1 else f"⏰ Faltam {minutos} min para {len(lista)} jogos!"]
    for j in lista:
        canais = " / ".join(j.get("canais") or []) or "a confirmar"
        linhas += ["", f"⚽ {j['casa']} x {j['fora']}", f"🏆 {j['liga']} · 🕒 {j['hora']}", f"📺 {canais}"]
    marca = jogos.config().get("rodape") or ""
    if marca:
        linhas += ["", marca]
    return "\n".join(linhas)


def _imagem(lista, dia, minutos):
    import jogos_imagem
    cfg = {**jogos.config(), "_titulo": "COMEÇA EM", "_subtitulo": f"{minutos} MINUTOS",
           "_pasta_arte": jogos.DIR}  # reaproveita a arte de IA do dia (não gera outra a cada alerta)
    pasta = os.path.join(jogos.DIR, "alertas")
    os.makedirs(pasta, exist_ok=True)
    caminhos = jogos_imagem.desenhar(lista, dia, cfg, pasta)
    # o desenho grava com o nome do dia; renomeia para não sobrescrever a lista do dia
    destino = os.path.join(pasta, f"{dia.isoformat()}-{lista[0]['hora'].replace(':', '')}.png")
    if caminhos:
        os.replace(caminhos[0], destino)
        return destino
    return None


def verificar(agora=None):
    """Manda os alertas que estão na hora. Devolve quantos jogos foram alertados."""
    c = config()
    if not c["ligado"] or not (c["para_mim"] or (c["para_grupo"] and c["token"] and c["grupo"])):
        return 0
    agora = agora or time.time()
    dia = jogos.hoje()
    d = jogos.do_dia()
    lista = d.get("jogos") if d and d.get("dia") == dia.isoformat() else None
    if lista is None:  # lista do dia ainda não gerada: busca na ESPN (guarda 15 min)
        if _cache.get("dia") == dia.isoformat() and time.time() - _cache.get("t", 0) < 900:
            lista = _cache["lista"]
        else:
            try:
                lista, _ = jogos.agenda(dia)
                # sem a lista do dia (canais não confirmados), só alerta internacional com time brasileiro
                lista = [j for j in lista if not j.get("internacional") or jogos.tem_brasileiro(j)]
                _cache.update(dia=dia.isoformat(), t=time.time(), lista=lista)
            except Exception as e:  # noqa: BLE001
                print("alertas: agenda falhou", e, flush=True)
                return 0
    ja = _enviados(dia)
    janela = c["minutos"] * 60
    na_hora = [j for j in lista if j.get("ts") and j["id"] not in ja and j.get("estado", "pre") == "pre"
               and -120 <= j["ts"] - agora <= janela]
    if not na_hora:
        return 0
    grupos = {}
    for j in na_hora:
        grupos.setdefault(j["hora"], []).append(j)
    for hora, js in sorted(grupos.items()):
        faltam = max(1, round((js[0]["ts"] - agora) / 60))
        texto = texto_alerta(js, faltam)
        img = None
        try:
            img = _imagem(js, dia, faltam)
        except Exception as e:  # noqa: BLE001
            print("alertas: imagem falhou", e, flush=True)
        if c["para_mim"]:
            import rotinas
            if img:
                rotinas.avisar_telegram_foto(img, texto)
            else:
                rotinas.avisar_telegram(texto)
        if c["para_grupo"] and c["token"] and c["grupo"]:
            ok, motivo = _foto_grupo(img, texto) if img else _texto_grupo(texto)
            if not ok:
                import rotinas
                rotinas.avisar_telegram(f"⚠️ Não consegui mandar o alerta dos jogos no grupo: {motivo}")
        _marcar(dia, [j["id"] for j in js])
    return len(na_hora)


def lista_no_grupo(d):
    """Depois que a lista do dia é gerada: manda no grupo (se ligado)."""
    c = config()
    if not (c["lista_no_grupo"] and c["token"] and c["grupo"]):
        return
    for i, img in enumerate(d.get("imagens") or []):
        _foto_grupo(img, "⚽ Jogos de hoje" + (f" ({i + 1}/{len(d['imagens'])})" if len(d["imagens"]) > 1 else ""))
    if d.get("video") and os.path.exists(d["video"]) and os.path.getsize(d["video"]) < 49 * 1024 * 1024:
        _foto_grupo(d["video"], "🎬 Jogos de hoje", tipo="video")
    _texto_grupo(re.sub(r"[*_]", "", d.get("texto") or ""))  # o Telegram sem formatação do WhatsApp


def iniciar():
    if _rodando["ativo"]:
        return
    _rodando["ativo"] = True

    def laco():
        time.sleep(30)
        while True:
            try:
                verificar()
            except Exception as e:  # noqa: BLE001
                print("alertas dos jogos:", type(e).__name__, e, flush=True)
            time.sleep(60)
    threading.Thread(target=laco, daemon=True).start()
