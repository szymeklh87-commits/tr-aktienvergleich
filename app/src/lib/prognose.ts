/* Wahrscheinlichkeiten, Nachrichtenereignisse, Analystenszenarien, Aufmerksamkeit und Gesamtbild (ab 1.25.0).
 *
 * Simons Auftrag vom 07.11.2026, 19:06 Uhr: getestete Wahrscheinlichkeiten für 1–30 Handelstage, heute nur mit aktuellen
 * Intraday-Daten, kalibriert mit Fehlerquote; Nachrichtenanalyse mit schweren Warnungen; Analystenziele, Spannen und
 * Szenarien; Aufmerksamkeit aus zulässigen Quellen; Kombination ohne erfundene Prozentzahlen; Grenzen offen zeigen.
 * Die App rechnet nichts hinzu: Prozentzahlen kommen nur aus dem geprüften Modell des Servers, sonst „Nicht ausreichend
 * zuverlässig“. Ohne Browser prüfbar (tests/prognose.test.ts). */

import * as f from './format';
import type { AnalystAction, Light, ProbabilityClass, ProbabilityData, ProbabilityQuality, SignalsData } from './types';

export const UNRELIABLE = 'Nicht ausreichend zuverlässig';

export interface HorizonView {
  h: number;
  /** Wahrscheinlichkeit für einen höheren Schlusskurs nach h Handelstagen (Anteil) oder null */
  p: number | null;
  reliable: boolean;
  quality: ProbabilityQuality | null;
  /** Testfälle mit ähnlicher Wahrscheinlichkeit: Ø Veränderung und mittlere Hälfte */
  expected: { mean: number; q25: number; q75: number; n: number } | null;
  /** Grundrate (Anteil steigender Fälle aller Aktien mit Mindestumsatz) */
  base: number | null;
}

/** Klasse der Testfälle, in die eine Wahrscheinlichkeit fällt. */
export function classOf(classes: ProbabilityClass[] | undefined, p: number): ProbabilityClass | null {
  if (!classes?.length) return null;
  return classes.find((c) => p >= c.von && (p < c.bis || (c.bis >= 1 && p <= 1))) ?? null;
}

export function horizonView(data: ProbabilityData | null | undefined, k: number, h: number): HorizonView {
  const quality = data?.qualitaet[String(h)] ?? null;
  const raw = data?.steigt[String(h)]?.[k];
  const reliable = Boolean(quality?.zuverlaessig);
  const p = reliable && raw !== null && raw !== undefined ? raw / 100 : null;
  const cls = p !== null ? classOf(quality?.klassen, p) : null;
  return {
    h,
    p,
    reliable,
    quality,
    expected: cls ? { mean: cls.mittel, q25: cls.q25, q75: cls.q75, n: cls.n } : null,
    base: data?.grundrate[String(h)] ?? null,
  };
}

/** Sofort sichtbare Horizonte (1/5/10/20/30) einer Aktie. */
export function shownHorizons(data: ProbabilityData | null | undefined, k: number): HorizonView[] {
  return (data?.gezeigt ?? [1, 5, 10, 20, 30]).map((h) => horizonView(data, k, h));
}

/** Ein Satz je Horizont: „steigt in 10 Handelstagen: 56 % (fällt 44 %), Ø +0,8 %, meist −2,1 % bis +3,4 %“. */
export function horizonText(v: HorizonView): string {
  const label = v.h === 1 ? 'nächster Handelstag' : `${v.h} Handelstage`;
  if (v.p === null) return `${label}: ${UNRELIABLE}${v.quality?.grund ? ` (${v.quality.grund})` : ''}`;
  const exp = v.expected ? `, Ø ${f.pct(v.expected.mean, 1)}, meist ${f.pct(v.expected.q25, 1)} bis ${f.pct(v.expected.q75, 1)}` : '';
  return `${label}: steigt ${f.plainPct(v.p * 100, 0)}, fällt ${f.plainPct((1 - v.p) * 100, 0)}${exp}`;
}

