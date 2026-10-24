/* Laden der veröffentlichten statischen API. Alle Ansichten einer Navigation sind an
 * dieselbe snapshot_id gebunden; ein neuer Stand wird erst nach Bestätigung aktiv. */

import { decodeJson, DecodeError, NeedKeyError } from './container';
import type {
  CryptoDescriptor,
  FrequencyData,
  FxData,
  Instruments,
  Manifest,
  Overview,
  RotationIndex,
  RotationVariant,
  SeriesData,
  SignalDetail,
  SignalsData,
  SnapshotSummary,
  Status,
  WindowData,
} from './types';

export class OfflineError extends Error {
  constructor(message = 'Keine Verbindung und keine gespeicherte Kopie') {
    super(message);
  }
}

/** Der Server war erreichbar, hat aber mit einem Fehler geantwortet (z. B. 500) – nicht „offline“ (ab 1.16). */
export class ServerError extends Error {
  constructor(
    public readonly status: number,
    path: string,
  ) {
    super(`Server antwortet mit ${status} (${path})`);
  }
}

export class NotFoundError extends Error {}

function dataBase(): string {
  try {
    return new URL('./data/', window.location.href.split('#')[0]).toString();
  } catch {
    return './data/'; // Seite ohne gewöhnliche Adresse (z. B. eingebettete Vorschau)
  }
}

const BASE = dataBase();

async function fetchResponse(path: string, fresh: boolean): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(BASE + path, { cache: fresh ? 'no-cache' : 'default' });
  } catch {
    throw new OfflineError();
  }
  if (response.status === 404) throw new NotFoundError(path.split('?')[0]);
  // Der Service Worker antwortet offline ohne gespeicherte Kopie mit 503 und „x-tr-cache: fehlt“
  if (response.status === 503 && response.headers.get('x-tr-cache') === 'fehlt') throw new OfflineError();
  if (!response.ok) throw new ServerError(response.status, path.split('?')[0]);
  return response;
}

async function fetchBuffer(path: string, fresh: boolean): Promise<ArrayBuffer> {
  return (await fetchResponse(path, fresh)).arrayBuffer();
}

/* Ab 1.15 (Simons Wahl „schneller“): Kerndateien (verschlüsselte Rohdaten) im Voraus laden – während der
 * Zugangsschlüssel eingegeben und geprüft wird und gleichzeitig mit Manifest und Instrumenten, statt erst danach. Die
 * Clients nehmen eine vorab geladene Datei genau einmal; entschlüsselt wird wie immer erst dort. */
const prefetched = new Map<string, Promise<ArrayBuffer>>();

export function prefetch(paths: string[]): void {
  const wanted = new Set(paths);
  for (const path of [...prefetched.keys()]) if (!wanted.has(path)) prefetched.delete(path); // anderer Stand: verwerfen
  for (const path of paths) {
    if (prefetched.has(path)) continue;
    const promise = fetchBuffer(path, false);
    promise.catch(() => prefetched.delete(path));
    prefetched.set(path, promise);
  }
}

function takeBuffer(path: string): Promise<ArrayBuffer> {
  const early = prefetched.get(path);
  if (early) {
    prefetched.delete(path);
    return early;
  }
  return fetchBuffer(path, false);
}

/** Die Dateien, die die Startseite sofort braucht (Top 3, Kandidaten, Bericht, Rangliste des gewählten Zeitraums). */
export function corePaths(snapshotId: string, signalsId: string | null, h: number): string[] {
  const base = `snapshots/${snapshotId}/`;
  const out = [`${base}manifest.bin`, `${base}instruments.bin`, `${base}overview.bin`, `${base}frequency.bin`, `${base}windows/${h}.bin`];
  if (signalsId) out.push(`signale/${signalsId}/signale.bin`);
  return out;
}

/** Der Service Worker kennzeichnet Antworten aus dem Offline-Speicher mit „x-tr-cache: offline“.
 *  Statusdateien sind klein und ändern sich nach jedem Lauf; der Zeitstempel umgeht den
 *  Zwischenspeicher von GitHub Pages (sonst bis zu 10 Minuten alte Angaben). */
async function fetchJsonPlain<T>(path: string): Promise<{ data: T; offline: boolean }> {
  const response = await fetchResponse(`${path}?t=${Date.now()}`, true);
  const offline = response.headers.get('x-tr-cache') === 'offline';
  const data = JSON.parse(new TextDecoder().decode(await response.arrayBuffer())) as T;
  return { data, offline };
}

