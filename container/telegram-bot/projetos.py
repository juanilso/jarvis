"""Gestão de projetos para o painel: criar, receber uploads e integrar com o GitHub (via gh + GH_TOKEN)."""
import io
import json
import os
import re
import shutil
import subprocess
import zipfile

import jarvis_core as core

NOME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
IGNORAR_ZIP = ("__MACOSX/", ".DS_Store")
LIMITE_UPLOAD = 300 * 1024 * 1024


class Erro(Exception):
    pass


def _pasta(nome):
    if not nome or not NOME_OK.match(nome):
        raise Erro("Nome inválido. Use letras, números, ponto, hífen ou sublinhado (sem espaços).")
    return os.path.join(core.WORKSPACE, nome)


def _rodar(cmd, cwd=None, timeout=120, entrada=None):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env, input=entrada)
    if r.returncode != 0:
        raise Erro((r.stderr or r.stdout or "falhou").strip()[-1500:])
    return r.stdout.strip()


# ------------------------------------------------------------------ git com identidade e credencial do gh
_ident = {}


def _identidade():
    if not _ident:
        nome = os.environ.get("GIT_NOME", "").strip()
        email = os.environ.get("GIT_EMAIL", "").strip()
        if (not nome or not email) and gh_ok():
            try:
                u = json.loads(_rodar(["gh", "api", "user"], timeout=20))
                nome = nome or u.get("name") or u["login"]
                email = email or f"{u['id']}+{u['login']}@users.noreply.github.com"
            except Exception:  # noqa: BLE001
                pass
        _ident.update(nome=nome or "Jarvis", email=email or "jarvis@localhost")
    return _ident


def git(pasta, *args, timeout=120):
    i = _identidade()
    base = ["git", "-c", "safe.directory=*", "-c", f"user.name={i['nome']}", "-c", f"user.email={i['email']}",
            "-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential", "-c", "init.defaultBranch=main"]
    return _rodar(base + list(args), cwd=pasta, timeout=timeout)


