"""Imagem dos jogos do dia: 1080x1920 (formato de Status/Stories), visual escuro com neon, várias páginas se precisar."""
import os
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont

L, A = 1080, 1920
FONTES = ["/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/dejavu/", "/usr/share/fonts/TTF/",
          os.path.join(os.path.dirname(os.path.abspath(__file__)), "fontes") + "/"]
DIAS = ["SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO", "DOMINGO"]
CIANO, VERDE, BRANCO, CINZA, OURO = (56, 214, 255), (74, 222, 128), (236, 246, 255), (140, 168, 190), (255, 196, 90)


RESERVA = {  # se a fonte pedida não existir, tenta estas (na ordem) antes da fonte mínima do Pillow
    "BebasNeue-Regular.ttf": ["Anton-Regular.ttf", "DejaVuSansCondensed-Bold.ttf", "DejaVuSans-Bold.ttf"],
    "DejaVuSansCondensed-Bold.ttf": ["DejaVuSans-Bold.ttf", "LiberationSansNarrow-Bold.ttf", "LiberationSans-Bold.ttf"],
    "DejaVuSans-Bold.ttf": ["LiberationSans-Bold.ttf", "FreeSansBold.ttf"],
    "DejaVuSans.ttf": ["LiberationSans-Regular.ttf", "FreeSans.ttf"],
}


def _fonte(nome, tam):
    for n in [nome] + RESERVA.get(nome, []):
        for d in FONTES + ["/usr/share/fonts/truetype/liberation/", "/usr/share/fonts/truetype/freefont/"]:
            try:
                return ImageFont.truetype(os.path.join(d, n), tam)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=tam)  # Pillow 10.1+: fonte padrão em qualquer tamanho
    except TypeError:
        return ImageFont.load_default()


def _sem_emoji(t):
    return re.sub(r"[^\w\s.,:;!?()/\-+&'ºª°%x]", "", t or "", flags=re.UNICODE).strip()


def _caber(d, texto, fonte, largura):
    if d.textlength(texto, font=fonte) <= largura:
        return texto
    while texto and d.textlength(texto + "…", font=fonte) > largura:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def _fundo():
    img = Image.new("RGB", (L, A), (5, 10, 20))
    d = ImageDraw.Draw(img)
    for y in range(A):  # degradê vertical azul-noite
        t = y / A
        d.line([(0, y), (L, y)], fill=(int(5 + 8 * t), int(12 + 10 * (1 - t)), int(26 + 18 * (1 - t))))
    grade = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    g = ImageDraw.Draw(grade)
    for x in range(0, L, 54):
        g.line([(x, 0), (x, A)], fill=(56, 189, 248, 14))
    for y in range(0, A, 54):
        g.line([(0, y), (L, y)], fill=(56, 189, 248, 14))
    brilho = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    b = ImageDraw.Draw(brilho)
    b.ellipse([-200, -260, L + 200, 520], fill=(56, 189, 248, 60))
    b.ellipse([L - 420, A - 520, L + 300, A + 200], fill=(74, 222, 128, 40))
    brilho = brilho.filter(ImageFilter.GaussianBlur(120))
    img = Image.alpha_composite(img.convert("RGBA"), brilho)
    return Image.alpha_composite(img, grade)


