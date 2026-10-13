"""Fehlgeschlagene Tests als GitHub-Hinweise (Annotations) ausgeben.

Aufruf im Workflow „Prüfung“ nach einem roten Testschritt:

    python tests/ci_zusammenfassung.py test-ausgabe.txt

Liest die Ausgabe von ``python -m unittest -v`` und meldet je fehlgeschlagenem Test eine
``::error``-Zeile mit Testname und dem Ende der Fehlermeldung. So steht der Grund direkt in der
Zusammenfassung des Laufs, ohne das ganze Protokoll öffnen zu müssen.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_HINWEISE = 10  # GitHub zeigt je Schritt höchstens zehn Fehler-Hinweise an
MAX_ZEILEN = 14


def _escape_data(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(text: str) -> str:
    return _escape_data(text).replace(":", "%3A").replace(",", "%2C")


def failures(output: str) -> list[tuple[str, str]]:
    """(Kopfzeile, Fehlermeldung) je FAIL/ERROR-Block der unittest-Ausgabe."""
    blocks = re.split(r"^={50,}\s*$", output, flags=re.MULTILINE)
    found = []
    for block in blocks:
        block = block.strip("\n")
        match = re.match(r"^(FAIL|ERROR): (.+)$", block, flags=re.MULTILINE)
        if not match:
            continue
        body = block[match.end():]
        body = re.split(r"^-{50,}\s*$", body, maxsplit=1, flags=re.MULTILINE)[-1]
        body = re.split(r"^-{50,}\s*$\n^Ran \d+ tests?", body, flags=re.MULTILINE)[0]
        lines = [line for line in body.strip("\n").splitlines() if line.strip()]
        found.append((f"{match.group(1)}: {match.group(2)}", "\n".join(lines[-MAX_ZEILEN:])))
    return found


def main(path: str) -> int:
    file = Path(path)
    if not file.exists():
        print(f"::error::Testausgabe {path} fehlt – der Testschritt ist vor den Tests abgebrochen.")
        return 0
    output = file.read_text(encoding="utf-8", errors="replace")
    found = failures(output)
    if not found:
        tail = "\n".join(output.strip().splitlines()[-MAX_ZEILEN:])
        print(f"::error title=Tests abgebrochen::{_escape_data(tail)}")
        return 0
    for title, message in found[:MAX_HINWEISE]:
        print(f"::error title={_escape_property(title[:200])}::{_escape_data(message)}")
    if len(found) > MAX_HINWEISE:
        print(f"::error::Weitere {len(found) - MAX_HINWEISE} fehlgeschlagene Tests – siehe Protokoll")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "test-ausgabe.txt"))
