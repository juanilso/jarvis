#!/usr/bin/env bash
# Liga o Hermes Agent como ajudante do Jarvis, usando o MESMO gateway do .env.claude.
# Rode na VPS, dentro da pasta container/:   ./hermes-configurar.sh
# Pode rodar de novo quando quiser (por exemplo, depois de trocar a chave do gateway).
set -euo pipefail
cd "$(dirname "$0")"

ENV=.env.claude
[ -f "$ENV" ] || { echo "Não achei $ENV nesta pasta."; exit 1; }

ler() { { grep -E "^$1=" "$ENV" || true; } | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"; }

CHAVE_GW="$(ler ANTHROPIC_API_KEY)"; [ -n "$CHAVE_GW" ] || CHAVE_GW="$(ler ANTHROPIC_AUTH_TOKEN)"
BASE_GW="$(ler ANTHROPIC_BASE_URL)"
MODELO="${1:-$(ler HERMES_MODELO)}"; [ -n "$MODELO" ] || MODELO="$(ler ANTHROPIC_DEFAULT_SONNET_MODEL)"
[ -n "$MODELO" ] || MODELO="claude-sonnet-5-5"
[ -n "$CHAVE_GW" ] || { echo "Falta ANTHROPIC_API_KEY (ou ANTHROPIC_AUTH_TOKEN) no $ENV."; exit 1; }

# chave que só o Jarvis conhece para falar com o Hermes
CHAVE_H="$(ler HERMES_API_KEY)"
if [ -z "$CHAVE_H" ]; then
  CHAVE_H="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  printf '\n# Hermes Agent (ajudante do Jarvis)\nHERMES_API_KEY=%s\nHERMES_URL=http://hermes:8642\n' "$CHAVE_H" >> "$ENV"
  echo "✔ HERMES_API_KEY criada no $ENV"
fi

echo "→ Baixando e ligando o Hermes (a primeira vez demora alguns minutos)…"
docker compose --profile hermes pull hermes
docker compose --profile hermes up -d hermes
sleep 8

H() { docker compose --profile hermes exec -T hermes hermes "$@"; }
echo "→ Configurando o modelo: provedor anthropic · $MODELO${BASE_GW:+ · $BASE_GW}"
H config set ANTHROPIC_API_KEY "$CHAVE_GW" >/dev/null
H config set model.provider anthropic >/dev/null
H config set model.default "$MODELO" >/dev/null
if [ -n "$BASE_GW" ]; then H config set model.base_url "$BASE_GW" >/dev/null; fi
H config set API_SERVER_KEY "$CHAVE_H" >/dev/null

echo "→ Reiniciando o Hermes e os serviços do Jarvis (para lerem a chave nova)…"
docker compose --profile hermes restart hermes
docker compose --profile web --profile telegram up -d
sleep 10

if docker compose exec -T dev jarvis-hermes --status; then
  echo
  echo "✅ Pronto. No painel ou no Telegram: /hermes <pedido>   (ex.: /hermes pesquise gateways PIX para PHP com fontes)"
else
  echo
  echo "⚠️ O Jarvis ainda não conseguiu falar com o Hermes. Veja os registros:"
  echo "   docker compose --profile hermes logs --tail 80 hermes"
  echo "   Se o problema for o modelo, rode o assistente do Hermes e escolha Anthropic ou 'Custom endpoint':"
  echo "   docker compose --profile hermes exec -it hermes hermes model"
fi
