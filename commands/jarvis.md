---
description: Jarvis - ponto de entrada único. Entende o pedido em linguagem natural e aciona o fluxo certo (novo projeto, executar, evoluir, decidir, status, modelos).
argument-hint: <qualquer pedido, ex. "toca o projeto", "quero adicionar login", "como estamos?">
---

Pedido: $ARGUMENTS

Carregue a skill `orquestrador`. Depois, identifique a intenção e siga o fluxo correspondente
(arquivos em `commands/` deste plugin), sem pedir confirmação de qual fluxo usar:

- Não existe `docs/PROJETO.md` OU pedido de criar algo novo → fluxo **novo**
- "toca", "continua", "executa", "faz as próximas" → fluxo **executar**
- mudança de escopo, nova funcionalidade, ajuste técnico, problema → fluxo **evoluir**
- respostas a decisões ("D-001 A", "ok pode seguir") → fluxo **decidir**
- "como estamos", "status", "o que falta" → fluxo **status**
- trocar modelo, custo, "mais barato", "mais qualidade" → fluxo **modelos**
- pergunta técnica pontual → responda direto, curto, sem subagentes

Se $ARGUMENTS estiver vazio: mostre o status (fluxo **status**) e as decisões pendentes,
e sugira a próxima ação em 1 linha.
