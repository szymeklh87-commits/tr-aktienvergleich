/* Signale je Aktie (ab 1.6, `signale-v1`): Sortierung, Filter, kurze Gründe und Sätze für die Anzeige.
 *
 * Die App rechnet keine Signale nach – sie ordnet und beschreibt nur, was der Server berechnet hat.
 * Reine Funktionen, damit sie ohne Browser getestet werden können. */

import * as f from './format';
import type { Calibration, Light, SignalComponent, SignalDetail, SignalsData } from './types';

export type ListKind = 'beide' | 'kurz' | 'lang' | 'potenzial';

export const LIGHT_WORD: Record<Light, string> = { gruen: 'grün', gelb: 'gelb', rot: 'rot', grau: 'grau' };
export const LIGHT_MEANING: Record<Light, string> = {
  gruen: 'Signale überwiegend positiv',
  gelb: 'gemischt',
  rot: 'Signale überwiegend negativ',
  grau: 'zu wenig Daten',
};
const LIGHT_ORDER: Record<Light, number> = { gruen: 0, gelb: 1, grau: 2, rot: 3 };

export const LIST_INFO: Record<ListKind, { label: string; title: string; text: string }> = {
  beide: {
    label: 'Beides stark',
    title: 'Kurz- und langfristig stark',
    text: 'Zuerst Aktien, bei denen beide Ampeln grün sind; danach nach dem Mittel beider Punktzahlen.',
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
      if (data.kurz[k] === null || data.lang[k] === null) continue;
      if (filter.onlyGreen && !(data.kurz_ampel[k] === 'gruen' && data.lang_ampel[k] === 'gruen')) continue;
      if (analysts < filter.minAnalysts) continue;
    }
    out.push(k);
  }
  const both = (k: number) => (data.kurz_ampel[k] === 'gruen' && data.lang_ampel[k] === 'gruen' ? 0 : 1);
  const sorters: Record<ListKind, (a: number, b: number) => number> = {
    beide: (a, b) => both(a) - both(b) || (mean([data.kurz[b], data.lang[b]]) ?? 0) - (mean([data.kurz[a], data.lang[a]]) ?? 0),
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
