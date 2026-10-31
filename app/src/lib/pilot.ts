/* Autopilot – Spielgeld (Gesamtauftrag, Abschnitte 20, 29, 31): Datentypen des verschlüsselten Standes ``pilot/<id>/pilot.bin``
 * und reine Hilfsfunktionen (Gruppierung, Vergleich, Regeltext auf Deutsch). Keine echten Orders: der Stand beschreibt
 * virtuelle Depots mit Spielgeld (PAPER mit echten verfügbaren Kursen, DEMO mit synthetischen Kursen). */

export type PilotModus = 'PAPER' | 'SIGNAL' | 'DEMO';
export type DepotArt = 'pilot' | 'forschung' | 'vergleich';

export interface PilotWert {
  datum: string;
  gesamt_eur: number;
  kern_eur: number;
  aktiv_eur: number;
  guthaben_eur: number;
  einzahlungen_eur: number;
  gebuehren_eur: number;
  vollstaendig: boolean;
  fehlend: string[];
  stufe: string;
}

export interface PilotKennzahlen {
  rendite_zeitgewichtet_pct: number | null;
  gewinn_realisiert_eur: number | null;
  gewinn_realisiert_unbekannt: number;
  gewinn_offen_eur: number | null;
  kosten_eur: number | null;
  max_rueckgang_pct: number | null;
  sitzungen: number;
  kaeufe: number;
  verkaeufe: number;
}

export interface PilotStrategie {
  zuordnung: string;
  regel: string; // ID@Version
  name: string;
  anteil: number;
}

export interface PilotDepotKopf {
  id: string;
  name: string;
  art: DepotArt;
  modus: PilotModus;
  test_id: string;
  status: 'aktiv' | 'pausiert' | 'archiviert';
  start: string | null;
  angelegt_am: string;
  archiviert_am: string | null;
  historisch: boolean;
  synthetisch: boolean;
  startkapital_eur: number;
  strategien: PilotStrategie[];
  wert: PilotWert | null;
  kennzahlen: PilotKennzahlen;
}

export interface PilotPosition {
  isin: string;
  name: string | null;
  zuordnung: string;
  stueck: number;
  einstand_eur: number | null;
  kurs_eur: number | null;
  wert_eur: number | null;
  gewinn_eur: number | null;
  gewinn_pct: number | null;
  stop: number | null;
  eroeffnet: string | null;
  gm: Record<string, unknown>;
  regel: string | null;
  branche: string | null;
}

export interface PilotOrder {
  id: string;
  zuordnung: string;
  isin: string;
  richtung: 'kauf' | 'verkauf';
  stueck: number;
  grund: string;
  grund_text?: string | null;
  profil: string;
  datentag: number;
  sitzung: number | null;
  preispunkt: string;
  frueheste: string | null;
  ablauf: string | null;
  reserviert_eur: number;
  status: 'offen' | 'ausgefuehrt' | 'teilweise' | 'verfallen' | 'abgelehnt' | 'storniert';
  ausgefuehrt_stueck: number;
  schutz: boolean;
  regel: string | null;
  erstellt_am: string | null;
  begruendung?: Record<string, unknown> | null;
}

export interface PilotBedingung {
  pfad: string;
  ergebnis: 'wahr' | 'falsch' | 'nicht_pruefbar';
  wert?: number | string | null;
  vergleichswert?: number | null;
}

export interface PilotKandidat {
  isin: string;
  platz: number | null;
  score: number | null;
  ausgewaehlt: boolean;
  grund: string | null;
  filter: 'wahr' | 'falsch' | 'nicht_pruefbar' | null;
  fundstellen?: number;
  sortwerte?: (number | null)[];
  bedingungen?: PilotBedingung[];
  beispiele?: { art: string; fenster?: number; gewicht?: number; rang?: number; tag?: number; anzahl?: number }[];
}

