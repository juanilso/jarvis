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


def omni(texto, imagem_png=None, pasta_tmp="/tmp", proporcao="9:16"):
    """Gera o clipe e devolve os bytes do MP4."""
    chave = os.environ.get("GEMINI_API_KEY", "")
    if not chave:
        raise RuntimeError("sem chave do Gemini (GEMINI_API_KEY)")
    base = os.environ.get("JARVIS_GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    entrada = texto
    if imagem_png:
        entrada = [{"type": "image", "data": base64.b64encode(imagem_png).decode(), "mime_type": "image/png"},
                   {"type": "text", "text": texto}]
    formato = {"type": "video", "aspect_ratio": proporcao, "resolution": "720p"}
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


# ------------------------------------------------------------------ gateway (padrão OpenAI de vídeos) e roteiro pelo Claude
def _gateway():
    base = (os.environ.get("JARVIS_VIDEO_GATEWAY_URL") or os.environ.get("ANTHROPIC_BASE_URL") or "").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    chave = (os.environ.get("JARVIS_VIDEO_GATEWAY_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
             or os.environ.get("ANTHROPIC_API_KEY") or "")
    if not base or not chave:
        raise RuntimeError("gateway não configurado (ANTHROPIC_BASE_URL e a chave no .env.claude)")
    return base, {"Authorization": f"Bearer {chave}", "x-api-key": chave, "User-Agent": UA}


def gateway_video(texto, proporcao, modelo, segundos=8):
    """POST /v1/videos → espera → GET /v1/videos/{id}/content (o padrão que gateways como o LiteLLM seguem)."""
    if not modelo:
        raise RuntimeError("escolha o modelo de vídeo do gateway no painel (⚽ → Vídeo)")
    base, cab = _gateway()
    campos = {"model": modelo, "prompt": texto, "seconds": str(segundos),
              "size": "1280x720" if proporcao == "16:9" else "720x1280"}

    def pedir(url, corpo=None, tipo="application/json", tempo=120, bruto=False):
        req = urllib.request.Request(url, data=corpo, headers={**cab, **({"Content-Type": tipo} if corpo else {})})
        with urllib.request.urlopen(req, timeout=tempo) as r:
            dados = r.read()
        return dados if bruto else json.loads(dados.decode() or "{}")
    try:
        job = pedir(f"{base}/v1/videos", json.dumps(campos).encode())
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")[:300]
        if e.code in (400, 415, 422) and re.search(r"multipart|form", msg, re.I):  # alguns pedem formulário
            b = "jarvis" + str(int(time.time()))
            corpo = "".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n"
                            for k, v in campos.items()) + f"--{b}--\r\n"
            job = pedir(f"{base}/v1/videos", corpo.encode(), f"multipart/form-data; boundary={b}")
        else:
            raise RuntimeError(f"gateway recusou o vídeo (HTTP {e.code}): {msg}") from None
    vid = job.get("id")
    if not vid:
        raise RuntimeError("o gateway não devolveu o id do vídeo: " + json.dumps(job)[:200])
    fim = time.time() + 900
    while job.get("status") not in ("completed", "succeeded") and time.time() < fim:
        if job.get("status") in ("failed", "cancelled", "error"):
            raise RuntimeError(f"o gateway não gerou o vídeo: {str(job.get('error') or job)[:200]}")
        time.sleep(8)
        job = pedir(f"{base}/v1/videos/{vid}", tempo=60)
    if job.get("status") not in ("completed", "succeeded"):
        raise RuntimeError("o vídeo do gateway demorou mais de 15 minutos")
    return pedir(f"{base}/v1/videos/{vid}/content", tempo=300, bruto=True)


def claude_texto(sistema, pedido, modelo=None, max_tokens=400):
    """Texto curto pelo Claude no seu gateway (o mesmo do Jarvis)."""
    base, cab = _gateway()
    corpo = {"model": modelo or os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL") or "claude-haiku-5-5",
             "max_tokens": max_tokens, "system": sistema, "messages": [{"role": "user", "content": pedido}]}
    req = urllib.request.Request(f"{base}/v1/messages", data=json.dumps(corpo).encode(),
                                 headers={**cab, "Content-Type": "application/json", "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.loads(r.read().decode())
    return "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text").strip()


def roteiro_claude(jogos, formato):
    """O Claude escreve a direção de cena do vídeo do dia (em inglês, que os modelos de vídeo entendem melhor)."""
    resumo = "; ".join(f"{j.get('casa')} x {j.get('fora')} ({j.get('liga', '')}, {j.get('hora', '')})" for j in jogos[:6])
    sistema = ("You are a sports promo video director. Write ONE prompt (max 90 words, English) for an AI video model: "
               "an 8-second cinematic soccer-stadium shot that matches today's mood. Use team colors as lights/flags "
               "only. NO text, letters, numbers, logos, crests, jerseys of real clubs or real/recognizable people. "
               "Describe camera motion, lighting, atmosphere and crowd sound. Output only the prompt.")
    forma = "vertical 9:16" if formato == "vertical" else "horizontal 16:9"
    t = claude_texto(sistema, f"Format: {forma}. Today's matches: {resumo}")
    if len(t) < 40:
        raise RuntimeError("roteiro vazio")
    return t + " No text, no logos, no real people."


def pedido_video():
    return ("Animate this image into a seamless vertical 9:16 video of about 8 seconds. Slow cinematic camera push-in. "
            "Stadium floodlights flicker and sweep, light haze drifts, the crowd in the stands waves and jumps, the "
            "soccer ball spins slowly with a soft glow, the generic players move subtly. Keep the composition and colors "
            "of the image and keep the central area dark and clean. Absolutely NO text, letters, numbers, logos, "
            "crests or watermarks, and no real or recognizable people. "
            "Audio: excited stadium crowd ambience and cheers, no dialogue, no narration, no music with lyrics.")


def _quadro_inicial(dia, cfg, pasta, formato):
    """Primeiro quadro para a IA (a arte do dia, cortada no formato) ou None."""
    arte = os.path.join(cfg.get("_pasta_arte") or pasta, f"{dia.isoformat()}-arte.png")
    if not os.path.exists(arte):
        return None
    im = Image.open(arte).convert("RGB")
    if formato == "horizontal":
        im = _cortar(im, 1280, 720)
    else:
        im = im.resize((720, 1280), Image.LANCZOS)
    caminho = os.path.join(pasta, f"{dia.isoformat()}-arte-{formato}-720.png")
    im.save(caminho, optimize=True)
    return open(caminho, "rb").read()


def _cortar(im, w, h, foco=0.45):
    """Recorta/escala para w x h sem distorcer (foco = altura do centro do recorte, 0 topo · 1 base)."""
    esc = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * esc) + 1, int(im.height * esc) + 1), Image.LANCZOS)
    x = (im.width - w) // 2
    y = int(max(0, min(im.height - h, im.height * foco - h / 2)))
    return im.crop((x, y, x + w, y + h))