def gh_ok():
    return bool(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")) and shutil.which("gh") is not None


# ------------------------------------------------------------------ projetos
def criar(nome, iniciar_git=True):
    pasta = _pasta(nome)
    if os.path.exists(pasta):
        raise Erro("Já existe um projeto com esse nome.")
    try:
        os.makedirs(pasta)
    except PermissionError:
        raise Erro("Sem permissão para criar a pasta em /workspace. Na VPS rode: "
                   "docker compose exec -u root dev chown -R dev:dev /workspace") from None
    if iniciar_git:
        git(pasta, "init")
        with open(os.path.join(pasta, "README.md"), "w", encoding="utf-8") as f:
            f.write(f"# {nome}\n")
    return pasta


def receber_upload(nome, nome_arquivo, dados, criar_se_nao_existir=True):
    """Salva um arquivo no projeto; .zip é extraído (se tiver uma única pasta raiz, ela é achatada)."""
    if len(dados) > LIMITE_UPLOAD:
        raise Erro("Arquivo maior que 300 MB.")
    pasta = _pasta(nome)
    novo = not os.path.isdir(pasta)
    if novo:
        if not criar_se_nao_existir:
            raise Erro("Projeto não encontrado.")
        criar(nome, iniciar_git=False)
    nome_arquivo = os.path.basename(nome_arquivo or "arquivo")
    if nome_arquivo.lower().endswith(".zip"):
        try:
            z = zipfile.ZipFile(io.BytesIO(dados))
        except zipfile.BadZipFile:
            raise Erro("O .zip está corrompido.") from None
        membros = [m for m in z.infolist()
                   if not any(m.filename.startswith(p) or m.filename.endswith(p) for p in IGNORAR_ZIP)
                   and not m.filename.startswith("/") and ".." not in m.filename.split("/")]
        raizes = {m.filename.split("/")[0] for m in membros if m.filename.strip("/")}
        prefixo = (next(iter(raizes)) + "/") if len(raizes) == 1 and any("/" in m.filename for m in membros) else ""
        base = os.path.realpath(pasta)
        total = 0
        for m in membros:
            rel = m.filename[len(prefixo):] if prefixo and m.filename.startswith(prefixo) else m.filename
            if not rel or rel.endswith("/"):
                continue
            destino = os.path.realpath(os.path.join(base, rel))
            if not destino.startswith(base + os.sep):
                continue  # ignora caminhos maliciosos (../)
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with z.open(m) as src, open(destino, "wb") as dst:
                shutil.copyfileobj(src, dst)
            total += 1
        msg = f"{total} arquivo(s) extraído(s) em {nome}"
    else:
        with open(os.path.join(pasta, nome_arquivo), "wb") as f:
            f.write(dados)
        msg = f"{nome_arquivo} salvo em {nome}"
    if not os.path.isdir(os.path.join(pasta, ".git")):
        git(pasta, "init")
    return msg + (" (projeto novo)" if novo else "")


# ------------------------------------------------------------------ GitHub
def gh_repos():
    if not gh_ok():
        raise Erro("GitHub não configurado: coloque GH_TOKEN no .env.claude.")
    saida = _rodar(["gh", "repo", "list", "--limit", "100", "--json", "nameWithOwner,isPrivate,updatedAt,description"], timeout=40)
    return json.loads(saida or "[]")


def clonar(repo, nome=None):
    if not gh_ok():
        raise Erro("GitHub não configurado: coloque GH_TOKEN no .env.claude.")
    if not re.match(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", repo or ""):
        raise Erro("Informe o repositório como dono/nome.")
    nome = nome or repo.split("/")[1]
    pasta = _pasta(nome)
    if os.path.exists(pasta):
        raise Erro(f"Já existe a pasta {nome} em /workspace.")
    _rodar(["gh", "repo", "clone", repo, pasta], timeout=600)
    return nome


def status(nome):
    pasta = _pasta(nome)
    if not os.path.isdir(os.path.join(pasta, ".git")):
        return {"git": False, "gh": gh_ok()}
    st = {"git": True, "gh": gh_ok(), "remoto": None, "url": None, "branch": None,
          "alteracoes": 0, "afrente": 0, "atras": 0, "commits": 0}
    try:
        st["branch"] = git(pasta, "rev-parse", "--abbrev-ref", "HEAD")
        st["commits"] = int(git(pasta, "rev-list", "--count", "HEAD"))
    except Erro:
        st["branch"] = "main"
    st["alteracoes"] = len([l for l in git(pasta, "status", "--porcelain").splitlines() if l.strip()])
    try:
        st["remoto"] = git(pasta, "remote", "get-url", "origin")
        m = re.search(r"github\.com[:/](.+?)(\.git)?$", st["remoto"])
        st["url"] = f"https://github.com/{m.group(1)}" if m else None
        if st["gh"]:
            try:
                git(pasta, "fetch", "--quiet", "origin", timeout=30)
            except Erro:
                pass
        ab = git(pasta, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
        st["afrente"], st["atras"] = (int(x) for x in ab.split())
    except Erro:
        pass
    return st


def _commit_tudo(pasta, mensagem):
    if git(pasta, "status", "--porcelain"):
        git(pasta, "add", "-A")
        git(pasta, "commit", "-m", mensagem or "Atualização pelo painel Jarvis")
        return True
    return False


def criar_repo(nome, privado=True):
    if not gh_ok():
        raise Erro("GitHub não configurado: coloque GH_TOKEN no .env.claude.")
    pasta = _pasta(nome)
    if not os.path.isdir(os.path.join(pasta, ".git")):
        git(pasta, "init")
    _commit_tudo(pasta, "Projeto inicial")
    try:
        git(pasta, "remote", "get-url", "origin")
        raise Erro("Este projeto já tem um repositório remoto (origin).")
    except Erro as e:
        if "já tem" in str(e):
            raise
    _rodar(["gh", "repo", "create", nome, "--private" if privado else "--public", "--source", pasta,
            "--remote", "origin", "--push"], cwd=pasta, timeout=180)
    return status(nome)


def enviar(nome, mensagem):
    pasta = _pasta(nome)
    try:
        git(pasta, "remote", "get-url", "origin")
    except Erro:
        raise Erro("Este projeto ainda não tem repositório no GitHub. Use “Criar repositório”.") from None
    commitou = _commit_tudo(pasta, mensagem)
    git(pasta, "push", "-u", "origin", "HEAD", timeout=300)
    return ("Alterações salvas e " if commitou else "") + "enviado para o GitHub."


def atualizar(nome):
    pasta = _pasta(nome)
    saida = git(pasta, "pull", "--ff-only", timeout=300)
    return saida.splitlines()[-1] if saida else "Já estava atualizado."