export interface PilotEntscheidung {
  regel: string | null;
  budget_eur: number | null;
  verluststufe: string | null;
  statistik: { kandidaten: number; zugelassen: number; ausgewaehlt: number; nicht_erfuellt: number; nicht_pruefbar: number; zu_wenige: boolean } | null;
  quellen: Record<string, unknown>[] | null;
  ausgewaehlt: string[] | null;
  kandidaten: PilotKandidat[];
  kaeufe: { isin: string; stueck: number; order: string; bestimmend?: string }[] | null;
  verkaeufe: { isin: string; stueck: number; order: string; grund: string }[] | null;
  abgelehnt: { isin: string; grund: string }[] | null;
  ausstiege: Record<string, { art: string; grund: string; verkaufen: boolean }> | null;
}

export interface PilotJournal {
  tag: number;
  datum: string;
  art: string;
  text: string;
  zuordnung: string | null;
  daten?: (PilotEntscheidung & Record<string, unknown>) | Record<string, unknown>;
}

export interface PilotDepot extends PilotDepotKopf {
  beschreibung: string;
  aktiver_anteil: number;
  kern: { ziele: Record<string, number>; schwelle_pp: number; rebalancing: boolean; namen: Record<string, string | null> } | null;
  reserviert_eur: number | null;
  verlust: { stufe: string; rueckgang: number; tagesstopp_bis: number | null; pause_bis_freigabe: boolean; grenzen: Record<string, number> };
  pausiert: boolean;
  letzter_tag: string | null;
  verlauf: { tag: string[]; gesamt: (number | null)[]; kern: (number | null)[]; aktiv: (number | null)[] };
  positionen: PilotPosition[];
  orders_offen: PilotOrder[];
  orders_zuletzt: PilotOrder[];
  journal: PilotJournal[];
}

export interface PilotChronik extends PilotDepotKopf {
  kompakt: true;
  letzter_tag: string | null;
}

/* ------------------------------------------------------------------ Regel (Schema tr-regel/1) */

export interface KennzahlRef {
  id: string;
  parameter: Record<string, number | string | number[] | null>;
}

export type Ausdruck =
  | { und: Ausdruck[] }
  | { oder: Ausdruck[] }
  | { nicht: Ausdruck }
  | { kennzahl: KennzahlRef; op: string; wert?: number | string | boolean | null; vergleich?: KennzahlRef; von?: number; bis?: number; werte?: (string | number)[] };

export interface Quelle {
  art: 'rangliste' | 'haeufigkeit' | 'universum' | 'isins';
  gruppe?: 'A' | 'B';
  politik?: 'native' | 'common_trend';
  gewichte?: number[];
  fenster?: { von: number; bis: number };
  platz_bis?: number;
  variante?: 'heute' | 'stichtage';
  stichtage?: number;
  k?: number;
  mindestens?: number;
  isins?: string[];
  bezeichnung?: string;
}

export interface Gewinnmitnahme {
  art: 'ganz' | 'leiter';
  basis: 'nach_kosten' | 'kurs';
  schwelle_pct?: number;
  umfang?: { art: 'alles' } | { art: 'anteil'; pct: number } | { art: 'stueck'; stueck: number };
  bezug?: 'urspruenglich' | 'verbleibend';
  stufen?: { schwelle_pct: number; anteil_pct: number }[];
}

export interface Regel {
  schema: 'tr-regel/1';
  id: string;
  version: number;
  name: string;
  beschreibung?: string;
  herkunft?: Record<string, string>;
  kandidaten: Quelle[];
  filter: Ausdruck | null;
  sortierung: { schluessel: { kennzahl: KennzahlRef; richtung: 'ab' | 'auf' }[] } | { score: { kennzahl: KennzahlRef; gewicht: number; richtung: 'ab' | 'auf' }[]; normierung?: string };
  auswahl: { anzahl: number; max_je_branche?: number | null };
  kapital: { art: 'gleich' | 'risiko' | 'ziel'; ziele_pct?: number[] };
  kauf: { ausloeser: 'termin' | 'neues_signal' | 'eintritt_top_n' | 'auffuellen' };
  verkauf: {
    herausfallen?: { aktiv: boolean; puffer: number } | null;
    ausstieg?: Ausdruck | null;
    max_haltedauer_sitzungen?: number | null;
    gewinnmitnahme?: Gewinnmitnahme | null;
    wiedereinstieg?: { art: 'neues_signal' | 'pause' | 'naechste_umschichtung'; pause_sitzungen?: number } | null;
  };
  stop: { initial: { art: 'atr'; faktor: number; sitzungen?: number } | { art: 'prozent'; wert: number }; trailing?: ({ art: 'atr'; faktor: number; sitzungen?: number } | { art: 'prozent'; wert: number }) | null };
  zeitplan: { intervall: 'taeglich' | 'woechentlich'; wochentag?: number };
  profil: 'FOLGETAG-SCHLUSS' | 'TAGESDATEN';
  optionen?: { mindesthaltedauer_sitzungen?: number; mindestorderwert_eur?: number };
}

