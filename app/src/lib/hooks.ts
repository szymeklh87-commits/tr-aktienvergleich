/* Daten-Hooks: alle Ansichten lesen ausschließlich aus dem aktiven Snapshot. */

import { useEffect, useState } from 'react';
import { useApp } from '../state/AppState';
import type { FrequencyData, Overview, RotationIndex, RotationVariant, SeriesData, WindowData } from './types';
import { useAsync, type AsyncState } from './useAsync';

export function useOverview(): AsyncState<Overview> {
  const { client } = useApp();
  const state = useAsync<Overview>(client ? () => client.overview() : null, [client]);
  return onlyMatching(state, (data) => sameSnapshot(data.snapshot_id, client?.id));
}

/** Liefert nur Daten, die zur aktuellen Anfrage passen. useAsync hält beim Nachladen den
 * vorherigen Wert; ein Fenster h=7 darf aber nie als h=30 angezeigt oder verrechnet werden. */
function onlyMatching<T>(state: AsyncState<T>, matches: (data: T) => boolean): AsyncState<T> {
  return state.data !== null && !matches(state.data) ? { data: null, error: state.error, loading: true } : state;
}

/** Alle Dateien einer Ansicht müssen zum selben Snapshot gehören (T47, T99). */
function sameSnapshot(fileId: string | undefined, activeId: string | undefined): boolean {
  return fileId === undefined || activeId === undefined || fileId === activeId;
}

/** Kopfdatei eines Fensters (erste 50 Plätze aller zwölf Ranglisten). */
export function useWindowHead(h: number | null): AsyncState<WindowData> {
  const { client } = useApp();
  const state = useAsync<WindowData>(client && h ? () => client.windowHead(h) : null, [client, h]);
  return onlyMatching(state, (data) => data.h === h && sameSnapshot(data.snapshot_id, client?.id));
}

/** Vollständige Fensterdatei (alle Mitglieder von V, alle Ranglisten, Status je Instrument). */
export function useWindowFull(h: number | null, enabled = true): AsyncState<WindowData> {
  const { client } = useApp();
  const state = useAsync<WindowData>(client && h && enabled ? () => client.windowFull(h) : null, [client, h, enabled]);
  return onlyMatching(state, (data) => data.h === h && data.part === 'vollstaendig' && sameSnapshot(data.snapshot_id, client?.id));
}

export function useFrequency(enabled = true): AsyncState<FrequencyData> {
  const { client } = useApp();
  const state = useAsync<FrequencyData>(client && enabled ? () => client.frequency() : null, [client, enabled]);
  return onlyMatching(state, (data) => sameSnapshot(data.snapshot_id, client?.id));
}

/** Umschichtungs-Regel: Übersicht aller Varianten (nur in Ständen ab Version 1.3). */
export function useRotationIndex(enabled = true): AsyncState<RotationIndex> {
  const { client, manifest } = useApp();
  const available = enabled && Boolean(manifest?.rotation);
  const state = useAsync<RotationIndex>(client && available ? () => client.rotationIndex() : null, [client, available]);
  return onlyMatching(state, (data) => sameSnapshot(data.snapshot_id, client?.id));
}

/** Umschichtungs-Regel: Verlauf, Orders und Tagesvorschlag einer Variante. */
export function useRotationVariant(key: string | null): AsyncState<RotationVariant> {
  const { client } = useApp();
  const state = useAsync<RotationVariant>(client && key ? () => client.rotationVariant(key) : null, [client, key]);
  return onlyMatching(state, (data) => data.key === key && sameSnapshot(data.snapshot_id, client?.id));
}

export function useSeries(isin: string | null): AsyncState<SeriesData> {
  const { client } = useApp();
  const state = useAsync<SeriesData>(client && isin ? () => client.series(isin) : null, [client, isin]);
  return onlyMatching(state, (data) => data.isin === isin && sameSnapshot(data.snapshot_id, client?.id));
}

export interface ManySeries {
  data: Map<string, SeriesData>;
  errors: Map<string, unknown>;
  pending: number;
}

/** Lädt mehrere Kursreihen mit begrenzter Parallelität (Schutz vor tausenden Anfragen).
 * Bereits geladene Reihen kommen aus dem Zwischenspeicher des Snapshot-Clients. */
export function useSeriesMany(isins: string[], limit = 6): ManySeries {
  const { client } = useApp();
  const key = isins.join(',');
  const [state, setState] = useState<ManySeries>({ data: new Map(), errors: new Map(), pending: isins.length });
  useEffect(() => {
    if (!client) return;
    let cancelled = false;
    const queue = [...new Set(isins)];
    const data = new Map<string, SeriesData>();
    const errors = new Map<string, unknown>();
    let active = 0;
    let index = 0;
    let done = 0;
    setState({ data: new Map(), errors: new Map(), pending: queue.length });
    const publish = () => {
      if (!cancelled) setState({ data: new Map(data), errors: new Map(errors), pending: queue.length - done });
    };
    const next = () => {
      while (!cancelled && active < limit && index < queue.length) {
        const isin = queue[index];
        index += 1;
        active += 1;
        client
          .series(isin)
          .then(
            (series) => data.set(isin, series),
            (error) => errors.set(isin, error),
          )
          .finally(() => {
            active -= 1;
            done += 1;
            publish();
            next();
          });
      }
    };
    next();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, key, limit]);
  return state;
}
