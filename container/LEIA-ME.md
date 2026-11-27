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

## Jarvis 1.55.1: VPS com pouca memória

- `telegram` e `jarvisweb` aceitam limite de memória no `.env` (`JARVIS_MEM_TELEGRAM`, `JARVIS_MEM_WEB`).
  Com limite menor que a memória da VPS, um vídeo grande demais é encerrado sozinho em vez de travar o servidor inteiro.
- VPS de 4 GB sem swap: crie 4 GB de swap e use `JARVIS_MEM_WEB=1500m`, `JARVIS_MEM_TELEGRAM=1200m`, `JARVIS_CPUS_VIDEO=2`.

## Jarvis 1.55: escritório com bonequinhos + vídeo não trava mais a VPS

**🏢 Escritório** (botão no painel ou `/escritorio`): planta em pixel art onde cada agente é um funcionário na mesa.
- Quem está trabalhando digita, a tela acende e aparece o balão; quem está livre às vezes vai tomar café na copa.
  Quando o Jarvis passa um trabalho, uma folha 📄 voa da mesa dele para a do agente. `!` amarelo = precisa de você
  (ex.: cliente esperando no WhatsApp).
- Os status são reais: projetos rodando, agentes do time de dev, Juliana (WhatsApp), jogos, filmes, rotinas do n8n,
  Hermes, DeepSeek e Ollama.
- **＋ Nova mesa**: crie setores/funções novos (ex.: "Grupo de benefícios"). Entram como **vaga** (pontilhado amarelo),
  com anotações do que vão fazer; viram agente de verdade quando você pedir ao Jarvis. Já vêm vagas sugeridas
  (YouTube, conversão, redes sociais, tráfego pago, e-mail), que dá para renomear ou apagar.
- Fica salvo em `jarvis-escritorio.json` na config do Claude.

**Vídeo pesado não derruba mais o servidor**
- Todo `ffmpeg` roda com prioridade baixa (`nice`/`ionice`) e usando metade dos núcleos (`JARVIS_FFMPEG_THREADS`).
- O reconhecimento de voz também usa metade dos núcleos (`JARVIS_WHISPER_THREADS`).
- Um vídeo por vez: se o de jogos estiver rodando, o de filme espera na fila.
- `telegram` e `jarvisweb` ficam limitados a 1 núcleo (`JARVIS_CPUS_VIDEO` no `.env`; não passe do número de núcleos da VPS).
- Se ainda travar, veja a memória: `free -h`. A soma dos `mem_limit` do compose passa de 20 GB; numa VPS menor,
  desligue o que não usa (ex.: `sqlserver`) e confira se existe swap.

## Jarvis 1.54: uniforme de qualquer time + escudos na abertura

- Os 2 jogadores do fundo são genéricos (não existem) e vestem o uniforme dos times do 1º jogo. Agora isso vale para
  **qualquer time** (Série B/C/D, estaduais, internacionais): na 1ª vez que o time aparece, o Claude descreve o
  uniforme principal (cores, padrão, gola, calção, meião) e o Jarvis guarda. Time que nem o Claude conhece usa as
  cores da ESPN.
- Painel → ⚽ Jogos → 👕 Uniformes → "Uniformes descritos · corrigir": veja e corrija qualquer descrição (a sua vale
  por cima de tudo). Foto de referência continua opcional para ficar idêntico.
- Com "Escudos dos times" ligado, os escudos oficiais (ESPN) aparecem nos cartões e, agora, também na abertura do
  vídeo, dos dois lados do X.
- Restauração: `versao-1.53.0`.

## Jarvis 1.53: Juliana, a agente de atendimento, conversa por voz

- O agente de atendimento agora é a **Juliana**, e você conversa com ela **por áudio**: ela responde com a **mesma voz
  do atendimento** (ElevenLabs; sem chave, a voz gratuita). Fala só a parte de conversa; detalhes (trecho que muda,
  teste antes/depois) vão por escrito.
- **Telegram:** `/juliana` liga o modo conversa (áudio ou texto vão para ela; `/juliana 2` = número 2) e
  `/juliana sair` volta ao Jarvis. `/atendente <texto>` continua para mensagem avulsa.
- **Painel:** WhatsApp → "Conversar com a Juliana": botão 🎙️ para falar; a resposta em áudio toca sozinha e fica
  no histórico. A conversa é a mesma do Telegram.
- Restauração: `versao-1.52.0`.

## Jarvis 1.52: agente de atendimento do WhatsApp (você treina conversando)

- **📱 Agente de atendimento**: painel → WhatsApp → "Conversar com o agente", ou `/atendente <mensagem>` no Telegram
  (`/atendente 2 …` = número 2). É a mesma conversa nos dois lugares, com memória própria.
