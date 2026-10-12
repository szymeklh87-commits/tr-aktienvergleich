/* Untergruppenranking (z. B. Watchlist) – Spiegel von traktien.analytics.ranking.rank_subgroup.
 *
 * Die globale Rangliste bleibt unverändert. V und U werden auf die Untergruppe eingeschränkt
 * und alle Perzentile darin neu berechnet. Das Ergebnis ist ausdrücklich als Untergruppe
 * beschriftet und keine Bewertung gegenüber dem gesamten TR-Angebot.
 *
 * Reihenfolgen:
 *   0/100 (V oder U): Rendite absteigend, ISIN aufsteigend → identisch zur globalen Reihenfolge,
 *                     eingeschränkt auf die Untergruppe.
 *   100/0:            R² ab, Steigung ab, Rauschen auf, ISIN → ebenfalls identisch zur globalen
 *                     Reihenfolge, eingeschränkt (dort mit ungerundeten Werten berechnet).
 *   10/90 … 90/10:    Score ab (Perzentile innerhalb der Untergruppe), Rendite ab, R² ab, ISIN.
 */

import { cohortFor, pctFromDoubled, weightedScore } from './scoring';
import type { Policy, WindowData } from './types';

export function averageRanksDoubled(values: number[]): number[] {
  const m = values.length;
  const order = values.map((_, i) => i).sort((a, b) => (values[a] < values[b] ? -1 : values[a] > values[b] ? 1 : a - b));
  const out = new Array<number>(m);
  let start = 0;
  while (start < m) {
    let end = start;
    while (end + 1 < m && values[order[end + 1]] === values[order[start]]) end += 1;
    for (let k = start; k <= end; k += 1) out[order[k]] = start + 1 + (end + 1);
    start = end + 1;
  }
  return out;
}

export interface SubgroupEntry {
  rank: number;
  idx: number;
  r: number;
  r2: number | null;
  score: number;
  g: number | null;
  rPct: number;
  tie: boolean;
}

export interface SubgroupRanking {
  label: string;
  cohort: 'V' | 'U';
  size: number;
  entries: SubgroupEntry[];
}

function tieFlags(primary: number[]): boolean[] {
  const flags = primary.map(() => false);
  for (let k = 1; k < primary.length; k += 1) {
    if (primary[k] === primary[k - 1]) {
      flags[k] = true;
      flags[k - 1] = true;
    }
  }
  return flags;
}

/** Benötigt die vollständige Fensterdatei (alle Mitglieder von V und vollständige Ranglisten). */
export function rankSubgroup(win: WindowData, subset: number[], policy: Policy, weight: number, name: string): SubgroupRanking {
  if (win.part !== 'vollstaendig') throw new Error('Untergruppenranking braucht die vollständige Fensterdatei');
  const wanted = new Set(subset);
  const position = new Map<number, number>();
  win.m.idx.forEach((idx, pos) => position.set(idx, pos));
  const cohort = cohortFor(policy, weight);
  const label = `Untergruppe: ${name}`;

  if (cohort === 'v0') {
    const members = win.m.idx.filter((idx) => wanted.has(idx));
    const rValues = members.map((idx) => win.m.r[position.get(idx)!]);
    const doubled = averageRanksDoubled(rValues);
    const pctOf = new Map<number, number>();
    members.forEach((idx, k) => pctOf.set(idx, pctFromDoubled(doubled[k], members.length)));
    const order = win.orders.v0.filter((idx) => wanted.has(idx));
    const primary = order.map((idx) => win.m.r[position.get(idx)!]);
    const ties = tieFlags(primary);
    return {
      label,
      cohort: 'V',
      size: members.length,
      entries: order.map((idx, k) => {
        const pos = position.get(idx)!;
        const rPct = pctOf.get(idx)!;
        return { rank: k + 1, idx, r: win.m.r[pos], r2: win.m.r2[pos], score: rPct, g: null, rPct, tie: ties[k] };
      }),
    };
  }

  const members = win.m.idx.filter((idx) => wanted.has(idx) && win.m.a_gu[position.get(idx)!] !== null);
  const rValues = members.map((idx) => win.m.r[position.get(idx)!]);
  const gValues = members.map((idx) => win.m.r2[position.get(idx)!] as number);
  const dR = averageRanksDoubled(rValues);
  const dG = averageRanksDoubled(gValues);
  const size = members.length;
  const info = new Map<number, { r: number; g: number; rPct: number; gPct: number; score: number }>();
  members.forEach((idx, k) => {
    const rPct = pctFromDoubled(dR[k], size);
    const gPct = pctFromDoubled(dG[k], size);
    info.set(idx, { r: rValues[k], g: gValues[k], rPct, gPct, score: weightedScore(weight, gPct, rPct) });
  });

  let order: number[];
  let primary: number[];
  if (weight === 0 || weight === 100) {
    order = (win.orders.u[String(weight)] ?? []).filter((idx) => info.has(idx));
    primary = order.map((idx) => (weight === 0 ? info.get(idx)!.r : info.get(idx)!.g));
  } else {
    order = [...members].sort((a, b) => {
      const x = info.get(a)!;
      const y = info.get(b)!;
      if (x.score !== y.score) return y.score - x.score;
      if (x.r !== y.r) return y.r - x.r;
      if (x.g !== y.g) return y.g - x.g;
      return a - b;
    });
    primary = order.map((idx) => info.get(idx)!.score);
  }
  const ties = tieFlags(primary);
  return {
    label,
    cohort: 'U',
    size,
    entries: order.map((idx, k) => {
      const x = info.get(idx)!;
      return { rank: k + 1, idx, r: x.r, r2: x.g, score: x.score, g: x.gPct, rPct: x.rPct, tie: ties[k] };
    }),
  };
}
