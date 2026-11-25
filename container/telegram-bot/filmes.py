"""Vídeo de filme ou série com os dados do TMDB (e cortes do trailer, se você enviar o arquivo).

- Token do TMDB (v4 "Read Access Token" ou a chave v3) fica em /segredos/tmdb.json (600, só no painel; o painel
  mostra mascarado).
- Busca em português, detalhes com imagens, cartaz, logo, gêneros, nota, duração/temporadas, elenco e o link do trailer.
- O Claude (no seu gateway) escreve uma chamada curta e um resumo SEM spoilers; sem ele, usa a sinopse.
- Vídeo vertical (Status/Reels) e horizontal (TV): imagens do filme com movimento, título, informações e chamada
  animados por cima, cartão final com o cartaz. Com o trailer enviado por você: cortes automáticos nas trocas de cena,
  com o áudio do trailer. O Jarvis não baixa trailers do YouTube.
- Crédito do TMDB no rodapé (exigência dos termos da API).
"""
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFilter

import jarvis_core as core
import jogos_imagem as ji
import jogos_video as jv

SEGREDO = os.environ.get("FILMES_TMDB_CONFIG", "/segredos/tmdb.json")
DIR = os.path.join(core.CONFIG_DIR, "filmes")
API = os.environ.get("TMDB_URL", "https://api.themoviedb.org/3").rstrip("/")
IMG = os.environ.get("TMDB_IMG", "https://image.tmdb.org/t/p").rstrip("/")
UA = "Jarvis/1.37 (TMDB)"
FPS = 30
CREDITO = "Dados e imagens: TMDB. Este produto usa a API do TMDB, mas não é endossado nem certificado pelo TMDB."
PADRAO = {"marca": "", "chamada": "Disponível agora", "formatos": ["vertical", "horizontal"], "frase_claude": True,
          "onde_assistir": False}
TRABALHO = {"rodando": False, "etapa": "", "erro": "", "resultado": None, "titulo": ""}
_trava = threading.Lock()


