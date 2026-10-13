/* Status- und Hinweistexte kommen aus dem Manifest des jeweiligen Snapshots. */

import type { CodeInfo, Manifest } from './types';

export const READY_LEVEL = 0;

export function statusInfo(manifest: Manifest | null, code: number): CodeInfo {
  if (code === READY_LEVEL) return { key: 'bereit', kurz: 'Schlusskurs am Stichtag vorhanden', text: 'Für dieses Instrument liegt ein geprüfter Schlusskurs am Kursstichtag vor.' };
  return manifest?.codes.status[String(code)] ?? { key: `status_${code}`, kurz: `Status ${code}`, text: '' };
}

export function isReturnPublishable(manifest: Manifest, code: number): boolean {
  return manifest.codes.return_publishable.includes(code);
}

export function isTrendEligible(manifest: Manifest, code: number): boolean {
  return manifest.codes.trend_eligible.includes(code);
}

export function warningTexts(table: Record<string, CodeInfo> | undefined, bits: number): string[] {
  if (!table || !bits) return [];
  const out: string[] = [];
  for (const [bit, info] of Object.entries(table)) {
    if ((bits >> Number(bit)) & 1) out.push(info.text);
  }
  return out;
}

export const EMPTY_REASONS: Record<string, string> = {
  keine_vergleichbare_aktie: 'Keine Aktie erfüllt für diesen Zeitraum die Daten- und Qualitätsregeln.',
  zu_wenig_tagesdaten: 'Für die Gleichmäßigkeit sind mindestens 15 echte Tageskurse nötig – in diesem kurzen Zeitraum gibt es weniger.',
  kein_aufwaertskandidat: 'Keine qualitätsgeprüfte Aktie ist in diesem Zeitraum gleichmäßig gestiegen (positive Rendite und positive Trendsteigung).',
};

export const TYPE_LABELS: Record<string, string> = {
  stammaktie: 'Stammaktie',
  vorzugsaktie: 'Vorzugsaktie',
  adr_gdr: 'ADR/GDR (Hinterlegungsschein)',
  reit: 'REIT',
  fonds_etp: 'Fonds/ETP',
  bezugsrecht: 'Bezugsrecht',
  optionsschein: 'Optionsschein',
  unklar: 'Typ unklar',
};

export const IDENTITY_LABELS: Record<string, string> = {
  verifiziert: 'ISIN eindeutig einer Börsennotierung zugeordnet',
  unklar: 'Identität unklar',
  offen: 'Identität noch nicht geprüft',
  kein_aktieninstrument: 'Kein Aktieninstrument',
  isin_ungueltig: 'ISIN formal ungültig',
};

/** Kurzbezeichnungen der Hinweis-Bits für Listen (Langtexte stehen im Manifest). */
export const INSTRUMENT_HINT_SHORT: Record<number, string> = {
  2: 'OTC-Markt',
  3: 'Kurs in Untereinheit',
  4: 'Ersatzkalender',
  5: 'wenige Handelstage',
  6: 'geprüfter Kurssprung',
  7: 'Volumen oft unbekannt',
  9: 'Split in der Historie',
  13: 'Bewegung ohne Umsatz',
};

export const WINDOW_HINT_SHORT: Record<number, string> = {
  0: 'Impulstag',
  1: 'Split im Zeitraum',
  2: 'geprüfter Kurssprung',
  3: 'R² instabil',
  4: 'Übernahmemuster',
  5: 'Börsenplatz-Abweichung',
};

export const VENUE_DEVIATION_BIT = 5;

export const VERY_LOW_TURNOVER_BIT = 14;
export const TURNOVER_UNKNOWN_BIT = 15;

/** Kurzbezeichnungen der gesetzten Bits (in Bitreihenfolge). */
export function hintLabels(table: Record<number, string>, bits: number): string[] {
  const out: string[] = [];
  for (const [bit, label] of Object.entries(table)) {
    if ((bits >> Number(bit)) & 1) out.push(label);
  }
  return out;
}
