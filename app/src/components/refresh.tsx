/* „Jetzt aktualisieren“ in den Ansichten (ab 1.21): Knopf mit Fortschritt, Zeitangaben je Kurs, Tagesverlauf. */

import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { progress, type UpdateJob, type UpdateScope } from '../lib/aktualisierung';
import * as f from '../lib/format';
import { buildHash } from '../lib/router';
import { agoText, dayChange, delayText, knownDelay, quoteStatus, whenText, type DayCourse, type LiveQuote } from '../lib/livekurse';
import { useUpdates } from '../state/UpdateState';
import { Pct } from './ui';

/** Sekündlich neu zeichnen, solange etwas läuft (Fortschritt, Alter der Kurse). */
export function useNow(intervalMs: number, enabled = true): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!enabled) return;
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs, enabled]);
  return now;
}

function sameStocks(job: UpdateJob, isins: string[]): boolean {
  if (!job.isins.length) return false;
  const wanted = new Set(isins);
  return job.isins.every((isin) => wanted.has(isin));
}

export function JobProgress({ job, onDismiss }: { job: UpdateJob; onDismiss?: () => void }) {
  const running = job.phase !== 'fertig' && job.phase !== 'fehler' && job.phase !== 'ohne_ergebnis';
  const now = useNow(1000, running);
  const info = progress(job, now);
  return (
    <div className={`update-progress${info.failed ? ' is-failed' : info.done ? ' is-done' : ''}`} role="status" aria-live="polite">
      <p className="update-progress-title">
        {info.title}
        {job.automatic ? <span className="badge">automatisch</span> : null}
      </p>
      {info.fraction !== null ? (
        <div className="progress" role="progressbar" aria-label={info.title} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(info.fraction * 100)}>
          <span className="progress-bar" style={{ width: `${Math.round(info.fraction * 100)}%` }} />
        </div>
      ) : null}
      <p className="update-progress-detail">{info.detail}</p>
      <div className="toolbar">
        {job.runUrl ? (
          <a className="btn btn-quiet" href={job.runUrl} target="_blank" rel="noopener noreferrer">
            Lauf auf GitHub
          </a>
        ) : null}
        {!running && onDismiss ? (
          <button type="button" className="btn btn-quiet" onClick={onDismiss}>
            Ausblenden
          </button>
        ) : null}
      </div>
    </div>
  );
}

export interface RefreshProps {
  scope: Exclude<UpdateScope, 'alles'>;
  /** Aktien in Anzeigereihenfolge (sichtbare zuerst) */
  isins: string[];
  visible?: number;
  /** Tagesverlauf (5 Minuten) für diese Aktien mitliefern */
  courses?: string[];
  /** wofür, z. B. „diese Aktie“, „die Merkliste (12 Aktien)“ */
  what: string;
}

/** Knopf „Jetzt aktualisieren“ für einzelne Aktien – mit Fortschritt; ohne Zugang ein Hinweis zur Einrichtung. */
export function RefreshButton({ scope, isins, visible, courses, what }: RefreshProps) {
  const { access, jobs, request, dismiss } = useUpdates();
  const [message, setMessage] = useState<string | null>(null);
  const job = useMemo(() => jobs.find((j) => j.scope === scope && sameStocks(j, isins)) ?? null, [jobs, scope, isins]);
  const running = job !== null && (job.phase === 'senden' || job.phase === 'wartet' || job.phase === 'laeuft' || job.phase === 'teil');

  if (!isins.length) return null;
  if (access !== 'bereit') {
    return (
      <div className="refresh">
        <a className="btn" href={buildHash('/einstellungen', { abschnitt: 'zugang' })}>
          Jetzt aktualisieren – Zugang einrichten
        </a>
        <p className="section-note">
          {access === 'gesperrt'
            ? 'Der Zugang ist gespeichert, aber gesperrt: erst nach dem Entsperren nutzbar.'
            : `Damit die App Kurse für ${what} selbst abrufen kann, braucht sie einmalig einen GitHub-Zugang (Einstellungen). Ohne Zugang zeigt sie den Stand des letzten Laufs.`}
        </p>
      </div>
    );
  }
  const start = async () => {
    setMessage(null);
    const result = await request(scope, isins, { visible, courses, label: what });
    if (typeof result === 'string') setMessage(result);
  };
  return (
    <div className="refresh">
      <button type="button" className="btn btn-primary" disabled={running} onClick={() => void start()}>
        {running ? 'Wird aktualisiert …' : 'Jetzt aktualisieren'}
      </button>
      <span className="refresh-what">Kurse für {what} neu abrufen (meist unter einer Minute)</span>
      {message ? <p className="section-note warn-text">{message}</p> : null}
      {job ? <JobProgress job={job} onDismiss={() => dismiss(job.kennung)} /> : null}
    </div>
  );
}

/** Drei getrennte Zeitangaben eines gelieferten Kurses und sein Zustand (neu gerechnet bei jeder Anzeige). */
export function QuoteTimes({ quote, compact = false }: { quote: LiveQuote; compact?: boolean }) {
  const now = useNow(30_000);
  const state = quoteStatus(quote, now);
  const tone = state.state === 'aktuell' ? 'badge-live' : state.state === 'nicht_aktuell' ? 'badge-warn' : '';
  if (compact) {
    return (
      <span className="quote-times-compact">
        <span className={`badge ${tone}`}>{state.badge}</span> {state.quoteText} · {state.fetchText} · {state.delayText}
      </span>
    );
  }
  return (
    <dl className="kv quote-times">
      <div className="kv-row">
        <dt>Zustand</dt>
        <dd>
          <span className={`badge ${tone}`}>{state.badge}</span>
        </dd>
      </div>
      <div className="kv-row">
        <dt>Kurszeit</dt>
        <dd>{state.quoteText.replace(/^Kurszeit /, '')}</dd>
      </div>
      <div className="kv-row">
        <dt>Abrufzeit</dt>
        <dd>{state.fetchText.replace(/^abgerufen /, '')}</dd>
      </div>
      <div className="kv-row">
        <dt>Bekannte Verzögerung</dt>
        <dd>{state.delayText}</dd>
      </div>
    </dl>
  );
}

