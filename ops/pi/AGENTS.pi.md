# Umgebung
- Pi läuft in einer Claude-Code-Cloud-VM (Ubuntu, Node 22). Die VM ist vorübergehend: alles außerhalb des Repos geht verloren.
- Ausgehender Netzverkehr nur über die Allowlist der Cloud-Umgebung; gesperrte Hosts nicht umgehen.

# Arbeitsweise
- Antworte auf Deutsch, knapp. Code schlank, ohne Platzhalter.
- Vor Änderungen Datei lesen, dann gezielt editieren statt neu schreiben.
- Nach jeder Änderung die passenden Tests ausführen (Python: `PYTHONPATH=backend python -m unittest discover -s tests/unit -t .`, App: `cd app && npm run typecheck && npm test`); Fehler bis zur Ursache verfolgen und beheben.
- Keine Passwörter, API-Keys oder Tokens in Code, Commits oder Ausgaben.
- Nie auf `main` pushen, nie `git push --force`. Änderungen auf einem eigenen Zweig, Push nur nach Rückfrage.
