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
  keine_aktie_mit_umsatz: 'Keine vergleichbare Aktie erreicht in diesem Zeitraum einen Ø Tagesumsatz von 10 Mio. USD (Gruppe B).',
};

/** Grund in einem Satz über mehrere leere Ranglisten („nicht berechenbar: 190 – …“). */
export const EMPTY_PHRASE: Record<string, string> = {
  keine_vergleichbare_aktie: 'keine vergleichbare Aktie',
  zu_wenig_tagesdaten: 'weniger als 15 Tageskurse für die Gleichmäßigkeit',
  kein_aufwaertskandidat: 'keine gleichmäßig gestiegene Aktie',
  keine_aktie_mit_umsatz: 'keine Aktie mit Ø Umsatz ≥ 10 Mio. USD',
};

/** Kurzform der Leerzustände für enge Tabellenzellen. */
export const EMPTY_SHORT: Record<string, string> = {
  keine_vergleichbare_aktie: 'keine vergleichbare Aktie',
  zu_wenig_tagesdaten: 'nicht berechenbar: weniger als 15 Tageskurse',
  kein_aufwaertskandidat: 'keine gleichmäßig gestiegene Aktie',
  keine_aktie_mit_umsatz: 'keine Aktie mit Ø Umsatz ≥ 10 Mio. USD',
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
  // ab 1.14 „Einzelsprung“ (vorher „Impulstag“): ein Handelstag erklärt mehr als die Hälfte der Kursbewegung
  0: 'Einzelsprung',
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

/** Bruch {num, den} aus manifest.method als Prozenttext, z. B. „80 %“. */
function ratioPct(value: unknown): string | null {
  if (value && typeof value === 'object' && 'num' in value && 'den' in value) {
    const r = value as { num: number; den: number };
    if (r.den > 0) return `${((100 * r.num) / r.den).toLocaleString('de-DE', { maximumFractionDigits: 1 })} %`;
  }
  return null;
}

/** Regel zu fehlenden Börsentagen des angezeigten Stands (Methode 1.8.0: höchstens 20 %, ein Tag immer erlaubt). */
export function sessionRuleText(method: Record<string, unknown> | null | undefined): string {
  const m = method ?? {};
  const raw = m.min_session_coverage as { num: number; den: number } | undefined;
  const tolerated = Number(m.tolerated_missing_sessions ?? 0);
  if (!raw || !(raw.den > 0)) return 'ausreichend viele Börsentage mit Kurs';
  const missing = ratioPct({ num: raw.den - raw.num, den: raw.den }) ?? '–';
  if (tolerated >= 1) return `höchstens ${missing} fehlende Börsentage (${tolerated === 1 ? 'ein einzelner fehlender Tag ist immer erlaubt' : `${tolerated} fehlende Tage sind immer erlaubt`})`;
  return `mindestens ${ratioPct(raw) ?? '–'} der erwarteten Börsentage mit Kurs`;
}

/** Volumenregel des angezeigten Stands, z. B. „an mindestens 80 % der Kurstage positives Volumen“. */
export function volumeRuleText(method: Record<string, unknown> | null | undefined): string {
  const m = method ?? {};
  const share = ratioPct(m.min_volume_coverage) ?? '80 %';
  const basis = m.volume_basis === 'sitzungen' ? 'der erwarteten Börsentage' : 'der Kurstage';
  return `an mindestens ${share} ${basis} positives Volumen`;
}

/** Status 11 „Startkurs fehlt“ und 12 „zu viele Börsentage ohne Kurs“. */
export const START_PRICE_MISSING = 11;
export const TOO_MANY_MISSING_DAYS = 12;

export interface CoverageFacts {
  /** erster Börsentag des Zeitraums (Startsitzung) */
  start: number;
  end: number;
  /** Börsentage der Börse im Zeitraum (Start und Ende eingeschlossen) */
  expected: number;
  /** davon mit Schlusskurs */
  withPrice: number;
  /** davon ohne Schlusskurs (Lücken beim Kursanbieter, auch Tage ohne Kurs und Umsatz) */
  missing: number;
}

/**
 * Zahlen zu fehlenden Kurstagen eines Zeitraums (ab 1.18) aus der Kursreihe der Aktie: Tage mit Kurs (`d`) und Lücken
 * (`gaps`, erwartete Börsentage ohne gültigen Kurs) zwischen Startsitzung und Endtag. Fehlende Tage werden gezählt,
 * nicht ersetzt. Ohne bekannte Startsitzung null.
 */
export function coverageFacts(series: { d: number[]; gaps: number[]; window_start: (number | null)[] }, h: number, endDay: number): CoverageFacts | null {
  const start = series.window_start[h - 1];
  if (start === null || start === undefined || start > endDay) return null;
  const withPrice = series.d.filter((d) => d >= start && d <= endDay).length;
  const missing = series.gaps.filter((d) => d >= start && d <= endDay).length;
  return { start, end: endDay, expected: withPrice + missing, withPrice, missing };
}

/**
 * Verständliche Begründung, warum für einen Zeitraum keine Kursrendite veröffentlicht wird (ab 1.18) – mit den Zahlen
 * des Zeitraums statt nur der Statusbezeichnung. `dayText` formatiert ein Datum (Tagesnummer → „07.10.2026“). Für
 * andere Status null (dann gilt der Statustext des Manifests).
 */
export function missingDataNote(status: number, facts: CoverageFacts | null, method: Record<string, unknown> | null | undefined, dayText: (day: number) => string): string | null {
  if (!facts) return null;
  if (status === START_PRICE_MISSING) {
    return `Am ersten Börsentag des Zeitraums, dem ${dayText(facts.start)}, fehlt der Schlusskurs. Ohne Startkurs gibt es keine Kursrendite; die App nimmt keinen älteren Kurs als Ersatz.`;
  }
  if (status === TOO_MANY_MISSING_DAYS && facts.expected > 0) {
    const share = ((100 * facts.missing) / facts.expected).toLocaleString('de-DE', { maximumFractionDigits: 0 });
    return (
      `Vom ${dayText(facts.start)} bis ${dayText(facts.end)} hatte die Börse ${facts.expected} Börsentage. Schlusskurse liegen für ${facts.withPrice} vor, ${facts.missing} fehlen (${share} %). ` +
      `Erlaubt sind ${sessionRuleText(method)}. Fehlende Tage werden weder ersetzt noch als null gezählt.`
    );
  }
  return null;
}
