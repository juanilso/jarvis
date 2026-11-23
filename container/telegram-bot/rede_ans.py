"""Rede credenciada por fontes OFICIAIS: ANS (quem atende a operadora) + CNES/DATASUS (detalhes de cada local).

Fontes (dados abertos, atualização mensal, sem bloqueio):
- ANS "Operadoras e prestadores não-hospitalares" (rede por operadora) e "Produtos e Prestadores Hospitalares"
  (rede hospitalar por plano): dadosabertos.ans.gov.br/FTP/PDA/…
- CNES (Ministério da Saúde/DATASUS): base mensal com estabelecimentos (endereço, telefone, e-mail, localização),
  profissionais por estabelecimento (CBO = ocupação/especialidade) e a tabela de ocupações.

Cruzamento pelo código CNES. Saídas (CSV com ; e acentos, abre no Excel) em CONFIG_DIR/rede/<op>-<UF>/<AAAA-MM>/:
  estabelecimentos.csv · profissionais.csv · hospitais_planos.csv · resumo.json · DIAGNOSTICO.txt
Compara com a execução anterior (quem entrou e quem saiu da rede).

As colunas são encontradas pelo nome (com alternativas), porque os arquivos mudam de layout com o tempo.
Se algo não bater, DIAGNOSTICO.txt mostra os arquivos e cabeçalhos encontrados.
"""
import csv
import datetime as dt
import io
import json
import os
import re
import shutil
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile

import jarvis_core as core

csv.field_size_limit(10_000_000)

ANS = os.environ.get("REDE_ANS_URL", "https://dadosabertos.ans.gov.br/FTP/PDA").rstrip("/")
CNES = os.environ.get("REDE_CNES_URL", "https://cnes.datasus.gov.br/EstatisticasServlet?path=BASE_DE_DADOS_CNES_{AAAAMM}.ZIP")
DIR = os.path.join(core.CONFIG_DIR, "rede")
CACHE = os.path.join(DIR, "downloads")
UA = "Jarvis/1.29 (dados abertos ANS/CNES)"
UF_IBGE = {"RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17", "MA": "21", "PI": "22",
           "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27", "SE": "28", "BA": "29", "MG": "31", "ES": "32",
           "RJ": "33", "SP": "35", "PR": "41", "SC": "42", "RS": "43", "MS": "50", "MT": "51", "GO": "52", "DF": "53"}
PADRAO = {"operadora": "AMIL", "codigos": [], "uf": "RJ", "profissionais": True, "hospitais": True}


# ------------------------------------------------------------------ utilidades
def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t)) if unicodedata.category(c) != "Mn").upper().strip()


def _col(cab, *nomes):
    """Índice da primeira coluna cujo nome bate (sem acento/caixa) com algum dos nomes; também aceita 'contém'."""
    norm = [_sem_acento(c).strip('"﻿ ') for c in cab]
    for n in nomes:
        n = _sem_acento(n)
        if n in norm:
            return norm.index(n)
    for n in nomes:
        n = _sem_acento(n)
        for i, c in enumerate(norm):
            if n in c:
                return i
    return None


def _so_digitos(t):
    return re.sub(r"\D", "", str(t or ""))


def _cnes(t):
    d = _so_digitos(t)
    return d.zfill(7)[-7:] if d else ""


def _baixar(url, destino, tempo=600):
    """Baixa para disco (arquivos grandes, sem estourar a memória). Reaproveita se baixou há menos de 20 dias."""
    if os.path.exists(destino) and time.time() - os.path.getmtime(destino) < 20 * 86400 and os.path.getsize(destino) > 0:
        return destino
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    tmp = destino + ".parcial"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=tempo) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1024 * 1024)
    os.replace(tmp, destino)
    return destino


