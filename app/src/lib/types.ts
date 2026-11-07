/* Datenvertrag „static-api-v1“ (siehe docs/11_Datenvertrag_API.md). */

export type Policy = 'native' | 'common_trend';
/** Vergleichsmenge einer Rangliste: v0/u = Gruppe A (alle Aktien), v0l/ul = Gruppe B (Ø Umsatz ≥ Schwelle, ab 1.4). */
export type Cohort = 'v0' | 'u' | 'v0l' | 'ul';
/** Aktiengruppe: A = alle vergleichbaren Aktien, B = zusätzlich Ø Tagesumsatz ≥ 10 Mio. USD (ab 1.4). */
export type Group = 'a' | 'b';

export interface Status {
  schema: string;
  generated_at_utc: string;
  app_mode: 'produktiv' | 'demo';
  latest_snapshot_id: string | null;
  latest_complete_snapshot_id: string | null;
  last_price_session: string | null;
  last_successful_check_utc: string | null;
  /** Letzter Lauf jeder Art – auch ein Zwischenstand. Für den offiziellen Tageslauf ab 1.20.5 ``offiziell.letzter_lauf``. */
  last_run: RunInfo | null;
  /** Ab 1.17 mit Nachtlauf (UTC-Uhrzeit, Wochentage 1 = Montag … 7 = Sonntag); fehlt, wenn keiner eingerichtet ist. */
  schedule: { uhrzeit: string; zeitzone: string; wiederholungen_minuten: number[]; nachtlauf_utc?: string | null; nachtlauf_wochentage?: number[] | null };
  heartbeat_max_age_hours: number;
  software_version: string;
  encryption?: { enabled: boolean; descriptor: string };
  retained_snapshot_ids?: string[];
  /** Manueller Start des Serverlaufs auf GitHub (ab 1.2; fehlt außerhalb von GitHub Actions). */
  aktualisieren?: { repository: string; workflow: string; starten_url: string; laeufe_url: string } | null;
  /** Nächster möglicher Kursstichtag und ab wann ein Lauf ihn berechnen kann (ab 1.2). */
  naechster_kursstand?: { datum: string; ab_utc: string; boersen: string[] } | null;
  /** Aktueller Signal-Stand (ab 1.6): Kennzahlen, Kursziele, Signale – unabhängig vom Kurs-Datenstand. */
  signale?: SignalStandInfo | null;
  /** Neuester offizieller Stand (ab 1.8; ``latest_snapshot_id`` zeigt auf den Zwischenstand, solange es einen gibt). */
  latest_official_snapshot_id?: string | null;
  /** Zwischenstand mit aktuellen Kursen (ab 1.8) – nur, solange er neuer ist als der offizielle Stand. */
  zwischenstand?: IntradayStatus | null;
  /** Spielgeld-Robo (Gesamtauftrag): nur Kennung, Zeit und Schema – die Depots stehen verschlüsselt in ``pilot/<id>/pilot.bin``. */
  spielgeld?: { id: string; erstellt_utc: string | null; schema: string | null } | null;
  /** Musterbereiche (Abschnitt 26): nur Kennung, Zeit und Schema – der Stand liegt verschlüsselt in ``muster/<id>/muster.bin``. */
  muster?: { id: string; erstellt_utc: string | null; schema: string | null } | null;
  /** Offizieller Stand mit Schlusskursen und eigenem Laufstatus (ab 1.20.5) – unabhängig von Zwischenständen. */
  offiziell?: OfficialStatus | null;
}

export interface RunInfo {
  run_id: string;
  trigger: string;
  planned_start_utc: string | null;
  started_at_utc: string;
  finished_at_utc: string | null;
  status: string;
  message: string | null;
  cutoff_session_date: string | null;
  attempt: number;
}

/** Offizieller Stand in status.json (ab 1.20.5). */
export interface OfficialStatus {
  snapshot_id: string | null;
  /** Kursstichtag (ISO-Datum) des neuesten veröffentlichten offiziellen Stands */
  kursstand: string | null;
  vollstaendigkeit: string | null;
  veroeffentlicht_utc: string | null;
  /** Letzter offizieller Lauf mit Erfolg (veröffentlicht oder „keine neuen Daten“) */
  letzte_erfolgreiche_pruefung_utc: string | null;
  letzter_lauf: RunInfo | null;
  /** Neuester Fehlschlag seit dem letzten Erfolg – ``null``, wenn danach ein offizieller Lauf gelang */
  letzter_fehlschlag: RunInfo | null;
  fehlschlaege_seit_erfolg: number;
  erster_fehlschlag_seit_erfolg_utc: string | null;
}

export interface IntradayStatus {
  snapshot_id: string;
  stichtag: string;
  kurse_bis_utc: string | null;
  erstellt_utc: string;
  aktien_mit_kurs: number | null;
  offizieller_stand: string | null;
  /** Ab 1.20.5: Kursstichtag des offiziellen Stands, auf dem der Zwischenstand aufbaut */
  offizieller_stichtag?: string | null;
  /** Ab 1.20.5: ``false`` = zwischen offiziellem Stand und Zwischenstand fehlt ein offizieller Stand (ungeprüfte
   * Schlusskurse); ``null``/fehlt = älterer Zwischenstand ohne Angabe */
  basis_geprueft?: boolean | null;
  basis_hinweis?: string | null;
}

/** Angaben eines Zwischenstands im Manifest (ab 1.8). */
export interface IntradayInfo {
  stichtag: string;
  kurse_bis_utc: string | null;
  kurse_ab_utc: string | null;
  abgerufen_utc: string;
  aktien_mit_kurs: number;
  davon_sitzung_beendet: number;
  abrufe: number;
  gedrosselt: boolean;
  offizieller_stand: string;
  offizieller_stichtag: string;
  tagwahl: { tag: string; erwartet: number; mit_kurs: number; anteil: number }[];
  boersen_mit_kurs: string[];
  boersen_ohne_kurs: string[];
  /** Sitzungsbeginn der Börsen ohne Kurs am Stichtag (UTC) */
  oeffnung_utc?: Record<string, string | null>;
  /** Ab 1.13: Börsen, die beim Abruf noch nicht geöffnet hatten, mit dem Tag des Schlusskurses, mit dem ihre Aktien
   * zählen (z. B. { XNYS: '2026-10-13' }). Fehlt das Feld (Stände bis 1.12), fehlen diese Aktien in den Ranglisten. */
  boersen_mit_schlusskurs?: Record<string, string>;
  /** Ab 1.13: Aktien ohne Kurs von heute, die mit dem Schlusskurs des Handelstags davor zählen */
  aktien_mit_schlusskurs?: number;
  /** Ab 1.20.5: Grundlage geprüft (kein Börsentag ohne offiziellen Stand zwischen offiziellem Stand und Stichtag) */
  basis_geprueft?: boolean;
  /** Ab 1.20.5: Börsentage ohne offiziellen Stand zwischen offiziellem Stand und Stichtag */
  basis_luecke?: string[];
  basis_hinweis?: string | null;
  beschreibung: string;
}

