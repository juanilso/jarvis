---
description: Piloto automático até a homologação. Constrói, testa, corrige e só devolve quando o projeto está pronto para a validação do usuário (decide sozinho o que é reversível)
argument-hint: '<objetivo, ex. "refatorar o site da loja com layout moderno">'
---

Objetivo: $ARGUMENTS

Carregue a skill `orquestrador`. Você está no **modo entrega**: o usuário NÃO quer ser chamado até o projeto estar
pronto para a validação dele. Esta é uma rodada; o piloto do Jarvis chama a próxima até você declarar PRONTO.
Trabalhe o máximo possível nesta rodada.

## 1. Situação (rápido)
- Leia `docs/PILOTO.md` (diário do piloto), `docs/ESTADO.md`, `docs/BACKLOG.md`, `docs/DECISOES-PENDENTES.md` e,
  se houver, o relatório de teste que veio no fim desta mensagem.
- Sem `docs/PROJETO.md`: código existente → fluxo **adotar**; pasta vazia → fluxo **novo**, mas SEM perguntar ao usuário:
  responda você mesmo às perguntas com o padrão recomendado (perfil de modelos do `docs/ORQUESTRACAO.md` ou equilibrado)
  e registre as premissas em `docs/DECISOES.md` como "decidido no piloto, pode mudar na validação".

## 2. Decisões: decida, não pergunte
- Toda decisão reversível (layout, cores, estrutura de páginas, nome de rota, biblioteca, ordem das tarefas) você toma,
  pela opção recomendada, e registra em `docs/DECISOES.md` com a marca **[piloto]**. Decisões pendentes antigas que
  forem reversíveis: decida e feche.
- Falta conteúdo do usuário (textos, fotos, logo, preços, telefone)? Use conteúdo provisório realista (rascunhe com
  `jarvis-ajudante` se estiver configurado, para economizar) e marque com
  `<!-- PROVISÓRIO -->`; liste em `docs/HOMOLOGACAO.md` → "O que você precisa me mandar". Isso NÃO bloqueia.
- Só pare (BLOQUEADO) para o que é irreversível ou que só o usuário tem: senha/credencial/conta de terceiros,
  publicar em produção (deploy, DNS, push), apagar dados reais, pagamento, decisão jurídica. Mesmo assim, termine
  antes tudo o que for possível.

## 3. Construir
- Objetivo envolve site, landing page, tela ou "refatorar/modernizar/deixar bonito": carregue a skill `refatorar-site`
  e siga as etapas dela (home completa e bonita já na primeira rodada; nota visual ≥ 8 em cada item).
- Rode o fluxo **executar** com `tudo` (todas as tarefas prontas), sem limite de 5, nesta mesma rodada.
- Site/tela: o `designer` faz o layout completo (não esqueleto); o site roda na prévia ao vivo (porta 8081).
- Mantenha `.jarvis/jornadas.json` com os caminhos críticos: cada página do menu abre sem estar em branco, links
  principais visíveis, formulários aparecem e enviam (em ambiente local), login se houver.

## 4. Homologação interna (o seu teste, antes do usuário)
Rode e corrija em ciclo até passar (ou até esgotar o que dá para fazer nesta rodada):
1. Testes do projeto (`testador`) passando.
2. Site: nota visual ≥ 8 em todos os itens da skill `refatorar-site`, em desktop e celular.
3. `jarvis-site testar` na pasta do projeto: **0 CRÍTICO, 0 ALTO, nota ≥ 85, todas as jornadas ✅**, sem erros novos em
   `.jarvis/php-erros.log`.
4. `jarvis-site print --paginas <todas as páginas principais>` e OLHE cada PNG com Read (computador e celular):
   nada em branco, nada sobreposto, nada cortado, textos legíveis, menu funcionando no celular. Achou algo feio? Corrija.
5. `revisor` sem CORRIGIR pendente.
Commit local a cada tarefa (nunca push).

## 5. Pronto para validação = TODOS verdadeiros
- Escopo do objetivo implementado (tarefas restantes no backlog só podem ser marcadas "pós-validação").
- Item 4 inteiro passou nesta rodada.
- `docs/HOMOLOGACAO.md` escrito para o usuário (curto, sem jargão):
  o que foi feito · como acessar (prévia ao vivo: `/previa` no Telegram ou 👁 no painel) · **roteiro de validação**
  (checklist passo a passo, 5 a 12 itens, do jeito que um cliente usaria) · decisões que você tomou sozinho [piloto] ·
  o que você precisa me mandar (conteúdo provisório) · limitações conhecidas.

## 6. Fim da rodada
Acrescente em `docs/PILOTO.md` 3 a 6 linhas: rodada, o que avançou, nota do teste, o que falta.
A ÚLTIMA linha da sua resposta deve ser exatamente uma destas:
`PILOTO: PRONTO`  ·  `PILOTO: CONTINUAR — <o que falta, 1 linha>`  ·  `PILOTO: BLOQUEADO — <o que só o usuário pode resolver>`

Se declarar PRONTO, antes dela coloque o roteiro de validação do `docs/HOMOLOGACAO.md` (resumido). Se for CONTINUAR,
a resposta é só para o diário: 3 linhas no máximo. Nunca faça push nem deploy.
