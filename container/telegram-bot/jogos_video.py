"""Vídeo dos jogos do dia (9:16, para Status/Reels/grupos).

Fundo:
- "ia": vídeo gerado pelo Gemini Omni Flash (API do Gemini, conta paga) a partir da arte do dia: estádio, luzes,
  torcida, bola girando, com som de torcida. Sem texto, sem pessoas reais. Um por dia (fica guardado).
- "animado": a própria arte do dia (ou o fundo simples) com zoom lento. Custo zero.
Por cima, o Jarvis anima os jogos de verdade (título, cartões entrando um a um, rodapé): a IA não escreve nada,
então nomes, horários e canais nunca saem errados. Se a IA falhar ou o limite do mês acabar, sai o "animado".
"""
import base64
import datetime as dt
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request

from PIL import Image

import jogos_imagem as ji

L, A = ji.L, ji.A
FPS = 30
MODELO = os.environ.get("JARVIS_VIDEO_MODELO", "gemini-omni-1.1-flash")
CUSTO_SEG = float(os.environ.get("JARVIS_VIDEO_CUSTO_SEG", "0.10"))  # estimativa US$/segundo (720p)
SEG_IA = 10  # duração estimada do clipe da IA (para a conta do limite)
UA = "jarvis-jogos/1.0"


# ------------------------------------------------------------------ limite de gasto
def _arq_gasto(pasta):
    return os.path.join(pasta, "video-gasto.json")


def gasto_mes(pasta):
    try:
        return float(json.load(open(_arq_gasto(pasta), encoding="utf-8")).get(time.strftime("%Y-%m"), 0))
    except (OSError, ValueError, AttributeError):
        return 0.0


def _somar_gasto(pasta, valor):
    try:
        g = json.load(open(_arq_gasto(pasta), encoding="utf-8"))
    except (OSError, ValueError):
        g = {}
    mes = time.strftime("%Y-%m")
    g[mes] = round(float(g.get(mes, 0)) + valor, 2)
    json.dump(g, open(_arq_gasto(pasta), "w", encoding="utf-8"))


