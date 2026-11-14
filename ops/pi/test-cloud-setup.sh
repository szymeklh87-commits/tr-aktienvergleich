#!/bin/bash
# Prüft ops/pi/cloud-setup.sh ohne Netz und ohne globale Änderungen (Ersatz für curl, pi, npm).
#   bash ops/pi/test-cloud-setup.sh
set -u
SKRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cloud-setup.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/agent"
fehler=0
pruef() { if [ "$2" = "$3" ]; then echo "  ok   $1"; else echo "  FEHL $1: erwartet '$3', erhalten '$2'"; fehler=$((fehler+1)); fi; }

# curl-Ersatz: Antwortköpfe je Host wie vom Cloud-Proxy bzw. Zielserver
cat > "$T/bin/curl" <<'EOF'
#!/bin/bash
for a; do u="$a"; done
case "$u" in
  https://deny.test/)     printf 'HTTP/1.1 403 Forbidden\r\nx-deny-reason: host_not_allowed\r\n\r\nCODE:403\n';;
  https://connect.test/)  printf 'HTTP/1.1 403 Forbidden\r\nX-Deny-Reason: host_not_allowed\r\n\r\nCODE:000\n';;
  https://proxyerr.test/) printf 'HTTP/1.1 200 Connection Established\r\n\r\nHTTP/1.1 403 Forbidden\r\nX-Proxy-Error: request blocked\r\n\r\nCODE:403\n';;
  https://tunnel.test/)   printf 'HTTP/1.1 403 Forbidden\r\n\r\nCODE:000\n';;
  https://bot403.test/)   printf 'HTTP/1.1 200 Connection Established\r\n\r\nHTTP/2 403\r\ncf-mitigated: challenge\r\n\r\nCODE:403\n';;
  *)                      printf 'HTTP/2 200\r\n\r\nCODE:200\n';;
esac
EOF
printf '#!/bin/sh\n[ "$1" = --version ] && echo 1.5.2\nexit 0\n' > "$T/bin/pi"
printf '#!/bin/sh\ncase "$1" in prefix) echo "%s/npm";; root) echo "%s/npm/lib";; esac\n' "$T" "$T" > "$T/bin/npm"
chmod +x "$T/bin/"*
export PATH="$T/bin:$PATH" PI_CODING_AGENT_DIR="$T/agent" PI_SETUP_FORCE=1 PI_VERSION=1.5.2
unset HTTPS_PROXY https_proxy

echo "Netz-Erkennung"
pruef "403 + x-deny-reason"            "$(bash "$SKRIPT" netz deny.test)"     "gesperrt (host_not_allowed)"
pruef "CONNECT 403 + X-Deny-Reason"    "$(bash "$SKRIPT" netz connect.test)"  "gesperrt (host_not_allowed)"
pruef "X-Proxy-Error"                  "$(bash "$SKRIPT" netz proxyerr.test)" "gesperrt (no rule allows host)"
pruef "Tunnel abgelehnt ohne Kopf"     "$(bash "$SKRIPT" netz tunnel.test)"   "gesperrt (Tunnel abgelehnt)"
pruef "403 des Zielservers = offen"    "$(bash "$SKRIPT" netz bot403.test)"   "erreichbar"
pruef "200"                            "$(bash "$SKRIPT" netz ok.test)"       "erreichbar"
# Ersatz-Proxy, der CONNECT wie das Cloud-Gateway mit Begründung ablehnt
node -e 'require("net").createServer(s=>s.once("data",()=>s.end("HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\nrequest blocked: no rule or allowlist entry allows host \"tunnel.test\"\n"))).listen(0,"127.0.0.1",function(){console.log(this.address().port)})' > "$T/port" &
PROXY_PID=$!; for _ in 1 2 3 4 5 6 7 8 9 10; do [ -s "$T/port" ] && break; sleep 0.2; done
pruef "Begründung des Gateways"        "$(HTTPS_PROXY="http://127.0.0.1:$(cat "$T/port")" bash "$SKRIPT" netz tunnel.test)" \
      'gesperrt (no rule or allowlist entry allows host "tunnel.test")'
kill "$PROXY_PID" 2>/dev/null

echo "Globale AGENTS.md"
A="$T/agent/AGENTS.md"; Q="$(dirname "$SKRIPT")/AGENTS.pi.md"
bloecke() { grep -c 'pi-setup:start' "$A"; }
bash "$SKRIPT" >/dev/null
pruef "fehlt -> Block angelegt" "$(bloecke)" "1"
printf '# Eigene Regeln\n- Nie löschen\n' > "$A"
bash "$SKRIPT" >/dev/null; bash "$SKRIPT" >/dev/null
pruef "eigener Inhalt bleibt"   "$(head -2 "$A" | tail -1)" "- Nie löschen"
pruef "zweimal -> ein Block"    "$(bloecke)" "1"
sed -i 's/^- Nie löschen$/- Nie löschen, geändert/' "$A"
bash "$SKRIPT" >/dev/null
pruef "Änderung bleibt"         "$(grep -c 'geändert' "$A")" "1"
cp "$Q" "$A"
bash "$SKRIPT" >/dev/null
pruef "alte Vollkopie ersetzt"  "$(bloecke):$(grep -c '^# Umgebung' "$A")" "1:1"
grep -q '"enableAnalytics": false' "$T/agent/settings.json"; pruef "settings.json geschrieben" "$?" "0"

echo; [ "$fehler" = 0 ] && echo "ALLE PRÜFUNGEN BESTANDEN" || { echo "$fehler FEHLGESCHLAGEN"; exit 1; }
