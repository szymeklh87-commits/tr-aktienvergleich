import { useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { FIXED_WINDOWS, WEIGHTS } from '../lib/scoring';
import type { Policy } from '../lib/types';
import type { NoiseFlags } from '../lib/turnover';
import { centerActive } from '../lib/scroll';
import { IconMinus, IconPlus } from './icons';
import { useApp } from '../state/AppState';

const MAJOR = new Set([1, 7, 14, 21, 30, 45, 60, 90]);

/** Feste Schnellwahl 7, 14, 21, 30, 40, 50, 60, 70, 80, 90 Kalendertage (zwei Reihen auf dem Handy). */
export function WindowChips({ value, onPick, label = 'Zeitraum wählen (Kalendertage)', onPage = false }: { value: number | null; onPick: (h: number) => void; label?: string; onPage?: boolean }) {
  const ref = useRef<HTMLDivElement | null>(null);
  // als waagerechte Leiste: gewählten Zeitraum sichtbar halten
  useEffect(() => {
    if (onPage) centerActive(ref.current);
  }, [value, onPage]);
  return (
    <div className={`wchips${onPage ? ' on-page' : ''}`} role="group" aria-label={label} ref={ref}>
      {FIXED_WINDOWS.map((h) => (
        <button key={h} type="button" className={`wchip${h === value ? ' is-active' : ''}`} aria-pressed={h === value} onClick={() => onPick(h)}>
          <b>{h}</b> <small>Tage</small>
        </button>
      ))}
    </div>
  );
}

/** Zeitraum 1–90 Kalendertage: feste Schnellwahl, freier Zeitraum (Eingabe) und Lineal mit Schieberegler. */
export function WindowRuler({ value, onChange, children, compact = false }: { value: number; onChange: (h: number) => void; children?: ReactNode; compact?: boolean }) {
  const [live, setLive] = useState(value);
  const timer = useRef<number | undefined>(undefined);
  const id = useId();
  useEffect(() => setLive(value), [value]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const commit = (next: number, immediate = false) => {
    const clamped = Math.min(90, Math.max(1, Math.round(next)));
    setLive(clamped);
    window.clearTimeout(timer.current);
    if (immediate) onChange(clamped);
    else timer.current = window.setTimeout(() => onChange(clamped), 260);
  };

  return (
    <div className={`ruler-block${compact ? ' is-compact' : ''}`}>
      <WindowChips value={value} onPick={(h) => commit(h, true)} />
      <div className="ruler-head">
        <div className="ruler-readout" aria-live="polite">
          <span className="ruler-number">{live}</span>
          <span className="ruler-unit">{live === 1 ? 'Kalendertag' : 'Kalendertage'} zurück</span>
        </div>
        <div className="free-field">
          <label htmlFor={`${id}-num`} className="free-label">
            Freier Zeitraum
            <small>1–90 Tage</small>
          </label>
          <div className="stepper">
            <button type="button" className="icon-btn" aria-label="Einen Tag weniger" disabled={live <= 1} onClick={() => commit(live - 1, true)}>
              <IconMinus />
            </button>
            <input
              id={`${id}-num`}
              className="stepper-input"
              type="number"
              inputMode="numeric"
              min={1}
              max={90}
              step={1}
              value={live}
              aria-label="Zeitraum in Kalendertagen (1 bis 90)"
              onChange={(e: Event) => {
                const text = (e.target as HTMLInputElement).value;
                const number = Number(text);
                if (Number.isInteger(number) && number >= 1 && number <= 90) commit(number);
                else setLive(Number.isFinite(number) ? number : live);
              }}
              onBlur={() => commit(Number.isInteger(live) ? live : value, true)}
            />
            <button type="button" className="icon-btn" aria-label="Einen Tag mehr" disabled={live >= 90} onClick={() => commit(live + 1, true)}>
              <IconPlus />
            </button>
          </div>
        </div>
      </div>
      {children ? <div className="ruler-context">{children}</div> : null}
      <div className="ruler">
        <svg className="ruler-ticks" viewBox="0 0 900 36" preserveAspectRatio="none" aria-hidden="true">
          {Array.from({ length: 90 }, (_, i) => {
            const h = i + 1;
            const x = (i / 89) * 890 + 5;
            const major = MAJOR.has(h);
            const week = h % 7 === 0;
            const len = major ? 18 : week ? 12 : 6;
            return <line key={h} x1={x} x2={x} y1={0} y2={len} className={h <= live ? 'tick tick-on' : 'tick'} />;
          })}
        </svg>
        <input
          className="ruler-range"
          type="range"
          min={1}
          max={90}
          step={1}
          value={live}
          aria-label="Zeitraum in Kalendertagen"
          aria-valuetext={`${live} Kalendertage`}
          onInput={(e: Event) => commit(Number((e.target as HTMLInputElement).value))}
          onChange={(e: Event) => commit(Number((e.target as HTMLInputElement).value))}
        />
        <div className="ruler-labels" aria-hidden="true">
          {[...MAJOR].map((h) => (
            <span key={h} style={{ left: `${((h - 1) / 89) * 100}%` }}>
              {h}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/** Elf Gewichtungen 0/100 … 100/0; erste Zahl = Gleichmäßigkeit. */
export function WeightControl({
  weight,
  onWeight,
  policy,
  onPolicy,
  showPolicy = true,
}: {
  weight: number;
  onWeight: (w: number) => void;
  policy?: Policy;
  onPolicy?: (p: Policy) => void;
  showPolicy?: boolean;
}) {
  const id = useId();
  return (
    <div className="weight-block">
      <div className="weight-head">
        <label htmlFor={id} className="weight-readout">
          <strong>{weight} % Gleichmäßigkeit</strong>
          <span> · {100 - weight} % Rendite</span>
        </label>
      </div>
      <input
        id={id}
        className="weight-range"
        type="range"
        min={0}
        max={100}
        step={10}
        value={weight}
        aria-valuetext={`${weight} Prozent Gleichmäßigkeit, ${100 - weight} Prozent Kursrendite`}
        onChange={(e: Event) => onWeight(Number((e.target as HTMLInputElement).value))}
      />
      <div className="weight-scale" aria-hidden="true">
        {WEIGHTS.map((w) => (
          <span key={w} className={w === weight ? 'is-active' : ''}>
            {w}
          </span>
        ))}
      </div>
      <div className="chips" role="group" aria-label="Gewichtung wählen">
        <button type="button" className={`chip${weight === 0 ? ' is-active' : ''}`} aria-pressed={weight === 0} onClick={() => onWeight(0)}>
          Nur Kursrendite
        </button>
        {[40, 50, 60].map((w) => (
          <button key={w} type="button" className={`chip${weight === w ? ' is-active' : ''}`} aria-pressed={weight === w} onClick={() => onWeight(w)}>
            {w}/{100 - w}
          </button>
        ))}
        <button type="button" className={`chip${weight === 100 ? ' is-active' : ''}`} aria-pressed={weight === 100} onClick={() => onWeight(100)}>
          Nur Gleichmäßigkeit
        </button>
      </div>
      {showPolicy && policy && onPolicy ? (
        <label className="check">
          <input type="checkbox" checked={policy === 'common_trend'} onChange={(e: Event) => onPolicy((e.target as HTMLInputElement).checked ? 'common_trend' : 'native')} />
          <span>
            Gleiches Vergleichsfeld für alle Gewichtungen
            <small>Alle elf Varianten nur auf den gleichmäßig steigenden Aktien (U). Dann ist auch 0/100 eingeschränkt.</small>
          </span>
        </label>
      ) : null}
    </div>
  );
}

/** Ab 1.14 (Simons Wahl „aussagekräftiger“): Rendite-Ranglisten ohne Aktien mit kaum Umsatz (Ø unter 1 Mio. USD am Tag oder
 * nicht bestimmbar) und ohne Einzelsprung (ein Handelstag erklärt mehr als die Hälfte der Kursbewegung). Gilt überall in der
 * App (gespeicherte Einstellung); die Plätze bleiben die der vollständigen Rangliste. */
export function NoiseToggle() {
  const { prefs, setPrefs } = useApp();
  return (
    <label className="check noise-toggle">
      <input type="checkbox" checked={prefs.ohneAuffaellige} onChange={(e: Event) => setPrefs({ ohneAuffaellige: (e.target as HTMLInputElement).checked })} />
      <span>
        Auffällige ausblenden
        <small>Kaum Umsatz (unter 1 Mio. USD am Tag) und Einzelsprünge – Plätze bleiben wie in der vollständigen Rangliste</small>
      </span>
    </label>
  );
}

const LOW_TITLE = 'Ø Tagesumsatz unter 1 Mio. USD – der Kurs lässt sich leicht bewegen, ein Kauf zum angezeigten Kurs ist oft nicht möglich';
const JUMP_TITLE = 'Ein einzelner Handelstag erklärt mehr als die Hälfte der Kursbewegung';

/** Kennzeichen „Kaum Umsatz“ und „Einzelsprung“ einer Ranglistenzeile (ab 1.14). */
export function NoiseBadges({ flags }: { flags: NoiseFlags }) {
  return (
    <>
      {flags.low ? (
        <span className="badge badge-warn" title={LOW_TITLE}>
          Kaum Umsatz
        </span>
      ) : null}
      {flags.jump ? (
        <span className="badge badge-warn" title={JUMP_TITLE}>
          Einzelsprung
        </span>
      ) : null}
    </>
  );
}
