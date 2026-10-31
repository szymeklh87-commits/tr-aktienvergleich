/* Depot-Optimierer (Aufträge vom 31.10.2026, 18 und 19): Typen des Optimierer-Teils im Spielgeld-Stand und kleine reine Hilfen
 * für die Ansicht „Depot-Empfehlungen“. Gerechnet wird im Forschungslauf und im täglichen Lauf
 * (`aktienpilot/optimierer.py`, `forschung.py`, `portfolio.py`); die App zeigt nur an. */

import * as f from './format';
import type { PilotDepot } from './pilot';

export type Horizont = 'w1' | 'w2' | 'w4' | 'w12' | 'w26' | 'w52';
export const HORIZONTE: Horizont[] = ['w1', 'w2', 'w4', 'w12', 'w26', 'w52'];
export type Belastbarkeit = 'belastbar' | 'eingeschränkt belastbar' | 'nicht belastbar';
export type VarianteId = 'rendite' | 'ausgewogen' | 'stabil' | 'kurz' | 'mittel' | 'lang';
/** Reihenfolge der Auswahl: zuerst nach Risiko, dann nach Zeitraum (Auftrag 18, Abschnitt 8) */
export const VARIANTEN: VarianteId[] = ['ausgewogen', 'rendite', 'stabil', 'kurz', 'mittel', 'lang'];

export interface OptKurs {
  kurs: number;
  waehrung: string | null;
  kurs_eur: number;
  datum: string;
  boerse: string | null;
}

/** Eine Aktie in Rangliste oder Depot (Prognose für den Horizont der Liste). */
export interface OptZeile {
  platz: number;
  isin: string;
  name: string | null;
  branche: string | null;
  waehrung: string | null;
  eignung: number | null;
  erwartet_pct: number | null;
  kosten_pct: number | null;
  positiv_pct: number | null;
  q10_pct: number | null;
  q50_pct: number | null;
  q90_pct: number | null;
  dezil: number;
  umsatz_eur: number | null;
  kurs: OptKurs | null;
  dafuer: string[];
  dagegen: string[];
  /** nur im Depot */
  gewicht_pct?: number;
  risiko_pct?: number | null;
}

export interface OptHorizontHeute {
  horizont: Horizont;
  text: string;
  modell: string | null;
  belastbarkeit: Belastbarkeit;
  aktien: number;
  rangliste: OptZeile[];
  grund?: string | null;
}

export interface OptDepotKennzahlen {
  erwartet_pct: number;
  kosten_pct: number;
  erwartet_nach_kosten_pct: number;
  schwankung_pct: number;
  verlustszenario_pct: number | null;
  positionen: number;
  effektive_anzahl: number;
  mittlere_korrelation: number | null;
  branchen: Record<string, number>;
  waehrungen: Record<string, number>;
}

export type OptArt = 'kaufen' | 'verkaufen' | 'aufstocken' | 'reduzieren' | 'halten' | 'nicht_aufnehmen';

export interface OptVeraenderung {
  isin: string;
  name?: string | null;
  art: OptArt;
  gewicht_alt_pct: number;
  gewicht_neu_pct: number;
  grund: string;
}

export interface OptVariante {
  variante: VarianteId;
  name: string;
  erklaerung: string;
  /** Horizont, mit dem gerechnet wurde (bei nicht belastbarem Wunschhorizont der nächstkürzere belastbare) */
  horizont: Horizont;
  horizont_text: string;
  horizont_wunsch?: Horizont;
  /** Hinweis, wenn mit einem anderen als dem eingestellten Horizont gerechnet wurde */
  ersatz?: string;
  verfuegbar: boolean;
  grund?: string;
  positionen: OptZeile[];
  kennzahlen: OptDepotKennzahlen | null;
  veraenderungen: OptVeraenderung[];
  kandidaten?: number;
}

export interface OptEinstellungen {
  variante: VarianteId;
  /** Anlagehorizont der Risikovarianten */
  horizont: Horizont;
  anzahl: number;
  kapital_eur: number;
  max_gewicht_pct: number;
  max_branche_pct: number;
  min_umsatz_eur: number;
  reserve_pct: number;
  umschichtung: 'taeglich' | 'woechentlich' | 'signal';
  mindestverbesserung_pp: number;
  toleranz_pp: number;
  halte_faktor: number;
}

