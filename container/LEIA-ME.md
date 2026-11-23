# Contêiner de desenvolvimento do Jarvis (Windows + Docker Desktop)

O Claude trabalha com liberdade total **dentro do contêiner**. O PC só compartilha a pasta `projetos/`,
então senhas, navegador e arquivos pessoais ficam fora do alcance dele. As outras IAs e o seu editor
trabalham nos mesmos arquivos pela pasta `projetos/` no Windows.

```
C:\dev\
 ├─ jarvis\       ← este repositório (git clone)
 └─ projetos\     ← seus projetos (compartilhado com o contêiner em /workspace)
```

## Instalação (uma vez)
1. Instale o **Docker Desktop** (usa WSL2) e o **Git for Windows**. Reinicie se for pedido.
2. No PowerShell:
   ```powershell
   mkdir C:\dev\projetos
   cd C:\dev
   git clone https://github.com/juanilso/jarvis.git
   cd jarvis\container
   docker compose up -d --build
   docker compose exec dev bash
   ```
   O repositório é privado, então o `git clone` pede login: use o navegador quando aparecer a janela do GitHub.
3. Dentro do contêiner, rode `primeiro-uso`: ele configura o Git, faz o login no Claude, instala o Jarvis e as permissões.

## Dia a dia
```powershell
cd C:\dev\jarvis\container
docker compose up -d          # liga (já liga sozinho com o Docker Desktop)
docker compose exec dev bash  # entra
```
Dentro do contêiner:
- `cd /workspace/meu-projeto && jarvis-auto`: Claude totalmente autônomo
- `/jarvis <ideia>`: começa ou continua o projeto
- Servidor PHP: `php -S 0.0.0.0:8080 -t public` → abra http://localhost:8080 no Windows
- MariaDB: host `mariadb` (de dentro) ou `localhost:3307` (do Windows); usuário, senha e banco são `dev`
- SQL Server (quando precisar): `docker compose --profile sqlserver up -d` → host `sqlserver`, usuário `sa`, senha `Dev@Local123`

## Desempenho em máquina modesta
- Limites já definidos: 4 GB para o dev, 1 GB para o MariaDB e 2 GB para o SQL Server (que só sobe quando você pedir).
- Docker Desktop → Settings → Resources: limite o WSL a uns 6 GB se o PC tiver 8 GB.
- Pasta no disco do Windows é mais lenta. Se incomodar, mova `projetos` para dentro do WSL
  (`\\wsl$\Ubuntu\home\...`): continua acessível pelo Explorer e pelas outras IAs.

## Segurança
- Nunca coloque credenciais de produção, cPanel ou FTP dentro de `projetos/`.
- As senhas acima são só para o ambiente local; não use em produção.
- `git push` continua bloqueado para o Claude: você revisa e envia.

## Telegram (controle pelo celular, funciona com API key ou gateway)
1. No Telegram, fale com @BotFather → /newbot → copie o token.
2. No `.env.claude` da VPS: `TELEGRAM_BOT_TOKEN=...` (deixe `TELEGRAM_CHAT_ID` vazio por enquanto).
3. `docker compose build && docker compose --profile telegram up -d`
4. Mande "oi" para o bot: ele responde com o seu chat ID. Coloque em `TELEGRAM_CHAT_ID=` e rode
   `docker compose --profile telegram up -d` de novo.
5. No bot: `/projetos` → `/projeto nome` → depois é só escrever as demandas.
Imagens e arquivos: mande foto (ou álbum) ou documento com a pergunta na legenda; ficam em /workspace/.jarvis-anexos.
Áudio: mande mensagem de voz (transcrição local). `/audio auto|sempre|nunca` controla a resposta falada.
`/agentes on|off` liga/desliga os avisos de cada agente trabalhando.
Logs: `docker logs -f jarvis-telegram`. Só os chat IDs autorizados conseguem usar o bot.