def _pagina(jogos, dia, cfg, pag, total):
    img = _fundo()
    d = ImageDraw.Draw(img)
    f_tit, f_sub = _fonte("DejaVuSans-Bold.ttf", 92), _fonte("DejaVuSans.ttf", 38)
    f_liga, f_hora = _fonte("DejaVuSans-Bold.ttf", 30), _fonte("DejaVuSans-Bold.ttf", 54)
    f_time, f_tv, f_rod = _fonte("DejaVuSansCondensed-Bold.ttf", 46), _fonte("DejaVuSans.ttf", 30), _fonte("DejaVuSans.ttf", 30)
    # cabeçalho
    d.text((70, 110), "JOGOS DE HOJE", font=f_tit, fill=BRANCO)
    sub = f"{DIAS[dia.weekday()]} · {dia.strftime('%d/%m/%Y')}" + (f"   ({pag}/{total})" if total > 1 else "")
    d.text((74, 222), sub, font=f_sub, fill=CIANO)
    d.rounded_rectangle([70, 290, 270, 298], 4, fill=VERDE)
    y, liga = 350, None
    for j in jogos:
        if j["liga"] != liga:
            liga = j["liga"]
            y += 14
            txt = liga.upper()
            w = d.textlength(txt, font=f_liga)
            d.rounded_rectangle([70, y, 70 + w + 44, y + 50], 25, fill=(18, 44, 66), outline=CIANO, width=2)
            d.text((92, y + 9), txt, font=f_liga, fill=CIANO)
            y += 70
        # cartão do jogo
        d.rounded_rectangle([70, y, L - 70, y + 150], 22, fill=(10, 24, 38), outline=(40, 80, 110), width=2)
        d.rounded_rectangle([70, y, 82, y + 150], 6, fill=VERDE if j.get("estado") == "pre" else OURO)
        d.text((108, y + 26), j["hora"], font=f_hora, fill=BRANCO)
        jogo = f"{j['casa']}  x  {j['fora']}"
        tam = 46
        while tam > 32 and d.textlength(jogo, font=_fonte("DejaVuSansCondensed-Bold.ttf", tam)) > L - 70 - 300 - 30:
            tam -= 2  # nome comprido: diminui um pouco antes de cortar
        d.text((300, y + 24 + (46 - tam) // 2), _caber(d, jogo, _fonte("DejaVuSansCondensed-Bold.ttf", tam), L - 70 - 300 - 30),
               font=_fonte("DejaVuSansCondensed-Bold.ttf", tam), fill=BRANCO)
        x = 302
        if j.get("placar"):
            selo = ("AO VIVO " if j.get("estado") == "in" else "ENCERRADO ") + j["placar"]
            d.text((x, y + 92), selo, font=_fonte("DejaVuSans-Bold.ttf", 30), fill=OURO)
            x += d.textlength(selo + "   ", font=_fonte("DejaVuSans-Bold.ttf", 30))
        canais = " / ".join(j.get("canais") or []) or "canal a confirmar"
        d.text((x, y + 92), _caber(d, "TV: " + canais, f_tv, L - 70 - x - 30), font=f_tv,
               fill=VERDE if j.get("canais") else CINZA)
        y += 172
    if not jogos:
        d.text((70, 420), "Sem jogos do futebol", font=f_time, fill=BRANCO)
        d.text((70, 480), "brasileiro hoje.", font=f_time, fill=BRANCO)
    # rodapé
    rod = _sem_emoji(cfg.get("rodape") or "")
    marca = _sem_emoji(cfg.get("marca") or "")
    d.line([(70, A - 210), (L - 70, A - 210)], fill=(40, 80, 110), width=2)
    if marca:
        d.text((70, A - 180), marca, font=_fonte("DejaVuSans-Bold.ttf", 44), fill=BRANCO)
    d.text((70, A - (115 if marca else 180)), rod, font=f_rod, fill=CINZA)
    d.text((70, A - 70), "Horários de Brasília · canais sujeitos a alteração", font=_fonte("DejaVuSans.ttf", 24), fill=CINZA)
    return img.convert("RGB")


# ------------------------------------------------------------------ estilo "arte" (fundo gerado por IA)
POR_PAGINA_ARTE = 4  # com 5, o último cartão encostava no rodapé/marca


def _hex(c, padrao):
    try:
        h = str(c or "").lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except (ValueError, IndexError):
        return padrao


def _contraste(cor):
    r, g, b = cor
    return (15, 15, 15) if (0.299 * r + 0.587 * g + 0.114 * b) > 160 else (255, 255, 255)


def _escudo(url, pasta):
    """Baixa (uma vez) o escudo informado pela ESPN. Devolve imagem RGBA ou None."""
    if not url or not url.startswith("https://"):
        return None
    import hashlib
    import urllib.request
    dirc = os.path.join(pasta, "escudos")
    cam = os.path.join(dirc, hashlib.sha1(url.encode()).hexdigest()[:16] + ".png")
    try:
        if not os.path.exists(cam):
            os.makedirs(dirc, exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.27 (jogos do dia)"})
            with urllib.request.urlopen(req, timeout=20) as r:
                bruto = r.read(3_000_000)
            from io import BytesIO
            Image.open(BytesIO(bruto)).convert("RGBA").save(cam)
        return Image.open(cam).convert("RGBA")
    except Exception:  # noqa: BLE001
        return None


def _colar_escudo(img, cx, cy, raio, escudo):
    """Escudo dentro de um círculo claro, centralizado e sem distorcer."""
    sombra = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).ellipse([cx - raio - 6, cy - raio + 4, cx + raio + 6, cy + raio + 16], fill=(0, 0, 0, 150))
    img.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(img)
    d.ellipse([cx - raio, cy - raio, cx + raio, cy + raio], fill=(245, 247, 250))
    caixa = escudo.getbbox()
    if caixa:
        escudo = escudo.crop(caixa)
    lado = int(raio * 1.42)
    esc = min(lado / escudo.width, lado / escudo.height)
    e2 = escudo.resize((max(1, int(escudo.width * esc)), max(1, int(escudo.height * esc))), Image.LANCZOS)
    img.alpha_composite(e2, (int(cx - e2.width / 2), int(cy - e2.height / 2)))


def _selo(img, cx, cy, raio, cor, cor2, sigla):
    """Selo redondo nas cores do clube com a sigla (usado quando não há escudo)."""
    sombra = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).ellipse([cx - raio - 6, cy - raio + 4, cx + raio + 6, cy + raio + 16], fill=(0, 0, 0, 150))
    img.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(img)
    anel = cor2 if sum(abs(a - b) for a, b in zip(cor, cor2)) > 90 else (255, 255, 255)
    d.ellipse([cx - raio, cy - raio, cx + raio, cy + raio], fill=anel)
    d.ellipse([cx - raio + 9, cy - raio + 9, cx + raio - 9, cy + raio - 9], fill=cor)
    tam = 56 if len(sigla) <= 3 else 46
    f = _fonte("BebasNeue-Regular.ttf", tam)
    w = d.textlength(sigla, font=f)
    caixa = d.textbbox((0, 0), sigla, font=f)
    d.text((cx - w / 2, cy - (caixa[3] - caixa[1]) / 2 - caixa[1]), sigla, font=f, fill=_contraste(cor))


