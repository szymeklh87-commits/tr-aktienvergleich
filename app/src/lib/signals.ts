/* Signale je Aktie (ab 1.6, `signale-v1`; Gesamtwertung ab 1.7, `signale-v2`): Sortierung, Filter, kurze
 * Gründe und Sätze für die Anzeige.
 *
 * Die App rechnet keine Signale nach – sie ordnet und beschreibt nur, was der Server berechnet hat.
 * Reine Funktionen, damit sie ohne Browser getestet werden können. */

import * as f from './format';
import type { Calibration, ConsistencyCalibration, ConsistencyPeriod, Light, SignalComponent, SignalDetail, SignalsData, TotalGrade, TotalPart } from './types';

/** „gesamt“ (ab 1.7) ersetzt die frühere Liste „beide“ – alte Links mit ``liste=beide`` führen dorthin. */
export type ListKind = 'gesamt' | 'kurz' | 'lang' | 'potenzial' | 'volumen';
export const LIST_KINDS: ListKind[] = ['gesamt', 'kurz', 'lang', 'potenzial', 'volumen'];

/** Ab diesem Vielfachen des üblichen Volumens erscheint eine Aktie in der Liste „Volumen“ (ab 1.11) */
export const VOLUME_LIST_MIN = 1.5;

export function parseListKind(value: string | null | undefined): ListKind {
  return value === 'kurz' || value === 'lang' || value === 'potenzial' || value === 'volumen' ? value : 'gesamt';
}

export const LIGHT_WORD: Record<Light, string> = { gruen: 'grün', gelb: 'gelb', rot: 'rot', grau: 'grau' };
export const LIGHT_MEANING: Record<Light, string> = {
  gruen: 'Signale überwiegend positiv',
  gelb: 'gemischt',
  rot: 'Signale überwiegend negativ',
  grau: 'zu wenig Daten',
};
const LIGHT_ORDER: Record<Light, number> = { gruen: 0, gelb: 1, grau: 2, rot: 3 };

export const LIST_INFO: Record<ListKind, { label: string; title: string; text: string }> = {
  gesamt: {
    label: 'Gesamt',
    title: 'Beste Gesamtwertung',
    text: 'Oben stehen Aktien, die in 30, 60 und 90 Tagen an vielen Tagen gestiegen sind und deren Kursziel deutlich über dem Kurs liegt. Die Gesamtwertung (0–100) zählt: regelmäßiges Steigen 35 %, Kursziel 35 %, Aufmerksamkeit und Schwung 15 %, Qualität 15 %. ▲ 15/21 heißt: an 15 von 21 Handelstagen gestiegen.',
  },
  kurz: {
    label: 'Kurz',
    title: 'Kurzfristig stark (Trading)',
    text: 'Für die nächsten Tage bis Wochen: sortiert nach dem kurzfristigen Urteil aus Umsatz, Schwung, Steigetagen, Trend, neuem Hoch, RSI, Nachrichten und Stimmung. Nur Aktien mit mindestens 250.000 € Umsatz am Tag.',
  },
  lang: {
    label: 'Lang',
    title: 'Langfristig stark (etwa 12 Monate)',
    text: 'Für etwa 12 Monate: sortiert nach dem langfristigen Urteil aus Kursziel der Analysten, Bewertung, Wachstum und Finanzen, langfristigem Trend und der Richtung der Analysten.',
  },
  potenzial: {
    label: 'Kursziel',
    title: 'Höchste erwartete Steigerung',
    text: 'Sortiert nach dem Abstand zwischen Kurs und durchschnittlichem Kursziel der Analysten – ohne die übrigen Signale. Beispiel: Kurs 40 €, Kursziel 50 € ergibt +25 %. Hohe Werte bei wenigen Analysten sind unsicher.',
  },
  volumen: {
    label: 'Volumen',
    title: 'Volumen gestiegen',
    text: 'Aktien, die am letzten Börsentag mindestens 1,5-mal so oft gehandelt wurden wie im Schnitt der 20 Börsentage davor. Zuerst die, deren Kurs in den letzten 5 Börsentagen gestiegen ist.',
  },
};

export interface SignalFilter {
  kind: ListKind;
  minAnalysts: number;
  onlyGreen: boolean;
  liquidOnly: boolean;
  sector: number | null;
}

const indexCache = new WeakMap<SignalsData, Map<string, number>>();

/** ISIN → Zeile im Signal-Stand; ab 1.15 einmal je Signal-Stand gebaut (vorher in jeder Ansicht neu, rund 11.000 Einträge). */
export function signalIndex(data: SignalsData): Map<string, number> {
  const cached = indexCache.get(data);
  if (cached) return cached;
  const map = new Map<string, number>();
  data.isin.forEach((isin, k) => map.set(isin, k));
  indexCache.set(data, map);
  return map;
}

function mean(values: (number | null)[]): number | null {
  const ok = values.filter((v): v is number => v !== null && Number.isFinite(v));
  return ok.length ? ok.reduce((a, b) => a + b, 0) / ok.length : null;
}

/** Gibt es im Signal-Stand eine Gesamtwertung? (ab signale-v2) */
export function hasTotal(data: SignalsData): boolean {
  return Array.isArray(data.gesamt) && data.gesamt.length === data.isin.length;
}

/** Gesamtwertung einer Aktie; in älteren Ständen ersatzweise das Mittel aus kurz- und langfristig. */
export function totalOf(data: SignalsData, k: number): number | null {
  if (hasTotal(data)) return data.gesamt![k] ?? null;
  if (data.kurz[k] === null || data.lang[k] === null) return null;
  return mean([data.kurz[k], data.lang[k]]);
}

export const GRADE_WORD: Record<TotalGrade, string> = { stark: 'stark', mittel: 'mittel', schwach: 'schwach', ohne: 'ohne Wertung' };

/** Stufe der Gesamtwertung (mit den Schwellen des Stands, sonst 65/50). */
export function gradeOf(total: number | null | undefined, data?: SignalsData | null): TotalGrade {
  if (total === null || total === undefined || !Number.isFinite(total)) return 'ohne';
  const strong = data?.regeln.gesamt_stark_ab ?? 65;
  const medium = data?.regeln.gesamt_mittel_ab ?? 50;
  return total >= strong ? 'stark' : total >= medium ? 'mittel' : 'schwach';
}

