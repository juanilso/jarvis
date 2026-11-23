---
description: Inicia um projeto, discute o escopo, recomenda o perfil de modelos (ou deixa você escolher) e gera os arquivos de orquestração
argument-hint: '<descrição livre do projeto>'
---

Ideia: $ARGUMENTS

Carregue a skill `orquestrador`.
Projeto complexo (vários perfis de usuário, financeiro, regras de negócio, integrações/n8n)? Recomende ao usuário
começar por `/jarvis:planejar` (planejamento com protótipo e testes) e pare aqui, a menos que ele queira seguir.

Etapa 1 — Leitura rápida: se já houver código no repositório, use o `explorador` (haiku)
para detectar a stack (composer.json, *.php, build.gradle, migrations etc.) em até 15 linhas.

Etapa 2 — Discussão: faça de uma vez só, no máximo 7 perguntas, cada uma com um padrão sugerido:
objetivo/usuário, funcionalidades do MVP, fora de escopo, perfil de stack (PHP/cPanel,
Android ou ambos), versão do PHP e banco(s), forma de deploy e criticidade (dados sensíveis/pagamentos?).
Inclua no fim a pergunta sobre os modelos:
"Perfil de modelos recomendado: <perfil> porque <motivo>. Responda ok, ou escolha economico/equilibrado/maximo."

Etapa 2.5 — Desafio das premissas (adaptado do /office-hours do gstack, MIT). Na MESMA mensagem das perguntas,
antes delas, inclua:
- O problema reescrito em 1 frase e 3 premissas para o usuário concordar ou corrigir:
  é o problema certo? o que acontece se não fizer nada? o que já existe (no código, na base de conhecimento ou no
  mercado) que resolve parte disso? como o usuário final vai receber e usar?
- 2 ou 3 abordagens: MÍNIMA (o menor que resolve), IDEAL e uma ALTERNATIVA criativa, cada uma com esforço,
  risco e o que fica de fora. Recomende uma.
Se o usuário discordar de uma premissa, ajuste antes de seguir.

Etapa 3 — Com as respostas, crie `docs/` a partir de `templates/` da skill e delegue ao `arquiteto`
(com o modelo do perfil escolhido) a tarefa de preencher PROJETO, STACK, ORQUESTRACAO, DECISOES (ADRs iniciais),
BACKLOG (tarefas atômicas com tags) e ESTADO.

Etapa 4 — Resumo em até 15 linhas: escopo, perfil de modelos, número de tarefas, as 5 primeiras.
Sugira: `/jarvis toca o projeto`.
