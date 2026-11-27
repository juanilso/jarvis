"""Voz da ElevenLabs para o atendimento do WhatsApp (respostas em áudio, como mensagem de voz).

- A chave fica em /segredos/elevenlabs.json (600). O painel só mostra mascarada; nunca vai para log nem Telegram.
- Gera MP3 na ElevenLabs e converte para OGG/Opus (o formato da mensagem de voz do WhatsApp).
- Sem chave (ou se a ElevenLabs falhar), usa a voz gratuita do Jarvis (edge-tts), para o cliente não ficar sem áudio.
"""
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request

SEGREDO = os.environ.get("ELEVENLABS_CONFIG", "/segredos/elevenlabs.json")
API = os.environ.get("ELEVENLABS_URL", "https://api.elevenlabs.io").rstrip("/")
MODELOS = {"eleven_multilingual_v2": "Multilingual v2 (mais natural)",
           "eleven_turbo_v2_5": "Turbo v2.5 (rápido, metade do custo)",
           "eleven_flash_v2_5": "Flash v2.5 (mais rápido e barato)",
           "eleven_v3": "v3 (mais expressivo)"}
PADRAO = {"token": "", "voz": "", "voz_nome": "", "modelo": "eleven_multilingual_v2", "estabilidade": 0.5,
          "velocidade": 1.0}
_trava = threading.Lock()
_cache_vozes = {"t": 0, "lista": []}


def config():
    try:
        with open(SEGREDO, encoding="utf-8") as f:
            return {**PADRAO, **json.load(f)}
    except (OSError, json.JSONDecodeError):
        return dict(PADRAO)


def publico():
    c = config()
    t = c["token"]
    return {"token": (t[:4] + "…" + t[-4:]) if len(t) > 12 else ("definido" if t else ""), "voz": c["voz"],
            "voz_nome": c["voz_nome"], "modelo": c["modelo"], "modelos": MODELOS, "estabilidade": c["estabilidade"],
            "velocidade": c["velocidade"]}


def salvar(novo):
    with _trava:
        c = config()
        t = (novo.get("token") or "").strip()
        if t and "…" not in t:
            if not re.fullmatch(r"[A-Za-z0-9_\-]{20,200}", t):
                raise ValueError("chave da ElevenLabs em formato inesperado")
            c["token"] = t
            _cache_vozes["t"] = 0
        if novo.get("apagar_token"):
            c["token"] = ""
        if "voz" in novo:
            c["voz"] = re.sub(r"[^A-Za-z0-9]", "", str(novo["voz"]))[:40]
            c["voz_nome"] = str(novo.get("voz_nome") or "")[:60]
        if novo.get("modelo") in MODELOS:
            c["modelo"] = novo["modelo"]
        for k, lo, hi in (("estabilidade", 0.0, 1.0), ("velocidade", 0.7, 1.2)):
            if k in novo:
                try:
                    c[k] = max(lo, min(hi, float(novo[k])))
                except (TypeError, ValueError):
                    pass
        os.makedirs(os.path.dirname(SEGREDO), exist_ok=True)
        tmp = SEGREDO + ".tmp"
        with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
            json.dump(c, f)
        os.replace(tmp, SEGREDO)
    return publico()


def _req(caminho, corpo=None, tempo=60, aceitar="application/json"):
    c = config()
    if not c["token"]:
        raise RuntimeError("chave da ElevenLabs não configurada")
    cab = {"xi-api-key": c["token"], "Accept": aceitar, "User-Agent": "Jarvis/1.44"}
    dados = None
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        cab["Content-Type"] = "application/json"
    req = urllib.request.Request(API + caminho, data=dados, headers=cab, method="POST" if dados else "GET")
    try:
        with urllib.request.urlopen(req, timeout=tempo) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:300]
        try:
            j = json.loads(detalhe).get("detail")
            detalhe = (j.get("message") or j.get("status")) if isinstance(j, dict) else (j or detalhe)
        except (ValueError, AttributeError):
            pass
        raise RuntimeError(f"ElevenLabs HTTP {e.code}: {str(detalhe)[:200]}") from None


