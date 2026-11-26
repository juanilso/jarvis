"""Fundo do banner dos jogos gerado por IA (estádio, bola, jogadores GENÉRICOS nas cores dos times do jogo destaque).

Regras do que é pedido à IA: nada de jogadores reais (direito de imagem), nada de escudos/logos/marcas, nada de texto.
Provedores, nesta ordem (usa as chaves dos ajudantes): Gemini (modelo de imagem) → Cloudflare Workers AI (FLUX).
Sem chave ou se todos falharem: devolve None e o banner sai no estilo simples de sempre.
"""
import base64
import io
import json
import os
import re
import urllib.error
import urllib.request

from PIL import Image, ImageFilter

L, A = 1080, 1920
UA = "jarvis-jogos/1.0"

# cores aproximadas em português (para o pedido à IA entender as cores dos uniformes)
_CORES = [((0, 0, 0), "preto"), ((255, 255, 255), "branco"), ((200, 16, 46), "vermelho"), ((120, 20, 40), "grená"),
          ((0, 70, 160), "azul"), ((20, 30, 80), "azul-marinho"), ((110, 190, 240), "azul-celeste"),
          ((0, 130, 60), "verde"), ((0, 80, 40), "verde-escuro"), ((250, 210, 0), "amarelo"), ((240, 120, 0), "laranja"),
          ((120, 40, 150), "roxo"), ((128, 128, 128), "cinza"), ((180, 150, 80), "dourado")]


def nome_cor(hexa):
    try:
        h = str(hexa or "").lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, IndexError):
        return ""
    return min(_CORES, key=lambda c: sum((a - b) ** 2 for a, b in zip(c[0], (r, g, b))))[1]