export interface SignalStandInfo {
  id: string;
  erstellt_utc: string;
  kursstand: string;
  snapshot_id: string;
  aktien: number;
  mit_kennzahlen: number;
  mit_kursziel: number;
  beide_gruen: number;
  kurz_gruen: number;
  lang_gruen: number;
  /** ab signale-v2 */
  gesamt_stark?: number;
  gesamt_mittel?: number;
  version: string;
}

export type Light = 'gruen' | 'gelb' | 'rot' | 'grau';

/** Stufe der Gesamtwertung (ab signale-v2): stark ≥ 65, mittel ≥ 50, schwach darunter, ohne = keine Wertung. */
export type TotalGrade = 'stark' | 'mittel' | 'schwach' | 'ohne';
export type TotalPart = 'konstanz' | 'kursziel' | 'kurzfristig' | 'qualitaet';

/** Trefferquote der Steig-Konstanz (ab signale-v2): Horizonte 20 und 60 Handelstage. */
export interface ConsistencyCalibration {
  bereiche: number[];
  horizonte: number[];
  faelle: number[];
  steigt_20: (number | null)[];
  mittel_20: (number | null)[];
  steigt_60: (number | null)[];
  mittel_60: (number | null)[];
  alle_steigt_20: number | null;
  alle_mittel_20: number | null;
  alle_steigt_60: number | null;
  alle_mittel_60: number | null;
  faelle_gesamt: number;
  erster_tag: number | null;
  letzter_tag: number | null;
  aktien: number;
}

/** Steig-Konstanz eines Zeitraums (Kalendertage) in der Einzelansicht. */
export interface ConsistencyPeriod {
  tage: number;
  steigtage: number | null;
  vergleiche: number | null;
  rendite: number | null;
  punkte: number | null;
}

export interface Calibration {
  bereiche: number[];
  faelle: number[];
  steigt_5: (number | null)[];
  mittel_5: (number | null)[];
  steigt_20: (number | null)[];
  mittel_20: (number | null)[];
  alle_steigt_5: number | null;
  alle_mittel_5: number | null;
  alle_steigt_20: number | null;
  alle_mittel_20: number | null;
  faelle_gesamt: number;
  erster_tag: number | null;
  letzter_tag: number | null;
  aktien: number;
}

/** signale.bin – Spalten je Aktie (Index = Position in ``isin``). */
export interface SignalsData {
  schema: string;
  id: string;
  snapshot_id: string;
  cutoff_day: number;
  kursstand: string;
  erstellt_utc: string;
  version: string;
  regeln: {
    kurz_gewichte: Record<string, number>;
    kurz_nachrichten_gewicht: number;
    lang_gewichte: Record<string, number>;
    mindestumsatz_eur: number;
    namen: Record<string, string>;
    erklaerungen: Record<string, string>;
    ampel_kurz: string;
    ampel_lang: string;
    hinweis: string;
    /** ab signale-v2 */
    gesamt_gewichte?: Record<TotalPart, number>;
    gesamt_namen?: Record<TotalPart, string>;
    gesamt_erklaerungen?: Record<TotalPart, string>;
    gesamt_regel?: string;
    gesamt_stark_ab?: number;
    gesamt_mittel_ab?: number;
    konstanz_zeitraeume?: number[];
  };
  kalibrierung: Calibration;
  /** ab signale-v2 */
  kalibrierung_konstanz?: ConsistencyCalibration | null;
  anzahl: {
    aktien: number;
    mit_kennzahlen: number;
    mit_kursziel: number;
    beide_gruen: number;
    kurz: Record<Light, number>;
    lang: Record<Light, number>;
    gesamt?: Record<TotalGrade, number>;
  };
  /** Gesamtwertung 0–100 (ab signale-v2; fehlt in älteren Signal-Ständen) */
  gesamt?: (number | null)[];
  gesamt_stufe?: TotalGrade[];
  gesamt_teile?: Record<TotalPart, (number | null)[]>;
  gesamt_steigt_20?: (number | null)[];
  gesamt_steigt_60?: (number | null)[];
  /** Börsenwert in EUR (ab 1.11; Yahoo „marketCap“ mit EZB-Kurs umgerechnet) */
  boersenwert_eur?: (number | null)[];
  sektoren: string[];
  isin: string[];
  sektor: number[];
  kurz: (number | null)[];
  kurz_ampel: Light[];
  kurz_grund: (string | null)[];
  lang: (number | null)[];
  lang_ampel: Light[];
  lang_grund: (string | null)[];
  potenzial: (number | null)[];
  ziel: (number | null)[];
  ziel_tief: (number | null)[];
  ziel_hoch: (number | null)[];
  analysten: number[];
  kaufen: (number | null)[];
  handelbar: boolean[];
  kurs: (number | null)[];
  kurs_tag: (number | null)[];
  punkte: Record<string, (number | null)[]>;
  merkmale: Record<string, (number | null)[]>;
  steigt_5: (number | null)[];
  steigt_20: (number | null)[];
  listen: { gesamt?: number[]; beide: number[]; kurz: number[]; lang: number[]; potenzial: number[]; handel?: number[] };
  /** Kaufsignal nach fester Regel (ab 1.21.0, „signalregel-1“) – fehlt in älteren Signal-Ständen */
  handel?: TradeColumns;
  /** KI-Auswertung der vorderen Kandidaten (ab 1.21.0): Zusammenfassung; der Text steht in der Einzelansicht */
  ki?: AiSummary | null;
  /** Risiko je Aktie (ab 1.24.0, „risiko-1“) */
  risiko?: RiskColumns;
  /** Rückblick der Signalregel ohne Vorgriff (ab 1.24.0, „rueckblick-1“) */
  rueckblick?: Backtest | null;
  /** frühere Kaufsignale je Aktie (ab 1.24.0): Plan mit Stop und Ziel nach 10 Handelstagen */
  rueckblick_eigen?: OwnBacktest | null;
  /** Wahrscheinlichkeiten 1–30 Handelstage, geprüft ohne Zukunftsdaten (ab 1.25.0, „wahrscheinlichkeit-1“) */
  wahrscheinlichkeit?: ProbabilityData | null;
  /** Ereignisse aus Schlagzeilen: Kaufwarnung und Nachrichtenlage je Aktie (ab 1.25.0, „ereignisse-1“) */
  ereignisse?: EventColumns | null;
  /** Aufmerksamkeit, eigene Berechnung (ab 1.25.0, „aufmerksamkeit-1“) */
  aufmerksamkeit?: AttentionData | null;
}

