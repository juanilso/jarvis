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
