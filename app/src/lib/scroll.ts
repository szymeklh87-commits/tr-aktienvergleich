/* Scrollposition je Ansicht merken: „Zurück“ landet wieder an derselben Stelle
 * (z. B. im Chart-Raster), Parameteränderungen innerhalb einer Ansicht springen nicht nach oben. */

import { useEffect } from 'react';

const positions = new Map<string, number>();

export function useScrollMemory(key: string): void {
  useEffect(() => {
    let frame = 0;
    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => positions.set(key, window.scrollY));
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('scroll', onScroll);
    };
  }, [key]);

  useEffect(() => {
    const target = positions.get(key) ?? 0;
    if (target <= 0) {
      window.scrollTo(0, 0);
      return;
    }
    let tries = 0;
    let timer = 0;
    const attempt = () => {
      const reachable = document.documentElement.scrollHeight - window.innerHeight >= target - 2;
      if (reachable || tries >= 40) {
        window.scrollTo(0, target);
        return;
      }
      tries += 1;
      timer = window.setTimeout(attempt, 50);
    };
    timer = window.setTimeout(attempt, 0);
    return () => window.clearTimeout(timer);
  }, [key]);
}

/** Waagerecht scrollende Leiste (Unterreiter, Schnellwahl): das aktive Element mittig zeigen, ohne die Seite
 * senkrecht zu verschieben (ab 1.10 – auf dem Handy war der aktive Reiter sonst oft halb abgeschnitten). */
export function centerActive(strip: HTMLElement | null, selector = '.is-active'): void {
  if (!strip) return;
  const item = strip.querySelector<HTMLElement>(selector);
  if (!item || strip.scrollWidth <= strip.clientWidth + 1) return;
  const box = strip.getBoundingClientRect();
  const rect = item.getBoundingClientRect();
  const delta = rect.left + rect.width / 2 - (box.left + box.width / 2);
  strip.scrollLeft = Math.max(0, Math.min(strip.scrollWidth - strip.clientWidth, strip.scrollLeft + delta));
}
