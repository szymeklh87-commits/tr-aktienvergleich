/* Hash-Router: funktioniert auf GitHub Pages in Unterverzeichnissen ohne Serverkonfiguration. */

import { useEffect, useState } from 'react';

export interface Route {
  path: string;
  segments: string[];
  params: URLSearchParams;
}

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#/, '') || '/';
  const [pathPart, query = ''] = raw.split('?');
  const path = pathPart.startsWith('/') ? pathPart : `/${pathPart}`;
  return { path, segments: path.split('/').filter(Boolean).map(decodeURIComponent), params: new URLSearchParams(query) };
}

export function buildHash(path: string, params?: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== null && v !== '') search.set(k, String(v));
  }
  const query = search.toString();
  return `#${path}${query ? `?${query}` : ''}`;
}

export function navigate(path: string, params?: Record<string, string | number | undefined | null>, replace = false): void {
  const hash = buildHash(path, params);
  if (replace) {
    history.replaceState(history.state, '', hash);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } else {
    window.location.hash = hash;
  }
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return route;
}

/** Aktualisiert einzelne Parameter der aktuellen Route ohne neuen Verlaufseintrag. */
export function updateParams(route: Route, changes: Record<string, string | number | undefined | null>): void {
  const params: Record<string, string> = {};
  route.params.forEach((v, k) => {
    params[k] = v;
  });
  for (const [k, v] of Object.entries(changes)) {
    if (v === undefined || v === null || v === '') delete params[k];
    else params[k] = String(v);
  }
  navigate(route.path, params, true);
}
