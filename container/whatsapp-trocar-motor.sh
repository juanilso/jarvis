#!/usr/bin/env bash
# Troca o motor do WhatsApp (WAHA) para o GOWS: o NOWEB parava de RECEBER mensagens em tempo real
# (enviar funcionava; as mensagens dos clientes só chegavam, horas depois, quando a sessão reiniciava).
# Rode na VPS, dentro de container/, DEPOIS de atualizar o Jarvis:   ./whatsapp-trocar-motor.sh
# Precisa escanear o QR code uma vez (o QR chega no Telegram e aparece em 📱 no painel).
# Voltar ao antigo: no arquivo .env ponha WAHA_IMAGEM=devlikeapro/waha:latest e WAHA_MOTOR=NOWEB e rode de novo.
set -euo pipefail
cd "$(dirname "$0")"
imagem="$(grep -E '^WAHA_IMAGEM=' .env 2>/dev/null | cut -d= -f2- || true)"; imagem="${imagem:-devlikeapro/waha:gows-2026.10.1}"
motor="$(grep -E '^WAHA_MOTOR=' .env 2>/dev/null | cut -d= -f2- || true)"; motor="${motor:-GOWS}"
echo "== Motor do WhatsApp: $motor ($imagem) =="
echo "Você vai precisar do celular da empresa para escanear o QR code (WhatsApp → Aparelhos conectados)."
read -r -p "Continuar? [S/n] " r; case "${r:-s}" in [sS]*) ;; *) echo "Cancelado."; exit 0;; esac

echo "→ Baixando a imagem…"
docker compose --profile whatsapp pull whatsapp
echo "→ Recriando o serviço do WhatsApp…"
docker compose --profile whatsapp up -d --force-recreate whatsapp
echo "→ Esperando o WAHA subir…"
for i in $(seq 1 30); do
  if docker compose --profile whatsapp exec -T whatsapp sh -c 'wget -qO- http://localhost:3000/ping >/dev/null 2>&1 || curl -fs http://localhost:3000/ping >/dev/null 2>&1'; then break; fi
  sleep 3
done
echo "→ Pedindo um QR code novo (vai para o Telegram e para o 📱 no painel)…"
docker compose --profile web exec -T jarvisweb python3 - <<'PY' || echo "  Não consegui pedir pelo painel: abra 📱 no painel e clique em 🔌 Reconectar (QR novo)."
import json, os, urllib.request
req = urllib.request.Request("http://localhost:%s/api/gatilho" % os.environ.get("JARVIS_WEB_PORT", "8090"),
    data=json.dumps({"acao": "atendimento_cmd", "cmd": "/whatsapp", "arg": "reconectar"}).encode(),
    headers={"Authorization": "Bearer " + os.environ.get("JARVIS_GATILHO_TOKEN", ""), "Content-Type": "application/json"})
print("  " + json.loads(urllib.request.urlopen(req, timeout=120).read().decode()).get("texto", "ok"))
PY
echo
echo "Pronto. Escaneie o QR no celular da empresa. Quando conectar, o Jarvis avisa no Telegram."
echo "Depois teste: mande uma mensagem de OUTRO número e rode /whatsapp testar no Telegram."