export interface ProbabilityClass {
  von: number;
  bis: number;
  p: number;
  beob: number;
  n: number;
  mittel: number;
  q25: number;
  q75: number;
}

export interface ProbabilityQuality {
  n: number;
  grundrate?: number;
  beob?: number;
  brier?: number;
  brier_grundrate?: number;
  skill?: number;
  t?: number;
  testtage?: number;
  logloss?: number;
  logloss_grundrate?: number;
  ece?: number;
  treffer?: number;
  maerkte?: Record<'steigend' | 'fallend', { n: number; skill: number | null; beob: number | null }>;
  klassen?: ProbabilityClass[];
  zuverlaessig: boolean;
  grund: string | null;
}

export interface ProbabilityData {
  version: string;
  regel: string;
  horizonte: number[];
  gezeigt: number[];
  grund_horizont: number;
  testzeitraum: { von: number | null; bis: number | null; stichtag: number | null };
  faelle: number;
  letzter_tag: number | null;
  merkmale: string[];
  grenzen: { mindestens_testfaelle: number; mindestens_verbesserung: number; mindestens_standardfehler?: number; hoechstens_kalibrierungsfehler: number };
  grundrate: Record<string, number | null>;
  qualitaet: Record<string, ProbabilityQuality>;
  hinweise: string[];
  /** Horizont → Prozent je Aktie (nur zuverlässige Horizonte) */
  steigt: Record<string, (number | null)[]>;
  gruende: string[][];
}

export interface EventColumns {
  version: string;
  warnung: (string | null)[];
  ampel: Light[];
  anzahl: { kaufwarnungen: number; mit_ereignissen: number };
  regel: string;
}

export interface NewsEvent {
  art: string;
  bezeichnung: string;
  ton: -1 | 0 | 1;
  kritisch: boolean;
  stand: 'bestaetigt' | 'bericht' | 'geruecht';
  titel: string;
  quelle: string | null;
  zeit: number | null;
  link: string | null;
}

export interface AttentionItem {
  /** Index im Signal-Stand */
  i: number;
  rang: number;
  punkte: number;
  vortag: number | null;
  vor7: number | null;
  vor30: number | null;
  neu: boolean;
  gruende: string[];
}

export interface AttentionData {
  version: string;
  regel: string;
  link_onvista: string;
  tag: number | null;
  tage_berechnet?: number;
  anzahl: number;
  liste: AttentionItem[];
  hinweis: string;
}

export type RiskLevel = 'niedrig' | 'mittel' | 'hoch' | 'unbekannt';

export interface RiskColumns {
  version: string;
  regel: string;
  stufe: RiskLevel[];
  punkte: (number | null)[];
  gruende: string[][];
  vollstaendig: boolean[];
  anzahl: Record<RiskLevel, number>;
}

/** Kennzahlen einer Gruppe historischer Nettorenditen (Anteile). ``belegt``: genug Fälle für eine Aussage. */
export interface BacktestStats {
  n: number;
  belegt: boolean;
  mittel?: number;
  median?: number;
  treffer?: number;
  verlust_mittel?: number | null;
  gewinn_mittel?: number | null;
  schlechtester?: number;
  bester?: number;
  rueckgang_mittel?: number;
  rueckgang_groesster?: number;
}

export interface BacktestGroup {
  faelle: number;
  ausgefuehrt: number;
  /** Haltedauer in Handelstagen ("1", "5", "10", "20", "21", "63", "126", "252") → Kennzahlen */
  halten: Record<string, BacktestStats>;
  /** nur Kaufsignale: Plan mit Stop und Ziel, nach 1/5/10/20 Handelstagen */
  plan?: Record<string, BacktestStats>;
}

export interface Backtest {
  version: string;
  regel: string;
  zeitraum: { von: number | null; bis: number | null; stichtag: number | null };
  mindestens_faelle: number;
  mindestens_faelle_aktie: number;
  horizonte: { tage: number[]; monate: [number, number][] };
  kosten: { position_eur: number; mit_kosten: boolean };
  status: { kaufsignal?: BacktestGroup; beobachten?: BacktestGroup; vergleich?: BacktestGroup };
  markt: { steigend: BacktestStats; fallend: BacktestStats };
  hinweise: string[];
}

export interface OwnBacktest {
  tage: number;
  n: number[];
  mittel: (number | null)[];
  treffer: (number | null)[];
}

export interface AiSummary {
  version: string;
  modell: string;
  /** Secret ANTHROPIC_API_KEY vorhanden */
  eingerichtet: boolean;
  gefragt: number;
  beantwortet: number;
  fehler?: number;
  hinweis?: string | null;
  /** Aktien mit KI-Auswertung */
  isin?: string[];
}

export type PlanStatus = 'kaufsignal' | 'beobachten' | 'kein_kauf';

/** Spalten des Handelsplans je Aktie (ab 1.21.0); Preise in der Kurseinheit der Notierung. */
export interface TradeColumns {
  regeln: TradeRules;
  status: PlanStatus[];
  grund: string[];
  einstieg: (number | null)[];
  stop: (number | null)[];
  ziel: (number | null)[];
  ziel_basis: ('2R' | 'analysten' | null)[];
  crv: (number | null)[];
  zu_spaet: boolean[];
  anzahl: Record<PlanStatus, number>;
}

export interface TradeRules {
  version: string;
  /** bis Signalregel 1 (1.21–1.22) */
  mindestumsatz_eur?: number;
  /** ab Signalregel 2 (1.23.0): 10 Mio. USD */
  mindestumsatz_usd?: number;
  staerke_perzentil: number;
  naehe_hoch: number;
  umsatz_faktor: number;
  max_ueberdehnung_atr: number;
  max_rsi: number;
  max_kursluecke_atr: number;
  einstieg_atr: number;
  stop_atr: number;
  ziel_r: number;
  min_crv: number;
  ziel_analysten_ab: number;
  zahlen_tage: number;
  beschreibung: string;
}

export interface PlanCheck {
  key: string;
  label: string;
  ok: boolean | null;
  wert: string;
  regel: string;
  gruppe: 'basis' | 'ausgangslage' | 'zeitpunkt' | 'ereignis' | 'risiko';
}

