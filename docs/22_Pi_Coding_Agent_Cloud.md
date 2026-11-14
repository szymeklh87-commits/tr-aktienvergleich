# Pi Coding Agent in Claude-Code-Cloud-Sitzungen

Stand 14.11.2026, Pi 1.5.2 (`@earendil-works/pi-coding-agent`). Werkzeug für die Entwicklung, kein Teil der App.

## Was eingerichtet ist

| Datei | Zweck |
|---|---|
| `.claude/settings.json` | SessionStart-Hook: führt bei jedem Start/Fortsetzen einer Cloud-Sitzung `ops/pi/cloud-setup.sh` aus |
| `ops/pi/cloud-setup.sh` | installiert Pi (nur in der Cloud, `CLAUDE_CODE_REMOTE=true`), setzt Einstellungen, `status` prüft Anbieter |
| `ops/pi/AGENTS.pi.md` | Arbeitsregeln für Pi (Deutsch, gezielt editieren, Tests ausführen, kein Push auf `main`) |
| `ops/pi/selbsttest.mjs` | Programmieraufgabe mit Tests und unabhängiger Nachprüfung |

Keine Zugangsdaten im Repository. Anmeldungen liegen nur in `~/.pi/agent/auth.json` der jeweiligen VM.

## Was dauerhaft ist – und was nicht

- **Dauerhaft:** die Konfiguration im Repository. Jede neue Cloud-Sitzung mit diesem Repository installiert Pi automatisch (ca. 10 s).
- **Nicht dauerhaft:** die VM selbst. Sie pausiert nach wenigen Minuten ohne Aktivität und wird später verworfen. Anmeldungen bei Modellanbietern gehen damit verloren und sind je Sitzung neu nötig.
- **Pi Pocket als dauerhaft erreichbare Weboberfläche ist hier nicht möglich:** Die VM nimmt keine Verbindungen von außen an und läuft nicht durchgehend. Kostenlos dauerhaft geht nur auf einem eigenen, durchgehend laufenden Gerät (PC oder Handy) mit `npm start -- --access tailscale` (Tailscale-Privattarif kostenlos).

## Modellanbindung

Die Umgebung „Trusted“ sperrt alle Modellanbieter außer Anthropic (Prüfung: `bash ops/pi/cloud-setup.sh status`).

| Anbieter | Kosten | Netz (Trusted) | Weg |
|---|---|---|---|
| ChatGPT-Abo (Plus/Pro) | im Abo enthalten | gesperrt | Umgebung auf **Custom** mit `auth.openai.com` und `chatgpt.com`, dann `pi auth login openai --no-browser` (Gerätecode; Einstellung „Gerätecode-Autorisierung für Codex“ in ChatGPT → Sicherheit muss an sein) |
| OpenRouter, Modelle mit `:free` | kostenlos, eng begrenzt | gesperrt | `openrouter.ai` freigeben, kostenlosen Schlüssel anlegen (ungeprüft in dieser Umgebung) |
| Gemini API (AI Studio) | kostenloses Kontingent; Eingaben dürfen von Google zur Verbesserung genutzt werden | gesperrt | `generativelanguage.googleapis.com` freigeben, kostenlosen Schlüssel anlegen (ungeprüft) |
| GitHub Copilot Free | kostenlos, begrenzt | gesperrt | Anmeldung läuft über github.com; der GitHub-Proxy der Cloud lässt nur freigegebene Repositories durch – voraussichtlich nicht nutzbar |
| Claude-Abo in Pi | nicht im Abo: Drittanbieter-Nutzung läuft über Zusatzkontingent bzw. kostenpflichtige Extra-Nutzung | erreichbar | **nicht eingerichtet** |
| Amazon Bedrock | – | gesperrt | Die VM setzt AWS-Variablen der Cloud-Infrastruktur (nicht deine). Der Pi-Starter entfernt sie, Pi bietet Bedrock daher nicht an |

**Freischalten (nur durch dich):** claude.ai/code → Umgebung bearbeiten → Network access **Custom** → Domains eintragen → „Also include default list of common package managers“ anhaken. Schlüssel nie in die Umgebungsvariablen oder ins Repository, sondern als **Network secret** der Umgebung.

## Prüfen

```bash
bash ops/pi/cloud-setup.sh status                 # Netz und Anmeldung je Anbieter
node ops/pi/selbsttest.mjs                        # Prüfmodell (lokal, ohne KI)
node ops/pi/selbsttest.mjs --modell openai/<id>   # echtes Modell nach Anmeldung
```

Das **Prüfmodell** ist eine lokale OpenAI-kompatible Gegenstelle mit festem Ablauf, kein KI-Modell. Es prüft, dass Pi seine Werkzeuge wirklich ausführt: Dateien schreiben, Test laufen lassen (schlägt absichtlich fehl), Datei lesen, gezielt editieren, Test erneut (grün). Danach prüft das Skript das Ergebnis unabhängig. Ergebnis am 14.11.2026: bestanden. Mit echtem Modell noch nicht geprüft, weil kein Anbieter erreichbar ist.
