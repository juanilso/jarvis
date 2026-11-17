#!/usr/bin/env bash
# Jarvis: injeta o estado do projeto no início de cada sessão (barato: só lê arquivos curtos).
TEMPLATES="${CLAUDE_PLUGIN_ROOT}/skills/orquestrador/templates"

if [ -f "docs/ESTADO.md" ]; then
  echo "## Jarvis — projeto orquestrado detectado"
  echo "Siga a skill 'orquestrador'. Modelos de arquivo: ${TEMPLATES}"
  [ -f "docs/ORQUESTRACAO.md" ] && grep -m1 -i "Perfil ativo" docs/ORQUESTRACAO.md
  echo
  head -n 30 docs/ESTADO.md
  if [ -f "docs/DECISOES-PENDENTES.md" ]; then
    n=$(grep -c "Status: pendente" docs/DECISOES-PENDENTES.md 2>/dev/null || echo 0)
    [ "$n" -gt 0 ] && echo && echo "⚠ ${n} decisão(ões) pendente(s): sugira /jarvis:decidir"
  fi
else
  echo "Jarvis disponível. Projeto sem orquestração. Para iniciar: /jarvis <ideia do projeto>. Modelos de arquivo: ${TEMPLATES}"
fi
exit 0