# Uniforme completo (alusão: cores e padrão de camisa, calção e meião, sem escudo/patrocínio/marca).
# Chave: nome do time sem acento, minúsculo. Times fora da lista usam as cores da ESPN; para ficar idêntico,
# mande uma foto do uniforme no painel (⚽ Jogos → 👕 Uniformes de referência).
CAMISAS = {
    "flamengo": "red and black horizontal hoops shirt, white shorts, red and black hooped socks",
    "palmeiras": "solid green shirt with white collar and white sleeve trims, white shorts, green socks",
    "corinthians": "white shirt with black collar and black sleeve cuffs, black shorts, white socks",
    "sao paulo": "white shirt with a red and black horizontal band across the chest, white shorts, white socks",
    "santos": "plain white shirt with thin black trims, white shorts, white socks",
    "fluminense": "maroon, green and white vertical stripes shirt, white shorts, white socks",
    "botafogo": "black and white vertical stripes shirt, black shorts, grey socks",
    "vasco": "white shirt with a black diagonal sash from shoulder to waist, black shorts, white socks",
    "vasco da gama": "white shirt with a black diagonal sash from shoulder to waist, black shorts, white socks",
    "gremio": "sky blue, black and white vertical stripes shirt, black shorts, white socks",
    "internacional": "solid red shirt with white collar, white shorts, red socks",
    "atletico-mg": "black and white vertical stripes shirt, black shorts, white socks",
    "atletico mineiro": "black and white vertical stripes shirt, black shorts, white socks",
    "cruzeiro": "solid royal blue shirt with white trims, white shorts, blue socks",
    "bahia": "white shirt with blue and red side details, blue shorts, white socks",
    "fortaleza": "red, blue and white horizontal stripes shirt, blue shorts, white socks",
    "ceara": "black and white vertical stripes shirt, black shorts, white socks",
    "sport": "red and black horizontal hoops shirt, black shorts, black socks",
    "sport recife": "red and black horizontal hoops shirt, black shorts, black socks",
    "athletico-pr": "red and black horizontal hoops shirt, black shorts, black socks",
    "athletico paranaense": "red and black horizontal hoops shirt, black shorts, black socks",
    "vitoria": "red and black horizontal hoops shirt, white shorts, red socks",
    "coritiba": "white shirt with green collar and green trims, black shorts, white socks",
    "juventude": "green and white vertical stripes shirt, white shorts, white socks",
    "bragantino": "white shirt with red details, red shorts, white socks", "red bull bragantino": "white shirt with red details, red shorts, white socks",
    "rb bragantino": "white shirt with red details, red shorts, white socks",
    "mirassol": "yellow shirt with green trims, green shorts, yellow socks",
    "goias": "solid green shirt with white trims, white shorts, green socks",
    "america-mg": "green and black vertical stripes shirt, black shorts, green socks",
    "cuiaba": "yellow shirt with green trims, green shorts, yellow socks",
    "chapecoense": "solid green shirt with white trims, white shorts, green socks",
    "criciuma": "yellow, black and white vertical stripes shirt, black shorts, yellow socks",
    "remo": "solid navy blue shirt, white shorts, navy socks",
    "paysandu": "light blue and white vertical stripes shirt, light blue shorts, white socks",
    "avai": "blue and white vertical stripes shirt, white shorts, blue socks",
    "brasil": "canary yellow shirt with green collar, blue shorts, white socks",
    "brazil": "canary yellow shirt with green collar, blue shorts, white socks",
    "argentina": "sky blue and white vertical stripes shirt, black shorts, white socks",
    "uruguay": "sky blue shirt, black shorts, black socks", "uruguai": "sky blue shirt, black shorts, black socks",
    "real madrid": "plain all-white kit (white shirt, white shorts, white socks)",
    "barcelona": "blue and garnet (dark red) vertical stripes shirt, blue shorts, blue socks",
    "liverpool": "all-red kit (red shirt, red shorts, red socks)",
    "manchester city": "sky blue shirt, white shorts, sky blue socks",
    "manchester united": "red shirt with white collar, white shorts, black socks",
    "arsenal": "red shirt with white sleeves, white shorts, red and white socks",
    "chelsea": "royal blue shirt, royal blue shorts, white socks",
    "bayern munich": "red shirt with white details, red shorts, red socks", "bayern munique": "red shirt with white details, red shorts, red socks",
    "juventus": "black and white vertical stripes shirt, black shorts, black socks",
    "inter milan": "black and blue vertical stripes shirt, black shorts, black socks", "internazionale": "black and blue vertical stripes shirt, black shorts, black socks",
    "ac milan": "red and black vertical stripes shirt, white shorts, black socks", "milan": "red and black vertical stripes shirt, white shorts, black socks",
    "psg": "navy blue shirt with a wide red vertical stripe bordered in white, navy shorts, navy socks",
    "paris saint-germain": "navy blue shirt with a wide red vertical stripe bordered in white, navy shorts, navy socks",
    "atletico madrid": "red and white vertical stripes shirt, blue shorts, red socks",
    "river plate": "white shirt with a red diagonal sash, black shorts, white socks",
    "boca juniors": "navy blue shirt with a yellow horizontal band across the chest, navy shorts, navy socks",
    "benfica": "red shirt with white details, white shorts, red socks", "porto": "blue and white vertical stripes shirt, blue shorts, blue socks",
    "sporting": "green and white horizontal hoops shirt, black shorts, green socks",
    "al hilal": "blue shirt, white shorts, white socks", "al nassr": "yellow shirt with blue trims, blue shorts, yellow socks",
}
TRAD = {"preto": "black", "branco": "white", "vermelho": "red", "grená": "maroon", "azul": "royal blue",
        "azul-marinho": "navy blue", "azul-celeste": "sky blue", "verde": "green", "verde-escuro": "dark green",
        "amarelo": "yellow", "laranja": "orange", "roxo": "purple", "cinza": "grey", "dourado": "gold"}


def camisa(jogo, lado):
    """Descrição em inglês do uniforme (alusão): padrão conhecido do clube, senão as cores que a ESPN informa."""
    import unicodedata
    nome = unicodedata.normalize("NFKD", (jogo.get(lado) or "").lower()).encode("ascii", "ignore").decode().strip()
    if nome in CAMISAS:
        return CAMISAS[nome]
    c1 = TRAD.get(nome_cor(jogo.get(f"cor_{lado}")), "") or ("red" if lado == "casa" else "blue")
    c2 = TRAD.get(nome_cor(jogo.get(f"cor2_{lado}")), "")
    return (f"{c1} shirt with {c2} collar and trims, {c2} shorts, {c1} socks" if c2 and c2 != c1
            else f"solid {c1} shirt, {c1} shorts, {c1} socks")


