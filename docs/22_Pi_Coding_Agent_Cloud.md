# Pi Coding Agent in Claude-Code-Cloud-Sitzungen

Stand 14.11.2026, Pi 1.5.2 (`@earendil-works/pi-coding-agent`). Werkzeug für die Entwicklung, kein Teil der App.

## Was eingerichtet ist

| Datei | Zweck |
|---|---|
| `.claude/settings.json` | SessionStart-Hook: führt bei jedem Start/Fortsetzen einer Cloud-Sitzung `ops/pi/cloud-setup.sh` aus |
| `ops/pi/cloud-setup.sh` | installiert Pi (nur in der Cloud, `CLAUDE_CODE_REMOTE=true`), setzt Einstellungen, `status` prüft Anbieter |
| `ops/pi/AGENTS.pi.md` | Arbeitsregeln für Pi (Deutsch, gezielt editieren, Tests ausführen, kein Push auf `main`) |
| `ops/pi/selbsttest.mjs` | Programmieraufgabe mit Tests und unabhängiger Nachprüfung |
| `ops/pi/test-cloud-setup.sh` | Test des Setup-Skripts ohne Netz (Sperr-Erkennung, globale `AGENTS.md`) |

Keine Zugangsdaten im Repository. Anmeldungen liegen nur in `~/.pi/agent/auth.json` der jeweiligen VM.

Die globale `~/.pi/agent/AGENTS.md` wird nicht überschrieben: Das Skript pflegt nur einen markierten Block (`<!-- pi-setup:start … -->` bis `<!-- pi-setup:end -->`); eigener Inhalt davor und danach bleibt erhalten.

## Was dauerhaft ist – und was nicht

- **Dauerhaft:** die Konfiguration im Repository. Jede neue Cloud-Sitzung mit diesem Repository installiert Pi automatisch (ca. 10 s).
- **Nicht dauerhaft:** die VM selbst. Sie pausiert nach wenigen Minuten ohne Aktivität und wird später verworfen. Anmeldungen bei Modellanbietern gehen damit verloren und sind je Sitzung neu nötig.
- **Pi Pocket als dauerhaft erreichbare Weboberfläche ist hier nicht möglich:** Die VM nimmt keine Verbindungen von außen an und läuft nicht durchgehend. Kostenlos dauerhaft geht nur auf einem eigenen, durchgehend laufenden Gerät (PC oder Handy) mit `npm start -- --access tailscale` (Tailscale-Privattarif kostenlos).

## Modellanbindung

Die Netzwerkstufe **Limited** lässt nur Paketquellen und weitere voreingestellte Domains zu und sperrt damit alle Modellanbieter außer Anthropic. Prüfung: `bash ops/pi/cloud-setup.sh status`. Als gesperrt gilt ein Host nur bei Zeichen des Cloud-Proxys: abgelehnter Tunnel, HTTP 403 mit `x-deny-reason` (z. B. `host_not_allowed`) oder `x-proxy-error`. Ein 403 des Zielservers selbst (Bot-Schutz) zählt als erreichbar.

| Anbieter | Kosten | Netz (Limited) | Weg |
|---|---|---|---|
| ChatGPT-Abo (Plus/Pro) | im Abo enthalten | gesperrt | `auth.openai.com` und `chatgpt.com` freigeben, dann `pi auth login openai-codex --no-browser` → „Device code login“, Code unter auth.openai.com/codex/device eingeben (Anbieter `openai-codex` ruft `chatgpt.com/backend-api` auf; der Anbieter `openai` bräuchte zusätzlich `api.openai.com`; Einstellung „Gerätecode-Autorisierung für Codex“ in ChatGPT → Sicherheit muss an sein) |
| OpenRouter, Modelle mit `:free` | kostenlos, eng begrenzt | gesperrt | `openrouter.ai` freigeben, kostenlosen Schlüssel anlegen (ungeprüft in dieser Umgebung) |
| Gemini API (AI Studio) | kostenloses Kontingent; Eingaben dürfen von Google zur Verbesserung genutzt werden | gesperrt | `generativelanguage.googleapis.com` freigeben, kostenlosen Schlüssel anlegen (ungeprüft) |
| GitHub Copilot Free | kostenlos, begrenzt | gesperrt | Anmeldung läuft über github.com; der GitHub-Proxy der Cloud lässt nur freigegebene Repositories durch – voraussichtlich nicht nutzbar |
| Claude-Abo in Pi | nicht im Abo: Drittanbieter-Nutzung läuft über Zusatzkontingent bzw. kostenpflichtige Extra-Nutzung | erreichbar | **nicht eingerichtet** |
| Amazon Bedrock | – | gesperrt | Die VM setzt AWS-Variablen der Cloud-Infrastruktur (nicht deine). Der Pi-Starter entfernt sie, Pi bietet Bedrock daher nicht an |

