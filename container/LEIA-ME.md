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