/* ------------------------------------------------------------------ Kennzahlenkatalog (aus dem Lauf, Abschnitt 31.8) */

export interface KatalogParam {
  name: string;
  art: 'ganzzahl' | 'zahl' | 'auswahl' | 'gewichte' | 'bereich';
  erklaerung: string;
  minimum?: number;
  maximum?: number;
  werte?: (string | number)[];
  standard?: number | string | number[] | { von: number; bis: number } | null;
}

export interface KatalogKennzahl {
  id: string;
  name: string;
  erklaerung: string;
  typ: 'zahl' | 'bool' | 'kategorie' | 'rang' | 'reihe';
  einheit: string;
  gruppe: string;
  parameter: KatalogParam[];
  operatoren: string[];
  rollen: string[];
  quelle: string;
  backtest: 'ja' | 'nur_vorwaerts' | 'nein';
  paper: boolean;
  rueckblickend: boolean;
  besser: 'hoch' | 'niedrig' | null;
  vergleichsklasse: string;
  reihe: boolean;
  hinweis: string;
  anzeige?: string;
}

export interface Katalog {
  schema: string;
  version: string;
  methode: string;
  bereiche: string[];
  kennzahlen: KatalogKennzahl[];
}

export interface PilotStand {
  schema: 'tr-spielgeld/1';
  id: string;
  erstellt_utc: string;
  datentag: string;
  snapshot_id: string;
  modus: PilotModus;
  version: string;
  katalog_version: string;
  hinweis: string;
  ueberwachung: string;
  depots: PilotDepot[];
  chronik: PilotChronik[];
  regeln: Record<string, Regel>;
  namen: Record<string, string | null>;
  katalog?: Katalog;
  vorlagen?: Record<string, Regel>;
  grenzen?: Record<string, number>;
}

/* ------------------------------------------------------------------ Gruppierung und Vergleich */

export interface DepotGruppe {
  /** Vorwärtstest (ab Start mit den täglichen Läufen) oder historische Simulation (nachgerechnet, kein Vorwärtstest) */
  historisch: boolean;
  pilot: PilotDepot | null;
  forschung: PilotDepot[];
  vergleich: PilotDepot[];
}

export function gruppieren(depots: PilotDepot[]): DepotGruppe[] {
  const out: DepotGruppe[] = [];
  for (const historisch of [false, true]) {
    const items = depots.filter((d) => Boolean(d.historisch) === historisch);
    if (!items.length) continue;
    out.push({
      historisch,
      pilot: items.find((d) => d.art === 'pilot') ?? null,
      forschung: items.filter((d) => d.art === 'forschung'),
      vergleich: items.filter((d) => d.art === 'vergleich'),
    });
  }
  return out;
}

/** Vergleichsdepot „Welt-ETF kaufen und halten“ einer Gruppe (Benchmark mit gleichem Startkapital, Abschnitt 29.6). */
export function benchmark(g: DepotGruppe): PilotDepot | null {
  return g.vergleich.find((d) => /(^|-)v-welt(-|$)/.test(d.id)) ?? null;
}

/** Robo-Kern ohne aktive Strategien (Referenz mit derselben Aktien-/Geldmarktquote). */
export function kernReferenz(g: DepotGruppe): PilotDepot | null {
  return g.vergleich.find((d) => /(^|-)v-kern(-|$)/.test(d.id)) ?? null;
}

