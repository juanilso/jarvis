#!/usr/bin/env bash
# Instala as extensões aprovadas na biblioteca do Jarvis (marketplace oficial da Anthropic)
# e reforça as proteções. Rode dentro do contêiner dev:  jarvis-extras
set -u
echo "== Jarvis: extensões aprovadas =="

claude plugin marketplace add anthropics/claude-plugins-official 2>/dev/null || true
claude plugin marketplace update claude-plugins-official 2>/dev/null || true
claude plugin marketplace update jarvis-marketplace 2>/dev/null || true

claude plugin marketplace add heydamir/unslop 2>/dev/null || true
claude plugin marketplace add haydenschmitty/floorplan 2>/dev/null || true
for p in unslop@heydamir floorplan@floorplan; do
  echo "-> $p"
  claude plugin install "$p" || echo "   (não consegui instalar $p agora; tente de novo depois)"
done

for p in frontend-design canva; do
  echo "-> $p"
  claude plugin install "$p@claude-plugins-official" || echo "   (não consegui instalar $p agora; tente de novo depois)"
done

echo "-> atualizando o plugin Jarvis"
claude plugin uninstall jarvis@jarvis-marketplace >/dev/null 2>&1 || true
claude plugin install jarvis@jarvis-marketplace || true

echo "-> permissões (bloqueio da execução de código arbitrário no navegador)"
bash /opt/jarvis/instalar-permissoes.sh

cat <<'MSG'

Pronto.
- Design: a skill frontend-design já é usada pelo agente designer.
- Navegador: o MCP "playwright" vem com o plugin Jarvis (veja com /mcp dentro do Claude).
- Canva: falta autorizar a sua conta. Dentro do Claude rode /mcp, escolha "canva" e "Authenticate".
  Abra o link no navegador do PC e autorize. Se a página final der erro de "localhost",
  copie o endereço inteiro dessa página e rode NA VPS:
     docker compose exec dev curl -s "COLE_O_ENDERECO_AQUI"
  (isso entrega a autorização ao Claude dentro do contêiner).
MSG
