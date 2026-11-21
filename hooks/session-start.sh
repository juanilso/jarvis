#!/usr/bin/env bash
# Jarvis: injeta o estado do projeto no início de cada sessão (barato: só lê arquivos curtos).
BASE="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_PROJECT_DIR:-.}/.claude}"
TEMPLATES="$BASE/skills/orquestrador/templates"

if [ -f "docs/ESTADO.md" ]; then
  echo "## Jarvis — projeto orquestrado detectado"
  echo "Siga a skill 'orquestrador'. Modelos de arquivo: ${TEMPLATES}"
  echo "MODO ATIVO: pergunta sobre o código → explorador antes de responder; alteração → explorador, executor da área,"
  echo "testador e revisor; evolução/decisão → arquiteto; tela/site → designer; fim de ciclo → documentador."
  echo "Antes de cada etapa, diga em uma linha o que vai fazer e qual agente trabalha."
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