export interface TotalEntry {
  total: number | null;
  grade: TotalGrade;
}

/** Gesamtwertung je ISIN – nur Stände ab signale-v2 (ältere Stände haben keine Gesamtwertung, dann null). */
export function totalsByIsin(data: SignalsData | null | undefined): Map<string, TotalEntry> | null {
  if (!data || !hasTotal(data)) return null;
  const out = new Map<string, TotalEntry>();
  data.isin.forEach((isin, k) => {
    const total = data.gesamt![k] ?? null;
    out.set(isin, { total, grade: data.gesamt_stufe?.[k] ?? gradeOf(total, data) });
  });
  return out;
}

export interface ConsistencyCell {
  tage: number;
  auf: number;
  von: number;
  rendite: number | null;
  /** Anteil der Anstiegstage 0–1 */
  anteil: number;
  /** pos = mindestens 60 % und gestiegen, neg = unter 50 % oder gefallen, sonst neu */
  ton: 'pos' | 'neu' | 'neg';
}

function cellTone(share: number, ret: number | null): ConsistencyCell['ton'] {
  if (ret !== null && ret <= 0) return 'neg';
  if (share >= 0.6) return 'pos';
  return share < 0.5 ? 'neg' : 'neu';
}

/** Steig-Konstanz einer Listenzeile: je Zeitraum Anstiegstage von Handelstagen (nur vorhandene Zeiträume). */
export function consistencyCells(data: SignalsData, k: number): ConsistencyCell[] {
  const periods = data.regeln.konstanz_zeitraeume ?? [30, 60, 90];
  const out: ConsistencyCell[] = [];
  for (const days of periods) {
    const up = feature(data, `steig_${days}`, k);
    const of = feature(data, `tage_${days}`, k);
    if (up === null || of === null || of <= 0) continue;
    const ret = feature(data, `r_${days}k`, k);
    out.push({ tage: days, auf: up, von: of, rendite: ret, anteil: up / of, ton: cellTone(up / of, ret) });
  }
  return out;
}

/** Dasselbe für die Einzelansicht. */
export function detailConsistency(periods: ConsistencyPeriod[] | undefined): ConsistencyCell[] {
  return (periods ?? [])
    .filter((p) => p.steigtage !== null && p.vergleiche !== null && p.vergleiche > 0)
    .map((p) => ({ tage: p.tage, auf: p.steigtage!, von: p.vergleiche!, rendite: p.rendite, anteil: p.steigtage! / p.vergleiche!, ton: cellTone(p.steigtage! / p.vergleiche!, p.rendite) }));
}

export const TOTAL_PARTS: TotalPart[] = ['konstanz', 'kursziel', 'kurzfristig', 'qualitaet'];
export const TOTAL_PART_FALLBACK: Record<TotalPart, string> = {
  konstanz: 'Steig-Konstanz (30/60/90 Tage)',
  kursziel: 'Kursziel-Potenzial',
  kurzfristig: 'Aufmerksamkeit & Schwung',
  qualitaet: 'Qualität',
};
const TOTAL_WEIGHT_FALLBACK: Record<TotalPart, number> = { konstanz: 0.35, kursziel: 0.35, kurzfristig: 0.15, qualitaet: 0.15 };

/** Teile der Gesamtwertung mit Gewicht und Beitrag (Punkte × Gewicht). */
export function totalParts(detail: SignalDetail, data: SignalsData | null): { key: TotalPart; name: string; weight: number; points: number | null; contribution: number | null }[] {
  const weights = data?.regeln.gesamt_gewichte ?? TOTAL_WEIGHT_FALLBACK;
  const names = data?.regeln.gesamt_namen ?? TOTAL_PART_FALLBACK;
  return TOTAL_PARTS.map((key) => {
    const points = detail.gesamt_teile?.[key] ?? null;
    const weight = weights[key] ?? TOTAL_WEIGHT_FALLBACK[key];
    return { key, name: names[key] ?? TOTAL_PART_FALLBACK[key], weight, points, contribution: points === null ? null : points * weight };
  });
}

/** Ein Satz zur Gesamtwertung: Steig-Konstanz und Kursziel in Worten. */
export function totalSentence(detail: SignalDetail): string | null {
  if (detail.gesamt === null || detail.gesamt === undefined) return null;
  const cells = detailConsistency(detail.konstanz);
  const parts: string[] = [];
  if (cells.length) {
    parts.push(`Gestiegen an ${cells.map((c) => `${c.auf} von ${c.von}`).join(', ')} Handelstagen (${cells.map((c) => c.tage).join('/')} Tage)`);
  }
  if (detail.potenzial !== null && detail.potenzial !== undefined) {
    const analysts = Math.max(detail.kennzahlen?.analysten?.anzahl ?? 0, ...detail.ziel_quellen.map((q) => q.anzahl ?? 0));
    parts.push(`Kursziel ${f.pct(detail.potenzial, 0)}${analysts ? ` (${f.plural(analysts, 'Analyst', 'Analysten')})` : ''}`);
  } else {
    parts.push('kein Kursziel der Analysten');
  }
  return `${parts.join('; ')}.`;
}

/** Trefferquote der Steig-Konstanz als Satz (nur wenn berechnet). */
export function totalProbabilityText(detail: SignalDetail, cal: ConsistencyCalibration | null | undefined): string | null {
  const p = detail.wahrscheinlichkeit_gesamt;
  if (!p || p.steigt_20 === null) return null;
  const range = `${Math.round(p.bereich[0])}–${Math.round(Math.min(100, p.bereich[1]))} Punkte`;
  const twenty = `20 Handelstage später in ${f.plainPct(p.steigt_20 * 100, 0)} der Fälle höher (im Mittel ${f.pct(p.mittel_20, 1)})`;
  const sixty = p.steigt_60 !== null ? `, 60 Handelstage später in ${f.plainPct(p.steigt_60 * 100, 0)} (${f.pct(p.mittel_60, 1)})` : '';
  const base =
    cal && cal.alle_steigt_20 !== null
      ? ` Zum Vergleich alle Aktien: ${f.plainPct(cal.alle_steigt_20 * 100, 0)}${cal.alle_steigt_60 !== null ? ` bzw. ${f.plainPct(cal.alle_steigt_60 * 100, 0)}` : ''}.`
      : '';
  return `Aktien mit ähnlicher Steig-Konstanz (${range}) standen ${twenty}${sixty}.${base} Grundlage: ${f.integer(p.faelle)} Vergleichsfälle aus der eigenen Kurshistorie (überlappende Zeiträume). Das gilt nur für den Kursverlauf – Kursziele lassen sich so nicht prüfen. Eine Häufigkeit aus der Vergangenheit, keine Zusage.`;
}

