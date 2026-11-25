#!/usr/bin/env bash
# Cadastra os servidores que o Jarvis pode acessar (SSH, SFTP e MySQL/MariaDB) para homologar e corrigir na hora.
# Rode na VPS, dentro de container/:  ./servidores-configurar.sh
#   - Homologação: o Jarvis lê e altera, sempre com backup antes (arquivo e tabelas).
#   - Produção: somente leitura (consultas, logs, SELECT, download). Ele nunca envia nada para produção.
# As senhas ficam só no volume "servidores-segredos" (modo 600). Nunca mande senha pelo chat ou pelo Telegram.
# Recomendado: acesso pela chave SSH do Jarvis (o assistente mostra a chave pública para colocar no servidor)
# e um usuário de banco só do banco de homologação.
set -euo pipefail
cd "$(dirname "$0")"
if docker compose --profile web ps --status running jarvisweb 2>/dev/null | grep -q jarvisweb; then
  docker compose --profile web exec -it jarvisweb jarvis-servidor configurar
else
  docker compose --profile web run --rm --no-deps -it jarvisweb jarvis-servidor configurar
fi
echo
echo "Pronto. No Telegram ou no painel: /servidores (lista e últimas ações) · /servidores testar <nome>"