/** Abstand der zeitgewichteten Rendite zum Vergleichsdepot in Prozentpunkten; null, wenn eine Seite fehlt oder die
 * Zeiträume verschieden sind (Start und letzter Tag müssen gleich sein). */
export function abstandPp(depot: PilotDepotKopf, ref: PilotDepotKopf | null): number | null {
  if (!ref || depot.start !== ref.start || depot.wert?.datum !== ref.wert?.datum) return null;
  const a = depot.kennzahlen.rendite_zeitgewichtet_pct;
  const b = ref.kennzahlen.rendite_zeitgewichtet_pct;
  if (a === null || b === null || !Number.isFinite(a) || !Number.isFinite(b)) return null;
  return a - b;
}

export type Sortierung = 'rendite' | 'rueckgang' | 'kosten' | 'name';

export function sortiereDepots<T extends PilotDepotKopf>(depots: T[], by: Sortierung): T[] {
  const val = (d: T): number => {
    switch (by) {
      case 'rendite':
        return -(d.kennzahlen.rendite_zeitgewichtet_pct ?? Number.NEGATIVE_INFINITY);
      case 'rueckgang':
        return d.kennzahlen.max_rueckgang_pct ?? Number.POSITIVE_INFINITY;
      case 'kosten':
        return d.kennzahlen.kosten_eur ?? Number.POSITIVE_INFINITY;
      default:
        return 0;
    }
  };
  return [...depots].sort((a, b) => val(a) - val(b) || a.name.localeCompare(b.name, 'de') || a.id.localeCompare(b.id));
}

/** Journal nach Tag gruppiert (neueste zuerst), innerhalb des Tages in der gespeicherten Reihenfolge. */
export function journalNachTag(journal: PilotJournal[]): { datum: string; eintraege: PilotJournal[] }[] {
  const days = new Map<string, PilotJournal[]>();
  for (const e of journal) {
    const list = days.get(e.datum) ?? [];
    list.push(e);
    days.set(e.datum, list);
  }
  return [...days.entries()].sort((a, b) => (a[0] < b[0] ? 1 : a[0] > b[0] ? -1 : 0)).map(([datum, eintraege]) => ({ datum, eintraege }));
}

export const ART_TEXT: Record<string, string> = {
  start: 'Start',
  entscheidung: 'Entscheidung',
  ausfuehrung: 'Ausführung',
  stop: 'Stop',
  gewinnmitnahme: 'Gewinnmitnahme',
  kern: 'Robo-Kern',
  verlustgrenze: 'Verlustgrenze',
  split: 'Split',
  order: 'Order',
  hinweis: 'Hinweis',
};

export const ORDER_STATUS: Record<PilotOrder['status'], string> = {
  offen: 'offen',
  ausgefuehrt: 'ausgeführt',
  teilweise: 'teilweise ausgeführt',
  verfallen: 'verfallen',
  abgelehnt: 'abgelehnt',
  storniert: 'storniert',
};

export const STUFE_TEXT: Record<string, string> = {
  normal: 'normal',
  tagesstopp: 'Tagesstopp: keine neuen aktiven Käufe bis zur nächsten Sitzung',
  nur_risikosenkend: 'nur risikosenkende Transaktionen',
  schliessen: 'aktive Positionen werden geschlossen, Pause bis zur Freigabe',
};

/* ------------------------------------------------------------------ Regel als deutscher Text */

const NBSP = ' ';

function zahl(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return '–';
  return new Intl.NumberFormat('de-DE', { maximumFractionDigits: digits }).format(x);
}

function katalogIndex(katalog: Katalog | null | undefined): Map<string, KatalogKennzahl> {
  return new Map((katalog?.kennzahlen ?? []).map((k) => [k.id, k]));
}

