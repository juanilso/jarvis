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


# Alusão às camisas (cores e padrão, sem escudo/patrocínio/marca). Chave: nome do time sem acento, minúsculo.
CAMISAS = {
    "flamengo": "red and black horizontal hoops", "palmeiras": "solid green with white collar",
    "corinthians": "white with black collar and black trim", "sao paulo": "white with a red and black horizontal chest band",
    "santos": "plain white with black trim", "fluminense": "maroon, green and white vertical stripes",
    "botafogo": "black and white vertical stripes", "vasco": "white with a black diagonal sash",
    "vasco da gama": "white with a black diagonal sash", "gremio": "sky blue, black and white vertical stripes",
    "internacional": "solid red with white collar", "atletico-mg": "black and white vertical stripes",
    "atletico mineiro": "black and white vertical stripes", "cruzeiro": "solid royal blue with white trim",
    "bahia": "white with blue and red details", "fortaleza": "red, blue and white horizontal stripes",
    "ceara": "black and white vertical stripes", "sport": "red and black horizontal hoops",
    "athletico-pr": "red and black horizontal hoops", "athletico paranaense": "red and black horizontal hoops",
    "vitoria": "red and black horizontal hoops", "coritiba": "white with green trim", "juventude": "green and white vertical stripes",
    "bragantino": "white with red trim", "red bull bragantino": "white with red trim", "mirassol": "yellow with green trim",
    "goias": "solid green with white trim", "america-mg": "green and black vertical stripes", "cuiaba": "yellow with green trim",
    "chapecoense": "solid green with white trim", "remo": "solid navy blue", "paysandu": "light blue and white vertical stripes",
    "brasil": "canary yellow with green collar", "argentina": "sky blue and white vertical stripes",
    "real madrid": "plain white", "barcelona": "blue and garnet vertical stripes", "liverpool": "solid red",
    "manchester city": "sky blue", "manchester united": "red with white collar", "arsenal": "red body with white sleeves",
    "chelsea": "solid royal blue", "bayern munich": "red with white details", "juventus": "black and white vertical stripes",
    "inter milan": "black and blue vertical stripes", "ac milan": "red and black vertical stripes", "psg": "navy blue with a red vertical stripe",
    "paris saint-germain": "navy blue with a red vertical stripe", "river plate": "white with a red diagonal sash",
    "boca juniors": "navy blue with a yellow horizontal chest band", "atletico madrid": "red and white vertical stripes",
}
TRAD = {"preto": "black", "branco": "white", "vermelho": "red", "grená": "maroon", "azul": "royal blue",
        "azul-marinho": "navy blue", "azul-celeste": "sky blue", "verde": "green", "verde-escuro": "dark green",
        "amarelo": "yellow", "laranja": "orange", "roxo": "purple", "cinza": "grey", "dourado": "gold"}


def camisa(jogo, lado):
    """Descrição em inglês da camisa (alusão): padrão conhecido do clube, senão as cores que a ESPN informa."""
    import unicodedata
    nome = unicodedata.normalize("NFKD", (jogo.get(lado) or "").lower()).encode("ascii", "ignore").decode().strip()
    if nome in CAMISAS:
        return CAMISAS[nome]
    c1 = TRAD.get(nome_cor(jogo.get(f"cor_{lado}")), "") or ("red" if lado == "casa" else "blue")
    c2 = TRAD.get(nome_cor(jogo.get(f"cor2_{lado}")), "")
    return f"{c1} with {c2} details" if c2 and c2 != c1 else f"solid {c1}"


def pedido(jogo):
    """Texto do pedido de imagem (em inglês, que os modelos de imagem entendem melhor): dois jogadores FICTÍCIOS,
    de costas/três-quartos, um de cada lado, com camisas que lembram as dos times do jogo principal do dia."""
    return ("Vertical 9:16 dramatic sports poster background, photorealistic. A packed football (soccer) stadium at "
            "night, bright floodlights, light beams and haze, lush green pitch. Two fictional soccer players (generic, "
            "not any real person, faces turned away or in shadow) seen from behind / three-quarter back view, standing "
            "face to face like a matchday duel: one on the LEFT third of the image wearing a soccer jersey that is "
            f"{camisa(jogo, 'casa')}, and one on the RIGHT third wearing a soccer jersey that is {camisa(jogo, 'fora')}. "
            "Soccer kits only (shirt, shorts, socks), NOT American football, no helmets, no shoulder pads. Jerseys have "
            "NO crests, NO logos, NO sponsors, NO numbers, NO names. Absolutely NO text, letters, words or watermarks "
            "anywhere in the image. The central vertical strip is darker and clean, left free for text overlay. "
            "Cinematic, high detail, Brazilian matchday atmosphere.")


def _http(url, corpo=None, cab=None, tempo=120):
    req = urllib.request.Request(url, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Content-Type": "application/json", "User-Agent": UA, **(cab or {})})
    with urllib.request.urlopen(req, timeout=tempo) as r:
        return json.loads(r.read().decode())


def _gemini(texto):
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
                r = _http(f"{base}/models/{m}:generateContent", {"contents": [{"parts": [{"text": texto}]}],
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
    texto = pedido(destaque or {})
    erros = []
    for nome, func in (("gemini", _gemini), ("cloudflare", _cloudflare)):
        try:
            bruto, origem = func(texto)
            img = _vertical(bruto)
            img.save(cache, optimize=True)
            return img, origem
        except Exception as e:  # noqa: BLE001
            erros.append(f"{nome}: {str(e)[:160]}")
    return None, " · ".join(erros)