def fundo_video(dia, destaque, pasta, cfg, info, formato="vertical"):
    """Caminho do MP4 de fundo do dia (gera uma vez por dia e formato) ou None (motivo em info['aviso_video'])."""
    sufixo = "" if formato == "vertical" else "-h"
    cache = os.path.join(pasta, f"{dia.isoformat()}-fundo{sufixo}.mp4")
    if os.path.exists(cache) and os.path.getsize(cache) > 10000:
        info.setdefault("video_fundo", "vídeo de IA do dia (já gerado)")
        return cache
    limite = float(cfg.get("video_limite") or 0)
    custo = CUSTO_SEG * SEG_IA
    if limite and gasto_mes(pasta) + custo > limite:
        info["aviso_video"] = f"limite de US$ {limite:.0f}/mês do vídeo com IA atingido; saiu o vídeo animado"
        return None
    provedor = cfg.get("video_provedor") or "gemini"
    imagem = _quadro_inicial(dia, cfg, pasta, formato) if provedor == "gemini" else None
    texto = pedido_video()
    if cfg.get("roteiro_claude"):
        try:
            texto = roteiro_claude(cfg.get("_jogos") or [destaque or {}], formato)
            info["video_roteiro"] = "Claude"
        except Exception as e:  # noqa: BLE001
            info["video_roteiro"] = f"padrão (Claude indisponível: {type(e).__name__})"
    if formato == "horizontal":
        texto = texto.replace("vertical 9:16", "horizontal 16:9 widescreen")
    if not imagem and not info.get("video_roteiro") == "Claude":
        import jogos_arte
        texto = jogos_arte.pedido(destaque or {}) + " " + texto.replace("Animate this image into", "Create")
        if formato == "horizontal":
            texto = texto.replace("Vertical 9:16", "Horizontal 16:9")
    prop = "16:9" if formato == "horizontal" else "9:16"
    try:
        if provedor == "gateway":
            mp4 = gateway_video(texto, prop, cfg.get("video_modelo_gateway") or os.environ.get("JARVIS_VIDEO_GATEWAY_MODELO", ""))
        else:
            mp4 = omni(texto, imagem, pasta, prop)
    except Exception as e:  # noqa: BLE001
        info["aviso_video"] = f"vídeo com IA indisponível ({type(e).__name__}: {str(e)[:200]}); saiu o vídeo animado"
        return None
    _somar_gasto(pasta, custo)
    open(cache, "wb").write(mp4)
    info["video_fundo"] = (f"gateway ({cfg.get('video_modelo_gateway')})" if provedor == "gateway" else f"Gemini ({MODELO})") \
        + (" · roteiro do Claude" if info.get("video_roteiro") == "Claude" else "")
    return cache


