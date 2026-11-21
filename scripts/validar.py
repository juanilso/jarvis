#!/usr/bin/env python3
"""Valida a estrutura do Jarvis antes de publicar: JSONs, cabeçalhos (frontmatter) de agentes, comandos e skills,
referências entre arquivos e cópia do modo projeto. Uso: python3 scripts/validar.py  (sai com código 1 se houver erro)"""
import json
import os
import re
import sys

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
erros, avisos = [], []


def fm(caminho):
    t = open(caminho, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    if not m:
        erros.append(f"{caminho}: sem cabeçalho ---")
        return {}, t
    try:
        return yaml.safe_load(m.group(1)) or {}, t
    except yaml.YAMLError as e:
        erros.append(f"{caminho}: cabeçalho YAML inválido ({e})")
        return {}, t


for j in [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", ".mcp.json", "settings-recomendado.json",
          "hooks/hooks.json", "projeto/.claude/settings.json"]:
    try:
        json.load(open(os.path.join(RAIZ, j), encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        erros.append(f"{j}: JSON inválido ({e})")

for base in ["", "projeto/.claude/"]:
    agentes = set()
    for a in sorted(os.listdir(os.path.join(RAIZ, base + "agents"))):
        d, _ = fm(os.path.join(RAIZ, base + "agents", a))
        if d:
            if not d.get("name") or not d.get("description"):
                erros.append(f"{base}agents/{a}: falta name ou description")
            if d.get("model") not in (None, "opus", "sonnet", "haiku", "inherit"):
                erros.append(f"{base}agents/{a}: model inválido {d.get('model')}")
            agentes.add(d.get("name"))
    for c in sorted(os.listdir(os.path.join(RAIZ, base + "commands"))):
        d, t = fm(os.path.join(RAIZ, base + "commands", c))
        if d and not d.get("description"):
            erros.append(f"{base}commands/{c}: falta description")
        for ref in re.findall(r"`(arquiteto|explorador|desenvolvedor|dba|android|testador|revisor|deploy|documentador|designer)`", t):
            if ref not in agentes:
                erros.append(f"{base}commands/{c}: cita o agente {ref}, que não existe")
    for sk in sorted(os.listdir(os.path.join(RAIZ, base + "skills"))):
        p = os.path.join(RAIZ, base + "skills", sk, "SKILL.md")
        if os.path.isfile(p):
            d, _ = fm(p)
            if d and (not d.get("name") or not d.get("description")):
                erros.append(f"{base}skills/{sk}/SKILL.md: falta name ou description")

for c in os.listdir(os.path.join(RAIZ, "commands")):
    if not os.path.isfile(os.path.join(RAIZ, "projeto/.claude/commands", c)):
        avisos.append(f"modo projeto sem o comando {c}")
for a in os.listdir(os.path.join(RAIZ, "agents")):
    if not os.path.isfile(os.path.join(RAIZ, "projeto/.claude/agents", a)):
        avisos.append(f"modo projeto sem o agente {a}")

for e in erros:
    print("ERRO  ", e)
for a in avisos:
    print("AVISO ", a)
print(f"{'FALHOU' if erros else 'OK'}: {len(erros)} erro(s), {len(avisos)} aviso(s)")
sys.exit(1 if erros else 0)