/** KI-Auswertung eines Kaufkandidaten (ab 1.21.0): erstellt auf dem Server aus Plan, Kennzahlen und Schlagzeilen. */
export interface AiReview {
  einordnung: string;
  risiken: string[];
  /** Hält die KI den Einstieg für zu spät? (zusätzlich zur Regel – entscheidet nicht über den Status) */
  zu_spaet: boolean | null;
  nachrichtenlage: 'positiv' | 'gemischt' | 'negativ' | 'keine' | null;
  modell: string;
  erstellt_utc: string;
}

/** Vollständiger Handelsplan einer Aktie in details/<ISIN>.bin (ab 1.21.0). */
export interface TradePlanDetail {
  regel: string;
  status: PlanStatus;
  grund: string;
  einstieg: number | null;
  stop: number | null;
  ziel: number | null;
  ziel_basis: '2R' | 'analysten' | null;
  crv: number | null;
  risiko_anteil: number | null;
  zu_spaet: boolean;
  pruefungen: PlanCheck[];
}

export interface SignalComponent {
  key: string;
  punkte: number | null;
  text: string;
  ton: -1 | 0 | 1;
  horizont: 'kurz' | 'lang';
}

export interface AnalystAction {
  tag: number | null;
  haus: string | null;
  aktion: string | null;
  von: string | null;
  zu: string | null;
  ziel: number | null;
  ziel_vorher: number | null;
  ziel_aktion: string | null;
}

export interface RatingMonth {
  monat: string;
  stark_kaufen: number;
  kaufen: number;
  halten: number;
  verkaufen: number;
  stark_verkaufen: number;
}

export interface NewsItem {
  titel: string;
  quelle: string | null;
  zeit: number;
  link: string;
  bezug: boolean;
  tendenz: -1 | 0 | 1;
}

/** details/<ISIN>.bin – Einzelansicht einer Aktie. */
export interface SignalDetail {
  schema: string;
  id: string;
  isin: string;
  kursstand: string;
  kurs: number | null;
  kurs_tag: number | null;
  einheit: string | null;
  /** ab signale-v2 */
  gesamt?: number | null;
  gesamt_stufe?: TotalGrade;
  gesamt_teile?: Partial<Record<TotalPart, number | null>>;
  konstanz?: ConsistencyPeriod[];
  wahrscheinlichkeit_gesamt?: null | { bereich: [number, number]; faelle: number; steigt_20: number | null; mittel_20: number | null; steigt_60: number | null; mittel_60: number | null };
  kurz: number | null;
  kurz_technik: number | null;
  kurz_ampel: Light;
  kurz_grund: string | null;
  lang: number | null;
  lang_ampel: Light;
  lang_grund: string | null;
  handelbar: boolean;
  komponenten: SignalComponent[];
  merkmale: Record<string, unknown>;
  potenzial: number | null;
  ziel: number | null;
  ziel_tief: number | null;
  ziel_hoch: number | null;
  ziel_quellen: { quelle: string; ziel: number; tief: number | null; hoch: number | null; anzahl: number | null }[];
  wahrscheinlichkeit: null | { bereich: [number, number]; faelle: number; steigt_5: number | null; mittel_5: number | null; steigt_20: number | null; mittel_20: number | null };
  prognose: null | { schwankung_jahr: number | null; band_3m: [number | null, number | null]; band_12m: [number | null, number | null] };
  kennzahlen: null | {
    analysten: null | {
      anzahl: number;
      ziel_mittel: number | null;
      ziel_median: number | null;
      ziel_hoch: number | null;
      ziel_tief: number | null;
      kurs: number | null;
      empfehlung_mittel: number | null;
      empfehlung: string | null;
      kaufen_anteil: number | null;
      empfehlungen_anzahl: number;
    };
    empfehlungen: RatingMonth[] | null;
    urteile: AnalystAction[] | null;
    urteile_anzahl: number | null;
    bewertung: Record<string, number | null> | null;
    wachstum: Record<string, number | null> | null;
    finanzen: Record<string, number | boolean | null> | null;
    risiko: Record<string, number | null> | null;
    termine: { zahlen: number | null } | null;
    branche: { sektor: string | null; industrie: string | null } | null;
    waehrung_bilanz: string | null;
  };
  bewertung_tc: null | {
    bewertung: 'unterbewertet' | 'fair' | 'ueberbewertet' | null;
    abschlag: number | null;
    bewertung_quelle: string | null;
    ausblick: Record<string, string>;
    ausblick_quelle: string | null;
    research: null | { quelle: string | null; einstufung: string | null; ziel: number | null };
  };
  nasdaq: null | { ziel: number | null; tief: number | null; hoch: number | null; anzahl: number | null };
  nachrichten: NewsItem[];
  /** Kaufsignal nach Signalregel 1 (ab 1.21.0) */
  handel?: TradePlanDetail | null;
  /** KI-Auswertung (ab 1.21.0, serverseitig, nur wenn eingerichtet) */
  ki?: AiReview | null;
  /** eingeordnete Ereignisse und Kaufwarnung (ab 1.25.0) */
  ereignisse?: NewsEvent[];
  kaufwarnung?: NewsEvent | null;
  community: null | { beitraege: number; bullish: number; bearish: number; je_tag: number | null; erster: string | null; letzter: string | null; beobachter: number | null };
  abgerufen: Record<string, string | null>;
  /** Kursverlauf: Tageskurse bis gut 1 Jahr, davor Wochenkurse bis 3 Jahre (ab 1.6) */
  verlauf?: { d: number[]; c: (number | null)[] };
  wochen?: { d: number[]; c: (number | null)[] } | null;
}

export interface SnapshotSummary {
  snapshot_id: string;
  /** „zwischenstand“ (ab 1.8) – sonst ein offizieller Stand */
  art?: 'zwischenstand';
  kurse_bis_utc?: string | null;
  aktien_mit_kurs?: number;
  offizieller_stand?: string;
  cutoff_session_date: string;
  computed_at_utc: string;
  published_at_utc?: string;
  completeness: 'vollstaendig' | 'teilstand';
  data_mode: 'produktiv' | 'demo';
  universe_count: number;
  return_eligible_30: number;
  trend_eligible_30: number;
  supersedes: string | null;
  /** Software-, Methoden- und Formelversionen des Stands (wie manifest.versions) */
  versions?: Record<string, string>;
}

export interface CryptoDescriptor {
  schema: string;
  enabled: boolean;
  kdf?: string;
  iterations?: number;
  salt_b64?: string;
  check_b64?: string;
  check_aad?: string;
}

export interface CodeInfo {
  key: string;
  kurz?: string;
  text: string;
  gruppe?: string;
}

