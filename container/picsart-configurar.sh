#!/usr/bin/env bash
# Conecta a sua conta Picsart ao Jarvis (MCP oficial hospedado da Picsart: imagens, banners e vídeos).
# Rode na VPS, dentro de container/:  ./picsart-configurar.sh
# Não usa chave de API: você entra com a sua conta Picsart no navegador do PC. Gerar gasta créditos da conta.
set -euo pipefail
cd "$(dirname "$0")"
docker compose exec dev sh -c 'claude mcp get picsart-gen-ai >/dev/null 2>&1 || claude mcp add --scope user --transport http picsart-gen-ai https://api.picsart.com/gen-ai/mcp'
cat <<'MSG'

Falta autorizar (uma vez só):
 1) Abra o Claude no contêiner:   docker compose exec -it dev claude
 2) Digite /mcp, escolha "picsart-gen-ai" e "Authenticate".
 3) Abra o link no navegador do PC e entre com a sua conta Picsart.
 4) Se a última página der erro de "localhost", copie o endereço INTEIRO dessa página e rode aqui na VPS:
       docker compose exec dev curl -s "COLE_O_ENDERECO_AQUI"
 5) Volte ao Claude, /mcp deve mostrar picsart-gen-ai conectado. Saia com /exit.

Depois é só pedir ao Jarvis: "crie um banner 1920x600 para a página X" ou "gere o fundo do vídeo dos jogos com a Picsart".
MSG
