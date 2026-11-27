#!/usr/bin/env bash
# Liga o cofre de senhas dos agentes (Vaultwarden + cofre do Jarvis).
# Rode na VPS, dentro da pasta container/:   ./cofre-configurar.sh
# Pode rodar de novo (mantém o token e as senhas). Etapas: liga o Vaultwarden → você cria a conta → o script
# fecha os cadastros e guarda o login da conta no cofre (só dentro do contêiner jarvis-cofre).
set -euo pipefail
cd "$(dirname "$0")"
ENV=.env.claude
[ -f "$ENV" ] || { echo "Não achei $ENV nesta pasta."; exit 1; }
ler() { { grep -E "^$1=" "$2" 2>/dev/null || true; } | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }
gerar() { openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
pdef() { touch .env; if grep -qE "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi; }

[ -n "$(ler JARVIS_GATILHO_TOKEN "$ENV")" ] || { echo "Antes rode ./automacoes-configurar.sh (o cofre te avisa pelo gatilho)."; }
if [ -z "$(ler COFRE_TOKEN "$ENV")" ]; then
  printf '\n# Cofre dos agentes (./cofre-configurar.sh)\nCOFRE_TOKEN=%s\n' "$(gerar)" >> "$ENV"
  echo "✔ COFRE_TOKEN criado no $ENV"
fi

# endereço HTTPS pelo Tailscale (o app do Bitwarden e o site do cofre exigem HTTPS)
URL=""
if command -v tailscale >/dev/null 2>&1; then
  NOME="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null || true)"
  if [ -n "$NOME" ]; then
    tailscale serve --bg --https=9443 http://127.0.0.1:8222 >/dev/null 2>&1 || true
    URL="https://$NOME:9443"
    pdef COFRE_DOMINIO "$URL"
  fi
fi

echo "→ Construindo e ligando o cofre…"
docker compose --profile cofre build cofre >/dev/null
docker compose --profile cofre up -d vaultwarden cofre

if [ "$(ler COFRE_CADASTRO .env)" != "false" ]; then
  cat <<TXT

=== 1) Crie a conta do cofre ===
Abra ${URL:-https://<sua-vps>.ts.net:9443 (rode: tailscale serve --bg --https=9443 http://127.0.0.1:8222)}
no PC ou no celular (com o Tailscale ligado) e clique em "Criar conta".
  • Use um e-mail qualquer seu e uma senha mestra FORTE (anote: ela abre o cofre).
  • Essa conta é SÓ para os acessos que os agentes podem usar. Banco, cartão etc. ficam fora.
Depois crie as pastas (exatamente com estes nomes): Pessoal, E-mail, Portais, Google, Servidores.
No celular: app Bitwarden › "Auto-hospedado" › servidor ${URL:-(o endereço acima)}.
TXT
  read -r -p "Criou a conta? [Enter para continuar] " _
  pdef COFRE_CADASTRO false
  docker compose --profile cofre up -d vaultwarden >/dev/null
  echo "✔ Cadastro de novas contas desligado (só a sua existe)."
fi

echo
echo "=== 2) Login da conta no cofre do Jarvis ==="
docker compose --profile cofre exec -it cofre python3 /opt/cofre/broker.py configurar

echo "→ Reiniciando o painel e o Telegram (para lerem o COFRE_TOKEN)…"
docker compose --profile web --profile telegram up -d --force-recreate jarvisweb telegram >/dev/null
cat <<TXT

✔ Pronto. Como usar:
  • Cadastre os acessos no cofre (site ou app Bitwarden), cada um na pasta certa:
      E-mail   → usuário = seu e-mail, senha = senha do e-mail (Gmail: senha de app)
      Google   → item "Google": usuário = client_id, senha = client_secret (para a Agenda)
      Pessoal / Portais / Servidores → o resto
  • No painel: 🧠 Cérebro › 👤 Assistente pessoal (conectar Google, ver pendências).
  • Ações que saem para fora (enviar e-mail, apagar compromisso) chegam com um código no seu Telegram/WhatsApp:
    responda ao Jarvis "ok 123456" para confirmar.
TXT