def escurecer():
    """Camada que escurece o topo e o rodapé (para o texto aparecer sobre a arte)."""
    escuro = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    e = ImageDraw.Draw(escuro)
    for y in range(A):  # escurece em cima (título) e embaixo (rodapé), suave, sem emendas
        if y < 520:
            alfa = 205 - (205 - 110) * y / 520
        elif y > A - 380:
            alfa = 110 + (215 - 110) * (y - (A - 380)) / 380
        else:
            alfa = 110
        e.line([(0, y), (L, y)], fill=(4, 8, 16, int(alfa)))
    return escuro


CARTAO_Y, CARTAO_H, CARTAO_PASSO = 470, 290, 308  # posição dos cartões (o vídeo anima cada faixa separadamente)
NEON, MARINHO = (181, 250, 49), (5, 14, 34)


def _titulo_do_dia(dia):
    import datetime as _dt
    hoje = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=-3))).date()
    return "JOGOS DE HOJE" if dia == hoje else "JOGOS DE AMANHÃ" if dia == hoje + _dt.timedelta(days=1) else "JOGOS DO DIA"


def _tv(d, x, y, cor):
    """Iconezinho de TV (o emoji não existe nas fontes do servidor)."""
    d.rounded_rectangle([x, y, x + 30, y + 21], 4, outline=cor, width=3)
    d.line([(x + 9, y + 26), (x + 21, y + 26)], fill=cor, width=3)


def _bola(img, cx, cy, r):
    """Bola de futebol simples (branca com gomos pretos)."""
    import math
    d = ImageDraw.Draw(img)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(250, 250, 250), outline=(20, 20, 20), width=3)
    pent = lambda x0, y0, rr: [(x0 + rr * math.cos(math.radians(-90 + 72 * k)), y0 + rr * math.sin(math.radians(-90 + 72 * k)))  # noqa: E731
                               for k in range(5)]
    d.polygon(pent(cx, cy, r * 0.36), fill=(20, 20, 20))
    for k in range(5):
        a = math.radians(-90 + 72 * k)
        px, py = cx + r * 0.36 * math.cos(a), cy + r * 0.36 * math.sin(a)
        qx, qy = cx + r * 0.78 * math.cos(a), cy + r * 0.78 * math.sin(a)
        d.line([(px, py), (qx, qy)], fill=(20, 20, 20), width=3)
        d.polygon(pent(cx + r * 0.95 * math.cos(a), cy + r * 0.95 * math.sin(a), r * 0.2), fill=(20, 20, 20))


