/* Suche nach vollständigem Namen, Alias, Ticker, Symbol und ISIN über das ganze Universum. */

import type { Instruments } from './types';

export function normalize(text: string | null | undefined): string {
  return (text ?? '')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

export interface SearchIndex {
  haystack: string[];
}

export function buildSearchIndex(inst: Instruments): SearchIndex {
  const haystack: string[] = [];
  for (let i = 0; i < inst.count; i += 1) {
    const parts = [inst.isin[i], inst.name[i], inst.tr_name[i], inst.ticker[i], inst.symbol[i], ...(inst.aliases[i] ?? [])];
    haystack.push(` ${parts.map(normalize).join(' | ')} `);
  }
  return { haystack };
}

/** Liefert Indizes passender Instrumente; ISIN-Volltreffer zuerst. */
export function search(index: SearchIndex, inst: Instruments, query: string, limit = 500): number[] {
  const q = normalize(query);
  if (!q) return [];
  const upper = query.trim().toUpperCase();
  const exact: number[] = [];
  const hits: number[] = [];
  const terms = q.split(' ');
  for (let i = 0; i < index.haystack.length; i += 1) {
    if (inst.isin[i] === upper) {
      exact.push(i);
      continue;
    }
    const text = index.haystack[i];
    if (terms.every((t) => text.includes(t))) hits.push(i);
    if (hits.length >= limit) break;
  }
  return [...exact, ...hits];
}
