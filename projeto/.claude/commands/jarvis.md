---
description: Jarvis - ponto de entrada único. Entende o pedido em linguagem natural e aciona o fluxo certo (novo projeto, executar, evoluir, decidir, status, modelos).
argument-hint: <qualquer pedido, ex. "toca o projeto", "quero adicionar login", "como estamos?">
---

Pedido: $ARGUMENTS

Carregue a skill `orquestrador`. Depois, identifique a intenção e siga o fluxo correspondente
(arquivos em `commands/` deste plugin), sem pedir confirmação de qual fluxo usar:

- Existe código mas não existe `docs/PROJETO.md` → fluxo **adotar** (antes de qualquer outra coisa)
- Pasta vazia OU pedido de criar algo novo → fluxo **novo**
- "corrigir", "erro", "bug", "não está funcionando" → crie UMA tarefa no backlog com o erro como critério
  (primeiro um teste que reproduz o erro, depois a correção) e rode o fluxo **executar** só nela
- "toca", "continua", "executa", "faz as próximas" → fluxo **executar**
- mudança de escopo, nova funcionalidade, ajuste técnico, problema → fluxo **evoluir**
- respostas a decisões ("D-001 A", "ok pode seguir") → fluxo **decidir**
- "como estamos", "status", "o que falta" → fluxo **status**
- URL de site + "parecido", "moderno", "redesenhar", "melhorar o visual" → fluxo **redesenhar**
- instalar/avaliar skill, plugin ou MCP → fluxo **skill** (portão de segurança)
- trocar modelo, custo, "mais barato", "mais qualidade" → fluxo **modelos**
- pergunta técnica pontual → responda direto, curto, sem subagentes

Se $ARGUMENTS estiver vazio: mostre o status (fluxo **status**) e as decisões pendentes,
e sugira a próxima ação em 1 linha.
