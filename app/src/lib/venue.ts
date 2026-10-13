/* Abgleich mit einem zweiten Börsenplatz (ab Version 1.2 `boersenplatz-v1`, ab 1.5.1 `boersenplatz-v2`).
 *
 * Für die Aktien unter den ersten Plätzen der Rendite-Ranglisten misst der Server die Kursrendite
 * zusätzlich an einem zweiten Handelsplatz derselben ISIN (bevorzugt Xetra, dann Frankfurt) und
 * vergleicht in der Währung der Referenznotierung. Die App zeigt das Ergebnis nur an; sie rechnet
 * nichts nach und ändert keine Rangfolge.
 */

import * as f from './format';
import type { Instruments, Manifest, VenueSummary, WindowData } from './types';

/** Welcher Schlusskurs des zweiten Platzes zählt – je nach Version des Abgleichs im Datenstand.
 *  v1: letzter gelieferter Kurs bis N Tage vorher; ab v2: Kurs genau des Tages, wenn dort gehandelt
 *  wurde (Lieferlücke des Kursanbieters → kein Vergleich). */
export function venueDayRule(venue: Pick<VenueSummary, 'version' | 'max_abstand_tage' | 'nur_mit_umsatz'> | null | undefined): string {
  const days = venue?.max_abstand_tage ?? 4;
  if (venue?.version === 'boersenplatz-v1') {
    return `Schlusskurs am letzten Handelstag am oder vor dem Start- und dem Enddatum, höchstens ${days} Tage früher.`;
  }
  const traded = venue?.nur_mit_umsatz ? ' Ohne Umsatz dort an einem dieser Tage ist der Kurs nur fortgeschrieben und wird nicht verglichen.' : '';
  return (
    `Schlusskurs genau vom Start- und vom Enddatum; hatte der Platz an einem dieser Tage keinen Handel, der der letzten Sitzung davor ` +
    `(höchstens ${days} Tage früher). Fehlt ein solcher Schlusskurs beim Kursanbieter, entfällt der Vergleich.${traded}`
  );
}

type LimitSettings = Pick<VenueSummary, 'schwelle_wertentwicklung' | 'schwankung_faktor' | 'schwankung_sitzungen' | 'schwelle_hoechstens'>;

/** Satz für „So wird gerechnet“: wann ein Zeitraum auffällig ist (ab boersenplatz-v3 Schwelle nach Tagesschwankung). */
export function venueLimitSentence(venue: LimitSettings | null | undefined): string {
  const base = Math.round((venue?.schwelle_wertentwicklung ?? 0.1) * 100);
  const z = venue?.schwankung_faktor ?? 0;
  if (!venue || z <= 0) return `Auffällig ist ein Zeitraum, wenn diese Abweichung oder die Abweichung des Endkurses mehr als ${base} % beträgt.`;
  const cap = venue.schwelle_hoechstens ?? 1;
  return (
    `Auffällig ist ein Zeitraum, wenn diese Abweichung oder die Abweichung des Endkurses die Schwelle der Aktie übersteigt: mindestens ${base} %, ` +
    `bei stark schwankenden Aktien das ${f.integer(z)}-Fache ihrer üblichen Tagesschwankung der letzten ${f.integer(venue.schwankung_sitzungen ?? 20)} Tage ` +
    `(bei der Wertentwicklung zusätzlich × √2, weil Start- und Endkurs betroffen sind). Die Schlusszeiten der Börsenplätze liegen Stunden auseinander; ` +
    `bei stark schwankenden Aktien erklärt das allein große Abweichungen. Ab ${f.integer(cap * 100)} % (Faktor ${f.integer(1 + cap)}) ist eine Abweichung immer auffällig.`
  );
}

/** Kurzfassung für „Datenstand & Betrieb“. */
export function venueLimitShort(venue: LimitSettings | null | undefined): string {
  const base = Math.round((venue?.schwelle_wertentwicklung ?? 0.1) * 100);
  const z = venue?.schwankung_faktor ?? 0;
  if (!venue || z <= 0) return `Abweichung über ${base} % bei Wertentwicklung oder Endkurs`;
  return `Abweichung über der Schwelle der Aktie: mindestens ${base} %, nach üblicher Tagesschwankung bis ${f.integer((venue.schwelle_hoechstens ?? 1) * 100)} %`;
}

export interface VenueInfo {
  status: string;
  symbol: string | null;
  exchange: string | null;
  currency: string | null;
  priceUnit: string | null;
  level: number | null;
  levelFlag: boolean;
  endDay: number | null;
  endPrice: number | null;
  /** ab boersenplatz-v3 */
  noise: number | null;
  limitR: number | null;
  limitL: number | null;
}

export interface VenuePair {
  status: string;
  r: number | null;
  dev: number | null;
  d0: number | null;
  d1: number | null;
  p0: number | null;
  p1: number | null;
}

export function venueOf(instruments: Instruments | null, idx: number): VenueInfo | null {
  const v = instruments?.venue;
  if (!v) return null;
  const k = v.idx.indexOf(idx);
  if (k < 0) return null;
  return {
    status: v.status[k],
    symbol: v.symbol[k],
    exchange: v.exchange[k],
    currency: v.currency[k],
    priceUnit: v.price_unit[k],
    level: v.level[k],
    levelFlag: Boolean(v.level_flag[k]),
    endDay: v.end_day[k],
    endPrice: v.end_price[k],
    noise: v.noise?.[k] ?? null,
    limitR: v.limit_r?.[k] ?? null,
    limitL: v.limit_l?.[k] ?? null,
  };
}

