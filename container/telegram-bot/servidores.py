"""Acesso do Jarvis aos servidores (SSH, SFTP e MySQL/MariaDB), para homologar e corrigir na hora.

Regras de segurança (fixas no código, não dependem do modelo obedecer):
- Credenciais só em /segredos-servidores (volume próprio, modo 600). Nunca no repositório, no log ou no Telegram;
  qualquer senha que apareça numa saída é apagada antes de mostrar.
- Servidor de HOMOLOGAÇÃO: pode ler e alterar, com backup automático antes (arquivo substituído → cópia no próprio
  servidor em ~/.jarvis-backup/<data>/; SQL que altera dados → dump das tabelas em /workspace/.jarvis-backups/).
- Servidor de PRODUÇÃO: somente leitura (comandos de consulta, SELECT/SHOW, download). Enviar arquivo é bloqueado.
- DROP DATABASE e comandos destrutivos amplos (rm -rf /, mkfs, shutdown…) são bloqueados em qualquer ambiente.
- Toda ação vai para a auditoria (/servidores no Telegram/painel), sem senhas.
"""
import datetime
import getpass
import gzip
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time

DIR = os.environ.get("JARVIS_SERVIDORES_DIR", "/segredos-servidores")
ARQ = os.path.join(DIR, "servidores.json")
CHAVE = os.path.join(DIR, "jarvis_ed25519")
HOSTS = os.path.join(DIR, "known_hosts")
AUDITORIA = os.path.join(DIR, "auditoria.jsonl")
WORKSPACE = os.environ.get("JARVIS_WORKSPACE") or os.environ.get("WORKSPACE") or "/workspace"
BACKUPS = os.path.join(WORKSPACE, ".jarvis-backups")
BAIXADOS = os.path.join(WORKSPACE, ".jarvis-servidores")
MAX_SAIDA = 20000


class Erro(Exception):
    pass


# ------------------------------------------------------------ cadastro

def _ler():
    try:
        with open(ARQ, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _gravar(dados):
    os.makedirs(DIR, mode=0o700, exist_ok=True)
    tmp = ARQ + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ARQ)
    os.chmod(ARQ, 0o600)


def servidor(nome):
    s = _ler().get(nome)
    if not s:
        disp = ", ".join(_ler()) or "nenhum (configure na VPS: ./servidores-configurar.sh)"
        raise Erro(f"servidor “{nome}” não cadastrado. Disponíveis: {disp}")
    return {"nome": nome, "porta": 22, "ambiente": "homologacao", **s}


def publico(s):
    """Dados que podem aparecer (sem senhas)."""
    db = s.get("db") or {}
    return {"nome": s["nome"], "ambiente": s["ambiente"], "host": s["host"], "porta": s["porta"], "usuario": s["usuario"],
            "acesso": "senha" if s.get("senha") else "chave do Jarvis", "pasta": s.get("pasta", ""),
            "projeto": s.get("projeto", ""),
            "banco": (f"{db.get('banco', '')} ({db.get('usuario', '')}@{db.get('host', '127.0.0.1')}"
                      f"{', por túnel SSH' if db.get('via_ssh', True) else ''})") if db else ""}


def listar():
    return [publico({"nome": n, "porta": 22, "ambiente": "homologacao", **s}) for n, s in _ler().items()]


def _segredos(s):
    return [x for x in (s.get("senha"), (s.get("db") or {}).get("senha")) if x]


def _esconder(texto, s):
    for seg in _segredos(s):
        texto = texto.replace(seg, "[senha]")
    return texto