/** Indizes (in ``data``) der passenden Aktien in Ranglistenreihenfolge. ``liquid``: Gruppe B je ISIN. */
export function rankSignals(data: SignalsData, filter: SignalFilter, liquid?: (isin: string) => boolean): number[] {
  const out: number[] = [];
  for (let k = 0; k < data.isin.length; k++) {
    if (filter.sector !== null && data.sektor[k] !== filter.sector) continue;
    if (filter.liquidOnly && liquid && !liquid(data.isin[k])) continue;
    const analysts = data.analysten[k] ?? 0;
    if (filter.kind === 'kurz') {
      if (data.kurz[k] === null || !data.handelbar[k]) continue;
      if (filter.onlyGreen && data.kurz_ampel[k] !== 'gruen') continue;
      if (filter.minAnalysts > 0 && analysts < filter.minAnalysts) continue;
    } else if (filter.kind === 'lang') {
      if (data.lang[k] === null) continue;
      if (filter.onlyGreen && data.lang_ampel[k] !== 'gruen') continue;
      if (analysts < filter.minAnalysts) continue;
    } else if (filter.kind === 'potenzial') {
      if (data.potenzial[k] === null || analysts < Math.max(1, filter.minAnalysts)) continue;
      if (filter.onlyGreen && data.lang_ampel[k] !== 'gruen') continue;
    } else if (filter.kind === 'volumen') {
      const rvol = feature(data, 'rvol', k);
      if (rvol === null || rvol < VOLUME_LIST_MIN) continue;
      if (filter.onlyGreen && data.kurz_ampel[k] !== 'gruen') continue;
      if (analysts < filter.minAnalysts) continue;
    } else {
      if (totalOf(data, k) === null) continue;
      if (filter.onlyGreen && (hasTotal(data) ? gradeOf(totalOf(data, k), data) !== 'stark' : !(data.kurz_ampel[k] === 'gruen' && data.lang_ampel[k] === 'gruen'))) continue;
      if (analysts < filter.minAnalysts) continue;
    }
    out.push(k);
  }
  const sorters: Record<ListKind, (a: number, b: number) => number> = {
    gesamt: (a, b) => (totalOf(data, b) ?? -1) - (totalOf(data, a) ?? -1) || (data.potenzial[b] ?? -9) - (data.potenzial[a] ?? -9),
    kurz: (a, b) => LIGHT_ORDER[data.kurz_ampel[a]] - LIGHT_ORDER[data.kurz_ampel[b]] || (data.kurz[b] ?? 0) - (data.kurz[a] ?? 0),
    lang: (a, b) =>
      LIGHT_ORDER[data.lang_ampel[a]] - LIGHT_ORDER[data.lang_ampel[b]] || (data.lang[b] ?? 0) - (data.lang[a] ?? 0) || (data.potenzial[b] ?? -9) - (data.potenzial[a] ?? -9),
    potenzial: (a, b) => (data.potenzial[b] ?? -9) - (data.potenzial[a] ?? -9),
    volumen: (a, b) => {
      const rising = (k: number) => ((feature(data, 'r5', k) ?? 0) > 0 ? 0 : 1);
      return rising(a) - rising(b) || (feature(data, 'rvol', b) ?? 0) - (feature(data, 'rvol', a) ?? 0);
    },
  };
  return out.sort(sorters[filter.kind]);
}

function feature(data: SignalsData, key: string, k: number): number | null {
  const value = data.merkmale[key]?.[k];
  return value === undefined || value === null || !Number.isFinite(value) ? null : value;
}

/** Bis zu vier kurze Gründe für eine Listenzeile, passend zur Liste. */
export function reasonChips(data: SignalsData, k: number, kind: ListKind): string[] {
  const chips: { text: string; weight: number }[] = [];
  const upside = data.potenzial[k];
  const analysts = data.analysten[k] ?? 0;
  if (upside !== null) chips.push({ text: `Kursziel ${f.pct(upside, 0)}${analysts ? ` (${analysts} Anal.)` : ''}`, weight: kind === 'kurz' ? 1 : 10 });
  if (kind === 'gesamt') {
    const p20 = data.gesamt_steigt_20?.[k];
    if (p20 !== null && p20 !== undefined) chips.push({ text: `Trefferquote ${f.plainPct(p20 * 100, 0)}`, weight: 4 });
  }
  const buy = data.kaufen[k];
  if (buy !== null && buy >= 0.5) chips.push({ text: `${Math.round(buy * 100)} % Kaufen`, weight: kind === 'lang' || kind === 'potenzial' ? 6 : 1 });
  const rvol = feature(data, 'rvol', k);
  if (rvol !== null && rvol >= 1.3 && kind !== 'volumen') chips.push({ text: `Umsatz ${rvol.toFixed(1).replace('.', ',')}× üblich`, weight: kind === 'kurz' ? 9 : 3 });
  if (kind === 'volumen') {
    const r1 = feature(data, 'r1', k);
    const r5 = feature(data, 'r5', k);
    if (r1 !== null) chips.push({ text: `letzte Sitzung ${f.pct(r1, 1)}`, weight: 9 });
    if (r5 !== null) chips.push({ text: `5 Sitzungen ${f.pct(r5, 1)}`, weight: 8 });
  }
  const up10 = feature(data, 'up10', k);
  if (up10 !== null && up10 >= 0.7) chips.push({ text: `${Math.round(up10 * 10)} von 10 Tagen gestiegen`, weight: kind === 'kurz' ? 8 : 2 });
  const streak = feature(data, 'serie', k);
  if (streak !== null && streak >= 3) chips.push({ text: `${streak} Tage in Folge ↑`, weight: kind === 'kurz' ? 7 : 2 });
  const r20 = feature(data, 'r20', k);
  if (r20 !== null && r20 > 0) chips.push({ text: `20 Tage ${f.pct(r20, 1)}`, weight: kind === 'kurz' ? 6 : 3 });
  const r250 = feature(data, 'r250', k);
  if (r250 !== null && r250 > 0) chips.push({ text: `1 Jahr ${f.pct(r250, 0)}`, weight: kind === 'lang' ? 5 : 1 });
  const rsi = feature(data, 'rsi', k);
  if (rsi !== null && rsi >= 55 && rsi <= 70) chips.push({ text: `RSI ${Math.round(rsi)}`, weight: kind === 'kurz' ? 4 : 0 });
  if (rsi !== null && rsi > 75) chips.push({ text: `RSI ${Math.round(rsi)} – überkauft`, weight: kind === 'kurz' ? 5 : 1 });
  return chips
    .filter((c) => c.weight > 0)
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 4)
    .map((c) => c.text);
}