# ------------------------------------------------------------------ Gemini Omni Flash
def _http(url, corpo=None, chave="", tempo=600, bruto=False):
    req = urllib.request.Request(url, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Content-Type": "application/json", "User-Agent": UA, "x-goog-api-key": chave})
    with urllib.request.urlopen(req, timeout=tempo) as r:
        dados = r.read()
    return dados if bruto else json.loads(dados.decode())


def _video_da_resposta(r):
    for passo in r.get("steps") or []:
        if passo.get("type") == "model_output":
            for c in passo.get("content") or []:
                if c.get("type") == "video" or str(c.get("mime_type", "")).startswith("video"):
                    return c
    v = r.get("output_video")  # caso a API devolva o campo de conveniência
    return v if isinstance(v, dict) else None


def omni(texto, imagem_png=None, pasta_tmp="/tmp"):
    """Gera o clipe e devolve os bytes do MP4."""
    chave = os.environ.get("GEMINI_API_KEY", "")
    if not chave:
        raise RuntimeError("sem chave do Gemini (GEMINI_API_KEY)")
    base = os.environ.get("JARVIS_GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    entrada = texto
    if imagem_png:
        entrada = [{"type": "image", "data": base64.b64encode(imagem_png).decode(), "mime_type": "image/png"},
                   {"type": "text", "text": texto}]
    formato = {"type": "video", "aspect_ratio": "9:16", "resolution": "720p"}
    corpo = {"model": MODELO, "input": entrada, "response_format": formato}
    try:
        r = _http(f"{base}/interactions", corpo, chave)
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")[:300]
        if e.code == 400 and re.search(r"deliver|uri|4 ?MB|too large", msg, re.I):
            r = _http(f"{base}/interactions", {**corpo, "response_format": {**formato, "delivery": "uri"}}, chave)
        else:
            raise RuntimeError(f"HTTP {e.code}: {msg}") from None
    fim = time.time() + 900
    while r.get("status") not in (None, "completed") and time.time() < fim:  # modo em segundo plano
        if r.get("status") in ("failed", "cancelled", "incomplete"):
            raise RuntimeError(f"a IA não gerou o vídeo ({r.get('status')}): {str(r.get('error'))[:200]}")
        time.sleep(10)
        r = _http(f"{base}/interactions/{r['id']}", chave=chave, tempo=60)
    v = _video_da_resposta(r)
    if not v:
        raise RuntimeError("resposta sem vídeo: " + json.dumps(r)[:200])
    if v.get("data"):
        return base64.b64decode(v["data"])
    uri = v.get("uri") or ""
    if not uri:
        raise RuntimeError("vídeo sem dados nem link")
    nome = re.search(r"(files/[^:/?]+)", uri)
    while nome and time.time() < fim:  # espera o arquivo ficar pronto
        st = _http(f"{base}/{nome.group(1)}", chave=chave, tempo=60)
        if st.get("state") in (None, "ACTIVE"):
            break
        if st.get("state") == "FAILED":
            raise RuntimeError("o arquivo do vídeo falhou no Google")
        time.sleep(6)
    return _http(uri, chave=chave, tempo=300, bruto=True)


def pedido_video():
    return ("Animate this image into a seamless vertical 9:16 video of about 8 seconds. Slow cinematic camera push-in. "
            "Stadium floodlights flicker and sweep, light haze drifts, the crowd in the stands waves and jumps, the "
            "soccer ball spins slowly with a soft glow, the generic players move subtly. Keep the composition and colors "
            "of the image and keep the central area dark and clean. Absolutely NO text, letters, numbers, logos, "
            "crests or watermarks, and no real or recognizable people. "
            "Audio: excited stadium crowd ambience and cheers, no dialogue, no narration, no music with lyrics.")


def fundo_video(dia, destaque, pasta, cfg, info):
    """Caminho do MP4 de fundo do dia (gera uma vez por dia) ou None (com o motivo em info['aviso_video'])."""
    cache = os.path.join(pasta, f"{dia.isoformat()}-fundo.mp4")
    if os.path.exists(cache) and os.path.getsize(cache) > 10000:
        info["video_fundo"] = "vídeo de IA do dia (já gerado)"
        return cache
    limite = float(cfg.get("video_limite") or 0)
    custo = CUSTO_SEG * SEG_IA
    if limite and gasto_mes(pasta) + custo > limite:
        info["aviso_video"] = f"limite de US$ {limite:.0f}/mês do vídeo com IA atingido; saiu o vídeo animado"
        return None
    arte = os.path.join(cfg.get("_pasta_arte") or pasta, f"{dia.isoformat()}-arte.png")
    imagem = None
    if os.path.exists(arte):  # a arte do dia vira o primeiro quadro: vídeo e banner combinam
        im = Image.open(arte).convert("RGB").resize((720, 1280), Image.LANCZOS)
        caminho = os.path.join(pasta, f"{dia.isoformat()}-arte-720.png")
        im.save(caminho, optimize=True)
        imagem = open(caminho, "rb").read()
        texto = pedido_video()
    else:
        import jogos_arte
        texto = jogos_arte.pedido(destaque or {}) + " " + pedido_video().replace("Animate this image into", "Create")
    try:
        mp4 = omni(texto, imagem, pasta)
    except Exception as e:  # noqa: BLE001
        info["aviso_video"] = f"vídeo com IA indisponível ({type(e).__name__}: {str(e)[:200]}); saiu o vídeo animado"
        return None
    _somar_gasto(pasta, custo)
    open(cache, "wb").write(mp4)
    info["video_fundo"] = f"Gemini ({MODELO})"
    return cache


# ------------------------------------------------------------------ animação por cima
def _suave(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _colar(base, peca, x, y, alfa=1.0):
    """Cola uma peça RGBA em (x, y), cortando o que sair da tela, com transparência extra opcional."""
    if alfa <= 0.01:
        return
    x, y = int(round(x)), int(round(y))
    esq, cima = max(0, -x), max(0, -y)
    dir_, baixo = min(peca.width, L - x), min(peca.height, A - y)
    if dir_ <= esq or baixo <= cima:
        return
    p = peca.crop((esq, cima, dir_, baixo)) if (esq or cima or dir_ < peca.width or baixo < peca.height) else peca
    if alfa < 0.99:
        p = p.copy()
        p.putalpha(p.getchannel("A").point(lambda v: int(v * alfa)))
    base.alpha_composite(p, (x + esq, y + cima))


def _pecas(pagina):
    """Divide a página transparente em faixas: cabeçalho, um cartão por jogo, rodapé."""
    cab = pagina.crop((0, 0, L, ji.CARTAO_Y - 8))
    rod = pagina.crop((0, A - 210, L, A))
    cartoes = []
    for k in range(ji.POR_PAGINA_ARTE):
        y = ji.CARTAO_Y + k * ji.CARTAO_PASSO
        faixa = pagina.crop((0, y - 6, L, y + ji.CARTAO_H + 6))
        if faixa.getbbox():
            cartoes.append((faixa, y - 6))
    return cab, cartoes, rod


def _quadros(paginas, ultima_seg):
    """Gera os quadros RGBA (bytes) da camada animada. paginas = [(cab, cartoes, rod, segundos)]."""
    fundo = ji.escurecer()
    for n, (cab, cartoes, rod, seg) in enumerate(paginas):
        total = int(seg * FPS)
        fim_anim = 0.35 + 0.3 * len(cartoes) + 0.6
        anterior = None
        for f in range(total):
            t = f / FPS
            saindo = n < len(paginas) - 1 and t > seg - 0.35
            parado = fim_anim < t and not saindo
            if parado and anterior is not None:
                yield anterior
                continue
            sai = 1 - _suave((t - (seg - 0.35)) / 0.35) if saindo else 1.0
            base = fundo.copy()
            e = _suave(t / 0.5)
            _colar(base, cab, 0, -90 * (1 - e), e * sai)
            for k, (peca, y) in enumerate(cartoes):
                e = _suave((t - 0.35 - 0.3 * k) / 0.55)
                lado = -1 if k % 2 == 0 else 1
                _colar(base, peca, lado * L * (1 - e), y, min(1.0, e * 1.5) * sai)
            e = _suave((t - 0.35 - 0.3 * len(cartoes)) / 0.6)
            _colar(base, rod, 0, A - 210 + 40 * (1 - e), e * sai)
            anterior = base.tobytes()
            yield anterior


def _tem_audio(caminho):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                            "-of", "csv=p=0", caminho], capture_output=True, text=True, timeout=30)
        return bool(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def montar(jogos, dia, cfg, pasta, info=None):
    """Gera o MP4 do dia. Devolve o caminho (ou None se não houver jogos)."""
    info = {} if info is None else info
    if not jogos:
        return None
    os.makedirs(pasta, exist_ok=True)
    fundo = None
    if cfg.get("video") == "ia":
        fundo = fundo_video(dia, jogos[0], pasta, cfg, info)
    still = None
    if not fundo:
        arte = os.path.join(cfg.get("_pasta_arte") or pasta, f"{dia.isoformat()}-arte.png")
        still = arte if os.path.exists(arte) else os.path.join(pasta, f"{dia.isoformat()}-fundo.png")
        if not os.path.exists(still):
            ji._fundo().convert("RGB").save(still)
        info.setdefault("video_fundo", "arte do dia com zoom" if still == arte else "fundo simples com zoom")
    grupos = [jogos[i:i + ji.POR_PAGINA_ARTE] for i in range(0, len(jogos), ji.POR_PAGINA_ARTE)]
    paginas = []
    for i, g in enumerate(grupos, 1):
        camada = ji._pagina_arte(None, g, dia, {**cfg, "_pasta": pasta}, i, len(grupos))
        cab, cartoes, rod = _pecas(camada)
        seg = max(6.5, 0.35 + 0.3 * len(cartoes) + 0.6 + 4.5)
        paginas.append((cab, cartoes, rod, seg))
    total = sum(p[3] for p in paginas)
    saida = os.path.join(pasta, f"{dia.isoformat()}-jogos.mp4")
    tmp = saida + ".tmp.mp4"
    if fundo:
        entrada0 = ["-stream_loop", "-1", "-i", fundo]
        filtro0 = f"[0:v]scale={L}:{A}:force_original_aspect_ratio=increase,crop={L}:{A},fps={FPS},setsar=1[bg]"
    else:
        entrada0 = ["-loop", "1", "-framerate", str(FPS), "-i", still]
        n = int(total * FPS)
        filtro0 = (f"[0:v]scale={int(L * 1.5)}:{int(A * 1.5)},zoompan=z='1+0.08*on/{n}':x='iw/2-(iw/zoom/2)':"
                   f"y='ih/2-(ih/zoom/2)':d=1:s={L}x{A}:fps={FPS},setsar=1[bg]")
    audio = bool(fundo) and _tem_audio(fundo)
    cmd = (["ffmpeg", "-y", "-loglevel", "error"] + entrada0 +
           ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{L}x{A}", "-framerate", str(FPS), "-i", "-",
            "-filter_complex", filtro0 + ";[bg][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
            "-map", "[v]"] +
           (["-map", "0:a", "-c:a", "aac", "-b:a", "128k", "-af", f"afade=t=out:st={max(0, total - 1.2):.2f}:d=1.2"]
            if audio else []) +
           ["-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart", tmp])
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for q in _quadros(paginas, total):
            proc.stdin.write(q)
        proc.stdin.close()
    except BrokenPipeError:
        pass
    erro = proc.stderr.read().decode(errors="replace")
    if proc.wait() != 0 or not os.path.exists(tmp):
        raise RuntimeError("ffmpeg falhou: " + erro[-300:])
    os.replace(tmp, saida)
    info["video_seg"] = round(total, 1)
    return saida