function paramText(name: string, value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (name === 'fenster' && typeof value === 'number') return `${value}${NBSP}Tage`;
  if (name === 'fenster' && typeof value === 'object' && value && 'von' in value) {
    const v = value as { von: number; bis: number };
    return v.von === v.bis ? `${v.von}${NBSP}Tage` : `${v.von}–${v.bis}${NBSP}Tage`;
  }
  if (name === 'sitzungen' && typeof value === 'number') return `${value}${NBSP}Sitzungen`;
  if (name === 'gewicht' && typeof value === 'number') return `Gewichtung ${value}/${100 - value}`;
  if (name === 'gewichte' && Array.isArray(value)) return value.length === 11 ? 'alle Gewichtungen' : `Gewichtungen ${value.map((w) => `${w}/${100 - Number(w)}`).join(', ')}`;
  if (name === 'gruppe' && typeof value === 'string') return `Gruppe ${value}`;
  if (name === 'politik') return value === 'common_trend' ? 'gemeinsamer Trend' : null;
  if (name === 'k' && typeof value === 'number') return `Top ${value}`;
  return `${name} ${Array.isArray(value) ? value.join(', ') : String(value)}`;
}

/** „Rendite (30 Tage)“ – Name aus dem Katalog, Parameter lesbar. */
export function kennzahlText(ref: KennzahlRef, katalog?: Katalog | null, index?: Map<string, KatalogKennzahl>): string {
  const k = (index ?? katalogIndex(katalog)).get(ref.id);
  const name = k?.name ?? ref.id;
  const parts = Object.entries(ref.parameter ?? {})
    .map(([n, v]) => paramText(n, v))
    .filter((p): p is string => Boolean(p));
  return parts.length ? `${name} (${parts.join(', ')})` : name;
}

const OP_TEXT: Record<string, string> = {
  '>': '>',
  '>=': '≥',
  '<': '<',
  '<=': '≤',
  '==': '=',
  '!=': '≠',
  gekreuzt_aufwaerts: 'kreuzt von unten nach oben',
  gekreuzt_abwaerts: 'kreuzt von oben nach unten',
  neu_eingetreten: 'neu erfüllt',
  verlassen: 'nicht mehr erfüllt',
};

function wertText(v: unknown, einheit: string): string {
  if (typeof v === 'number') return `${zahl(v, 4)}${einheit ? `${NBSP}${einheit}` : ''}`;
  if (typeof v === 'boolean') return v ? 'ja' : 'nein';
  return String(v);
}

/** Ausdruck als Text: „Rendite (30 Tage) > 5 %“, Gruppen mit UND/ODER in Klammern. */
export function ausdruckText(a: Ausdruck | null | undefined, katalog?: Katalog | null, index?: Map<string, KatalogKennzahl>): string {
  if (!a) return 'keine Bedingung';
  const idx = index ?? katalogIndex(katalog);
  if ('und' in a) return a.und.map((x) => klammer(x, idx)).join(' UND ');
  if ('oder' in a) return a.oder.map((x) => klammer(x, idx)).join(' ODER ');
  if ('nicht' in a) return `NICHT ${klammer(a.nicht, idx)}`;
  const k = idx.get(a.kennzahl.id);
  const unit = k?.einheit ?? '';
  const left = kennzahlText(a.kennzahl, undefined, idx);
  switch (a.op) {
    case 'zwischen':
      return `${left} zwischen ${wertText(a.von, unit)} und ${wertText(a.bis, unit)}`;
    case 'in':
      return `${left} ist eine von: ${(a.werte ?? []).join(', ')}`;
    case 'nicht_in':
      return `${left} ist keine von: ${(a.werte ?? []).join(', ')}`;
    case 'ist_wahr':
      return `${left}: ja`;
    case 'ist_falsch':
      return `${left}: nein`;
    case 'neu_eingetreten':
    case 'verlassen':
      return `${left} ${OP_TEXT[a.op]}`;
    default: {
      const op = OP_TEXT[a.op] ?? a.op;
      const right = a.vergleich ? kennzahlText(a.vergleich, undefined, idx) : wertText(a.wert, unit);
      return `${left} ${op} ${right}`;
    }
  }
}

function klammer(a: Ausdruck, idx: Map<string, KatalogKennzahl>): string {
  const text = ausdruckText(a, undefined, idx);
  return 'und' in a || 'oder' in a ? `(${text})` : text;
}

