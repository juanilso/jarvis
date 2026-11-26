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

echo "-> skills de design, SEO e segurança (revisadas; atualização só manual, com nova revisão)"
# Commits revisados em 26/11/2026: claude-seo 5d7d85e · taste-skill d1a2bb4 · impeccable 2fc5e14 · hallmark 04977e1.
# Não rodamos "marketplace update" nelas aqui de propósito: versão nova = revisar antes (jarvis-extras --atualizar-design).
for m in AgriciDaniel/claude-seo Leonxlnx/taste-skill pbakaus/impeccable Nutlope/hallmark; do
  claude plugin marketplace add "$m" 2>/dev/null || true
done
if [ "${1:-}" = "--atualizar-design" ]; then
  for n in agricidaniel-claude-seo taste-skill impeccable hallmark; do claude plugin marketplace update "$n" 2>/dev/null || true; done
fi
for p in claude-seo@agricidaniel-claude-seo taste-skill@taste-skill impeccable@impeccable hallmark@hallmark \
         claude-security@claude-plugins-official; do
  echo "-> $p"
  claude plugin install "$p" || echo "   (não consegui instalar $p agora; tente de novo depois)"
done

echo "-> Picsart (MCP oficial hospedado: imagens, banners e vídeos com a sua conta Picsart)"
claude mcp get picsart-gen-ai >/dev/null 2>&1 || \
  claude mcp add --scope user --transport http picsart-gen-ai https://api.picsart.com/gen-ai/mcp \
  || echo "   (não consegui adicionar o Picsart agora; tente de novo depois)"

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
- Design: taste-skill (sites institucionais), hallmark (landing/variação de estilo, estudar referência),
  impeccable (/impeccable audit, polish, critique em telas prontas). SEO: /seo audit <site>.
  Segurança: /claude-security (auditoria oficial da Anthropic: varre o projeto, confirma achados e propõe correções)
  e /security-review (nativo, revisa só as mudanças).
- Picsart: mesma coisa. Dentro do Claude rode /mcp, escolha "picsart-gen-ai" e "Authenticate", entre com a sua
  conta Picsart no PC e, se a página final der erro de "localhost", use o mesmo comando do curl acima.
  Gerar imagem/vídeo gasta créditos da sua conta Picsart (o Jarvis consulta o preço antes).
MSG