/** Güte eines Horizonts in Worten. */
export function qualityText(q: ProbabilityQuality | null | undefined): string {
  if (!q || !q.n) return 'kein Test möglich (zu kurze Kurshistorie)';
  const skill = q.skill !== undefined ? `Brier ${f.plainPct((q.skill ?? 0) * 100, 1)} besser als die Grundrate` : '';
  const ece = q.ece !== undefined ? `Kalibrierungsfehler ${f.plainPct((q.ece ?? 0) * 100, 1)}` : '';
  const hits = q.treffer !== undefined ? `Richtung in ${f.plainPct((q.treffer ?? 0) * 100, 0)} der Testfälle getroffen` : '';
  return [`${f.integer(q.n)} Testfälle`, skill, ece, hits].filter(Boolean).join(', ');
}

/** Heute: ohne Kurse im Tagesverlauf der Vergangenheit nicht prüfbar – nur der Stand des Tages, keine Prozentzahl. */
export function todayText(intradayChange: number | null): string {
  if (intradayChange === null) return 'Heute: nur mit aktuellen Kursen im Tagesverlauf – ohne sie keine Aussage.';
  return `Heute bisher ${f.pct(intradayChange, 1)} zum Vortag. Eine Wahrscheinlichkeit für den laufenden Tag gibt es nicht: ohne Kurse im Tagesverlauf der Vergangenheit lässt sie sich nicht prüfen.`;
}

/* ---------------------------------------------------------------- Nachrichtenereignisse */

export const KAUFWARNUNG = 'Hohes Unternehmensrisiko – Kaufwarnung';

export function warningOf(data: SignalsData | null | undefined, k: number): string | null {
  return data?.ereignisse?.warnung?.[k] ?? null;
}

export function newsLightOf(data: SignalsData | null | undefined, k: number): Light | null {
  return data?.ereignisse?.ampel?.[k] ?? null;
}

/* ---------------------------------------------------------------- Analysten */

export interface AnalystScenario {
  count: number;
  mean: number | null;
  median: number | null;
  low: number | null;
  high: number | null;
  /** jüngstes Ziel je Haus aus den Urteilen der letzten 12 Monate, gewichtet nach Aktualität (Halbwertszeit 90 Tage) */
  weighted: number | null;
  weightedCount: number;
}

const HALF_LIFE = 90;

/** Gewichteter Ø der jüngsten Ziele je Analystenhaus (ohne Doppelte), Gewicht 0,5^(Alter/90 Tage). */
export function weightedTarget(actions: AnalystAction[] | null | undefined, today: number): { value: number | null; count: number } {
  const latest = new Map<string, AnalystAction>();
  for (const a of actions ?? []) {
    if (a.ziel === null || a.ziel <= 0 || a.tag === null || today - a.tag > 366 || a.tag > today) continue;
    const house = (a.haus ?? '').trim().toLowerCase();
    if (!house) continue;
    const prev = latest.get(house);
    if (!prev || (prev.tag ?? 0) < a.tag) latest.set(house, a);
  }
  let sum = 0;
  let weights = 0;
  for (const a of latest.values()) {
    const w = 0.5 ** ((today - (a.tag ?? today)) / HALF_LIFE);
    sum += w * (a.ziel ?? 0);
    weights += w;
  }
  return { value: weights > 0 ? sum / weights : null, count: latest.size };
}

export interface ScenarioRow {
  key: 'pessimistisch' | 'basis' | 'optimistisch';
  label: string;
  target: number;
  change: number | null;
}