def _auditar(s, acao, detalhe, ok, extra=None):
    try:
        os.makedirs(DIR, mode=0o700, exist_ok=True)
        reg = {"quando": datetime.datetime.now().isoformat(timespec="seconds"), "servidor": s["nome"],
               "ambiente": s["ambiente"], "acao": acao, "detalhe": _esconder(detalhe, s)[:400], "ok": ok, **(extra or {})}
        fd = os.open(AUDITORIA, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    except OSError:
        pass


def auditoria(n=15):
    try:
        with open(AUDITORIA, encoding="utf-8") as f:
            return [json.loads(x) for x in f.readlines()[-n:]]
    except FileNotFoundError:
        return []


# ------------------------------------------------------------ travas

PERIGOSO = re.compile(r"(\brm\s+-[a-z]*r[a-z]*f?[a-z]*\s+(/|~|\*|/\*)(\s|$)|\bmkfs|\bdd\s+if=|\bshutdown\b|\breboot\b|"
                      r"\bhalt\b|\bpoweroff\b|:\(\)\s*\{|\bchmod\s+-R\s+777\s+/(\s|$)|\buserdel\b|\bpasswd\b)", re.I)
LEITURA_CMD = {"ls", "ll", "cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "zgrep", "zcat", "find",
               "stat", "file", "du", "df", "free", "uptime", "ps", "top", "wc", "sort", "uniq", "cut", "awk", "sed", "tr",
               "whoami", "id", "pwd", "hostname", "date", "uname", "which", "echo", "printf", "journalctl",
               "systemctl", "service", "git", "php", "node", "python3", "composer", "nginx", "apache2ctl", "mysql",
               "mariadb", "md5sum", "sha256sum", "diff", "tree", "basename", "dirname", "realpath", "readlink", "test",
               "netstat", "ss", "lsof", "crontab", "docker", "pm2", "curl"}
LEITURA_SUB = {"systemctl": r"(status|is-active|is-enabled|list-units|list-timers|show|cat)\b",
               "service": r"\S+\s+status\b", "git": r"(status|log|diff|show|branch|remote|rev-parse|describe|ls-files|blame)\b",
               "php": r"(-v|-m|-i|-l|--version|--ini)\b", "node": r"(-v|--version)\b", "python3": r"(-V|--version)\b",
               "composer": r"(show|outdated|validate|--version|diagnose)\b", "nginx": r"(-t|-T|-v|-V)\b",
               "apache2ctl": r"(-t|-S|-M|-v)\b", "crontab": r"-l\b",
               "docker": r"(ps|logs|images|inspect|stats --no-stream|version)\b", "pm2": r"(list|ls|status|logs|show)\b",
               "sed": r"-n\b", "find": r"(?!.*(-delete|-exec|-execdir|-ok)\b)", "curl": r"(?!.*(-X\s*(POST|PUT|DELETE|PATCH)|--data|-d\s|-F\s|-T\s|-o\s|-O\b))",
               "mysql": r"(?!.*)", "mariadb": r"(?!.*)", "awk": r"(?!.*system\s*\()"}


def checar_ssh(s, cmd):
    if PERIGOSO.search(cmd):
        raise Erro("comando destrutivo bloqueado em qualquer servidor (peça ao usuário para fazer manualmente)")
    if s["ambiente"] != "producao":
        return
    if re.search(r"`|\$\(|(?<![0-9&])>(?!&)|>>|\btee\b|<\(", re.sub(r"\d?>\s*/dev/null|2>&1", "", cmd)):
        raise Erro("PRODUÇÃO é só leitura: redirecionamento/subcomando não permitido")
    for parte in re.split(r"\|\||&&|;|\|", cmd):
        palavras = parte.strip().split(None, 1)
        if not palavras:
            continue
        p0 = palavras[0].lstrip("(").rsplit("/", 1)[-1]
        if p0 == "sudo" or p0 not in LEITURA_CMD:
            raise Erro(f"PRODUÇÃO é só leitura: “{p0}” não está na lista de comandos de consulta")
        regra = LEITURA_SUB.get(p0)
        if regra and not re.match(regra, palavras[1] if len(palavras) > 1 else ""):
            raise Erro(f"PRODUÇÃO é só leitura: “{parte.strip()[:60]}” pode alterar algo")
        if p0 == "sed" and re.search(r"\s-i", parte):
            raise Erro("PRODUÇÃO é só leitura: sed -i altera arquivo")


SQL_LEITURA = re.compile(r"^\s*(select|show|describe|desc|explain|with|use|help)\b", re.I)
SQL_TABELA = re.compile(r"\b(?:update(?:\s+(?:low_priority|ignore))*|delete\s+(?:\w+\s+)*?from|insert(?:\s+(?:ignore|into))+|"
                        r"replace(?:\s+into)?|alter\s+table|drop\s+table(?:\s+if\s+exists)?|truncate(?:\s+table)?|"
                        r"rename\s+table|create\s+(?:or\s+replace\s+)?(?:temporary\s+)?table(?:\s+if\s+not\s+exists)?|"
                        r"create\s+(?:unique\s+|fulltext\s+)?index\s+\w+\s+on|drop\s+index\s+\w+\s+on)\s+"
                        r"[`\"]?(?:\w+[`\"]?\.[`\"]?)?(\w+)", re.I)


def _sem_comentarios(sql):
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return re.sub(r"(?m)(--\s|#).*$", " ", sql)


def _comandos_sql(sql):
    return [c.strip() for c in re.split(r";\s*(?=(?:[^'\"]|'[^']*'|\"[^\"]*\")*$)", _sem_comentarios(sql)) if c.strip()]


def checar_sql(s, sql):
    """Devolve as tabelas que serão alteradas (para o backup). Bloqueia o que não pode."""
    cmds = _comandos_sql(sql)
    if not cmds:
        raise Erro("SQL vazio")
    if re.search(r"\b(drop\s+(database|schema)|into\s+(out|dump)file|load_file\s*\(|grant\b|revoke\b|"
                 r"create\s+user|drop\s+user|alter\s+user|set\s+password)", " ".join(cmds), re.I):
        raise Erro("comando bloqueado (DROP DATABASE, arquivos do servidor, usuários e permissões): faça manualmente")
    escrita = [c for c in cmds if not SQL_LEITURA.match(c)]
    if escrita and s["ambiente"] == "producao":
        raise Erro("PRODUÇÃO é só leitura: só SELECT, SHOW, DESCRIBE e EXPLAIN")
    tabelas = []
    for c in escrita:
        m = SQL_TABELA.search(c)
        tabelas.append(m.group(1) if m else "*")
    return escrita, sorted(set(tabelas))


# ------------------------------------------------------------ SSH / SCP

def _opcoes(s, scp=False):
    o = ["-P" if scp else "-p", str(s["porta"]), "-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={HOSTS}",
         "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=20", "-o", "LogLevel=ERROR"]
    if s.get("senha"):
        o += ["-o", "PreferredAuthentications=password,keyboard-interactive", "-o", "PubkeyAuthentication=no"]
    else:
        o += ["-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-i", CHAVE]
    return o


def _rodar(s, args, timeout=300, entrada=None):
    env = dict(os.environ)
    if s.get("senha"):
        if not shutil.which("sshpass"):
            raise Erro("acesso por senha precisa do sshpass (atualize a imagem: docker compose build)")
        args = ["sshpass", "-e"] + args
        env["SSHPASS"] = s["senha"]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env, input=entrada)
    except subprocess.TimeoutExpired:
        raise Erro(f"tempo esgotado ({timeout}s)")
    except FileNotFoundError as e:
        raise Erro(f"programa ausente: {e.filename} (atualize a imagem: docker compose build)")
    saida = _esconder((r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr.strip() else ""), s)
    if len(saida) > MAX_SAIDA:
        saida = saida[:MAX_SAIDA // 2] + f"\n… ({len(saida) - MAX_SAIDA} caracteres omitidos) …\n" + saida[-MAX_SAIDA // 2:]
    return r.returncode, saida


def ssh(nome, cmd, timeout=300):
    s = servidor(nome)
    checar_ssh(s, cmd)
    if s.get("pasta") and not cmd.lstrip().startswith("cd "):
        cmd = f"cd {shlex.quote(s['pasta'])} 2>/dev/null; {cmd}"
    code, saida = _rodar(s, ["ssh"] + _opcoes(s) + [f"{s['usuario']}@{s['host']}", cmd], timeout)
    _auditar(s, "ssh", cmd, code == 0)
    return code, saida


def _remoto(s, caminho):
    if not caminho.startswith(("/", "~")) and s.get("pasta"):
        caminho = s["pasta"].rstrip("/") + "/" + caminho
    return caminho


def baixar(nome, remoto, local=None):
    s = servidor(nome)
    remoto = _remoto(s, remoto)
    local = local or os.path.join(BAIXADOS, nome, remoto.lstrip("/~"))
    os.makedirs(os.path.dirname(os.path.abspath(local)) or ".", exist_ok=True)
    code, saida = _rodar(s, ["scp", "-r", "-p"] + _opcoes(s, True) + [f"{s['usuario']}@{s['host']}:{shlex.quote(remoto)}", local])
    _auditar(s, "baixar", remoto, code == 0)
    if code:
        raise Erro("não consegui baixar: " + saida[-500:])
    return local


def enviar(nome, local, remoto):
    s = servidor(nome)
    if s["ambiente"] == "producao":
        _auditar(s, "enviar", remoto, False, {"bloqueado": True})
        raise Erro("PRODUÇÃO é só leitura: o Jarvis não envia arquivos para produção (o deploy é com você)")
    if not os.path.exists(local):
        raise Erro(f"arquivo local não existe: {local}")
    remoto = _remoto(s, remoto)
    marca = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    q = shlex.quote(remoto)
    bkp = f"~/.jarvis-backup/{marca}"
    cmd_bkp = (f"if [ -e {q} ]; then mkdir -p {bkp}/$(dirname {q} | sed 's#^/##') && cp -rp {q} {bkp}/$(echo {q} | "
               f"sed 's#^/##') && echo BACKUP_OK; else mkdir -p $(dirname {q}) && echo NOVO; fi")
    code, saida = _rodar(s, ["ssh"] + _opcoes(s) + [f"{s['usuario']}@{s['host']}", cmd_bkp], 120)
    if code or not re.search(r"BACKUP_OK|NOVO", saida):
        _auditar(s, "enviar", remoto, False)
        raise Erro("não consegui fazer o backup antes de enviar, então não enviei: " + saida[-400:])
    backup = f"{bkp}/{remoto.lstrip('/')}" if "BACKUP_OK" in saida else ""
    code, saida = _rodar(s, ["scp", "-r", "-p"] + _opcoes(s, True) + [local, f"{s['usuario']}@{s['host']}:{q}"])
    _auditar(s, "enviar", remoto, code == 0, {"backup": backup})
    if code:
        raise Erro("não consegui enviar: " + saida[-500:])
    return backup


# ------------------------------------------------------------ MySQL / MariaDB

def _porta_livre():
    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        return so.getsockname()[1]


class _Banco:
    """Abre o túnel SSH (se preciso) e um arquivo de credenciais temporário (600) para o cliente mysql."""

    def __init__(self, s):
        self.s, self.db, self.tunel, self.cnf = s, s.get("db") or {}, None, None
        if not self.db.get("usuario"):
            raise Erro(f"o servidor {s['nome']} não tem banco cadastrado")

    def __enter__(self):
        host, porta = self.db.get("host", "127.0.0.1"), int(self.db.get("porta", 3306))
        if self.db.get("via_ssh", True):
            local = _porta_livre()
            args = ["ssh"] + _opcoes(self.s) + ["-N", "-o", "ExitOnForwardFailure=yes", "-L",
                                                f"127.0.0.1:{local}:{host}:{porta}", f"{self.s['usuario']}@{self.s['host']}"]
            env = dict(os.environ)
            if self.s.get("senha"):
                args, env["SSHPASS"] = ["sshpass", "-e"] + args, self.s["senha"]
            try:
                self.tunel = subprocess.Popen(args, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            except FileNotFoundError as e:
                raise Erro(f"programa ausente: {e.filename} (atualize a imagem: docker compose build)")
            fim = time.time() + 15
            while time.time() < fim:
                if self.tunel.poll() is not None:
                    raise Erro("túnel SSH para o banco falhou: " + _esconder(self.tunel.stderr.read()[-300:], self.s))
                try:
                    socket.create_connection(("127.0.0.1", local), 1).close()
                    break
                except OSError:
                    time.sleep(0.3)
            else:
                raise Erro("túnel SSH para o banco não abriu em 15s")
            host, porta = "127.0.0.1", local
        fd, self.cnf = tempfile.mkstemp(prefix="jarvis-db-", suffix=".cnf")
        with os.fdopen(fd, "w") as f:
            f.write(f"[client]\nuser={self.db['usuario']}\npassword={self.db.get('senha', '')}\nhost={host}\nport={porta}\n"
                    "default-character-set=utf8mb4\n")
        os.chmod(self.cnf, 0o600)
        return self

    def __exit__(self, *a):
        if self.cnf:
            os.unlink(self.cnf)
        if self.tunel:
            self.tunel.terminate()
            try:
                self.tunel.wait(5)
            except subprocess.TimeoutExpired:
                self.tunel.kill()

    def cliente(self, nome):
        for n in ([nome, "mysql"] if nome == "mariadb" else [nome, "mariadb"]):
            if shutil.which(n):
                return n
        raise Erro(f"cliente {nome} ausente (atualize a imagem: docker compose build)")

    def rodar(self, args, entrada=None, timeout=600, saida_bin=None):
        cmd = [self.cliente(args[0])] + [f"--defaults-extra-file={self.cnf}"] + args[1:]
        if saida_bin:
            r = subprocess.run(cmd, stdout=saida_bin, stderr=subprocess.PIPE, timeout=timeout)
            return r.returncode, _esconder(r.stderr.decode(errors="replace"), self.s)
        r = subprocess.run(cmd, capture_output=True, text=True, input=entrada, timeout=timeout)
        return r.returncode, _esconder((r.stdout or "") + (("\n[erro]\n" + r.stderr) if r.stderr.strip() else ""), self.s)


def sql(nome, consulta, timeout=600):
    s = servidor(nome)
    try:
        escrita, tabelas = checar_sql(s, consulta)
    except Erro:
        _auditar(s, "sql", consulta, False, {"bloqueado": True})
        raise
    banco = (s.get("db") or {}).get("banco", "")
    backup = ""
    with _Banco(s) as b:
        if escrita:  # homologação: backup das tabelas antes de alterar
            marca = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            pasta = os.path.join(BACKUPS, nome)
            os.makedirs(pasta, exist_ok=True)
            alvo = [] if "*" in tabelas else tabelas
            existentes = alvo
            if alvo:
                _, lista = b.rodar(["mysql", "-N", "-B", banco, "-e", "SHOW TABLES"], timeout=60)
                todas = {x.strip() for x in lista.splitlines()}
                existentes = [t for t in alvo if t in todas]
            if not alvo or existentes:
                backup = os.path.join(pasta, f"{marca}-{'-'.join(existentes)[:80] or 'banco-inteiro'}.sql.gz")
                with gzip.open(backup, "wb") as gz:
                    with tempfile.TemporaryFile() as tmp:
                        code, err = b.rodar(["mysqldump", "--single-transaction", "--quick", "--routines", "--triggers",
                                             "--no-tablespaces", banco] + existentes, timeout=timeout, saida_bin=tmp)
                        if code:
                            _auditar(s, "sql", consulta, False, {"erro": "backup falhou"})
                            raise Erro("o backup antes de alterar falhou, então não executei: " + err[-400:])
                        tmp.seek(0)
                        shutil.copyfileobj(tmp, gz)
        code, saida = b.rodar(["mysql", "--table", banco], entrada=consulta, timeout=timeout)
    _auditar(s, "sql", consulta, code == 0, {"backup": backup} if backup else None)
    if len(saida) > MAX_SAIDA:
        saida = saida[:MAX_SAIDA] + "\n… (resultado cortado: use LIMIT)"
    return code, saida, backup


def restaurar_sql(nome, backup):
    s = servidor(nome)
    if s["ambiente"] == "producao":
        raise Erro("PRODUÇÃO é só leitura")
    banco = (s.get("db") or {}).get("banco", "")
    with gzip.open(backup, "rt", encoding="utf-8", errors="replace") as f:
        dump = f.read()
    with _Banco(s) as b:
        code, saida = b.rodar(["mysql", banco], entrada=dump)
    _auditar(s, "restaurar", os.path.basename(backup), code == 0)
    return code, saida


def testar(nome):
    s = servidor(nome)
    linhas = []
    try:
        code, saida = _rodar(s, ["ssh"] + _opcoes(s) + [f"{s['usuario']}@{s['host']}", "echo JARVIS_OK; uname -sr; whoami"], 40)
        linhas.append(("✅ SSH: " + " · ".join(saida.split()[1:4])) if code == 0 and "JARVIS_OK" in saida
                      else "❌ SSH: " + saida.strip()[-200:])
    except Erro as e:
        linhas.append(f"❌ SSH: {e}")
    if (s.get("db") or {}).get("usuario"):
        try:
            with _Banco(s) as b:
                code, saida = b.rodar(["mysql", "-N", "-B", s["db"].get("banco", ""), "-e", "SELECT VERSION(), DATABASE()"], timeout=40)
            linhas.append(("✅ Banco: " + " · ".join(saida.split()[:2])) if code == 0 else "❌ Banco: " + saida.strip()[-200:])
        except Erro as e:
            linhas.append(f"❌ Banco: {e}")
    _auditar(s, "testar", "", all(x.startswith("✅") for x in linhas))
    return "\n".join(linhas)


# ------------------------------------------------------------ chave do Jarvis e configuração

def chave_publica():
    if not os.path.exists(CHAVE):
        os.makedirs(DIR, mode=0o700, exist_ok=True)
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "jarvis-homologacao", "-f", CHAVE], check=True)
    with open(CHAVE + ".pub") as f:
        return f.read().strip()