/** Positive und vorhandene Signale eines Horizonts. */
export function signalCount(components: SignalComponent[], horizon: 'kurz' | 'lang'): { positive: number; negative: number; available: number } {
  const own = components.filter((c) => c.horizont === horizon && c.punkte !== null);
  return { positive: own.filter((c) => c.ton === 1).length, negative: own.filter((c) => c.ton === -1).length, available: own.length };
}

/** Ein Satz je Horizont für die Kopfzeile der Einzelansicht. */
export function verdictSentence(detail: SignalDetail, horizon: 'kurz' | 'lang', names: Record<string, string>): string {
  const light = horizon === 'kurz' ? detail.kurz_ampel : detail.lang_ampel;
  const reason = horizon === 'kurz' ? detail.kurz_grund : detail.lang_grund;
  const count = signalCount(detail.komponenten, horizon);
  if (light === 'grau') return reason ? `Kein Urteil – ${reason}.` : 'Kein Urteil – zu wenig Daten.';
  const good = detail.komponenten.filter((c) => c.horizont === horizon && c.ton === 1).map((c) => names[c.key] ?? c.key);
  const bad = detail.komponenten.filter((c) => c.horizont === horizon && c.ton === -1).map((c) => names[c.key] ?? c.key);
  const parts = [`${count.positive} von ${count.available} Signalen positiv`];
  if (good.length) parts.push(`stark: ${good.join(', ')}`);
  if (bad.length) parts.push(`schwach: ${bad.join(', ')}`);
  return `${parts.join(' – ')}.${reason ? ` ${reason[0].toUpperCase()}${reason.slice(1)}.` : ''}`;
}

/** Trefferquote der Vergangenheit als Satz (nur wenn berechnet). */
export function probabilityText(detail: SignalDetail, cal: Calibration | null | undefined): string | null {
  const p = detail.wahrscheinlichkeit;
  if (!p || p.steigt_5 === null) return null;
  const range = `${Math.round(p.bereich[0])}–${Math.round(Math.min(100, p.bereich[1]))} Punkte`;
  const five = `in 5 Handelstagen in ${f.plainPct(p.steigt_5 * 100, 0)} der Fälle (im Mittel ${f.pct(p.mittel_5, 1)})`;
  const twenty = p.steigt_20 !== null ? `, in 20 Handelstagen in ${f.plainPct(p.steigt_20 * 100, 0)} (${f.pct(p.mittel_20, 1)})` : '';
  const base =
    cal && cal.alle_steigt_5 !== null
      ? ` Zum Vergleich alle Aktien: ${f.plainPct(cal.alle_steigt_5 * 100, 0)}${cal.alle_steigt_20 !== null ? ` bzw. ${f.plainPct(cal.alle_steigt_20 * 100, 0)}` : ''}.`
      : '';
  return `Aktien mit ähnlichem kurzfristigem Bild (${range}) stiegen danach ${five}${twenty}.${base} Grundlage: ${f.integer(p.faelle)} Vergleichsfälle aus der eigenen Kurshistorie – eine Häufigkeit aus der Vergangenheit, keine Zusage.`;
}

/** Kurztext der Kursziel-Spanne. */
export function targetText(detail: SignalDetail, unit: string | null): string | null {
  if (detail.ziel === null || detail.potenzial === null) return null;
  const range =
    detail.ziel_tief !== null && detail.ziel_hoch !== null && detail.kurs
      ? ` Spanne ${f.price(detail.ziel_tief, unit)} (${f.pct(detail.ziel_tief / detail.kurs - 1, 0)}) bis ${f.price(detail.ziel_hoch, unit)} (${f.pct(detail.ziel_hoch / detail.kurs - 1, 0)}).`
      : '';
  return `Ø Kursziel ${f.price(detail.ziel, unit)} – erwartete Steigerung ${f.pct(detail.potenzial, 0)} gegenüber dem Schlusskurs ${f.price(detail.kurs, unit)}.${range}`;
}

export const ACTION_WORD: Record<string, string> = {
  hochgestuft: 'hochgestuft',
  herabgestuft: 'herabgestuft',
  bestätigt: 'bestätigt',
  'neu aufgenommen': 'neu aufgenommen',
};

/** Anteile Kaufen/Halten/Verkaufen eines Monats (0–1), null ohne Empfehlungen. */
export function ratingShares(row: { stark_kaufen: number; kaufen: number; halten: number; verkaufen: number; stark_verkaufen: number } | null | undefined) {
  if (!row) return null;
  const total = row.stark_kaufen + row.kaufen + row.halten + row.verkaufen + row.stark_verkaufen;
  if (!total) return null;
  return { kaufen: (row.stark_kaufen + row.kaufen) / total, halten: row.halten / total, verkaufen: (row.verkaufen + row.stark_verkaufen) / total, total };
}

export const MONTH_LABEL: Record<string, string> = { '0m': 'aktuell', '-1m': 'vor 1 Monat', '-2m': 'vor 2 Monaten', '-3m': 'vor 3 Monaten' };