**Freischalten (nur durch dich):** claude.ai/code → Umgebung bearbeiten → Network access **Limited** → zusätzliche Domains eintragen → **Allow package managers** eingeschaltet lassen (sonst kann der Hook Pi nicht über npm installieren). 
**Wo die Freigabe wirkt:** nur in **Claude-Code-Cloud-Sitzungen** (claude.ai/code oder Tab „Code“ der Claude-App), die mit der bearbeiteten Umgebung gestartet werden. Der Arbeitsbereich eines normalen Claude-Chats (`status` zeigt `Sitzung: claude_ai_chat, Umgebung: cloud_default`) hat eine feste Allowlist, die sich über die Umgebungseinstellungen nicht ändern lässt. Nachweis 14.11.2026, 14:15 Uhr, in einem solchen Chat-Arbeitsbereich: Das Gateway lehnt `CONNECT auth.openai.com:443` ab mit „no rule or allowlist entry allows host "auth.openai.com"“, ebenso `chatgpt.com` und als Gegenprobe `example.com`; `registry.npmjs.org` ist erlaubt. Schlüssel nie in die Umgebungsvariablen oder ins Repository, sondern als **Network secret** der Umgebung.

## Prüfen

```bash
bash ops/pi/test-cloud-setup.sh                  # Setup-Skript ohne Netz (13 Prüfungen)
bash ops/pi/cloud-setup.sh status                 # Netz und Anmeldung je Anbieter
node ops/pi/selbsttest.mjs                        # Prüfmodell (lokal, ohne KI)
node ops/pi/selbsttest.mjs --modell openai-codex/<id>   # echtes Modell nach Anmeldung (pi --list-models openai-codex)
```

Das **Prüfmodell** ist eine lokale OpenAI-kompatible Gegenstelle mit festem Ablauf, kein KI-Modell. Es prüft, dass Pi seine Werkzeuge wirklich ausführt: Dateien schreiben, Test laufen lassen (schlägt absichtlich fehl), Datei lesen, gezielt editieren, Test erneut (grün). Danach prüft das Skript das Ergebnis unabhängig. Ergebnis am 14.11.2026: bestanden. Mit echtem Modell noch nicht geprüft: Netz und Anmeldung funktionieren, das Codex-Kontingent war beim Test erschöpft (siehe unten).

## Testergebnisse 14.11.2026

| Prüfung | Ergebnis |
|---|---|
| `bash ops/pi/test-cloud-setup.sh` | 13/13 bestanden (inkl. Begründung des Gateways über Ersatz-Proxy); Gegenprobe: ohne `x-deny-reason`-Erkennung schlagen 2 Prüfungen fehl |
| `node ops/pi/selbsttest.mjs` (Prüfmodell) | bestanden |
| Selbsttest mit OpenAI-Modell | **offen** – im Chat-Arbeitsbereich gesperrt (siehe „Wo die Freigabe wirkt“). Nachtrag 14.11.2026, 14:20 Uhr, in einer Claude-Code-Cloud-Sitzung mit eigener Umgebung (`auth.openai.com`, `chatgpt.com` freigegeben): beide Hosts erreichbar, Gerätecode-Login `openai-codex` erfolgreich (`pi auth check` → `ready`). Modellaufruf scheitert mit „Codex error: The usage limit has been reached“ (Wochenkontingent des Abos zu 100 % verbraucht, Rücksetzung 15.11.2026, 10:51 Uhr); keine Credits gekauft. Selbsttest danach nachholen |
| App: `npm ci`, `typecheck`, `npm test`, Build = `app/dist` | bestanden (157 bestanden, 27 übersprungen; `dist` identisch) |
| Sperrdatei (saubere venv) | in Ordnung (28 Bibliotheken) |
| Abhängigkeiten gegen OSV | ungeprüft: OSV aus der Cloud-VM gesperrt; läuft in der GitHub-CI |
| Python-Suite `unittest discover -s tests` | 1160 Tests: 1135 bestanden, 24 übersprungen, **1 fehlgeschlagen** (`test_no_word_or_number_breaks_inside_at_normal_font_size`) – schlägt ebenso auf unverändertem `main` fehl; Ursache: andere Standardschrift in der Cloud-VM (Inter statt der Schriften des CI-Runners). Der PR ändert App, Backend und Tests nicht; in der GitHub-CI grün |

