#!/usr/bin/env bash
# Liga os "ajudantes": outras IAs (Gemini, Grok, OpenRouter, Groq) como mão de obra barata do Jarvis.
# Rode na VPS, dentro de container/:   ./ajudantes-configurar.sh
# As chaves ficam só em .env.ajudantes (fora do Git, permissão 600). Enter = mantém a atual / pula.
set -euo pipefail
cd "$(dirname "$0")"
ARQ=.env.ajudantes
touch "$ARQ"; chmod 600 "$ARQ"
atual() { grep -E "^$1=" "$ARQ" 2>/dev/null | tail -1 | cut -d= -f2- || true; }
gravar() {
  local tmp; tmp="$(mktemp)"; { grep -vE "^$1=" "$ARQ" 2>/dev/null || true; } > "$tmp"
  [ -n "$2" ] && printf '%s=%s\n' "$1" "$2" >> "$tmp"
  cat "$tmp" > "$ARQ"; rm -f "$tmp"; chmod 600 "$ARQ"
}

echo "== Ajudantes do Jarvis =="
echo "Gemini, Groq, Mistral e OpenRouter fazem tarefas de TEXTO (rascunhos, traduções, SEO, resumos, ideias) para economizar o Claude."
echo "Antes de enviar, o Jarvis apaga e-mails, telefones, CPF, tokens e senhas. Mesmo assim:"
echo "planos gratuitos costumam usar o conteúdo para treinar os modelos. Não use contas com dados sensíveis."
echo

pedir() { # pedir VAR "Nome" "onde pegar"
  local v; v="$(atual "$1")"
  echo "• $2 — chave em: $3"
  if [ -n "$v" ]; then echo "  (já configurada: ...${v: -4}; Enter mantém, digite - para remover)"; fi
  read -r -s -p "  Chave: " nova; echo
  if [ "$nova" = "-" ]; then gravar "$1" ""; echo "  removida"
  elif [ -n "$nova" ]; then gravar "$1" "$nova"; echo "  gravada"; fi
}
pedir GEMINI_API_KEY "Google Gemini (plano grátis)" "https://aistudio.google.com/apikey"
pedir GROQ_API_KEY "Groq (plano grátis, muito rápido)" "https://console.groq.com/keys"
pedir MISTRAL_API_KEY "Mistral (plano grátis Experiment, sem cartão)" "https://console.mistral.ai/api-keys"
pedir OPENROUTER_API_KEY "OpenRouter (modelos :free)" "https://openrouter.ai/keys"
if [ -n "$(atual XAI_API_KEY)" ]; then
  read -r -p "• Grok: a conta precisa de crédito. Remover a chave do Grok? [S/n] " r
  case "${r:-s}" in [sS]*) gravar XAI_API_KEY ""; echo "  removida";; esac
fi

ordem="$(atual JARVIS_AJUDANTES)"; ordem="${ordem:-gemini,groq,mistral,openrouter}"
case ",$ordem," in *,mistral,*) ;; *) ordem="$(echo "$ordem" | sed 's/grok/mistral/')"; case ",$ordem," in *,mistral,*) ;; *) ordem="$ordem,mistral";; esac;; esac
read -r -p "Ordem de preferência [$ordem]: " o; gravar JARVIS_AJUDANTES "${o:-$ordem}"

echo; echo "→ Recriando os contêineres para lerem as chaves…"
docker compose --profile web --profile telegram up -d --force-recreate jarvisweb telegram >/dev/null
docker compose up -d --force-recreate dev >/dev/null 2>&1 || true
echo "→ Testando cada ajudante (até 45 s cada; as chaves já estão gravadas, Ctrl+C pula o teste)…"
timeout 400 docker compose --profile telegram exec -T -e JARVIS_AJUDANTE_TIMEOUT=45 telegram python3 -u - <<'PY' || echo "  (teste interrompido ou demorou demais: confira depois com /ajudantes no Telegram)"
import sys; sys.path.insert(0, "/opt/jarvis-bots")
import ajudantes as a
a.liberar()  # chaves podem ter mudado: começa sem pausas antigas
if not a.configurados():
    print("  nenhuma chave configurada")
for n in a.configurados():
    print(f"  {n}: testando…", flush=True)
    r = a.perguntar("Responda só: ok", ia=n, maximo=300)
    print(f"  {n}: {'✅ ' + r['modelo'] if r['ok'] else '❌ ' + '; '.join(r.get('tentativas', []))[:200]}", flush=True)
PY
echo; echo "Pronto. No Telegram: /ajudantes (situação) · /ajudante <tarefa> (pedido direto)."
