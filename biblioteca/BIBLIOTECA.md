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

## Instalar os aprovados
No contêiner `dev`: `jarvis-extras` (instala frontend-design e canva do marketplace oficial e aplica as proteções).
