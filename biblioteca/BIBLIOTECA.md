# Biblioteca do Jarvis: skills, plugins e MCPs aprovados

Tudo que entra no Jarvis passa antes por `/jarvis:skill` (verificação de segurança com a skill-scanner).
Status: ✅ aprovada · ⚠️ atenção (decisão do usuário) · ❌ reprovada

| Item | Tipo | Fonte | Para quê | Verificação | Status |
|---|---|---|---|---|---|
| frontend-design | plugin/skill | anthropics/claude-plugins-official | Design de interfaces com qualidade (evita visual genérico) | 2026-11-20 · 0 achados | ✅ |
| canva | plugin + MCP | anthropics/claude-plugins-official → canva-sdks/canva-skills | Criar, editar, redimensionar e checar marca no Canva | 2026-11-20 · 0 achados nas skills; MCP oficial https://mcp.canva.com/mcp | ✅ |
| playwright (MCP) | MCP | microsoft/playwright-mcp (via `jarvis-playwright-mcp`) | Navegador: analisar sites, prints, testes visuais | 2026-11-20 · oficial Microsoft; `browser_run_code_unsafe` bloqueado | ✅ |
| gstack (ideias) | adaptação | garrytan/gstack (MIT) | Checklists de revisão, design, QA e premissas, reescritos no Jarvis | 2026-11-20 · nada instalado nem executado; ver CREDITOS.md | ✅ |
| unslop | plugin/skill | heydamir/unslop (CC BY 4.0) | Tirar a "cara de IA" de telas existentes | 2026-11-20 · 0 achados; scripts só fazem prints locais | ✅ |
| floorplan | plugin/skill | haydenschmitty/floorplan (MIT) | Mapa interativo do sistema + check-up de segurança (PHP puro e Laravel) | 2026-11-20 · sem telemetria; script de status local na carga (revisado) | ✅ |
| skill-scanner | skill | getsentry/skills (Apache 2.0, embutida no Jarvis) | Verificar skills antes de instalar | 2026-11-20 · revisada | ✅ |
| Hermes Agent | serviço (contêiner) | NousResearch/hermes-agent (MIT), imagem oficial `nousresearch/hermes-agent` | Ajudante: pesquisa, análise e segunda opinião via `/hermes` e `jarvis-hermes` | 2026-11-21 · isolado: sem porta publicada, `/workspace` só leitura, sem GH_TOKEN/Telegram; respostas tratadas como dados | ✅ |
| n8n | serviço (contêiner) | n8n-io/n8n, imagem oficial `docker.n8n.io/n8nio/n8n` (Sustainable Use License: uso interno permitido) | Rotinas e integrações que chamam o Jarvis/Hermes | 2026-11-21 · só pela VPN; fala com o Jarvis por token; rotinas sem edição/push/deploy | ✅ |
| last30days (motor) | script (embutido na imagem) | mvanhorn/last30days-skill (MIT), commit `bb2f1ed` | `/tendencias` e `jarvis-tendencias`: o que estão falando nos últimos 30 dias | 2026-11-21 · skill-scanner: 6 alertas revisados (falsos positivos/testes removidos); roda com ambiente limpo, sem chaves, cookies, publicação ou instalação de extras; fontes limitadas a reddit, hackernews, github, polymarket, stocktwits | ✅ |
| WAHA Core | serviço (contêiner) | devlikeapro/waha (Apache 2.0), imagem oficial `devlikeapro/waha` | WhatsApp Web para o atendimento automático | 2026-11-21 · sem porta aberta; chave só no painel; o modelo do atendimento não tem ferramentas; não oficial (risco de bloqueio do número) | ✅ |

## Instalar os aprovados
No contêiner `dev`: `jarvis-extras` (instala canva do marketplace oficial e aplica as proteções). A `frontend-design`
já vem no plugin (skills/frontend-design, Apache 2.0), junto com a skill própria `refatorar-site`.
