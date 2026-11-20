"""Base de conhecimento do Jarvis: notas em Markdown (compatíveis com Obsidian) num repositório
privado do GitHub (jarvis-conhecimento), com sincronização automática. Nada se perde se a VPS sumir."""
import os
import re
import threading
import time
import unicodedata

import jarvis_core as core
import projetos

KB_DIR = os.environ.get("JARVIS_KB_DIR") or os.path.join(core.WORKSPACE, ".jarvis-conhecimento")
KB_REPO = os.environ.get("JARVIS_KB_REPO", "jarvis-conhecimento")
TIPOS = {"ideias": "💡", "pesquisas": "🔎", "decisoes": "⚖️", "aprendizados": "📚", "projetos": "📁"}
_lock = threading.Lock()

LEIA_ME = """# Base de conhecimento do Jarvis

Notas em Markdown, compatíveis com o Obsidian (abra esta pasta como um "vault").

- `ideias/`: ideias capturadas (/ideia, por texto ou áudio)
- `pesquisas/`: pesquisas na internet com as fontes (/pesquisar)
- `decisoes/`: decisões técnicas e de negócio
- `aprendizados/`: o que funcionou, o que não funcionou e por quê
- `projetos/`: uma página por projeto, com resumo, stack e links

Toda alteração é salva automaticamente no GitHub.
"""


def slug(texto, n=50):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:n] or "nota"


def garantir():
    """Cria a base (ou clona do GitHub se já existir lá) e deixa o remoto configurado."""
    with _lock:
        if os.path.isdir(os.path.join(KB_DIR, ".git")):
            return KB_DIR
        if projetos.gh_ok():
            try:
                projetos._rodar(["gh", "repo", "view", KB_REPO, "--json", "name"], timeout=30)
                projetos._rodar(["gh", "repo", "clone", KB_REPO, KB_DIR], timeout=300)
                return KB_DIR
            except projetos.Erro:
                pass
        os.makedirs(KB_DIR, exist_ok=True)
        for t in TIPOS:
            os.makedirs(os.path.join(KB_DIR, t), exist_ok=True)
            open(os.path.join(KB_DIR, t, ".gitkeep"), "a").close()
        with open(os.path.join(KB_DIR, "README.md"), "w", encoding="utf-8") as f:
            f.write(LEIA_ME)
        projetos.git(KB_DIR, "init")
        projetos.git(KB_DIR, "add", "-A")
        projetos.git(KB_DIR, "commit", "-m", "Base de conhecimento do Jarvis")
        if projetos.gh_ok():
            try:
                projetos._rodar(["gh", "repo", "create", KB_REPO, "--private", "--source", KB_DIR,
                                 "--remote", "origin", "--push"], cwd=KB_DIR, timeout=180)
            except projetos.Erro as e:
                print("não consegui criar o repositório da base:", e, flush=True)
        return KB_DIR


def sincronizar():
    """Salva alterações pendentes (inclusive as escritas pelo Claude) e envia ao GitHub."""
    with _lock:
        if not os.path.isdir(os.path.join(KB_DIR, ".git")):
            return "sem base"
        try:
            if projetos.git(KB_DIR, "status", "--porcelain"):
                projetos.git(KB_DIR, "add", "-A")
                projetos.git(KB_DIR, "commit", "-m", "Atualização da base de conhecimento")
            if projetos.gh_ok():
                try:
                    projetos.git(KB_DIR, "remote", "get-url", "origin")
                except projetos.Erro:
                    return "sem remoto"
                try:
                    projetos.git(KB_DIR, "pull", "--rebase", "--autostash", "origin", "HEAD", timeout=120)
                except projetos.Erro:
                    pass
                projetos.git(KB_DIR, "push", "-u", "origin", "HEAD", timeout=180)
                return "ok"
            return "sem remoto"
        except projetos.Erro as e:
            print("erro ao sincronizar a base:", e, flush=True)
            return str(e)


def sincronizar_depois():
    threading.Thread(target=sincronizar, daemon=True).start()


def iniciar_sincronizacao_periodica(minutos=10):
    def laco():
        while True:
            time.sleep(minutos * 60)
            sincronizar()
    threading.Thread(target=laco, daemon=True).start()