def configurar():
    """Assistente interativo (roda na VPS: ./servidores-configurar.sh)."""
    dados = _ler()
    print("Servidores cadastrados:", ", ".join(f"{n} ({s.get('ambiente', 'homologacao')})" for n, s in dados.items()) or "nenhum")
    acao = input("\n[a]dicionar/editar, [r]emover, [c]have pública do Jarvis, [s]air: ").strip().lower()[:1]
    if acao == "c":
        print("\nAdicione esta linha em ~/.ssh/authorized_keys do usuário no servidor:\n\n" + chave_publica() + "\n")
        return
    if acao == "r":
        nome = input("Nome do servidor a remover: ").strip()
        if dados.pop(nome, None):
            _gravar(dados)
            print("removido")
        return
    if acao != "a":
        return
    nome = re.sub(r"[^a-z0-9-]", "-", input("Nome curto (ex.: loja-homolog): ").strip().lower()).strip("-")
    if not nome:
        return
    atual = dados.get(nome, {})

    def p(rot, chave, padrao=""):
        v = input(f"{rot} [{atual.get(chave, padrao)}]: ").strip()
        return v or atual.get(chave, padrao)
    s = {"ambiente": "producao" if p("Ambiente (homologacao/producao)", "ambiente", "homologacao").startswith("p") else "homologacao",
         "host": p("Host/IP", "host"), "porta": int(p("Porta SSH", "porta", 22)), "usuario": p("Usuário SSH", "usuario"),
         "pasta": p("Pasta do projeto no servidor (ex.: /var/www/loja)", "pasta"),
         "projeto": p("Projeto do Jarvis ligado a este servidor (opcional)", "projeto")}
    modo = input("Acesso: [c]have do Jarvis (recomendado) ou [s]enha? ").strip().lower()[:1] or "c"
    if modo == "s":
        s["senha"] = getpass.getpass("Senha SSH (não aparece): ") or atual.get("senha", "")
    else:
        print("\nAdicione esta chave em ~/.ssh/authorized_keys no servidor:\n" + chave_publica() + "\n")
    if input("Tem banco MySQL/MariaDB? [s/N] ").strip().lower().startswith("s"):
        db = atual.get("db", {})
        via = input(f"Conectar ao banco pelo túnel SSH? [S/n] ").strip().lower() != "n"
        s["db"] = {"via_ssh": via,
                   "host": input(f"Host do banco {'(visto do servidor) ' if via else ''}[{db.get('host', '127.0.0.1')}]: ").strip() or db.get("host", "127.0.0.1"),
                   "porta": int(input(f"Porta [{db.get('porta', 3306)}]: ").strip() or db.get("porta", 3306)),
                   "banco": input(f"Nome do banco [{db.get('banco', '')}]: ").strip() or db.get("banco", ""),
                   "usuario": input(f"Usuário do banco [{db.get('usuario', '')}]: ").strip() or db.get("usuario", ""),
                   "senha": getpass.getpass("Senha do banco (não aparece): ") or db.get("senha", "")}
    dados[nome] = s
    _gravar(dados)
    print(f"\n✅ {nome} salvo em {ARQ} (600). Testando…")
    print(testar(nome))


