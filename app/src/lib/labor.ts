/* Strategielabor (Gesamtauftrag vom 31.10.2026, Abschnitte 12, 13, 15): Typen des Laborergebnisses im Spielgeld-Stand und
 * kleine reine Hilfen für die Ansicht. Das Ergebnis rechnet der Lauf (`aktienpilot/labor.py`); die App zeigt es nur an. */

import type { Regel } from './pilot';

export type LaborStatus = 'verworfen' | 'nicht_ausgewaehlt' | 'validierung_verfehlt' | 'validiert' | 'vorwaerts';

export interface LaborKennzahlen {
  rendite_pct: number;
  abstand_welt_pp: number | null;
  max_rueckgang_pct: number;
  rendite_je_rueckgang: number;
  gewinnquote_pct: number | null;
  kaeufe: number;
  verkaeufe: number;
  kosten_eur: number;
  profitfaktor: number | null;
  wertung?: number;
}

export interface LaborVariante {
  id: string;
  familie: string;
  familie_name: string;
  name: string;
  parameter: Record<string, number>;
  fingerabdruck: string;
  status: LaborStatus;
  grund: string;
  entwicklung: LaborKennzahlen;
  validierung?: LaborKennzahlen;
  /** nur für validierte Varianten – berichtet, ohne Einfluss auf die Auswahl */
  test?: LaborKennzahlen;
  regel?: Regel;
}

export interface LaborZeitraum {
  schluessel: string;
  art: 'entwicklung' | 'validierung' | 'test' | 'training' | 'pruefung';
  von: string;
  bis: string;
  tage: number;
  faltung?: number;
}

export interface LaborFaltung {
  faltung: number;
  training: LaborZeitraum;
  pruefung: LaborZeitraum;
  gewaehlt: string | null;
  welt_pct: number | null;
  rendite_pct?: number;
  max_rueckgang_pct?: number;
  abstand_welt_pp?: number | null;
  training_rendite_pct?: number;
}

export interface LaborErgebnis {
  schema: string;
  id: string;
  version: string;
  modus: 'DEMO' | 'PAPER';
  synthetisch: boolean;
  erstellt_utc: string;
  datenstand: string;
  datentag: string;
  zeitraeume: LaborZeitraum[];
  vergleich: Record<string, LaborKennzahlen | null>;
  uebernahme: { modus: 'nur_vorschlagen' | 'nach_freigabe' | 'automatisch_im_spielgeld'; vorwaerts: string[] };
  hinweise: string[];
  kennzahlen: { varianten: number; depots: number; tage: number; rechnungen: number; sekunden: Record<string, number>; aktien?: number };
  varianten: LaborVariante[];
  walk_forward: {
    faltungen: LaborFaltung[];
    zusammenfassung: { faltungen: number; mit_wahl: number; mittel_rendite_pct: number | null; mittel_welt_pct: number | null; besser_als_welt: number; positiv: number; wechsel: number };
  };
  parameterwirkung: { familie: string; parameter: string; werte: { wert: number; median_rendite_pct: number; varianten: number; positiv: number }[] }[];
  zaehlung: Record<LaborStatus, number>;
  positiv_entwicklung: number;
  /** Abschnitte 5.2, 5.3, 6: Folgerenditen der Signale gegen das Tagesmittel aller Aktien (ältere Ergebnisse ohne) */
  signalpruefung?: {
    horizonte: number[];
    hinweis: string;
    ergebnisse: {
      signal: string;
      text: string;
      horizont: number;
      tage: number;
      signale: number;
      mittel_rendite_pct?: number;
      mittel_ueberschuss_pp?: number;
      median_ueberschuss_pp?: number;
      trefferquote_pct?: number;
    }[];
  };
}

