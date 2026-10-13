"""Vergleich mit den Regeln der Vorversion auf denselben Daten (Methodenwechsel transparent machen).

Ab tr-methode-1.7.0 gelten die im Auftrag vom 13.10.2026 dokumentierten Regeln des Ausgangsmodells
(TR-90D-11W-two-universes-v1.1): Volumen an jeder Beobachtung gemeldet, positives Volumen an Start
und Ende, gemeldeter Split im Fenster zurückgehalten, Gleichstand Score → Rendite → ISIN. Jeder Lauf
rechnet zusätzlich die Mengen und Spitzenplätze nach den Regeln der Vorversion (tr-methode-1.6.0) und
veröffentlicht die Unterschiede im Manifest – so ist sichtbar, was der Methodenwechsel an genau
diesem Datenstand verändert.
"""

from __future__ import annotations

import numpy as np

from ..config import CANONICAL_WEIGHTS, MethodConfig
from .codes import RETURN_PUBLISHABLE, Status
from .ranking import WindowRanking, group_b_ranking, rank_window

RULE_VOLUME_MISSING = 1
RULE_EDGE_VOLUME = 2
RULE_SPLIT = 4
MAX_EXAMPLES = 12


def compare_with_previous_rules(
    *,
    status: np.ndarray,
    previous_status: np.ndarray,
    rule_hits: np.ndarray,
    rankings: dict[int, WindowRanking],
    liquid: np.ndarray,
    r: np.ndarray,
    r2: np.ndarray,
    slope: np.ndarray,
    noise: np.ndarray,
    windows: tuple[int, ...],
    cfg: MethodConfig,
) -> dict:
    publishable = [int(s) for s in RETURN_PUBLISHABLE]
    new_v = np.isin(status, publishable)
    old_v = np.isin(previous_status, publishable)
    new_u = status == Status.TREND_BEWERTBAR
    old_u = previous_status == Status.TREND_BEWERTBAR
    dropped = old_v & ~new_v
    added = new_v & ~old_v  # nur theoretisch (die neuen Regeln sind strenger); wird mitgezählt

    compared = changed = 0
    examples: list[dict] = []
    for col, h in enumerate(windows):
        new = rankings[h]
        v_idx = np.nonzero(old_v[:, col])[0].astype(np.int64)
        u_idx = np.nonzero(old_u[:, col])[0].astype(np.int64)
        old = rank_window(h, v_idx, u_idx, r[:, col], r2[:, col], slope[:, col], noise[:, col], tie_rule="v1")
        old_b = group_b_ranking(old, liquid, r[:, col], r2[:, col], slope[:, col], noise[:, col], tie_rule="v1")
        pairs = [("A", 0, old.native0, new.native0)]
        pairs += [("A", w, old.trend[w], new.trend[w]) for w in CANONICAL_WEIGHTS if w > 0]
        if new.group_b is not None:
            pairs.append(("B", 0, old_b.native0, new.group_b.native0))
            pairs += [("B", w, old_b.trend[w], new.group_b.trend[w]) for w in CANONICAL_WEIGHTS if w > 0]
        for group, weight, before, after in pairs:
            if before.size == 0 and after.size == 0:
                continue
            compared += 1
            top_before = int(before.order[0]) if before.size else None
            top_after = int(after.order[0]) if after.size else None
            if top_before != top_after:
                changed += 1
                if len(examples) < MAX_EXAMPLES:
                    examples.append({"gruppe": group, "h": h, "w": weight, "vorher": top_before, "jetzt": top_after})

    def instruments_with(mask: np.ndarray) -> int:
        return int(np.count_nonzero(mask.any(axis=1))) if mask.size else 0

    return {
        "vorher": cfg.previous_method_version,
        "jetzt": cfg.method_version,
        "ausgangsmodell": cfg.reference_model,
        "regeln": [
            "Handelsvolumen an jeder Beobachtung des Fensters gemeldet (endlich, nicht negativ)",
            "Start- und Endbeobachtung mit positivem Handelsvolumen",
            "gemeldeter Split bzw. Zusammenlegung im Fenster: zurückgehalten (Freigabe nur nach dokumentierter Prüfung)",
            "Gleichstand: Score, dann Kursrendite, dann ISIN – für alle Gewichtungen",
        ],
        "paare": {
            "vorher_V": int(old_v.sum()),
            "jetzt_V": int(new_v.sum()),
            "vorher_U": int(old_u.sum()),
            "jetzt_U": int(new_u.sum()),
            "nicht_mehr_bewertet": int(dropped.sum()),
            "neu_bewertet": int(added.sum()),
            # Mehrfachnennung möglich: ein Fenster kann mehrere neue Regeln verletzen
            "grund": {
                "volumen_fehlt": int(np.count_nonzero(dropped & ((rule_hits & RULE_VOLUME_MISSING) > 0))),
                "randvolumen": int(np.count_nonzero(dropped & ((rule_hits & RULE_EDGE_VOLUME) > 0))),
                "split_im_fenster": int(np.count_nonzero(dropped & ((rule_hits & RULE_SPLIT) > 0))),
            },
        },
        "aktien": {"vorher_mit_rendite": instruments_with(old_v), "jetzt_mit_rendite": instruments_with(new_v)},
        "ranglisten": {
            "verglichen": compared,
            "spitze_geaendert": changed,
            "beispiele": examples,
            "hinweis": "Je Gruppe (A, B), Zeitraum 1–90 und Gewichtung (0/100 auf V, übrige auf U) der erste Platz nach alten und neuen Regeln auf denselben Kursen.",
        },
    }
