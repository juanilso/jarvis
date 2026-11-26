"""Navegador do PC: o Jarvis controla um Chrome separado no seu Windows, pela rede Tailscale.

No PC, o atalho "Chrome do Jarvis" (pc-windows/) abre o Chrome com um PERFIL PRÓPRIO (não o seu do dia a dia) e
libera a porta de depuração só para a sua rede Tailscale. Aqui, o Playwright conecta nele (servidor MCP
"navegador-pc") e o Jarvis abre páginas, clica, preenche, lê o console e tira prints, e você vê tudo na tela.
Fechou a janela do Chrome do Jarvis = acesso encerrado.
"""
import ipaddress
import json
import os
import re
import urllib.request

CONFIG_DIR = os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))
ARQ = os.path.join(CONFIG_DIR, "jarvis-navegador-pc.json")
PORTA = 9222
INVALIDO = "http://127.0.0.1:1"  # sem PC configurado: a ferramenta responde "não conectado"


def endereco():
    try:
        with open(ARQ, encoding="utf-8") as f:
            return json.load(f).get("endpoint") or ""
    except (OSError, ValueError):
        return ""


def salvar(ip):
    ip = (ip or "").strip()
    m = re.fullmatch(r"(?:https?://)?([0-9.]+)(?::(\d+))?/?", ip)
    if not m:
        raise ValueError("use o IP do Tailscale do PC (começa com 100.), ex.: /navegador 100.101.102.103")
    endereco_ip = ipaddress.ip_address(m.group(1))
    if endereco_ip not in ipaddress.ip_network("100.64.0.0/10"):
        raise ValueError("por segurança, só aceito IP da rede Tailscale (100.64.x.x a 100.127.x.x)")
    url = f"http://{endereco_ip}:{int(m.group(2) or PORTA)}"
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(ARQ, "w", encoding="utf-8") as f:
        json.dump({"endpoint": url}, f)
    return url


def desligar():
    try:
        os.unlink(ARQ)
    except FileNotFoundError:
        pass


def status(tempo=4):
    url = endereco()
    if not url:
        return {"configurado": False, "conectado": False}
    try:
        with urllib.request.urlopen(url + "/json/version", timeout=tempo) as r:
            v = json.loads(r.read())
        with urllib.request.urlopen(url + "/json/list", timeout=tempo) as r:
            abas = [a for a in json.loads(r.read()) if a.get("type") == "page"]
        return {"configurado": True, "conectado": True, "endpoint": url, "versao": v.get("Browser", ""),
                "abas": [{"titulo": a.get("title", "")[:60], "url": a.get("url", "")[:100]} for a in abas[:8]]}
    except Exception as e:  # noqa: BLE001
        return {"configurado": True, "conectado": False, "endpoint": url, "erro": type(e).__name__}


def texto(arg=""):
    arg = (arg or "").strip()
    if arg.lower() in ("desligar", "remover", "off"):
        desligar()
        return "🖥️ Navegador do PC desligado no Jarvis (ele não tenta mais conectar)."
    if arg:
        try:
            url = salvar(arg)
        except ValueError as e:
            return f"❌ {e}"
        s = status()
        return (f"🖥️ Navegador do PC salvo: {url}\n" + ("✅ Conectado: " + s["versao"] if s["conectado"] else
                "⏳ Ainda não respondeu: abra o atalho “Chrome do Jarvis” no PC (ele precisa ficar aberto)."))
    s = status()
    if not s["configurado"]:
        return ("🖥️ Navegador do PC ainda não configurado.\n1) No Windows, baixe o atalho pelo painel "
                "(endereço do painel + /api/navegador/kit), descompacte e abra Chrome-do-Jarvis.bat.\n"
                "2) Ele mostra (e copia) o comando: /navegador 100.x.x.x — mande aqui.")
    if not s["conectado"]:
        return (f"🖥️ Navegador do PC: ❌ sem resposta de {s['endpoint']} ({s.get('erro')}).\n"
                "Abra o atalho “Chrome do Jarvis” no PC (e deixe a janela aberta). PC desligado/dormindo também cai aqui.")
    abas = "\n".join(f"  • {a['titulo'] or '(sem título)'} — {a['url']}" for a in s["abas"]) or "  (nenhuma aba)"
    return f"🖥️ Navegador do PC: ✅ conectado ({s['versao']})\nAbas abertas:\n{abas}\n\n/navegador desligar · /navegador <novo IP>"


REGRA = """NAVEGADOR DO PC (Chrome do Jarvis no Windows do usuário, ferramentas mcp__…navegador-pc__browser_*):
- Use para homologar no navegador DELE: o que só abre no PC/na rede dele, sistemas em que ele já entrou nesse perfil,
  e para conferir visualmente o que você criou (ele vê tudo ao vivo). Páginas públicas e prévias: prefira o navegador
  da VPS (ferramentas playwright), que não mexe na tela dele.
- Abra uma aba NOVA para o seu trabalho e não feche as abas dele. Seja objetivo: navegue, teste, leia o console
  (browser_console_messages), tire print como prova e diga o que encontrou.
- NUNCA digite senhas, códigos de verificação, dados de cartão ou documentos, e não conclua compras, pagamentos,
  envios de mensagem/e-mail, exclusões ou publicações sem o usuário pedir explicitamente naquela conversa. Ao chegar
  numa tela de login/pagamento, pare e peça para ele preencher lá na janela.
- Se a ferramenta não conectar: diga para abrir o atalho “Chrome do Jarvis” no PC (ou o PC está desligado)."""
