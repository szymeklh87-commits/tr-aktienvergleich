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