- Você ensina em palavras ("na renovação não pergunte o app; peça o comprovante ou o login"). O agente confere as
  decisões anteriores e a base, **lembra se algo contradiz** o que você já disse (com a data), escreve o
  **procedimento**, **testa** como o robô responderia antes → depois e só aplica com o seu ok (botão ✅ ou "pode
  aplicar"). Backup e desfazer sempre; cada decisão fica registrada.
- Também analisa as conversas reais ("como foi hoje?") e sugere ajustes; não fala com clientes.
- O robô segue os **procedimentos** com prioridade sobre a base e ficou mais objetivo: pergunta só o necessário para
  o próximo passo e não pede dado só para preencher a ficha.
- Arquivos: `<atendimento>/agente/` (procedimentos.md, decisoes.md, versoes/). Ferramenta: `jarvis-atendimento`.
- O WhatsApp ativo (campanhas para quem já falou com você) fica para a próxima etapa. Restauração: `versao-1.51.0`.

## Jarvis 1.51: jogadores com o uniforme do time

- O pedido da imagem agora descreve o **uniforme completo** (camisa com o padrão, calção e meião) de ~60 clubes e
  seleções, mostra os jogadores de frente/três-quartos (do joelho para cima, rosto na sombra) para o uniforme
  aparecer inteiro, e põe o uniforme como o mais importante da imagem.
- **👕 Uniformes de referência** (⚽ Jogos): mande uma foto do uniforme de qualquer time; quando ele estiver no 1º
  jogo, a foto vai junto para a IA copiar cores, listras, gola, calção e meião (sem escudo, patrocínio, marca e
  número). Depois use 🎨 Nova arte para ver.
- Restauração: `versao-1.50.0`.

## Jarvis 1.50: arte dos jogos no estilo do modelo do Canva + jogadores do jogo principal

- Banner (estilo "arte") redesenhado no visual aprovado no Canva: "JOGOS DE HOJE" grande com traço neon, data,
  selo neon, cartões escuros com borda e cantoneiras neon, círculos dos times, horário grande, "x" neon, faixa com
  o ícone de TV e os canais, rodapé "Bom jogo!" com bola. Escudos continuam opcionais (ESPN, sua responsabilidade).
- Fundo do dia: 2 jogadores FICTÍCIOS (de costas/três-quartos, rosto não aparece), um de cada lado, com camisas que
  lembram as dos dois times do primeiro jogo: padrão conhecido (listras, faixa, cores) de ~50 clubes brasileiros e
  internacionais, ou as cores da ESPN. Sem escudo, patrocínio, número ou texto na imagem.
- Vídeo: abre com a cena "JOGO PRINCIPAL DE HOJE" (times, horário e canal sobre os jogadores) e segue com os
  cartões; no formato TV os cartões se ajustam para não encostar no rodapé.
- Restauração: `versao-1.49.2`.

## Jarvis 1.49.2: correção urgente do atendimento do WhatsApp

- A 1.49.0 quebrou a rota `/api/gatilho` (o n8n entrega as mensagens do WhatsApp e as rotinas por ela): um
  `import` dentro da central de chaves fazia o painel fechar a conexão ("The connection to the server was closed
  unexpectedly"). Corrigido. O robô voltou a receber as mensagens.
- O `scripts/validar.py` agora barra esse tipo de erro antes de qualquer versão sair.

## Jarvis 1.49.1: diagnóstico do WhatsApp diz por que o n8n não chamou o Jarvis

- No passo "n8n repassou ao Jarvis", o diagnóstico agora mostra a causa: token do n8n diferente do Jarvis (o Jarvis
  registra a recusa), token vazio, ou o erro real do nó "Jarvis responde" pela API do n8n (conexão recusada,
  tempo esgotado…), com o comando que resolve.
- Novo `./n8n-token-sincronizar.sh`: confere se o n8n usa o mesmo token do Jarvis, corrige e reinicia só o n8n
  (não mexe nos fluxos e não mostra o token).

## Jarvis 1.49: central de chaves e conexões

- Painel → 🧠 Cérebro → **🔑 Chaves e conexões**: adicionar, trocar, testar e remover as chaves das IAs (Gemini,
  DeepSeek, Ollama, Groq, OpenRouter, Mistral, Grok, NVIDIA, Cloudflare) sem editar arquivo nem reiniciar: vale na
  hora em todo o Jarvis. ElevenLabs e TMDB aparecem com o status e o lugar onde trocar.
- Segurança: só o final da chave aparece; trocar/remover pede a senha do painel de novo, fica no histórico e avisa no
  Telegram (sem a chave). Os endereços dos serviços não são editáveis pelo painel (só no .env da VPS).
- Chave do painel vale por cima do .env; "Remover" desliga mesmo que esteja no .env; "Voltar ao .env" desfaz.
- Canva e Picsart: status da conexão (conectado / precisa entrar na conta) e o passo a passo para trocar de conta
  (`/mcp` → Clear authentication → Authenticate).
- Restauração: `versao-1.48.0`.

## Jarvis 1.48: jogos internacionais no banner e no vídeo

- Além dos brasileiros, entram os **internacionais que passam no Brasil**: Libertadores, Sul-Americana, Mundial de
  Clubes, Copa do Mundo, Eliminatórias, Copa América, amistosos de seleções, Champions, Premier League, La Liga e
  Serie A (marcados por padrão); Bundesliga, Ligue 1, Europa/Conference League, Portugal, Saudi, MLS e Argentino
  opcionais. Painel → ⚽ Jogos → 🌎 Internacionais.
- Ordem: brasileiros sempre primeiro → internacionais com time brasileiro (ou a seleção) → demais, pela importância.
- Só entra internacional com **canal brasileiro confirmado** na pesquisa (o canal que a ESPN informa é o dos EUA e
  é ignorado). Limite de internacionais por dia (padrão 8) para o banner/vídeo não ficar enorme.
- Texto dos grupos com 🌎 nos internacionais; o banner vira "FUTEBOL NO BRASIL E NO MUNDO" quando há internacional.
- Restauração: `versao-1.47.0`.

## Jarvis 1.47: skills de design, SEO e segurança

- Revisadas e adicionadas ao `jarvis-extras` (commits revisados em 26/11/2026; atualizar exige nova revisão:
  `jarvis-extras --atualizar-design`):
  - **Claude SEO** (AgriciDaniel/claude-seo): `/seo audit <site>`, `/seo page`, `/seo schema`, sitemap. Sem
    rastreamento; extensões pagas (DataForSEO, Ahrefs…) só se você configurar.
  - **taste-skill** (Leonxlnx): sites institucionais. **hallmark** (Nutlope): landing pages e "no estilo deste site".
    **impeccable** (pbakaus): `/impeccable audit`, `polish`, `critique` em telas prontas. O designer usa uma por
    entrega; o detector automático do impeccable fica desligado (pesa em todos os projetos).
  - **Segurança:** `/claude-security` (plugin oficial da Anthropic: auditoria completa, confirma achados e propõe
    patches; informa o custo antes) + `/security-review` (nativo, revisa as mudanças).
- Instalar: `docker compose exec dev jarvis-extras`. Restauração: `versao-1.46.0`.

## Jarvis 1.46: Picsart (banners e vídeos com a sua conta)

- O Jarvis pode usar o **MCP oficial da Picsart** (hospedado pela Picsart, sem chave de API): gera banners e artes
  das páginas, remove fundo, aumenta resolução e cria fundos/cenas de vídeo, com a sua conta Picsart.
- Conectar: na VPS `./picsart-configurar.sh` e siga os passos (autoriza uma vez pelo navegador do PC; se a página
  final der erro de "localhost", o script mostra o comando que conclui).
- Gerar gasta **créditos da sua conta Picsart**; o Jarvis consulta o preço antes e confirma com você o que for caro
  (vídeo). A skill de página usa a Picsart para banners (WebP, versões para PC e celular).
- Restauração: `versao-1.45.0`.

## Jarvis 1.45: navegador do seu PC (Chrome do Jarvis no Windows, via Tailscale)

- O Jarvis controla um **Chrome separado** no seu Windows para homologar o que criou e buscar dados em sistemas em
  que você entrou: abre páginas, clica, preenche, lê o console de erros e tira prints. Você vê tudo ao vivo.
- Perfil próprio (não é o seu Chrome do dia a dia: banco, e-mail etc. ficam de fora). A porta fica liberada só na
  rede Tailscale e só enquanto a janela estiver aberta; fechou = acesso encerrado.
- Instalar no PC: baixe `<endereço do painel>/api/navegador/kit` (ou a pasta `pc-windows/` do repositório),
  descompacte, abra `Chrome-do-Jarvis.bat` e mande ao Jarvis o comando que aparece (já copiado): `/navegador 100.x.x.x`.
- `/navegador` mostra se está conectado e as abas abertas · `/navegador desligar`.
- Regras: aba nova para o trabalho dele; nunca digita senhas, códigos ou cartão, nem conclui pagamento, compra,
  envio ou exclusão sem você pedir. Só aceita IP da rede Tailscale. Imagem nova: `docker compose build`.
- Restauração: `versao-1.44.0`.

## Jarvis 1.44: atendimento responde em áudio (ElevenLabs)

- O robô do WhatsApp responde com **mensagem de voz**. Modos: quando o cliente manda áudio (padrão), sempre ou nunca.
- Se o cliente disser que não sabe ler (ou prefere áudio), a IA percebe e passa a responder em áudio só para ele.
  Se pedir para voltar a escrever, volta ao texto.
- Links, códigos Pix e números longos não são lidos em voz alta: vão por escrito junto (ou sempre/nunca, no painel).
  Valores viram fala ("R$ 35,90" → "35 reais e 90 centavos"). Enquanto gera, o cliente vê "gravando áudio…".
- **ElevenLabs:** painel → WhatsApp → 🔊 Respostas em áudio → cole a chave, escolha a voz da sua conta, o modelo e a
  velocidade; "▶ Ouvir teste" toca uma amostra. A chave fica em /segredos/elevenlabs.json (600), só mascarada.
- Sem chave (ou se a ElevenLabs falhar), usa a voz gratuita do Jarvis; se até a voz falhar, manda o texto.
- Restauração: `versao-1.43.0`.

## Jarvis 1.43: o atendimento do WhatsApp ouve áudios e vê imagens

- **Áudio** do cliente vira texto (a mesma transcrição dos áudios do Telegram) e a IA responde ao que ele falou.
- **Imagem/print/comprovante:** a IA descreve o que aparece (mensagens de erro, valores, datas, nome do app/plano) e
  responde com base nisso. **Vídeo:** 4 quadros + a fala. Figurinha: entende a emoção. PDF/arquivo: pede para o
  cliente dizer o que precisa.
- A mídia é baixada do WAHA, usada e apagada na hora (não fica guardada); no histórico fica só o texto.
- Vale para os dois números. Liga/desliga no painel: WhatsApp → Recursos → "🎧 Ouvir áudios e ver imagens/vídeos"
  (ligado por padrão). Cada imagem custa uma chamada curta ao modelo rápido.
- Restauração: `versao-1.42.0`.

## Jarvis 1.42: imagens e vídeos para o Jarvis entender a demanda

- **Painel:** botão 📎 no chat (no celular abre câmera/galeria), colar print com Ctrl+V ou arrastar arquivos para a
  tela. As miniaturas aparecem antes de enviar e ficam na conversa. Até 500 MB por arquivo.
- **Telegram:** fotos, álbuns, vídeos, vídeos redondos e arquivos (o Telegram limita o bot a 20 MB; maior, pelo painel).
  Mandou sem legenda? O Jarvis espera 40 s: o próximo texto ou áudio vira a explicação do anexo.
- **Vídeo:** o Claude não assiste vídeo, então o Jarvis extrai até 12 quadros com o instante de cada um e transcreve a
  fala (até 15 min). O Claude vê os quadros como imagens e pode extrair mais quadros de um trecho específico.
- Os anexos ficam em `/workspace/.jarvis-anexos` (fora dos projetos, não vão para o Git) e são apagados após 30 dias.
- Restauração: `versao-1.41.0`.

## Jarvis 1.41: servidores (SSH, SFTP e MySQL/MariaDB) para homologar na hora

- O Jarvis acessa os servidores cadastrados para reproduzir o problema, ler logs, consultar o banco, corrigir e
  validar no mesmo instante: `jarvis-servidor ssh | sql | baixar | enviar | testar`.
- **Homologação:** lê e altera, sempre com backup antes. Arquivo substituído → cópia no próprio servidor em
  `~/.jarvis-backup/<data>/`. SQL que altera dados → dump das tabelas em `.jarvis-backups/` (desfazer:
  `jarvis-servidor restaurar-sql <srv> <arquivo>`).
- **Produção:** somente leitura (comandos de consulta, SELECT/SHOW, download). Enviar arquivo e alterar banco são
  bloqueados pela ferramenta, não só por regra.
- Sempre bloqueados: DROP DATABASE, usuários/permissões do banco, `rm -rf /`, desligar/reiniciar o servidor.
- Cadastro: `./servidores-configurar.sh` (host, usuário, pasta, banco; acesso pela chave SSH do Jarvis, recomendado,
  ou por senha). As senhas ficam só no volume `servidores-segredos` (600) e são apagadas de qualquer saída.
- `/servidores` lista os servidores e as últimas ações (auditoria) · `/servidores testar <nome>`.
- A imagem ganhou `openssh-client` e `sshpass`: precisa de `docker compose build`. Restauração: `versao-1.40.0`.

## Jarvis 1.40: memória contínua

- O Jarvis passa a lembrar o que aprende nas conversas, **em todos os projetos**: `memoria/geral.md` (vale para tudo:
  hospedagem, deploy, preferências, padrões) e `memoria/projetos/<projeto>.md` (escopo, configurações, decisões,
  problemas resolvidos). Fica na base de conhecimento e vai para o GitHub (`jarvis-conhecimento`).
- Toda execução já começa com essa memória no prompt. Ele parte do que sabe e, se algo parecer diferente, pergunta
  ("na memória está X; agora é Y?") e atualiza. A versão antiga vai para `memoria/historico.md`.
- Duas formas de anotar: o próprio Jarvis anota na hora (`jarvis-memoria anotar`) e, ao fim de cada conversa, uma
  revisão leve (Haiku, em segundo plano) pega o que faltou. Senhas, tokens e chaves nunca são guardados.
- `/memoria` mostra o que ele sabe · `/memoria <termo>` busca · `/memoria anotar [geral] <fato>` ·
  `/memoria esquecer [geral] <assunto>`. No painel: 🧠 Cérebro → "Memória contínua" (automática, manual ou desligada).
- Também funciona no Claude Code direto no terminal (o hook de início de sessão carrega a memória).
- Restauração: `versao-1.39.0`.

## Jarvis 1.39: DeepSeek como ajudante

- **/deepseek <pedido>** no Telegram e no painel (resposta com o rótulo 🐋 DEEPSEEK; aparece na equipe enquanto
  trabalha). `/deepseek` sozinho mostra o modelo em uso.
- Entra na fila automática dos ajudantes e no **conselho de IAs**; os agentes podem chamá-lo com
  `jarvis-ajudante --ia deepseek`. Modelo: `deepseek-flash` (o mais rápido e barato); `deepseek-v4-pro` como reserva.
  Para fixar: `JARVIS_AJUDANTE_DEEPSEEK_MODELO=deepseek-v4-pro` no `.env.ajudantes`.
- Responde sem o modo "pensar" (mais rápido e barato); `DEEPSEEK_PENSAR=1` liga o raciocínio.
- Ligar: `./ajudantes-configurar.sh` → cole a chave (platform.deepseek.com/api_keys). Restauração: `versao-1.38.0`.

## Jarvis 1.38: números bloqueados no atendimento do WhatsApp

- O robô **ignora** os números bloqueados: não responde, não chama você e o vigia não avisa "mensagem sem resposta".
  Você continua podendo falar com eles pelo celular. Cada número de WhatsApp (1 e 2) tem a sua lista.
- Painel 📱 → **🚫 Números bloqueados** (adicionar com nome, desbloquear) e botão 🚫 nas conversas que esperam você.
- Telegram: `/bloquear 21 99999-0000 Fulano` · `/desbloquear 21999990000` · `/bloqueados` (número 2: `/bloquear 2 …`).
- O número é reconhecido com ou sem +55, com ou sem o nono dígito, e também quando o WhatsApp manda o ID interno
  (@lid) no lugar do telefone. Restauração: branch `versao-1.37.1`.

## Jarvis 1.37.1: trailer por link direto

- Painel 🎬 Filmes → "cole o link direto do arquivo do trailer" (Google Drive, Dropbox, área de imprensa da
  distribuidora…) e o Jarvis baixa (até 400 MB), corta e monta. No Telegram:
  `/filme Duna Parte Dois https://link-do-arquivo.mp4`. Links de compartilhamento do Drive/Dropbox são convertidos.
- Links do YouTube são recusados: os termos do YouTube proíbem baixar os vídeos de lá.

## Jarvis 1.37: vídeo pelo gateway, roteiro pelo Claude e vídeos de filmes/séries (TMDB)

**Vídeo dos jogos**
- Painel ⚽ → "Quem gera o fundo com IA": **Gemini** (Omni Flash) ou **Meu gateway**. No gateway, escolha o modelo de
  vídeo da lista dele (o painel mostra os que parecem de vídeo). O Jarvis usa o padrão `/v1/videos` (o mesmo do
  LiteLLM/OpenAI) e, se o gateway pedir formulário, tenta assim. Modelos Claude não geram vídeo: quem gera é um
  modelo de vídeo que o gateway ofereça.
- **🎬 O Claude escreve o roteiro da cena** de cada dia (com qualquer provedor), a partir dos jogos do dia.

**Filmes e séries (🎬 no painel · `/filme <nome>` no Telegram)**
- Cole o token do TMDB (themoviedb.org → Configurações → API → "Token de leitura da API"). Fica em
  `/segredos/tmdb.json` (600) e o painel mostra mascarado.
- Busque, escolha e gere: vídeo vertical e/ou horizontal com as imagens do título em movimento, logo/título, nota,
  ano, gêneros, duração/temporadas, chamada e resumo **sem spoiler** escritos pelo Claude, elenco, "onde assistir"
  (opcional), botão com a sua chamada ("Disponível agora") e cartão final com o cartaz. Vai para o Telegram com legenda
  e o link do trailer oficial.
- **Cortes do trailer:** envie o arquivo do trailer no painel (é seu; o Jarvis não baixa do YouTube) e o vídeo passa a
  usar os melhores cortes nas trocas de cena, com o áudio do trailer. Sem trailer, usa a música dos jogos (se houver).
- `/filme Duna 2021` escolhe pelo ano; se houver outros parecidos, o Jarvis lista para você escolher.
- Crédito do TMDB no rodapé dos vídeos (exigência dos termos da API).
- Restauração: branch `versao-1.36.0`.

## Jarvis 1.36: cérebro (modelo e esforço por demanda, agentes por nível, conselho de IAs, escalada para o Fable)

- **Painel → 🧠 Cérebro** (ou `/cerebro` no Telegram): modelo do Jarvis (padrão **Opus**), **esforço** (automático:
  alto para planejar e começar uma demanda, médio para continuar e revalidar; ou baixo, médio, alto, extra-alto,
  máximo), **nível dos agentes** (econômico · equilibrado · caprichado), **conselho de IAs** e **escalada**.
- **Agentes por tarefa:** no plano de cada demanda o Jarvis define qual agente faz cada parte, com qual modelo e
  esforço, e passa isso em cada chamada. Padrão (equilibrado): explorador/documentador/deploy em Haiku baixo,
  testador Haiku médio, designer/desenvolvedor/android em Sonnet médio, dba/revisor Sonnet alto, arquiteto e casos
  críticos (pagamentos, segurança, migração, bug que já falhou) em Opus alto.
- **Fable:** o Jarvis conta quando você diz que ainda não resolveu. Na 2ª vez ele aumenta o esforço e muda de
  abordagem; na 3ª **sugere o Fable** (ou usa sozinho, se você escolher "automático"). `/fable <pedido>` usa o Fable
  só naquela mensagem; "funcionou"/"deu certo" zera a contagem.
- **Conselho de IAs:** Gemini, Groq, Ollama, Grok e as outras ligadas opinam em paralelo
  (`jarvis-ajudante --conselho`); o Jarvis compara, escolhe a melhor abordagem e registra em docs/DECISOES.md.
  Padrão: nas decisões e nos problemas difíceis; "sempre" = em todas as etapas.
- Comandos: `/esforco alto` · `/equipe economico` · `/conselho sempre` · `/escalar automatico` · `/modelo sonnet`.
- Corrigido: a janela "Projetos e GitHub" voltou a abrir por cima da tela. Restauração: branch `versao-1.35.0`.

## Jarvis 1.35: skill criar-pagina (/pagina)

- **`/pagina <o que a página deve fazer>`** no Telegram e no painel (ou `/jarvis:pagina`): o Jarvis cria UMA página do
  zero pronta para converter: landing, vendas, captura de contatos, serviço/local, institucional, evento, link da bio.
- Método: briefing de até 5 perguntas (ou deduz e anota as premissas), estrutura certa para o tipo de página, texto
  persuasivo, formulário em PHP que funciona no cPanel (anti-robô, LGPD, página de obrigado) e/ou botão de WhatsApp,
  SEO e compartilhamento, desempenho, testes com `jarvis-site` e nota visual ≥ 8, prints e link da prévia.
- Nunca inventa depoimentos, números, logos de clientes ou IDs de rastreamento: o que faltar vira `[MARCADOR]` e
  vem listado na entrega. Publicar continua sendo decisão sua.
- Para um site inteiro ou refatoração continua a skill `refatorar-site`. Restauração: branch `versao-1.34.0`.

## Jarvis 1.34: Ollama Cloud como ajudante (igual ao Hermes)

- **/ollama <pedido>** no Telegram e no painel: pergunta direto ao Ollama (modelos abertos grandes na nuvem:
  gpt-oss 120b, qwen3-coder, deepseek…). A resposta chega com o rótulo 🦙 OLLAMA; no painel ele aparece na equipe
  como ativo enquanto trabalha. `/ollama` sozinho mostra se está ligado e qual modelo está usando.
- Os agentes do Jarvis também podem chamá-lo (`jarvis-ajudante --ia ollama …`) para segunda opinião e textos longos,
  e ele entra na fila automática dos ajudantes. Dados sensíveis são apagados antes de enviar.
- Ligar: `./ajudantes-configurar.sh` → cole a chave do Ollama (ollama.com/settings/keys). Para fixar um modelo:
  `JARVIS_AJUDANTE_OLLAMA_MODELO=qwen3-coder:480b` no `.env.ajudantes`.
- Restauração: branch `versao-1.33.0`.

## Jarvis 1.33: painel novo (layout A · Cockpit) para PC, tablet e celular

- **Holograma em destaque:** o Jarvis/Hermes ocupa a altura toda de um quadro próprio, sem degradê; o status
  (processando, agentes da vez) fica no canto, por cima.
- **Equipe:** cartões dos agentes trabalhando (o que cada um está fazendo, tempo e barra de atividade), os que
  terminaram com "✓ há X min" e os ociosos recolhidos em "+N agentes ociosos". No topo: "● N agentes trabalhando".
- **Ferramentas com nome** no PC (as menos usadas ficam só com ícone em telas menores que 1600px).
- **Tablet:** a equipe vira uma faixa de fichas que rola de lado; ferramentas no botão "☰ Ferramentas" e o painel
  do projeto no botão "📋 Projeto".
- **Celular:** holograma no alto, conversa, e abas embaixo: Conversa · Agentes · Projeto · Ferramentas.
- Depois de atualizar, aperte Ctrl+F5 (ou feche e abra o painel no celular). Restauração: branch `versao-1.32.1`.

## Jarvis 1.32.1: agentes trabalhando de verdade e holograma novo

- **Agentes:** o Claude Code 2.1+ passou a rodar subagentes em segundo plano por padrão; o painel via o agente
  "terminar" logo no início (sempre "ocioso") e o orquestrador seguia sozinho. Agora o Jarvis roda com
  `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` e as regras pedem agentes em primeiro plano: cada um aparece ativo no
  painel, acende a sua região do cérebro e o Jarvis espera o relatório antes de seguir.
- **Holograma:** cérebro, rosto e esfera (Hermes) novos. Ao falar, aproxima o rosto e mostra o anel de onda sonora
  na base reagindo à voz; pensando, órbitas de luz em volta do cérebro e fluxos de dados entrando pelos lados.
- Restauração: branch `versao-1.32.0`.

## Jarvis 1.32: segundo número de WhatsApp e treinador do atendimento

**Segundo número (grátis):** outro WAHA, com QR code, base de respostas, configurações, vigia e estado próprios.
```bash
cd ~/jarvis/container && git pull && docker compose build
./whatsapp2-configurar.sh "Nome da loja 2"        # desligar: ./whatsapp2-configurar.sh desligar
```
- Painel → 📱: botões no topo para trocar entre os números (tudo abaixo passa a ser do número escolhido).
- As mensagens do número 2 vão direto do WAHA ao painel (endereço com senha, só na rede interna), sem n8n.
- Avisos no Telegram vêm com o nome do número: 【Loja 2】. Comandos: `/atendimento 2`, `/whatsapp 2 testar`,
  `/assumir 2 <número>` (sem o "2", o Jarvis procura em qual número a conversa está).
- O número 1 continua exatamente como antes (n8n). Pagamentos, consulta e teste grátis seguem no número 1.

**Treinador do atendimento:** toda segunda (fluxo n8n "Jarvis · Treinador do atendimento", importe e ative) ele lê
as conversas da semana de cada número, aponta onde o robô se perdeu e manda no Telegram o relatório + a base
sugerida (trechos novos com "(novo)"). Nada muda sem você: `/treinar aplicar` · `/treinar descartar` ·
`/treinar 2 aplicar`, ou no painel 📱 → 🎓 Treinador (Analisar agora · Revisar na base · Aplicar · Descartar).
A base anterior fica guardada. Usa o modelo mais forte (alguns centavos por semana).
- O atendimento passou a guardar um diário das conversas por 35 dias (sem o número do cliente) para o treinador.
```bash
docker compose --profile automacoes exec -T -u node n8n n8n import:workflow --input=/opt/jarvis-n8n/fluxos/jarvisRotina0010.json
```
- Restauração: branch `versao-1.31.0`.

## Jarvis 1.31: atendimento do WhatsApp que lê e pensa antes de responder

- Antes de cada resposta o robô **pensa** (o que o cliente disse, o que já se sabe, o que falta, o que a base manda)
  e só depois escreve. O raciocínio nunca vai para o cliente.
- **Ficha por cliente** (caso, login, app, aparelho, resumo): ele lembra o que já foi dito e não repete perguntas.
  Quando chama você, o aviso no Telegram traz o 📝 resumo do pedido.
- A **sua base manda**: as regras internas não brigam mais com ela (ex.: não fala de pagamento se a base não explica).
- Imagem/áudio/vídeo: em vez de resposta pronta, o robô responde dentro do assunto e pede para escrever.
- Painel → 🧠 **Atendimento caprichado**: usa o modelo mais forte (entende melhor, custa mais por mensagem).
- Restauração: branch `versao-1.30.1`.

## Jarvis 1.30.1: tudo no Telegram ao gerar

- O Telegram recebe **um álbum só** com o banner, o vídeo vertical, o vídeo da TV e a imagem da TV, e depois o texto
  pronto para o WhatsApp. Se o álbum falhar, vão um por um.
- Agora também ao clicar **Gerar agora** ou **Nova arte** no painel (não só na rotina das manhãs). Para desligar:
  painel ⚽ → "Ao gerar, mandar no meu Telegram". O grupo continua recebendo só na rotina diária.

## Jarvis 1.30: vídeo dos jogos para TV (horizontal) e música de fundo

- Painel ⚽ → **Formatos**: 📱 vertical (Status/Reels) e/ou 📺 **horizontal 16:9 (TV)**. Na TV, os jogos aparecem
  em 2 colunas (até 6 por tela) e também sai uma **imagem parada** por tela, para TVs que só mostram fotos.
- O vídeo de TV vai para o seu Telegram (o grupo recebe só o vertical) e pode ser baixado no painel (pendrive/TV).
- Com IA e os dois formatos ligados, são 2 clipes por dia (~US$ 2); o limite do mês vale para os dois.
- **Música de fundo:** envie um mp3/m4a/wav/ogg no painel (até 25 MB; guarda até 5 min) e ajuste o volume. Ela repete
  se o vídeo for maior, entra e sai suave e, no vídeo com IA, toca junto com a torcida. Use música sem direitos
  autorais (Biblioteca de áudio do YouTube, por exemplo), senão Instagram/YouTube podem bloquear ou tirar o som.
- Restauração: branch `versao-1.29.0`.

## Jarvis 1.29: vídeo dos jogos do dia

- **Vídeo vertical (9:16)** para Status, Reels e grupos, enviado no seu Telegram e no grupo junto com a imagem e o texto.
- Painel ⚽ → **Vídeo dos jogos**:
  - **Animado (grátis):** a arte do dia com zoom lento, o título descendo e os jogos entrando um a um.
  - **Com IA:** o fundo vira um vídeo de verdade (estádio, luzes, torcida, bola girando, **com som de torcida**), gerado
    pelo **Gemini Omni Flash** com a sua chave do Gemini (conta paga). A arte do dia é o primeiro quadro, então vídeo
    e banner combinam. Cerca de **US$ 1 por dia** (um clipe por dia; gerar de novo reaproveita). "Nova arte" refaz os dois.
  - **Limite por mês** (padrão US$ 20): ao passar, sai o animado. O painel mostra o gasto do mês.
- A IA faz **só o fundo**: times, horários e canais são colocados pelo Jarvis, então nunca saem errados. Sem pessoas
  reais e sem texto inventado. Se a IA falhar, sai o animado e o aviso aparece no painel.
- O Flow (labs.google) não tem API; o mesmo tipo de modelo é usado pela API do Gemini. Os Veo 3.1 "preview" da API
  foram desligados pelo Google em 22/10/2026, por isso o Jarvis usa o Omni Flash (`JARVIS_VIDEO_MODELO` para trocar).
- Banner com arte: agora 4 jogos por página (com 5, o último cartão encostava no rodapé).
- Restauração: branch `versao-1.28.0`.

## Jarvis 1.28: alerta antes dos jogos (no seu Telegram e num grupo)

- ⚽ → **⏰ Alerta antes do jogo**: X minutos antes (padrão 30) de cada jogo da lista, o Jarvis manda a imagem
  "COMEÇA EM 30 MINUTOS" (mesmo estilo do banner) + texto com times, campeonato, horário e canal. Jogos no mesmo
  horário saem num alerta só. Não repete.
- Destinos: o seu Telegram (bot do Jarvis) e/ou **um grupo**, por um **bot próprio só de envio**: crie no
  @BotFather (/newbot), cole o token no painel, coloque o bot no grupo, mande uma mensagem lá e clique em
  **🔎 Detectar grupo**. **📨 Testar envio** confere tudo. O token fica em `/segredos/jogos_grupo.json` (600) e nunca
  aparece inteiro no painel.
- Opcional: **mandar no grupo também a lista do dia** quando ela sai (rotina das 8h).
- Se o bot perder permissão no grupo, você recebe o aviso no seu Telegram.

## Jarvis 1.27.1: escudos dos times (opcional)

- ⚽ → "Mostrar os escudos dos times": usa a imagem de cada time informada pela ESPN (baixada uma vez e guardada),
  dentro de um círculo claro no cartão. Uso informativo, sob sua responsabilidade. Escudo que não baixar → selo com
  cores e sigla. O fundo da IA continua sem escudos (a IA desenharia escudos falsos).

## Jarvis 1.27: banner dos jogos com arte de IA

- Estilo novo **🎨 Arte com IA** (padrão): fundo gerado por IA todo dia (estádio à noite, refletores, bola e dois
  jogadores **genéricos** nas cores dos times do jogo principal) + layout "DESTAQUES DO DIA" com cartões: selo de cada
  time **nas cores do clube com a sigla** (COR, CAM, FLA…), horário grande, canal em destaque, placar ao vivo em dourado.
- Sem jogadores reais (direito de imagem) e sem escudos oficiais (marcas dos clubes): a IA recebe essa proibição.
- Usa as chaves dos ajudantes: **Gemini** (modelo de imagem) e, se não der, **Cloudflare Workers AI** (FLUX).
  Sem chave ou se a IA falhar, sai o **banner simples** de antes (o aviso aparece no ⚽).
- A arte é gerada 1 vez por dia e reaproveitada; **🎨 Nova arte** no ⚽ pede outra. Estilo escolhido no ⚽ → Salvar.
- Fonte Bebas Neue (OFL) incluída no projeto para os títulos.

## Jarvis 1.26: mensagens seguidas viram uma resposta só

- O cliente manda "Bom dia" e logo depois "Quero renovar": o robô espera ele terminar (7 s, ajustável em
  📱 → Proteção → Juntar mensagens seguidas) e responde **uma vez**, lendo tudo junto e indo direto ao ponto.
- Se chegar mensagem nova enquanto a resposta ainda está sendo escrita, essa resposta é descartada e sai uma só,
  com tudo. A mesma mensagem entregue duas vezes continua gerando uma resposta.
- A IA responde fora da trava geral: um cliente não espera mais a resposta do outro.
- Regras: não se apresentar de novo na mesma conversa; não perguntar o que o cliente já disse.

## Jarvis 1.25: atendimento sem nome de IA e com textos variados

- **Sem marca de IA:** o robô não diz mais qual IA o move (Claude, Anthropic, GPT, Gemini…). Regra no prompt +
  filtro que limpa qualquer menção antes de enviar ("Sou o assistente virtual da empresa"). Se o cliente perguntar se
  é robô, ele diz que é o assistente virtual automático.
- **Respostas da conversa variadas:** cumprimentos e frases mudam a cada conversa; o robô recebe as últimas frases
  usadas e é instruído a não repeti-las (temperatura mais alta).
- **Mensagens automáticas variadas** (pagamento, consulta…): o Jarvis cria sozinho 4–6 versões de cada mensagem,
  com as mesmas variáveis ({nome} {valor} {login} {vencimento}), descarta versões que perdem variáveis e refaz quando
  você muda o texto (ou a cada 7 dias). As suas versões com `||` continuam valendo. Liga/desliga em 📱 → Recursos →
  🔀 Variar o texto.
- A mensagem de instabilidade (quando o modelo falha) também varia.

## Jarvis 1.24: WhatsApp no motor GOWS (recebimento em tempo real)

- **Problema:** no motor NOWEB a conexão de recebimento morria em silêncio. A sessão continuava "conectada", enviar
  funcionava, mas as mensagens dos clientes só chegavam (horas depois) quando a sessão reiniciava, e o robô as
  ignorava por serem antigas.
- **Solução:** o WhatsApp passa para o motor **GOWS** (Go, sem navegador, substituto do NOWEB, grátis no WAHA Core),
  imagem fixa `devlikeapro/waha:gows-2026.10.1`. Troca: `./whatsapp-trocar-motor.sh` (pede escanear o QR uma vez;
  o QR chega no Telegram). Voltar: `WAHA_IMAGEM=devlikeapro/waha:latest` e `WAHA_MOTOR=NOWEB` no `.env`.
- **Vigia:** novo teste "Mensagens chegando na hora". Mensagem de cliente que chega com mais de 10 min de atraso
  = recebimento travado → reconecta a sessão e te manda a lista de quem ficou sem resposta.
- O painel mostra o motor em uso.

## Jarvis 1.23: vigia do atendimento do WhatsApp

- **Vigia** (roda sozinho no painel a cada 5 min, `JARVIS_VIGIA_MIN`): testa a corrente inteira WhatsApp → WAHA → n8n
  → Jarvis e **conserta sozinho** quando dá:
  - sessão parada/falhou/travada → reinicia (sem QR);
  - webhook ou histórico faltando na sessão → grava de novo (sem QR);
  - fluxo do n8n despublicado → publica de novo (precisa da chave da API do n8n: `./n8n-api-configurar.sh`;
    sem ela, ele avisa para você publicar);
  - **cliente escreveu e a mensagem não chegou** (compara as conversas do WhatsApp com o que o Jarvis recebeu) →
    regrava o webhook e te manda **a lista de quem ficou sem resposta**;
  - WhatsApp desconectado → manda o **QR code no Telegram** e avisa quando conectar.
  Avisa uma vez por problema e quando volta ao normal.
- O histórico de conversas do motor NOWEB passa a ficar ligado na sessão (é o que permite achar mensagens perdidas).
- Painel 📱: 🔄 **Reiniciar** (sem QR), 🔌 **Reconectar (QR novo)** e o quadro 🛡 Vigia (último teste, testar agora, ligar/desligar).
- Telegram: `/whatsapp` (situação do vigia) · `/whatsapp testar` · `/whatsapp reiniciar` · `/whatsapp reconectar`.
- Cada teste aparece como uma execução no fluxo do n8n (é o teste passando pelo mesmo caminho das mensagens).

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