/** Szenarien für etwa 12 Monate aus den Zielen der Analysten: tiefstes, Median (sonst Ø) und höchstes Ziel. */
export function scenarios(s: AnalystScenario, price: number | null): ScenarioRow[] {
  const rows: ScenarioRow[] = [];
  const add = (key: ScenarioRow['key'], label: string, target: number | null) => {
    if (target === null || !(target > 0)) return;
    rows.push({ key, label, target, change: price !== null && price > 0 ? target / price - 1 : null });
  };
  add('pessimistisch', 'Pessimistisch (tiefstes Ziel)', s.low);
  add('basis', s.median !== null ? 'Basis (Median der Ziele)' : 'Basis (Ø der Ziele)', s.median ?? s.mean);
  add('optimistisch', 'Optimistisch (höchstes Ziel)', s.high);
  return rows;
}

/* ---------------------------------------------------------------- Gesamtbild ohne erfundene Prozentzahl */

export interface Overall {
  positive: string[];
  negative: string[];
  neutral: string[];
  text: string;
}

export interface OverallInput {
  entry: 'guenstig' | 'abwarten' | 'kein' | 'unklar';
  kurz: Light;
  lang: Light;
  /** Wahrscheinlichkeit 20 Tage und Grundrate, nur wenn zuverlässig */
  p20: number | null;
  base20: number | null;
  news: Light | null;
  risk: 'niedrig' | 'mittel' | 'hoch' | 'unbekannt' | null;
  warning: string | null;
}

/** Zählt, welche Hinweise dafür und welche dagegen sprechen – ohne daraus eine neue Prozentzahl zu machen. */
export function overall(i: OverallInput): Overall {
  const pos: string[] = [];
  const neg: string[] = [];
  const neu: string[] = [];
  const light = (value: Light, name: string) => (value === 'gruen' ? pos : value === 'rot' ? neg : neu).push(name);
  if (i.entry === 'guenstig') pos.push('Kaufzeitpunkt');
  else if (i.entry === 'kein') neg.push('Kaufzeitpunkt');
  else neu.push('Kaufzeitpunkt');
  light(i.kurz, 'kurzfristig');
  light(i.lang, 'langfristig');
  if (i.p20 !== null && i.base20 !== null) {
    if (i.p20 >= i.base20 + 0.03) pos.push('Wahrscheinlichkeit 20 Tage');
    else if (i.p20 <= i.base20 - 0.03) neg.push('Wahrscheinlichkeit 20 Tage');
    else neu.push('Wahrscheinlichkeit 20 Tage');
  }
  if (i.news) light(i.news, 'Nachrichten');
  if (i.risk === 'hoch') neg.push('Risiko');
  else if (i.risk === 'niedrig') pos.push('Risiko');
  else if (i.risk === 'mittel') neu.push('Risiko');
  const total = pos.length + neg.length + neu.length;
  const head = i.warning ? `${KAUFWARNUNG}. ` : '';
  const text = `${head}${f.integer(pos.length)} von ${f.integer(total)} Hinweisen sprechen dafür${pos.length ? ` (${pos.join(', ')})` : ''}, ${f.integer(neg.length)} dagegen${neg.length ? ` (${neg.join(', ')})` : ''}. Eine gemeinsame Wahrscheinlichkeit daraus gibt es nicht.`;
  return { positive: pos, negative: neg, neutral: neu, text };
}

/** Grenzen der Daten – immer sichtbar in den Einzelheiten. */
export const DATA_LIMITS = [
  'Kurse laut Yahoo (inoffiziell) und je Börse verzögert; kein ausführbarer Kurs von Trade Republic.',
  'Nachrichten: nur Schlagzeilen des Kursanbieters für die vorderen Aktien; die Einordnung folgt Wortlisten und liest den Text der Meldung nicht.',
  'Analystenziele: Anzahl, Ø, Median, Spanne und einzelne Urteile laut Yahoo und Nasdaq; Ziele gelten für etwa 12 Monate, frühere Treffsicherheit einzelner Häuser liegt nicht vor.',
  'Wahrscheinlichkeiten: nur aus Kursen und Umsätzen, geprüft ohne Zukunftsdaten; für den laufenden Tag nicht prüfbar.',
  'Rückblick: heutiges Aktienverzeichnis – nicht mehr gelistete Aktien fehlen (Überlebensverzerrung).',
];
