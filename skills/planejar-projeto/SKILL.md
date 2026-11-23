---
name: planejar-projeto
description: Planejamento de projeto ANTES de desenvolver - descoberta, regras do negócio, fluxos, modelo de dados, integrações (n8n, WhatsApp, pagamentos), riscos, protótipo navegável e experimentos técnicos em laboratório, até um plano aprovado que vira backlog. Use para projetos novos complexos, sistemas com vários perfis de usuário, ou quando o usuário quer "planejar", "desenhar", "testar antes", "validar a ideia".
---

# Planejar antes de desenvolver

Objetivo: chegar ao desenvolvimento sabendo **o que** construir, **para quem**, **como as peças conversam** e com os
**pontos arriscados já testados**. Planejamento bom é curto e visual: o usuário precisa entender em 5 minutos.
Tudo fica em `docs/plano/` (vai para o Git). Nada de código de produção nesta fase.

## Fase 1: Descoberta (uma conversa, não um questionário infinito)
1. Leia o pedido e, se houver, a referência de domínio em `referencias/` desta skill (ex.: `rede-credenciada.md`).
2. Faça **uma mensagem** com no máximo 10 perguntas, cada uma com uma resposta sugerida (o usuário pode só dizer
   "ok"). Cubra: quem usa (perfis), o que cada perfil precisa fazer, como o dinheiro entra e sai, o que já existe hoje
   (planilha, sistema, WhatsApp), integrações, volume esperado, onde vai rodar (cPanel/VPS), prazo, dados sensíveis
   (LGPD), o que fica FORA da primeira versão.
3. Antes das perguntas, reescreva o problema em 1 frase e proponha 2–3 abordagens (MÍNIMA, IDEAL, ALTERNATIVA) com
   esforço e risco; recomende uma.
4. No modo piloto ou se o usuário pedir para seguir sozinho: assuma as respostas sugeridas e marque [premissa].

## Fase 2: Plano (documentos curtos, com diagramas)
Crie em `docs/plano/` (modelos em `referencias/modelos.md`):
- `VISAO.md`: problema, perfis, objetivos, métrica de sucesso, MVP x depois, fora de escopo.
- `FLUXOS.md`: as jornadas principais de cada perfil, passo a passo, com diagrama Mermaid (`flowchart`/`sequenceDiagram`).
- `DOMINIO.md`: entidades, campos principais, relações (Mermaid `erDiagram`), estados (Mermaid `stateDiagram`) e
  **regras de negócio numeradas** (R1, R2…): elas viram testes depois.
- `INTEGRACOES.md`: cada integração com gatilho, dados de entrada/saída, quem chama quem, o que acontece se falhar.
  Automações no n8n: um quadro por fluxo (gatilho → passos → resultado) e o que fica no sistema x no n8n
  (regra: regra de negócio e dados no sistema; n8n para orquestrar avisos, integrações e rotinas).
- `ARQUITETURA.md`: stack, módulos, telas por perfil, onde roda, autenticação/permissões, LGPD, backups.
- `RISCOS.md`: riscos e **hipóteses a testar** (H1, H2…), cada uma com como testar e o critério de sucesso.
- `ROADMAP.md`: marcos pequenos e entregáveis: M0 laboratório/protótipo · M1 MVP · M2… Cada marco com critério de pronto.

## Fase 3: Laboratório (testar antes de construir)
Tudo descartável, fora do código de produção:
- **Protótipo navegável** em `prototipo/` (HTML/CSS/JS com dados falsos, sem banco): as telas principais de cada perfil,
  com a qualidade visual da skill `refatorar-site`. Navegação funcionando entre as telas das jornadas. O usuário
  clica pela prévia ao vivo (`/previa`; o protótipo abre em `/prototipo/`; se o projeto já tem `public/`,
  coloque em `public/prototipo/`). Crie `.jarvis/jornadas.json` das jornadas
  e rode `jarvis-site testar prototipo` + prints.
- **Experimentos técnicos** em `laboratorio/<hipotese>/` para cada hipótese de risco: um script pequeno, uma consulta,
  uma chamada de API, um fluxo do n8n. Para o n8n use `jarvis-n8n` (cria fluxos [LAB] desativados, ativa só os
  [LAB], chama o webhook e lê o resultado das execuções). Nunca altere fluxos que não sejam [LAB].
- Registre cada experimento em `docs/plano/EXPERIMENTOS.md`: hipótese · como testei · resultado (com evidência:
  saída, print, id da execução) · decisão. Hipótese que falhou muda o plano: atualize os documentos.

## Fase 4: Revisão e aprovação (aqui SIM o usuário decide)
Mande um resumo de até 20 linhas: o problema em 1 frase, os perfis, o MVP, as decisões principais, os
experimentos (✅/❌), os riscos que sobraram, o tamanho estimado (marcos e número de tarefas) e o link da prévia do
protótipo com o roteiro do que clicar. Pergunte: aprovar, ajustar (o quê) ou cortar escopo.
Ajustes voltam para a fase 2 ou 3 só no que mudou.

## Fase 5: Do plano para o desenvolvimento
Aprovado: gere os documentos de orquestração (`docs/PROJETO.md`, `STACK.md`, `DECISOES.md`, `BACKLOG.md`, `ESTADO.md`)
a partir do plano. O backlog segue o ROADMAP (M1 primeiro), com tarefas atômicas e tags, e cada regra de negócio Rn
vira pelo menos um teste. Os fluxos do n8n aprovados viram tarefas `[automacao]` com o JSON exportado do laboratório.
Sugira: `/piloto desenvolver o M1 conforme docs/plano` (ou `/jarvis toca o projeto`).

## Bom senso
- Projeto simples (um site, uma landing page): pule direto para `/jarvis:novo`; esta skill é para sistemas.
- Planejamento não é fim: se passou de 1 dia sem protótipo na tela, simplifique.
- Use os ajudantes (`jarvis-ajudante`) para rascunhar textos longos, dados falsos do protótipo e listas; revise.