export interface Manifest {
  schema: string;
  snapshot_id: string;
  /** „zwischenstand“ (ab 1.8): vorläufiger Stand mit aktuellen Kursen; fehlt bei offiziellen Ständen */
  art?: 'zwischenstand';
  zwischenstand?: IntradayInfo;
  data_mode: 'produktiv' | 'demo' | 'import';
  cutoff_session_date: string;
  cutoff_day: number;
  computed_at_utc: string;
  published_at_utc: string;
  completeness: {
    status: 'vollstaendig' | 'teilstand';
    share: number;
    delivered_markets: string[];
    missing_markets: string[];
    expected_instruments_at_cutoff: number;
    present_instruments_at_cutoff: number;
    market_threshold?: number;
    per_market?: Record<string, { expected: number; present: number; closed: number }>;
  };
  supersedes: string | null;
  versions: Record<string, string>;
  method: Record<string, unknown>;
  currency_basis: string;
  universe: {
    universe_snapshot_id: string;
    source_url: string;
    retrieved_at_utc: string;
    http_last_modified: string | null;
    pdf_creation_date: string | null;
    isin_count: number;
    nachweis: string;
  };
  provider: { prices: string; calendars: string; license_note: string; live_data: boolean; intraday: boolean };
  flags: { report_publishable: boolean; model_validated: boolean; forecast_eligible: boolean; original_run_on_time: boolean | null };
  /** ab 1.5.4: Schlusskurse aus der letzten Kursmeldung (Tageskerze beim Anbieter noch unvollständig) */
  kursmeldung?: { am_stichtag: number; aktien: number; beschreibung: string };
  /** ab tr-methode-1.9.0 (Software 1.14): Aktien ohne Kurs am Stichtag, die mit ihrem letzten Schlusskurs zählen */
  letzter_schlusskurs?: { aktien: number; je_kalender: Record<string, number>; max_verpasste_sitzungen: number; beschreibung: string } | null;
  checks: { name: string; passed: boolean; detail: string }[];
  codes: {
    status: Record<string, CodeInfo>;
    return_publishable: number[];
    trend_eligible: number[];
    instrument_warnings: Record<string, CodeInfo>;
    window_warnings: Record<string, CodeInfo>;
    turnover_status?: Record<string, CodeInfo>;
    venue_status?: Record<string, CodeInfo>;
    venue_pair_status?: Record<string, CodeInfo>;
  };
  coverage: {
    universe_total: number;
    identified: number;
    histories_loaded: number;
    with_any_return_window: number;
    instrument_level: Record<string, number>;
    per_window: { h: number; return_eligible: number; trend_eligible: number; by_status: Record<string, number> }[];
    warnings: Record<string, number>;
  };
  series_files: number;
  /** Euro-Referenzkurse für die Musterdepots (ab 1.9; fehlt in älteren Ständen) */
  fx?: FxSummary | null;
  turnover?: TurnoverSummary;
  /** Abgleich mit einem zweiten Börsenplatz (ab Version 1.2); fehlt in älteren Ständen. */
  venue_check?: VenueSummary | null;
  /** Umschichtungs-Regel (ab Version 1.3); fehlt in älteren Ständen. */
  rotation?: RotationManifest | null;
  /** Vergleich mit den Regeln der Vorversion auf denselben Kursen (ab Methode 1.7.0). */
  method_comparison?: MethodComparison | null;
  /** ab 1.20.0: Kursabgleich mit den Kursarchiven der Börsen (Zusammenfassung; Einzelheiten in kursabgleich.bin) */
  kursabgleich?: KursabgleichSummary | null;
}

export interface MethodComparison {
  vorher: string;
  jetzt: string;
  ausgangsmodell: string;
  regeln: string[];
  paare: {
    vorher_V: number;
    jetzt_V: number;
    vorher_U: number;
    jetzt_U: number;
    nicht_mehr_bewertet: number;
    neu_bewertet: number;
    /** nur Methode 1.7.0: Wegfall je neuer Regel (Mehrfachnennung möglich) */
    grund?: { volumen_fehlt: number; randvolumen: number; split_im_fenster: number };
    /** ab Methode 1.8.0: weggefallene Paare nach ihrem Status nach den neuen Regeln (Texte in codes.status) */
    weggefallen_nach_status?: Record<string, number>;
    /** ab Methode 1.8.0: hinzugekommene Paare nach ihrem Status nach den Regeln der Vorversion */
    hinzugekommen_aus_status?: Record<string, number>;
  };
  aktien: { vorher_mit_rendite: number; jetzt_mit_rendite: number };
  ranglisten: {
    verglichen: number;
    spitze_geaendert: number;
    /** ab tr-methode-1.10.0: Ranglisten mit anderen Aktien unter den ersten 10 */
    top10_andere_aktien?: number;
    /** ab tr-methode-1.10.0: dieselben ersten 10 in anderer Reihenfolge */
    top10_andere_reihenfolge?: number;
    /** ab tr-methode-1.10.0: Ranglisten mit irgendeinem anderen Platz */
    reihenfolge_geaendert?: number;
    beispiele: { gruppe: 'A' | 'B'; h: number; w: number; vorher: number | null; jetzt: number | null }[];
    hinweis: string;
  };
}

/** Kennzahlen einer Regelvariante im Rückblick (Beträge in EUR, Renditen als Anteil). */
export interface RotationStats {
  start_day: number | null;
  end_day: number | null;
  tage: number | null;
  umschichtungen: number | null;
  orders: number | null;
  verkaeufe: number | null;
  kaeufe: number | null;
  startkapital: number | null;
  endwert: number | null;
  endwert_ohne_kosten: number | null;
  vergleich_endwert: number | null;
  gebuehren: number | null;
  spanne: number | null;
  steuern: number | null;
  verlusttopf: number | null;
  rendite: number | null;
  rendite_ohne_kosten: number | null;
  vergleich_rendite: number | null;
  rendite_pro_jahr: number | null;
  vergleich_pro_jahr: number | null;
  max_rueckgang: number | null;
  vergleich_max_rueckgang: number | null;
}

export type RotationRhythm = 'monatlich' | 'woechentlich';

export interface RotationVariantInfo {
  key: string;
  aktien: number;
  rhythmus: RotationRhythm;
  trend_wochen: number;
  kapital: number;
  status: 'ok' | 'zu_wenig_historie';
  kennzahlen: Partial<RotationStats>;
  aenderungen_heute: number | null;
  /** Prüftag einer beschlossenen, noch nicht ausgeführten Umschichtung (sonst null). */
  beschlossen_am: number | null;
  naechste_entscheidung: number | null;
}

export interface RotationRule {
  aktien: number[];
  rhythmus: RotationRhythm[];
  trend_wochen: number[];
  kapital: number[];
  haltepuffer_faktor: number;
  anteil_toleranz: number;
  min_umsatz_usd: number;
  umsatz_wochen: number;
  min_anteil_umsatztage: number;
  min_abdeckung: number;
  max_sprung_faktor: number;
  langhistorie_jahre: number;
  vorauswahl_min_umsatz_usd: number;
}