# ------------------------------------------------------------------ token e configuração
def _ler_segredo():
    try:
        return json.load(open(SEGREDO, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def token():
    return (_ler_segredo().get("token") or os.environ.get("TMDB_TOKEN", "")).strip()


def mascarado():
    t = token()
    return (t[:4] + "…" + t[-4:]) if len(t) > 12 else ("definido" if t else "")


def salvar_token(t):
    t = (t or "").strip()
    if t and not re.fullmatch(r"[A-Za-z0-9._\-]{20,600}", t):
        raise ValueError("token do TMDB em formato inesperado")
    os.makedirs(os.path.dirname(SEGREDO), exist_ok=True)
    tmp = SEGREDO + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
        json.dump({"token": t}, f)
    os.replace(tmp, SEGREDO)


def config():
    try:
        return {**PADRAO, **json.load(open(os.path.join(DIR, "config.json"), encoding="utf-8"))}
    except (OSError, ValueError):
        return dict(PADRAO)


def salvar_config(novo):
    c = config()
    for k in ("marca", "chamada"):
        if k in novo:
            c[k] = str(novo[k] or "").strip()[:60]
    if isinstance(novo.get("formatos"), list):
        c["formatos"] = [f for f in ("vertical", "horizontal") if f in novo["formatos"]] or ["vertical"]
    for k in ("frase_claude", "onde_assistir"):
        if k in novo:
            c[k] = bool(novo[k])
    os.makedirs(DIR, exist_ok=True)
    json.dump(c, open(os.path.join(DIR, "config.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return c


# ------------------------------------------------------------------ TMDB
def _get(caminho, **params):
    t = token()
    if not t:
        raise RuntimeError("cadastre o token do TMDB no painel (🎬 Filmes)")
    cab = {"User-Agent": UA, "Accept": "application/json"}
    if "." in t and len(t) > 60:  # token v4 (JWT)
        cab["Authorization"] = f"Bearer {t}"
    else:
        params["api_key"] = t
    url = f"{API}{caminho}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=30) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise RuntimeError("o TMDB recusou o token (confira no painel 🎬 Filmes)") from None
        raise RuntimeError(f"TMDB respondeu HTTP {e.code}") from None


def _ano(d):
    return (d.get("release_date") or d.get("first_air_date") or "")[:4]


def buscar(q):
    j = _get("/search/multi", query=q, language="pt-BR", include_adult="false")
    res = []
    for d in j.get("results", []):
        if d.get("media_type") not in ("movie", "tv"):
            continue
        res.append({"id": d["id"], "tipo": d["media_type"], "titulo": d.get("title") or d.get("name") or "",
                    "original": d.get("original_title") or d.get("original_name") or "", "ano": _ano(d),
                    "nota": round(float(d.get("vote_average") or 0), 1), "popularidade": d.get("popularity") or 0,
                    "poster": f"{IMG}/w185{d['poster_path']}" if d.get("poster_path") else ""})
    return res[:10]


def melhor(q):
    """Escolhe o resultado mais provável para um nome (o Telegram não mostra lista)."""
    ano = re.search(r"\b(19|20)\d{2}\b", q)
    nome = re.sub(r"\b(19|20)\d{2}\b", "", q).strip()
    res = buscar(nome)
    if ano:
        res = [r for r in res if r["ano"] == ano.group(0)] or res
    if not res:
        return None, []
    exatos = [r for r in res if r["titulo"].lower() == nome.lower() or r["original"].lower() == nome.lower()]
    escolhido = max(exatos or res, key=lambda r: r["popularidade"])
    return escolhido, [r for r in res if r is not escolhido][:3]


def detalhes(tipo, id_):
    d = _get(f"/{tipo}/{int(id_)}", language="pt-BR",
             append_to_response="videos,images,credits,watch/providers",
             include_image_language="pt,en,null", include_video_language="pt,en")
    sinopse = d.get("overview") or ""
    if not sinopse:  # sem tradução: pega em inglês
        sinopse = _get(f"/{tipo}/{int(id_)}", language="en-US").get("overview", "")
    imgs = d.get("images") or {}
    fundos = sorted(imgs.get("backdrops") or [], key=lambda i: (i.get("iso_639_1") is not None, -(i.get("vote_average") or 0)))
    logos = [l for l in imgs.get("logos") or [] if l.get("iso_639_1") in ("pt", "en", None)]
    logos.sort(key=lambda l: (l.get("iso_639_1") != "pt", l.get("iso_639_1") != "en"))
    trailer = next((v for v in (d.get("videos") or {}).get("results", [])
                    if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser")), None)
    equipe = (d.get("credits") or {}).get("crew") or []
    criador = ", ".join(c["name"] for c in d.get("created_by") or [])[:60] or \
        next((c["name"] for c in equipe if c.get("job") == "Director"), "")
    br = ((d.get("watch/providers") or {}).get("results") or {}).get("BR") or {}
    return {
        "id": d["id"], "tipo": tipo, "titulo": d.get("title") or d.get("name") or "", "ano": _ano(d),
        "original": d.get("original_title") or d.get("original_name") or "",
        "generos": [g["name"] for g in d.get("genres") or []][:3], "nota": round(float(d.get("vote_average") or 0), 1),
        "duracao": d.get("runtime") or 0, "temporadas": d.get("number_of_seasons") or 0,
        "sinopse": sinopse, "frase": d.get("tagline") or "",
        "elenco": [c["name"] for c in ((d.get("credits") or {}).get("cast") or [])[:3]], "criador": criador,
        "fundos": [f"{IMG}/original{f['file_path']}" for f in fundos[:6]],
        "poster": f"{IMG}/w780{d['poster_path']}" if d.get("poster_path") else "",
        "logo": f"{IMG}/w500{logos[0]['file_path']}" if logos else "",
        "trailer": f"https://www.youtube.com/watch?v={trailer['key']}" if trailer else "",
        "onde": [p["provider_name"] for p in (br.get("flatrate") or [])][:4],
    }


def _baixar_img(url, destino):
    if os.path.exists(destino) and os.path.getsize(destino) > 1000:
        return destino
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        open(destino, "wb").write(r.read())
    return destino


# ------------------------------------------------------------------ textos
def textos(d, cfg):
    """Chamada curta + resumo sem spoiler. Claude no gateway; sem ele, a sinopse cortada."""
    resumo = _cortar_frase(d["sinopse"], 230)
    chamada = d["frase"][:90]
    if cfg.get("frase_claude"):
        try:
            sistema = ("Você escreve textos curtos para vídeos de divulgação de filmes e séries, em português do Brasil. "
                       "Responda SÓ um JSON: {\"chamada\": \"frase de impacto, até 70 caracteres\", "
                       "\"resumo\": \"até 220 caracteres, sem spoilers\"}. Não invente fatos fora da sinopse.")
            t = jv.claude_texto(sistema, json.dumps({k: d[k] for k in ("titulo", "ano", "generos", "sinopse", "frase")},
                                                    ensure_ascii=False), max_tokens=300)
            j = json.loads(re.search(r"\{.*\}", t, re.S).group(0))
            chamada = str(j.get("chamada") or chamada)[:80]
            resumo = _cortar_frase(str(j.get("resumo") or resumo), 230)
        except Exception:  # noqa: BLE001
            pass
    return chamada, resumo


def _cortar_frase(t, n):
    t = re.sub(r"\s+", " ", t or "").strip()
    if len(t) <= n:
        return t
    corte = t[:n].rsplit(". ", 1)[0]
    return (corte if len(corte) > n * 0.5 else t[:n].rsplit(" ", 1)[0]) + "…"


def meta(d):
    partes = [d["ano"]] + d["generos"][:2]
    if d["tipo"] == "movie" and d["duracao"]:
        partes.append(f"{d['duracao'] // 60}h{d['duracao'] % 60:02d}" if d["duracao"] >= 60 else f"{d['duracao']} min")
    if d["tipo"] == "tv" and d["temporadas"]:
        partes.append(f"{d['temporadas']} temporada{'s' if d['temporadas'] > 1 else ''}")
    return " · ".join(p for p in partes if p)


# ------------------------------------------------------------------ fundo: imagens em movimento ou cortes do trailer
def _fundo_imagens(fotos, W, H, segundos, saida):
    """Ken Burns com transição suave entre as imagens (PIL → ffmpeg)."""
    ims = []
    for f in fotos:
        im = Image.open(f).convert("RGB")
        esc = max(W / im.width, H / im.height) * 1.14
        ims.append(im.resize((int(im.width * esc) + 2, int(im.height * esc) + 2), Image.LANCZOS))
    if not ims:
        ims = [Image.new("RGB", (int(W * 1.14), int(H * 1.14)), (10, 14, 24))]
    total = int(segundos * FPS)
    por = total / len(ims)
    trans = int(0.6 * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-framerate", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-pix_fmt", "yuv420p", saida]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def quadro(i, f):
        im = ims[i % len(ims)]
        p = min(1.0, f / max(1, por + trans))
        z = 1 + 0.12 * (p if i % 2 == 0 else 1 - p)
        cw, ch = int(W * 1.14 / z), int(H * 1.14 / z)
        sobra_x, sobra_y = im.width - cw, im.height - ch
        x = int(sobra_x * (p if i % 2 else 1 - p))
        y = int(sobra_y * 0.45)
        return im.crop((x, y, x + cw, y + ch)).resize((W, H), Image.BILINEAR)
    try:
        for n in range(total):
            i = int(n // por)
            f = n - i * por
            q = quadro(i, f)
            if f > por - trans and i + 1 < len(ims):  # transição para a próxima imagem
                q = Image.blend(q, quadro(i + 1, f - por), (f - (por - trans)) / trans)
            proc.stdin.write(q.tobytes())
        proc.stdin.close()
    except BrokenPipeError:
        pass
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg (imagens): " + proc.stderr.read().decode(errors="replace")[-200:])
    return saida


def cenas(trailer):
    """Instantes (s) de troca de cena do trailer."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", trailer, "-vf", "select='gt(scene,0.32)',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    return [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def duracao(arq):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", arq],
                       capture_output=True, text=True, timeout=60)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def escolher_cortes(trocas, total, n=6, seg=2.3):
    """Cortes espalhados entre 12% e 88% do trailer (pula logos do começo e a cartela final)."""
    ini, fim = total * 0.12, total * 0.88 - seg
    candidatos = [t for t in trocas if ini <= t <= fim] or [ini + (fim - ini) * k / max(1, n - 1) for k in range(n)]
    escolhidos = []
    for k in range(n):
        alvo = ini + (fim - ini) * (k + 0.5) / n
        c = min(candidatos, key=lambda t: abs(t - alvo))
        if all(abs(c - e) >= seg + 0.3 for e in escolhidos):
            escolhidos.append(c)
    return sorted(escolhidos)


def _fundo_trailer(trailer, W, H, saida):
    total = duracao(trailer)
    if total < 8:
        raise RuntimeError("trailer curto demais ou inválido")
    cortes = escolher_cortes(cenas(trailer), total)
    seg = 2.3
    filtros, rot = [], []
    for k, t in enumerate(cortes):
        filtros.append(f"[0:v]trim=start={t + 0.08:.2f}:duration={seg},setpts=PTS-STARTPTS,"
                       f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1[v{k}]")
        filtros.append(f"[0:a]atrim=start={t + 0.08:.2f}:duration={seg},asetpts=PTS-STARTPTS,"
                       f"afade=t=in:d=0.08,afade=t=out:st={seg - 0.15:.2f}:d=0.15[a{k}]")
        rot.append(f"[v{k}][a{k}]")
    filtros.append("".join(rot) + f"concat=n={len(cortes)}:v=1:a=1[v][a]")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", trailer, "-filter_complex", ";".join(filtros),
                        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", saida], capture_output=True, text=True, timeout=900)
    if r.returncode != 0:  # trailer sem áudio: só imagem
        filtros = [f for f in filtros if not f.startswith("[0:a]")]
        filtros[-1] = "".join(f"[v{k}]" for k in range(len(cortes))) + f"concat=n={len(cortes)}:v=1:a=0[v]"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", trailer, "-filter_complex", ";".join(filtros),
                            "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
                            saida], capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            raise RuntimeError("não consegui cortar o trailer: " + r.stderr[-200:])
    return saida, len(cortes) * seg


def salvar_trailer(tipo, id_, dados):
    if len(dados) > 400 * 1024 * 1024:
        raise ValueError("arquivo grande demais (máximo 400 MB)")
    pasta = os.path.join(DIR, "trailers")
    os.makedirs(pasta, exist_ok=True)
    destino = os.path.join(pasta, f"{tipo}-{int(id_)}.mp4")
    open(destino + ".tmp", "wb").write(dados)
    if duracao(destino + ".tmp") < 8:
        os.remove(destino + ".tmp")
        raise ValueError("não reconheci esse arquivo como vídeo (use mp4, mov ou mkv)")
    os.replace(destino + ".tmp", destino)
    return destino


BLOQUEADOS = re.compile(r"(^|\.)(youtube\.com|youtu\.be|youtube-nocookie\.com|googlevideo\.com|ytimg\.com)$", re.I)


def link_direto(url):
    """Ajusta links de compartilhamento (Drive, Dropbox) para o download do arquivo. Recusa o YouTube."""
    p = urllib.parse.urlparse((url or "").strip())
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("cole um link http(s) do arquivo de vídeo")
    if BLOQUEADOS.search(p.hostname):
        raise ValueError("links do YouTube não: os termos do YouTube proíbem baixar os vídeos de lá. Use o arquivo do "
                         "trailer (área de imprensa da distribuidora, Drive, Dropbox) ou envie o arquivo no painel.")
    m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=)([\w-]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&confirm=t&id={m.group(1)}"
    if "dropbox.com" in p.hostname:
        return re.sub(r"([?&])dl=0", r"\1dl=1", url) if "dl=" in url else url + ("&" if "?" in url else "?") + "dl=1"
    return url


def baixar_trailer(tipo, id_, url, limite=400 * 1024 * 1024):
    """Baixa o arquivo do link (até 400 MB), confere se é vídeo e guarda como o trailer do título."""
    direto = link_direto(url)
    req = urllib.request.Request(direto, headers={"User-Agent": "Mozilla/5.0 (Jarvis)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        tipo_c = r.headers.get("Content-Type", "")
        if "text/html" in tipo_c:
            raise ValueError("o link abre uma página, não o arquivo. Use o link de download do arquivo "
                             "(no Drive: compartilhar → qualquer pessoa com o link).")
        partes, total = [], 0
        while True:
            bloco = r.read(1024 * 1024)
            if not bloco:
                break
            total += len(bloco)
            if total > limite:
                raise ValueError("arquivo grande demais (máximo 400 MB)")
            partes.append(bloco)
    return salvar_trailer(tipo, id_, b"".join(partes))


def trailer_de(tipo, id_):
    p = os.path.join(DIR, "trailers", f"{tipo}-{int(id_)}.mp4")
    return p if os.path.exists(p) else None


# ------------------------------------------------------------------ camada animada
def _f(nome, tam):
    return ji._fonte(nome, tam)


def _quebrar(d, texto, fonte, largura, max_linhas):
    linhas, atual = [], ""
    for p in texto.split():
        t = (atual + " " + p).strip()
        if d.textlength(t, font=fonte) <= largura:
            atual = t
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        linhas[-1] = linhas[-1].rstrip(".,;") + "…"
    return linhas


def _pecas(d, cfg, W, H, logo, poster, chamada, resumo, fundo_final=None):
    """Peças RGBA (imagem, x, y, movimento, início) para o quadro principal e o cartão final."""
    vert = H > W
    larg = W - 120 if vert else int(W * 0.5)
    x0 = 60 if vert else 90
    pecas = []
    rascunho = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    y = int(H * 0.50) if vert else int(H * 0.30)
    tag = ("SÉRIE" if d["tipo"] == "tv" else "FILME") + (f" · {cfg['marca'].upper()}" if cfg.get("marca") else "")
    ft = _f("DejaVuSans-Bold.ttf", 30 if vert else 24)
    im = Image.new("RGBA", (int(rascunho.textlength(tag, font=ft)) + 44, 56 if vert else 46), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=im.height // 2, fill=(229, 9, 20, 235))
    ImageDraw.Draw(im).text((22, (im.height - ft.size) // 2 - 2), tag, font=ft, fill="white")
    pecas.append((im, x0, y - im.height - 24, "cima", 0.2))
    if logo:  # logo oficial do título, se o TMDB tiver
        lg = Image.open(logo).convert("RGBA")
        esc = min(larg / lg.width, (230 if vert else 170) / lg.height)
        lg = lg.resize((int(lg.width * esc), int(lg.height * esc)), Image.LANCZOS)
        pecas.append((lg, x0, y, "cima", 0.4))
        y += lg.height + 26
    else:
        fT = _f("BebasNeue-Regular.ttf", 118 if vert else 104)
        linhas = _quebrar(rascunho, d["titulo"].upper(), fT, larg, 3)
        im = Image.new("RGBA", (larg, len(linhas) * int(fT.size * 0.92) + 12), (0, 0, 0, 0))
        dd = ImageDraw.Draw(im)
        for i, l in enumerate(linhas):
            dd.text((0, i * int(fT.size * 0.92)), l, font=fT, fill="white", stroke_width=2, stroke_fill=(0, 0, 0, 160))
        pecas.append((im, x0, y, "cima", 0.4))
        y += im.height + 18
    fm = _f("DejaVuSans-Bold.ttf", 32 if vert else 26)
    m = meta(d)
    nota = f"★ {d['nota']:.1f}".replace(".", ",") if d["nota"] else ""
    im = Image.new("RGBA", (larg, fm.size + 16), (0, 0, 0, 0))
    dd = ImageDraw.Draw(im)
    xx = 0
    if nota:
        dd.text((0, 4), nota, font=fm, fill=(255, 205, 60))
        xx = int(dd.textlength(nota + "   ", font=fm))
    dd.text((xx, 4), m, font=fm, fill=(225, 232, 240))
    pecas.append((im, x0, y, "fade", 0.9))
    y += im.height + 22
    if chamada:
        fc = _f("DejaVuSans-Bold.ttf", 44 if vert else 34)
        linhas = _quebrar(rascunho, chamada, fc, larg, 2)
        im = Image.new("RGBA", (larg, len(linhas) * (fc.size + 10) + 6), (0, 0, 0, 0))
        dd = ImageDraw.Draw(im)
        for i, l in enumerate(linhas):
            dd.text((0, i * (fc.size + 10)), l, font=fc, fill=(255, 255, 255))
        pecas.append((im, x0, y, "esq", 1.4))
        y += im.height + 16
    if resumo:
        fr = _f("DejaVuSans.ttf", 32 if vert else 25)
        linhas = _quebrar(rascunho, resumo, fr, larg, 5 if vert else 4)
        im = Image.new("RGBA", (larg, len(linhas) * (fr.size + 12) + 6), (0, 0, 0, 0))
        dd = ImageDraw.Draw(im)
        for i, l in enumerate(linhas):
            dd.text((0, i * (fr.size + 12)), l, font=fr, fill=(214, 224, 235))
        pecas.append((im, x0, y, "fade", 2.0))
        y += im.height + 20
    extra = []
    if cfg.get("onde_assistir") and d.get("onde"):
        extra.append("Onde assistir: " + ", ".join(d["onde"]))
    if d.get("elenco"):
        extra.append("Com " + ", ".join(d["elenco"]))
    if extra:
        fe = _f("DejaVuSans.ttf", 26 if vert else 21)
        im = Image.new("RGBA", (larg, len(extra) * (fe.size + 10) + 6), (0, 0, 0, 0))
        dd = ImageDraw.Draw(im)
        for i, l in enumerate(extra):
            dd.text((0, i * (fe.size + 10)), _quebrar(dd, l, fe, larg, 1)[0], font=fe, fill=(160, 178, 196))
        pecas.append((im, x0, y, "fade", 2.4))
    # botão da chamada fixa (ex.: "Disponível agora")
    if cfg.get("chamada"):
        fb = _f("DejaVuSans-Bold.ttf", 36 if vert else 28)
        tb = cfg["chamada"].upper()
        im = Image.new("RGBA", (int(rascunho.textlength(tb, font=fb)) + 80, fb.size + 40), (0, 0, 0, 0))
        dd = ImageDraw.Draw(im)
        dd.rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=im.height // 2, fill=(255, 255, 255, 240))
        dd.text((40, 18), tb, font=fb, fill=(10, 12, 20))
        yb = H - im.height - (150 if vert else 110)
        pecas.append((im, x0, yb, "baixo", 3.0))
    # crédito do TMDB (pequeno, sempre)
    fcr = _f("DejaVuSans.ttf", 18 if vert else 15)
    cred = _quebrar(rascunho, CREDITO, fcr, W - 2 * x0, 2)
    im = Image.new("RGBA", (W - 2 * x0, len(cred) * (fcr.size + 6) + 6), (0, 0, 0, 0))
    for i, l in enumerate(cred):
        ImageDraw.Draw(im).text((0, 2 + i * (fcr.size + 6)), l, font=fcr, fill=(150, 160, 172))
    y_cred = H - im.height - (24 if vert else 16)
    pecas.append((im, x0, y_cred, "fade", 0.0))
    # cartão final: cartaz + título + chamada
    final = Image.new("RGBA", (W, H), (4, 6, 12, 255))
    if fundo_final:  # imagem do filme desfocada e escura atrás do cartaz
        fb_ = jv._cortar(Image.open(fundo_final).convert("RGB"), W, H).filter(ImageFilter.GaussianBlur(18)).convert("RGBA")
        final = Image.alpha_composite(fb_, Image.new("RGBA", (W, H), (4, 6, 12, 205)))
    df = ImageDraw.Draw(final)
    if poster:
        pt = Image.open(poster).convert("RGB")
        ph = int(H * (0.52 if vert else 0.68))
        pt = pt.resize((int(pt.width * ph / pt.height), ph), Image.LANCZOS)
        px = (W - pt.width) // 2 if vert else int(W * 0.12)
        py = int(H * 0.12) if vert else (H - ph) // 2
        final.paste(pt, (px, py))
        tx, ty, tw = (60, py + ph + 40, W - 120) if vert else (px + pt.width + 70, int(H * 0.32), W - px - pt.width - 160)
    else:
        tx, ty, tw = 60, int(H * 0.35), W - 120
    fT = _f("BebasNeue-Regular.ttf", 96 if vert else 90)
    for i, l in enumerate(_quebrar(df, d["titulo"].upper(), fT, tw, 2)):
        df.text((tx, ty + i * int(fT.size * 0.95)), l, font=fT, fill="white")
    ty += int(fT.size * 0.95) * min(2, len(_quebrar(df, d["titulo"].upper(), fT, tw, 2))) + 20
    df.text((tx, ty), meta(d), font=_f("DejaVuSans-Bold.ttf", 30 if vert else 26), fill=(225, 232, 240))
    if cfg.get("chamada"):
        fb = _f("DejaVuSans-Bold.ttf", 40 if vert else 32)
        tb = cfg["chamada"].upper()
        bw = int(df.textlength(tb, font=fb)) + 90
        by = ty + 70
        df.rounded_rectangle((tx, by, tx + bw, by + fb.size + 44), radius=(fb.size + 44) // 2, fill=(229, 9, 20, 245))
        df.text((tx + 45, by + 20), tb, font=fb, fill="white")
    if cfg.get("marca"):
        df.text((tx, by + fb.size + 90 if cfg.get("chamada") else ty + 80), cfg["marca"],
                font=_f("DejaVuSans-Bold.ttf", 30 if vert else 24), fill=(180, 190, 205))
    for i, l in enumerate(cred):
        df.text((x0, y_cred + 2 + i * (fcr.size + 6)), l, font=fcr, fill=(150, 160, 172))
    return pecas, final


def _escurecer(W, H):
    vert = H > W
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    if vert:
        for y in range(H):
            a = 40 if y < H * 0.38 else int(40 + 200 * min(1, (y - H * 0.38) / (H * 0.30)))
            d.line([(0, y), (W, y)], fill=(4, 6, 12, a))
    else:
        for x in range(W):
            a = int(225 - 185 * min(1, x / (W * 0.62)))
            d.line([(x, 0), (x, H)], fill=(4, 6, 12, a))
    return camada


def _quadros(pecas, final, W, H, total):
    base0 = _escurecer(W, H)
    ini_final = total - 3.4
    anterior = None
    for n in range(int(total * FPS)):
        t = n / FPS
        estavel = 3.6 < t < ini_final - 0.05
        if estavel and anterior is not None:
            yield anterior
            continue
        b = base0.copy()
        for im, x, y, mov, t0 in pecas:
            e = jv._suave((t - t0) / 0.6)
            if mov == "cima":
                jv._colar(b, im, x, y + 50 * (1 - e), e)
            elif mov == "baixo":
                jv._colar(b, im, x, y + 40 * (1 - e), e)
            elif mov == "esq":
                jv._colar(b, im, x - 120 * (1 - e), y, e)
            else:
                jv._colar(b, im, x, y, e)
        if t >= ini_final:
            jv._colar(b, final, 0, 0, jv._suave((t - ini_final) / 0.5))
        anterior = b.tobytes()
        yield anterior


# ------------------------------------------------------------------ gerar tudo
def gerar(tipo, id_, usar_trailer=True, cfg=None):
    cfg = cfg or config()
    TRABALHO.update(rodando=True, etapa="buscando os dados no TMDB", erro="", resultado=None)
    try:
        d = detalhes(tipo, id_)
        TRABALHO["titulo"] = f"{d['titulo']} ({d['ano']})"
        pasta = os.path.join(DIR, f"{tipo}-{d['id']}")
        os.makedirs(pasta, exist_ok=True)
        TRABALHO["etapa"] = "baixando imagens"
        fotos = []
        for i, u in enumerate(d["fundos"][:5]):
            try:
                fotos.append(_baixar_img(u, os.path.join(pasta, f"fundo{i}.jpg")))
            except Exception:  # noqa: BLE001
                pass
        poster = _baixar_img(d["poster"], os.path.join(pasta, "poster.jpg")) if d["poster"] else ""
        if not fotos and poster:
            fotos = [poster]
        logo = ""
        if d["logo"]:
            try:
                logo = _baixar_img(d["logo"], os.path.join(pasta, "logo.png"))
            except Exception:  # noqa: BLE001
                logo = ""
        TRABALHO["etapa"] = "escrevendo a chamada"
        chamada, resumo = textos(d, cfg)
        trailer = trailer_de(tipo, d["id"]) if usar_trailer else None
        musica = jv.musica(os.path.join(core.CONFIG_DIR, "jogos"))
        res = {"titulo": d["titulo"], "ano": d["ano"], "trailer_link": d["trailer"], "videos": {}, "imagens": {},
               "chamada": chamada, "resumo": resumo, "com_trailer": bool(trailer)}
        for formato in cfg.get("formatos") or ["vertical"]:
            W, H = jv.FORMATOS[formato]
            TRABALHO["etapa"] = f"montando o vídeo {formato}"
            fundo = os.path.join(pasta, f"fundo-{formato}.mp4")
            if trailer:
                fundo, dur = _fundo_trailer(trailer, W, H, fundo)
                total = dur + 3.4
                ext = os.path.join(pasta, f"fundo-{formato}-ext.mp4")  # estica o fim para o cartão final
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", fundo, "-vf",
                                f"tpad=stop_mode=clone:stop_duration=3.4", "-af", "apad", "-t", f"{total:.2f}",
                                "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
                                "-c:a", "aac", ext], capture_output=True, timeout=600)
                fundo = ext if os.path.exists(ext) else fundo
            else:
                total = 14.0
                _fundo_imagens(fotos, W, H, total, fundo)
            pecas, final = _pecas(d, cfg, W, H, logo, poster, chamada, resumo, fotos[0] if fotos else None)
            saida = os.path.join(pasta, f"{d['tipo']}-{d['id']}-{formato}.mp4")
            entradas = ["-i", fundo, "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-framerate", str(FPS),
                        "-i", "-"]
            filtro = f"[0:v]fps={FPS},setsar=1[bg];[bg][1:v]overlay=0:0:format=auto,format=yuv420p[v]"
            audio = []
            som_trailer = trailer and jv._tem_audio(fundo)
            fade = f"afade=t=in:d=0.5,afade=t=out:st={total - 1.5:.2f}:d=1.5"
            if som_trailer:
                filtro += f";[0:a]{fade}[a]"
                audio = ["-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
            elif musica:
                entradas += ["-stream_loop", "-1", "-i", musica]
                filtro += f";[2:a]volume=0.8,{fade}[a]"
                audio = ["-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
            proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error"] + entradas +
                                    ["-filter_complex", filtro, "-map", "[v]"] + audio +
                                    ["-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                                     "-movflags", "+faststart", saida], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                for q in _quadros(pecas, final, W, H, total):
                    proc.stdin.write(q)
                proc.stdin.close()
            except BrokenPipeError:
                pass
            if proc.wait() != 0:
                raise RuntimeError("ffmpeg: " + proc.stderr.read().decode(errors="replace")[-200:])
            res["videos"][formato] = saida
            img = os.path.join(pasta, f"{d['tipo']}-{d['id']}-{formato}.png")  # imagem parada (cartão final)
            final.convert("RGB").save(img, quality=90)
            res["imagens"][formato] = img
        res["legenda"] = (f"🎬 {d['titulo']} ({d['ano']})\n{meta(d)}" + (f" · ★ {d['nota']:.1f}".replace(".", ",") if d["nota"] else "")
                          + (f"\n\n{chamada}" if chamada else "") + (f"\n{resumo}" if resumo else "")
                          + (f"\n\n{cfg['chamada']}" if cfg.get("chamada") else "")
                          + (f"\nTrailer oficial: {d['trailer']}" if d["trailer"] else ""))
        json.dump(res, open(os.path.join(DIR, "ultimo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        TRABALHO.update(resultado=res, etapa="pronto")
        return res
    except Exception as e:  # noqa: BLE001
        TRABALHO.update(erro=f"{type(e).__name__}: {str(e)[:300]}", etapa="erro")
        raise
    finally:
        TRABALHO["rodando"] = False


def ultimo():
    try:
        return json.load(open(os.path.join(DIR, "ultimo.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return None


def mandar_telegram(res):
    import rotinas
    itens = [(res["videos"][f], "video", "") for f in ("vertical", "horizontal") if f in res["videos"]]
    itens += [(res["imagens"][f], "photo", "") for f in ("vertical", "horizontal") if f in res["imagens"]]
    if itens:
        itens[0] = (itens[0][0], itens[0][1], res.get("legenda", "")[:1000])
    rotinas.avisar_telegram_album(itens)


def gerar_fundo(tipo, id_, usar_trailer=True, avisar=True, link=None):
    if TRABALHO["rodando"]:
        raise RuntimeError("já estou gerando um vídeo de filme; aguarde")

    def rodar():
        try:
            if link:
                TRABALHO["etapa"] = "baixando o trailer do link"
                try:
                    baixar_trailer(tipo, id_, link)
                except (ValueError, OSError) as e:
                    if avisar:
                        import rotinas
                        rotinas.avisar_telegram(f"🎬 Não consegui usar o trailer do link ({str(e)[:200]}). "
                                                "Vou gerar com as imagens.")
            res = gerar(tipo, id_, usar_trailer)
            if avisar:
                mandar_telegram(res)
        except Exception as e:  # noqa: BLE001
            if avisar:
                import rotinas
                rotinas.avisar_telegram(f"🎬 Não consegui gerar o vídeo: {type(e).__name__}: {str(e)[:200]}")
    TRABALHO.update(rodando=True, etapa="começando", erro="", resultado=None)
    threading.Thread(target=rodar, daemon=True).start()
