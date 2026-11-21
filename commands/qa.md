---
description: Testa o site ou sistema como um usuário real no navegador, encontra bugs, corrige um por um com teste e gera relatório
argument-hint: '<url ou "local"> [foco: login, pagamento, cadastro, celular...] [--so-testar]'
---

Pedido: $ARGUMENTS
(Adaptado do /qa do gstack, licença MIT. Versão enxuta para o Jarvis.)

Carregue a skill `orquestrador`. Use o navegador (ferramentas do MCP `playwright`), NUNCA `browser_run_code_unsafe`.

**Segurança antes de tudo**
- URL de terceiro (site que não é do projeto atual) ou `--so-testar`: apenas teste e relate. Não altere código.
- Nunca faça pagamento real, nunca envie formulário que dispare e-mail, SMS ou cobrança para pessoas reais,
  nunca apague dados. Se o fluxo exigir, use sandbox ou dados de teste; se não houver, registre como portão de decisão.
- Produção com dados de clientes: só leitura e navegação, salvo autorização explícita do usuário.

**1. Plano (máx. 10 linhas)**: liste as jornadas a testar, priorizando o foco pedido e o que dá dinheiro ou dá
suporte (login, cadastro, pagamento/renovação, painel principal, formulários). Inclua celular (390x844).

**2. Exploração**: para cada jornada, navegue como um usuário: caminho feliz, campos vazios e inválidos, voltar e
recarregar, duplo clique em botões, mensagens de erro, estados vazios, links quebrados, console do navegador e
responsividade. Para cada bug, registre: passos para reproduzir, esperado × obtido, print e gravidade
(CRÍTICO, ALTO, MÉDIO, BAIXO).

**3. Triagem**: ordene por gravidade. Itens de design vão como observação para o `designer`.

**4. Correção** (só no projeto atual e sem `--so-testar`), um bug por vez:
reproduza → escreva o teste que falha → `desenvolvedor` (ou `dba`/`designer` conforme o caso) corrige →
rode o teste e refaça o passo no navegador → `revisor` → commit `fix(qa): <bug>`.
Pare e reavalie depois de 3 tentativas sem sucesso no mesmo bug. Mudança em pagamento, permissão ou dados de
produção é portão de decisão do usuário.

**5. Relatório**: crie `qa/RELATORIO-AAAA-MM-DD.md` com o resumo, a tabela de bugs (status: corrigido, pendente,
precisa de decisão), os prints e as jornadas aprovadas. Se a base de conhecimento existir, registre os padrões de
bug encontrados em `aprendizados/`.

Resposta final (máx. 15 linhas): bugs encontrados por gravidade, quantos foram corrigidos, o que ficou pendente
e o caminho do relatório.
