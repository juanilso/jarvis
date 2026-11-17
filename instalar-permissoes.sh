#!/usr/bin/env bash
# Mescla as permissões recomendadas do Jarvis em ~/.claude/settings.json (global), com backup.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/settings.json"
mkdir -p "$HOME/.claude"
[ -f "$DEST" ] && cp "$DEST" "$DEST.bak.$(date +%Y%m%d%H%M%S)" && echo "Backup criado."
python3 - "$DIR/settings-recomendado.json" "$DEST" <<'PY'
import json, sys, os
src, dest = sys.argv[1], sys.argv[2]
new = json.load(open(src))
cur = json.load(open(dest)) if os.path.exists(dest) else {}
p = cur.setdefault("permissions", {})
for k in ("allow", "ask", "deny"):
    merged = list(dict.fromkeys(p.get(k, []) + new["permissions"].get(k, [])))
    p[k] = merged
p.setdefault("defaultMode", new["permissions"]["defaultMode"])
json.dump(cur, open(dest, "w"), indent=2, ensure_ascii=False)
print("Permissões do Jarvis aplicadas em", dest)
PY
