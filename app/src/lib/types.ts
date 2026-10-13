/* Datenvertrag „static-api-v1“ (siehe docs/11_Datenvertrag_API.md). */

export type Policy = 'native' | 'common_trend';
export type Cohort = 'v0' | 'u';

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
  anzahl: {
    kandidaten: number;
    aktien: Record<string, number>;
    auffaellige_aktien: number;
    aktie_zeitraum: Record<string, number>;
  };
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
    wf?: number;
    /** Abgleich mit dem zweiten Börsenplatz (ab Version 1.2; null = nicht geprüft). */
    xv?: { status: string; r: number | null; dev: number | null; d0: number | null; d1: number | null; p0: number | null; p1: number | null } | null;
  }[];
}

export interface Overview {
  schema: string;
  snapshot_id?: string;
  cutoff_day: number;
  counts: { V: number[]; U: number[]; L?: number[] };
  v0: OverviewRow[];
  u: Record<string, OverviewRow[]>;
  winners: WinnerRow[];
  overall_max: OverallMax;
  /** Ranking 2 (Ø Tagesumsatz ≥ Schwelle): gleiche Renditen, kleinere Menge. */
  winners_l?: WinnerRow[];
  overall_max_l?: OverallMax;
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
  vol: number[];
  wf: number[];
  a_rv: number[];
  a_gu: (number | null)[];
  a_ru: (number | null)[];
}

export interface WindowData {
  schema: string;
  snapshot_id?: string;
  h: number;
  part: string;
  cutoff_day: number;
  target_start_day: number;
  counts: { V: number; U: number; L?: number };
  m: WindowMembers;
  orders: { v0: number[]; u: Record<string, number[]>; v0l?: number[] };
  ties: { v0: number[]; u: Record<string, number[]>; v0l?: number[] };
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
  M: { v0: number[]; u: number[]; v0l?: number[] };
  occ: { v0: Occurrences; u: Record<string, Occurrences>; v0l?: Occurrences };
  universe?: { v0: string; u: string; v0l?: string };
  server_reference: {
    policy: string;
    weights: string;
    top_k: number;
    E: number;
    cells: number;
    entries: { idx: number; n1: number; n3: number; n10: number; A: number; H: number; W: number; dew: number }[];
  };
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
