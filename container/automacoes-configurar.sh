#!/usr/bin/env bash
# Liga o n8n (rotinas e integrações) e o gatilho seguro do Jarvis.
# Rode na VPS, dentro da pasta container/:   ./automacoes-configurar.sh
# Pode rodar de novo: mantém a chave do n8n e o token; reimporta os fluxos de exemplo (desativados).
set -euo pipefail
cd "$(dirname "$0")"

ENV=.env.claude
[ -f "$ENV" ] || { echo "Não achei $ENV nesta pasta."; exit 1; }
ler() { { grep -E "^$1=" "$2" 2>/dev/null || true; } | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }
gerar() { openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'; }

TOKEN="$(ler JARVIS_GATILHO_TOKEN "$ENV")"
if [ -z "$TOKEN" ]; then
  TOKEN="$(gerar)"
  printf '\n# Gatilho das rotinas (n8n -> Jarvis)\nJARVIS_GATILHO_TOKEN=%s\n' "$TOKEN" >> "$ENV"
  echo "✔ JARVIS_GATILHO_TOKEN criado no $ENV"
fi
CHAVE_N8N="$(ler N8N_ENCRYPTION_KEY .env.n8n)"; [ -n "$CHAVE_N8N" ] || CHAVE_N8N="$(gerar)"
umask 077
printf 'N8N_ENCRYPTION_KEY=%s\nJARVIS_TOKEN=%s\n' "$CHAVE_N8N" "$TOKEN" > .env.n8n
echo "✔ .env.n8n atualizado (a chave do n8n é mantida entre execuções)"

echo "→ Baixando e ligando o n8n…"
docker compose --profile automacoes pull n8n
docker compose --profile automacoes up -d n8n
echo "→ Reiniciando o painel e o Telegram (para lerem o token)…"
docker compose --profile web --profile telegram up -d >/dev/null

printf "   aguardando o n8n ligar"
for i in $(seq 1 60); do
  docker compose --profile automacoes exec -T n8n wget -qO- http://localhost:5678/healthz >/dev/null 2>&1 && break
  printf "."; sleep 3
done
echo

echo "→ Importando os fluxos de exemplo (ficam DESATIVADOS até você ligar)…"
docker compose --profile automacoes exec -T -u node n8n n8n import:workflow --separate --input=/opt/jarvis-n8n/fluxos \
  || echo "   (não consegui importar; dá para importar pela tela: menu ⋯ → Import from file, arquivos em container/n8n/fluxos)"
docker compose --profile automacoes restart n8n >/dev/null

echo "→ Testando o gatilho do Jarvis…"
sleep 5
if docker compose --profile web exec -T jarvisweb python3 - "$TOKEN" <<'PY'
import json, sys, urllib.request
req = urllib.request.Request("http://localhost:8090/api/gatilho", data=json.dumps({"acao": "status", "rotina": "teste"}).encode(),
                             headers={"Authorization": "Bearer " + sys.argv[1], "Content-Type": "application/json"})
print("   gatilho:", "ok" if json.load(urllib.request.urlopen(req, timeout=20)).get("ok") else "falhou")
PY
then :; else echo "   ⚠️ o gatilho não respondeu; veja: docker compose --profile web logs --tail 50 jarvisweb"; fi

NOME="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null || true)"
echo
echo "✅ n8n ligado. Falta publicar na VPN (uma vez):"
echo "   sudo tailscale serve --bg --https=5678 http://127.0.0.1:5678"
echo "   Depois abra: https://${NOME:-<nome-da-vps>.ts.net}:5678  (no 1º acesso, crie o usuário dono)"
echo "   Os fluxos 'Jarvis · …' já estão lá: revise o texto/projeto e ative no botão Active."
echo "   No painel do Jarvis, o botão 🏢 abre o escritório com as rotinas."