/** Ergebnisse der Signalprüfung je Signal (Reihenfolge des Laufs), je Horizont ein Eintrag. */
export function signalZeilen(e: LaborErgebnis): { signal: string; text: string; je: NonNullable<LaborErgebnis['signalpruefung']>['ergebnisse'] }[] {
  const out: { signal: string; text: string; je: NonNullable<LaborErgebnis['signalpruefung']>['ergebnisse'] }[] = [];
  for (const x of e.signalpruefung?.ergebnisse ?? []) {
    let row = out.find((r) => r.signal === x.signal);
    if (!row) {
      row = { signal: x.signal, text: x.text, je: [] };
      out.push(row);
    }
    row.je.push(x);
  }
  return out;
}

export const STATUS_TEXT: Record<LaborStatus, string> = {
  verworfen: 'verworfen',
  nicht_ausgewaehlt: 'robust, nicht ausgewählt',
  validierung_verfehlt: 'in der Validierung verworfen',
  validiert: 'validiert',
  vorwaerts: 'im Vorwärtstest',
};

export const MODUS_TEXT: Record<LaborErgebnis['uebernahme']['modus'], string> = {
  nur_vorschlagen: 'nur vorschlagen – validierte Varianten laufen als eigene Spielgelddepots vorwärts; das Pilotdepot ändert sich nicht',
  nach_freigabe: 'nach Freigabe – eine Variante übernimmt erst nach deiner Bestätigung in der App',
  automatisch_im_spielgeld: 'automatisch im Spielgeld – nur innerhalb der festgelegten Risikogrenzen',
};

export const PARAMETER_TEXT: Record<string, string> = {
  fenster_bis: 'Zeiträume bis (Tage)',
  mindestens: 'mindestens Nennungen',
  schwankung_min: 'Anstieg je Schwankung mindestens',
  abschnitte_min: 'positive Abschnitte mindestens (%)',
  volumenfaktor: 'Volumenfaktor mindestens',
  stichtage: 'Stichtage',
  fenster: 'Zeitraum (Tage)',
  haltedauer: 'höchstens halten (Sitzungen)',
  mindesthaltedauer: 'mindestens halten (Sitzungen)',
};

const RANG: Record<LaborStatus, number> = { vorwaerts: 0, validiert: 1, validierung_verfehlt: 2, nicht_ausgewaehlt: 3, verworfen: 4 };

/** Varianten je Familie (A–H), innerhalb einer Familie erst die weitergekommenen, dann nach Entwicklungswertung. */
export function nachFamilie(e: LaborErgebnis): { familie: string; name: string; varianten: LaborVariante[] }[] {
  const out = new Map<string, { familie: string; name: string; varianten: LaborVariante[] }>();
  for (const v of e.varianten) {
    if (!out.has(v.familie)) out.set(v.familie, { familie: v.familie, name: v.familie_name, varianten: [] });
    out.get(v.familie)!.varianten.push(v);
  }
  const groups = [...out.values()].sort((a, b) => a.familie.localeCompare(b.familie));
  for (const g of groups) {
    g.varianten.sort((a, b) => RANG[a.status] - RANG[b.status] || (b.entwicklung.wertung ?? 0) - (a.entwicklung.wertung ?? 0) || a.id.localeCompare(b.id));
  }
  return groups;
}

/** Vorgeschlagene Varianten in der Reihenfolge des Laufs. */
export function vorschlaege(e: LaborErgebnis): LaborVariante[] {
  const by = new Map(e.varianten.map((v) => [v.id, v]));
  return e.uebernahme.vorwaerts.map((id) => by.get(id)).filter((v): v is LaborVariante => Boolean(v));
}

/** Kennung des Vorwärtsdepots einer Variante (wie `labor.vorwaerts_depots`). */
export function vorwaertsDepotId(e: LaborErgebnis, variantId: string): string {
  return `${e.synthetisch ? 'demo-' : ''}l-${variantId.replace(/^r-/, '')}`;
}

export function zeitraum(e: LaborErgebnis, art: LaborZeitraum['art']): LaborZeitraum | undefined {
  return e.zeitraeume.find((z) => z.art === art);
}

export function parameterText(p: Record<string, number>): string {
  return Object.entries(p)
    .map(([k, v]) => `${PARAMETER_TEXT[k] ?? k} ${String(v).replace('.', ',')}`)
    .join(', ');
}
