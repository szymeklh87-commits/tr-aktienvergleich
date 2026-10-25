/* Unabhängige Kursprüfung (ab 1.19.0) – Ergebnisse des Workflows „Datenqualität der Kurse prüfen“ für genau einen Stand, nur
 * Zählwerte und Ranglisten (Zeitraum/Gruppe/Gewichtung), keine Namen. Die App rechnet unverändert mit den Kursen des Stands;
 * diese Angaben zeigen nur, wo Platz 1 von der Kursquelle abhängt oder ungeprüft ist. Für jeden anderen Stand gilt „nicht geprüft“.
 *
 * Simons Auftrag vom 25.10.2026, 14:23 Uhr: „Zeige verbleibende Datenlücken und deren Auswirkungen verständlich an.“ Quelle der
 * Zahlen: GitHub-Lauf 40203960435 (alle Jobs: Ursachen, auffällige Aktien, Datenlücken, Spitzenreiter an Warschau, Toronto und
 * TSX Venture; Endfassung der Prüfskripte, Commit 4ddce83). */

export type CheckReason = 'nocp' | 'gpw' | 'tmx' | 'ungeprueft';

export interface RankingKey {
  h: number;
  g: 'a' | 'b';
  w: number;
}

export interface PriceCheck {
  stand: string;
  kursstand: string;
  geprueft: string;
  laeufe: string[];
  ranglisten: number;
  platz1_abgesichert: number;
  top10_abgesichert: number;
  top10_plaetze: number;
  aktientage: number;
  abweichend: number;
  belegt: number;
  plausibel: number;
  stand_veraltet: number;
  abweichende_tage_heute: number;
  ausgewaehlt: number;
  universum: number;
  /** Ranglisten je Grund (ein Ranglisten-Kürzel „h/g/w“ kann unter mehreren Gründen stehen) */
  ranglisten_je_grund: Record<CheckReason, string[]>;
}

const range = (h: number, g: 'A' | 'B', ws: number[]) => ws.map((w) => `${h}/${g}/${w}`);

export const PRICE_CHECK: PriceCheck = {
  stand: '2026-10-23_3f7ce5f3',
  kursstand: '2026-10-23',
  geprueft: '25.10.2026',
  laeufe: ['40203960435'],
  ranglisten: 1640,
  platz1_abgesichert: 1615,
  top10_abgesichert: 14564,
  top10_plaetze: 16400,
  aktientage: 34500,
  abweichend: 1066,
  belegt: 34,
  plausibel: 74,
  stand_veraltet: 0,
  abweichende_tage_heute: 1288,
  ausgewaehlt: 560,
  universum: 11596,
  ranglisten_je_grund: {
    nocp: ['33/A/10', '34/A/10', '35/A/10', '45/A/80'],
    gpw: ['31/A/20', '33/A/10', '34/A/10', '35/A/10', '52/B/70', '53/B/70', '57/B/70', '58/A/70', '58/B/60', '58/B/70', '58/B/90', '60/B/90'],
    tmx: ['30/A/90', '33/A/50', '34/A/50', '35/A/50', '36/A/10', '64/A/30', '65/A/40', '66/A/40', '67/A/40', '71/A/40', '71/A/50'],
    ungeprueft: [
      ...range(58, 'A', [10, 20]),
      ...range(64, 'A', [10, 20, 30]),
      ...range(65, 'A', [10, 20, 30, 40]),
      ...range(66, 'A', [10, 20, 30, 40]),
      ...range(67, 'A', [10, 20, 30, 40]),
      ...range(71, 'A', [10, 20, 30, 40, 50]),
      '58/B/90',
      '8/A/0',
      '71/B/100',
    ],
  },
};

export const REASON_TEXT: Record<CheckReason, string> = {
  nocp: 'Mit dem offiziellen Schlusskurs der Nasdaq (NOCP) statt des Kurses von Yahoo bei einer Aktie stünde eine andere Aktie auf Platz 1.',
  gpw: 'Mit den Kursen der Warschauer Börse (Hauptmarkt bzw. NewConnect) an Tagen ohne Umsatz statt der Kurse von Yahoo stünde eine andere Aktie auf Platz 1.',
  tmx: 'Mit den Schlusskursen der TSX Venture (TMX) statt der Kurse von Yahoo bei einer Aktie stünde eine andere Aktie auf Platz 1 – dieser Vergleich ist nicht abgesichert (Kurse weichen oft um einen Kursschritt ab).',
  ungeprueft: 'Die Kurse der Aktie auf Platz 1 sind nicht abgesichert gegen eine zweite Quelle geprüft.',
};

export function rankingKey(h: number, group: 'a' | 'b', weight: number): string {
  return `${h}/${group.toUpperCase()}/${weight}`;
}

/** Hinweise der Kursprüfung zu einer Rangliste – leer, wenn der Stand nicht geprüft ist oder nichts vorliegt. */
export function rankingNotes(snapshotId: string | null | undefined, h: number, group: 'a' | 'b', weight: number): CheckReason[] {
  if (!snapshotId || snapshotId !== PRICE_CHECK.stand) return [];
  const key = rankingKey(h, group, weight);
  return (Object.keys(PRICE_CHECK.ranglisten_je_grund) as CheckReason[]).filter((reason) => PRICE_CHECK.ranglisten_je_grund[reason].includes(key));
}

/** Ranglisten, deren Platz 1 laut Prüfung von der Kursquelle abhängt (abgesicherte Vergleiche: NOCP, GPW) bzw. nur in einem nicht
 * abgesicherten Vergleich (TMX) – ohne Doppelzählung. */
export function sourceDependent(reasons: CheckReason[]): number {
  const set = new Set<string>();
  for (const r of reasons) for (const key of PRICE_CHECK.ranglisten_je_grund[r]) set.add(key);
  return set.size;
}
