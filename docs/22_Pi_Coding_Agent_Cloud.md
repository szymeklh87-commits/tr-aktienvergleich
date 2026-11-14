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
| ChatGPT-Abo (Plus/Pro) | im Abo enthalten | gesperrt | `auth.openai.com` und `chatgpt.com` freigeben, dann `pi auth login openai --no-browser` (Gerätecode; Einstellung „Gerätecode-Autorisierung für Codex“ in ChatGPT → Sicherheit muss an sein) |
| OpenRouter, Modelle mit `:free` | kostenlos, eng begrenzt | gesperrt | `openrouter.ai` freigeben, kostenlosen Schlüssel anlegen (ungeprüft in dieser Umgebung) |
| Gemini API (AI Studio) | kostenloses Kontingent; Eingaben dürfen von Google zur Verbesserung genutzt werden | gesperrt | `generativelanguage.googleapis.com` freigeben, kostenlosen Schlüssel anlegen (ungeprüft) |
| GitHub Copilot Free | kostenlos, begrenzt | gesperrt | Anmeldung läuft über github.com; der GitHub-Proxy der Cloud lässt nur freigegebene Repositories durch – voraussichtlich nicht nutzbar |
| Claude-Abo in Pi | nicht im Abo: Drittanbieter-Nutzung läuft über Zusatzkontingent bzw. kostenpflichtige Extra-Nutzung | erreichbar | **nicht eingerichtet** |
| Amazon Bedrock | – | gesperrt | Die VM setzt AWS-Variablen der Cloud-Infrastruktur (nicht deine). Der Pi-Starter entfernt sie, Pi bietet Bedrock daher nicht an |

**Freischalten (nur durch dich):** claude.ai/code → Umgebung bearbeiten → Network access **Limited** → zusätzliche Domains eintragen → **Allow package managers** eingeschaltet lassen (sonst kann der Hook Pi nicht über npm installieren). Am 14.11.2026, 13:10 Uhr war eine Freigabe in der laufenden Sitzung noch nicht wirksam (`auth.openai.com`: Tunnel abgelehnt); danach eine neue Sitzung starten und mit `status` prüfen. Schlüssel nie in die Umgebungsvariablen oder ins Repository, sondern als **Network secret** der Umgebung.

## Prüfen

```bash
bash ops/pi/test-cloud-setup.sh                  # Setup-Skript ohne Netz (12 Prüfungen)
bash ops/pi/cloud-setup.sh status                 # Netz und Anmeldung je Anbieter
node ops/pi/selbsttest.mjs                        # Prüfmodell (lokal, ohne KI)
node ops/pi/selbsttest.mjs --modell openai/<id>   # echtes Modell nach Anmeldung
```

Das **Prüfmodell** ist eine lokale OpenAI-kompatible Gegenstelle mit festem Ablauf, kein KI-Modell. Es prüft, dass Pi seine Werkzeuge wirklich ausführt: Dateien schreiben, Test laufen lassen (schlägt absichtlich fehl), Datei lesen, gezielt editieren, Test erneut (grün). Danach prüft das Skript das Ergebnis unabhängig. Ergebnis am 14.11.2026: bestanden. Mit echtem Modell noch nicht geprüft, weil kein Anbieter erreichbar ist.

## Testergebnisse 14.11.2026

| Prüfung | Ergebnis |
|---|---|
| `bash ops/pi/test-cloud-setup.sh` | 12/12 bestanden; Gegenprobe: ohne `x-deny-reason`-Erkennung schlagen 2 Prüfungen fehl |
| `node ops/pi/selbsttest.mjs` (Prüfmodell) | bestanden |
| Selbsttest mit OpenAI-Modell | **offen** – `auth.openai.com` und `chatgpt.com` in der Sitzung noch gesperrt |
| App: `npm ci`, `typecheck`, `npm test`, Build = `app/dist` | bestanden (157 bestanden, 27 übersprungen; `dist` identisch) |
| Sperrdatei (saubere venv) | in Ordnung (28 Bibliotheken) |
| Abhängigkeiten gegen OSV | ungeprüft: OSV aus der Cloud-VM gesperrt; läuft in der GitHub-CI |
| Python-Suite `unittest discover -s tests` | 1160 Tests: 1135 bestanden, 24 übersprungen, **1 fehlgeschlagen** (`test_no_word_or_number_breaks_inside_at_normal_font_size`) – schlägt ebenso auf unverändertem `main` fehl; Ursache: andere Standardschrift in der Cloud-VM (Inter statt der Schriften des CI-Runners). Der PR ändert App, Backend und Tests nicht; in der GitHub-CI grün |

