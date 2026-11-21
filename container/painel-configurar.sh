#!/usr/bin/env bash
# Conecta o atendimento à API do painel (consulta de vencimento, teste grátis, renovação) e aos pagamentos FastFlow.
# Rode na VPS, dentro de container/:   ./painel-configurar.sh
# O token fica SÓ no .env.atendimento desta VPS (lido apenas pelo serviço do painel do Jarvis).
set -euo pipefail
cd "$(dirname "$0")"
touch .env.atendimento && chmod 600 .env.atendimento
ler() { { grep -E "^$1=" "$2" 2>/dev/null || true; } | tail -1 | cut -d= -f2-; }
gravar() {  # gravar CHAVE VALOR ARQUIVO (substitui se já existir)
  local tmp; tmp="$(mktemp)"; { grep -vE "^$1=" "$3" 2>/dev/null || true; } > "$tmp"; printf '%s=%s\n' "$1" "$2" >> "$tmp"
  cat "$tmp" > "$3"; rm -f "$tmp"
}

echo "== API do painel =="
URL_ATUAL="$(ler PAINEL_API_URL .env.atendimento)"; URL_ATUAL="${URL_ATUAL:-https://pg.tvdc.site/api.php}"
read -r -p "Endereço da API [$URL_ATUAL]: " URL; URL="${URL:-$URL_ATUAL}"
read -r -s -p "Token da API (não aparece ao digitar; Enter = manter o atual): " TOKEN; echo
[ -n "$TOKEN" ] || TOKEN="$(ler PAINEL_API_TOKEN .env.atendimento)"
[ -n "$TOKEN" ] || { echo "Sem token, nada a fazer."; exit 1; }
PLANOS_ATUAL="$(ler PAINEL_PLANOS .env.atendimento)"; PLANOS_ATUAL="${PLANOS_ATUAL:-25=1,30=1}"
read -r -p "Tabela valor=meses (ex.: 25=1,30=1,70=3) [$PLANOS_ATUAL]: " PLANOS; PLANOS="${PLANOS:-$PLANOS_ATUAL}"
HORAS_ATUAL="$(ler PAINEL_TESTE_HORAS .env.atendimento)"; HORAS_ATUAL="${HORAS_ATUAL:-4}"
read -r -p "Horas do teste grátis [$HORAS_ATUAL]: " HORAS; HORAS="${HORAS:-$HORAS_ATUAL}"
ACAO_ATUAL="$(ler PAINEL_ACAO_RENOVAR .env.atendimento)"
read -r -p "Nome da action de RENOVAR no api.php (vazio = renovação manual) [$ACAO_ATUAL]: " ACAO; ACAO="${ACAO:-$ACAO_ATUAL}"

gravar PAINEL_API_URL "$URL" .env.atendimento
gravar PAINEL_API_TOKEN "$TOKEN" .env.atendimento
gravar PAINEL_PLANOS "$PLANOS" .env.atendimento
gravar PAINEL_TESTE_HORAS "$HORAS" .env.atendimento
gravar PAINEL_ACAO_RENOVAR "$ACAO" .env.atendimento
echo "✔ .env.atendimento atualizado"

echo
echo "== Onde chegam os pagamentos FastFlow no Telegram =="
echo "  • Grupo: adicione o bot do Jarvis ao grupo e, no @BotFather, /setprivacy → Disable (ou deixe o bot como admin)."
echo "  • Canal: adicione o bot do Jarvis como ADMIN do canal."
echo "  • Conversa privada com o bot do FastFlow: o Jarvis não lê; encaminhe as mensagens para o bot do Jarvis."
echo "  Para descobrir o ID do grupo/canal: mande uma mensagem lá e rode:"
echo "    docker compose --profile telegram logs --tail 20 telegram"
ATUAL="$(ler PAGAMENTOS_CHAT_ID .env.claude)"
read -r -p "ID do grupo/canal de pagamentos (vazio = só encaminhadas) [$ATUAL]: " CHATS; CHATS="${CHATS:-$ATUAL}"
[ -n "$CHATS" ] && gravar PAGAMENTOS_CHAT_ID "$CHATS" .env.claude

echo "→ Reiniciando o painel e o Telegram…"
docker compose --profile web --profile telegram up -d >/dev/null
sleep 6
echo "→ Testando a consulta (login inexistente, só para ver se a API responde)…"
docker compose --profile web exec -T jarvisweb python3 -c "
import sys; sys.path.insert(0,'/opt/jarvis-bots'); import painel_api
try:
    painel_api.consultar('teste-jarvis-0000'); print('   API respondeu (login de teste existe?!)')
except painel_api.ErroPainel as e:
    print('   API respondeu:', e)
" || echo "   ⚠️ não consegui testar; veja: docker compose --profile web logs --tail 40 jarvisweb"
echo
echo "✅ Pronto. Encaminhe uma mensagem de pagamento antiga para o bot do Jarvis para testar (ela não é processada 2 vezes)."