function quelleText(q: Quelle): string {
  switch (q.art) {
    case 'rangliste': {
      const f = q.fenster ? (q.fenster.von === q.fenster.bis ? `${q.fenster.von} Tage` : `${q.fenster.von}–${q.fenster.bis} Tage`) : '';
      const w = q.gewichte?.length === 11 ? 'alle Gewichtungen' : (q.gewichte ?? []).map((x) => `${x}/${100 - x}`).join(', ');
      const where = q.variante === 'stichtage' ? `an den letzten ${q.stichtage ?? 1} Stichtagen (archivierte Ranglisten)` : 'heute';
      return `Plätze 1–${q.platz_bis ?? 1} der Lineal-Rangliste ${w} (Gruppe ${q.gruppe ?? 'A'}${q.politik === 'common_trend' ? ', gemeinsamer Trend' : ''}), ${f}, ${where}`.replace('Plätze 1–1 ', 'Platz 1 ');
    }
    case 'haeufigkeit': {
      const f = q.fenster ? `${q.fenster.von}–${q.fenster.bis} Tage` : '';
      return `mindestens ${q.mindestens ?? 1} Nennungen in den Top ${q.k ?? 10} (${f}, ${q.gewichte?.length === 11 ? 'alle Gewichtungen' : `${q.gewichte?.length ?? 0} Gewichtungen`}, Gruppe ${q.gruppe ?? 'A'})`;
    }
    case 'universum':
      return 'alle Aktien des Universums';
    case 'isins':
      return `${q.bezeichnung ?? 'eigene Liste'} (${q.isins?.length ?? 0} Aktien)`;
    default:
      return String((q as Quelle).art);
  }
}

function stopText(s: Regel['stop']['initial'] | NonNullable<Regel['stop']['trailing']>): string {
  return s.art === 'atr' ? `${zahl(s.faktor)} × ATR (${s.sitzungen ?? 14} Sitzungen)` : `${zahl(s.wert)}${NBSP}% unter dem Einstieg`;
}

function gewinnText(g: Gewinnmitnahme): string {
  const basis = g.basis === 'kurs' ? 'Kursgewinn' : 'Gewinn nach Kosten';
  if (g.art === 'leiter') {
    const stufen = (g.stufen ?? []).map((s) => `+${zahl(s.schwelle_pct)}${NBSP}% → ${zahl(s.anteil_pct)}${NBSP}%`).join(', ');
    return `Gewinnleiter (${basis}, Anteile der ${g.bezug === 'verbleibend' ? 'verbleibenden' : 'ursprünglichen'} Menge): ${stufen}`;
  }
  const u = g.umfang;
  const what = !u || u.art === 'alles' ? 'alles' : u.art === 'anteil' ? `${zahl(u.pct)}${NBSP}% der Position` : `${u.stueck} Stück`;
  return `ab +${zahl(g.schwelle_pct ?? 0)}${NBSP}% ${basis}: ${what} verkaufen`;
}

