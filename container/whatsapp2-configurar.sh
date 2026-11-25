#!/usr/bin/env bash
# Liga um SEGUNDO número de WhatsApp no atendimento do Jarvis (outro WAHA grátis, com QR code próprio).
# Rode na VPS, dentro de container/, depois que o primeiro já estiver funcionando (./whatsapp-configurar.sh):
#   ./whatsapp2-configurar.sh "Nome da loja 2"     → liga (o nome aparece no painel e nos avisos do Telegram)
#   ./whatsapp2-configurar.sh desligar             → desliga o número 2 (a sessão fica guardada)
# O número 2 tem base de respostas, configurações e vigia próprios (painel → 📱 → botão do número).
set -euo pipefail
cd "$(dirname "$0")"
ENV=.env.atendimento
[ -f .env.whatsapp ] && [ -f "$ENV" ] || { echo "Ligue primeiro o número 1: ./whatsapp-configurar.sh"; exit 1; }

gravar() {  # gravar CHAVE valor  (troca ou acrescenta no .env.atendimento)
  local tmp; tmp="$(mktemp)"
  { grep -vE "^$1=" "$ENV" || true; printf '%s=%s\n' "$1" "$2"; } > "$tmp"
  cat "$tmp" > "$ENV"; rm -f "$tmp"; chmod 600 "$ENV"
}

if [ "${1:-}" = "desligar" ]; then
  gravar WHATSAPP2 0
  docker compose --profile whatsapp2 stop whatsapp2 || true
  docker compose --profile web up -d --force-recreate jarvisweb >/dev/null
  echo "⏹ Número 2 desligado. Para ligar de novo: ./whatsapp2-configurar.sh"
  exit 0
fi

NOME="${1:-Número 2}"
gravar WHATSAPP2 1
gravar WHATSAPP2_NOME "$NOME"
echo "→ Baixando e ligando o segundo WhatsApp (WAHA)…"
docker compose --profile whatsapp2 pull whatsapp2
docker compose --profile whatsapp2 up -d whatsapp2
echo "→ Reiniciando o painel (para enxergar o número 2)…"
docker compose --profile web up -d --force-recreate jarvisweb >/dev/null

echo
echo "✅ Pronto. Agora:"
echo "  1. No painel do Jarvis, abra 📱 e clique no botão “📱 $NOME” no topo."
echo "  2. Clique em 'Conectar' e leia o QR code com o WhatsApp desse número"
echo "     (no celular: Configurações → Dispositivos conectados → Conectar dispositivo)."
echo "  3. Preencha a 'Base de respostas' desse número (é separada da do número 1)."
echo "  4. Mande uma mensagem de outro celular para testar. Não precisa mexer no n8n."
echo "  No Telegram: /atendimento 2 · /whatsapp 2 testar · /assumir 2 <número>"