def _cantos(d, x0, y0, x1, y1, cor, t=6, c=46):
    """Cantoneiras em destaque (canto de cima à esquerda e de baixo à direita), como no modelo do Canva."""
    d.line([(x0, y0 + c), (x0, y0), (x0 + c, y0)], fill=cor, width=t, joint="curve")
    d.line([(x1 - c, y1), (x1, y1), (x1, y1 - c)], fill=cor, width=t, joint="curve")


def _pagina_arte(fundo, jogos, dia, cfg, pag, total):
    """Arte no estilo do modelo aprovado no Canva: título grande, data, selo neon e cartões escuros com borda neon.
    fundo=None: devolve só o texto e os cartões numa camada transparente (RGBA), sem escurecer, para o vídeo."""
    if fundo is None:
        img = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    else:
        img = Image.alpha_composite(fundo.copy().convert("RGBA"), escurecer())
    d = ImageDraw.Draw(img)
    # ---- cabeçalho
    tit = cfg.get("_titulo") or _titulo_do_dia(dia)
    f_tit = _fonte("BebasNeue-Regular.ttf", 214)
    while d.textlength(tit, font=f_tit) > L - 120 and f_tit.size > 120:
        f_tit = _fonte("BebasNeue-Regular.ttf", f_tit.size - 8)
    w = d.textlength(tit, font=f_tit)
    sombra = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).text(((L - w) / 2 + 6, 48), tit, font=f_tit, fill=(0, 0, 0, 200))
    img.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(img)
    d.text(((L - w) / 2, 40), tit, font=f_tit, fill=(255, 255, 255))
    d.polygon([(150, 262), (L - 130, 262), (L - 150, 274), (130, 274)], fill=NEON)  # traço neon inclinado
    data = f"{DIAS[dia.weekday()]} · {dia.strftime('%d/%m')}" + (f"  ·  {pag}/{total}" if total > 1 else "")
    f_data = _fonte("BebasNeue-Regular.ttf", 72)
    w = d.textlength(data, font=f_data)
    d.text(((L - w) / 2, 288), data, font=f_data, fill=(255, 255, 255))
    tag = "FUTEBOL BRASILEIRO" if not any(j.get("internacional") for j in (cfg.get("_jogos_todos") or jogos)) \
        else "FUTEBOL NO BRASIL E NO MUNDO"
    f_tag = _fonte("DejaVuSans-Bold.ttf", 28)
    wt = d.textlength(tag, font=f_tag)
    d.polygon([((L - wt) / 2 - 40, 386), ((L + wt) / 2 + 52, 386), ((L + wt) / 2 + 40, 434), ((L - wt) / 2 - 52, 434)],
              fill=NEON)
    d.text(((L - wt) / 2, 393), tag, font=f_tag, fill=(0, 11, 38))
    # ---- cartões
    f_liga, f_time = _fonte("DejaVuSans-Bold.ttf", 26), _fonte("DejaVuSansCondensed-Bold.ttf", 30)
    f_hora, f_x = _fonte("BebasNeue-Regular.ttf", 132), _fonte("BebasNeue-Regular.ttf", 58)
    f_tv, f_sig = _fonte("DejaVuSans-Bold.ttf", 26), _fonte("BebasNeue-Regular.ttf", 58)
    y = CARTAO_Y
    x0, x1 = 70, L - 70
    for j in jogos:
        h = CARTAO_H
        cartao = Image.new("RGBA", (L, A), (0, 0, 0, 0))
        c = ImageDraw.Draw(cartao)
        c.rounded_rectangle([x0, y, x1, y + h], 22, fill=MARINHO + (218,), outline=NEON + (150,), width=3)
        c.line([(x0 + 40, y + h - 58), (x1 - 40, y + h - 58)], fill=NEON + (70,), width=2)
        img = Image.alpha_composite(img, cartao)
        d = ImageDraw.Draw(img)
        _cantos(d, x0 - 4, y - 4, x1 + 4, y + h + 4, NEON)
        liga = j["liga"].upper()
        w = d.textlength(liga, font=f_liga)
        d.text(((L - w) / 2, y + 16), liga, font=f_liga, fill=NEON)
        for lx in ((L - w) / 2 - 90, (L + w) / 2 + 20):
            d.line([(lx, y + 32), (lx + 70, y + 32)], fill=NEON + (255,), width=2)
        for lado, cx in (("casa", 232), ("fora", L - 232)):
            cor = _hex(j.get(f"cor_{lado}"), (40, 60, 90))
            cy, r = y + 118, 68
            escudo = _escudo(j.get(f"logo_{lado}"), cfg.get("_pasta", "")) if cfg.get("escudos") and cfg.get("_pasta") else None
            if escudo is not None:
                _colar_escudo(img, cx, cy, r, escudo)
                d = ImageDraw.Draw(img)
                d.ellipse([cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5], outline=NEON, width=5)
            else:
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=cor, outline=NEON, width=5)
                sig = (j.get(f"sigla_{lado}") or j[lado][:3]).upper()[:4]
                w = d.textlength(sig, font=f_sig)
                cx_b = d.textbbox((0, 0), sig, font=f_sig)
                d.text((cx - w / 2, cy - (cx_b[3] - cx_b[1]) / 2 - cx_b[1]), sig, font=f_sig, fill=_contraste(cor))
            t = _caber(d, j[lado].upper(), f_time, 300)
            w = d.textlength(t, font=f_time)
            d.text((cx - w / 2, y + 194), t, font=f_time, fill=(255, 255, 255))
        if j.get("placar"):
            meio, embaixo, cor_meio = j["placar"].upper(), ("AO VIVO" if j.get("estado") == "in" else "FIM"), OURO
        else:
            meio, embaixo, cor_meio = j["hora"], "X", (255, 255, 255)
        w = d.textlength(meio, font=f_hora)
        d.text(((L - w) / 2, y + 42), meio, font=f_hora, fill=cor_meio)
        w = d.textlength(embaixo, font=f_x)
        d.text(((L - w) / 2, y + 168), embaixo, font=f_x, fill=NEON)
        canais = " · ".join(j.get("canais") or []) or "A CONFIRMAR"
        t = _caber(d, canais, f_tv, 560)
        w = d.textlength(t, font=f_tv) + 44
        _tv(d, (L - w) / 2, y + h - 42, NEON if j.get("canais") else CINZA)
        d.text(((L - w) / 2 + 44, y + h - 44), t, font=f_tv, fill=NEON if j.get("canais") else CINZA)
        y += CARTAO_PASSO
    # ---- rodapé
    marca, rod = _sem_emoji(cfg.get("marca") or ""), _sem_emoji(cfg.get("rodape") or "Bom jogo!").strip() or "Bom jogo!"
    f_rod = _fonte("BebasNeue-Regular.ttf", 96)
    w = d.textlength(rod, font=f_rod)
    xr = (L - w - 96) / 2
    d.text((xr, A - 196), rod, font=f_rod, fill=NEON)
    _bola(img, int(xr + w + 60), A - 146, 38)
    d = ImageDraw.Draw(img)
    if marca:
        f = _fonte("DejaVuSans-Bold.ttf", 26)
        w = d.textlength(marca.upper(), font=f)
        d.text(((L - w) / 2, A - 86), marca.upper(), font=f, fill=(255, 255, 255))
    nota = "Horários de Brasília · canais sujeitos a alteração"
    f = _fonte("DejaVuSans.ttf", 21)
    w = d.textlength(nota, font=f)
    d.text(((L - w) / 2, A - 48), nota, font=f, fill=CINZA)
    return img if fundo is None else img.convert("RGB")