# ------------------------------------------------------------------ animação por cima
FORMATOS = {"vertical": (L, A), "horizontal": (1920, 1080)}


def _suave(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _colar(base, peca, x, y, alfa=1.0):
    """Cola uma peça RGBA em (x, y), cortando o que sair da tela, com transparência extra opcional."""
    if alfa <= 0.01:
        return
    x, y = int(round(x)), int(round(y))
    esq, cima = max(0, -x), max(0, -y)
    dir_, baixo = min(peca.width, base.width - x), min(peca.height, base.height - y)
    if dir_ <= esq or baixo <= cima:
        return
    p = peca.crop((esq, cima, dir_, baixo)) if (esq or cima or dir_ < peca.width or baixo < peca.height) else peca
    if alfa < 0.99:
        p = p.copy()
        p.putalpha(p.getchannel("A").point(lambda v: int(v * alfa)))
    base.alpha_composite(p, (x + esq, y + cima))


def _pecas(pagina):
    """Divide a página transparente (vertical) em faixas: cabeçalho, um cartão por jogo, rodapé."""
    cab = pagina.crop((0, 0, L, ji.CARTAO_Y - 8))
    rod = pagina.crop((0, A - 210, L, A))
    cartoes = []
    for k in range(ji.POR_PAGINA_ARTE):
        y = ji.CARTAO_Y + k * ji.CARTAO_PASSO
        faixa = pagina.crop((0, y - 6, L, y + ji.CARTAO_H + 6))
        if faixa.getbbox():
            cartoes.append((faixa, y - 6))
    return cab, cartoes, rod


def _escala(im, f):
    return im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))), Image.LANCZOS)


def _escurecer_h(w, h):
    from PIL import ImageDraw
    camada = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    for y in range(h):
        if y < 280:
            alfa = 215 - (215 - 120) * y / 280
        elif y > h - 140:
            alfa = 120 + (220 - 120) * (y - (h - 140)) / 140
        else:
            alfa = 120
        d.line([(0, y), (w, y)], fill=(4, 8, 16, int(alfa)))
    return camada