/** Kennzahlen der Einzelansicht mit Erklärung: [Name, Wert, Erklärung]. */
export function factRows(detail: SignalDetail, unit: string | null): { group: string; rows: [string, string, string][] }[] {
  const k = detail.kennzahlen;
  if (!k) return [];
  const pct = (x: unknown, d = 0) => (typeof x === 'number' ? f.pct(x, d) : '–');
  const num = (x: unknown, d = 1) => (typeof x === 'number' ? x.toFixed(d).replace('.', ',') : '–');
  const groups: { group: string; rows: [string, string, string][] }[] = [];
  const b = k.bewertung ?? {};
  groups.push({
    group: 'Bewertung',
    rows: [
      ['KGV (letzte 12 Monate)', num(b.kgv), 'Kurs-Gewinn-Verhältnis: Kurs geteilt durch den Gewinn je Aktie der letzten 12 Monate. Niedriger = günstiger, aber nur innerhalb einer Branche vergleichbar.'],
      ['KGV erwartet', num(b.kgv_erwartet), 'Kurs geteilt durch den von Analysten erwarteten Gewinn je Aktie des nächsten Jahres. Negativ = Verlust erwartet.'],
      ['PEG', num(b.peg, 2), 'KGV geteilt durch das erwartete Gewinnwachstum. Unter 1 gilt als günstig im Verhältnis zum Wachstum, über 2 als teuer.'],
      ['Kurs-Buchwert', num(b.kbv), 'Kurs geteilt durch den Buchwert (Eigenkapital) je Aktie.'],
      ['Dividendenrendite', typeof b.dividende === 'number' ? f.plainPct(b.dividende * 100, 1) : '–', 'Jährliche Dividende im Verhältnis zum Kurs.'],
    ],
  });
  const w = k.wachstum ?? {};
  groups.push({
    group: 'Wachstum (Erwartung der Analysten)',
    rows: [
      ['Gewinn nächstes Jahr', pct(w.gewinn_naechstes_jahr), 'Erwartete Veränderung des Gewinns je Aktie im nächsten Geschäftsjahr (Schätzung der Analysten).'],
      ['Umsatz nächstes Jahr', pct(w.umsatz_naechstes_jahr), 'Erwartete Veränderung des Umsatzes im nächsten Geschäftsjahr.'],
      ['Gewinn dieses Jahr', pct(w.gewinn_dieses_jahr), 'Erwartete Veränderung des Gewinns je Aktie im laufenden Geschäftsjahr.'],
      ['Umsatz letztes Quartal', pct(w.umsatz_quartal), 'Umsatz des letzten Quartals gegenüber dem Vorjahresquartal (tatsächlich, keine Schätzung).'],
    ],
  });
  const fin = k.finanzen ?? {};
  groups.push({
    group: 'Finanzen',
    rows: [
      ['Nettomarge', pct(fin.nettomarge), 'Gewinn in Prozent des Umsatzes.'],
      ['Eigenkapitalrendite', pct(fin.eigenkapitalrendite), 'Gewinn im Verhältnis zum Eigenkapital – wie viel das Unternehmen aus dem Geld der Aktionäre macht.'],
      ['Verschuldung', typeof fin.verschuldung === 'number' ? `${num(fin.verschuldung, 2)}× Eigenkapital` : '–', 'Schulden im Verhältnis zum Eigenkapital. Über 2 gilt in den meisten Branchen als hoch.'],
      ['Freier Cashflow', fin.free_cashflow_positiv === true ? 'positiv' : fin.free_cashflow_positiv === false ? 'negativ' : '–', 'Geld, das nach Investitionen übrig bleibt. Negativ heißt: Das Unternehmen verbraucht Geld.'],
    ],
  });
  const r = k.risiko ?? {};
  groups.push({
    group: 'Risiko und Termine',
    rows: [
      ['Beta', num(r.beta, 2), 'Schwankung im Vergleich zum Gesamtmarkt: 1 = wie der Markt, 2 = doppelt so stark.'],
      ['Leerverkaufsquote', typeof r.leerverkauf === 'number' ? f.plainPct(r.leerverkauf * 100, 1) : '–', 'Anteil der frei handelbaren Aktien, die auf fallende Kurse gesetzt sind (nur US-Aktien).'],
      ['52-Wochen-Spanne', typeof r.tief_52w === 'number' && typeof r.hoch_52w === 'number' ? `${f.price(r.tief_52w, unit)} – ${f.price(r.hoch_52w, unit)}` : '–', 'Tiefster und höchster Kurs der letzten 52 Wochen laut Kursanbieter.'],
      ['Nächste Zahlen', k.termine?.zahlen ? f.day(k.termine.zahlen) : '–', 'Voraussichtlicher Termin der nächsten Geschäftszahlen – rund um diesen Tag schwanken Kurse oft stark.'],
    ],
  });
  return groups.map((g) => ({ ...g, rows: g.rows.filter((row) => row[1] !== '–') })).filter((g) => g.rows.length);
}

export function sectorName(name: string | null | undefined): string {
  const map: Record<string, string> = {
    Technology: 'Technologie',
    Healthcare: 'Gesundheit',
    Industrials: 'Industrie',
    'Financial Services': 'Finanzen',
    'Consumer Cyclical': 'Zyklischer Konsum',
    'Consumer Defensive': 'Basiskonsum',
    'Communication Services': 'Kommunikation',
    Energy: 'Energie',
    'Basic Materials': 'Rohstoffe',
    'Real Estate': 'Immobilien',
    Utilities: 'Versorger',
  };
  return name ? map[name] ?? name : '–';
}

// ------------------------------------------------------------------ Texte für die Einzelansicht (ab 1.7.1)

function ratingCounts(row: { stark_kaufen: number; kaufen: number; halten: number; verkaufen: number; stark_verkaufen: number } | null | undefined) {
  if (!row) return null;
  const buy = row.stark_kaufen + row.kaufen;
  const sell = row.verkaufen + row.stark_verkaufen;
  const total = buy + row.halten + sell;
  return total ? { buy, hold: row.halten, sell, total, share: buy / total } : null;
}

/** Größte Zahl der Analysten über alle Kursziel-Quellen. */
export function analystCount(detail: SignalDetail): number {
  return Math.max(detail.kennzahlen?.analysten?.anzahl ?? 0, ...detail.ziel_quellen.map((q) => q.anzahl ?? 0), 0);
}

