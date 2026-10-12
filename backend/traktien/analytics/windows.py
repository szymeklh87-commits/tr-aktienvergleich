"""Kalenderfenster 1–90 Tage (Abschnitt 8 des Auftrags).

Für Stichtag D und Zeitraum h:

* Ziel-Startdatum B = D − h Kalendertage.
* Endpunkt E = geprüfter Schlusskurs mit Sitzungsdatum D.
* Startpunkt S = letzte laut Börsenkalender existierende Sitzung am oder vor B,
  höchstens ``anchor_max_gap`` Kalendertage vor B. An S muss ein echter gültiger
  Kurs vorliegen; fehlt er, wird nicht auf einen älteren Kurs ausgewichen.
* Beobachtungen: alle gültigen Sitzungskurse zwischen S und D einschließlich.

Alle Datumswerte sind Epochentage (int). Die Eingaben müssen aufsteigend sortiert
und eindeutig sein; ``obs_days`` enthält nur gültige Kurse an Kalendersitzungen.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .codes import Status


@dataclass(frozen=True)
class ResolvedWindow:
    h: int
    target_start: int
    status: Status | None
    start_session: int | None = None
    start_index: int | None = None
    end_index: int | None = None
    n_obs: int = 0
    n_expected: int = 0

    @property
    def ok(self) -> bool:
        return self.status is None


def resolve_window(
    obs_days: np.ndarray,
    sessions: np.ndarray,
    cutoff: int,
    h: int,
    anchor_max_gap: int = 7,
) -> ResolvedWindow:
    """Bestimmt Start-/Endpunkt und Beobachtungszahlen eines Kalenderfensters.

    ``obs_days`` darf keine Tage nach ``cutoff`` enthalten (Aufrufer kürzt vorher).
    """
    if h < 1 or h > 90:
        raise ValueError("Fensterlänge muss zwischen 1 und 90 Kalendertagen liegen")
    target = int(cutoff) - int(h)

    session_pos = int(np.searchsorted(sessions, cutoff))
    if session_pos >= len(sessions) or int(sessions[session_pos]) != cutoff:
        return ResolvedWindow(h, target, Status.MARKT_AM_STICHTAG_GESCHLOSSEN)

    if len(obs_days) == 0 or int(obs_days[-1]) != cutoff:
        return ResolvedWindow(h, target, Status.KURS_AM_STICHTAG_FEHLT)

    k = int(np.searchsorted(sessions, target, side="right")) - 1
    if k < 0:
        # Kalender reicht nicht so weit zurück: wie fehlende Historie behandeln.
        return ResolvedWindow(h, target, Status.HISTORIE_ZU_KURZ)
    start_session = int(sessions[k])
    if target - start_session > anchor_max_gap:
        if int(obs_days[0]) > target:
            return ResolvedWindow(h, target, Status.HISTORIE_ZU_KURZ)
        return ResolvedWindow(h, target, Status.KEINE_STARTSITZUNG)

    if start_session < int(obs_days[0]):
        return ResolvedWindow(h, target, Status.HISTORIE_ZU_KURZ, start_session=start_session)

    j = int(np.searchsorted(obs_days, start_session))
    if j >= len(obs_days) or int(obs_days[j]) != start_session:
        return ResolvedWindow(h, target, Status.STARTKURS_FEHLT, start_session=start_session)

    end_index = len(obs_days) - 1
    n_obs = end_index - j + 1
    n_expected = session_pos - k + 1
    return ResolvedWindow(
        h=h,
        target_start=target,
        status=None,
        start_session=start_session,
        start_index=j,
        end_index=end_index,
        n_obs=n_obs,
        n_expected=n_expected,
    )


def expected_start_sessions(sessions: np.ndarray, cutoff: int, windows: range, anchor_max_gap: int = 7) -> list[int | None]:
    """Startsitzung je Fenster unabhängig von Kursdaten (für Charts und Leerzustände)."""
    result: list[int | None] = []
    for h in windows:
        target = int(cutoff) - int(h)
        k = int(np.searchsorted(sessions, target, side="right")) - 1
        if k < 0:
            result.append(None)
            continue
        start = int(sessions[k])
        result.append(start if target - start <= anchor_max_gap else None)
    return result