def pedido(jogo, refs=None):
    """Pedido de imagem (em inglês): dois jogadores FICTÍCIOS, um de cada lado, cada um com o uniforme que lembra o
    do time (padrão e cores da camisa, calção e meião). refs: {"casa": True/False, "fora": ...} = há foto de referência."""
    refs = refs or {}
    uni = {}
    n = 1
    for lado in ("casa", "fora"):
        if refs.get(lado):
            uni[lado] = (f"a soccer kit that copies the colors, stripes/pattern, collar, shorts and socks of the kit in "
                         f"reference image {n} as closely as possible (but with NO crest, NO sponsor, NO brand logo, NO number)")
            n += 1
        else:
            uni[lado] = camisa(jogo, lado)
    return ("Vertical 9:16 dramatic matchday poster background, photorealistic sports photography. A packed soccer "
            "stadium at night, bright floodlights, light beams and haze, green pitch. Two fictional soccer players "
            "(generic athletes, not any real person; faces turned away, in profile or in deep shadow) standing face to face "
            "in a duel, shown from the knees up in a front three-quarter view so their FULL KITS ARE CLEARLY VISIBLE: "
            f"the player on the LEFT third wears {uni['casa']}; the player on the RIGHT third wears {uni['fora']}. "
            "The kit colors and patterns are the most important part of the image and must be accurate and vivid. "
            "Real soccer kits only (short-sleeve jersey, shorts, socks): NOT American football, no helmets, no pads. "
            "Jerseys have NO crests, NO logos, NO sponsors, NO numbers, NO names. Absolutely NO text, letters or "
            "watermarks anywhere. Keep the central vertical strip darker and clean for text overlay. Cinematic, high detail.")


def _http(url, corpo=None, cab=None, tempo=120):
    req = urllib.request.Request(url, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Content-Type": "application/json", "User-Agent": UA, **(cab or {})})
    with urllib.request.urlopen(req, timeout=tempo) as r:
        return json.loads(r.read().decode())


UNIFORMES = "uniformes"  # pasta (dentro da pasta dos jogos) com as fotos de referência: <time>.jpg


def _slug_time(nome):
    import unicodedata
    t = unicodedata.normalize("NFKD", (nome or "").lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60]


def referencias(jogo, pasta):
    """Fotos de referência do uniforme dos dois times (se você mandou no painel): {"casa": caminho, "fora": caminho}."""
    achadas = {}
    for lado in ("casa", "fora"):
        cam = os.path.join(pasta, UNIFORMES, _slug_time(jogo.get(lado)) + ".jpg")
        if jogo.get(lado) and os.path.exists(cam):
            achadas[lado] = cam
    return achadas


def salvar_uniforme(pasta, time, dados):
    if not _slug_time(time):
        raise ValueError("diga o nome do time")
    if not dados or len(dados) > 12_000_000:
        raise ValueError("mande uma imagem de até 12 MB")
    img = Image.open(io.BytesIO(dados)).convert("RGB")
    img.thumbnail((1024, 1024))
    os.makedirs(os.path.join(pasta, UNIFORMES), exist_ok=True)
    img.save(os.path.join(pasta, UNIFORMES, _slug_time(time) + ".jpg"), quality=88)
    return _slug_time(time)


def uniformes(pasta):
    try:
        return sorted(n[:-4] for n in os.listdir(os.path.join(pasta, UNIFORMES)) if n.endswith(".jpg"))
    except FileNotFoundError:
        return []


def apagar_uniforme(pasta, slug):
    try:
        os.remove(os.path.join(pasta, UNIFORMES, _slug_time(slug) + ".jpg"))
    except FileNotFoundError:
        pass


def _gemini(texto, imagens=None):
    try:
        import chaves
        chaves.aplicar()
    except Exception:  # noqa: BLE001
        pass
    chave = os.environ.get("GEMINI_API_KEY", "")
    if not chave:
        raise RuntimeError("sem chave do Gemini")
    base = os.environ.get("JARVIS_GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    cab = {"x-goog-api-key": chave}
    fixo = os.environ.get("JARVIS_JOGOS_MODELO_IMAGEM", "").strip()
    modelos = [fixo] if fixo else []
    if not modelos:
        lista = _http(base + "/models?pageSize=200", cab=cab).get("models", [])
        nomes = [m["name"].split("/", 1)[-1] for m in lista
                 if "generateContent" in (m.get("supportedGenerationMethods") or []) and "image" in m.get("name", "")
                 and "gemini" in m.get("name", "")]
        nomes.sort(key=lambda n: ("preview" in n or "exp" in n, [-int(x) for x in re.findall(r"\d+", n)[:2]]))
        modelos = nomes[:3]
    if not modelos:
        raise RuntimeError("nenhum modelo de imagem do Gemini disponível para esta chave")
    erros = []
    for m in modelos:
        for config in ({"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}},
                       {"responseModalities": ["TEXT", "IMAGE"]}):
            try:
                partes = [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(open(c, "rb").read()).decode()}}
                          for c in (imagens or [])] + [{"text": texto}]
                r = _http(f"{base}/models/{m}:generateContent", {"contents": [{"parts": partes}],
                                                                 "generationConfig": config}, cab=cab)
                for c in r.get("candidates") or []:
                    for p in (c.get("content") or {}).get("parts") or []:
                        dado = (p.get("inlineData") or p.get("inline_data") or {}).get("data")
                        if dado:
                            return base64.b64decode(dado), f"Gemini ({m})"
                erros.append(f"{m}: sem imagem na resposta")
                break
            except urllib.error.HTTPError as e:
                corpo = e.read().decode(errors="replace")[:160]
                erros.append(f"{m}: HTTP {e.code} {corpo}")
                if e.code != 400:
                    break  # 429/403 (cota, plano): outro formato não resolve
    raise RuntimeError("; ".join(erros)[:400])


def _cloudflare(texto):
    conta, token = os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""), os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not (conta and token):
        raise RuntimeError("sem chave da Cloudflare")
    base = os.environ.get("JARVIS_CLOUDFLARE_URL", "https://api.cloudflare.com/client/v4").rstrip("/")
    modelo = os.environ.get("JARVIS_JOGOS_MODELO_CF", "@cf/black-forest-labs/flux-1-schnell")
    r = _http(f"{base}/accounts/{conta}/ai/run/{modelo}", {"prompt": texto[:2000], "steps": 8},
              cab={"Authorization": "Bearer " + token})
    dado = (r.get("result") or {}).get("image")
    if not dado:
        raise RuntimeError(f"Cloudflare sem imagem: {str(r.get('errors'))[:160]}")
    return base64.b64decode(dado), f"Cloudflare ({modelo.rsplit('/', 1)[-1]})"