/** Zeitangaben eines Kurses aus dem veröffentlichten Stand (ohne Lieferung). */
export function StandPriceTimes({ kind, quoteIso, day, fetchedIso, symbol }: { kind: 'schluss' | 'vorlaeufig'; quoteIso: string | null; day: number | null; fetchedIso: string | null; symbol: string | null }) {
  const now = useNow(60_000);
  const delay = knownDelay(symbol);
  const quoteMs = quoteIso ? Date.parse(quoteIso) : NaN;
  const fetchedMs = fetchedIso ? Date.parse(fetchedIso) : NaN;
  return (
    <dl className="kv quote-times">
      <div className="kv-row">
        <dt>Zustand</dt>
        <dd>
          <span className="badge badge-wrap">{kind === 'schluss' ? `Schlusskurs vom ${f.day(day)} – kein aktueller Kurs` : `vorläufiger Kurs (Zwischenstand)${Number.isFinite(quoteMs) ? `, ${agoText(quoteMs, now)}` : ''}`}</span>
        </dd>
      </div>
      <div className="kv-row">
        <dt>Kurszeit</dt>
        <dd>{kind === 'schluss' ? `Börsenschluss am ${f.day(day)}` : Number.isFinite(quoteMs) ? whenText(quoteMs, now) : '–'}</dd>
      </div>
      <div className="kv-row">
        <dt>Abrufzeit</dt>
        <dd>{Number.isFinite(fetchedMs) ? `${whenText(fetchedMs, now)} (${agoText(fetchedMs, now)})` : '–'}</dd>
      </div>
      <div className="kv-row">
        <dt>Bekannte Verzögerung</dt>
        <dd>{kind === 'schluss' ? 'entfällt (Schlusskurs)' : delayText(delay, delay !== null ? 'yahoo_hilfe' : null)}</dd>
      </div>
    </dl>
  );
}

/** Kurs mit Veränderung zum Vortag – eine Zeile. */
export function LivePriceLine({ quote, unit }: { quote: LiveQuote; unit: string | null }) {
  const change = dayChange(quote);
  return (
    <span className="live-price">
      {f.price(quote.price, quote.unit ?? unit)}
      {change !== null ? (
        <span>
          {' '}
          <Pct value={change} /> zum Vortag
        </span>
      ) : null}
    </span>
  );
}

const timeFmt = new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Berlin' });

/** Tagesverlauf (5-Minuten-Kurse) als schlichte Linie mit Anfangs- und Endzeit. */
export function DayCourseChart({ course, unit, previousClose }: { course: DayCourse; unit: string | null; previousClose?: number | null }): ReactNode {
  const width = 360;
  const height = 120;
  const pad = { l: 44, r: 8, t: 8, b: 18 };
  const values = previousClose ? [...course.c, previousClose] : course.c;
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || Math.abs(hi) * 0.01 || 1;
  const t0 = course.t[0];
  const t1 = course.t[course.t.length - 1];
  const x = (t: number) => pad.l + ((t - t0) / Math.max(1, t1 - t0)) * (width - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - (v - lo) / span) * (height - pad.t - pad.b);
  const path = course.t.map((t, i) => `${i ? 'L' : 'M'}${x(t).toFixed(1)},${y(course.c[i]).toFixed(1)}`).join('');
  const last = course.c[course.c.length - 1];
  const up = previousClose ? last >= previousClose : last >= course.c[0];
  return (
    <figure className="day-course">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Tagesverlauf von ${timeFmt.format(new Date(t0 * 1000))} bis ${timeFmt.format(new Date(t1 * 1000))} Uhr, zuletzt ${f.price(last, unit)}`}>
        {previousClose ? <line x1={pad.l} x2={width - pad.r} y1={y(previousClose)} y2={y(previousClose)} className="day-course-ref" /> : null}
        <path d={path} className={up ? 'day-course-line up' : 'day-course-line down'} />
        <text x={pad.l - 4} y={pad.t + 8} textAnchor="end" className="day-course-axis">
          {f.price(hi)}
        </text>
        <text x={pad.l - 4} y={height - pad.b} textAnchor="end" className="day-course-axis">
          {f.price(lo)}
        </text>
        <text x={pad.l} y={height - 4} className="day-course-axis">
          {timeFmt.format(new Date(t0 * 1000))}
        </text>
        <text x={width - pad.r} y={height - 4} textAnchor="end" className="day-course-axis">
          {timeFmt.format(new Date(t1 * 1000))}
        </text>
      </svg>
      <figcaption className="section-note">
        Tagesverlauf in 5-Minuten-Schritten (Berliner Zeit), {course.c.length} Kurse{previousClose ? ', gestrichelt: Schluss des Vortags' : ''}. Abgerufen {whenText(course.fetchedAt)}. Je
        Börse verzögert – kein ausführbarer Trade-Republic-Kurs.
      </figcaption>
    </figure>
  );
}