export interface RotationCosts {
  order_eur: number;
  spanne: number;
  steuersatz: number;
  freibetrag_eur: number;
}

/** rotation/index.bin */
export interface RotationIndex {
  schema: string;
  snapshot_id: string;
  version: string;
  stichtag: number;
  standard: string | null;
  vorauswahl: number;
  raster: { von: number | null; bis: number | null; wochen: number; erste_woche_mit_daten: number | null };
  hinweis: string | null;
  /** Fortschritt der Langhistorie (Wochenwerte bis 3 Jahre) für den Rückblick. */
  langhistorie?: { aktien: number; geladen: number; offen: number; ohne_daten: number };
  regel: RotationRule;
  kosten: RotationCosts;
  varianten: RotationVariantInfo[];
}

export type RotationAction = 'kauf' | 'verkauf' | 'aufstocken' | 'reduzieren';
export type RotationReason = 'nicht_mehr_kandidat' | 'platz_ausserhalb_puffer' | 'anteil_angleichen' | 'neu_unter_den_besten';

export interface RotationPreview {
  tag: number;
  /** Prüftag (Freitag) der beschlossenen Umschichtung; null = Änderungen nach heutigem Stand (noch nicht beschlossen). */
  beschlossen_am: number | null;
  naechste_entscheidung: number;
  depotwert: number | null;
  bargeld: number | null;
  bestand: {
    idx: number[];
    stueck: (number | null)[];
    wert: (number | null)[];
    anteil: (number | null)[];
    seit: number[];
    einstand: (number | null)[];
    rendite: (number | null)[];
    platz: (number | null)[];
    trend: (number | null)[];
  };
  aenderungen: {
    idx: number[];
    aktion: RotationAction[];
    anteil_vorher: (number | null)[];
    anteil_nachher: (number | null)[];
    wert: (number | null)[];
    platz: (number | null)[];
    trend: (number | null)[];
    grund: RotationReason[];
  };
  rangliste: {
    idx: number[];
    platz: number[];
    trend: (number | null)[];
    umsatz_usd: (number | null)[];
    gehalten: boolean[];
  };
}

/** rotation/<Variante>.bin */
export interface RotationVariant {
  schema: string;
  snapshot_id: string;
  key: string;
  status: 'ok' | 'zu_wenig_historie';
  kennzahlen: Partial<RotationStats>;
  verlauf: { tage: number[]; depot: (number | null)[]; ohne_kosten: (number | null)[]; vergleich: (number | null)[] };
  umschichtungen: number[];
  orders: {
    /** Prüftag der Entscheidung (Freitag) */
    tag: number[];
    /** Handelstag der Ausführung (erste Sitzung danach) */
    ausfuehrung: number[];
    idx: number[];
    aktion: RotationAction[];
    wert: (number | null)[];
    anteil_vorher: (number | null)[];
    anteil_nachher: (number | null)[];
    platz: (number | null)[];
    trend: (number | null)[];
    gebuehr: (number | null)[];
    spanne: (number | null)[];
    steuer: (number | null)[];
    gewinn: (number | null)[];
  };
  vorschlag: RotationPreview | null;
}

/** Manifest-Abschnitt der Umschichtungs-Regel. */
export interface RotationManifest {
  version: string;
  standard: string | null;
  varianten: number;
  vorauswahl: number;
  raster: RotationIndex['raster'];
  langhistorie?: RotationIndex['langhistorie'];
  standard_status: string | null;
  standard_kennzahlen: Partial<RotationStats>;
  hinweis: string | null;
  beschreibung: string;
}

/** Manifest-Abschnitt: Regeln und Zählungen des Börsenplatz-Abgleichs. */
export interface VenueSummary {
  version: string;
  plaetze: number;
  bevorzugt: string[];
  schwelle_wertentwicklung: number;
  schwelle_endkurs: number;
  max_abstand_tage: number;
  max_aktien: number;
  beschreibung: string;
  hinweis: string | null;
  /** ab 1.5.1: Abgleich wegen eines Fehlers übersprungen (keine Ergebnisse, keine Kennzeichen) */
  abgebrochen?: boolean;
  /** ab boersenplatz-v3: Schwelle nach Tagesschwankung, nur Kurse mit Umsatz */
  schwankung_faktor?: number;
  schwankung_sitzungen?: number;
  schwelle_hoechstens?: number;
  nur_mit_umsatz?: boolean;
  auswertung?: VenueDiagnostics;
  anzahl: {
    kandidaten: number;
    aktien: Record<string, number>;
    auffaellige_aktien: number;
    aktie_zeitraum: Record<string, number>;
  };
}

/** Was wäre nach der festen 10-%-Regel bis boersenplatz-v2 auffällig gewesen (ab v3). */
export interface VenueDiagnostics {
  feste_schwelle_auffaellig: number;
  feste_schwelle_aktien: number;
  davon_ohne_umsatz: number;
  davon_in_schwankungsbreite: number;
  davon_weiter_auffaellig: number;
  schwelle_median: number | null;
  schwelle_max: number | null;
  schwelle_erhoeht_aktien: number;
}

/** Zweiter Börsenplatz je geprüfter Aktie (dünn besetzt, Index = Instrument). */
export interface VenueColumns {
  idx: number[];
  status: string[];
  symbol: (string | null)[];
  exchange_key: (string | null)[];
  exchange: (string | null)[];
  currency: (string | null)[];
  price_unit: (string | null)[];
  level: (number | null)[];
  level_flag: boolean[];
  end_day: (number | null)[];
  end_price: (number | null)[];
  /** ab boersenplatz-v3: übliche Tagesschwankung der Referenz (log., robust) und angewandte Schwellen */
  noise?: (number | null)[];
  limit_r?: (number | null)[];
  limit_l?: (number | null)[];
  /** ab 1.24: in mindestens einem Zeitraum auffällig abweichend (oder Endkurs auffällig) – Kurs nicht bestätigt */
  auffaellig?: boolean[];
}

/** Abgleich je Aktie in einem Fenster: Rendite am zweiten Platz (in Referenzwährung) und Abweichung. */
export interface VenueWindow {
  idx: number[];
  status: string[];
  r: (number | null)[];
  dev: (number | null)[];
  d0: (number | null)[];
  d1: (number | null)[];
  p0: (number | null)[];
  p1: (number | null)[];
}

