/* Laden der veröffentlichten statischen API. Alle Ansichten einer Navigation sind an
 * dieselbe snapshot_id gebunden; ein neuer Stand wird erst nach Bestätigung aktiv. */

import { decodeJson, DecodeError, NeedKeyError } from './container';
import type {
  CryptoDescriptor,
  FrequencyData,
  Instruments,
  Manifest,
  Overview,
  SeriesData,
  SnapshotSummary,
  Status,
  WindowData,
} from './types';

export class OfflineError extends Error {
  constructor(message = 'Keine Verbindung und keine gespeicherte Kopie') {
    super(message);
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
  if (response.status === 404) throw new NotFoundError(path);
  if (!response.ok) throw new OfflineError(`Server antwortet mit ${response.status}`);
  return response;
}

async function fetchBuffer(path: string, fresh: boolean): Promise<ArrayBuffer> {
  return (await fetchResponse(path, fresh)).arrayBuffer();
}

/** Der Service Worker kennzeichnet Antworten aus dem Offline-Speicher mit „x-tr-cache: offline“. */
async function fetchJsonPlain<T>(path: string): Promise<{ data: T; offline: boolean }> {
  const response = await fetchResponse(path, true);
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
      const buffer = await fetchBuffer(`snapshots/${this.id}/${relative}`, false);
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

  series(isin: string): Promise<SeriesData> {
    if (!/^[A-Z]{2}[A-Z0-9]{9}\d$/.test(isin)) return Promise.reject(new NotFoundError(isin));
    return this.get(`series/${isin}.bin`);
  }
}

export { DecodeError, NeedKeyError };