export type Herkunft = 'app' | 'risikoprofil' | 'konfiguration';

export interface OptRangliste {
  horizonte: Partial<Record<Horizont, OptHorizontHeute>>;
  einstellungen: OptEinstellungen;
  herkunft: Herkunft;
  aktien_geprueft: number;
}

/* --------------------------------------------------------------- Forschungsergebnis */

export interface OptPruefzeitraum {
  ic: number | null;
  t: number | null;
  tage: number;
  trefferquote_pct: number | null;
  unabhaengig: number;
  spanne_pp?: number | null;
}

export interface OptFaktor {
  merkmal: string;
  horizont: Horizont;
  richtung: number;
  bestaetigt: boolean;
  auffaellig: boolean;
  urteil: string;
  entwicklung: OptPruefzeitraum;
  validierung: OptPruefzeitraum;
  test: OptPruefzeitraum;
}

export interface OptModellPruefung {
  name: string;
  ic: number | null;
  t: number | null;
  tage: number;
  unabhaengig: number;
  top_ueberschuss_pp: number | null;
  top_trefferquote_pct: number | null;
}

export interface OptDezil {
  dezil: number;
  n: number;
  mittel_pct: number | null;
  mittel_roh_pct: number | null;
  positiv_pct: number | null;
  q10_pct: number | null;
  q50_pct: number | null;
  q90_pct: number | null;
}

export interface OptRueckblickStrategie {
  text: string;
  perioden: number;
  mittel_pct: number | null;
  median_pct: number | null;
  kumuliert_pct: number | null;
  schlechteste_pct: number | null;
  positiv: number;
  besser_als_welt: number | null;
}

export interface OptRueckblick {
  horizont: Horizont;
  text: string;
  perioden: number;
  anzahl: number;
  kosten_pct: number;
  strategien: Record<string, OptRueckblickStrategie>;
  beste: string | null;
  hinweis: string;
}

export interface OptAuswahl {
  merkmale: string[];
  richtungen: number[];
  schritte: { merkmal: string; ic_entwicklung: number; ic_validierung: number }[];
  uebersprungen: { merkmal: string; grund: string }[];
}

export interface OptHorizontForschung {
  horizont: Horizont;
  text: string;
  handelstage: number;
  tage_bekannt: number;
  unabhaengig: number;
  zeitraeume: Record<'entwicklung' | 'validierung' | 'test', { von: string; bis: string; tage: number } | null>;
  auswahl: OptAuswahl | null;
  walk_forward: { faltungen: number; modelle: Record<string, OptModellPruefung> } | null;
  modell: string | null;
  modell_grund: string | null;
  belastbarkeit: Belastbarkeit;
  kalibrierung: { dezile: OptDezil[]; basis_positiv_pct: number | null; brier: { modell: number | null; basis: number | null } } | null;
  rueckblick: OptRueckblick | null;
}

export interface OptInventar {
  kennzahl: string;
  name: string;
  gruppe: string;
  typ: string;
  einheit: string;
  quelle: string;
  methode: string;
  historisch: string;
  verfuegbar: string;
  waehrung: string;
  verwendet: boolean;
  grund: string | null;
  merkmale: string[];
}

export interface OptZaehlung {
  universum: number;
  aktien_gerechnet: number;
  aktien_panel: number;
  aktien_heute: number;
  kennzahlen_katalog: number;
  kennzahlen_verwendet: number;
  merkmale: number;
  entscheidungstage: number;
  pruefungen: number;
  bestaetigt: number;
  kombinationen: number;
  modelle: number;
  rechenkern: number;
}

export interface OptModell {
  schema: string;
  id: string;
  version: string;
  modus: 'DEMO' | 'PAPER';
  synthetisch: boolean;
  erstellt_utc: string;
  datenstand: string;
  datentag: string;
  zeitraum: { von: string; bis: string; entscheidungstage: number; schritt: number; kurse_ab: string };
  historie: { geladen: boolean; aktien?: number; ergaenzt?: number; ohne_daten?: number; jahre?: Record<string, number> };
  merkmale: { schluessel: string; kennzahl: string; name: string; gruppe: string }[];
  inventar: OptInventar[];
  forschung: {
    faktoren: { zeilen: OptFaktor[]; fdr_q: number; validierung_t: number; hinweis?: string };
    redundanz: { rho: number; paare: { a: string; b: string; rho: number }[] };
    horizonte: Partial<Record<Horizont, OptHorizontForschung>>;
    namen: Record<string, string>;
  };
  zaehlung: OptZaehlung;
  hinweise: string[];
  einstellungen_herkunft: Herkunft;
  laufzeit_s: Record<string, number>;
}

