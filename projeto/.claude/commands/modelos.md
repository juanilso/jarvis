---
description: Mostra ou troca o perfil de modelos do projeto (economico, equilibrado, maximo) e exceções por papel
argument-hint: '[economico | equilibrado | maximo | "revisor opus" | vazio para recomendar]'
---

Carregue a skill `orquestrador` e leia `docs/ORQUESTRACAO.md`, `docs/PROJETO.md` e `docs/BACKLOG.md`.

- Vazio: mostre o perfil atual e a tabela de modelos por papel, recomende o perfil ideal
  (com o critério da skill e 1 linha de motivo) e estime o impacto relativo de custo
  (menor, igual ou maior). Pergunte se deve trocar.
- Nome de perfil: aplique-o. Se for `maximo` em projeto já em andamento, confirme antes (portão de custo).
- "<papel> <modelo>": registre a exceção em `docs/ORQUESTRACAO.md`.

Registre toda troca no "Histórico de trocas". Responda em até 8 linhas.
