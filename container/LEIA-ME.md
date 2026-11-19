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
Áudio: mande mensagem de voz (transcrição local). `/audio auto|sempre|nunca` controla a resposta falada.
`/agentes on|off` liga/desliga os avisos de cada agente trabalhando.
Logs: `docker logs -f jarvis-telegram`. Só os chat IDs autorizados conseguem usar o bot.
