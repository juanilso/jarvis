#!/usr/bin/env bash
# Confere se o n8n usa o MESMO token do gatilho que o Jarvis e, se estiver diferente, corrige e reinicia só o n8n.
# Rode na VPS, dentro de container/:  ./n8n-token-sincronizar.sh
# Não mexe nos fluxos (diferente do automacoes-configurar.sh, que reimporta os exemplos) e não mostra o token.
set -euo pipefail
cd "$(dirname "$0")"
ler() { { grep -E "^$1=" "$2" 2>/dev/null || true; } | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }
J="$(ler JARVIS_GATILHO_TOKEN .env.claude)"
N="$(ler JARVIS_TOKEN .env.n8n)"
if [ -z "$J" ]; then
  echo "❌ O Jarvis não tem token do gatilho (.env.claude). Rode ./automacoes-configurar.sh uma vez."; exit 1
fi
if [ "$J" = "$N" ]; then
  echo "✅ Tokens iguais no Jarvis e no n8n."
  echo "   Se o diagnóstico ainda falhar, reinicio os dois para relerem:"
else
  echo "⚠️  Token do n8n diferente do Jarvis: corrigindo .env.n8n…"
  umask 077
  if grep -qE '^JARVIS_TOKEN=' .env.n8n 2>/dev/null; then
    sed -i "s|^JARVIS_TOKEN=.*|JARVIS_TOKEN=$J|" .env.n8n
  else
    printf 'JARVIS_TOKEN=%s\n' "$J" >> .env.n8n
  fi
fi
docker compose --profile automacoes up -d --force-recreate n8n >/dev/null
docker compose --profile web up -d jarvisweb >/dev/null
echo "✅ n8n reiniciado com o token do Jarvis. Aguarde ~30 s e rode o diagnóstico do WhatsApp de novo."
