#!/usr/bin/env bash
# Deixa o Jarvis usar o laboratório no n8n (jarvis-n8n): criar e testar fluxos [LAB] durante o planejamento.
# Rode na VPS, dentro de container/:   ./n8n-api-configurar.sh
# Antes: no n8n (http://localhost:5678 pelo túnel/Tailscale) → Settings → n8n API → Create an API key.
# A chave fica em .env.ajudantes (fora do Git, permissão 600). O jarvis-n8n só mexe em fluxos [LAB].
set -euo pipefail
cd "$(dirname "$0")"
ARQ=.env.ajudantes; touch "$ARQ"; chmod 600 "$ARQ"
gravar() {
  local tmp; tmp="$(mktemp)"; { grep -vE "^$1=" "$ARQ" 2>/dev/null || true; } > "$tmp"
  [ -n "$2" ] && printf '%s=%s\n' "$1" "$2" >> "$tmp"
  cat "$tmp" > "$ARQ"; rm -f "$tmp"; chmod 600 "$ARQ"
}
echo "Cole a chave da API do n8n (Settings → n8n API). Ela não aparece na tela. Enter = não mudar, - = remover."
read -r -s -p "Chave: " k; echo
if [ "$k" = "-" ]; then gravar N8N_API_KEY ""; elif [ -n "$k" ]; then gravar N8N_API_KEY "$k"; fi
gravar N8N_URL "http://n8n:5678"
docker compose --profile web --profile telegram up -d --force-recreate jarvisweb telegram >/dev/null
docker compose up -d --force-recreate dev >/dev/null 2>&1 || true
echo "→ Testando…"
docker compose --profile telegram exec -T telegram jarvis-n8n status || echo "Confira se o n8n está ligado: docker compose --profile automacoes up -d n8n"
