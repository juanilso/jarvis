#!/usr/bin/env bash
# Liga o Hermes Agent como ajudante do Jarvis, usando o MESMO gateway do .env.claude.
# Rode na VPS, dentro da pasta container/:   ./hermes-configurar.sh            (mesmo gateway do Jarvis)
#                                            ./hermes-configurar.sh <ID>       (outro modelo do gateway)
#                                            ./hermes-configurar.sh --nous     (modelo e ferramentas da Nous)
# Pode rodar de novo quando quiser (por exemplo, depois de trocar a chave do gateway).
set -euo pipefail
cd "$(dirname "$0")"

ENV=.env.claude
[ -f "$ENV" ] || { echo "Não achei $ENV nesta pasta."; exit 1; }

ler() { { grep -E "^$1=" "$ENV" || true; } | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"; }
# o aviso "install out of sync (pnpm…)" é só da interface de terminal do Hermes; não afeta a API
H() { docker compose --profile hermes exec -T hermes hermes "$@" 2>&1 | grep -v "install out of sync" || true; }
esperar() {  # espera a API do Hermes responder (até ~3 min)
  local i
  printf "   aguardando o Hermes ligar"
  for i in $(seq 1 60); do
    docker compose exec -T dev jarvis-hermes --status >/dev/null 2>&1 && return 0
    printf "."; sleep 3
  done
  echo; return 1
}
personalidade() {  # SOUL.md em português (guarda a anterior, se existir) + pasta /saida gravável
  docker compose --profile hermes exec -T -u root hermes sh -c 'mkdir -p /saida && chmod 777 /saida' >/dev/null 2>&1 || true
  docker compose --profile hermes exec -T hermes sh -c \
    'H=${HERMES_HOME:-/opt/data}; [ -f "$H/SOUL.md" ] && ! cmp -s "$H/SOUL.md" /opt/jarvis-hermes/SOUL.md && cp "$H/SOUL.md" "$H/SOUL.md.anterior"; cp /opt/jarvis-hermes/SOUL.md "$H/SOUL.md"' \
    && echo "✔ Personalidade do Hermes em português (SOUL.md)" || echo "   (não consegui copiar o SOUL.md; o Jarvis ainda pede português em cada pedido)"
}

CHAVE_GW="$(ler ANTHROPIC_API_KEY)"; [ -n "$CHAVE_GW" ] || CHAVE_GW="$(ler ANTHROPIC_AUTH_TOKEN)"
BASE_GW="$(ler ANTHROPIC_BASE_URL)"
MODELO="${1:-$(ler HERMES_MODELO)}"; [ -n "$MODELO" ] || MODELO="$(ler ANTHROPIC_DEFAULT_SONNET_MODEL)"
[ -n "$MODELO" ] || MODELO="claude-sonnet-5-5"
[ -n "$CHAVE_GW" ] || { echo "Falta ANTHROPIC_API_KEY (ou ANTHROPIC_AUTH_TOKEN) no $ENV."; exit 1; }

# Opção: só atualizar a personalidade (português) sem mexer no modelo
if [ "${1:-}" = "--portugues" ]; then
  docker compose --profile hermes up -d hermes; sleep 5; personalidade
  docker compose --profile hermes restart hermes; exit 0
fi

# Opção: usar o modelo e as ferramentas da própria Nous (Nous Portal, conta e créditos separados)
if [ "${1:-}" = "--nous" ]; then
  CHAVE_H="$(ler HERMES_API_KEY)"
  if [ -z "$CHAVE_H" ]; then
    CHAVE_H="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    printf '\n# Hermes Agent (ajudante do Jarvis)\nHERMES_API_KEY=%s\nHERMES_URL=http://hermes:8642\n' "$CHAVE_H" >> "$ENV"
  fi
  umask 077; echo "API_SERVER_KEY=$CHAVE_H" > .env.hermes
  grep -q '^HERMES_MODO=' "$ENV" && sed -i 's/^HERMES_MODO=.*/HERMES_MODO=nous/' "$ENV" || echo "HERMES_MODO=nous" >> "$ENV"
  docker compose --profile hermes pull hermes
  docker compose --profile hermes up -d --force-recreate hermes
  sleep 8
  echo "→ Abra o link que aparecer, entre na sua conta Nous e autorize (modelo + busca, navegador, voz e imagens)."
  docker compose --profile hermes exec -it hermes hermes setup --portal
  personalidade
  docker compose --profile hermes restart hermes
  docker compose --profile web --profile telegram up -d
  esperar || true
  docker compose exec -T dev jarvis-hermes "Responda apenas: OK" && echo "✅ Hermes usando o Nous Portal." \
    || echo "⚠️ Não respondeu. Veja: docker compose --profile hermes logs --tail 80 hermes"
  exit 0
fi

# chave que só o Jarvis conhece para falar com o Hermes
CHAVE_H="$(ler HERMES_API_KEY)"
if [ -z "$CHAVE_H" ]; then
  CHAVE_H="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  printf '\n# Hermes Agent (ajudante do Jarvis)\nHERMES_API_KEY=%s\nHERMES_URL=http://hermes:8642\n' "$CHAVE_H" >> "$ENV"
  echo "✔ HERMES_API_KEY criada no $ENV"
fi

# segredos que o Hermes recebe (só estes; o resto do .env.claude fica fora dele)
TOKEN_GW="$(ler ANTHROPIC_AUTH_TOKEN)"
umask 077
{
  echo "ANTHROPIC_API_KEY=$CHAVE_GW"
  [ -n "$TOKEN_GW" ] && echo "ANTHROPIC_AUTH_TOKEN=$TOKEN_GW"
  [ -n "$BASE_GW" ] && echo "ANTHROPIC_BASE_URL=$BASE_GW"
  echo "API_SERVER_KEY=$CHAVE_H"
} > .env.hermes
echo "✔ .env.hermes atualizado (chave e endereço do gateway para o Hermes)"

echo "→ Baixando e ligando o Hermes (a primeira vez demora alguns minutos)…"
docker compose --profile hermes pull hermes
docker compose --profile hermes up -d --force-recreate hermes
sleep 8

modo_anthropic() {
  echo "→ Modo 1: API da Anthropic pelo gateway · $MODELO${BASE_GW:+ · $BASE_GW}"
  H config set model.provider anthropic >/dev/null
  H config set model.default "$MODELO" >/dev/null
  if [ -n "$BASE_GW" ]; then H config set model.base_url "$BASE_GW" >/dev/null || true; fi
}
modo_openai() {
  local url="${BASE_GW%/}"; case "$url" in */v1) ;; *) url="$url/v1";; esac
  echo "→ Modo 2: gateway no formato OpenAI · $MODELO · $url"
  H config set OPENAI_API_KEY "$CHAVE_GW" >/dev/null || true
  H config set model.provider custom >/dev/null
  H config set model.base_url "$url" >/dev/null
  H config set model.default "$MODELO" >/dev/null
}
testar() {  # 0 = funcionou · 1 = o gateway recusou · 2 = o Hermes não ligou
  docker compose --profile hermes restart hermes >/dev/null 2>&1
  if ! esperar; then
    echo "   O Hermes não ligou. Últimas linhas do registro:"
    docker compose --profile hermes logs --tail 25 hermes 2>&1 | grep -v "install out of sync"
    return 2
  fi
  echo " ligado"
  local r; r="$(docker compose exec -T dev jarvis-hermes "Responda apenas: OK" 2>&1 || true)"
  echo "   resposta: $(echo "$r" | head -c 300)"
  echo "$r" | grep -qiE "401|403|invalid|rejected|recusou|não consegui|error|erro" && return 1
  echo "$r" | grep -qi "ok"
}

