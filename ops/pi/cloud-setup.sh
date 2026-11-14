#!/bin/bash
# Pi Coding Agent in Claude-Code-Cloud-Sitzungen bereitstellen.
# Läuft als SessionStart-Hook (.claude/settings.json); außerhalb der Cloud ohne Wirkung.
#   bash ops/pi/cloud-setup.sh          Pi installieren/konfigurieren, Kurzstatus
#   bash ops/pi/cloud-setup.sh status   Anbieter-Erreichbarkeit und Anmeldungen prüfen
# Enthält keine Zugangsdaten. Anmeldungen liegen nur in ~/.pi/agent/auth.json der jeweiligen VM.

PI_PAKET="@earendil-works/pi-coding-agent"
PI_VERSION="${PI_VERSION:-1.5.2}"        # geprüfte Version; PI_VERSION=latest für die neueste
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AG="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"

status() {
  echo "Pi: $(pi --version 2>/dev/null || echo 'nicht installiert')"
  # Host  Anbieter-ID  Bezeichnung
  while read -r host id name; do
    kopf=$(curl -s -o /dev/null -D - -w 'CODE:%{http_code}' -m 6 "https://$host/" 2>/dev/null)
    if grep -q 'CODE:000' <<<"$kopf" || grep -qi '^x-proxy-error' <<<"$kopf"; then
      netz="gesperrt (Netzwerk-Allowlist)"; else netz="erreichbar"; fi
    pi auth check --provider "$id" >/dev/null 2>&1 && anm="angemeldet" || anm="nicht angemeldet"
    printf '  %-34s %-26s %s\n' "$name" "$netz" "$anm"
  done <<'EOF'
chatgpt.com openai ChatGPT-Abo (Sign in with ChatGPT)
api.individual.githubcopilot.com github-copilot GitHub Copilot (Free)
openrouter.ai openrouter OpenRouter (:free-Modelle)
generativelanguage.googleapis.com google Gemini API (Gratis-Kontingent)
EOF
}

[ "${1:-}" = status ] && { status; exit 0; }
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || [ "${PI_SETUP_FORCE:-}" = 1 ] || exit 0

# 1) Installieren (nur wenn Version abweicht)
if [ "$(pi --version 2>/dev/null)" != "$PI_VERSION" ] || [ "$PI_VERSION" = latest ]; then
  npm install -g --ignore-scripts --no-fund --no-audit "$PI_PAKET@$PI_VERSION" >/dev/null 2>&1 \
    || { echo "Pi: Installation fehlgeschlagen (npm)"; exit 0; }
fi

# Die VM setzt AWS-Variablen der Cloud-Infrastruktur (nicht deine). Pi würde damit Amazon Bedrock
# anbieten; der Starter entfernt sie, damit Pi nur eigene Anmeldungen nutzt.
BIN="$(npm prefix -g)/bin/pi"
CLI="$(npm root -g)/$PI_PAKET/dist/bundle/cli.js"
if [ -f "$CLI" ] && ! grep -q PI-SETUP "$BIN" 2>/dev/null; then
  rm -f "$BIN"
  printf '#!/bin/sh\n# PI-SETUP\nexec env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN -u AWS_PROFILE node "%s" "$@"\n' "$CLI" > "$BIN"
  chmod 755 "$BIN"
fi

# 2) Einstellungen zusammenführen (vorhandene Werte bleiben)
mkdir -p "$AG"
node -e '
  const fs=require("fs"),f=process.argv[1];let s={};try{s=JSON.parse(fs.readFileSync(f))}catch{}
  s.defaultThinkingLevel??="medium";
  s.defaultTools??=["read","bash","edit","write"];
  s.retry={enabled:true,maxRetries:3,baseDelayMs:2000,maxAgentDelayMs:60000,...(s.retry||{})};
  s.compaction={enabled:true,...(s.compaction||{})};
  s.enableAnalytics??=false;
  fs.writeFileSync(f,JSON.stringify(s,null,2)+"\n");' "$AG/settings.json"
cp "$HIER/AGENTS.pi.md" "$AG/AGENTS.md"

echo "Pi $(pi --version 2>/dev/null) bereit. Anbieter prüfen: bash ops/pi/cloud-setup.sh status"
exit 0
