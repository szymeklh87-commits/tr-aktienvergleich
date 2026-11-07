/* Geprüfte Ranglisten (ab 1.24.0, Simons Auftrag vom 07.11.2026, 19:06 Uhr): Aktien mit ungeklärter Kursabweichung
 * (Hinweis 13 oder 18, Endkurs oder Wertentwicklung am zweiten Börsenplatz auffällig) stehen nicht in den bestätigten
 * Ranglisten; die Plätze werden ohne sie neu gezählt. Die ausgeblendeten Aktien bleiben mit Grund sichtbar. */

import { unverifiedInWindow } from './tradeplan';
import { isNoisy, listEntries, listOrder, noiseFlags, type ListEntry, type ReturnList } from './turnover';
import type { Instruments, Manifest, WindowData } from './types';

export interface RemovedEntry {
  entry: ListEntry;
  reason: string;
}

export interface CheckedList {
  /** bestätigte Einträge, Plätze neu gezählt */
  kept: ListEntry[];
  /** ausgeblendet: ``entry.rank`` ist der Platz in der Liste vor der Prüfung */
  removed: RemovedEntry[];
}

/** Einträge prüfen und neu nummerieren (Reihenfolge bleibt). */
export function confirmedEntries(entries: ListEntry[], instruments: Instruments): CheckedList {
  const kept: ListEntry[] = [];
  const removed: RemovedEntry[] = [];
  for (const entry of entries) {
    const reason = unverifiedInWindow(instruments, entry.idx, entry.venue?.status);
    if (reason) removed.push({ entry, reason });
    else kept.push({ ...entry, rank: kept.length + 1, before: entry.before ?? entry.rank });
  }
  return { kept, removed };
}

/** Ganze Rangliste einer Fensterdatei geprüft; ``clean`` blendet danach zusätzlich Auffällige aus (Plätze der geprüften
 * Liste bleiben stehen). */
export function checkedList(win: WindowData, list: ReturnList, instruments: Instruments, manifest: Manifest | null, clean = false): CheckedList {
  const all = listEntries(win, list, 0, listOrder(win, list).length, instruments.last_close_day);
  const checked = confirmedEntries(all, instruments);
  return clean ? { kept: checked.kept.filter((e) => !isNoisy(noiseFlags(instruments, manifest, e.idx, e.wf))), removed: checked.removed } : checked;
}
