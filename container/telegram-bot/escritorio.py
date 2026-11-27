"""Escritório virtual: cada agente/rotina do Jarvis é um funcionário com mesa, e você organiza o escritório.

Mesas fixas (ligadas ao que acontece de verdade no Jarvis) + mesas que você cria (ex.: "Grupo de benefícios"),
que ficam como "planejadas" até virarem um agente de verdade. Guardado em <config do Claude>/jarvis-escritorio.json.
"""
import json
import os
import re
import threading
import time

CONFIG_DIR = os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))
ARQ = os.path.join(CONFIG_DIR, "jarvis-escritorio.json")
_trava = threading.Lock()

# id: (nome, função, cor, setor). Setores: comando, atendimento, conteudo, consultoria, dev, automacao, crescimento
FIXAS = {
    "jarvis": ("Jarvis", "Gerente: recebe seus pedidos e distribui o trabalho", "#38bdf8", "comando"),
    "juliana": ("Juliana", "Atendimento do WhatsApp", "#4ade80", "atendimento"),
    "pessoal": ("Reginaldo", "Assistente pessoal: e-mail, agenda, compras e roteiros (WhatsApp 2)", "#2dd4bf", "comando"),
    "jogos": ("Designer de jogos", "Banner e vídeo dos jogos do dia", "#facc15", "conteudo"),
    "filmes": ("Editor de vídeo", "Vídeos de filmes e séries", "#f472b6", "conteudo"),
    "n8n": ("Rotinas", "Agenda e dispara as rotinas do n8n", "#34d399", "automacao"),
    "hermes": ("Hermes", "Consultor: pesquisa e segunda opinião", "#ffc45a", "consultoria"),
    "deepseek": ("DeepSeek", "Consultor (IA)", "#9db8ff", "consultoria"),
    "ollama": ("Ollama", "Consultor (IA aberta)", "#bef264", "consultoria"),
    "arquiteto": ("Arquiteto", "Planeja e quebra o trabalho", "#7dd3fc", "dev"),
    "explorador": ("Explorador", "Lê e mapeia o código", "#f0abfc", "dev"),
    "desenvolvedor": ("Desenvolvedor", "Escreve o código", "#93c5fd", "dev"),
    "dba": ("DBA", "Bancos e migrations", "#5eead4", "dev"),
    "android": ("Android", "App Android", "#a3e635", "dev"),
    "designer": ("Designer", "Telas e sites", "#f9a8d4", "dev"),
    "testador": ("Testador", "Testa tudo", "#fdba74", "dev"),
    "revisor": ("Revisor", "Revisa antes de entregar", "#c4b5fd", "dev"),
    "deploy": ("Deploy", "Prepara a publicação", "#fde68a", "dev"),
    "documentador": ("Documentador", "Docs e memória", "#67e8f9", "dev"),
}
# vagas sugeridas (você pode apagar, renomear ou criar outras)
VAGAS = {
    "youtube": ("Canal do YouTube", "Cria, publica e acompanha os vídeos", "#ef4444", "crescimento"),
    "conversao": ("Analista de conversão", "Cruza WhatsApp, YouTube e vendas", "#a78bfa", "crescimento"),
    "redes": ("Redes sociais", "Instagram e Facebook", "#fb7185", "crescimento"),
    "ads": ("Tráfego pago", "Sugere campanhas Google/Meta (gasto só com seu ok)", "#f59e0b", "crescimento"),
    "email": ("E-mail", "Lê e responde e-mails", "#60a5fa", "atendimento"),
}
SETORES = {"comando": "Sala de comando", "atendimento": "Atendimento", "conteudo": "Conteúdo",
           "crescimento": "Crescimento", "automacao": "Automação", "consultoria": "Consultoria", "dev": "Desenvolvimento"}


def _ler():
    try:
        with open(ARQ, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _gravar(d):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = ARQ + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ARQ)


