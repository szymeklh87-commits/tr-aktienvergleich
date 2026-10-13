"""Testergebnis als GitHub-Hinweise (Annotations) ausgeben.

Aufruf im Workflow „Prüfung“ als letzter Schritt – immer, auch nach einem roten Testschritt:

    python tests/ci_zusammenfassung.py test-ausgabe.txt kalender-ausgabe.txt

Liest die Ausgabe von ``python -m unittest -v``. Je Datei erscheint ein Hinweis mit Zahl der Tests,
Ergebnis und den übersprungenen Tests samt Grund, und je fehlgeschlagenem Test eine Fehlermeldung
mit Testname und dem Ende der Meldung. So stehen Ergebnis und Fehlergrund direkt in der
Zusammenfassung des Laufs, ohne das Protokoll herunterzuladen. Eine fehlende Datei (der zugehörige
Schritt lief nicht) wird übergangen; der Fehler des früheren Schritts steht dann schon im Lauf.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
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


def outcome(output: str) -> tuple[str, str] | None:
    """(„Ran …“-Zeile, Ergebniszeile „OK …“/„FAILED …“) am Ende der Ausgabe, sonst None."""
    ran = re.findall(r"^Ran \d+ tests? in [\d.]+s\s*$", output, flags=re.MULTILINE)
    verdict = re.findall(r"^(?:OK|FAILED)(?: \(.*\))?\s*$", output, flags=re.MULTILINE)
    if not ran or not verdict:
        return None
    return ran[-1].strip(), verdict[-1].strip()


def skipped(output: str) -> Counter[str]:
    """Übersprungene Tests je Grund."""
    reasons = re.findall(r"\.\.\. skipped (['\"])(.*)\1\s*$", output, flags=re.MULTILINE)
    return Counter(reason for _, reason in reasons)


def report(path: Path) -> list[str]:
    """Workflow-Befehle (::notice/::error) für eine Testausgabe."""
    output = path.read_text(encoding="utf-8", errors="replace")
    label = path.stem
    result = outcome(output)
    found = failures(output)
    lines: list[str] = []
    if result is None:
        tail = "\n".join(output.strip().splitlines()[-MAX_ZEILEN:]) or "(keine Ausgabe)"
        lines.append(f"::error title={_escape_property(f'{label}: Tests abgebrochen')}::{_escape_data(tail)}")
    else:
        ran, verdict = result
        text = f"{ran} – {verdict}"
        for reason, count in sorted(skipped(output).items()):
            text += f"\nÜbersprungen: {count}× {reason}"
        lines.append(f"::notice title={_escape_property(label)}::{_escape_data(text)}")
    for title, message in found[:MAX_HINWEISE]:
        lines.append(f"::error title={_escape_property(title[:200])}::{_escape_data(message)}")
    if len(found) > MAX_HINWEISE:
        lines.append(f"::error::Weitere {len(found) - MAX_HINWEISE} fehlgeschlagene Tests – siehe Protokoll")
    return lines


def main(paths: list[str]) -> int:
    for name in paths:
        path = Path(name)
        if path.exists():
            print("\n".join(report(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["test-ausgabe.txt"]))