/** Manifest-Abschnitt zum Ø Tagesumsatz (Ranking 2) samt Wechselkursquelle. */
export interface TurnoverSummary {
  version: string;
  sitzungen: number;
  min_sitzungen_mit_umsatz: number;
  schwelle_usd: number;
  sehr_niedrig_usd: number;
  berechnung: string;
  wechselkurse: {
    quelle: string | null;
    url: string | null;
    abgerufen_utc: string | null;
    erster_kurstag: string | null;
    letzter_kurstag: string | null;
    waehrungen: string[];
    max_alter_tage: number;
    hinweis: string;
  };
  anzahl: { status: Record<string, number>; aufgenommen: number; sehr_niedrig: number };
}

/** Ø Tagesumsatz je Instrument (spaltenweise, Index = Instrument). */
export interface TurnoverColumns {
  status: string[];
  usd: (number | null)[];
  local: (number | null)[];
  currency: (string | null)[];
  sessions: number[];
  with_data: number[];
  positive: number[];
  first: (number | null)[];
  last: (number | null)[];
  fx_first: (number | null)[];
  fx_last: (number | null)[];
  liquid: boolean[];
}

export interface Instruments {
  schema: string;
  snapshot_id?: string;
  count: number;
  isin: string[];
  name: string[];
  tr_name: string[];
  aliases: string[][];
  ticker: (string | null)[];
  symbol: (string | null)[];
  exchange_key: (string | null)[];
  exchange: (string | null)[];
  mic: (string | null)[];
  tz: (string | null)[];
  /** Börsenkalender der Referenznotierung (ab 1.4) */
  calendar?: (string | null)[];
  currency: (string | null)[];
  price_unit: (string | null)[];
  type: string[];
  identity: string[];
  identity_reason: (string | null)[];
  pre_status: number[];
  level_status: number[];
  warnings: number[];
  last_close: (number | null)[];
  last_close_day: (number | null)[];
  has_series: boolean[];
  v_bits: string[];
  u_bits: string[];
  best_h: (number | null)[];
  best_r: (number | null)[];
  turnover?: TurnoverColumns;
  venue?: VenueColumns | null;
}

export interface OverviewRow {
  h: number;
  M: number;
  idx?: number;
  r?: number | null;
  score?: number | null;
  r2?: number | null;
  start?: number;
  /** Zahl der Schlusskurse im Fenster (ab 1.5) */
  n?: number;
  tie?: boolean;
  sole?: boolean;
  empty?: string;
}

export interface WinnerRow {
  h: number;
  M: number;
  tie: boolean;
  all_negative: boolean;
  empty: string | null;
  /** ab 1.14 (Spitzenreiter ohne Auffällige): Platz in der vollständigen Rangliste */
  rank?: number | null;
  entries: {
    idx: number;
    r: number;
    start: number;
    end: number;
    p0?: number | null;
    p1?: number | null;
    /** Zahl der Schlusskurse im Fenster (ab 1.5) */
    n?: number;
    wf?: number;
    /** Abgleich mit dem zweiten Börsenplatz (ab Version 1.2; null = nicht geprüft). */
    xv?: { status: string; r: number | null; dev: number | null; d0: number | null; d1: number | null; p0: number | null; p1: number | null } | null;
  }[];
}

/** Spitzenreiter ohne ungeklärte Kursabweichung (ab 1.24): ``rank`` = Platz in der Liste mit Mindestumsatz, ``ausgeschlossen`` =
 * die davor stehenden Aktien mit ungeklärter Abweichung. */
export interface VerifiedWinnerRow extends WinnerRow {
  ausgeschlossen: number[];
}

export interface Overview {
  schema: string;
  snapshot_id?: string;
  cutoff_day: number;
  counts: { V: number[]; U: number[]; L?: number[]; UL?: number[] };
  v0: OverviewRow[];
  u: Record<string, OverviewRow[]>;
  /** Gruppe B (ab 1.4): Spitzenreiter je Zeitraum, 0/100 auf V ∩ L und elf Gewichtungen auf U ∩ L. */
  v0l?: OverviewRow[];
  ul?: Record<string, OverviewRow[]>;
  winners: WinnerRow[];
  overall_max: OverallMax;
  /** Ranking 2 (Ø Tagesumsatz ≥ Schwelle): gleiche Renditen, kleinere Menge. */
  winners_l?: WinnerRow[];
  overall_max_l?: OverallMax;
  /** ab 1.14: Spitzenreiter ohne Aktien mit kaum Umsatz oder Einzelsprung (A bzw. B) */
  winners_klar?: WinnerRow[];
  winners_l_klar?: WinnerRow[];
  /** ab 1.24: Spitzenreiter mit Mindestumsatz ohne ungeklärte Kursabweichung (Plätze ohne sie gezählt) */
  winners_lg?: VerifiedWinnerRow[];
  winners_lg_klar?: VerifiedWinnerRow[];
  klar_regel?: { umsatz_unter_usd: number; einzelsprung_bit: number; text: string };
  /** Identische Kursfenster (ab 1.5), wie `FrequencyData.same_set`. */
  same_set?: { v0: number[]; u: number[]; v0l?: number[]; ul?: number[] };
}

export interface OverallMax {
  tie: boolean;
  pairs_evaluated: number;
  entries: { idx: number; h: number; r: number; start: number; end: number; same_h?: number[] }[];
}

export interface WindowMembers {
  idx: number[];
  start: number[];
  n: number[];
  n_exp: number[];
  r: number[];
  /** Start- und Endkurs (Schluss, Notierungseinheit) – ab Version 1.1 */
  p0?: (number | null)[];
  p1?: (number | null)[];
  r2: (number | null)[];
  slope: (number | null)[];
  noise: (number | null)[];
  mdd: number[];
  /** Zahl positiver Schlusskursvergleiche p_i > p_(i−1) (ab 1.5, kennzahlen-v2) */
  up?: number[];
  vol: number[];
  wf: number[];
  a_rv: number[];
  a_gu: (number | null)[];
  a_ru: (number | null)[];
  /** Gruppe B (ab 1.4): doppelte Durchschnittsränge innerhalb V ∩ L bzw. U ∩ L */
  a_rvl?: (number | null)[];
  a_gul?: (number | null)[];
  a_rul?: (number | null)[];
}

export interface WindowData {
  schema: string;
  snapshot_id?: string;
  h: number;
  part: string;
  cutoff_day: number;
  target_start_day: number;
  counts: { V: number; U: number; L?: number; UL?: number };
  m: WindowMembers;
  orders: { v0: number[]; u: Record<string, number[]>; v0l?: number[]; ul?: Record<string, number[]> };
  ties: { v0: number[]; u: Record<string, number[]>; v0l?: number[]; ul?: Record<string, number[]> };
  xv?: VenueWindow | null;
  status_b64?: string;
}

