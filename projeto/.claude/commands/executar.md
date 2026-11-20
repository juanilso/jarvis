---
description: Executa o backlog de forma autônoma (explorar → executar → testar → revisar → commit) com o modelo do perfil ativo, sem pedir aceite a cada etapa
argument-hint: [quantidade | T-ID | tudo]
---

Alvo: $ARGUMENTS (se vazio, até 5 tarefas).

Carregue a skill `orquestrador`. Leia `docs/ORQUESTRACAO.md` (perfil), `docs/ESTADO.md` e `docs/BACKLOG.md`.

Para cada tarefa `pendente` com as dependências `feita`, em ordem:
1. Marque `em_andamento`.
2. `explorador` (modelo do perfil): mapa do código para a tarefa.
3. Executor pela tag ([db] dba, [android] android, [deploy] deploy, [design] designer, sem tag desenvolvedor),
   com o modelo do perfil (ou `[modelo:x]` da tarefa): ID + critério + mapa.
   - `precisa_decisao` → registre em DECISOES-PENDENTES, marque `aguardando_decisao` e vá para a próxima.
4. `testador`: falhou → reenvie só as falhas ao executor (máx. 2 voltas).
5. `revisor`: CORRIGIR → reenvie só as correções (máx. 2 voltas).
6. Aprovado → `git add -A && git commit -m "<tipo>(T-XXX): <título>"` e marque `feita`.
7. Depois de 2 falhas, suba um nível de modelo nessa tarefa; depois de 3 falhas, chame o `arquiteto`;
   se ainda falhar, marque `bloqueada — motivo` e siga.

Nunca peça confirmação entre etapas e nunca faça push.
No fim: `documentador` atualiza ESTADO e CHANGELOG. Relatório de até 15 linhas com feitas, bloqueadas,
decisões pendentes (sugira `/decidir`), próximas tarefas e se vale `/compact`.