export interface OptKontrolle {
  ausgewertet: {
    modell_id: string;
    horizont: Horizont;
    text: string;
    prognosen: number;
    tage: number;
    richtung_pct: number | null;
    mittel_erwartet_pct: number | null;
    mittel_ist_pct: number | null;
    mittlerer_fehler_pp: number | null;
    positiv_erwartet_pct: number | null;
    positiv_ist_pct: number | null;
    in_spanne_pct: number | null;
    rang_ic: number | null;
    spitze_ist_pct: number | null;
  }[];
  offen: number;
  gespeichert: number;
  hinweis: string;
}

/** Freigaberegeln für eine Übernahme ins Pilotdepot (dieselben wie im Strategielabor, `labor.yaml`). */
export interface Freigaberegeln {
  vorwaerts_sitzungen: number;
  verkaeufe: number;
  max_rueckgang_pct: number;
  vollstaendig_pct: number;
  vorsprung_pp: number;
  welt_schlagen: boolean;
  abstand_sitzungen: number;
}

/** Teil „optimierer“ des Spielgeld-Stands. */
export interface OptStand {
  modell: OptModell;
  heute: { datentag: string; tage: number; varianten: Partial<Record<VarianteId, OptVariante>> & { rangliste?: OptRangliste } } | null;
  kontrolle: OptKontrolle | null;
  freigabe?: Freigaberegeln | null;
}

/* --------------------------------------------------------------- Texte */

export const ART_TEXT: Record<OptArt, string> = {
  kaufen: 'Kaufen',
  aufstocken: 'Aufstocken',
  halten: 'Halten',
  reduzieren: 'Reduzieren',
  verkaufen: 'Verkaufen',
  nicht_aufnehmen: 'Nicht aufnehmen',
};

export const HERKUNFT_TEXT: Record<Herkunft, string> = {
  app: 'in der App eingestellt',
  risikoprofil: 'aus dem Risikoprofil der Einrichtung',
  konfiguration: 'Vorgabe (noch keine Einrichtung)',
};

export const UMSCHICHTUNG_TEXT: Record<OptEinstellungen['umschichtung'], string> = {
  taeglich: 'täglich prüfen',
  woechentlich: 'wöchentlich',
  signal: 'nur bei deutlichem Signal',
};

export const STRATEGIE_REIHENFOLGE = ['modell', 'momentum', 'platz1', 'top10', 'gleichmaessig', 'markt', 'kern', 'welt'];

/* --------------------------------------------------------------- Hilfen */

export function rangliste(o: OptStand): OptRangliste | null {
  return o.heute?.varianten.rangliste ?? null;
}

/** Gewählte Variante: aus den Einstellungen der neuesten Empfehlung (App, Risikoprofil oder Vorgabe). */
export function standardVariante(o: OptStand): VarianteId {
  return rangliste(o)?.einstellungen.variante ?? 'ausgewogen';
}

export function variante(o: OptStand, id: VarianteId): OptVariante | null {
  return o.heute?.varianten[id] ?? null;
}

export function belastbarkeitTon(b: Belastbarkeit | null | undefined): 'ok' | 'warn' | 'fehlt' {
  if (b === 'belastbar') return 'ok';
  if (b === 'eingeschränkt belastbar') return 'warn';
  return 'fehlt';
}

/** Prozentpunkte mit Vorzeichen („+1,2 pp“). */
export function pp(v: number | null | undefined, digits = 1): string {
  return v === null || v === undefined || !Number.isFinite(v) ? '–' : f.signedPctValue(v, digits).replace('%', 'pp');
}

