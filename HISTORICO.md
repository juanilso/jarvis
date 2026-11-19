# Histórico e contexto do Jarvis (para continuar em outra conta/conversa)

## Quem sou e o que uso
- Desenvolvo painéis em PHP + MySQL/SQL Server/SQLite, hospedados em cPanel. Próximo projeto: app Android.
- Uso o Claude Code numa **VPS Ubuntu 24.04**, dentro de um **contêiner Docker** (`container/` deste repositório).
- O Claude da VPS usa a **API por um gateway** (`ANTHROPIC_BASE_URL` + chave em `container/.env.claude`, fora do Git).
  Por isso o Remote Control do app do Claude não funciona: o acesso remoto é pelo **bot do Telegram** (`container/telegram-bot/`).

## O que é o Jarvis (este repositório)
Plugin do Claude Code que orquestra um time de agentes com roteamento de modelos:
- arquiteto (Opus), explorador (Haiku), desenvolvedor/dba/android (Sonnet), testador (Haiku),
  revisor (Sonnet), deploy e documentador (Haiku). Perfis: economico, equilibrado (padrão), maximo.
- Fluxo por tarefa: explorar → implementar → testar → revisar → commit local. Push e deploy são sempre meus.
- Decisões que sempre ficam comigo ficam na fila `docs/DECISOES-PENDENTES.md`:
  escopo/stack, dependência nova, migration destrutiva, deploy, permissão Android, custo, segurança/LGPD.
- Estado de cada projeto em `docs/` (PROJETO, STACK, ORQUESTRACAO, BACKLOG, DECISOES, ESTADO).
- Comandos do plugin: `/jarvis:jarvis <pedido>`, `/jarvis:novo`, `/jarvis:adotar`, `/jarvis:executar`,
  `/jarvis:decidir`, `/jarvis:evoluir`, `/jarvis:modelos`, `/jarvis:status`.
  No modo projeto (`projeto/.claude/`, para sessões na nuvem) os comandos ficam sem prefixo: `/jarvis`, `/executar`…

## Ambiente na VPS (como está hoje)
- Repositório em `~/jarvis`; projetos em `~/projetos` (= `/workspace` no contêiner).
- Subir: `cd ~/jarvis/container && docker compose up -d` · Entrar: `docker compose exec dev bash`
- Dentro: `cd /workspace/<projeto> && jarvis-auto` (Claude autônomo, seguro porque está isolado no contêiner).
- Sessão persistente: `tmux attach -t jarvis` (Ctrl+B, D para sair deixando rodando).
- Bancos: MariaDB (`mariadb`, usuário/senha/banco `dev`); SQL Server opcional (`--profile sqlserver`).
- Portas só em 127.0.0.1; acesso pelo PC via túnel `ssh -L 3307:localhost:3307 -L 8080:localhost:8080 root@IP`.
- Telegram: `docker compose --profile telegram up -d`; no bot: `/projetos`, `/projeto <nome>`, `/status`, `/parar`, `/novo`.
- Pendências de segurança da VPS: entrar só por chave SSH, desligar o login por senha, ufw, fail2ban, snapshots.

## Problemas já resolvidos (não repetir)
- PPA do PHP fora do ar → PHP 8.3 vem do Ubuntu; PPA só para outras versões.
- Login do Claude não era salvo → `CLAUDE_CONFIG_DIR` no volume + pastas de propriedade do usuário `dev`.
- Comando `/jarvis` "unknown" → os comandos de plugin usam o prefixo `/jarvis:`.
- Desktop HP sem virtualização (VT-x) → Docker não roda nele; por isso uso a VPS.

## Projeto em andamento: painel `pn.unitvplayer.lat`
Painel administrativo PHP + MySQL: clientes, revendedores, liberação de acesso, quantidade de telas e
integração com gateway de pagamento via API. O Jarvis adotou (ou está adotando) o painel com perfil
**equilibrado** e `[modelo:opus]` nas tarefas de pagamento.

### Demanda principal (evolução)
- Hoje: cliente de outro revendedor que paga pelo MEU link só renova e continua com o revendedor dele.
- Quero: qualquer cliente que pagar pelo MEU link (o do dono do painel) seja transferido para a minha carteira.
  A função é **exclusiva do dono**: links de revendedores mantêm o comportamento atual.
- Tela onde o cliente informa o login antes de pagar, para ser identificado.
- Pontos a decidir: validação no servidor (link/token assinado), tempo de plano restante e comissão do
  revendedor anterior, estorno/chargeback, webhook duplicado (idempotência), histórico de transferências,
  aviso ao revendedor, testes só no sandbox do gateway.

## Como continuar numa nova conversa
Cole no início: "Leia o HISTORICO.md do repositório juanilso/jarvis e continue a partir dele."
(A outra conta precisa ter o GitHub conectado com acesso a este repositório.)
