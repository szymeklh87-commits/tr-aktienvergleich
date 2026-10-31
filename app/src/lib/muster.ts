/* Musterbereiche (Gesamtauftrag, Abschnitt 26; Auftrag vom 31.10.2026, Abschnitt 8): Typen des Musterstands aus dem
 * täglichen Lauf (backend/traktien/aktienpilot/muster.py, Schema tr-muster/1) und reine Hilfsfunktionen für die Ansicht.
 * Die App rechnet keine Muster nach – Zustände, Score und Nachrechnung kommen fertig aus dem Lauf. */

export type Modul = 'A' | 'B' | 'C';

export interface MusterTreffer {
  isin: string;
  zustand: string;
  tag: string;
  schluss: number | null;
  score: number | null;
  volumenfaktor: number | null;
  reaktion: boolean;
  rendite_n_pct: number | null;
  ueberdehnt: boolean;
  wenig_umsatz: boolean;
  umsatz_usd: number | null;
  id: string | null;
  widerstand?: number | null;
  unten?: number | null;
  abstand_pct?: number | null;
  bandbreite_pct?: number | null;
  bandbreite_atr?: number | null;
  drift_pct?: number | null;
  basis_von?: string | null;
  basis_bis?: string | null;
  vorlauf?: 'aufwaertstrend' | 'bodenbildung' | 'neutral' | null;
  vorlauf_pct?: number | null;
  volumen_fehlt?: boolean;
}

export interface MusterModul {
  name: string;
  geprueft: number;
  zustaende: Record<string, number>;
  top: string[];
  treffer: MusterTreffer[];
  nicht_pruefbar: Record<string, string[]>;
  intraday?: { status: string; grund: string };
}

export interface MusterHorizont {
  n: number;
  mittel_pct: number | null;
  median_pct: number | null;
  anteil_positiv_pct: number | null;
  vergleich_mittel_pct: number | null;
}

export interface MusterAuswertung {
  signale: Record<string, number>;
  horizonte: Record<string, MusterHorizont>;
  stichtage: number;
  folgequote_pct?: number | null;
  kandidaten_abgeschlossen?: number;
  fehlausbrueche_pct?: number | null;
  uebergaenge_abgeschlossen?: number;
}

export interface MusterEreignis {
  id: string;
  modul: Modul;
  isin: string;
  zustand: string;
  datum: string;
}

export interface MusterStand {
  id: string;
  schema: 'tr-muster/1';
  version: string;
  erstellt_utc: string;
  datentag: string;
  snapshot_id: string;
  modus: string;
  hinweis: string;
  universum: number;
  parameter: Record<string, unknown> & { A: Record<string, number>; B: Record<string, number | boolean>; C: Record<string, number> };
  gruende: Record<string, string>;
  zustaende: Record<string, string>;
  module: Record<Modul, MusterModul>;
  auswertung: Record<Modul, MusterAuswertung> & { hinweis: string };
  journal?: MusterEreignis[];
}

export const MODULE: { value: Modul; label: string; kurz: string }[] = [
  { value: 'A', label: 'Vor-Ausbruch', kurz: 'A' },
  { value: 'C', label: 'Seitwärtsbasis', kurz: 'C' },
  { value: 'B', label: 'Volumensprung', kurz: 'B' },
];

export const AKTIV: Record<Modul, string[]> = {
  A: ['kandidat', 'vorlaeufig', 'bestaetigt'],
  B: ['sprung'],
  C: ['basis', 'naehert', 'vorlaeufig', 'bestaetigt'],
};

/** Reihenfolge der Zustände je Modul für Filter und Zählung (aktive zuerst, dann Abschlusszustände). */
export const ZUSTAENDE: Record<Modul, string[]> = {
  A: ['kandidat', 'vorlaeufig', 'bestaetigt', 'ungueltig', 'abgelaufen'],
  B: ['sprung'],
  C: ['basis', 'naehert', 'vorlaeufig', 'bestaetigt', 'zurueck'],
};

export type Sortierung = 'score' | 'rendite';

