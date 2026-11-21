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
- 👁 Prévia: liga `php -S` do projeto na porta 8081. Publique no Tailscale: `tailscale serve --bg --https=8081 http://localhost:8081`.
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
  avisa você no Telegram e para de responder aquela conversa.
- Quando você responde pelo WhatsApp, o robô se cala naquela conversa por 12 h. `#bot` na conversa (ou `/devolver <número>`)
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
