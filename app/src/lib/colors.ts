/* Kategoriale Farben (validierte Referenzpalette, feste Reihenfolge, nie zyklisch).
 * Höchstens acht Linien gleichzeitig; Farbe folgt der ISIN, nicht dem Rang. */

export const SERIES_LIGHT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948'];
export const SERIES_DARK = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'];
export const MAX_SERIES = 8;

export function seriesColor(slot: number, dark: boolean): string {
  const palette = dark ? SERIES_DARK : SERIES_LIGHT;
  return palette[slot % palette.length];
}

/** Ordnet ISINs stabil Farbplätzen zu: bestehende behalten ihren Platz, neue erhalten den ersten freien. */
export function assignSlots(previous: Record<string, number>, isins: string[]): Record<string, number> {
  const next: Record<string, number> = {};
  const used = new Set<number>();
  for (const isin of isins) {
    if (previous[isin] !== undefined && !used.has(previous[isin])) {
      next[isin] = previous[isin];
      used.add(previous[isin]);
    }
  }
  for (const isin of isins) {
    if (next[isin] !== undefined) continue;
    let slot = 0;
    while (used.has(slot)) slot += 1;
    if (slot >= MAX_SERIES) continue;
    next[isin] = slot;
    used.add(slot);
  }
  return next;
}

export function prefersDark(): boolean {
  const root = document.documentElement;
  if (root.dataset.theme === 'dunkel') return true;
  if (root.dataset.theme === 'hell') return false;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
}
