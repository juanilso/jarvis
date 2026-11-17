#!/usr/bin/env bash
# Configuração única dentro do contêiner: Git, login no Claude, plugin Jarvis e permissões.
set -e
echo "== Jarvis: primeira configuração =="

if ! git config --global user.name >/dev/null; then
  read -rp "Seu nome para os commits: " NOME
  read -rp "Seu e-mail do GitHub (pode ser o noreply): " EMAIL
  git config --global user.name "$NOME"
  git config --global user.email "$EMAIL"
  git config --global init.defaultBranch main
fi

echo
echo "1) Login no Claude: vai abrir um link para você autorizar no navegador."
echo "   Depois do login, digite /exit para voltar aqui."
read -rp "   Pressione Enter para continuar..."
claude || true

echo
echo "2) Instalando o plugin Jarvis (cópia local em /opt/jarvis)..."
claude plugin marketplace add /opt/jarvis || true
claude plugin install jarvis@jarvis-marketplace || true

echo
echo "3) Aplicando as permissões recomendadas..."
bash /opt/jarvis/instalar-permissoes.sh

touch ~/.jarvis-ok
cat <<'MSG'

Pronto! Como usar:
  cd /workspace/<seu-projeto>
  claude          -> modo normal (pede só o que está na lista "ask")
  jarvis-auto     -> modo totalmente autônomo (seguro aqui: só /workspace é compartilhado com o PC)
  /jarvis <ideia> -> dentro do Claude, para começar

Para atualizar o Jarvis: no PC, dê "git pull" na pasta do jarvis e rode "docker compose build".
MSG