const WOCHENTAG = ['', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag'];

/** Die ganze Regel in kurzen deutschen Zeilen [Überschrift, Text] – für Übersicht, Prüfung vor dem Speichern und Journal. */
export function regelZusammenfassung(regel: Regel, katalog?: Katalog | null): [string, string][] {
  const idx = katalogIndex(katalog);
  const out: [string, string][] = [];
  out.push(['Kandidaten', regel.kandidaten.map(quelleText).join(' + ')]);
  if (regel.filter) out.push(['Filter', ausdruckText(regel.filter, undefined, idx)]);
  if ('schluessel' in regel.sortierung) {
    out.push(['Sortierung', regel.sortierung.schluessel.map((s) => `${kennzahlText(s.kennzahl, undefined, idx)} ${s.richtung === 'ab' ? 'absteigend' : 'aufsteigend'}`).join(', dann ')]);
  } else {
    out.push([
      'Score',
      `${regel.sortierung.score.map((s) => `${zahl(s.gewicht)} × ${kennzahlText(s.kennzahl, undefined, idx)}${s.richtung === 'auf' ? ' (niedrig besser)' : ''}`).join(' + ')} – je Kennzahl als Perzentil innerhalb der Kandidaten`,
    ]);
  }
  out.push([
    'Auswahl',
    `bis zu ${regel.auswahl.anzahl} Aktien${regel.auswahl.max_je_branche ? `, höchstens ${regel.auswahl.max_je_branche} je Branche` : ''}; Gleichstand nach ISIN`,
  ]);
  const kap = regel.kapital.art === 'gleich' ? 'gleich gewichtet' : regel.kapital.art === 'risiko' ? 'nach Risiko (ATR)' : `Zielgewichte ${(regel.kapital.ziele_pct ?? []).map((x) => `${zahl(x)}${NBSP}%`).join(' / ')}`;
  out.push(['Kapital', `${kap}; zentrale Grenzen des Risiko-Managers gelten immer`]);
  const kauf: Record<Regel['kauf']['ausloeser'], string> = {
    termin: 'zum Umschichtungstermin',
    neues_signal: 'nur bei neuem Signal',
    eintritt_top_n: 'bei Eintritt in die Auswahl',
    auffuellen: 'beim Wiederauffüllen mit freiem Guthaben',
  };
  out.push(['Kauf', kauf[regel.kauf.ausloeser] ?? regel.kauf.ausloeser]);
  const v = regel.verkauf ?? {};
  const sells: string[] = [];
  if (v.herausfallen?.aktiv) sells.push(`fällt aus der Auswahl (Puffer ${v.herausfallen.puffer} Plätze)`);
  if (v.ausstieg) sells.push(`Ausstieg: ${ausdruckText(v.ausstieg, undefined, idx)}`);
  if (v.max_haltedauer_sitzungen) sells.push(`nach höchstens ${v.max_haltedauer_sitzungen} Sitzungen`);
  out.push(['Verkauf', sells.length ? sells.join('; ') : 'nur über Stop und Gewinnmitnahme']);
  if (v.gewinnmitnahme) out.push(['Gewinnmitnahme', gewinnText(v.gewinnmitnahme)]);
  if (v.wiedereinstieg) {
    const w = v.wiedereinstieg;
    out.push(['Wiedereinstieg', w.art === 'pause' ? `nach ${w.pause_sitzungen ?? 0} Sitzungen Pause` : w.art === 'naechste_umschichtung' ? 'zur nächsten Umschichtung' : 'erst bei einem neuen Signal']);
  }
  out.push(['Stop', `${stopText(regel.stop.initial)}${regel.stop.trailing ? `; nachgezogen: ${stopText(regel.stop.trailing)}` : ''}`]);
  out.push([
    'Zeitplan',
    regel.zeitplan.intervall === 'taeglich' ? 'jeden Handelstag nach dem Datenstand' : `wöchentlich am ${WOCHENTAG[regel.zeitplan.wochentag ?? 5] ?? 'Freitag'}`,
  ]);
  out.push(['Ausführung', regel.profil === 'FOLGETAG-SCHLUSS' ? 'zum Schlusskurs der ersten Sitzung nach der Veröffentlichung' : 'mit dem Tagesdatenprofil']);
  return out;
}

/** Kurztext einer Kandidaten-Bedingung aus dem Journal (Pfad → Bedingung der Regel). */
export function bedingungAusPfad(regel: Regel | null | undefined, pfad: string, katalog?: Katalog | null): string {
  if (!regel) return pfad;
  const parts = pfad.split('.');
  let node: unknown = regel;
  for (const p of parts) {
    const m = /^(\w+)(?:\[(\d+)\])?$/.exec(p);
    if (!m || node === null || typeof node !== 'object') return pfad;
    node = (node as Record<string, unknown>)[m[1]];
    if (m[2] !== undefined) node = Array.isArray(node) ? node[Number(m[2])] : undefined;
  }
  return node && typeof node === 'object' ? ausdruckText(node as Ausdruck, katalog) : pfad;
}

export const ERGEBNIS_TEXT: Record<PilotBedingung['ergebnis'], string> = { wahr: 'erfüllt', falsch: 'nicht erfüllt', nicht_pruefbar: 'nicht prüfbar' };
