# Ambiente de desenvolvimento do Jarvis: PHP + bancos + Claude Code, isolado do sistema do host.
FROM ubuntu:24.04

ARG PHP_VERSION=8.3
ARG INSTALL_SQLSRV=false
ENV DEBIAN_FRONTEND=noninteractive TZ=America/Sao_Paulo

# Repetir downloads que falharem (espelhos instáveis)
RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80-retries

# Base + PHP. O PHP 8.3 vem do próprio Ubuntu 24.04 (não depende do PPA).
# Outras versões (7.4, 8.1, 8.2, 8.4) usam o PPA ondrej/php automaticamente.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg git unzip zip nano less sudo tzdata software-properties-common \
      sqlite3 mariadb-client jq ripgrep python3 python3-pip ffmpeg \
 && if [ "$PHP_VERSION" != "8.3" ]; then add-apt-repository -y ppa:ondrej/php && apt-get update; fi \
 && apt-get install -y --no-install-recommends \
      php${PHP_VERSION}-cli php${PHP_VERSION}-mysql php${PHP_VERSION}-sqlite3 php${PHP_VERSION}-mbstring \
      php${PHP_VERSION}-xml php${PHP_VERSION}-curl php${PHP_VERSION}-zip php${PHP_VERSION}-intl \
      php${PHP_VERSION}-gd php${PHP_VERSION}-bcmath php${PHP_VERSION}-dev php-pear \
 && rm -rf /var/lib/apt/lists/*

# Voz no Telegram: transcrição local (faster-whisper) e fala (edge-tts)
RUN pip3 install --no-cache-dir --break-system-packages faster-whisper edge-tts pyyaml

# GitHub CLI (integração do painel com o GitHub via GH_TOKEN)
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update && apt-get install -y --no-install-recommends gh && rm -rf /var/lib/apt/lists/*

# Composer
RUN curl -fsSL https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Node.js LTS + Claude Code
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/* \
 && npm install -g @anthropic-ai/claude-code

# Navegador para o Jarvis (Playwright MCP oficial da Microsoft + Chromium headless)
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
RUN npm install -g @playwright/mcp@latest \
 && D="$(npm root -g)/@playwright/mcp" \
 && node "$(dirname "$(node -p "require.resolve('playwright-core/package.json',{paths:['$D']})")")/cli.js" install --with-deps chromium \
 && chmod -R a+rX /opt/ms-playwright \
 && printf '#!/bin/sh\nD="$(npm root -g)/@playwright/mcp"\nexec node "$D/cli.js" --headless --isolated --browser chromium --no-sandbox --output-dir /tmp/playwright-mcp "$@"\n' > /usr/local/bin/jarvis-playwright-mcp \
 && chmod 755 /usr/local/bin/jarvis-playwright-mcp

# VS Code no navegador (acesso web)
RUN curl -fsSL https://code-server.dev/install.sh | sh

# (Opcional) Extensões PHP para SQL Server — habilite com INSTALL_SQLSRV=true
RUN if [ "$INSTALL_SQLSRV" = "true" ]; then \
      curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg && \
      echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/ubuntu/24.04/prod noble main" > /etc/apt/sources.list.d/mssql.list && \
      apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18 mssql-tools18 unixodbc-dev && \
      pecl install sqlsrv pdo_sqlsrv && \
      echo "extension=sqlsrv.so" > /etc/php/${PHP_VERSION}/cli/conf.d/30-sqlsrv.ini && \
      echo "extension=pdo_sqlsrv.so" > /etc/php/${PHP_VERSION}/cli/conf.d/30-pdo_sqlsrv.ini && \
      rm -rf /var/lib/apt/lists/*; \
    fi

# Usuário sem root (o modo autônomo do Claude Code não roda como root). Pode usar sudo DENTRO do contêiner.
RUN useradd -m -s /bin/bash dev && echo "dev ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/dev \
 # pastas dos volumes já pertencendo ao dev (senão o Docker cria como root e o login não é salvo)
 && mkdir -p /home/dev/.claude /home/dev/.cache /home/dev/.local/share/code-server /workspace && chown -R dev:dev /home/dev /workspace

# Jarvis embutido (copiado do repositório no momento do build)
COPY --chown=dev:dev . /opt/jarvis
RUN rm -rf /opt/jarvis/.git /opt/jarvis/container

COPY --chown=dev:dev container/primeiro-uso.sh /usr/local/bin/primeiro-uso
COPY --chown=dev:dev container/jarvis-extras.sh /usr/local/bin/jarvis-extras
COPY --chown=dev:dev container/telegram-bot/ /opt/jarvis-bots/
RUN install -m 755 /opt/jarvis-bots/jarvis-busca /usr/local/bin/jarvis-busca
RUN chmod +x /usr/local/bin/primeiro-uso /usr/local/bin/jarvis-extras \
 && echo 'alias jarvis-auto="claude --dangerously-skip-permissions"' >> /home/dev/.bashrc \
 && echo '[ -f ~/.jarvis-ok ] || echo ">> Primeira vez? Rode: primeiro-uso"' >> /home/dev/.bashrc

USER dev
WORKDIR /workspace
CMD ["sleep", "infinity"]