export interface Occurrences {
  h: number[];
  rank: number[];
  idx: number[];
  score: number[];
  r: number[];
  start: number[];
}

export interface FrequencyData {
  schema: string;
  snapshot_id?: string;
  aggregation_version: string;
  cutoff_day: number;
  M: { v0: number[]; u: number[]; v0l?: number[]; ul?: number[] };
  occ: { v0: Occurrences; u: Record<string, Occurrences>; v0l?: Occurrences; ul?: Record<string, Occurrences> };
  universe?: { v0: string; u: string; v0l?: string; ul?: string };
  /** Startsitzung je Börsenkalender für die Zeiträume 1–90 (ab 1.4; null = keine Sitzung in Reichweite). */
  starts?: Record<string, (number | null)[]>;
  /** Identische Kursfenster (ab 1.5, frequency-v2): je Vergleichsmenge der kleinste Zeitraum mit demselben
   * Bestand aus ISIN und tatsächlichem Startdatum – gleicher Wert = gleiche Rangliste. */
  same_set?: { v0: number[]; u: number[]; v0l?: number[]; ul?: number[] };
  server_reference: ServerReference;
  /** Dieselbe Referenz für Gruppe B (ab 1.4). */
  server_reference_b?: ServerReference | null;
}

export interface ServerReference {
  policy: string;
  weights: string;
  top_k: number;
  E: number;
  cells: number;
  entries: { idx: number; n1: number; n3: number; n10: number; A: number; H: number; W: number; dew: number }[];
}

export interface SeriesData {
  schema: string;
  snapshot_id?: string;
  isin: string;
  listing: {
    symbol: string | null;
    exchange: string | null;
    mic: string | null;
    tz: string | null;
    currency: string | null;
    price_unit: string | null;
    unit_factor: number;
    calendar: string | null;
  };
  price_basis: string;
  resolution: string;
  source: { provider: string | null; fetched_at: string | null; revision: number | null };
  d: number[];
  c: number[];
  v: (number | null)[];
  o: (number | null)[] | null;
  h: (number | null)[] | null;
  l: (number | null)[] | null;
  c_raw: (number | null)[] | null;
  ohlc_complete: boolean;
  gaps: number[];
  window_start: (number | null)[];
  window_status: number[];
  rank_columns: string[];
  ranks_b64: string;
  events: { type: string; day: number; factor: number }[];
  /** Zwischenstand (ab 1.8): der letzte Punkt ist ein vorläufiger Kurs. */
  provisional?: { day: number; time_utc: string | null; session_closed: boolean } | null;
  /** ab 1.5.4: Tage, deren Schlusskurs aus der letzten Kursmeldung stammt */
  quote_days?: number[];
  /** ab 1.20.0: Kursabgleich – Quelle der Börse und Ergebnis der Auswahlregel */
  kursabgleich?: { quelle: string; status: string; grund: string | null } | null;
  /** ab 1.20.0: jeder Tag, an dem der verwendete Kurs von der Hauptquelle abweicht */
  korrekturen?: KursCorrection[];
}

/* ------------------------------------------------------------------ Kursabgleich (ab 1.20.0, kursabgleich.bin) */

export interface KursCorrection {
  d: number;
  grund: string;
  alt: number | null;
  neu: number;
  boerse_roh: number;
  quelle?: string;
  umsatz_alt?: number | null;
  umsatz_neu?: number | null;
}

export interface KursabgleichSummary {
  regel: string;
  kursdefinition: string;
  zeitraum_tage: number;
  erste_plaetze: number;
  durchgaenge: number;
  quellen: Record<string, Record<string, number>>;
  tage: Record<string, Record<string, number>>;
  abrufe: Record<string, number>;
  aktien_mit_kurskorrektur: number;
  /** ab 1.20.0 (zweiter Lauf): Aktien mit korrigiertem Schlusskurs oder Umsatzstatus */
  aktien_mit_korrektur_kurs_oder_umsatz?: number;
  ranglisten: { ranglisten?: number; platz1_anders?: number; erste10_andere_aktien?: number; erste10_andere_reihenfolge?: number };
  platz1_ohne_abgleich: Record<string, number>;
  us_zuordnung: Record<string, string | number>;
  datei: string;
}

export interface KursabgleichSource {
  key: string;
  name: string;
  rolle: string;
  betreiber: string;
  definition: string;
  url: string;
  boersen: string[];
}

export interface KursabgleichCase {
  idx: number | null;
  isin: string;
  boerse: string | null;
  quelle: string;
  status: string;
  grund: string | null;
  basis: string | null;
  gleich_anteil: number | null;
  abdeckung: number | null;
  faktor: number | null;
  tage: Record<string, number>;
  korrekturen: KursCorrection[];
  abweichend_ohne_uebernahme: { d: number; code: string; hauptquelle: number | null; boerse: number | null; boerse_roh: number | null }[];
}

export interface KursabgleichRanking {
  h: number;
  gruppe: 'A' | 'B';
  w: number;
  vorher: number[];
  nachher: number[];
  platz1_anders: boolean;
  ausloeser: number[];
}

export interface KursabgleichGap {
  idx: number;
  isin: string;
  boerse: string | null;
  grund: string;
  platz1: number;
  erste10: number;
  bester_platz: [number, number, 'A' | 'B', number] | null;
  fehlende_quelle: string | null;
}

export interface KursabgleichData {
  schema: string;
  snapshot_id?: string;
  stichtag: string;
  regel: string;
  kursdefinition: string;
  quellen: KursabgleichSource[];
  tagescodes: Record<string, string>;
  gruende: Record<string, string>;
  status: Record<string, string>;
  nicht_vergleichbar: Record<string, string>;
  fehlende_quellen: Record<string, string>;
  faelle: KursabgleichCase[];
  ranglisten: KursabgleichRanking[];
  luecken: KursabgleichGap[];
  luecken_gesamt: number;
  us_zuordnung: { idx: number | null; isin: string | null; ergebnis: string }[];
  zusammenfassung: KursabgleichSummary;
}

/* ------------------------------------------------------------------ Wechselkurse (ab 1.9, fx.bin) */

export interface FxSummary {
  datei: string;
  quelle: string;
  erster_tag: string | null;
  letzter_tag: string | null;
  waehrungen: string[];
  max_alter_tage: number;
}

/** Euro-Referenzkurse der letzten 100 Tage: je Währung Einheiten je EUR (null = kein Kurs an diesem Tag). */
export interface FxData {
  schema: string;
  snapshot_id: string;
  quelle: string;
  url: string | null;
  abgerufen_utc: string | null;
  max_alter_tage: number;
  basis: string;
  tage: number[];
  je_eur: Record<string, (number | null)[]>;
}
