---
description: Mostra as decisões pendentes em lote para você escolher e destrava as tarefas
argument-hint: [ex. "D-001 A, D-002 B" | ok]
---

Leia `docs/DECISOES-PENDENTES.md`.

Se $ARGUMENTS tiver respostas, aplique direto ("ok" = seguir todas as recomendações).
Caso contrário, mostre cada decisão pendente em até 4 linhas (pergunta, opções, recomendação) e
peça todas as respostas numa única mensagem.

Para cada decisão tomada: marque `decidida — <opção>`, registre o ADR em `docs/DECISOES.md`,
volte as tarefas afetadas para `pendente` (ou peça ao `arquiteto` para ajustar o backlog se a decisão mudar o escopo).
Termine em 2 linhas: o que foi destravado e a sugestão `/jarvis toca o projeto`.
