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
  last_run: null | {
    run_id: string;
    trigger: string;
    planned_start_utc: string | null;
    started_at_utc: string;
    finished_at_utc: string | null;
    status: string;
    message: string | null;
    cutoff_session_date: string | null;
    attempt: number;
  };
  schedule: { uhrzeit: string; zeitzone: string; wiederholungen_minuten: number[] };
  heartbeat_max_age_hours: number;
  software_version: string;
  encryption?: { enabled: boolean; descriptor: string };
  retained_snapshot_ids?: string[];
  /** Manueller Start des Serverlaufs auf GitHub (ab 1.2; fehlt außerhalb von GitHub Actions). */
  aktualisieren?: { repository: string; workflow: string; starten_url: string; laeufe_url: string } | null;
  /** Nächster möglicher Kursstichtag und ab wann ein Lauf ihn berechnen kann (ab 1.2). */
  naechster_kursstand?: { datum: string; ab_utc: string; boersen: string[] } | null;
}

export interface SnapshotSummary {
  snapshot_id: string;
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
  turnover?: TurnoverSummary;
  /** Abgleich mit einem zweiten Börsenplatz (ab Version 1.2); fehlt in älteren Ständen. */
  venue_check?: VenueSummary | null;
  /** Umschichtungs-Regel (ab Version 1.3); fehlt in älteren Ständen. */
  rotation?: RotationManifest | null;
  /** Vergleich mit den Regeln der Vorversion auf denselben Kursen (ab Methode 1.7.0). */
  method_comparison?: MethodComparison | null;
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
}
