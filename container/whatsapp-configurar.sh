#!/usr/bin/env bash
# Liga o WhatsApp Web (WAHA Core) para o atendimento automático do Jarvis.
# Rode na VPS, dentro de container/:   ./whatsapp-configurar.sh
# Requisitos: n8n já ligado (./automacoes-configurar.sh). Use um número separado, só para a empresa.
set -euo pipefail
cd "$(dirname "$0")"
ENV=.env.claude
[ -f "$ENV" ] || { echo "Não achei $ENV nesta pasta."; exit 1; }
ler() { { grep -E "^$1=" "$2" 2>/dev/null || true; } | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }
gerar() { openssl rand -hex "${1:-32}" 2>/dev/null || head -c "${1:-32}" /dev/urandom | od -An -tx1 | tr -d ' \n'; }

CHAVE="$(ler WAHA_API_KEY .env.atendimento)"; [ -n "$CHAVE" ] || CHAVE="$(gerar 32)"
SENHA="$(ler WAHA_DASHBOARD_PASSWORD .env.whatsapp)"; [ -n "$SENHA" ] || SENHA="$(gerar 12)"
umask 077
printf 'WAHA_API_KEY=%s\nWHATSAPP_API_KEY=%s\nWAHA_DASHBOARD_USERNAME=admin\nWAHA_DASHBOARD_PASSWORD=%s\nWHATSAPP_SWAGGER_USERNAME=admin\nWHATSAPP_SWAGGER_PASSWORD=%s\n' \
  "$CHAVE" "$CHAVE" "$SENHA" "$SENHA" > .env.whatsapp
printf 'WAHA_API_KEY=%s\nWAHA_URL=http://whatsapp:3000\n' "$CHAVE" > .env.atendimento
echo "✔ chaves do WhatsApp criadas (.env.whatsapp e .env.atendimento; ficam só nesta VPS)"

echo "→ Baixando e ligando o WhatsApp Web (WAHA)…"
docker compose --profile whatsapp pull whatsapp
docker compose --profile whatsapp up -d whatsapp
echo "→ Reiniciando o painel (para ler a chave)…"
docker compose --profile web up -d jarvisweb >/dev/null

if docker compose --profile automacoes ps --status running n8n 2>/dev/null | grep -q n8n; then
  echo "→ Importando o fluxo 'Jarvis · Atendimento WhatsApp' no n8n (fica desativado)…"
  docker compose --profile automacoes exec -T -u node n8n n8n import:workflow \
    --input=/opt/jarvis-n8n/fluxos/jarvisRotina0006.json >/dev/null 2>&1 || echo "   (importe pela tela do n8n: container/n8n/fluxos/jarvisRotina0006.json)"
  docker compose --profile automacoes restart n8n >/dev/null
else
  echo "⚠️ O n8n não está ligado. Rode ./automacoes-configurar.sh e depois este script de novo."
fi

echo
echo "✅ Pronto. Agora:"
echo "  1. No painel do Jarvis, clique em 📱 → 'Conectar' e leia o QR code com o WhatsApp da empresa"
echo "     (no celular: Configurações → Dispositivos conectados → Conectar dispositivo)."
echo "  2. No 📱, preencha a 'Base de respostas' (preços, horários, como pagar, quando chamar você)."
echo "  3. No n8n, ative o fluxo 'Jarvis · Atendimento WhatsApp' (Active)."
echo "  4. Mande uma mensagem de outro número para testar."