def mesas():
    """Todas as mesas: fixas (com o que você renomeou) + vagas que não foram apagadas + as suas."""
    d = _ler()
    ajustes, apagadas, minhas = d.get("ajustes", {}), set(d.get("apagadas", [])), d.get("minhas", {})
    lista = []
    for mid, (nome, funcao, cor, setor) in FIXAS.items():
        a = ajustes.get(mid, {})
        lista.append({"id": mid, "nome": a.get("nome") or nome, "funcao": a.get("funcao") or funcao,
                      "cor": a.get("cor") or cor, "setor": setor, "tipo": "fixa"})
    for mid, (nome, funcao, cor, setor) in VAGAS.items():
        if mid in apagadas:
            continue
        a = ajustes.get(mid, {})
        lista.append({"id": mid, "nome": a.get("nome") or nome, "funcao": a.get("funcao") or funcao,
                      "cor": a.get("cor") or cor, "setor": a.get("setor") or setor, "tipo": "vaga",
                      "notas": a.get("notas", "")})
    for mid, m in minhas.items():
        lista.append({"id": mid, "nome": m.get("nome", mid), "funcao": m.get("funcao", ""), "cor": m.get("cor", "#94a3b8"),
                      "setor": m.get("setor", "crescimento"), "tipo": "minha", "notas": m.get("notas", "")})
    return lista


def _slug(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40]


def salvar_mesa(dados):
    """Cria ou edita uma mesa. Fixas: só nome/função/cor. Vagas e suas: tudo (nome, função, cor, setor, notas)."""
    mid = str(dados.get("id") or "").strip()
    nome = " ".join(str(dados.get("nome") or "").split())[:40]
    funcao = " ".join(str(dados.get("funcao") or "").split())[:120]
    cor = str(dados.get("cor") or "")
    cor = cor if re.fullmatch(r"#[0-9a-fA-F]{6}", cor) else ""
    setor = dados.get("setor") if dados.get("setor") in SETORES else None
    notas = str(dados.get("notas") or "")[:1000]
    with _trava:
        d = _ler()
        if mid in FIXAS or mid in VAGAS:
            a = d.setdefault("ajustes", {}).setdefault(mid, {})
            for k, v in (("nome", nome), ("funcao", funcao), ("cor", cor)):
                if v:
                    a[k] = v
            if mid in VAGAS:
                if setor:
                    a["setor"] = setor
                a["notas"] = notas
                d["apagadas"] = [x for x in d.get("apagadas", []) if x != mid]
        else:
            if not nome:
                raise ValueError("dê um nome para a mesa")
            mid = mid or _slug(nome) or f"mesa-{int(time.time())}"
            if mid in FIXAS or mid in VAGAS:
                mid += "-2"
            m = d.setdefault("minhas", {}).setdefault(mid, {})
            m.update(nome=nome, funcao=funcao, cor=cor or m.get("cor") or "#94a3b8", setor=setor or m.get("setor") or "crescimento",
                     notas=notas, criada=m.get("criada") or time.strftime("%Y-%m-%d"))
        _gravar(d)
    return mid


def apagar_mesa(mid):
    with _trava:
        d = _ler()
        if mid in FIXAS:
            raise ValueError("essa mesa é de um agente que já trabalha no Jarvis; dá para renomear, não apagar")
        if mid in VAGAS:
            d["apagadas"] = sorted(set(d.get("apagadas", [])) | {mid})
        else:
            d.get("minhas", {}).pop(mid, None)
        _gravar(d)


def _tempo(s):
    s = max(0, int(s))
    return f"{s}s" if s < 60 else f"{s // 60}min" if s < 3600 else f"{s // 3600}h{(s % 3600) // 60:02d}"