/** Rang-IC mit Vorzeichen und drei Nachkommastellen. */
export function ic(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '–';
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(3).replace('.', ',')}`;
}

/** 10–90-%-Spanne einer Prognose („−3,1 % bis +6,4 %“). */
export function spanne(z: { q10_pct: number | null; q90_pct: number | null }): string {
  if (z.q10_pct === null || z.q90_pct === null) return '–';
  return `${f.signedPctValue(z.q10_pct, 1)} bis ${f.signedPctValue(z.q90_pct, 1)}`;
}

export type Spalte = 'gewicht' | 'erwartet' | 'risiko' | 'eignung' | 'name' | 'kurs';

/** Depotzeilen sortieren (stabil; fehlende Werte zuletzt). */
export function sortieren(zeilen: OptZeile[], spalte: Spalte, absteigend: boolean): OptZeile[] {
  const wert = (z: OptZeile): number | string | null => {
    if (spalte === 'gewicht') return z.gewicht_pct ?? null;
    if (spalte === 'erwartet') return z.erwartet_pct;
    if (spalte === 'risiko') return z.risiko_pct ?? null;
    if (spalte === 'eignung') return z.eignung;
    if (spalte === 'kurs') return z.kurs?.kurs_eur ?? null;
    return (z.name ?? z.isin).toLocaleLowerCase('de');
  };
  return zeilen
    .map((z, i) => ({ z, i, v: wert(z) }))
    .sort((a, b) => {
      if (a.v === null && b.v === null) return a.i - b.i;
      if (a.v === null) return 1;
      if (b.v === null) return -1;
      const c = typeof a.v === 'string' ? (a.v as string).localeCompare(b.v as string, 'de') : (a.v as number) - (b.v as number);
      return (absteigend ? -c : c) || a.i - b.i;
    })
    .map((x) => x.z);
}

/** Bestätigte Merkmale eines Horizonts nach Stärke in der Entwicklung (|IC|). */
export function bestaetigte(o: OptStand, h: Horizont): OptFaktor[] {
  return o.modell.forschung.faktoren.zeilen
    .filter((z) => z.horizont === h && z.bestaetigt)
    .sort((a, b) => Math.abs(b.entwicklung.ic ?? 0) - Math.abs(a.entwicklung.ic ?? 0));
}

export function merkmalName(o: OptStand, key: string): string {
  return o.modell.forschung.namen[key] ?? o.modell.merkmale.find((m) => m.schluessel === key)?.name ?? key;
}

/** Erwartete Depotrendite ± Schwankung über den Horizont („+2,1 % ± 4,8 %“). */
export function depotErwartung(k: OptDepotKennzahlen | null): string {
  if (!k) return '–';
  return `${f.signedPctValue(k.erwartet_nach_kosten_pct, 1)} ± ${f.plainPct(k.schwankung_pct, 1)}`;
}

/** Modellprüfung des gewählten Modells eines Horizonts (Walk-forward). */
export function modellPruefung(o: OptStand, h: Horizont): OptModellPruefung | null {
  const x = o.modell.forschung.horizonte[h];
  if (!x?.modell || !x.walk_forward) return null;
  return x.walk_forward.modelle[x.modell] ?? null;
}

/** Varianten in fester Reihenfolge mit ihrer Verfügbarkeit (nicht belastbare Horizonte ausdrücklich). */
export function variantenListe(o: OptStand): OptVariante[] {
  return VARIANTEN.map((v) => variante(o, v)).filter((v): v is OptVariante => v !== null);
}

/** Anteile (Branchen, Währungen) absteigend, kleine Reste zusammengefasst. */
export function anteile(werte: Record<string, number>, max = 6): { name: string; pct: number }[] {
  const rows = Object.entries(werte)
    .map(([name, pct]) => ({ name, pct }))
    .sort((a, b) => b.pct - a.pct);
  if (rows.length <= max) return rows;
  const rest = rows.slice(max - 1).reduce((s, r) => s + r.pct, 0);
  return [...rows.slice(0, max - 1), { name: `übrige (${rows.length - max + 1})`, pct: Math.round(rest * 10) / 10 }];
}

/** Dieselben Grenzen wie auf dem Server (`optimierer.pruefen_einstellungen`) – nur zur sofortigen Rückmeldung. */
export function einstellungenFehler(e: OptEinstellungen): string | null {
  if (!(e.anzahl >= 3 && e.anzahl <= 20) || !Number.isInteger(e.anzahl)) return 'Anzahl Aktien: 3 bis 20';
  if (!(e.kapital_eur >= 500 && e.kapital_eur <= 10_000_000)) return 'Spielgeldkapital: 500 bis 10.000.000 EUR';
  if (!(e.max_gewicht_pct >= 5 && e.max_gewicht_pct <= 100) || e.max_gewicht_pct * e.anzahl < 100 - e.reserve_pct - 1e-9)
    return 'Höchstgewicht je Aktie zu klein für die Anzahl Aktien (oder über 100 %)';
  if (!(e.max_branche_pct >= 10 && e.max_branche_pct <= 100)) return 'Höchstgewicht je Branche: 10 bis 100 %';
  if (!(e.min_umsatz_eur >= 0 && e.min_umsatz_eur <= 1e10) || !(e.reserve_pct >= 0 && e.reserve_pct <= 50)) return 'Mindestliquidität oder Reserve außerhalb der Grenzen';
  if (!(e.mindestverbesserung_pp >= 0 && e.mindestverbesserung_pp <= 20) || !(e.toleranz_pp >= 0 && e.toleranz_pp <= 20)) return 'Umschichtungsschutz außerhalb der Grenzen';
  return null;
}

export interface FreigabeZeile {
  bedingung: string;
  soll: string;
  ist: string;
  /** null: jetzt nicht prüfbar (erst bei einer Übernahme oder ohne Daten) */
  erfuellt: boolean | null;
}

/** Freigaberegeln am Vorwärtstest des Spielgeld-Musterdepots (Auftrag 18, Abschnitt 14, Modus C; Zusatz 20:16 Uhr, Punkt 5):
 *  gemessen nur im Vorwärtstest, nie am Rückblick. Der Vorsprung vor der ersetzten Strategie wird erst bei einer Übernahme
 *  geprüft. */
export function freigabePruefung(d: PilotDepot, r: Freigaberegeln): { zeilen: FreigabeZeile[]; erfuellt: number; pruefbar: number } {
  const k = d.kennzahlen;
  const b = d.bericht ?? null;
  const tage = b?.bewertungstage ?? 0;
  const voll = tage > 0 ? (100 * (tage - (b?.unvollstaendig ?? 0))) / tage : null;
  const welt = (b?.vergleiche ?? []).find((v) => /(^|-)v-welt(-|$)/.test(v.depot));
  const zeilen: FreigabeZeile[] = [
    { bedingung: 'Vorwärtstest', soll: `mindestens ${r.vorwaerts_sitzungen} Sitzungen`, ist: `${k.sitzungen} Sitzungen`, erfuellt: k.sitzungen >= r.vorwaerts_sitzungen },
    { bedingung: 'Abgeschlossene Verkäufe', soll: `mindestens ${r.verkaeufe}`, ist: String(k.verkaeufe), erfuellt: k.verkaeufe >= r.verkaeufe },
    {
      bedingung: 'Größter Rückgang',
      soll: `höchstens ${f.plainPct(r.max_rueckgang_pct, 0)}`,
      ist: f.plainPct(k.max_rueckgang_pct, 1),
      erfuellt: k.max_rueckgang_pct === null ? null : k.max_rueckgang_pct <= r.max_rueckgang_pct,
    },
    { bedingung: 'Vollständig bewertete Tage', soll: `mindestens ${f.plainPct(r.vollstaendig_pct, 0)}`, ist: f.plainPct(voll, 1), erfuellt: voll === null ? null : voll >= r.vollstaendig_pct },
  ];
  if (r.welt_schlagen) {
    zeilen.push({
      bedingung: 'Besser als der Welt‑ETF im selben Zeitraum',
      soll: 'Abstand über 0',
      ist: welt?.abstand_pp === null || welt?.abstand_pp === undefined ? 'noch kein Vergleich' : pp(welt.abstand_pp),
      erfuellt: welt?.abstand_pp === null || welt?.abstand_pp === undefined ? null : welt.abstand_pp > 0,
    });
  }
  zeilen.push({ bedingung: 'Vorsprung vor der ersetzten Strategie', soll: `mindestens ${pp(r.vorsprung_pp).replace('+', '')}`, ist: 'erst bei einer Übernahme geprüft', erfuellt: null });
  return { zeilen, erfuellt: zeilen.filter((z) => z.erfuellt === true).length, pruefbar: zeilen.filter((z) => z.erfuellt !== null).length };
}
