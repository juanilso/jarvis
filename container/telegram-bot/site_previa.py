"""Prévia (prints) e teste automático do site do projeto, usando o jarvis-site (Chromium headless).

Os resultados ficam em <projeto>/.jarvis/previas/<data-hora>/ e o ponteiro em <projeto>/.jarvis/previas/ultima.json.
O painel, o Telegram e as respostas do Jarvis mostram os prints da última prévia.
"""
import json
import os
import shutil
import subprocess
import time
from datetime import datetime

import jarvis_core as core

PASTA = os.path.join(".jarvis", "previas")
CMD = shutil.which("jarvis-site") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis-site")
_rodando = {}


def pasta_projeto(projeto):
    return os.path.join(core.WORKSPACE, projeto)


def ultima(projeto, desde=None, arquivo="ultima.json"):
    """Última prévia/teste do projeto (dict com 'prints' em caminhos absolutos) ou None.
    desde: só devolve se foi feita depois deste horário (time.time())."""
    if not projeto:
        return None
    base = pasta_projeto(projeto)
    arq = os.path.join(base, PASTA, arquivo)
    try:
        d = json.load(open(arq, encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if desde is not None and os.path.getmtime(arq) < desde:
        return None
    d["prints_abs"] = [p for p in (seguro(projeto, x.get("arquivo", "")) for x in d.get("prints") or []) if p]
    if d.get("relatorio"):
        r = seguro(projeto, d["relatorio"])
        d["relatorio_texto"] = open(r, encoding="utf-8").read() if r else ""
    return d


def seguro(projeto, relativo):
    """Caminho absoluto de um arquivo dentro de <projeto>/.jarvis/previas (bloqueia ../ e links para fora)."""
    raiz = os.path.realpath(os.path.join(pasta_projeto(projeto), PASTA))
    cam = os.path.realpath(os.path.join(pasta_projeto(projeto), relativo))
    if not cam.startswith(raiz + os.sep) or not os.path.isfile(cam):
        return None
    return cam


def ocupado(projeto):
    return _rodando.get(projeto)


def rodar(modo, projeto, alvo=None, paginas=None, maximo=15):
    """Executa (bloqueante). modo: 'print' ou 'testar'. alvo: URL ou vazio (pasta do projeto).
    Retorna (ok, saida_texto, ultima)."""
    if modo not in ("print", "testar"):
        raise ValueError("modo inválido")
    if not projeto:
        return False, "Escolha um projeto primeiro.", None
    if _rodando.get(projeto):
        return False, f"Já estou rodando {_rodando[projeto]} neste projeto, espere terminar.", None
    pasta = pasta_projeto(projeto)
    if alvo and not alvo.lower().startswith(("http://", "https://")):
        alvo = None  # só URL ou a pasta do projeto (nada de caminhos arbitrários)
    cmd = [CMD, modo, alvo or pasta]
    if paginas:
        cmd += ["--paginas", ",".join(paginas)]
    if modo == "testar":
        cmd += ["--max", str(maximo)]
    inicio = time.time()
    _rodando[projeto] = "o teste" if modo == "testar" else "os prints"
    try:
        p = subprocess.run(cmd, cwd=pasta, capture_output=True, text=True, timeout=600)
        saida = (p.stdout or "") + (("\n" + p.stderr) if p.returncode and p.stderr else "")
        return p.returncode == 0, saida.strip(), ultima(projeto, desde=inicio - 1)
    except subprocess.TimeoutExpired:
        return False, "Demorou demais (mais de 10 minutos).", None
    finally:
        _rodando.pop(projeto, None)


def resumo_teste(d, limite=3300):
    """Texto curto do teste para Telegram/painel."""
    if not d:
        return "Sem resultado."
    c = d.get("contagem") or {}
    cab = (f"🧪 Teste do site · nota {d.get('nota', '?')}/100\n"
           f"críticos {c.get('CRÍTICO', 0)} · altos {c.get('ALTO', 0)} · médios {c.get('MÉDIO', 0)} · baixos {c.get('BAIXO', 0)}"
           f" · {d.get('paginas', 0)} página(s)")
    corpo, secao = [], False
    for linha in (d.get("relatorio_texto") or "").splitlines():
        if linha.startswith("## "):
            secao = True
            corpo.append("\n📄 " + linha[3:])
        elif secao and linha.startswith("- **"):
            corpo.append("• " + linha[2:].replace("**", ""))
    if not corpo:
        corpo = ["\nNenhum problema encontrado nos testes automáticos. 🎉"]
    texto = cab + "\n" + "\n".join(corpo)
    if len(texto) > limite:
        texto = texto[:limite].rsplit("\n", 1)[0] + "\n… (relatório completo no painel → 🖼)"
    return texto


def quando(d):
    try:
        return datetime.fromisoformat(d["quando"].replace("Z", "+00:00")).astimezone().strftime("%d/%m %H:%M")
    except (KeyError, ValueError):
        return ""


PROMPT_CORRIGIR = (
    "Rode `jarvis-site testar` na pasta do projeto (ou use o relatório mais recente em .jarvis/previas/ultima.json). "
    "Corrija os problemas CRÍTICOS, ALTOS e MÉDIOS que forem do próprio site (não mexa em links externos de terceiros). "
    "Depois rode `jarvis-site testar` de novo, rode `jarvis-site print` e OLHE os prints com a ferramenta Read "
    "(desktop e celular) para confirmar que nada ficou quebrado visualmente. "
    "Responda com a nota antes e depois e o que foi corrigido.")
