# Stack do projeto

Perfil ativo: <php-cpanel | android | ambos>

---
## Perfil: PHP + cPanel
- PHP: <versão do MultiPHP no cPanel, ex. 8.2> — o código NÃO pode usar recursos de versão maior
- Banco principal: <MySQL/MariaDB | SQL Server | SQLite>
- Acesso a dados: PDO com prepared statements (sempre). Nada de concatenar SQL.
- Dependências: Composer (`vendor/` não vai para o git; no deploy roda `composer install --no-dev`)
- Estrutura: `public/` como document root; config e segredos fora de `public/`
- Segredos: `.env` (fora do git) lido via `getenv`/biblioteca dotenv
- Testes: PHPUnit; testes de banco rodam em SQLite em memória quando possível
- Qualidade: `php -l`, PHPStan nível <5>
- Hospedagem compartilhada: sem root, sem daemons; tarefas agendadas via Cron do cPanel;
  rotas via `.htaccess`; limite de memória/tempo de execução do plano
- Deploy: <Git Version Control do cPanel com `.cpanel.yml` | FTP/SFTP | Gerenciador de Arquivos>

### Compatibilidade de bancos
- Migrations em SQL separadas por driver quando a sintaxe divergir
  (`migrations/mysql/`, `migrations/sqlsrv/`, `migrations/sqlite/`)
- Atenção: `AUTO_INCREMENT` (MySQL) × `IDENTITY` (SQL Server) × `AUTOINCREMENT` (SQLite);
  `LIMIT` × `TOP`/`OFFSET FETCH`; tipos de data; aspas de identificadores
- SQL Server a partir de PHP exige as extensões `sqlsrv`/`pdo_sqlsrv`, que muitas hospedagens
  cPanel compartilhadas NÃO oferecem. Confirme com a hospedagem antes de depender delas.

---
## Perfil: Android
- Linguagem/UI: <Kotlin + Jetpack Compose | Flutter | outro>
- minSdk / targetSdk: <ex. 26 / 35>
- Build: `./gradlew assembleDebug`, testes `./gradlew test`, lint `./gradlew lint`
- Backend: API PHP deste projeto (JSON, autenticação por token)
- Permissões: só as estritamente necessárias, pedidas em tempo de execução e no momento do uso;
  cada nova permissão passa pela fila de decisões
- Tamanho: R8/minify no release, App Bundle (.aab), recursos/imagens otimizados
- Assinatura: keystore FORA do repositório; release só com decisão do usuário