personalidade
echo "→ Reiniciando o painel e o Telegram (para lerem a chave nova)…"
docker compose --profile web --profile telegram up -d >/dev/null

MODO="$(ler HERMES_MODO)"
if [ "$MODO" = "openai" ] || [ -z "$BASE_GW" ]; then
  [ -z "$BASE_GW" ] && modo_anthropic || modo_openai
  testar && OK=1 || OK=0
else
  modo_anthropic
  RC=0; testar || RC=$?
  if [ "$RC" = 0 ]; then OK=1
  elif [ "$RC" = 2 ]; then OK=0
  else
    echo "   O modo 1 não funcionou; tentando o modo 2…"
    modo_openai
    if testar; then OK=1; grep -q '^HERMES_MODO=' "$ENV" || echo "HERMES_MODO=openai" >> "$ENV"; else OK=0; fi
  fi
fi

if [ "$OK" = 1 ]; then
  echo
  echo "✅ Pronto. No painel ou no Telegram: /hermes <pedido>   (ex.: /hermes pesquise gateways PIX para PHP com fontes)"
else
  echo
  echo "⚠️ O Hermes ainda não conseguiu usar o gateway. Veja os registros:"
  echo "   docker compose --profile hermes logs --tail 80 hermes"
  echo "   Confira se o modelo '$MODELO' existe no gateway (/modelos no painel) e rode de novo:"
  echo "   ./hermes-configurar.sh <ID-do-modelo>"
  echo "   Ou configure pelo assistente do Hermes: docker compose --profile hermes exec -it hermes hermes model"
fi