def _paginas(jogos, dia, cfg, pasta, formato):
    """[(itens, segundos)] com itens = (peça, x, y, movimento, início, duração)."""
    saida = []
    if formato == "vertical":
        grupos = [jogos[i:i + ji.POR_PAGINA_ARTE] for i in range(0, len(jogos), ji.POR_PAGINA_ARTE)]
        for i, g in enumerate(grupos, 1):
            cab, cartoes, rod = _pecas(ji._pagina_arte(None, g, dia, {**cfg, "_pasta": pasta}, i, len(grupos)))
            itens = [(cab, 0, 0, "cima", 0, 0.5)]
            itens += [(p, 0, y, "esq" if k % 2 == 0 else "dir", 0.35 + 0.3 * k, 0.55) for k, (p, y) in enumerate(cartoes)]
            itens.append((rod, 0, A - 210, "baixo", 0.35 + 0.3 * len(cartoes), 0.6))
            saida.append((itens, max(6.5, 0.35 + 0.3 * len(cartoes) + 0.6 + 4.5)))
        return saida
    # horizontal (TV): cabeçalho no alto, cartões em 2 colunas (até 6 por tela), rodapé embaixo
    W, H = FORMATOS["horizontal"]
    por = 6
    grupos = [jogos[i:i + por] for i in range(0, len(jogos), por)]
    for i, g in enumerate(grupos, 1):
        cfg_p = {**cfg, "_pasta": pasta}
        camada = ji._pagina_arte(None, g[:4], dia, cfg_p, i, len(grupos))
        cab, cartoes, rod = _pecas(camada)
        if len(g) > 4:
            cartoes += _pecas(ji._pagina_arte(None, g[4:], dia, cfg_p, i, len(grupos)))[1]
        cab = _escala(cab, 0.6)
        rod = _escala(rod, 0.5)
        cartoes = [_escala(p.crop((40, 0, L - 40, p.height)), 0.88) for p, _ in cartoes]
        cw, ch = cartoes[0].size if cartoes else (880, 236)
        linhas = (len(cartoes) + 1) // 2
        topo, base = 250, H - 108
        passo = ch + 8
        y0 = topo + max(0, (base - topo - linhas * passo) // 2)
        itens = [(cab, (W - cab.width) // 2, 0, "cima", 0, 0.5)]
        for k, p in enumerate(cartoes):
            col, lin = k % 2, k // 2
            sozinho = col == 0 and k == len(cartoes) - 1
            x = (W - cw) // 2 if sozinho else (W // 2 - 20 - cw if col == 0 else W // 2 + 20)
            itens.append((p, x, y0 + lin * passo, "esq" if col == 0 else "dir", 0.35 + 0.22 * k, 0.55))
        itens.append((rod, (W - rod.width) // 2, H - rod.height, "baixo", 0.35 + 0.22 * len(cartoes), 0.6))
        saida.append((itens, max(6.5, 0.35 + 0.22 * len(cartoes) + 0.6 + 4.5)))
    return saida


def _compor(itens, t, seg, ultima, fundo, W):
    base = fundo.copy()
    saindo = not ultima and t > seg - 0.35
    sai = 1 - _suave((t - (seg - 0.35)) / 0.35) if saindo else 1.0
    for peca, x, y, mov, t0, dur in itens:
        e = _suave((t - t0) / dur)
        if mov == "cima":
            _colar(base, peca, x, y - 90 * (1 - e), e * sai)
        elif mov == "baixo":
            _colar(base, peca, x, y + 40 * (1 - e), e * sai)
        else:
            _colar(base, peca, x + (-1 if mov == "esq" else 1) * W * (1 - e), y, min(1.0, e * 1.5) * sai)
    return base


def _quadros(paginas, formato):
    W, H = FORMATOS[formato]
    fundo = ji.escurecer() if formato == "vertical" else _escurecer_h(W, H)
    for n, (itens, seg) in enumerate(paginas):
        ultima = n == len(paginas) - 1
        fim_anim = max(t0 + d for _, _, _, _, t0, d in itens)
        anterior = None
        for f in range(int(seg * FPS)):
            t = f / FPS
            if anterior is not None and fim_anim < t and (ultima or t <= seg - 0.35):
                yield anterior
                continue
            anterior = _compor(itens, t, seg, ultima, fundo, W).tobytes()
            yield anterior


def _tem_audio(caminho):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                            "-of", "csv=p=0", caminho], capture_output=True, text=True, timeout=30)
        return bool(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def musica(pasta):
    cam = os.path.join(pasta, "musica.m4a")
    return cam if os.path.exists(cam) else None


def salvar_musica(pasta, dados):
    """Recebe o arquivo de áudio (mp3, m4a, wav, ogg…), confere e guarda como musica.m4a (até 5 min)."""
    if len(dados) > 25 * 1024 * 1024:
        raise ValueError("arquivo grande demais (máximo 25 MB)")
    os.makedirs(pasta, exist_ok=True)
    bruto = os.path.join(pasta, "musica-envio.tmp")
    open(bruto, "wb").write(dados)
    destino = os.path.join(pasta, "musica.m4a")
    try:
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", bruto, "-vn", "-t", "300", "-ac", "2",
                            "-c:a", "aac", "-b:a", "160k", destino + ".tmp.m4a"], capture_output=True, text=True, timeout=180)
        if r.returncode != 0 or not _tem_audio(destino + ".tmp.m4a"):
            raise ValueError("não reconheci esse arquivo como áudio (use mp3, m4a, wav ou ogg)")
        os.replace(destino + ".tmp.m4a", destino)
    finally:
        for c in (bruto, destino + ".tmp.m4a"):
            try:
                os.remove(c)
            except OSError:
                pass
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", destino],
                       capture_output=True, text=True, timeout=30)
    try:
        return round(float(r.stdout.strip()), 1)
    except ValueError:
        return 0.0


def apagar_musica(pasta):
    try:
        os.remove(os.path.join(pasta, "musica.m4a"))
    except OSError:
        pass


def _fundo_parado(dia, cfg, pasta, formato):
    W, H = FORMATOS[formato]
    arte = os.path.join(cfg.get("_pasta_arte") or pasta, f"{dia.isoformat()}-arte.png")
    origem = Image.open(arte).convert("RGB") if os.path.exists(arte) else ji._fundo().convert("RGB")
    caminho = os.path.join(pasta, f"{dia.isoformat()}-parado-{formato}.png")
    (_cortar(origem, W, H) if (W, H) != origem.size else origem).save(caminho)
    return caminho, ("arte do dia com zoom" if os.path.exists(arte) else "fundo simples com zoom")


def montar(jogos, dia, cfg, pasta, info=None, formato="vertical"):
    """Gera o MP4 do dia no formato pedido (vertical 1080x1920 ou horizontal 1920x1080). Devolve o caminho."""
    info = {} if info is None else info
    if not jogos:
        return None
    os.makedirs(pasta, exist_ok=True)
    W, H = FORMATOS[formato]
    fundo = fundo_video(dia, jogos[0], pasta, {**cfg, "_jogos": jogos}, info, formato) if cfg.get("video") == "ia" else None
    still = None
    if not fundo:
        still, origem = _fundo_parado(dia, cfg, pasta, formato)
        info.setdefault("video_fundo", origem)
    paginas = _paginas(jogos, dia, cfg, pasta, formato)
    total = sum(seg for _, seg in paginas)
    nome = "jogos" if formato == "vertical" else "jogos-tv"
    saida = os.path.join(pasta, f"{dia.isoformat()}-{nome}.mp4")
    tmp = saida + ".tmp.mp4"
    if fundo:
        entradas = ["-stream_loop", "-1", "-i", fundo]
        filtro = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1[bg]"
    else:
        entradas = ["-loop", "1", "-framerate", str(FPS), "-i", still]
        n = int(total * FPS)
        filtro = (f"[0:v]scale={int(W * 1.5)}:{int(H * 1.5)},zoompan=z='1+0.08*on/{n}':x='iw/2-(iw/zoom/2)':"
                  f"y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},setsar=1[bg]")
    entradas += ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-framerate", str(FPS), "-i", "-"]
    filtro += ";[bg][1:v]overlay=0:0:format=auto,format=yuv420p[v]"
    som_fundo = bool(fundo) and _tem_audio(fundo)
    trilha = musica(pasta) if cfg.get("musica", True) else None
    vol = max(0, min(100, int(cfg.get("musica_volume", 70)))) / 100
    fade = f"afade=t=in:d=0.8,afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5"
    audio = []
    if trilha:
        entradas += ["-stream_loop", "-1", "-i", trilha]
        if som_fundo:
            filtro += (f";[0:a]volume=0.45[a0];[2:a]volume={vol:.2f}[a2];"
                       f"[a0][a2]amix=inputs=2:duration=longest:normalize=0,{fade}[a]")
        else:
            filtro += f";[2:a]volume={vol:.2f},{fade}[a]"
        audio = ["-map", "[a]"]
    elif som_fundo:
        filtro += f";[0:a]{fade}[a]"
        audio = ["-map", "[a]"]
    if audio:
        audio += ["-c:a", "aac", "-b:a", "160k"]
        info["video_som"] = "música + torcida" if trilha and som_fundo else ("música" if trilha else "torcida")
    cmd = (["ffmpeg", "-y", "-loglevel", "error"] + entradas + ["-filter_complex", filtro, "-map", "[v]"] + audio +
           ["-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart", tmp])
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for q in _quadros(paginas, formato):
            proc.stdin.write(q)
        proc.stdin.close()
    except BrokenPipeError:
        pass
    erro = proc.stderr.read().decode(errors="replace")
    if proc.wait() != 0 or not os.path.exists(tmp):
        raise RuntimeError("ffmpeg falhou: " + erro[-300:])
    os.replace(tmp, saida)
    if formato == "horizontal":  # imagem parada para a TV (último quadro de cada tela)
        parado = Image.open(still or _fundo_parado(dia, cfg, pasta, formato)[0]).convert("RGBA")
        fundo_esc = Image.alpha_composite(parado, _escurecer_h(W, H))
        info["imagens_tv"] = []
        for i, (itens, seg) in enumerate(paginas, 1):
            cam = os.path.join(pasta, f"{dia.isoformat()}-jogos-tv-{i}.png")
            _compor(itens, seg, seg, True, fundo_esc, W).convert("RGB").save(cam, optimize=True)
            info["imagens_tv"].append(cam)
    info[f"video_seg_{formato}"] = round(total, 1)
    return saida
