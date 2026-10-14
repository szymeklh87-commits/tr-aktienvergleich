import { useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import * as f from '../lib/format';
import { useApp } from '../state/AppState';
import { IconCheck, IconChevron, IconCopy, IconStar } from './icons';

/** Kursrendite mit Vorzeichen, Text und Farbe (Farbe nie allein bedeutungstragend). */
export function Pct({ value, digits = 2, strong = false }: { value: number | null | undefined; digits?: number; strong?: boolean }) {
  const dir = f.direction(value);
  const label = dir === 'fehlt' ? 'nicht berechenbar' : `${f.pct(value, digits)} (${f.directionWord(value)})`;
  return (
    <span className={`pct pct-${dir}${strong ? ' pct-strong' : ''}`} aria-label={label}>
      {f.pct(value, digits)}
    </span>
  );
}

/** ISIN sichtbar mit Kopierfunktion und zugänglicher Rückmeldung. */
export function IsinCopy({ isin, compact = false }: { isin: string; compact?: boolean }) {
  const [copied, setCopied] = useState<'ok' | 'fehler' | null>(null);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const copy = async (event: Event) => {
    event.stopPropagation();
    event.preventDefault();
    let ok = false;
    try {
      await navigator.clipboard.writeText(isin);
      ok = true;
    } catch {
      const area = document.createElement('textarea');
      area.value = isin;
      document.body.appendChild(area);
      area.select();
      try {
        ok = document.execCommand('copy');
      } catch {
        ok = false;
      }
      area.remove();
    }
    setCopied(ok ? 'ok' : 'fehler');
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(null), 2200);
  };
  return (
    <span className={`isin${compact ? ' isin-compact' : ''}`}>
      <span className="isin-code" translate="no">
        {isin}
      </span>
      <button type="button" className="icon-btn isin-copy" onClick={copy} aria-label={`ISIN ${isin} kopieren`}>
        {copied === 'ok' ? <IconCheck /> : <IconCopy />}
      </button>
      <span className="visually-hidden" role="status" aria-live="polite">
        {copied === 'ok' ? `ISIN ${isin} kopiert` : copied === 'fehler' ? 'Kopieren nicht möglich' : ''}
      </span>
      {copied === 'ok' && !compact ? <span className="isin-copied" aria-hidden="true">kopiert</span> : null}
    </span>
  );
}

export function WatchButton({ isin, name }: { isin: string; name: string }) {
  const { watchlist, toggleWatch } = useApp();
  const on = watchlist.includes(isin);
  return (
    <button
      type="button"
      className={`icon-btn watch-btn${on ? ' is-on' : ''}`}
      aria-pressed={on}
      aria-label={on ? `${name} von der Watchlist entfernen` : `${name} zur Watchlist hinzufügen`}
      onClick={(e: Event) => {
        e.stopPropagation();
        e.preventDefault();
        toggleWatch(isin);
      }}
    >
      <IconStar filled={on} />
    </button>
  );
}

export function Notice({
  tone = 'info',
  title,
  children,
  actions,
  compact = false,
}: {
  tone?: 'info' | 'warn' | 'demo' | 'error';
  title?: string;
  children?: ReactNode;
  actions?: ReactNode;
  /** eine schmale Zeile (Text links, Knopf rechts) – für Hinweise, die auf jeder Seite stehen */
  compact?: boolean;
}) {
  if (compact) {
    return (
      <div className={`notice notice-${tone} notice-compact`} role={tone === 'error' ? 'alert' : undefined}>
        <div className="notice-body">{children}</div>
        {actions ? <div className="notice-actions">{actions}</div> : null}
      </div>
    );
  }
  return (
    <div className={`notice notice-${tone}`} role={tone === 'error' ? 'alert' : undefined}>
      {title ? <p className="notice-title">{title}</p> : null}
      {children ? <div className="notice-body">{children}</div> : null}
      {actions ? <div className="notice-actions">{actions}</div> : null}
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <p className="empty-title">{title}</p>
      {children ? <div className="empty-body">{children}</div> : null}
      {action ? <div className="empty-action">{action}</div> : null}
    </div>
  );
}