/** „Was die Analysten denken“: Sätze aus Empfehlungen, Kurszielen, Urteilen der Häuser, Bewertung und Prognosen. */
export function analystSummary(detail: SignalDetail, unit: string | null): string[] {
  const out: string[] = [];
  const months = detail.kennzahlen?.empfehlungen ?? [];
  const now = ratingCounts(months.find((m) => m.monat === '0m'));
  const oldRow = months.find((m) => m.monat === '-3m') ?? months.find((m) => m.monat === '-2m') ?? null;
  const old = ratingCounts(oldRow);
  const analysts = analystCount(detail);
  if (!now && detail.potenzial === null) {
    return ['Für diese Aktie liegen keine Einschätzungen von Analysten vor – bei kleineren Werten oft, weil keine Bank sie beobachtet.'];
  }
  if (now) {
    let text = `${now.buy} von ${now.total} Analysten empfehlen Kaufen (${f.plainPct(now.share * 100, 0)}), ${now.hold} Halten, ${now.sell ? `${now.sell} Verkaufen` : 'keiner Verkaufen'}`;
    if (old && oldRow) {
      const when = oldRow.monat === '-3m' ? 'vor drei Monaten' : 'vor zwei Monaten';
      const diff = now.share - old.share;
      text +=
        diff >= 0.05
          ? ` – ${when} waren es ${f.plainPct(old.share * 100, 0)}: Die Analysten sind optimistischer geworden.`
          : diff <= -0.05
            ? ` – ${when} waren es ${f.plainPct(old.share * 100, 0)}: Die Analysten sind vorsichtiger geworden.`
            : ` – ähnlich wie ${when}.`;
    } else {
      text += '.';
    }
    out.push(text);
  }
  if (detail.ziel !== null && detail.potenzial !== null && detail.kurs) {
    const dir = detail.potenzial >= 0 ? `${f.plainPct(detail.potenzial * 100, 0)} über` : `${f.plainPct(-detail.potenzial * 100, 0)} unter`;
    let text = `Im Durchschnitt erwarten ${analysts ? `die ${f.plural(analysts, 'Analyst', 'Analysten')} mit Kursziel` : 'die Analysten'} in etwa 12 Monaten einen Kurs von ${f.price(detail.ziel, unit)} – ${dir} dem aktuellen Kurs`;
    if (detail.ziel_tief !== null && detail.ziel_hoch !== null) {
      text += `; das vorsichtigste Ziel liegt bei ${f.price(detail.ziel_tief, unit)} (${f.pct(detail.ziel_tief / detail.kurs - 1, 0)}), das höchste bei ${f.price(detail.ziel_hoch, unit)} (${f.pct(detail.ziel_hoch / detail.kurs - 1, 0)})`;
    }
    out.push(`${text}.`);
    if (detail.ziel_quellen.length > 1) {
      out.push(`Die ${detail.ziel_quellen.length} Quellen (${detail.ziel_quellen.map((q) => q.quelle.replace(/ \(.*\)$/, '')).join(', ')}) liegen zwischen ${f.pct(Math.min(...detail.ziel_quellen.map((q) => q.ziel)) / detail.kurs - 1, 0)} und ${f.pct(Math.max(...detail.ziel_quellen.map((q) => q.ziel)) / detail.kurs - 1, 0)}.`);
    }
  }
  const actions = (detail.kennzahlen?.urteile ?? []).filter((a) => a.tag !== null);
  if (actions.length) {
    const up = actions.filter((a) => a.ziel_aktion === 'angehoben').length;
    const down = actions.filter((a) => a.ziel_aktion === 'gesenkt').length;
    const upgrades = actions.filter((a) => a.aktion === 'hochgestuft').length;
    const downgrades = actions.filter((a) => a.aktion === 'herabgestuft').length;
    const since = Math.min(...actions.map((a) => a.tag as number));
    const parts = [
      up || down ? `${up} ${up === 1 ? 'Kursziel' : 'Kursziele'} angehoben und ${down} gesenkt` : null,
      upgrades ? `${upgrades} ${upgrades === 1 ? 'Hochstufung' : 'Hochstufungen'}` : null,
      downgrades ? `${downgrades} ${downgrades === 1 ? 'Herabstufung' : 'Herabstufungen'}` : null,
    ].filter(Boolean);
    if (parts.length) out.push(`Bei den letzten ${f.plural(actions.length, 'Urteil', 'Urteilen')} der Analystenhäuser (seit ${f.day(since)}): ${parts.join(', ')}.`);
  }
  const tc = detail.bewertung_tc;
  if (tc?.bewertung) {
    const word = tc.bewertung === 'unterbewertet' ? 'unterbewertet' : tc.bewertung === 'ueberbewertet' ? 'überbewertet' : 'fair bewertet';
    const gap = tc.abschlag !== null && tc.bewertung !== 'fair' ? ` (${f.plainPct(Math.abs(tc.abschlag) * 100, 0)} ${tc.abschlag >= 0 ? 'unter' : 'über'} dem geschätzten fairen Wert)` : '';
    out.push(`Trading Central hält die Aktie für ${word}${gap}.`);
  }
  const w = detail.kennzahlen?.wachstum;
  const eps = typeof w?.gewinn_naechstes_jahr === 'number' ? w.gewinn_naechstes_jahr : null;
  const rev = typeof w?.umsatz_naechstes_jahr === 'number' ? w.umsatz_naechstes_jahr : null;
  if (eps !== null || rev !== null) {
    out.push(
      `Für das nächste Geschäftsjahr erwarten sie ${[eps !== null ? `beim Gewinn je Aktie ${f.pct(eps, 0)}` : null, rev !== null ? `beim Umsatz ${f.pct(rev, 0)}` : null].filter(Boolean).join(' und ')}.`,
    );
  }
  const next = detail.kennzahlen?.termine?.zahlen ?? null;
  if (next !== null && detail.kurs_tag !== null && next >= detail.kurs_tag) out.push(`Die nächsten Geschäftszahlen kommen voraussichtlich am ${f.day(next)}.`);
  return out;
}