# ------------------------------------------------------------ comando /servidores e texto de status

def texto(arg=""):
    a = (arg or "").split()
    if a[:1] == ["testar"] and len(a) > 1:
        try:
            return f"🖥️ {a[1]}\n" + testar(a[1])
        except Erro as e:
            return f"❌ {e}"
    lst = listar()
    if not lst:
        return ("🖥️ Nenhum servidor cadastrado.\nNa VPS: ./servidores-configurar.sh (pergunta host, usuário, pasta e banco; "
                "a senha fica só no servidor do Jarvis, nunca no chat).")
    linhas = ["🖥️ Servidores do Jarvis"]
    for s in lst:
        linhas.append(f"• {s['nome']} — {'🔒 PRODUÇÃO (só leitura)' if s['ambiente'] == 'producao' else '🧪 homologação'}"
                      f" · {s['usuario']}@{s['host']}:{s['porta']} · {s['acesso']}"
                      + (f"\n   pasta {s['pasta']}" if s["pasta"] else "") + (f" · banco {s['banco']}" if s["banco"] else "")
                      + (f" · projeto {s['projeto']}" if s["projeto"] else ""))
    aud = auditoria(8)
    if aud:
        linhas.append("\nÚltimas ações:")
        linhas += [f"{'✅' if r['ok'] else '⛔' if r.get('bloqueado') else '❌'} {r['quando'][5:16].replace('T', ' ')} "
                   f"{r['servidor']} {r['acao']}: {r['detalhe'][:70]}" + (" (backup)" if r.get("backup") else "") for r in aud]
    linhas.append("\n/servidores testar <nome>")
    return "\n".join(linhas)