def salvar(tipo, titulo, corpo, tags=(), fontes=(), projeto=None):
    garantir()
    tipo = tipo if tipo in TIPOS else "ideias"
    data = time.strftime("%Y-%m-%d")
    nome = f"{data}-{slug(titulo)}.md"
    caminho = os.path.join(KB_DIR, tipo, nome)
    i = 2
    while os.path.exists(caminho):
        caminho = os.path.join(KB_DIR, tipo, f"{data}-{slug(titulo)}-{i}.md")
        i += 1
    cab = ["---", f"titulo: \"{titulo.replace(chr(34), '')}\"", f"tipo: {tipo}", f"data: {time.strftime('%Y-%m-%d %H:%M')}"]
    if projeto:
        cab.append(f"projeto: \"[[{projeto}]]\"")
    if tags:
        cab.append("tags: [" + ", ".join(tags) + "]")
    cab.append("---")
    texto = "\n".join(cab) + f"\n\n# {titulo}\n\n{corpo.strip()}\n"
    if fontes:
        texto += "\n## Fontes\n" + "\n".join(f"- {f}" for f in fontes) + "\n"
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)
    sincronizar_depois()
    return os.path.relpath(caminho, KB_DIR)


def _notas():
    if not os.path.isdir(KB_DIR):
        return []
    saida = []
    for raiz, pastas, arqs in os.walk(KB_DIR):
        pastas[:] = [p for p in pastas if not p.startswith(".")]
        for a in arqs:
            if a.endswith(".md") and a != "README.md":
                saida.append(os.path.join(raiz, a))
    return saida


def _titulo(texto, caminho):
    m = re.search(r'^titulo:\s*"?(.*?)"?\s*$', texto, re.M) or re.search(r"^#\s+(.+)$", texto, re.M)
    return m.group(1).strip() if m else os.path.basename(caminho)[:-3]


def buscar(consulta, limite=8):
    termos = [slug(t, 40) for t in re.findall(r"\w{3,}", consulta.lower())]
    termos = [t for t in termos if t]
    res = []
    for c in _notas():
        try:
            texto = open(c, encoding="utf-8").read()
        except OSError:
            continue
        norm = slug(texto, 10**9).replace("-", " ")
        pontos = sum(norm.count(t.replace("-", " ")) for t in termos)
        if not termos or pontos:
            pos = min([norm.find(t.replace("-", " ")) for t in termos if t.replace("-", " ") in norm] or [0])
            corpo = re.sub(r"^---.*?---", "", texto, flags=re.S).strip()
            trecho = re.sub(r"\s+", " ", corpo)[max(0, pos - 80): pos + 220]
            res.append({"caminho": os.path.relpath(c, KB_DIR), "titulo": _titulo(texto, c), "pontos": pontos,
                        "trecho": trecho, "data": os.path.getmtime(c)})
    res.sort(key=lambda r: (-r["pontos"], -r["data"]))
    return res[:limite]


def recentes(tipo=None, limite=20):
    notas = [c for c in _notas() if not tipo or os.path.relpath(c, KB_DIR).startswith(tipo + "/")]
    notas.sort(key=os.path.getmtime, reverse=True)
    out = []
    for c in notas[:limite]:
        texto = open(c, encoding="utf-8").read()
        out.append({"caminho": os.path.relpath(c, KB_DIR), "titulo": _titulo(texto, c), "data": os.path.getmtime(c)})
    return out


def ler(caminho_rel):
    base = os.path.realpath(KB_DIR)
    c = os.path.realpath(os.path.join(base, caminho_rel))
    if not c.startswith(base + os.sep) or not c.endswith(".md") or not os.path.isfile(c):
        raise projetos.Erro("Nota não encontrada.")
    return open(c, encoding="utf-8").read()


def prompt_pesquisa(tema):
    garantir()
    destino = os.path.join(KB_DIR, "pesquisas", f"{time.strftime('%Y-%m-%d')}-{slug(tema)}.md")
    return destino, (
        f"Pesquise na internet sobre: {tema}\n\n"
        "Use a ferramenta WebSearch; se ela não estiver disponível ou falhar, use no terminal "
        "`jarvis-busca \"termos\"` para buscar e `jarvis-busca --ler URL` (ou WebFetch) para ler as páginas. "
        "Consulte de 3 a 6 fontes confiáveis e recentes.\n\n"
        f"Depois, crie o arquivo {destino} em Markdown com este cabeçalho:\n"
        f"---\ntitulo: \"{tema}\"\ntipo: pesquisas\ndata: {time.strftime('%Y-%m-%d %H:%M')}\ntags: [pesquisa]\n---\n"
        "e as seções: Resumo (5 a 10 linhas), Pontos principais, O que isso significa para os meus projetos, "
        "e Fontes (lista com título e link de cada fonte). Escreva em português.\n"
        "Na resposta, mostre só o Resumo e diga onde a nota foi salva."
    )
