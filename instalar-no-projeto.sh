#!/usr/bin/env bash
# Copia o Jarvis (modo projeto) para dentro de um repositório: funciona no Claude Code local E na nuvem.
# Uso: bash instalar-no-projeto.sh /caminho/do/projeto
set -e
SRC="$(cd "$(dirname "$0")" && pwd)/projeto/.claude"
DEST="${1:?informe a pasta do projeto}"
mkdir -p "$DEST/.claude"
[ -f "$DEST/.claude/settings.json" ] && cp "$DEST/.claude/settings.json" "$DEST/.claude/settings.json.bak"
cp -r "$SRC/." "$DEST/.claude/"
chmod +x "$DEST/.claude/hooks/session-start.sh"
echo "Jarvis instalado em $DEST/.claude — faça commit e abra o projeto no Claude Code (local ou nuvem)."