export function Segmented<T extends string | number>({
  label,
  options,
  value,
  onChange,
  hideLabel = false,
}: {
  label: string;
  options: { value: T; label: string; title?: string }[];
  value: T;
  onChange: (value: T) => void;
  hideLabel?: boolean;
}) {
  const id = useId();
  return (
    <div className="segmented-wrap">
      <span id={id} className={hideLabel ? 'visually-hidden' : 'control-label'}>
        {label}
      </span>
      <div className="segmented" role="radiogroup" aria-labelledby={id}>
        {options.map((option) => (
          <button
            key={String(option.value)}
            type="button"
            role="radio"
            aria-checked={option.value === value}
            className={option.value === value ? 'is-active' : ''}
            title={option.title}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Höhe der eingeklappten Einleitung (etwa drei Zeilen) in rem. */
const INTRO_CLAMP_REM = 4.3;

/**
 * Erklärender Einleitungstext oben in einer Ansicht: auf dem Handy auf etwa drei Zeilen gekürzt, damit
 * die Inhalte gleich sichtbar sind; „Mehr“ zeigt den ganzen Text. Kurze Texte bleiben ohne Knopf.
 */
export function ViewIntro({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [long, setLong] = useState(false);
  const id = useId();
  const check = () => {
    const el = ref.current;
    if (!el) return;
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const next = el.scrollHeight > INTRO_CLAMP_REM * rem + 6;
    setLong((prev) => (prev === next ? prev : next));
  };
  // nach jeder Darstellung (Text kann sich ändern) und bei Größenänderung (Drehen, Schriftgröße)
  useEffect(check);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(check);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  const clamped = long && !open;
  return (
    <div className={`view-intro-wrap${clamped ? ' is-clamped' : ''}`}>
      <div className="view-intro-body" id={id} ref={ref}>
        {children}
      </div>
      {long ? (
        <button type="button" className="view-intro-more" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
          {open ? 'Weniger anzeigen' : 'Mehr zu dieser Ansicht'}
          <IconChevron open={open} />
        </button>
      ) : null}
    </div>
  );
}

export function Disclosure({ summary, children, defaultOpen = false }: { summary: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div className={`disclosure${open ? ' is-open' : ''}`}>
      <button type="button" className="disclosure-toggle" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
        <span>{summary}</span>
        <IconChevron open={open} />
      </button>
      <div id={id} hidden={!open} className="disclosure-body">
        {open ? children : null}
      </div>
    </div>
  );
}

export function Pager({ page, pages, onChange, label }: { page: number; pages: number; onChange: (page: number) => void; label: string }) {
  if (pages <= 1) return null;
  return (
    <nav className="pager" aria-label={label}>
      <button type="button" className="btn btn-quiet" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        Vorherige
      </button>
      <span className="pager-info">
        Seite {page} von {pages}
      </span>
      <button type="button" className="btn btn-quiet" disabled={page >= pages} onClick={() => onChange(page + 1)}>
        Nächste
      </button>
    </nav>
  );
}

export function KeyValues({ items }: { items: [ReactNode, ReactNode][] }) {
  return (
    <dl className="kv">
      {items.map(([k, v], i) => (
        <div className="kv-row" key={i}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Loading({ label = 'Daten werden geladen', height = 160 }: { label?: string; height?: number }) {
  return (
    <div className="loading" style={{ minHeight: height }} role="status" aria-live="polite">
      <span className="loading-bar" aria-hidden="true" />
      <span>{label} …</span>
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  const text = error instanceof Error ? error.message : String(error);
  const offline = /verbindung|offline|503/i.test(text);
  return (
    <Notice tone={offline ? 'warn' : 'error'} title={offline ? 'Offline nicht verfügbar' : 'Daten konnten nicht geladen werden'}>
      <p>{offline ? 'Diese Daten wurden auf diesem Gerät noch nicht gespeichert. Mit Internetverbindung erneut öffnen.' : text}</p>
    </Notice>
  );
}

export function SectionTitle({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <h2 className="section-title" id={id}>
      {children}
    </h2>
  );
}