export interface Snapshot {
  status: Status;
  index: SnapshotSummary[];
  crypto: CryptoDescriptor;
  fromCache: boolean;
}

export async function loadEntry(): Promise<Snapshot> {
  const [status, index, crypto] = await Promise.all([
    fetchJsonPlain<Status>('status.json'),
    fetchJsonPlain<{ snapshots: SnapshotSummary[] }>('snapshots/index.json'),
    fetchJsonPlain<CryptoDescriptor>('crypto.json'),
  ]);
  return {
    status: status.data,
    index: index.data.snapshots ?? [],
    crypto: crypto.data,
    fromCache: status.offline || index.offline,
  };
}

/** Prüft nur den Status (z. B. beim Zurückkehren in die App). */
export async function checkStatus(): Promise<{ status: Status; offline: boolean }> {
  const result = await fetchJsonPlain<Status>('status.json');
  return { status: result.data, offline: result.offline };
}

export class SnapshotClient {
  private cache = new Map<string, Promise<unknown>>();

  constructor(public readonly id: string, private readonly key: CryptoKey | null) {}

  private get<T>(relative: string): Promise<T> {
    const existing = this.cache.get(relative);
    if (existing) return existing as Promise<T>;
    const promise = (async () => {
      const buffer = await takeBuffer(`snapshots/${this.id}/${relative}`);
      const data = await decodeJson<T>(buffer, this.key, `snapshots/${this.id}/${relative}`);
      const fileId = (data as { snapshot_id?: unknown }).snapshot_id;
      if (typeof fileId === 'string' && fileId !== this.id) {
        throw new DecodeError(`Datei ${relative} gehört zu einem anderen Datenstand (${fileId})`);
      }
      return data;
    })();
    this.cache.set(relative, promise);
    promise.catch(() => this.cache.delete(relative));
    return promise;
  }

  manifest(): Promise<Manifest> {
    return this.get('manifest.bin');
  }

  instruments(): Promise<Instruments> {
    return this.get('instruments.bin');
  }

  overview(): Promise<Overview> {
    return this.get('overview.bin');
  }

  frequency(): Promise<FrequencyData> {
    return this.get('frequency.bin');
  }

  windowHead(h: number): Promise<WindowData> {
    return this.get(`windows/${h}.bin`);
  }

  windowFull(h: number): Promise<WindowData> {
    return this.get(`windows/${h}.full.bin`);
  }

  rotationIndex(): Promise<RotationIndex> {
    return this.get('rotation/index.bin');
  }

  rotationVariant(key: string): Promise<RotationVariant> {
    if (!/^n\d{1,2}-(monatlich|woechentlich)-w\d{1,2}-k\d{3,7}$/.test(key)) return Promise.reject(new NotFoundError(key));
    return this.get(`rotation/${key}.bin`);
  }

  series(isin: string): Promise<SeriesData> {
    if (!/^[A-Z]{2}[A-Z0-9]{9}\d$/.test(isin)) return Promise.reject(new NotFoundError(isin));
    return this.get(`series/${isin}.bin`);
  }

  /** Euro-Referenzkurse (ab 1.9); nur aufrufen, wenn das Manifest ``fx`` nennt. */
  fx(): Promise<FxData> {
    return this.get('fx.bin');
  }
}

/** Signal-Stand (ab 1.6): eigene Dateien unter ``signale/<id>/``, unabhängig vom Kurs-Datenstand. */
export class SignalsClient {
  private cache = new Map<string, Promise<unknown>>();

  constructor(public readonly id: string, private readonly key: CryptoKey | null) {}

  private get<T>(relative: string): Promise<T> {
    const existing = this.cache.get(relative);
    if (existing) return existing as Promise<T>;
    const promise = (async () => {
      const path = `signale/${this.id}/${relative}`;
      const buffer = await takeBuffer(path);
      const data = await decodeJson<T>(buffer, this.key, path);
      const fileId = (data as { id?: unknown }).id;
      if (typeof fileId === 'string' && fileId !== this.id) throw new DecodeError(`Datei ${relative} gehört zu einem anderen Signal-Stand (${fileId})`);
      return data;
    })();
    this.cache.set(relative, promise);
    promise.catch(() => this.cache.delete(relative));
    return promise;
  }

  main(): Promise<SignalsData> {
    return this.get('signale.bin');
  }

  detail(isin: string): Promise<SignalDetail> {
    if (!/^[A-Z]{2}[A-Z0-9]{9}\d$/.test(isin)) return Promise.reject(new NotFoundError(isin));
    return this.get(`details/${isin}.bin`);
  }
}

export { DecodeError, NeedKeyError };
