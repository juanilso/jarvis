#!/usr/bin/env bash
# Liga o leitor de pagamentos: lê na SUA conta do Telegram só a conversa com o bot de pagamentos e repassa ao Jarvis.
# Rode na VPS, dentro de container/:   ./pagamentos-configurar.sh
set -euo pipefail
cd "$(dirname "$0")"
ler() { { grep -E "^$1=" "$2" 2>/dev/null || true; } | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }

TOKEN_G="$(ler JARVIS_GATILHO_TOKEN .env.claude)"
[ -n "$TOKEN_G" ] || { echo "Falta o gatilho do Jarvis. Rode antes: ./automacoes-configurar.sh"; exit 1; }

cat <<'TXT'
== Leitor de pagamentos ==
O Telegram não deixa o bot do Jarvis ler a sua conversa com outro bot. Por isso este leitor entra na SUA conta
(como um "dispositivo conectado") e lê SÓ a conversa com o bot de pagamentos. Ele não envia mensagens e não lê
outras conversas. Para desligar: Telegram → Configurações → Dispositivos → encerrar "Jarvis leitor".

1. Abra https://my.telegram.org no navegador e entre com o seu número.
2. Clique em "API development tools", crie um app (nome: Jarvis leitor; plataforma: Other).
3. Copie o "App api_id" e o "App api_hash".
TXT
ID_ATUAL="$(ler TG_API_ID .env.pagamentos)"; BOT_ATUAL="$(ler PAGAMENTOS_BOT .env.pagamentos)"
read -r -p "api_id [$ID_ATUAL]: " API_ID; API_ID="${API_ID:-$ID_ATUAL}"
read -r -s -p "api_hash (não aparece; Enter = manter): " API_HASH; echo
[ -n "$API_HASH" ] || API_HASH="$(ler TG_API_HASH .env.pagamentos)"
read -r -p "@usuário do bot de pagamentos (Enter = achar sozinho pela conversa com os pagamentos) [${BOT_ATUAL:-automático}]: " BOT
BOT="${BOT:-$BOT_ATUAL}"; BOT="${BOT#@}"
[ -n "$API_ID" ] && [ -n "$API_HASH" ] || { echo "Faltou api_id ou api_hash."; exit 1; }

umask 077
printf 'TG_API_ID=%s\nTG_API_HASH=%s\nPAGAMENTOS_BOT=%s\nJARVIS_GATILHO_TOKEN=%s\n' "$API_ID" "$API_HASH" "$BOT" "$TOKEN_G" > .env.pagamentos
echo "✔ .env.pagamentos criado (fica só nesta VPS)"

echo
echo "→ Login na sua conta (o Telegram manda um código no app; se tiver senha de 2 etapas, ela também é pedida):"
docker compose --profile pagamentos run --rm -it leitor python3 /opt/jarvis-bots/leitor_pagamentos.py --login

echo "→ Ligando o leitor…"
docker compose --profile pagamentos up -d leitor
sleep 8
docker compose --profile pagamentos logs --tail 15 leitor
echo
echo "✅ Pronto. Cada 'PAGAMENTO FASTFLOW RECEBIDO' do @$BOT vai para o Jarvis (resumo no Telegram e no 🏢)."
echo "   Desligar: docker compose --profile pagamentos stop leitor"
