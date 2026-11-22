#!/usr/bin/env bash
# Publica a prévia dos sites (porta 8081) no Tailscale e grava o link para o Jarvis mandar no Telegram.
# Rode na VPS, dentro de container/:   sudo ./previa-configurar.sh
# A prévia fica só na sua rede do Tailscale (privada): não abre nada para a internet.
set -euo pipefail
cd "$(dirname "$0")"
touch .env.claude
gravar() {  # gravar CHAVE VALOR ARQUIVO (substitui se já existir)
  local tmp; tmp="$(mktemp)"; { grep -vE "^$1=" "$3" 2>/dev/null || true; } > "$tmp"; printf '%s=%s\n' "$1" "$2" >> "$tmp"
  cat "$tmp" > "$3"; rm -f "$tmp"
}

URL=""
if command -v tailscale >/dev/null 2>&1; then
  echo "→ Publicando a porta 8081 no Tailscale (só para os seus aparelhos)…"
  tailscale serve --bg --https=8081 http://127.0.0.1:8081 >/dev/null
  NOME="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null || true)"
  [ -n "$NOME" ] && URL="https://$NOME:8081"
else
  echo "Tailscale não encontrado nesta VPS."
fi
if [ -z "$URL" ]; then
  echo "Sem Tailscale, use um túnel SSH no seu PC:  ssh -L 8081:localhost:8081 root@IP-DA-VPS   e abra http://localhost:8081"
  read -r -p "Endereço que você usa para abrir a prévia (Enter = http://localhost:8081): " URL
  URL="${URL:-http://localhost:8081}"
fi

gravar JARVIS_PREVIA_URL "$URL" .env.claude
echo "✔ JARVIS_PREVIA_URL=$URL gravado no .env.claude"
echo "→ Reiniciando o painel e o Telegram para usarem o link…"
docker compose --profile web --profile telegram up -d --force-recreate jarvisweb telegram >/dev/null
echo
echo "Pronto. No Telegram: /previa  ·  no painel: 👁 ou 🖼 → 🌐 Navegar no site"
echo "Abra $URL com o app do Tailscale ligado (PC ou celular)."
