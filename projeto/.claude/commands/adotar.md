---
description: Adota um projeto que já existe (sem docs do Jarvis) mapeando o código real, sem alterar nada
argument-hint: '[observações, ex. "painel admin PHP com gateway de pagamento"]'
---

Observações do usuário: $ARGUMENTS

Carregue a skill `orquestrador`. Nada de código é alterado neste fluxo.

1. `explorador` (haiku), em até 40 linhas: estrutura de pastas, ponto de entrada, rotas/telas,
   acesso ao banco (tabelas principais), integrações externas (gateways, APIs, webhooks),
   autenticação e perfis de acesso, testes existentes, versão do PHP e dependências.
2. `arquiteto` (modelo do perfil), com base no mapa: cria `docs/` a partir de `templates/`.
   - PROJETO.md descreve o sistema COMO ELE É HOJE (engenharia reversa), não um ideal.
   - STACK.md com versões reais e como o projeto roda localmente (banco, .env de exemplo).
   - DECISOES.md com ADR-000 "Estado herdado": riscos e dívidas técnicas encontrados.
   - BACKLOG.md vazio, exceto tarefas de segurança críticas encontradas (marcadas `aguardando_decisao`).
   - Recomenda o perfil de modelos (sistemas com pagamento → `maximo` nas tarefas que tocam pagamento).
3. Se não houver testes, proponha como primeira tarefa testes de caracterização para as áreas críticas
   (pagamento, autenticação), que travam o comportamento atual antes de qualquer refatoração.
4. Resumo em até 15 linhas: o que o sistema faz, pontos de risco e a sugestão de próxima ação
   (`/jarvis evoluir <mudança>` ou `/jarvis corrigir <erro>`).
