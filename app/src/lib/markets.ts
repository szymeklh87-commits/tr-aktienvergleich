/* Lesbare Namen der Börsenkalender, wie sie im Manifest unter `completeness` stehen (Kalendercodes
 * aus config/boersen.yaml). Unbekannte Codes erscheinen unverändert. */

import type { Manifest } from './types';

const MARKET_NAMES: Record<string, string> = {
  ASEX: 'Athen',
  BVMF: 'São Paulo',
  XAMS: 'Amsterdam',
  XASX: 'Australien',
  XBKK: 'Bangkok',
  XBOM: 'Indien',
  XBRU: 'Brüssel',
  XBUD: 'Budapest',
  XCSE: 'Kopenhagen',
  XDUB: 'Dublin',
  XETR: 'Xetra',
  XFRA: 'Frankfurt',
  XHEL: 'Helsinki',
  XHKG: 'Hongkong',
  XICE: 'Island',
  XIDX: 'Jakarta',
  XIST: 'Istanbul',
  XJSE: 'Johannesburg',
  XKLS: 'Kuala Lumpur',
  XKRX: 'Korea',
  XLIS: 'Lissabon',
  XLON: 'London',
  XMAD: 'Madrid',
  XMEX: 'Mexiko',
  XMIL: 'Mailand',
  XNYS: 'USA',
  XNZE: 'Neuseeland',
  XOSL: 'Oslo',
  XPAR: 'Paris',
  XPRA: 'Prag',
  XSES: 'Singapur',
  XSGO: 'Santiago de Chile',
  XSHG: 'Shanghai/Shenzhen',
  XSTO: 'Stockholm',
  XSWX: 'Zürich (SIX)',
  XTAE: 'Tel Aviv',
  XTAI: 'Taiwan',
  XTAL: 'Tallinn',
  XTKS: 'Tokio',
  XTSE: 'Toronto',
  XWAR: 'Warschau',
  XWBO: 'Wien',
};

export function marketName(code: string): string {
  return MARKET_NAMES[code] ?? code;
}

function sortedNames(codes: readonly string[]): string[] {
  return [...codes].map(marketName).sort((a, b) => a.localeCompare(b, 'de'));
}

/** Fehlende Märkte eines Teilstands, alphabetisch nach Namen. */
export function missingMarketNames(manifest: Manifest): string[] {
  return sortedNames(manifest.completeness.missing_markets);
}

/** „A“, „A und B“, „A, B und C“ */
export function joinNames(names: readonly string[]): string {
  if (names.length <= 1) return names[0] ?? '';
  return `${names.slice(0, -1).join(', ')} und ${names[names.length - 1]}`;
}

/** Kurzfassung eines Teilstands für die Startseite: genannt wird die kürzere Liste. Fehlen mehr
 *  Börsen, als geliefert haben (am 12.10.2026: 28 von 31), stehen dort die gelieferten Börsen;
 *  die vollständige Liste der fehlenden steht unter „Datenstand & Betrieb“. */
export function partialSummary(manifest: Manifest): { mode: 'missing' | 'delivered'; names: string[]; missing: number; delivered: number; markets: number } {
  const c = manifest.completeness;
  const missing = c.missing_markets.length;
  const delivered = c.delivered_markets.length;
  const mode = delivered > 0 && delivered < missing ? 'delivered' : 'missing';
  return { mode, names: sortedNames(mode === 'delivered' ? c.delivered_markets : c.missing_markets), missing, delivered, markets: missing + delivered };
}

/** „1.234 von 8.293 Aktien mit Schlusskurs am Stichtag“ – Zählung über alle Märkte mit Sitzung. */
export function cutoffCoverage(manifest: Manifest): { present: number; expected: number; delivered: number; markets: number } {
  const c = manifest.completeness;
  return {
    present: c.present_instruments_at_cutoff,
    expected: c.expected_instruments_at_cutoff,
    delivered: c.delivered_markets.length,
    markets: c.delivered_markets.length + c.missing_markets.length,
  };
}