def _listar(url):
    """Arquivos de uma pasta da ANS (página de listagem do servidor)."""
    req = urllib.request.Request(url.rstrip("/") + "/", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", "replace")
    return sorted(set(h for h in re.findall(r'href="([^"?#]+)"', html) if not h.startswith(("/", "..", "http")) or h.endswith((".zip", ".csv"))))


def _ler_csv(arquivo_bin):
    """Lê um CSV (latin-1 ou utf-8; ; ou ,) em fluxo. Devolve (cabeçalho, iterador de linhas)."""
    bruto = io.BufferedReader(arquivo_bin, 1024 * 1024)
    amostra = bruto.peek(65536)[:65536]
    try:
        amostra.decode("utf-8")
        cod = "utf-8-sig"
    except UnicodeDecodeError:
        cod = "latin-1"
    texto = io.TextIOWrapper(bruto, encoding=cod, errors="replace", newline="")
    primeira = amostra.decode(cod, "replace").splitlines()[0] if amostra else ""
    sep = ";" if primeira.count(";") >= primeira.count(",") else ","
    leitor = csv.reader(texto, delimiter=sep, quotechar='"')
    cab = next(leitor, [])
    return [c.strip('﻿" ') for c in cab], leitor


def _csvs_do_zip(caminho, filtro=None):
    """[(nome, abrir)] dos CSVs de um zip (inclusive zips dentro do zip)."""
    saida = []
    z = zipfile.ZipFile(caminho)
    for n in z.namelist():
        base = os.path.basename(n)
        if filtro and not filtro(base):
            continue
        if n.lower().endswith(".csv"):
            saida.append((base, lambda n=n, z=z: z.open(n)))
        elif n.lower().endswith(".zip"):
            interno = os.path.join(os.path.dirname(caminho), "_interno_" + base)
            if not os.path.exists(interno):
                with z.open(n) as s, open(interno, "wb") as d:
                    shutil.copyfileobj(s, d, 1024 * 1024)
            saida += _csvs_do_zip(interno)
    return saida


# ------------------------------------------------------------------ ANS
def _arquivos_ans(pasta, uf, diag):
    """Baixa os arquivos da UF (ou o nacional, se não houver partição por UF). Devolve caminhos."""
    url = f"{ANS}/{pasta}"
    nomes = _listar(url)
    diag.append(f"[ANS {pasta}] arquivos na pasta: {', '.join(nomes[:30])}")
    da_uf = [n for n in nomes if n.lower().endswith((".zip", ".csv")) and re.search(rf"(^|[_\-.]){uf}([_\-.]|$)", n, re.I)]
    escolhidos = da_uf or [n for n in nomes if n.lower().endswith(".zip") and "dicionario" not in n.lower()][:1]
    if not escolhidos:
        raise RuntimeError(f"não achei arquivo de dados em {url}")
    caminhos = []
    for n in escolhidos:
        caminhos.append(_baixar(f"{url}/{n}", os.path.join(CACHE, "ans", pasta, n)))
    diag.append(f"[ANS {pasta}] usados: {', '.join(escolhidos)}")
    return caminhos


def _linhas_ans(caminhos):
    for cam in caminhos:
        fontes = _csvs_do_zip(cam) if cam.lower().endswith(".zip") else [(os.path.basename(cam), lambda c=cam: open(c, "rb"))]
        for nome, abrir in fontes:
            with abrir() as f:
                cab, linhas = _ler_csv(f)
                yield nome, cab, linhas


def _bate_operadora(cod, nome, cfg):
    if cfg.get("codigos"):
        return _so_digitos(cod) in [_so_digitos(c) for c in cfg["codigos"]]
    alvo = _sem_acento(cfg.get("operadora") or "")
    return bool(alvo) and alvo in _sem_acento(nome)


def rede_ans(cfg, diag):
    """{cnes: dados} dos estabelecimentos da operadora na UF + lista de vínculos hospitalares por plano."""
    uf = cfg["uf"].upper()
    estab, hosp, operadoras = {}, [], {}
    pastas = [("operadoras_e_prestadores_nao_hospitalares", False)]
    if cfg.get("hospitais", True):
        pastas.append(("produtos_e_prestadores_hospitalares", True))
    for pasta, hospitalar in pastas:
        for nome, cab, linhas in _linhas_ans(_arquivos_ans(pasta, uf, diag)):
            diag.append(f"[ANS {nome}] colunas: {' | '.join(cab)}")
            c = {k: _col(cab, *v) for k, v in {
                "op": ("CD_OPERADORA", "REGISTRO_ANS", "REG_ANS"), "nop": ("NM_OPERADORA", "NO_RAZAO", "RAZAO_SOCIAL", "NM_RAZAO_SOCIAL"),
                "cnes": ("CD_CNES", "CNES"), "cnpj": ("CD_CNPJ_ESTB_SAUDE", "CNPJ"), "nome": ("NM_ESTABELECIMENTO_SAUDE", "NO_ESTABELECIMENTO"),
                "clas": ("DE_CLAS_ESTB_SAUDE",), "tipo": ("DE_TIPO_PRESTADOR",), "urg": ("LG_URGENCIA_EMERGENCIA",),
                "contrato": ("DE_TIPO_CONTRATO",), "disp": ("DE_DISPONIBILIDADE",), "mun": ("NM_MUNICIPIO_X", "NM_MUNICIPIO"),
                "codmun": ("CD_MUNICIPIO",), "uf": ("SG_UF", "UF"), "fim": ("DT_VINCULO_OPERADORA_FIM", "DT_VINCULO_FIM"),
                "inicio": ("DT_VINCULO_OPERADORA_INICIO", "DT_VINCULO_INICIO"), "plano": ("CD_PLANO",),
                "contr": ("DE_TIPO_CONTRATACAO", "CONTRATACAO"), "seg": ("SEGMENTACAO_ASSISTENCIAL",),
                "abr": ("DE_TIPO_ABRANGENCIA_GEOGRAFICA",), "sit": ("DE_SITUACAO_PRINCIPAL",)}.items()}
            if c["op"] is None or c["cnes"] is None:
                diag.append(f"  ⚠️ {nome}: sem coluna de operadora ou CNES, pulei")
                continue
            for ln in linhas:
                g = lambda k: (ln[c[k]].strip() if c[k] is not None and c[k] < len(ln) else "")  # noqa: E731
                if g("uf") and g("uf").upper() != uf:
                    continue
                if not _bate_operadora(g("op"), g("nop"), cfg):
                    continue
                if g("fim"):  # vínculo encerrado
                    continue
                operadoras[g("op")] = g("nop")
                cn = _cnes(g("cnes"))
                if not cn:
                    continue
                e = estab.setdefault(cn, {"cnes": cn, "cnpj": _so_digitos(g("cnpj")), "nome_ans": g("nome"),
                                          "classificacao": g("clas"), "tipo_prestador": g("tipo"),
                                          "urgencia": "sim" if g("urg") in ("1", "S", "SIM") else "não",
                                          "contrato": g("contrato"), "disponibilidade": g("disp"), "municipio": g("mun"),
                                          "uf": uf, "inicio_vinculo": g("inicio"), "operadoras": set(), "hospitalar": "não"})
                e["operadoras"].add(g("op"))
                if hospitalar:
                    e["hospitalar"] = "sim"
                    if g("plano"):
                        hosp.append({"cnes": cn, "estabelecimento": g("nome"), "municipio": g("mun"), "operadora": g("op"),
                                     "plano": g("plano"), "contratacao": g("contr"), "segmentacao": g("seg"),
                                     "abrangencia": g("abr"), "situacao_plano": g("sit"), "urgencia": e["urgencia"]})
    diag.append("[ANS] operadoras que bateram com o filtro: " +
                (", ".join(f"{k} {v}" for k, v in sorted(operadoras.items())) or "NENHUMA (confira o nome/código)"))
    return estab, hosp, operadoras


# ------------------------------------------------------------------ CNES
def _zip_cnes(diag):
    hoje = dt.date.today()
    erros = []
    for meses in range(0, 5):
        ano, mes = hoje.year, hoje.month - meses
        while mes <= 0:
            ano, mes = ano - 1, mes + 12
        aaaamm = f"{ano}{mes:02d}"
        url = CNES.replace("{AAAAMM}", aaaamm)
        try:
            cam = _baixar(url, os.path.join(CACHE, "cnes", f"BASE_DE_DADOS_CNES_{aaaamm}.ZIP"), tempo=1800)
            zipfile.ZipFile(cam).namelist()  # confere se é zip de verdade
            diag.append(f"[CNES] base {aaaamm}")
            return cam, aaaamm
        except (urllib.error.HTTPError, urllib.error.URLError, zipfile.BadZipFile, OSError) as e:
            erros.append(f"{aaaamm}: {type(e).__name__}")
            try:
                os.remove(os.path.join(CACHE, "cnes", f"BASE_DE_DADOS_CNES_{aaaamm}.ZIP"))
            except OSError:
                pass
    raise RuntimeError("não consegui baixar a base do CNES (" + "; ".join(erros) + ")")


def detalhes_cnes(cnes_set, uf, com_profissionais, diag):
    """Endereço/telefone/e-mail/geo por CNES + profissionais (nome e CBO) por CNES."""
    cam, aaaamm = _zip_cnes(diag)
    arquivos = {n.lower(): a for n, a in _csvs_do_zip(cam)}
    diag.append(f"[CNES] arquivos: {', '.join(sorted(arquivos)[:40])}")

    def achar(prefixo):
        for n, a in arquivos.items():
            if n.startswith(prefixo.lower()):
                return n, a
        return None, None

    # estabelecimentos
    nome, abrir = achar("tbestabelecimento")
    if not abrir:
        raise RuntimeError("a base do CNES não tem tbEstabelecimento")
    det, unidade_p_cnes = {}, {}
    with abrir() as f:
        cab, linhas = _ler_csv(f)
        diag.append(f"[CNES {nome}] colunas: {' | '.join(cab)}")
        c = {k: _col(cab, *v) for k, v in {
            "un": ("CO_UNIDADE",), "cnes": ("CO_CNES",), "fant": ("NO_FANTASIA",), "razao": ("NO_RAZAO_SOCIAL",),
            "log": ("NO_LOGRADOURO",), "num": ("NU_ENDERECO",), "comp": ("NO_COMPLEMENTO",), "bairro": ("NO_BAIRRO",),
            "cep": ("CO_CEP",), "tel": ("NU_TELEFONE",), "email": ("NO_EMAIL",), "lat": ("NU_LATITUDE",),
            "lon": ("NU_LONGITUDE",), "tipo": ("TP_UNIDADE", "CO_TIPO_UNIDADE"), "uf": ("CO_ESTADO_GESTOR", "CO_UF")}.items()}
        for ln in linhas:
            g = lambda k: (ln[c[k]].strip() if c[k] is not None and c[k] < len(ln) else "")  # noqa: E731
            cn = _cnes(g("cnes"))
            if cn not in cnes_set:
                continue
            if g("un"):
                unidade_p_cnes[g("un")] = cn
            endereco = ", ".join(x for x in (g("log"), g("num"), g("comp")) if x)
            det[cn] = {"nome_fantasia": g("fant"), "razao_social": g("razao"), "endereco": endereco, "bairro": g("bairro"),
                       "cep": g("cep"), "telefone": g("tel"), "email": g("email").lower(), "latitude": g("lat"),
                       "longitude": g("lon"), "tipo_unidade_cod": g("tipo")}
    # tipos de unidade (nome)
    nome_t, abrir_t = achar("tbtipounidade")
    if abrir_t:
        with abrir_t() as f:
            cab, linhas = _ler_csv(f)
            ic, idesc = _col(cab, "CO_TIPO_UNIDADE"), _col(cab, "DS_TIPO_UNIDADE", "NO_TIPO_UNIDADE")
            tipos = {ln[ic].strip(): ln[idesc].strip() for ln in linhas if ic is not None and idesc is not None and len(ln) > max(ic, idesc)}
        for d in det.values():
            d["tipo_unidade"] = tipos.get(d["tipo_unidade_cod"], d["tipo_unidade_cod"])
    profissionais = []
    if com_profissionais:
        ocup = {}
        n_o, abrir_o = achar("tbocupacao")
        if abrir_o:
            with abrir_o() as f:
                cab, linhas = _ler_csv(f)
                ic, idesc = _col(cab, "CO_CBO"), _col(cab, "DS_CBO", "NO_CBO", "DS_OCUPACAO")
                ocup = {ln[ic].strip(): ln[idesc].strip() for ln in linhas if ic is not None and idesc is not None and len(ln) > max(ic, idesc)}
        n_c, abrir_c = achar("tbcargahorariasus")
        vinculos = []
        if abrir_c:
            with abrir_c() as f:
                cab, linhas = _ler_csv(f)
                diag.append(f"[CNES {n_c}] colunas: {' | '.join(cab)}")
                iu, ip, icbo = _col(cab, "CO_UNIDADE"), _col(cab, "CO_PROFISSIONAL_SUS"), _col(cab, "CO_CBO")
                for ln in linhas:
                    if iu is None or ip is None or icbo is None or len(ln) <= max(iu, ip, icbo):
                        continue
                    cn = unidade_p_cnes.get(ln[iu].strip())
                    if cn:
                        vinculos.append((cn, ln[ip].strip(), ln[icbo].strip()))
        quem = {p for _, p, _ in vinculos}
        nomes = {}
        n_p, abrir_p = achar("tbdadosprofissionalsus")
        if abrir_p and quem:
            with abrir_p() as f:
                cab, linhas = _ler_csv(f)
                ip, inome = _col(cab, "CO_PROFISSIONAL_SUS"), _col(cab, "NO_PROFISSIONAL")
                for ln in linhas:
                    if ip is not None and inome is not None and len(ln) > max(ip, inome) and ln[ip].strip() in quem:
                        nomes[ln[ip].strip()] = ln[inome].strip()
        vistos = set()
        for cn, p, cbo in vinculos:
            if (cn, p, cbo) in vistos:
                continue
            vistos.add((cn, p, cbo))
            profissionais.append({"cnes": cn, "profissional": nomes.get(p, ""), "cbo": cbo, "ocupacao": ocup.get(cbo, "")})
        diag.append(f"[CNES] profissionais ligados aos estabelecimentos: {len(profissionais)}")
    return det, profissionais, aaaamm


# ------------------------------------------------------------------ montar, salvar, comparar
def _gravar(caminho, linhas, campos):
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


def config():
    try:
        return {**PADRAO, **json.load(open(os.path.join(DIR, "config.json"), encoding="utf-8"))}
    except (OSError, ValueError):
        return dict(PADRAO)


def salvar_config(novo):
    c = config()
    if novo.get("operadora") is not None:
        c["operadora"] = str(novo["operadora"]).strip()[:60]
    if novo.get("codigos") is not None:
        c["codigos"] = [_so_digitos(x) for x in (novo["codigos"] if isinstance(novo["codigos"], list) else str(novo["codigos"]).split(",")) if _so_digitos(x)]
    if novo.get("uf"):
        uf = str(novo["uf"]).upper().strip()
        if uf not in UF_IBGE:
            raise ValueError("UF inválida")
        c["uf"] = uf
    for k in ("profissionais", "hospitais"):
        if k in novo:
            c[k] = bool(novo[k])
    os.makedirs(DIR, exist_ok=True)
    json.dump(c, open(os.path.join(DIR, "config.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return c


def gerar(cfg=None):
    """Executa tudo. Devolve dict com resumo, caminhos e diferenças."""
    cfg = cfg or config()
    diag = [f"Rede {cfg.get('operadora') or cfg.get('codigos')} · {cfg['uf']} · {time.strftime('%d/%m/%Y %H:%M')}"]
    chave = re.sub(r"\W+", "-", (",".join(cfg["codigos"]) if cfg.get("codigos") else cfg.get("operadora", "op")).lower()).strip("-")
    base = os.path.join(DIR, f"{chave}-{cfg['uf'].lower()}")
    pasta = os.path.join(base, time.strftime("%Y-%m"))
    os.makedirs(pasta, exist_ok=True)
    try:
        estab, hosp, operadoras = rede_ans(cfg, diag)
        det, profs, aaaamm = ({}, [], "") if not estab else detalhes_cnes(set(estab), cfg["uf"], cfg.get("profissionais", True), diag)
    except Exception as e:
        diag.append(f"❌ ERRO: {type(e).__name__}: {e}")
        open(os.path.join(pasta, "DIAGNOSTICO.txt"), "w", encoding="utf-8").write("\n".join(diag))
        raise
    especialidades = {}
    for p in profs:
        if p["ocupacao"]:
            especialidades.setdefault(p["cnes"], set()).add(p["ocupacao"])
    linhas = []
    for cn, e in sorted(estab.items(), key=lambda x: (x[1]["municipio"], x[1]["nome_ans"])):
        d = det.get(cn, {})
        linhas.append({**e, **d, "operadoras": ",".join(sorted(e["operadoras"])),
                       "nome": d.get("nome_fantasia") or e["nome_ans"],
                       "especialidades_no_local": " | ".join(sorted(especialidades.get(cn, [])))[:2000],
                       "achado_no_cnes": "sim" if d else "não"})
    campos = ["cnes", "cnpj", "nome", "razao_social", "tipo_unidade", "classificacao", "hospitalar", "urgencia",
              "endereco", "bairro", "municipio", "uf", "cep", "telefone", "email", "latitude", "longitude",
              "especialidades_no_local", "tipo_prestador", "contrato", "disponibilidade", "inicio_vinculo", "operadoras",
              "achado_no_cnes"]
    _gravar(os.path.join(pasta, "estabelecimentos.csv"), linhas, campos)
    nomes = {x["cnes"]: x["nome"] for x in linhas}
    for p in profs:
        p["estabelecimento"] = nomes.get(p["cnes"], "")
    _gravar(os.path.join(pasta, "profissionais.csv"), profs, ["cnes", "estabelecimento", "profissional", "cbo", "ocupacao"])
    _gravar(os.path.join(pasta, "hospitais_planos.csv"), hosp, ["cnes", "estabelecimento", "municipio", "operadora", "plano",
                                                                 "contratacao", "segmentacao", "abrangencia", "situacao_plano", "urgencia"])
    # diferenças com a execução anterior
    anteriores = sorted(p for p in os.listdir(base) if re.fullmatch(r"\d{4}-\d{2}", p) and p != os.path.basename(pasta))
    entrou, saiu = [], []
    if anteriores:
        try:
            ant = json.load(open(os.path.join(base, anteriores[-1], "resumo.json"), encoding="utf-8")).get("lista", {})
            atual = {x["cnes"]: x["nome"] for x in linhas}
            entrou = [f"{atual[c]} ({c})" for c in atual if c not in ant]
            saiu = [f"{ant[c]} ({c})" for c in ant if c not in atual]
        except (OSError, ValueError):
            pass
    resumo = {"quando": time.strftime("%d/%m/%Y %H:%M"), "uf": cfg["uf"], "operadoras": operadoras,
              "estabelecimentos": len(linhas), "hospitalares": sum(1 for x in linhas if x["hospitalar"] == "sim"),
              "com_telefone": sum(1 for x in linhas if x.get("telefone")), "sem_cnes": sum(1 for x in linhas if x["achado_no_cnes"] == "não"),
              "profissionais": len(profs), "vinculos_planos": len(hosp), "cnes_competencia": aaaamm,
              "entrou": entrou[:300], "saiu": saiu[:300], "pasta": pasta,
              "municipios": dict(sorted({m: sum(1 for x in linhas if x["municipio"] == m) for m in {x["municipio"] for x in linhas}}.items(),
                                         key=lambda kv: -kv[1])[:15]),
              "lista": {x["cnes"]: x["nome"] for x in linhas}}
    json.dump(resumo, open(os.path.join(pasta, "resumo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    diag.append(f"✅ {len(linhas)} estabelecimentos · {len(profs)} profissionais · {len(hosp)} vínculos hospital×plano")
    open(os.path.join(pasta, "DIAGNOSTICO.txt"), "w", encoding="utf-8").write("\n".join(diag))
    return resumo


def texto_resumo(r):
    ops = ", ".join(f"{k} {v}" for k, v in (r.get("operadoras") or {}).items()) or "nenhuma"
    linhas = [f"🏥 Rede credenciada · {r['uf']} · {r['quando']}", f"Operadora(s): {ops}",
              f"• {r['estabelecimentos']} estabelecimentos ({r['hospitalares']} hospitalares)",
              f"• {r['com_telefone']} com telefone · {r['sem_cnes']} sem dados no CNES",
              f"• {r['profissionais']} profissionais nos locais · {r['vinculos_planos']} vínculos hospital × plano",
              f"• Fontes: ANS (dados abertos) + CNES {r.get('cnes_competencia', '')}"]
    if r.get("municipios"):
        linhas.append("Cidades: " + " · ".join(f"{m} {n}" for m, n in list(r["municipios"].items())[:8]))
    if r.get("entrou") or r.get("saiu"):
        linhas.append(f"\n🆕 Entraram {len(r['entrou'])}: " + "; ".join(r["entrou"][:15]) + ("…" if len(r["entrou"]) > 15 else ""))
        linhas.append(f"❌ Saíram {len(r['saiu'])}: " + "; ".join(r["saiu"][:15]) + ("…" if len(r["saiu"]) > 15 else ""))
    linhas.append("\nObs.: profissionais = quem trabalha no local segundo o CNES (pode não atender pelo convênio).")
    return "\n".join(linhas)