/** Treffer eines Moduls nach Auswahl („aktiv“ = alle aktiven Zustände, sonst genau ein Zustand) und Sortierung.
 * „score“ ist die feste Reihenfolge des Laufs (Zustand, Muster-Score, ISIN); „rendite“ eine eigene Ansicht nach der
 * bisherigen Rendite der letzten Sitzungen (Abschnitt 26.2: beide nicht vermischen). */
export function auswahl(m: MusterModul, modul: Modul, filter: string, sort: Sortierung): MusterTreffer[] {
  const rows = filter === 'aktiv' ? m.treffer.filter((t) => AKTIV[modul].includes(t.zustand)) : m.treffer.filter((t) => t.zustand === filter);
  if (sort === 'score') return rows;
  return [...rows].sort((a, b) => (b.rendite_n_pct ?? Number.NEGATIVE_INFINITY) - (a.rendite_n_pct ?? Number.NEGATIVE_INFINITY) || a.isin.localeCompare(b.isin));
}

export function nichtPruefbarSumme(m: MusterModul): number {
  return Object.values(m.nicht_pruefbar).reduce((s, v) => s + v.length, 0);
}

/** Kurzbeschreibung der Regel eines Moduls aus den Parametern des Laufs (keine zweiten Standardwerte in der App). */
export function regelText(stand: MusterStand, modul: Modul): string[] {
  const p = stand.parameter;
  const fmt = (v: unknown, d = 1) => (typeof v === 'number' ? v.toLocaleString('de-DE', { maximumFractionDigits: d }) : String(v));
  if (modul === 'B') {
    const b = p.B;
    return [
      `Tagesvolumen mindestens ${fmt(b.schwelle)} × Ø der ${fmt(p.volumen_vergleich_sitzungen)} vollständigen Sitzungen davor (der Tag selbst zählt nicht; mindestens ${fmt(p.volumen_min_vergleich)} gültige Vergleichstage).`,
      b.positive_reaktion ? 'Dazu eine positive Kursreaktion: Schluss über dem Vortag und in der oberen Hälfte der Tagesspanne. Ein Volumenschock bei fallendem Kurs zählt nicht.' : 'Ohne Bedingung an die Kursreaktion.',
      'Das ist die Tagesansicht – nicht der 5-/15-Minuten-Faktor und nicht die S2-Schwelle 1,5.',
    ];
  }
  const r = modul === 'A' ? p.A : p.C;
  const lines = [
    `Basis: die ${fmt(r.basis_sitzungen, 0)} abgeschlossenen Sitzungen vor dem Stichtag; Widerstand = höchstes Hoch, Unterstützung = tiefstes Tief der Basis.`,
    `Basis besteht bei einer Bandbreite bis ${fmt(r.max_bandbreite_pct)} % und bis ${fmt(r.max_bandbreite_atr)} ATR(${fmt(p.atr_sitzungen, 0)}) sowie einer Trendneigung (Drift) bis ±${fmt(r.max_drift_pct)} %.`,
    `„Nahe am Widerstand“: Schluss höchstens ${fmt(r.naehe_pct)} % darunter und im oberen ${fmt(100 - 100 * Number(r.oberer_anteil), 0)} %-Teil der Basis.`,
    `Bestätigt: Schluss mindestens ${fmt(r.bestaetigung_pct)} % über dem Widerstand und Tagesvolumen mindestens ${fmt(r.bestaetigung_volumen)} × Vergleichsvolumen; sonst vorläufig.`,
    `Rückfall unter den damaligen Widerstand innerhalb von ${fmt(r.ablauf_sitzungen, 0)} Sitzungen: ${modul === 'A' ? 'ungültig' : 'zurück in der Basis'}.`,
  ];
  if (modul === 'A') lines.splice(3, 0, `Kandidat ab der ersten positiven Reaktion in dieser Zone; nach ${fmt(r.ablauf_sitzungen, 0)} Sitzungen ohne Übergang: abgelaufen.`);
  lines.push(`Markiert, nicht ausgeschlossen: überdehnt (mehr als ${fmt(p.ueberdehnt_pct)} % in ${fmt(p.ueberdehnt_sitzungen, 0)} Sitzungen), wenig Liquidität (Ø Tagesumsatz unter ${fmt(Number(p.wenig_umsatz_usd) / 1e6)} Mio. USD).`);
  return lines;
}
