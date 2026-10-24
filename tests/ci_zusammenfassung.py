"""Testergebnis als GitHub-Hinweise (Annotations) ausgeben.

Aufruf im Workflow „Prüfung“ als letzter Schritt – immer, auch nach einem roten Testschritt:

    python tests/ci_zusammenfassung.py test-ausgabe.txt kalender-ausgabe.txt

Mit ``--einzeln`` (ab 1.18, Workflows „Datenquellen prüfen“ und „App mit echten Daten prüfen“) zusätzlich das Ergebnis
jedes einzelnen Tests – bestanden, übersprungen mit Grund oder nicht bestanden –, weil sich die Protokolle der Läufe hier
nicht herunterladen lassen und ein übersprungener Test nicht als bestanden gelten darf.

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


def ran_count(output: str) -> int | None:
    """Zahl der Tests aus der letzten Zeile „Ran N tests in …s“, sonst None."""
    found = re.findall(r"^Ran (\d+) tests? in [\d.]+s\s*$", output, flags=re.MULTILINE)
    return int(found[-1]) if found else None


def skipped(output: str) -> Counter[str]:
    """Übersprungene Tests je Grund."""
    reasons = re.findall(r"\.\.\. skipped (['\"])(.*)\1\s*$", output, flags=re.MULTILINE)
    return Counter(reason for _, reason in reasons)


STATUS_TEXT = {"ok": "bestanden", "FAIL": "fehlgeschlagen", "ERROR": "Fehler", "expected failure": "erwarteter Fehler", "unexpected success": "unerwartet bestanden"}


def _verdict(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("skipped"):
        return "übersprungen: " + raw[len("skipped") :].strip().strip("'\"")
    return STATUS_TEXT.get(raw, raw)


def results(output: str) -> list[tuple[str, str]]:
    """Ergebnis je Test aus der Ausgabe von ``unittest -v`` (ab 1.18): (Klasse.test, Ergebnis) mit „bestanden“,
    „übersprungen: Grund“, „fehlgeschlagen“ oder „Fehler“. Tests mit Beschreibung stehen in zwei Zeilen – erst der Name,
    dann die erste Zeile der Beschreibung mit dem Ergebnis.

    Die Kopfzeile eines Tests kann auch mitten in einer Zeile stehen: Ohne ungepufferte Ausgabe bleibt nach einem langen
    ``print`` (Bericht in ``tearDownModule``) der Zeilenumbruch im Puffer, und unittest schreibt den nächsten Test direkt
    dahinter (``}test_close_times_in_utc (…) ... ok`` im Lauf „Datenquellen prüfen“ vom 24.10.2026). Solche Köpfe werden
    an der Form ab Python 3.11 erkannt: ``name (paket.Klasse.name)``."""
    status = r"(ok|skipped (['\"]).*\2|FAIL|ERROR|expected failure|unexpected success)"
    head = re.compile(r"^(\w+) \(([\w.]+)\)(?: \.\.\. (.*))?$")
    glued = re.compile(r"(\w+) \(((?:\w+\.)+\1)\)(?: \.\.\. (.*))?$")  # Kopf mitten in der Zeile (Name wiederholt)
    alone = re.compile(rf"^{status}\s*$")  # Ergebnis allein in einer Zeile (nach Protokollzeilen des Tests)
    tail = re.compile(rf" \.\.\. {status}\s*$")
    found: list[tuple[str, str]] = []
    pending: str | None = None
    for line in output.splitlines():
        match = head.match(line) or glued.search(line)
        if match:
            parts = match.group(2).split(".")
            method = match.group(1)
            if len(parts) >= 2 and method.endswith(parts[-1]):  # Form ab Python 3.11: name (paket.Klasse.name)
                method, cls = parts[-1], parts[-2]  # Name aus der Kennung – ein davorgeklebter Rest zählt nicht
            else:  # ältere Form: name (paket.Klasse)
                cls = parts[-1]
            name = f"{cls}.{method}"
            rest = (match.group(3) or "").strip()
            known = alone.match(rest)
            if known:
                found.append((name, _verdict(known.group(1))))
                pending = None
            else:
                pending = name  # Beschreibung in der nächsten Zeile oder Protokollzeilen vor dem Ergebnis
            continue
        if pending:
            ending = tail.search(line) or alone.match(line.strip())
            if ending:
                found.append((pending, _verdict(ending.group(1))))
                pending = None
    return found


def report(path: Path, einzeln: bool = False) -> list[str]:
    """Workflow-Befehle (::notice/::error) für eine Testausgabe; ``einzeln``: zusätzlich ein Hinweis mit dem Ergebnis
    jedes einzelnen Tests (für die Live-Prüfungen, deren Protokoll sich nicht herunterladen lässt)."""
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
        # ab 1.18 mit den Namen der übersprungenen Tests (höchstens 12 je Grund)
        names: dict[str, list[str]] = {}
        for name, value in results(output):
            if value.startswith("übersprungen: "):
                names.setdefault(value[len("übersprungen: ") :], []).append(name)
        for reason, count in sorted(skipped(output).items()):
            listed = names.get(reason, [])
            shown = ", ".join(n.split(".", 1)[-1] for n in listed[:12]) + (f" und {len(listed) - 12} weitere" if len(listed) > 12 else "")
            text += f"\nÜbersprungen: {count}× {reason}" + (f" ({shown})" if listed else "")
        lines.append(f"::notice title={_escape_property(label)}::{_escape_data(text)}")
    if einzeln:
        each = results(output)
        total = ran_count(output)
        # Abgleich mit „Ran N tests“: Ein Test ohne eigenes Ergebnis wird genannt und nie als bestanden gezählt
        unassigned = (total - len(each)) if total is not None else 0
        if each or unassigned:
            counts = Counter("bestanden" if v == "bestanden" else "übersprungen" if v.startswith("übersprungen") else "nicht bestanden" for _, v in each)
            counts["ohne Einzelergebnis"] = max(unassigned, 0)
            summary = ", ".join(f"{k} {counts[k]}" for k in ("bestanden", "übersprungen", "nicht bestanden", "ohne Einzelergebnis") if counts[k])
            text = f"{total if total is not None else len(each)} Tests: {summary}\n" + "\n".join(f"{name} – {verdict}" for name, verdict in each)
            lines.append(f"::notice title={_escape_property(f'{label}: je Test')}::{_escape_data(text)}")
        if unassigned:
            text = (
                f"unittest meldet {total} Tests, einzeln zugeordnet {len(each)}. Nicht zugeordnete Tests zählen nicht als "
                "bestanden – Ergebnis nur über die Gesamtzeile des Laufs bekannt."
            )
            lines.append(f"::warning title={_escape_property(f'{label}: Ergebnis je Test unvollständig')}::{_escape_data(text)}")
    for title, message in found[:MAX_HINWEISE]:
        lines.append(f"::error title={_escape_property(title[:200])}::{_escape_data(message)}")
    if len(found) > MAX_HINWEISE:
        lines.append(f"::error::Weitere {len(found) - MAX_HINWEISE} fehlgeschlagene Tests – siehe Protokoll")
    return lines


def main(args: list[str]) -> int:
    einzeln = "--einzeln" in args
    paths = [a for a in args if a != "--einzeln"] or ["test-ausgabe.txt"]
    for name in paths:
        path = Path(name)
        if path.exists():
            print("\n".join(report(path, einzeln)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
