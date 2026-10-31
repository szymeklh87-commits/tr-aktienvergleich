"""Frei wählbare Gewinnmitnahme: +30 %, +50 %, +100 % oder eigener Wert, ganz oder gestaffelt (Abschnitt 31.7).

* Die Schwelle bezieht sich auf **meine virtuelle Position** seit ihrem tatsächlichen simulierten Einstieg – nicht auf die
  Kursentwicklung der Aktie in einem Rankingfenster.
* Basis „nach_kosten“ (Standard): ``100 × (geschätzter EUR-Erlös nach Verkaufskosten − zugeordnete EUR-Anschaffungskosten
  inkl. Kaufkosten) / zugeordnete Anschaffungskosten``, vor Steuern. Unbekannter oder nicht positiver Einstand → nicht prüfbar
  (kein Verkauf). Basis „kurs“: ``100 × (Schlusskurs / Ø Einstandskurs − 1)`` in Notierungswährung, splitbereinigt.
* Geprüft wird zum Tagesschluss (Tagesdaten): Ein kurzer Anstieg während des Tages, der zum Prüfzeitpunkt nicht mehr besteht,
  löst nichts aus. Ausgeführt wird nach dem Ausführungsprofil – zum dann verfügbaren Kurs, nicht exakt zur Schwelle.
* Leiter: erfüllte, noch offene Stufen werden zusammen verarbeitet (Kurs springt über mehrere Stufen), jede Stufe genau einmal;
  Anteile beziehen sich auf die **ursprüngliche** Stückzahl der Position oder auf die jeweils **verbleibende** Menge. Die letzte
  Stufe, mit der 100 % der ursprünglichen Menge erreicht sind, verkauft den ganzen Rest. Bezug „ursprünglich“: Zielmenge nach
  Stufe i = ⌊ursprünglich × Summe der Anteile bis i⌋ – ergibt eine Stufe weniger als ein ganzes Stück, gilt sie als erledigt
  und ihr Anteil geht in die nächste Stufe ein (keine verlorenen Reste, kein tägliches Neuauslösen).
* Gewinnmitnahmen sind freiwillige Verkäufe: Schutzstops und Risikoverkäufe gehen immer vor; ein offenes Gewinnziel verhindert
  kein notwendiges Schließen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Stufenzustand:
    """Gespeicherter Zustand der Gewinnmitnahme einer Position (eine Position = von Eröffnung bis vollständigem Verkauf)."""

    urspruenglich: float
    erledigt: list[int] = field(default_factory=list)  # ausgeführte bzw. übersprungene Stufen
    offen: dict[str, str] = field(default_factory=dict)  # Stufe → Order-ID (beauftragt, noch nicht ausgeführt)
    uebersprungen: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"urspruenglich": self.urspruenglich, "erledigt": sorted(self.erledigt), "offen": dict(self.offen),
                "uebersprungen": sorted(self.uebersprungen)}

    @staticmethod
    def from_dict(data: dict | None, qty: float) -> "Stufenzustand":
        if not data:
            return Stufenzustand(float(qty))
        return Stufenzustand(float(data.get("urspruenglich", qty)), [int(x) for x in data.get("erledigt", [])],
                             {str(k): str(v) for k, v in (data.get("offen") or {}).items()}, [int(x) for x in data.get("uebersprungen", [])])


def gewinn_nach_kosten_pct(qty: float, cost_eur: float | None, price_eur: float | None, *, sell_price_factor: float, fee_eur: float) -> float | None:
    """Geschätzter liquidierbarer Gewinn in % der zugeordneten Anschaffungskosten (vor Steuern)."""
    if cost_eur is None or not (cost_eur > 0) or price_eur is None or not math.isfinite(price_eur) or qty <= 0:
        return None
    proceeds = qty * price_eur * sell_price_factor - fee_eur
    return 100.0 * (proceeds - cost_eur) / cost_eur


def kursgewinn_pct(avg_entry_local: float | None, close_local: float | None) -> float | None:
    if avg_entry_local is None or close_local is None or not (avg_entry_local > 0) or not math.isfinite(close_local):
        return None
    return 100.0 * (close_local / avg_entry_local - 1.0)


@dataclass(frozen=True)
class Faelligkeit:
    stufen: tuple[str, ...]  # „ganz“ oder Stufennummern als Text
    stueck: int
    grund: str
    uebersprungen: tuple[int, ...] = ()


def faellig(regel_gm: dict | None, zustand: Stufenzustand, held: float, gewinn: float | None) -> Faelligkeit | None:
    """Fällige Gewinnmitnahme oder None. ``held`` = verwaltete Stückzahl der Position für diese Regel."""
    if not regel_gm or held < 1 or gewinn is None:
        return None
    pending = set(zustand.offen)
    if regel_gm["art"] == "ganz":
        if "ganz" in pending or 0 in zustand.erledigt:
            return None
        if gewinn + 1e-12 < regel_gm["schwelle_pct"]:
            return None
        u = regel_gm["umfang"]
        if u["art"] == "alles":
            qty = int(math.floor(held + 1e-9))
        elif u["art"] == "anteil":
            qty = int(math.floor(held * u["pct"] / 100.0 + 1e-9))
        else:
            qty = int(min(held, u["stueck"]))
        if qty < 1:
            return Faelligkeit(("ganz",), 0, f"Gewinn {gewinn:.1f} % ≥ {regel_gm['schwelle_pct']:g} %, aber weniger als ein ganzes Stück – übersprungen", (0,))
        return Faelligkeit(("ganz",), qty, f"Gewinnmitnahme: Position {gewinn:.1f} % im Plus (Schwelle {regel_gm['schwelle_pct']:g} %, Basis {_basis(regel_gm)})")
    # Leiter
    stufen = regel_gm["stufen"]
    due = [i for i, s in enumerate(stufen) if i not in zustand.erledigt and str(i) not in pending and gewinn + 1e-12 >= s["schwelle_pct"]]
    if not due:
        return None
    total = 0
    skipped: list[int] = []
    taken: list[int] = []
    if regel_gm["bezug"] == "urspruenglich":
        # Zielmenge nach Stufe i = ⌊ursprünglich × Σ Anteile bis i⌋ (bei 100 %: alles); bereits verkauft = ursprünglich − gehalten.
        # So gehen Rundungsreste übersprungener Stufen nicht verloren, und dieselben Stücke werden nie zweimal verkauft.
        sold = max(0.0, zustand.urspruenglich - held)
        for i in due:
            cum = sum(stufen[j]["anteil_pct"] for j in range(i + 1))
            target = zustand.urspruenglich if cum >= 100.0 - 1e-9 else math.floor(zustand.urspruenglich * cum / 100.0 + 1e-9)
            qty = int(max(0.0, math.floor(min(target - sold - total, held - total) + 1e-9)))
            if qty < 1:
                skipped.append(i)
                continue
            total += qty
            taken.append(i)
    else:
        remaining = float(held)
        for i in due:
            qty = int(math.floor(remaining * stufen[i]["anteil_pct"] / 100.0 + 1e-9))
            if qty < 1:
                skipped.append(i)
                continue
            total += qty
            remaining -= qty
            taken.append(i)
    if total < 1:
        return Faelligkeit(tuple(str(i) for i in skipped), 0, "Gewinnstufe erreicht, aber weniger als ein ganzes Stück – Anteil geht in die nächste Stufe ein", tuple(skipped))
    labels = ", ".join(f"+{stufen[i]['schwelle_pct']:g} %" for i in taken)
    return Faelligkeit(tuple(str(i) for i in taken), total,
                       f"Gewinnleiter: Position {gewinn:.1f} % im Plus – Stufe {labels} ({'ursprüngliche' if regel_gm['bezug'] == 'urspruenglich' else 'verbleibende'} Menge, Basis {_basis(regel_gm)})",
                       tuple(skipped))


def _basis(regel_gm: dict) -> str:
    return "nach Kosten" if regel_gm.get("basis", "nach_kosten") == "nach_kosten" else "Kurs"


def gewinn_fuer_regel(regel_gm: dict | None, *, qty: float, cost_eur: float | None, price_eur: float | None, avg_entry_local: float | None,
                      close_local: float | None, sell_price_factor: float, fee_eur: float) -> float | None:
    if not regel_gm:
        return None
    if regel_gm.get("basis", "nach_kosten") == "kurs":
        return kursgewinn_pct(avg_entry_local, close_local)
    return gewinn_nach_kosten_pct(qty, cost_eur, price_eur, sell_price_factor=sell_price_factor, fee_eur=fee_eur)