def situacao(ctx):
    """Estado de cada mesa a partir do que está acontecendo de verdade.
    ctx: {"rodando", "agentes", "hermes", "hermes_ligado", "ias", "atendimento", "rotinas", "n8n"} (montado no web.py).
    Devolve {id: {"estado": trabalhando|livre|vaga|desligado|ok|erro|atencao, "texto": str}}."""
    agora = time.time()
    st = {}
    rod = ctx.get("rodando") or []
    st["jarvis"] = ({"estado": "trabalhando", "texto": " · ".join(f"📁 {r['projeto']} {_tempo(r.get('segundos', 0))}" for r in rod[:3])}
                    if rod else {"estado": "livre", "texto": "esperando seus pedidos"})
    at = ctx.get("atendimento") or {}
    try:
        import atendente
        coach = atendente.ocupado(1) or atendente.ocupado(2)
    except Exception:  # noqa: BLE001
        coach = False
    if not at.get("configurado"):
        st["juliana"] = {"estado": "desligado", "texto": "WhatsApp não configurado"}
    elif coach:
        st["juliana"] = {"estado": "trabalhando", "texto": "conversando com você (treino)"}
    else:
        esperando = at.get("aguardando") or []
        recente = agora - (at.get("ultimo_t") or 0) < 120
        texto = f"{at.get('mensagens_hoje', 0)} mensagens hoje · {at.get('respostas_hoje', 0)} respostas"
        if esperando:
            st["juliana"] = {"estado": "atencao", "texto": f"🙋 {len(esperando)} cliente(s) esperando você · " + texto}
        elif not at.get("ligado", True):
            st["juliana"] = {"estado": "desligado", "texto": "robô pausado"}
        else:
            st["juliana"] = {"estado": "trabalhando" if recente else "livre", "texto": texto}
    try:
        import jogos
        js = jogos.STATUS
        st["jogos"] = ({"estado": "trabalhando", "texto": f"montando banner e vídeo · {_tempo(agora - js['desde'])}"}
                       if js.get("rodando") else
                       {"estado": "livre", "texto": "último: " + time.strftime("%d/%m %H:%M", time.localtime(js["ultimo"]))
                        if js.get("ultimo") else "esperando a rotina do dia"})
    except Exception:  # noqa: BLE001
        st["jogos"] = {"estado": "livre", "texto": ""}
    try:
        import filmes
        t = filmes.TRABALHO
        st["filmes"] = ({"estado": "trabalhando", "texto": f"{t.get('titulo') or 'vídeo'}: {t.get('etapa') or 'editando'}"}
                        if t.get("rodando") else {"estado": "erro" if t.get("erro") else "livre",
                                                  "texto": t.get("erro") or (f"último: {t['titulo']}" if t.get("titulo") else "livre")})
    except Exception:  # noqa: BLE001
        st["filmes"] = {"estado": "livre", "texto": ""}
    rs = ctx.get("rotinas") or []
    curso = [r for r in rs if r.get("ok") is None]
    st["n8n"] = ({"estado": "desligado", "texto": "rotinas desligadas"} if not ctx.get("n8n") else
                 {"estado": "trabalhando", "texto": "rodando: " + ", ".join(r.get("rotina", "") for r in curso[:2])} if curso else
                 {"estado": "livre", "texto": (f"última: {rs[0].get('rotina')} {'✅' if rs[0].get('ok') else '❌'}" if rs else "nenhuma rotina ainda")})
    st["hermes"] = ({"estado": "desligado", "texto": "desligado"} if not ctx.get("hermes_ligado") else
                    {"estado": "trabalhando" if ctx.get("hermes") else "livre", "texto": "atendendo um pedido" if ctx.get("hermes") else "disponível"})
    ias = set(ctx.get("ias") or [])
    for n in ("deepseek", "ollama"):
        ligado = bool(os.environ.get(f"{n.upper()}_API_KEY"))
        st[n] = ({"estado": "trabalhando", "texto": "respondendo uma consulta"} if n in ias else
                 {"estado": "livre" if ligado else "desligado", "texto": "disponível" if ligado else "sem chave"})
    try:
        import pessoal
        at_p = pessoal.atividade()
        import reginaldo
        if reginaldo.ocupado():
            st["pessoal"] = {"estado": "trabalhando", "texto": at_p.get("acao") or "atendendo você"}
        elif not os.environ.get("COFRE_TOKEN"):
            st["pessoal"] = {"estado": "desligado", "texto": "cofre não ligado (./cofre-configurar.sh)"}
        elif agora - (at_p.get("t") or 0) < 90:
            st["pessoal"] = {"estado": "trabalhando", "texto": at_p.get("acao") or "trabalhando"}
        else:
            st["pessoal"] = {"estado": "livre", "texto": "pronto para e-mail, agenda e listas"}
    except Exception:  # noqa: BLE001
        pass
    for n, a in (ctx.get("agentes") or {}).items():
        if n in FIXAS:
            if a.get("estado") == "ativo":
                st[n] = {"estado": "trabalhando", "texto": (a.get("acao") or a.get("descricao") or "trabalhando…")[:90]
                         + (f" · 📁 {a['projeto']}" if a.get("projeto") else "")}
            else:
                st[n] = {"estado": a.get("estado", "ok"), "texto": ("✓ concluiu: " if a.get("estado") == "ok" else "✕ ")
                         + (a.get("descricao") or "")[:80]}
    for m in mesas():
        if m["id"] not in st:
            st[m["id"]] = ({"estado": "vaga", "texto": "vaga: ainda não contratado"} if m["tipo"] != "fixa"
                           else {"estado": "livre", "texto": "livre"})
    return st
