"""Imagem dos jogos do dia: 1080x1920 (formato de Status/Stories), visual escuro com neon, várias páginas se precisar."""
import os
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont

L, A = 1080, 1920
FONTES = ["/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/dejavu/", "/usr/share/fonts/TTF/"]
DIAS = ["SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO", "DOMINGO"]
CIANO, VERDE, BRANCO, CINZA, OURO = (56, 214, 255), (74, 222, 128), (236, 246, 255), (140, 168, 190), (255, 196, 90)


def _fonte(nome, tam):
    for d in FONTES:
        try:
            return ImageFont.truetype(os.path.join(d, nome), tam)
        except OSError:
            continue
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
        d.text((300, y + 24), _caber(d, jogo, f_time, L - 70 - 300 - 30), font=f_time, fill=BRANCO)
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


def desenhar(jogos, dia, cfg, pasta, por_pagina=None):
    """Gera 1 ou mais PNGs. Devolve a lista de caminhos."""
    os.makedirs(pasta, exist_ok=True)
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
