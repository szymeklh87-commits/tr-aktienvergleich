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

/** Fehlende Märkte eines Teilstands, alphabetisch nach Namen. */
export function missingMarketNames(manifest: Manifest): string[] {
  return [...manifest.completeness.missing_markets].map(marketName).sort((a, b) => a.localeCompare(b, 'de'));
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