def vozes():
    """Vozes da conta (as suas, clonadas e as da biblioteca que você adicionou)."""
    if time.time() - _cache_vozes["t"] < 600 and _cache_vozes["lista"]:
        return _cache_vozes["lista"]
    j = json.loads(_req("/v1/voices", tempo=30))
    lista = []
    for v in j.get("voices", []):
        rot = v.get("labels") or {}
        info = " · ".join(x for x in (rot.get("gender"), rot.get("accent"), rot.get("age"), v.get("category")) if x)
        lista.append({"id": v.get("voice_id"), "nome": v.get("name"), "info": info, "previa": v.get("preview_url") or ""})
    _cache_vozes.update(t=time.time(), lista=lista)
    return lista


def para_fala(texto):
    """Texto de WhatsApp → texto para falar: sem links, códigos, emojis e marcações."""
    t = re.sub(r"https?://\S+|www\.\S+", " (o link está na mensagem escrita) ", texto or "")
    t = re.sub(r"\S{28,}", " (o código está na mensagem escrita) ", t)  # Pix copia e cola, chaves, códigos longos
    t = re.sub(r"[*_~`]", "", t)
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️‍]", "", t)
    t = re.sub(r"R\$\s?(\d+),(\d{2})", lambda m: f"{m.group(1)} reais" + (f" e {int(m.group(2))} centavos" if int(m.group(2)) else ""), t)
    t = re.sub(r"\(o (link|código) está na mensagem escrita\)(\s*\(o \1 está na mensagem escrita\))+", r"(o \1 está na mensagem escrita)", t)
    return re.sub(r"[ \t]+", " ", t).strip()[:2500]


def precisa_texto(texto):
    """A resposta tem algo que o cliente precisa copiar/clicar (link, Pix, código, número longo)?"""
    return bool(re.search(r"https?://|www\.|\S{28,}|\d{6,}|@\w+\.\w+", texto or ""))


def _para_ogg(origem, destino):
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", origem, "-vn", "-ac", "1", "-ar", "48000",
                    "-c:a", "libopus", "-b:a", "32k", "-application", "voip", destino], check=True, timeout=120)


def gerar_audio(texto, formato="ogg"):
    """Áudio em bytes no formato pedido ("ogg" = mensagem de voz; "mp3" = toca em qualquer navegador)."""
    ogg, origem = gerar_ogg(texto)
    if formato == "ogg":
        return ogg, origem
    with tempfile.TemporaryDirectory() as tmp:
        a, b = os.path.join(tmp, "a.ogg"), os.path.join(tmp, "a.mp3")
        with open(a, "wb") as f:
            f.write(ogg)
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", a, "-c:a", "libmp3lame", "-b:a", "96k", b],
                       check=True, timeout=120)
        with open(b, "rb") as f:
            return f.read(), origem


def gerar_ogg(texto):
    """Mensagem de voz (OGG/Opus, em bytes) e quem gerou ("elevenlabs" ou "gratuita")."""
    fala = para_fala(texto)
    if not fala:
        raise ValueError("nada para falar")
    c = config()
    with tempfile.TemporaryDirectory() as tmp:
        mp3, ogg = os.path.join(tmp, "a.mp3"), os.path.join(tmp, "a.ogg")
        origem = "gratuita"
        if c["token"] and c["voz"]:
            try:
                corpo = {"text": fala, "model_id": c["modelo"], "language_code": "pt",
                         "voice_settings": {"stability": c["estabilidade"], "similarity_boost": 0.75,
                                            "speed": c["velocidade"]}}
                if c["modelo"] == "eleven_multilingual_v2":
                    corpo.pop("language_code")
                audio = _req(f"/v1/text-to-speech/{c['voz']}?output_format=mp3_44100_128", corpo, tempo=90,
                             aceitar="audio/mpeg")
                with open(mp3, "wb") as f:
                    f.write(audio)
                origem = "elevenlabs"
            except Exception as e:  # noqa: BLE001
                print("elevenlabs: falhou, usando a voz gratuita:", str(e)[:200], flush=True)
        if origem == "gratuita":
            import jarvis_core
            if not jarvis_core.gerar_mp3(fala, mp3, voz=os.environ.get("ATENDIMENTO_VOZ_GRATUITA", "pt-BR-FranciscaNeural")):
                raise RuntimeError("não consegui gerar a voz")
        _para_ogg(mp3, ogg)
        with open(ogg, "rb") as f:
            return f.read(), origem


def testar(texto="Oi! Aqui é o atendimento. Pode me mandar sua dúvida por áudio ou por escrito, do jeito que preferir."):
    ogg, origem = gerar_ogg(texto)
    return ogg, origem