/** Was für und was gegen die Aktie spricht – aus den Signalen mit klarer Richtung, Steig-Konstanz, Kursziel und Terminen. */
export function proContra(detail: SignalDetail, names: Record<string, string>): { pro: string[]; contra: string[] } {
  const pro: string[] = [];
  const contra: string[] = [];
  const cells = detailConsistency(detail.konstanz);
  const good = cells.filter((c) => c.ton === 'pos');
  const bad = cells.filter((c) => c.ton === 'neg');
  if (good.length) pro.push(`Oft gestiegen: an ${good.map((c, i) => `${c.auf} von ${c.von}${i === 0 ? ' Handelstagen' : ''} (${c.tage} Tage)`).join(', ')}`);
  if (bad.length) contra.push(`Selten gestiegen oder gefallen: ${bad.map((c) => `${c.tage} Tage – ${c.auf} von ${c.von} Handelstagen, Kurs ${f.pct(c.rendite, 0)}`).join('; ')}`);
  const analysts = analystCount(detail);
  if (detail.potenzial !== null) {
    if (detail.potenzial >= 0.1) pro.push(`Kursziel ${f.pct(detail.potenzial, 0)} über dem Kurs (${f.plural(analysts, 'Analyst', 'Analysten')})`);
    else if (detail.potenzial < 0) contra.push(`Kursziel ${f.pct(detail.potenzial, 0)} – unter dem aktuellen Kurs`);
    if (analysts > 0 && analysts < 3) contra.push(`Nur ${f.plural(analysts, 'Analyst', 'Analysten')} – das Kursziel ist unsicher`);
  }
  const rsi = typeof detail.merkmale.rsi === 'number' ? (detail.merkmale.rsi as number) : null;
  for (const c of detail.komponenten) {
    if (c.key === 'kursziel' || c.punkte === null) continue;
    const label = `${names[c.key] ?? c.key}: ${c.text}`;
    if (c.key === 'rsi' && rsi !== null && rsi > 75) {
      contra.push(`${names.rsi ?? 'RSI'}: ${Math.round(rsi)} – überkauft, Rücksetzer werden häufiger`);
      continue;
    }
    if (c.ton === 1) pro.push(label);
    else if (c.ton === -1) contra.push(label);
  }
  const next = detail.kennzahlen?.termine?.zahlen ?? null;
  if (next !== null && detail.kurs_tag !== null && next >= detail.kurs_tag && next - detail.kurs_tag <= 14) {
    contra.push(`Geschäftszahlen am ${f.day(next)} – an solchen Tagen schwankt der Kurs oft stark`);
  }
  if (!detail.handelbar) contra.push('Wenig Umsatz (unter 250.000 € am Tag) – kurzfristig schwer zu handeln');
  return { pro: pro.slice(0, 7), contra: contra.slice(0, 7) };
}

export interface TraderCheck {
  key: string;
  label: string;
  value: string;
  /** true = spricht dafür, false = spricht dagegen, null = neutral oder keine Daten */
  ok: boolean | null;
  why: string;
}

function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/** Anteil der Aktien mit kleinerem Wert (0–100), nur bei mindestens 20 Vergleichswerten. */
export function percentileOf(values: (number | null)[] | undefined, x: number | null): number | null {
  if (!values || x === null) return null;
  const ok = values.filter((v): v is number => v !== null && Number.isFinite(v));
  if (ok.length < 20) return null;
  let below = 0;
  let equal = 0;
  for (const v of ok) {
    if (v < x) below++;
    else if (v === x) equal++;
  }
  return ((below + equal / 2) / ok.length) * 100;
}