def abertura(jogo, dia, cfg, faixa_escura=True):
    """Cena de abertura do vídeo: o jogo principal do dia em destaque (camada transparente 1080x1920)."""
    img = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f_tag, f_time, f_x = _fonte("DejaVuSans-Bold.ttf", 34), _fonte("BebasNeue-Regular.ttf", 150), _fonte("BebasNeue-Regular.ttf", 110)
    f_info = _fonte("BebasNeue-Regular.ttf", 84)
    if faixa_escura:
        faixa = Image.new("RGBA", (L, A), (0, 0, 0, 0))
        ImageDraw.Draw(faixa).rectangle([0, 1120, L, 1700], fill=(3, 8, 20, 170))
        img.alpha_composite(faixa.filter(ImageFilter.GaussianBlur(30)))
    d = ImageDraw.Draw(img)
    tag = "JOGO PRINCIPAL DE HOJE"
    wt = d.textlength(tag, font=f_tag)
    d.polygon([((L - wt) / 2 - 40, 1110), ((L + wt) / 2 + 52, 1110), ((L + wt) / 2 + 40, 1166), ((L - wt) / 2 - 52, 1166)],
              fill=NEON)
    d.text(((L - wt) / 2, 1118), tag, font=f_tag, fill=(0, 11, 38))
    for k, (txt, f, yy, cor) in enumerate(((_caber(d, jogo["casa"].upper(), f_time, L - 120), f_time, 1190, (255, 255, 255)),
                                           ("X", f_x, 1340, NEON),
                                           (_caber(d, jogo["fora"].upper(), f_time, L - 120), f_time, 1440, (255, 255, 255)))):
        w = d.textlength(txt, font=f)
        d.text(((L - w) / 2 + 5, yy + 6), txt, font=f, fill=(0, 0, 0))
        d.text(((L - w) / 2, yy), txt, font=f, fill=cor)
    info = f"{jogo['hora']} · {' · '.join(jogo.get('canais') or []) or jogo['liga']}".upper()
    info = _caber(d, info, f_info, L - 100)
    w = d.textlength(info, font=f_info)
    d.text(((L - w) / 2, 1610), info, font=f_info, fill=NEON)
    return img