export function venuePair(win: WindowData | null, idx: number): VenuePair | null {
  const xv = win?.xv;
  if (!xv) return null;
  const k = xv.idx.indexOf(idx);
  if (k < 0) return null;
  return { status: xv.status[k], r: xv.r[k], dev: xv.dev[k], d0: xv.d0[k], d1: xv.d1[k], p0: xv.p0[k], p1: xv.p1[k] };
}

/** Wurde der Abgleich in diesem Datenstand überhaupt ausgeführt? */
export function venueCheckAvailable(manifest: Manifest | null): boolean {
  const check = manifest?.venue_check;
  return Boolean(check && check.anzahl && !check.abgebrochen && !check.hinweis?.includes('nicht eingerichtet'));
}

function pct(x: number): string {
  return f.pct(x);
}

/** „8,0 %“ ohne Vorzeichen (Tagesschwankung) */
function pct0(x: number): string {
  return f.plainPct(x * 100, 1);
}

/** Überschrift: „Xetra (APC.DE)“ */
export function venueLabel(info: VenueInfo): string {
  const symbol = info.symbol ? ` (${info.symbol})` : '';
  return `${info.exchange ?? 'zweiter Börsenplatz'}${symbol}`;
}

/** Eine Zeile für Ranglisten: „Vergleich mit Börse Frankfurt (S194.F): unauffällig, dort +58,10 %“.
 *  Leer, wenn die Aktie nicht geprüft wurde oder das Ergebnis für diesen Zeitraum nicht vorliegt. */
export function venueListText(manifest: Manifest | null, info: VenueInfo | null, pair: VenuePair | null | undefined): string {
  if (!info || !venueCheckAvailable(manifest)) return '';
  const where = info.symbol ? `Vergleich mit ${venueLabel(info)}` : 'Vergleich mit zweitem Börsenplatz';
  if (info.status !== 'geprueft') return `${where}: ${manifest?.codes.venue_status?.[info.status]?.kurz ?? info.status}`;
  if (!pair) return '';
  if (pair.status === 'ok') return `${where}: unauffällig${pair.r !== null ? `, dort ${pct(pair.r)}` : ''}`;
  if (pair.status === 'abweichung') {
    const parts = [pair.r !== null ? `dort ${pct(pair.r)}` : '', info.levelFlag && info.level !== null ? `Endkurs ${pct(info.level)}` : ''].filter(Boolean);
    return `${where}: auffällige Abweichung${parts.length ? ` – ${parts.join(', ')}` : ''}`;
  }
  return `${where}: ${manifest?.codes.venue_pair_status?.[pair.status]?.kurz ?? pair.status}`;
}

/** Kurzfassung für die Einzelansicht. */
export function venueShort(manifest: Manifest | null, info: VenueInfo | null, pair: VenuePair | null): string {
  if (!venueCheckAvailable(manifest)) return 'In diesem Datenstand nicht abgeglichen';
  const top = manifest?.venue_check?.plaetze ?? 10;
  if (!info) return `Nicht geprüft – abgeglichen werden die ersten ${top} Plätze beider Rendite-Ranglisten`;
  if (info.status !== 'geprueft') return manifest?.codes.venue_status?.[info.status]?.kurz ?? info.status;
  if (!pair) return 'In diesem Zeitraum ohne Rendite – kein Abgleich';
  const text = manifest?.codes.venue_pair_status?.[pair.status]?.kurz ?? pair.status;
  return pair.status === 'abweichung' ? `Auffällig: ${text}` : text;
}

/** Ausführliche Zeilen für die Einzelansicht (ohne erfundene Werte: fehlende Angaben bleiben weg). */
export function venueDetails(manifest: Manifest | null, info: VenueInfo | null, pair: VenuePair | null, refCurrency: string | null, refReturn: number | null): string[] {
  if (!info || !venueCheckAvailable(manifest)) return [];
  const lines: string[] = [];
  if (info.status !== 'geprueft') {
    const text = manifest?.codes.venue_status?.[info.status]?.text;
    if (info.symbol) lines.push(venueLabel(info));
    if (text) lines.push(text);
    return lines;
  }
  const unit = info.priceUnit ?? info.currency ?? '';
  lines.push(`${venueLabel(info)}, Kurse in ${unit}`);
  if (pair && pair.r !== null && pair.d0 !== null && pair.d1 !== null) {
    const converted = info.currency && refCurrency && info.currency !== refCurrency ? ` (in ${refCurrency} umgerechnet, EZB-Referenzkurse)` : '';
    lines.push(`Kursrendite dort ${f.dayShort(pair.d0)}–${f.day(pair.d1)}: ${pct(pair.r)}${converted}`);
    if (refReturn !== null && pair.dev !== null) {
      lines.push(`Referenzbörse: ${pct(refReturn)}; Unterschied der Wertentwicklung ${pct(pair.dev)}`);
    }
    if (pair.p0 !== null && pair.p1 !== null) lines.push(`Schlusskurse dort: ${f.price(pair.p0, unit)} → ${f.price(pair.p1, unit)}`);
  } else if (pair) {
    const text = manifest?.codes.venue_pair_status?.[pair.status]?.text;
    if (text) lines.push(text);
  }
  if (info.level !== null) {
    lines.push(`Endkurs dort ${info.levelFlag ? 'weicht auffällig ab' : 'stimmt überein'}: ${pct(info.level)} gegenüber der Referenzbörse`);
  }
  const limit = info.limitR ?? manifest?.venue_check?.schwelle_wertentwicklung;
  if (limit !== undefined && limit !== null) {
    const swing = info.noise !== null && info.limitR !== null ? ` (übliche Tagesschwankung dieser Aktie ${pct0(info.noise)})` : '';
    lines.push(`Schwelle ${Math.round(limit * 100)} %${swing} – nur ein Hinweis, Rendite und Rang bleiben unverändert.`);
  }
  return lines;
}
