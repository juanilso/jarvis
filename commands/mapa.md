---
description: Gera ou atualiza o mapa interativo do sistema (Floorplan) com check-up de segurança, em docs/mapa.html
argument-hint: '[foco opcional: pagamento, login, revendedores...]'
---

Foco: $ARGUMENTS

Carregue a skill `orquestrador`. Se a skill `floorplan` não estiver instalada, diga ao usuário para rodar
`jarvis-extras` no contêiner e pare.

1. Rode a skill `floorplan` neste projeto em modo sem interação (`export FLOORPLAN_UNATTENDED=1`). Ela cria a pasta
   `floorplan/` no projeto; garanta que `floorplan/.cache/` esteja no `.gitignore`.
2. Exporte o mapa num único HTML, com o check-up incluído:
   `node floorplan/serve.mjs --export docs/mapa.html --include flows,notes,recent,health`
   (não abra servidor nem navegador; o painel mostra o arquivo pelo botão 🗺).
3. Leia o resultado do check-up (Health). Para cada problema real (chave no código, endpoint sem proteção,
   webhook que aceita chamada falsa, banco aberto), crie uma tarefa no `docs/BACKLOG.md` com a tag adequada.
   Segredos expostos e webhook de pagamento sem validação são portões de segurança: registre em
   `docs/DECISOES-PENDENTES.md`.
4. Se a base de conhecimento existir, atualize `projetos/<projeto>.md` com um resumo do mapa (partes principais e
   integrações externas).

Resposta final (máx. 12 linhas): partes principais do sistema, integrações externas, problemas do check-up por
gravidade e "Abra o mapa pelo botão 🗺 no painel".