## Acesso web (VS Code no navegador)
1. No `.env.claude`: `PASSWORD=<senha forte>`.
2. `docker compose build && docker compose --profile web up -d`
3. Acesso privado com Tailscale (na VPS, como root):
   `curl -fsSL https://tailscale.com/install.sh | sh` → `tailscale up` (abra o link e entre com sua conta)
   → `tailscale serve --bg 8443` (mostra o endereço https://...ts.net)
4. Instale o app Tailscale no PC/celular com a mesma conta e abra o endereço. Terminal: menu ☰ → Terminal → New Terminal → `jarvis-auto`.
Sem Tailscale: `ssh -L 8443:localhost:8443 root@IP` e abra http://localhost:8443.

## Página web do Jarvis (microfone e respostas faladas)
Sobe junto com o acesso web: `docker compose --profile web up -d` (usa a mesma `PASSWORD`).
Publique no Tailscale numa segunda porta: `tailscale serve --bg --https=8090 http://localhost:8090`
→ abra `https://<sua-vps>.ts.net:8090`. Microfone: clique para gravar e clique de novo para enviar.
Sem Tailscale: `ssh -L 8090:localhost:8090 root@IP` → http://localhost:8090.

## Projetos e GitHub no painel (botão 📁)
- Novo projeto, upload de arquivos/.zip, clonar repositórios, status, criar repositório, salvar e enviar (commit + push) e atualizar (pull).
- Requer `GH_TOKEN` no `.env.claude` (token do GitHub). Se aparecer erro de permissão ao criar pastas:
  `docker compose exec -u root dev chown -R dev:dev /workspace`

## Base de conhecimento, pesquisa e prévia de sites
- 🧠 no painel (ou /ideia, /lembrar, /pesquisar, /sincronizar no chat e no Telegram). Por voz no Telegram: "ideia: …".
- As notas ficam em /workspace/.jarvis-conhecimento e no repositório privado `jarvis-conhecimento` do seu GitHub
  (criado automaticamente com o GH_TOKEN). Abra a pasta como "vault" no Obsidian para navegar pelas notas.
- Busca: o Claude usa WebSearch; sem ele, `jarvis-busca` (Brave com BRAVE_API_KEY, ou DuckDuckGo sem chave).
- 👁 Prévia: o site do projeto atual na porta 8081 (sempre ligada desde a 1.18). Publique uma vez: `sudo ./previa-configurar.sh`.
- Depois de atualizar, renove o plugin no contêiner dev:
  `claude plugin marketplace update jarvis-marketplace && claude plugin uninstall jarvis@jarvis-marketplace && claude plugin install jarvis@jarvis-marketplace`

## Design, Canva, navegador e biblioteca de skills
- `jarvis-extras` (no contêiner dev): instala frontend-design e canva do marketplace oficial e atualiza o Jarvis.
- `/jarvis:redesenhar <url> [o que mudar]`: analisa o site e cria 3 variantes em `redesign/` (veja pelo 👁 Prévia).
- `/jarvis:skill <link>`: verifica uma skill/plugin/MCP com a skill-scanner (Sentry) antes de instalar.
- Biblioteca de itens aprovados: `biblioteca/BIBLIOTECA.md`.
- Canva: dentro do Claude, `/mcp` → canva → Authenticate (ver instruções no final do `jarvis-extras`).

## Voltar a uma versão anterior do Jarvis (se algo der errado)
A branch `versao-1.3.0` guarda o Jarvis antes das adaptações do gstack. Para voltar, dentro do contêiner dev:
`claude plugin marketplace remove jarvis-marketplace && claude plugin marketplace add juanilso/jarvis#versao-1.3.0 && claude plugin install jarvis@jarvis-marketplace`
Antes de publicar mudanças, rode `python3 scripts/validar.py` (verifica os arquivos do Jarvis).

## Jarvis 1.5: histórico por projeto, atividade ao vivo, agentes ativos, mapa e guia
- Cada projeto tem o seu histórico no painel (salvo em ~/.claude/historico-web/). Trocar de projeto troca a conversa.
- Ao lado do holograma: cronômetro e os últimos passos (que arquivo está sendo lido, que agente trabalha).
  No Telegram, uma única mensagem de progresso é atualizada a cada poucos segundos.
- Modo ativo: no painel, no Telegram e no terminal, toda demanda passa pelo time (explorador, executor da área,
  testador, revisor; arquiteto em decisões; designer em telas; documentador no fim do ciclo).
- 🗺 Mapa do sistema (Floorplan) com /jarvis:mapa · ❔ Guia de uso no painel ou /guia.
- unslop (tirar a cara de IA de telas) e Floorplan são instalados pelo `jarvis-extras`.
- Restauração: branches `versao-1.3.0` e `versao-1.4.0` no GitHub.

## Jarvis 1.22.6: NVIDIA e Cloudflare no lugar de Mistral e Grok

- A Mistral encerrou o plano grátis da API e o Grok exige crédito. Entram:
  - **NVIDIA** (build.nvidia.com → Get API Key, chave `nvapi-…`): grátis para desenvolvedor, 40 pedidos/minuto,
    muitos modelos (Llama 70B, gpt-oss-120b, Qwen…).
  - **Cloudflare Workers AI** (dash.cloudflare.com → Workers AI → Use REST API: Account ID + token): 10.000
    neurons/dia grátis (dezenas de pedidos); a Cloudflare não treina com o conteúdo.
- Ordem padrão: gemini, groq, nvidia, cloudflare, openrouter. O script oferece remover as chaves de Mistral/Grok.

## Jarvis 1.22.5: Mistral no lugar do Grok

- O Grok exige crédito na conta da xAI; no lugar dele entra a **Mistral** (plano grátis Experiment, sem cartão,
  só telefone verificado; a Mistral pode usar o conteúdo para treinar). Chave em https://console.mistral.ai/api-keys.
- Ordem padrão: gemini, groq, mistral, openrouter. O `./ajudantes-configurar.sh` pergunta a chave da Mistral e
  oferece remover a do Grok. O Grok continua suportado se um dia você colocar crédito (`XAI_API_KEY`).
- `jarvis-ajudante --liberar [ia]` tira pausas; pedir uma IA pelo nome tenta mesmo pausada; o comando não trava
  mais quando chamado sem material.

## Jarvis 1.22: planejar antes de desenvolver (com laboratório no n8n)

- **`/planejar <ideia>`** no Telegram (ou `/jarvis:planejar` no Claude Code), skill `planejar-projeto`:
  1. **Descoberta:** uma mensagem com o problema reescrito, 2–3 abordagens e até 10 perguntas com respostas sugeridas.
  2. **Plano** em `docs/plano/`: VISAO, FLUXOS (diagramas), DOMINIO (dados, estados e regras R1, R2…), INTEGRACOES
     (o que fica no sistema x no n8n), ARQUITETURA (com LGPD), RISCOS (hipóteses a testar) e ROADMAP (M0, M1…).
  3. **Laboratório:** protótipo navegável com dados falsos em `prototipo/` (você clica pela prévia ao vivo) e
     experimentos em `laboratorio/` para cada risco, com o resultado em `docs/plano/EXPERIMENTOS.md`.
  4. **Aprovação:** resumo + link do protótipo; nada de desenvolvimento antes do seu "aprovado".
  5. **Backlog** a partir do plano (cada regra vira teste) e sugestão de `/piloto` para o M1.
- **Referência de rede credenciada** embutida: perfis, processos (credenciamento, elegibilidade com token, guias,
  repasse), entidades, regras para perguntar, papel do n8n, riscos e LGPD (dados de saúde são sensíveis).
- **Laboratório no n8n (`jarvis-n8n`):** o Jarvis cria fluxos "[LAB] …" desativados (webhooks "lab-…"), ativa, chama
  com dados falsos e lê o resultado das execuções. Fluxos de produção (como o atendimento do WhatsApp) ele só lê:
  não altera, não ativa e não dispara. Configure: crie a chave no n8n (Settings → n8n API) e rode `./n8n-api-configurar.sh`.

## Jarvis 1.21: ajudantes (outras IAs como mão de obra)

- **Gemini, Grok, OpenRouter e Groq** trabalham para o Jarvis em tarefas de TEXTO: rascunhos e conteúdo provisório
  do site, traduções, title/description, alt de imagens, resumos, ideias, segunda opinião. O Claude continua o chefe:
  decide, programa, revisa e responde por tudo. Os ajudantes não leem arquivos nem mexem no projeto.
- Configure: `./ajudantes-configurar.sh` (pede as chaves escondidas, grava em `.env.ajudantes` com permissão 600,
  recria os contêineres e testa cada uma). Chaves grátis: aistudio.google.com/apikey, console.x.ai,
  openrouter.ai/keys, console.groq.com/keys.
- **Proteção de dados:** antes de enviar, o Jarvis apaga e-mails, telefones, CPF/CNPJ, tokens, chaves, senhas e links
  com token; recusa arquivos `.env`, segredos, bancos e chaves privadas. Mesmo assim, **planos gratuitos costumam usar o
  conteúdo para treinar**: os ajudantes são para conteúdo público do site, não para dados de clientes.
- **Cota e troca automática:** cota diária por ajudante (`JARVIS_AJUDANTE_GEMINI_DIA=200`…); se um responder "sem cota"
  ou "sem crédito", o Jarvis pausa esse e passa para o próximo da lista. O modelo é escolhido sozinho pela lista do
  provedor (troca quando um sai de linha) ou fixado em `JARVIS_AJUDANTE_<NOME>_MODELO`.
- Telegram/painel: `/ajudantes` (situação, cota, dados apagados) e `/ajudante <tarefa>` ou `/ajudante grok <tarefa>`.
- Terminal e agentes: `jarvis-ajudante "tarefa" < arquivo` · `jarvis-ajudante --status`.

## Jarvis 1.20: refatorar sites com qualidade de agência

- **Skill `frontend-design` (oficial da Anthropic) agora vem junto:** o designer pedia essa skill "se disponível", mas
  ela só existia se você tivesse rodado `jarvis-extras`. Sem ela, ele desenhava sem direção visual.
- **Skill nova `refatorar-site`:** inventário rápido (nunca perder conteúdo) → direção visual e sistema de design
  (`docs/site/DESIGN.md`, `css/tokens.css`, componentes) → **home completa e bonita primeiro, com prints** → página
  por página → acabamento. Cada tela recebe nota visual (hierarquia, espaçamento, tipografia, cor, acabamento,
  conteúdo, celular, identidade) e só passa com 8 ou mais em cada item.
- **O teste agora pega os defeitos de "site sem vida":** HTML aparecendo como texto (`<p>`, `&copy;`), link com a cor
  padrão do navegador, fonte padrão (Times), seção com título e sem conteúdo, elemento colado na borda. Todos
  contam como ALTO, então o `/piloto` não aceita "pronto" com eles.
- Corrigido: `jarvis-site` com caminho relativo (`redesign/variante-a`) não subia o servidor.
- Pedido ideal: `/piloto refatorar o site <assunto e público>, manter <logo/cores>, páginas <lista>, referências <sites>`.

## Jarvis 1.19: piloto automático até a homologação

- **`/piloto <objetivo>`** (Telegram ou chat do painel): o Jarvis segue sozinho, em rodadas, construindo, testando,
  corrigindo e homologando. Decisões reversíveis (layout, cores, páginas, bibliotecas) ele toma e anota com [piloto]
  em `docs/DECISOES.md`; conteúdo que falta vira provisório marcado. Você recebe **1 linha por rodada** e só é chamado:
  - ✅ **pronto para a sua validação**: com prints, link da prévia e o roteiro de validação (`docs/HOMOLOGACAO.md`);
  - ⛔ **bloqueado**: só se precisar de algo seu (senha, publicar, pagamento, apagar dados reais);
  - ⏸ limite de rodadas (8), de custo (US$ 15) ou sem avanço (mesmo problema 3 vezes).
- **"Pronto" é conferido pelo Jarvis, não só pela IA:** o site precisa passar no teste (0 crítico, 0 alto, nota ≥ 85
  e todas as jornadas ok). Se a IA disser pronto e o teste reprovar, ela recebe o relatório e corrige na rodada seguinte.
- `/piloto` mostra o andamento · `/piloto parar` · `/piloto continuar` · depois de validar: `/piloto <ajustes>`.
- Limites no `.env.claude`: `JARVIS_PILOTO_RODADAS=8`, `JARVIS_PILOTO_CUSTO=15`, `JARVIS_PILOTO_NOTA=85`.
- No Claude Code direto: `/jarvis:entregar <objetivo>` faz uma rodada longa com as mesmas regras.

## Jarvis 1.18: site rodando no servidor (sem upload), jornadas de teste e teste diário no n8n

- **Prévia ao vivo, sempre ligada:** o site do projeto atual roda no servidor (PHP + banco de desenvolvimento) na porta 8081.
  Cada mudança do Jarvis aparece ao recarregar a página, sem upload. Publique a porta uma vez: `sudo ./previa-configurar.sh`
  (Tailscale, só para os seus aparelhos). Depois: `/previa` no Telegram, 👁 ou 🖼 → 🌐 Navegar no painel.
- **Igual ao cPanel:** `/contato` abre `contato.php`; Laravel/WordPress/CodeIgniter (tudo para `index.php`) funcionam;
  endereço inexistente dá 404 de verdade; erros do PHP aparecem na tela e ficam em `.jarvis/php-erros.log`.
- **Teste mais esperto:** acusa PÁGINA EM BRANCO, erro do PHP na tela ou no log, código PHP aparecendo como texto e `{{ }}` cru.
- **Jornadas** (`.jarvis/jornadas.json`, vai para o Git): o Jarvis grava os caminhos que não podem quebrar (menu → contato →
  enviar → "Obrigado") e o `/testar` repete todos, com print de onde falhou. Passos: abrir, ver, nao_ver, ver_link,
  ver_elemento, clicar, preencher, url_contem, esperar, print.
- **n8n:** fluxo "Jarvis · Teste dos sites" (7h, e um webhook `jarvis-testar-site` para chamar depois de publicar).
  Só avisa no Telegram se algo quebrar. Gatilho novo: `{"acao":"site_testar","projeto":"loja","url":"…"}` e `{"acao":"previa"}`.
  Importe SÓ o fluxo novo (reimportar todos desligaria os que você já ativou, como o do WhatsApp):
  `docker compose --profile automacoes exec -T -u node n8n n8n import:workflow --input=/opt/jarvis-n8n/fluxos/jarvisRotina0009.json`
- No site publicado, as jornadas que clicam ou preenchem só rodam se tiverem `"producao": true` (para não enviar formulário real).

## Jarvis 1.17: prévia (prints) e teste automático dos sites

- **O Jarvis enxerga o site:** sempre que cria ou altera um site, ele roda `jarvis-site testar`, corrige o que quebrou,
  tira prints (computador 1440 e celular 390), **olha as imagens** e só então responde. Os prints chegam junto com a
  resposta, no painel e no Telegram.
- **🖼 no painel:** 📸 Tirar prints (páginas opcionais, ex.: `/ /contato.html`), 🧪 Testar o site (pasta do projeto ou
  um endereço publicado) e 🛠 Jarvis, corrija. Mostra os últimos prints e o último relatório com nota de 0 a 100.
- **Telegram:** `/print`, `/print /contato.html`, `/testar`, `/testar https://seusite.com.br`, `/testar corrigir`.
- **O que o teste confere** (até 15 páginas do mesmo site): página fora do ar, links quebrados, erros de JavaScript,
  CSS/JS/imagens/fontes que não carregam, imagens quebradas, rolagem lateral e letra miúda no celular, meta viewport,
  título, description, lang, h1, campos sem rótulo, botões sem texto, páginas lentas ou pesadas.
- Não precisa ligar o 👁: o teste sobe um servidor temporário só para ele. Ele só navega (não clica em botões, não envia
  formulários). Os arquivos ficam em `<projeto>/.jarvis/previas/` (as 10 últimas; fora do Git).
- Para fluxos com clique e formulário (login, compra), continue usando `/jarvis:qa`, que agora começa por esse teste.
- Atualizar: `git pull` e `docker compose build && docker compose --profile web --profile telegram up -d --force-recreate jarvisweb telegram`.

## Jarvis 1.16: jogos do dia (futebol brasileiro)

- **⚽ no painel:** gera a agenda do dia (Série A, B, C, Copa do Brasil e estaduais), pesquisa **onde passa** cada jogo
  e monta uma **imagem 1080×1920** (formato de Status; divide em várias se tiver muitos jogos) e o **texto pronto** para grupos,
  com botões para copiar e mandar no Telegram. Configure campeonatos, nome da marca e rodapé.
- **Telegram:** `/jogos` manda a imagem e o texto. **n8n:** rotina "Jarvis · Jogos do dia" (todo dia às 8h).
- **WhatsApp:** o robô responde "que jogos tem hoje?" com a lista (📱 → Recursos → ⚽).
- **Fontes:** agenda da API pública da ESPN (sem chave; não oficial, pode mudar sem aviso). Canais: pesquisa na internet em
  sites de notícia — quando não acha, aparece "a confirmar". Confira os jogos mais importantes antes de divulgar.

**Aplicar:** `git pull && docker compose build && docker compose --profile web --profile telegram up -d --force-recreate jarvisweb telegram`.
Para a rotina diária: `./automacoes-configurar.sh` importa "Jarvis · Jogos do dia" (depois ative no n8n).

## Jarvis 1.15: mensagens editáveis, liga/desliga e proteção do número

No **📱** há três seções novas:
- **Recursos (liga/desliga):** pagamentos automáticos, teste grátis e consulta de vencimento, cada um separado.
  O robô inteiro continua no botão **⏸ Pausar robô**. Com os pagamentos desligados, você só recebe o aviso no Telegram.
- **Mensagens automáticas:** edite cada mensagem com `{nome}` `{login}` `{valor}` `{vencimento}` `{falta}`. Escreva várias
  versões separadas por `||` e o robô sorteia uma. "↺ voltar ao padrão" restaura o texto original.
- **Proteção do número:** marca como visto e mostra "digitando…", pausa de 2 a 6 s (+ tempo de digitar), no máximo
  12 respostas por minuto; mensagens que o robô **inicia** (pagamentos) saem por uma **fila** com 45 s de intervalo,
  no máximo 30 por hora, e ficam guardadas no **horário de silêncio** (22h–8h) até o fim dele. A fila sobrevive a reinícios.

**Boas práticas para não ter o número bloqueado** (o que o sistema não controla sozinho):
- Use um número "aquecido" (com conversas normais há semanas), com foto e nome de empresa no perfil.
- Não mande mensagens para quem nunca falou com você nem em massa. Pagamentos são exceção natural (o cliente acabou de pagar).
- Evite links na primeira mensagem que o robô inicia; prefira mandar o link depois que o cliente responder.
- Peça aos clientes para salvarem o número: contatos salvos e respostas rápidas melhoram a reputação.
- Se o número receber denúncias/bloqueios, pause o robô e aumente intervalos.

**Aplicar:** `git pull && docker compose build && docker compose --profile web up -d jarvisweb` (Ctrl+F5 no painel).

## Jarvis 1.14: API do painel no 📱, robô volta após 30 min e leitor do @DastDePixPartnerBot

- **📱 → Painel (API) e regras:** endereço do `api.php`, token (fica guardado num volume só do painel; a tela nunca mostra),
  ação de renovar (quando você publicar a `renew_client`, é só preencher), tabela valor=meses, horas e limite de testes,
  e **minutos sem você para o robô voltar**. O botão 🔌 **Testar conexão** confere endereço e token sem criar nada.
- **Você assume, o robô volta sozinho:** quando você responde o cliente pelo WhatsApp, o robô se cala naquela conversa;
  cada resposta sua reinicia a contagem; depois de 30 min (configurável) sem mensagem sua, ele volta a atender.
  As suas mensagens entram no histórico como da empresa, então ele continua de onde você parou.
- **Pagamentos do @DastDePixPartnerBot:** o Telegram não deixa um bot ler a sua conversa com outro bot. Por isso há
  um **leitor opcional** que entra na sua conta como "dispositivo conectado" e lê **só** essa conversa (não envia nada,
  não lê outras conversas). Ao ligar, recupera os pagamentos das últimas 24 h; cada pagamento é processado uma vez.

**Aplicar (na VPS):**
```bash
cd ~/jarvis/container && git pull
docker compose build && docker compose --profile web --profile telegram up -d
./pagamentos-configurar.sh     # api_id/api_hash do my.telegram.org + código de login no app do Telegram
```
Depois: painel → 📱 → **Painel (API) e regras** → preencha, **Salvar** e **Testar conexão**.
Desligar o leitor: `docker compose --profile pagamentos stop leitor`. Desconectar a conta: Telegram → Configurações →
Dispositivos → encerrar "Jarvis leitor".

## Jarvis 1.13: pagamentos FastFlow e autoatendimento com a API do painel

**O que faz**
- **Pagamento no Telegram** ("PAGAMENTO FASTFLOW RECEBIDO"): o Jarvis lê, confere o login no painel e manda WhatsApp ao cliente:
  - "Nome informado" é um login válido e o FastFlow já renovou → só confirma ("ativo até …");
  - login válido mas não renovado → renova pela API (se `PAINEL_ACAO_RENOVAR` existir) ou avisa você para renovar;
  - sem login (ou era um nome) → pede o login no WhatsApp; quando o cliente responde, confere e conclui.
  - Cada pagamento (#id) é processado uma única vez. Você recebe um resumo no Telegram.
- **WhatsApp (autoatendimento):** "quando vence?" → consulta e responde; "quero teste" → cria teste
  (1 por telefone a cada 30 dias, até `PAINEL_TESTES_DIA`=20 por dia); cancelar/alterar → chama você.
- **n8n:** ações `pagamento`, `painel_consultar`, `painel_teste` no gatilho (exemplo: "Jarvis · Funções do painel").

**Segurança:** quem chama a API é código com regras fixas, não a IA. A consulta mostra ao cliente só status e vencimento
(nunca senha ou links). Renovação só a partir de um pagamento confirmado. O token fica só no `.env.atendimento`.

**Ligar (na VPS):**
```bash
cd ~/jarvis/container && git pull
docker compose build && docker compose --profile web --profile telegram up -d
./painel-configurar.sh      # pede o token (sem mostrar), a tabela valor=meses e o grupo/canal dos pagamentos
```
**Onde chegam os pagamentos:** grupo (adicione o bot do Jarvis; no @BotFather `/setprivacy` → Disable) ou canal (bot como
admin). Se chegam numa conversa privada com o bot do FastFlow, encaminhe as mensagens para o bot do Jarvis.

**⚠️ API do painel:** chamar `api.php` sem token/ação cria uma conta de teste. Corrija para exigir token e `action`,
e limite testes por telefone/IP. Para renovar pela API, crie uma action (ex.: `renew_client`) com token, `username`,
`months` e `reference` (para não renovar 2 vezes o mesmo pagamento) e informe o nome no `./painel-configurar.sh`.

## Jarvis 1.11: atendimento automático no WhatsApp (WhatsApp Web)

O número da empresa fica conectado pelo **WhatsApp Web** (WAHA Core, código aberto), sem a API da Meta.
Cada mensagem passa pelo n8n e o Jarvis responde em segundos com base na **base de respostas** que você escreve (📱 no painel).

**Ligar (na VPS):**
```bash
cd ~/jarvis/container && git pull
docker compose build && docker compose --profile web --profile telegram up -d
./whatsapp-configurar.sh        # precisa do n8n ligado (./automacoes-configurar.sh)
```
Depois: painel → 📱 → **Conectar** → leia o QR code com o WhatsApp da empresa (Dispositivos conectados) →
preencha a **Base de respostas** → no n8n, ative "Jarvis · Atendimento WhatsApp".

**Como ele se comporta**
- Responde só com o que está na base; se não souber, se o cliente pedir um atendente ou for reclamação/reembolso,
  avisa você no Telegram (1 vez a cada 2 h por conversa) e **continua conversando** com o cliente.
- Só quando você responde pelo WhatsApp o robô se cala naquela conversa (por 12 h).
- Modelo: tenta o rápido (haiku) e, se o gateway não tiver, usa o próximo (sonnet). Veja os nomes com `/modelos`. `#bot` na conversa (ou `/devolver <número>`)
  devolve ao robô. `/assumir <número>` faz o contrário. `/atendimento off` pausa tudo.
- Ignora grupos, status e canais; não lê áudio/imagem (pede texto); limita mensagens em sequência.
- **Segurança:** o modelo do atendimento não tem nenhuma ferramenta (não roda comandos, não lê projetos, não mexe no painel).
  A chave do WhatsApp fica só no serviço do painel (`.env.atendimento`).
- **Privacidade:** guarda só as últimas mensagens de cada conversa, por até 24 h.
- **Modelo:** usa o `ANTHROPIC_DEFAULT_HAIKU_MODEL` (rápido e barato); troque com `ATENDIMENTO_MODELO=` no `.env.claude`.

**Risco:** não é a API oficial. Use um número só da empresa, só para responder clientes (nada de mensagens em massa
ou para quem não falou com você), porque o WhatsApp pode bloquear números com automação.

## Jarvis 1.10: tendências dos últimos 30 dias (last30days)

`/tendencias <tema>` (painel, Telegram ou rotina do n8n) mostra o que as pessoas estão falando nos últimos 30 dias no Reddit,
Hacker News, GitHub e Polymarket, ordenado por engajamento, e salva um resumo em português na base (📈 tendências).
Os agentes também usam (`jarvis-tendencias`) quando uma decisão depende do mercado.

**Segurança:** o motor da skill last30days (MIT) fica fixado num commit verificado e roda num ambiente limpo: nenhuma chave
(nem a do gateway, nem o GH_TOKEN), sem cookies do navegador, sem publicar e sem instalar extras. Só 5 fontes permitidas.
Opcional: `TENDENCIAS_GITHUB_TOKEN=` (token do GitHub **só leitura**) no `.env.claude` para mais resultados do GitHub.

**Aplicar:** `git pull && docker compose build && docker compose --profile web --profile telegram up -d` (Ctrl+F5 no painel).
Rotina de exemplo nova: `./automacoes-configurar.sh` de novo importa "Jarvis · Tendências da semana".

## Jarvis 1.9: escritório virtual, rotinas (n8n) e Hermes em português

**Hermes em português.** Ele recebe uma personalidade em português (`container/hermes/SOUL.md`), o pedido sempre lembra o idioma
e, se mesmo assim a resposta vier em inglês, o Jarvis pede a tradução antes de mostrar e falar. Ele também ganhou uma pasta onde
pode gravar arquivos (zip de projeto, relatórios): `/workspace/.hermes-saida`.

**Escritório virtual (🏢 no painel).** Uma sala por agente (acende quando trabalha, com o que está fazendo e há quanto tempo),
a sala de comando do Jarvis, a consultoria do Hermes, a sala de automação e o quadro de rotinas com os resultados.

**Rotinas com n8n.** O n8n roda num contêiner separado e chama o Jarvis/Hermes por um gatilho protegido por token
(`/api/gatilho`). Em rotina, o Jarvis roda sem as ferramentas de edição e com commit, push, deploy, banco e envio de arquivos
bloqueados: só analisa, testa e manda relatório (painel e Telegram).

**Aplicar (na VPS):**
```bash
cd ~/jarvis/container && git pull
docker compose build
docker compose --profile web --profile telegram up -d
./hermes-configurar.sh --portugues      # só atualiza a personalidade do Hermes (mantém o modelo)
./automacoes-configurar.sh              # liga o n8n, cria o token e importa 4 rotinas de exemplo (desativadas)
sudo tailscale serve --bg --https=5678 http://127.0.0.1:5678
```
Abra `https://<sua-vps>.ts.net:5678`, crie o usuário do n8n, revise as rotinas "Jarvis · …" e ative as que quiser.
Ctrl+F5 no painel e clique em 🏢.

**Rotinas de exemplo:** pesquisa semanal (Hermes, segunda 8h) · check-up diário do projeto (Jarvis, 7h30) ·
revisão de segurança (Hermes, sexta 18h) · alerta de erro por webhook (Jarvis analisa o log e avisa no Telegram).

**Criar outra rotina:** duplique um exemplo no n8n e troque o JSON do nó HTTP: `acao` = `hermes`, `jarvis`, `pesquisar`,
`ideia` ou `avisar`; `texto` = o pedido; `projeto` = pasta (vazio = projeto atual); `avisar: true` manda no Telegram.

**Desligar:** `docker compose --profile automacoes stop n8n` (o resto continua igual).

## Jarvis 1.8: voz do Hermes e cérebro com linhas de pensamento

- **Voz do Hermes:** as respostas do `/hermes` vêm faladas com outro timbre (painel e Telegram). Troque em `HERMES_VOICE`
  e `HERMES_VOICE_TOM` no `.env.claude`. Com 🔊 em "nunca", ele não fala.
- **Cérebro novo:** linhas de pensamento viajam entre as regiões do cérebro; cada agente acende a sua região e o nome aparece ao lado.
- **Para aplicar** (as imagens e a página ficam dentro da imagem do docker, por isso o `build` é necessário):
  `git pull && docker compose build && docker compose --profile web --profile telegram up -d` e Ctrl+F5 no painel.

## Jarvis 1.7.1: correção do Hermes + holograma novo

- **Erro "Anthropic rejected your API key / invalid x-api-key":** o Hermes ia direto para a Anthropic em vez do seu gateway.
  Agora o script entrega o endereço do gateway ao Hermes (arquivo `.env.hermes`, só com o necessário) e, se ainda falhar,
  tenta sozinho o formato OpenAI do gateway. Basta rodar de novo: `git pull && docker compose build && ./hermes-configurar.sh`
- **Modelo da Nous (opcional):** `./hermes-configurar.sh --nous` (conta no Nous Portal; traz navegador, busca, voz e imagens).
- **Teste real:** em tarefas com tela, o Hermes usa a prévia como um cliente e relata bugs.
- **Painel:** holograma novo (cérebro e rosto) e um holograma dourado que aparece enquanto o Hermes trabalha. Ctrl+F5 no painel.

## Jarvis 1.7: Hermes Agent como ajudante

O Hermes Agent (Nous Research, MIT) roda num contêiner separado e o Jarvis pede ajuda a ele.

**Ligar (uma vez), na VPS:**
```bash
cd ~/jarvis/container && git pull
docker compose build
./hermes-configurar.sh
```
O script baixa a imagem oficial, configura o Hermes com o MESMO gateway do `.env.claude` (chave e `ANTHROPIC_BASE_URL`),
cria a `HERMES_API_KEY`, reinicia o painel e o Telegram e testa a conexão. Outro modelo: `./hermes-configurar.sh <ID>`
(ou `HERMES_MODELO=` no `.env.claude`).

**Usar:** `/hermes <pedido>` no painel ou no Telegram. Os agentes também podem chamar `jarvis-hermes`.

**Segurança:** sem porta publicada (só a rede interna do docker), `/workspace` montado só para leitura, sem GH_TOKEN,
sem Telegram próprio. As respostas dele são tratadas como informação, nunca como ordem.

**Se não funcionar:**
- `docker compose --profile hermes logs --tail 80 hermes`
- Modelo não aceito: `docker compose --profile hermes exec -it hermes hermes model` e escolha Anthropic ou "Custom endpoint"
  com a URL do gateway.
- Desligar: `docker compose --profile hermes stop hermes` (o resto do Jarvis continua igual).

## Jarvis 1.6.2: modelos do seu gateway

- `/modelos` (ou 🛰️ no guia ❔ do painel) pergunta ao gateway (`ANTHROPIC_BASE_URL`) quais modelos ele oferece, agora.
- `/modelo <ID>` aceita qualquer ID do gateway (ex.: `anthropic/claude-opus-5-5`) e avisa se o ID não está na lista.
- Para os agentes usarem outros modelos: `ANTHROPIC_DEFAULT_OPUS_MODEL`, `..._SONNET_MODEL` e `..._HAIKU_MODEL` no `.env.claude`, depois `docker compose --profile web --profile telegram up -d`.
- Se o gateway não tiver a lista, a mensagem diz o motivo (ex.: chave recusada) e o resto continua igual.

## Jarvis 1.6: vários projetos ao mesmo tempo
- Cada projeto tem a sua própria execução: dá para mandar uma demanda no A, trocar para o B e mandar outra.
- Limite padrão de 2 projetos simultâneos (`JARVIS_MAX_PARALELO` no `.env.claude`). Cada um consome memória e tokens.
- Painel: projetos trabalhando aparecem com ⏳; Telegram: mensagens marcadas com [projeto]; /status lista todos.
- Restauração: branch `versao-1.5.0`.