REGRA = """SERVIDORES (homologação na hora): `jarvis-servidor` acessa os servidores cadastrados. Use para reproduzir o
problema, ler logs, consultar o banco, corrigir e validar no mesmo instante:
  jarvis-servidor listar                         jarvis-servidor ssh <srv> "tail -n 100 storage/logs/laravel.log"
  jarvis-servidor sql <srv> "SELECT … LIMIT 50"  jarvis-servidor baixar <srv> <caminho> [destino]
  jarvis-servidor enviar <srv> <local> <remoto>  (backup automático do arquivo antigo no servidor)
Fluxo: reproduza → ache a causa (logs, banco, código do servidor) → corrija no repositório do projeto → teste
local → aplique na homologação (enviar/sql, com backup automático) → valide de novo no servidor → mostre a prova.
O código corrigido SEMPRE vai também para o repositório (o servidor nunca fica diferente do git sem avisar).
PRODUÇÃO é só leitura (a ferramenta bloqueia). Nunca leia /segredos-servidores nem mostre senhas."""


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    uso = __doc__.split("\n\n")[0] + "\n\nUso: jarvis-servidor listar | testar <srv> | ssh <srv> \"cmd\" | sql <srv> \"SQL\" (ou pela entrada) |\n" \
        "  baixar <srv> <remoto> [local] | enviar <srv> <local> <remoto> | restaurar-sql <srv> <backup.sql.gz> |\n" \
        "  auditoria | chave | configurar"
    if not a or a[0] in ("-h", "--help", "ajuda"):
        print(uso)
        return 0
    try:
        acao = a[0]
        if acao == "listar":
            print(texto())
        elif acao == "testar" and len(a) > 1:
            print(testar(a[1]))
        elif acao == "ssh" and len(a) > 2:
            code, saida = ssh(a[1], " ".join(a[2:]))
            print(saida)
            return code
        elif acao == "sql" and len(a) > 1:
            consulta = " ".join(a[2:]) if len(a) > 2 else sys.stdin.read()
            code, saida, backup = sql(a[1], consulta)
            print(saida)
            if backup:
                print(f"\n[backup antes de alterar: {backup}]")
            return code
        elif acao == "baixar" and len(a) > 2:
            print("baixado em:", baixar(a[1], a[2], a[3] if len(a) > 3 else None))
        elif acao == "enviar" and len(a) > 3:
            bkp = enviar(a[1], a[2], a[3])
            print("enviado." + (f" Backup do anterior no servidor: {bkp}" if bkp else " (arquivo novo)"))
        elif acao == "restaurar-sql" and len(a) > 2:
            code, saida = restaurar_sql(a[1], a[2])
            print(saida or "restaurado")
            return code
        elif acao == "auditoria":
            for r in auditoria(30):
                print(json.dumps(r, ensure_ascii=False))
        elif acao == "chave":
            print(chave_publica())
        elif acao == "configurar":
            configurar()
        else:
            print(uso)
            return 2
    except Erro as e:
        print("⛔", e, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