def _vertical(bruto):
    """Qualquer proporção → 1080x1920 sem distorcer (imagem quadrada: centro nítido sobre a própria imagem desfocada)."""
    img = Image.open(io.BytesIO(bruto)).convert("RGB")
    w, h = img.size
    if h / w >= 1.6:  # já é vertical: corta e ajusta
        esc = max(L / w, A / h)
        img = img.resize((int(w * esc) + 1, int(h * esc) + 1), Image.LANCZOS)
        x, y = (img.width - L) // 2, (img.height - A) // 2
        return img.crop((x, y, x + L, y + A))
    esc = max(L / w, A / h)
    fundo = img.resize((int(w * esc) + 1, int(h * esc) + 1), Image.LANCZOS)
    x, y = (fundo.width - L) // 2, (fundo.height - A) // 2
    fundo = fundo.crop((x, y, x + L, y + A)).filter(ImageFilter.GaussianBlur(28))
    frente = img.resize((L, int(h * L / w)), Image.LANCZOS)
    mascara = Image.new("L", frente.size, 255)  # bordas de cima e de baixo em degradê: sem emenda com o fundo
    borda = min(220, frente.height // 4)
    for y in range(borda):
        v = int(255 * y / borda)
        mascara.paste(v, (0, y, frente.width, y + 1))
        mascara.paste(v, (0, frente.height - 1 - y, frente.width, frente.height - y))
    fundo.paste(frente, (0, (A - frente.height) // 2), mascara)
    return fundo


def fundo_ia(dia, destaque, pasta):
    """Devolve (imagem PIL 1080x1920, de_onde) ou (None, motivo). Guarda a arte do dia para não gerar de novo."""
    cache = os.path.join(pasta, f"{dia.isoformat()}-arte.png")
    if os.path.exists(cache):
        try:
            return Image.open(cache).convert("RGB"), "arte do dia (já gerada)"
        except OSError:
            pass
    try:
        import jogos
        base_uni = jogos.DIR
    except Exception:  # noqa: BLE001
        base_uni = pasta
    refs = referencias(destaque or {}, base_uni)
    texto = pedido(destaque or {}, {k: True for k in refs})
    imagens = [refs[k] for k in ("casa", "fora") if k in refs]
    erros = []
    for nome, func in (("gemini", lambda t: _gemini(t, imagens)), ("cloudflare", _cloudflare)):
        try:
            if nome == "cloudflare" and imagens:  # o FLUX não usa referência: volta ao pedido só com texto
                bruto, origem = func(pedido(destaque or {}))
            else:
                bruto, origem = func(texto)
            img = _vertical(bruto)
            img.save(cache, optimize=True)
            return img, origem
        except Exception as e:  # noqa: BLE001
            erros.append(f"{nome}: {str(e)[:160]}")
    return None, " · ".join(erros)