def _desenhar_arte(jogos, dia, cfg, pasta, info):
    import jogos_arte
    fundo, origem = jogos_arte.fundo_ia(dia, jogos[0], cfg.get("_pasta_arte") or pasta)
    if fundo is None:
        info["aviso"] = f"arte com IA indisponível ({origem[:200]}); saiu o banner simples"
        return None
    paginas = [jogos[i:i + POR_PAGINA_ARTE] for i in range(0, len(jogos), POR_PAGINA_ARTE)]
    caminhos = []
    for i, p in enumerate(paginas, 1):
        cam = os.path.join(pasta, f"{dia.isoformat()}-jogos-{i}.png")
        _pagina_arte(fundo, p, dia, {**cfg, "_pasta": pasta}, i, len(paginas)).save(cam, optimize=True)
        caminhos.append(cam)
    info.update(estilo="arte", arte=origem)
    return caminhos


def desenhar(jogos, dia, cfg, pasta, por_pagina=None, info=None):
    """Gera 1 ou mais PNGs. Devolve a lista de caminhos. Estilo "arte": fundo por IA; se falhar, o simples."""
    os.makedirs(pasta, exist_ok=True)
    info = {} if info is None else info
    if jogos and cfg.get("estilo", "arte") == "arte":
        try:
            feitos = _desenhar_arte(jogos, dia, cfg, pasta, info)
            if feitos:
                return feitos
        except Exception as e:  # noqa: BLE001
            info["aviso"] = f"arte com IA falhou ({type(e).__name__}: {str(e)[:120]}); saiu o banner simples"
    info.setdefault("estilo", "simples")
    paginas, atual, altura = [], [], 350
    for j in jogos:  # quebra por altura (cabeçalhos de campeonato ocupam espaço)
        extra = 172 + (84 if not atual or atual[-1]["liga"] != j["liga"] else 0)
        if atual and (altura + extra > A - 240 or (por_pagina and len(atual) >= por_pagina)):
            paginas.append(atual)
            atual, altura = [], 350
            extra = 172 + 84
        atual.append(j)
        altura += extra
    paginas.append(atual)
    caminhos = []
    for i, p in enumerate(paginas, 1):
        cam = os.path.join(pasta, f"{dia.isoformat()}-jogos-{i}.png")
        _pagina(p, dia, cfg, i, len(paginas)).save(cam, optimize=True)
        caminhos.append(cam)
    return caminhos
