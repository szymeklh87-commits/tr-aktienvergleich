"""Vergleich mit den Regeln der Vorversion auf denselben Daten (Methodenwechsel transparent machen).

Jeder Lauf bestimmt den Status jedes Aktie-Zeitraum-Paares zweimal: nach den Zulassungsregeln der
aktuellen Methodenversion und nach denen der Vorversion (``cfg.previous_rules``). Daraus entstehen
die Mengen V und U beider Fassungen, die Ranglisten der Vorversion und die Spitzenplätze im
Vergleich. Das Manifest veröffentlicht die Unterschiede (``method_comparison``) – so ist sichtbar,
was ein Methodenwechsel an genau diesem Datenstand verändert.

Seit tr-methode-1.8.0 sind die Gründe allgemein über die Statusnummern angegeben: weggefallene Paare
mit ihrem Status nach den neuen Regeln, hinzugekommene mit ihrem Status nach den alten Regeln. Stände
von 1.7.0 trugen stattdessen ``paare.grund`` mit drei festen Schlüsseln (die App liest beide Formen).
"""

from __future__ import annotations

from collections import Counter

import numpy as np

from ..config import CANONICAL_WEIGHTS, MethodConfig
from .codes import RETURN_PUBLISHABLE, Status
from .ranking import WindowRanking, group_b_ranking, rank_window

MAX_EXAMPLES = 12


def _counts(values: np.ndarray) -> dict[str, int]:
    return {str(code): int(n) for code, n in sorted(Counter(int(v) for v in values.ravel().tolist()).items())}


def compare_with_previous_rules(
    *,
    status: np.ndarray,
    previous_status: np.ndarray,
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
    added = new_v & ~old_v

    compared = changed = 0
    examples: list[dict] = []
    for col, h in enumerate(windows):
        new = rankings[h]
        v_idx = np.nonzero(old_v[:, col])[0].astype(np.int64)
        u_idx = np.nonzero(old_u[:, col])[0].astype(np.int64)
        # Gleichstandsregel ist seit 1.7.0 unverändert (ranking-11w-v2); nur die Mengen unterscheiden sich
        old = rank_window(h, v_idx, u_idx, r[:, col], r2[:, col], slope[:, col], noise[:, col])
        old_b = group_b_ranking(old, liquid, r[:, col], r2[:, col], slope[:, col], noise[:, col])
        pairs = [("A", 0, old.native0, new.native0)]
        pairs += [("A", w, old.trend[w], new.trend[w]) for w in CANONICAL_WEIGHTS if w > 0]
        if new.group_b is not None and old_b is not None:
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
        "regeln": list(cfg.change_notes),
        "paare": {
            "vorher_V": int(old_v.sum()),
            "jetzt_V": int(new_v.sum()),
            "vorher_U": int(old_u.sum()),
            "jetzt_U": int(new_u.sum()),
            "nicht_mehr_bewertet": int(dropped.sum()),
            "neu_bewertet": int(added.sum()),
            # Gründe über die Statusnummern (Texte in manifest.codes.status)
            "weggefallen_nach_status": _counts(status[dropped]),
            "hinzugekommen_aus_status": _counts(previous_status[added]),
        },
        "aktien": {"vorher_mit_rendite": instruments_with(old_v), "jetzt_mit_rendite": instruments_with(new_v)},
        "ranglisten": {
            "verglichen": compared,
            "spitze_geaendert": changed,
            "beispiele": examples,
            "hinweis": "Je Gruppe (A, B), Zeitraum 1–90 und Gewichtung (0/100 auf V, übrige auf U) der erste Platz nach alten und neuen Regeln auf denselben Kursen.",
        },
    }