/** Daytrader-Check: worauf kurzfristige Händler achten, mit dem Wert dieser Aktie und einer kurzen Begründung. */
export function dayTraderChecks(detail: SignalDetail, data: SignalsData | null): TraderCheck[] {
  const m = detail.merkmale;
  const close = detail.kurs;
  const out: TraderCheck[] = [];
  const turnover = num(m.umsatz_eur);
  out.push({
    key: 'umsatz',
    label: 'Liquidität',
    value: turnover === null ? 'unbekannt' : `Ø ${f.money(turnover, '€')} Umsatz am Tag`,
    ok: turnover === null ? null : turnover >= 1_000_000 ? true : turnover < 250_000 ? false : null,
    why: 'Daytrader handeln Aktien mit hohem Umsatz: Orders werden sofort ausgeführt und der Abstand zwischen Kauf- und Verkaufskurs (Spread) ist klein. Ab etwa 1 Mio. € am Tag gut, unter 250.000 € schwierig.',
  });
  const rvol = num(m.rvol);
  out.push({
    key: 'rvol',
    label: 'Relatives Volumen',
    value: rvol === null ? 'unbekannt' : `${rvol.toFixed(1).replace('.', ',')}× des Üblichen`,
    ok: rvol === null ? null : rvol >= 1.5 ? true : rvol < 0.8 ? false : null,
    why: 'Umsatz der letzten Sitzung im Verhältnis zum 20-Tage-Durchschnitt. Ab dem 1,5-Fachen ist ungewöhnlich viel los – für Daytrader die wichtigste Größe, weil Bewegung Umsatz braucht.',
  });
  const atr = num(m.atr);
  out.push({
    key: 'atr',
    label: 'Tagesspanne (ATR)',
    value: atr === null ? 'unbekannt' : `Ø ${f.plainPct(atr * 100, 1)} pro Tag`,
    ok: atr === null ? null : atr >= 0.02 && atr <= 0.12 ? true : atr < 0.01 ? false : null,
    why: 'Wie weit sich der Kurs an einem Tag üblicherweise bewegt (Mittel der letzten 14 Tagesspannen). Ohne Bewegung kein Gewinn – 2 bis 12 % sind für Daytrader typisch, mehr bedeutet großes Risiko.',
  });
  const gap = num(m.gap);
  out.push({
    key: 'gap',
    label: 'Kurslücke zur Eröffnung',
    value: gap === null ? 'unbekannt' : `${f.pct(gap, 1)} gegenüber dem Vortagesschluss`,
    ok: gap === null ? null : gap >= 0.02 ? true : gap <= -0.02 ? false : null,
    why: 'Öffnet die Aktie deutlich über dem Schlusskurs des Vortags („Gap up“), steckt meist eine Nachricht dahinter – Daytrader handeln solche Lücken gezielt. Eine Lücke nach unten zeigt Verkaufsdruck.',
  });
  const s20 = num(m.sma20);
  const s50 = num(m.sma50);
  out.push({
    key: 'trend',
    label: 'Trend',
    value: close === null || s20 === null || s50 === null ? 'zu kurze Historie' : close > s20 && close > s50 ? 'über der 20- und 50-Tage-Linie' : close < s20 && close < s50 ? 'unter der 20- und 50-Tage-Linie' : 'zwischen den Durchschnittslinien',
    ok: close === null || s20 === null || s50 === null ? null : close > s20 && close > s50 ? true : close < s20 && close < s50 ? false : null,
    why: 'Daytrader handeln bevorzugt in Richtung des Trends. Liegt der Kurs über dem Durchschnitt der letzten 20 und 50 Tage, überwiegen die Käufer.',
  });
  const high20 = num(m.hoch20);
  const dist = close !== null && high20 ? close / high20 - 1 : null;
  out.push({
    key: 'hoch',
    label: 'Ausbruch',
    value: dist === null ? 'zu kurze Historie' : dist >= -0.0001 ? 'neues 20-Tage-Hoch' : `${f.pct(dist, 1)} unter dem 20-Tage-Hoch`,
    ok: dist === null ? null : dist >= -0.02 ? true : dist <= -0.1 ? false : null,
    why: 'Steigt der Kurs über das Hoch der letzten 20 Tage („Breakout“), kommen oft weitere Käufer hinzu. Nahe am Hoch heißt: Die Stärke hält an.',
  });
  const rsi = num(m.rsi);
  out.push({
    key: 'rsi',
    label: 'RSI (14)',
    value: rsi === null ? 'unbekannt' : `${Math.round(rsi)}${rsi > 75 ? ' – überkauft' : rsi < 40 ? ' – schwach' : ''}`,
    ok: rsi === null ? null : rsi >= 50 && rsi <= 72 ? true : rsi > 78 || rsi < 40 ? false : null,
    why: 'Relative Stärke der letzten 14 Tage (0–100). 50–70: kräftig, aber nicht überhitzt. Über 75 gilt die Aktie als überkauft – Rücksetzer werden wahrscheinlicher.',
  });
  const r20 = num(m.r20);
  const pctile = percentileOf(data?.merkmale.r20, r20);
  out.push({
    key: 'staerke',
    label: 'Relative Stärke (20 Tage)',
    value: r20 === null ? 'unbekannt' : `${f.pct(r20, 1)}${pctile !== null ? ` – besser als ${Math.round(pctile)} % der Aktien` : ''}`,
    ok: pctile === null ? null : pctile >= 70 ? true : pctile <= 30 ? false : null,
    why: 'Daytrader suchen die stärksten Werte: Aktien, die in den letzten 20 Handelstagen besser gelaufen sind als die meisten anderen.',
  });
  const up10 = num(m.up10);
  const streak = num(m.serie);
  out.push({
    key: 'serie',
    label: 'Steigetage',
    value: up10 === null ? 'unbekannt' : `${Math.round(up10 * 10)} von 10 Tagen gestiegen${streak !== null && streak >= 2 ? `, ${streak} in Folge` : streak !== null && streak <= -2 ? `, ${-streak} Falltage in Folge` : ''}`,
    ok: up10 === null ? null : up10 >= 0.6 ? true : up10 <= 0.3 ? false : null,
    why: 'Steigt eine Aktie an vielen Tagen hintereinander, ist sie gerade gefragt – mehr Käufer als Verkäufer.',
  });
  const news = (m.nachrichten ?? null) as null | { meldungen_3_tage?: number; positiv?: number; negativ?: number };
  const nNews = news?.meldungen_3_tage ?? 0;
  out.push({
    key: 'nachrichten',
    label: 'Anlass (Nachrichten)',
    value: nNews ? `${f.plural(nNews, 'Meldung', 'Meldungen')} in 3 Tagen (${news?.positiv ?? 0} positiv, ${news?.negativ ?? 0} negativ)` : 'keine aktuellen Meldungen',
    ok: !nNews ? null : (news?.positiv ?? 0) > (news?.negativ ?? 0) ? true : (news?.negativ ?? 0) > (news?.positiv ?? 0) ? false : null,
    why: 'Starke Bewegungen brauchen einen Anlass („Katalysator“): Geschäftszahlen, Analystenurteile, Übernahmen, neue Produkte. Die Einordnung positiv/negativ ist eine einfache Wortliste.',
  });
  const next = detail.kennzahlen?.termine?.zahlen ?? null;
  const days = next !== null && detail.kurs_tag !== null ? next - detail.kurs_tag : null;
  out.push({
    key: 'zahlen',
    label: 'Nächste Geschäftszahlen',
    value: next === null || days === null || days < 0 ? 'kein Termin bekannt' : `${f.day(next)} (in ${f.plural(days, 'Tag', 'Tagen')})`,
    ok: days !== null && days >= 0 && days <= 3 ? false : null,
    why: 'Am Tag der Zahlen springt der Kurs oft stark – nach oben oder unten. Für Daytrader Chance und Risiko zugleich; kurz davor halten viele keine Positionen über Nacht.',
  });
  const short = num(detail.kennzahlen?.risiko?.leerverkauf ?? null);
  if (short !== null) {
    out.push({
      key: 'short',
      label: 'Leerverkaufsquote',
      value: `${f.plainPct(short * 100, 1)} der frei handelbaren Aktien${short >= 0.15 ? ' – hoch' : ''}`,
      ok: null,
      why: 'Anteil der Aktien, mit denen auf fallende Kurse gesetzt wird (nur US-Aktien). Hoch heißt: viel Skepsis – steigt der Kurs trotzdem, müssen Leerverkäufer zurückkaufen und verstärken den Anstieg („Short Squeeze“).',
    });
  }
  const c = detail.community;
  if (c) {
    const tagged = c.bullish + c.bearish;
    const share = tagged ? c.bullish / tagged : null;
    out.push({
      key: 'community',
      label: 'Aufmerksamkeit (Community)',
      value: `${c.je_tag !== null ? `${c.je_tag.toFixed(c.je_tag < 10 ? 1 : 0).replace('.', ',')} Beiträge am Tag` : `${c.beitraege} Beiträge`}${share !== null ? `, ${Math.round(share * 100)} % bullish` : ''}`,
      ok: share === null || tagged < 3 ? null : share >= 0.6 ? true : share <= 0.4 ? false : null,
      why: 'Viel Aufmerksamkeit in sozialen Medien bringt Käufer – Hype endet aber oft abrupt. Gezählt auf Stocktwits (nur US-Aktien).',
    });
  }
  return out;
}

/** Zusammenfassung des Daytrader-Checks: erfüllt / dagegen / bewertbar. */
export function traderTally(checks: TraderCheck[]): { good: number; bad: number; rated: number } {
  const rated = checks.filter((c) => c.ok !== null);
  return { good: rated.filter((c) => c.ok).length, bad: rated.filter((c) => c.ok === false).length, rated: rated.length };
}
