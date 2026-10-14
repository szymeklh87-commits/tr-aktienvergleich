/* Signale je Aktie (ab 1.6, `signale-v1`; Gesamtwertung ab 1.7, `signale-v2`): Sortierung, Filter, kurze
 * Gründe und Sätze für die Anzeige.
 *
 * Die App rechnet keine Signale nach – sie ordnet und beschreibt nur, was der Server berechnet hat.
 * Reine Funktionen, damit sie ohne Browser getestet werden können. */

import * as f from './format';
import type { Calibration, ConsistencyCalibration, ConsistencyPeriod, Light, SignalComponent, SignalDetail, SignalsData, TotalGrade, TotalPart } from './types';

/** „gesamt“ (ab 1.7) ersetzt die frühere Liste „beide“ – alte Links mit ``liste=beide`` führen dorthin. */
export type ListKind = 'gesamt' | 'kurz' | 'lang' | 'potenzial';
export const LIST_KINDS: ListKind[] = ['gesamt', 'kurz', 'lang', 'potenzial'];

export function parseListKind(value: string | null | undefined): ListKind {
  return value === 'kurz' || value === 'lang' || value === 'potenzial' ? value : 'gesamt';
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
    text: 'Sortiert nach der Gesamtwertung (0–100): Steig-Konstanz über 30, 60 und 90 Tage (35 %), Kursziel-Potenzial (35 %), Aufmerksamkeit & Schwung (15 %) und Qualität (15 %). ▲ 15/21 heißt: an 15 von 21 Handelstagen gestiegen.',
  },
  kurz: {
    label: 'Kurzfristig',
    title: 'Kurzfristig stark (Trading)',
    text: 'Nach dem kurzfristigen Urteil: Umsatz, Schwung, Steigetage, Trendlage, Ausbruch, RSI, Nachrichten und Community. Nur Aktien mit mindestens 250.000 € Umsatz am Tag.',
  },
  lang: {
    label: 'Langfristig',
    title: 'Langfristig stark (etwa 12 Monate)',
    text: 'Nach dem langfristigen Urteil: Kursziel der Analysten, Bewertung, Wachstum und Finanzen, langfristiger Trend, Richtung der Analysten.',
  },
  potenzial: {
    label: 'Kursziel',
    title: 'Höchste erwartete Steigerung',
    text: 'Nach der erwarteten Steigerung bis zum durchschnittlichen Kursziel der Analysten – ohne die übrigen Signale. Hohe Werte bei wenigen Analysten sind unsicher.',
  },
};

export interface SignalFilter {
  kind: ListKind;
  minAnalysts: number;
  onlyGreen: boolean;
  liquidOnly: boolean;
  sector: number | null;
}

export function signalIndex(data: SignalsData): Map<string, number> {
  const map = new Map<string, number>();
  data.isin.forEach((isin, k) => map.set(isin, k));
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
  if (rvol !== null && rvol >= 1.3) chips.push({ text: `Umsatz ${rvol.toFixed(1).replace('.', ',')}× üblich`, weight: kind === 'kurz' ? 9 : 3 });
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
