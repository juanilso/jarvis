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
POR_PAGINA_ARTE = 5


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


def _pagina_arte(fundo, jogos, dia, cfg, pag, total):
    img = fundo.copy().convert("RGBA")
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
    img = Image.alpha_composite(img, escuro)
    d = ImageDraw.Draw(img)
    f_tag, f_tit = _fonte("DejaVuSans-Bold.ttf", 28), _fonte("BebasNeue-Regular.ttf", 168)
    f_sub, f_data = _fonte("BebasNeue-Regular.ttf", 86), _fonte("DejaVuSans-Bold.ttf", 34)
    # cabeçalho
    tag = "FUTEBOL BRASILEIRO"
    wt = d.textlength(tag, font=f_tag)
    d.rounded_rectangle([(L - wt) / 2 - 26, 60, (L + wt) / 2 + 26, 112], 26, fill=VERDE)
    d.text(((L - wt) / 2, 70), tag, font=f_tag, fill=(6, 20, 12))
    for txt, f, y, cor in (("DESTAQUES", f_tit, 120, BRANCO), ("DO DIA", f_sub, 280, OURO)):
        w = d.textlength(txt, font=f)
        d.text(((L - w) / 2 + 4, y + 5), txt, font=f, fill=(0, 0, 0))
        d.text(((L - w) / 2, y), txt, font=f, fill=cor)
    data = f"{DIAS[dia.weekday()]} · {dia.strftime('%d/%m/%Y')}" + (f"  ·  {pag}/{total}" if total > 1 else "")
    w = d.textlength(data, font=f_data)
    d.text(((L - w) / 2, 372), data, font=f_data, fill=CIANO)
    # cartões
    y = 440
    f_liga, f_time = _fonte("DejaVuSans-Bold.ttf", 24), _fonte("DejaVuSansCondensed-Bold.ttf", 30)
    f_hora, f_tv, f_x = _fonte("BebasNeue-Regular.ttf", 96), _fonte("DejaVuSans-Bold.ttf", 25), _fonte("BebasNeue-Regular.ttf", 44)
    for j in jogos:
        h = 256
        cartao = Image.new("RGBA", (L, A), (0, 0, 0, 0))
        c = ImageDraw.Draw(cartao)
        c.rounded_rectangle([50, y, L - 50, y + h], 30, fill=(6, 12, 24, 190), outline=(255, 255, 255, 40), width=2)
        img = Image.alpha_composite(img, cartao)
        d = ImageDraw.Draw(img)
        cor_c, cor_f = _hex(j.get("cor_casa"), (200, 16, 46)), _hex(j.get("cor_fora"), (0, 70, 160))
        visivel = lambda cor, cor2: cor if sum(cor) > 120 else (cor2 if sum(cor2) > 120 else (235, 235, 235))  # noqa: E731
        d.rounded_rectangle([50, y + 30, 60, y + h - 30], 5,
                            fill=visivel(cor_c, _hex(j.get("cor2_casa"), (255, 255, 255))))
        d.rounded_rectangle([L - 60, y + 30, L - 50, y + h - 30], 5,
                            fill=visivel(cor_f, _hex(j.get("cor2_fora"), (255, 255, 255))))
        liga = j["liga"].upper()
        w = d.textlength(liga, font=f_liga)
        d.text(((L - w) / 2, y + 18), liga, font=f_liga, fill=CIANO)
        for lado, cx, cor_t in (("casa", 205, cor_c), ("fora", L - 205, cor_f)):
            escudo = _escudo(j.get(f"logo_{lado}"), cfg.get("_pasta", "")) if cfg.get("escudos") and cfg.get("_pasta") else None
            if escudo is not None:
                _colar_escudo(img, cx, y + 112, 74, escudo)
            else:
                _selo(img, cx, y + 112, 74, cor_t, _hex(j.get(f"cor2_{lado}"), (255, 255, 255)),
                      j.get(f"sigla_{lado}") or j[lado][:3].upper())
        d = ImageDraw.Draw(img)
        for nome_t, cx in ((j["casa"], 205), (j["fora"], L - 205)):
            t = _caber(d, nome_t.upper(), f_time, 270)
            w = d.textlength(t, font=f_time)
            d.text((cx - w / 2, y + 200), t, font=f_time, fill=BRANCO)
        if j.get("placar"):
            topo = "AO VIVO" if j.get("estado") == "in" else "ENCERRADO"
            meio, cor_meio = j["placar"].upper(), OURO
        else:
            topo, meio, cor_meio = "X", j["hora"], BRANCO
        w = d.textlength(topo, font=f_x)
        d.text(((L - w) / 2, y + 48), topo, font=f_x, fill=OURO if j.get("placar") else (190, 200, 215))
        w = d.textlength(meio, font=f_hora)
        d.text(((L - w) / 2, y + 88), meio, font=f_hora, fill=cor_meio)
        canais = " / ".join(j.get("canais") or []) or "A CONFIRMAR"
        t = _caber(d, canais.upper(), f_tv, 330)
        w = d.textlength(t, font=f_tv)
        d.rounded_rectangle([(L - w) / 2 - 18, y + 196, (L + w) / 2 + 18, y + 236], 20,
                            fill=VERDE if j.get("canais") else (70, 84, 100))
        d.text(((L - w) / 2, y + 202), t, font=f_tv, fill=(6, 20, 12) if j.get("canais") else BRANCO)
        y += h + 24
    # rodapé
    marca, rod = _sem_emoji(cfg.get("marca") or ""), _sem_emoji(cfg.get("rodape") or "")
    if marca:
        f = _fonte("BebasNeue-Regular.ttf", 64)
        w = d.textlength(marca.upper(), font=f)
        d.text(((L - w) / 2, A - 190), marca.upper(), font=f, fill=BRANCO)
    f = _fonte("DejaVuSans.ttf", 30)
    w = d.textlength(rod, font=f)
    d.text(((L - w) / 2, A - (115 if marca else 160)), rod, font=f, fill=CINZA)
    nota = "Horários de Brasília · canais sujeitos a alteração"
    f = _fonte("DejaVuSans.ttf", 22)
    w = d.textlength(nota, font=f)
    d.text(((L - w) / 2, A - 62), nota, font=f, fill=CINZA)
    return img.convert("RGB")


def _desenhar_arte(jogos, dia, cfg, pasta, info):
    import jogos_arte
    fundo, origem = jogos_arte.fundo_ia(dia, jogos[0], pasta)
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
