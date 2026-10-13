/* Abgleich mit einem zweiten Börsenplatz (ab Version 1.2, `boersenplatz-v1`).
 *
 * Für die Aktien unter den ersten Plätzen der Rendite-Ranglisten misst der Server die Kursrendite
 * zusätzlich an einem zweiten Handelsplatz derselben ISIN (bevorzugt Xetra, dann Frankfurt) und
 * vergleicht in der Währung der Referenznotierung. Die App zeigt das Ergebnis nur an; sie rechnet
 * nichts nach und ändert keine Rangfolge.
 */

import * as f from './format';
import type { Instruments, Manifest, WindowData } from './types';

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
  return Boolean(manifest?.venue_check && manifest.venue_check.anzahl && !manifest.venue_check.hinweis?.includes('nicht eingerichtet'));
}

function pct(x: number): string {
  return f.pct(x);
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
  const limit = manifest?.venue_check?.schwelle_wertentwicklung;
  if (limit !== undefined) lines.push(`Schwelle ${Math.round(limit * 100)} % – nur ein Hinweis, Rendite und Rang bleiben unverändert.`);
  return lines;
}
