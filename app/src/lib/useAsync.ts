import { useEffect, useRef, useState } from 'react';

export interface AsyncState<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
}

/** Lädt asynchron und hält den vorherigen Wert während des Nachladens (keine springenden Zeilen). */
export function useAsync<T>(factory: (() => Promise<T>) | null, deps: readonly unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: Boolean(factory) });
  const generation = useRef(0);
  useEffect(() => {
    if (!factory) {
      setState({ data: null, error: null, loading: false });
      return;
    }
    const current = ++generation.current;
    setState((previous) => ({ data: previous.data, error: null, loading: true }));
    factory().then(
      (data) => {
        if (current === generation.current) setState({ data, error: null, loading: false });
      },
      (error) => {
        if (current === generation.current) setState((previous) => ({ data: previous.data, error, loading: false }));
      },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
