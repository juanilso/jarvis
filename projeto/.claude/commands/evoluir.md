---
description: Discute uma evolução de escopo ou um ajuste técnico, apresenta opções e atualiza o escopo, as decisões e o backlog
argument-hint: '<mudança desejada ou problema técnico>'
---

Proposta: $ARGUMENTS

Carregue a skill `orquestrador`. O `arquiteto` (modelo do perfil) lê PROJETO, STACK, DECISOES e ESTADO
e devolve, em até 15 linhas: o impacto no escopo e na arquitetura, 2 ou 3 opções com prós, contras e custo relativo,
uma recomendação e as tarefas a criar, alterar ou cancelar.

Apresente ao usuário e discuta até ele escolher. Depois, o `arquiteto` atualiza PROJETO, DECISOES (novo ADR)
e BACKLOG. Se a mudança alterar a criticidade do projeto, sugira rever o perfil em `/modelos`.
Confirme em 3 linhas.
