/* Einschätzung je Aktie am angezeigten Kurs (ab 1.24.0): kompakte Zeile für Listen und Karte „Auf einen Blick“ für die
 * Einzelansicht. Rechnen: lib/bewertung.ts; hier nur Anzeige. */

import { useMemo, useState, useSyncExternalStore, type ReactNode } from 'react';
import {
  assessEntry,
  assessPosition,
  ENTRY_EMOJI,
  GROUP_TITLE,
  historyRows,
  historySentence,
  ownHistory,
  POSITION_EMOJI,
  positionLines,
  priceBasis,
  riskOf,
  statsText,
  type EntryAssessment,
  type PositionAssessment,
  type PriceBasis,
} from '../lib/bewertung';
import * as f from '../lib/format';
import { useSignals } from '../lib/hooks';
import { unitOf } from '../lib/instruments';
import { isIntraday } from '../lib/intraday';
import { loadPositions, parseAmount, savePosition, subscribePositions } from '../lib/positionen';
import { signalIndex } from '../lib/signals';
import { crvText, signalGate, stockIssue, type SignalGate } from '../lib/tradeplan';
import type { Light, NewsItem, SignalsData } from '../lib/types';
import { useApp } from '../state/AppState';
import { useUpdates } from '../state/UpdateState';
import type { ChartLevels } from './charts';
import { useNow } from './refresh';
import { LightTag } from './signals';
import { Disclosure } from './ui';

export interface Assessment {
  k: number;
  idx: number;
  data: SignalsData;
  gate: SignalGate;
  basis: PriceBasis;
  entry: EntryAssessment;
  unit: string | null;
}

/** Einschätzung einer Aktie (Index im Datenstand) – null ohne Signal-Stand oder wenn die Aktie darin fehlt. */
export function useAssessment(idx: number | null | undefined, tickMs = 60_000): Assessment | null {
  const { instruments, manifest, status, isDemo } = useApp();
  const signals = useSignals();
  const { quotes } = useUpdates();
  const data = signals.data ?? null;
  const isin = instruments && idx !== null && idx !== undefined && idx >= 0 ? instruments.isin[idx] : null;
  const quote = isin ? (quotes.get(isin) ?? null) : null;
  // „aktuell“ hängt von der Uhrzeit ab: mit Kurs aus „Jetzt aktualisieren“ jede Minute neu bewerten
  const now = useNow(tickMs, Boolean(quote));
  return useMemo(() => {
    if (!data || !instruments || !isin || idx === null || idx === undefined) return null;
    const k = signalIndex(data).get(isin) ?? -1;
    if (k < 0) return null;
    const gate = signalGate({ status, manifest, signals: data, isDemo });
    const unit = unitOf(instruments, idx);
    const interim =
      manifest && isIntraday(manifest) && manifest.zwischenstand?.basis_geprueft !== false && instruments.last_close_day[idx] === manifest.cutoff_day
        ? instruments.last_close[idx]
        : null;
    const basis = priceBasis({
      close: data.kurs[k],
      closeDay: data.kurs_tag[k],
      unit,
      quote,
      provisional: interim !== null ? { price: interim, timeIso: manifest?.zwischenstand?.kurse_bis_utc ?? null } : null,
      now,
    });
    const h = data.handel;
    const plan = h ? { status: h.status[k], reason: h.grund[k], entry: h.einstieg[k], stop: h.stop[k], target: h.ziel[k], late: Boolean(h.zu_spaet[k]) } : null;
    const entry = assessEntry({ gate, issue: stockIssue(instruments, idx), plan, basis });
    return { k, idx, data, gate, basis, entry, unit };
  }, [data, instruments, isin, idx, quote, status, manifest, isDemo, now]);
}

const ENTRY_CLASS = { guenstig: 'assess-go', abwarten: 'assess-wait', kein: 'assess-stop', unklar: 'assess-none' } as const;
const POSITION_CLASS = { halten: 'assess-hold', verkaufen: 'assess-stop', unklar: 'assess-none' } as const;

/** Ampel zum Kaufzeitpunkt als Plakette; DEMO nie in Ampelfarben. */
export function EntryBadge({ a, compact = false }: { a: EntryAssessment; compact?: boolean }) {
  // DEMO nie in Ampelfarben (wie die Plakette der Kaufkandidaten): kein farbiger Punkt, Farbe der DEMO-Hinweise
  if (a.demo && (a.light === 'guenstig' || a.light === 'abwarten')) {
    return (
      <span className={`assess-badge assess-demo${compact ? ' assess-compact' : ''}`} title={a.reason}>
        DEMO-Beispiel: {a.label}
      </span>
    );
  }
  return (
    <span className={`assess-badge ${ENTRY_CLASS[a.light]}${compact ? ' assess-compact' : ''}`} title={a.reason}>
      <span aria-hidden="true">{ENTRY_EMOJI[a.light]}</span> {a.label}
    </span>
  );
}

function PositionBadge({ p }: { p: PositionAssessment }) {
  return (
    <span className={`assess-badge ${POSITION_CLASS[p.light]}`}>
      <span aria-hidden="true">{POSITION_EMOJI[p.light]}</span> {p.label}
    </span>
  );
}

const RISK_CLASS = { niedrig: 'risk-low', mittel: 'risk-mid', hoch: 'risk-high', unbekannt: 'risk-none' } as const;

/** Kompakte Zeile für Listen: Kaufzeitpunkt am Kurs, Kurzgrund, Risiko. Ohne Signal-Stand: nichts. */
export function AssessLine({ idx }: { idx: number }) {
  const a = useAssessment(idx, 120_000);
  const position = usePosition(a ? a.data.isin[a.k] : null);
  if (!a) return null;
  const risk = riskOf(a.data, a.k);
  const own = position ? positionView(a, position) : null;
  return (
    <span className="assess-line">
      {own ? <PositionBadge p={own} /> : <EntryBadge a={a.entry} compact />}
      <span className="assess-short">{own ? (own.pnl !== null ? `seit Einstand ${f.pct(own.pnl, 1)}` : own.reason) : a.entry.short}</span>
      {risk && risk.level !== 'unbekannt' ? <span className={`assess-risk ${RISK_CLASS[risk.level]}`}>{risk.label}</span> : null}
      {a.basis.kind !== 'schluss' || a.entry.light === 'unklar' ? null : <span className="assess-basis">Schlusskurs</span>}
    </span>
  );
}

/* ---------------------------------------------------------------- Positionen */

function usePosition(isin: string | null) {
  const all = useSyncExternalStore(subscribePositions, loadPositions);
  return isin ? (all[isin] ?? null) : null;
}

function positionView(a: Assessment, position: ReturnType<typeof usePosition>): PositionAssessment | null {
  if (!position) return null;
  const rules = a.data.handel?.regeln;
  const atr = a.data.merkmale.atr?.[a.k] ?? null;
  return assessPosition({ position, basis: a.basis, atrPct: atr, close: a.data.kurs[a.k], stopAtr: rules?.stop_atr ?? 2, targetR: rules?.ziel_r ?? 2 });
}

function PositionForm({ isin, unit, onDone }: { isin: string; unit: string | null; onDone: () => void }) {
  const current = usePosition(isin);
  const [price, setPrice] = useState(current ? String(current.kurs).replace('.', ',') : '');
  const [date, setDate] = useState(current?.datum ?? '');
  const [error, setError] = useState<string | null>(null);
  const submit = (event: Event) => {
    event.preventDefault();
    const value = parseAmount(price);
    if (value === null) {
      setError('Bitte einen Kurs größer null eingeben, z. B. 17,79.');
      return;
    }
    const stored = savePosition(isin, { kurs: value, einheit: unit, datum: /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null });
    setError(stored ? null : 'Gespeichert nur bis zum Schließen der App (Speicher des Browsers nicht verfügbar).');
    if (stored) onDone();
  };
  return (
    <form className="position-form" onSubmit={submit}>
      <label>
        Einstandskurs je Aktie{unit ? ` in ${unit}` : ''}
        <input inputMode="decimal" autoComplete="off" value={price} onInput={(e: Event) => setPrice((e.target as HTMLInputElement).value)} placeholder="z. B. 17,79" required />
      </label>
      <label>
        Kaufdatum (freiwillig)
        <input type="date" value={date} onInput={(e: Event) => setDate((e.target as HTMLInputElement).value)} />
      </label>
      {error ? <p className="form-error">{error}</p> : null}
      <div className="toolbar">
        <button type="submit" className="btn btn-primary">
          Position speichern
        </button>
        {current ? (
          <button
            type="button"
            className="btn btn-quiet"
            onClick={() => {
              savePosition(isin, null);
              onDone();
            }}
          >
            Position entfernen
          </button>
        ) : null}
        <button type="button" className="btn btn-quiet" onClick={onDone}>
          Abbrechen
        </button>
      </div>
      <p className="section-note">Nur auf diesem Gerät gespeichert. Keine Order, keine Verbindung zu einem Depot.</p>
    </form>
  );
}

/* ---------------------------------------------------------------- Karte „Auf einen Blick“ */

function lightSentence(light: Light, reason: string | null, horizon: string): string {
  const word = light === 'gruen' ? 'Signale überwiegend positiv' : light === 'rot' ? 'Signale überwiegend negativ' : light === 'gelb' ? 'Signale gemischt' : 'nicht beurteilbar';
  return reason ? `${reason} (Sicht: ${horizon})` : `${word} (Sicht: ${horizon})`;
}

function topNews(items: NewsItem[] | null | undefined): { good: NewsItem | null; bad: NewsItem | null } {
  const related = (items ?? []).filter((n) => n.bezug).sort((a, b) => b.zeit - a.zeit);
  return { good: related.find((n) => n.tendenz > 0) ?? null, bad: related.find((n) => n.tendenz < 0) ?? null };
}

function NewsLine({ item, tone }: { item: NewsItem; tone: 'plus' | 'minus' }) {
  return (
    <li className={`glance-news glance-news-${tone}`}>
      <span aria-hidden="true">{tone === 'plus' ? '▲' : '▼'}</span>{' '}
      <a href={item.link} target="_blank" rel="noopener noreferrer">
        {item.titel}
      </a>{' '}
      <small>
        {item.quelle ?? 'Quelle unbekannt'}, {f.berlinTime(new Date(item.zeit * 1000).toISOString())}
      </small>
    </li>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="glance-row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

/** Alles Wichtige zu einer Aktie auf einen Blick – Einzelheiten aufklappbar. */
export function GlanceCard({ idx, news }: { idx: number; news?: NewsItem[] | null }) {
  const a = useAssessment(idx);
  const isin = a ? a.data.isin[a.k] : null;
  const position = usePosition(isin);
  const [editing, setEditing] = useState(false);
  if (!a || !isin) return null;
  const { data, k, entry, basis, unit } = a;
  const own = positionView(a, position);
  const risk = riskOf(data, k);
  const status = data.handel?.status[k] ?? null;
  const history = historySentence(data.rueckblick, status);
  const ownHist = ownHistory(data, k);
  const up5 = data.steigt_5?.[k] ?? null;
  const up20 = data.steigt_20?.[k] ?? null;
  const { good, bad } = topNews(news);
  return (
    <section className="section glance" aria-labelledby="auf-einen-blick">
      <h3 className="section-title" id="auf-einen-blick">
        Auf einen Blick
      </h3>
      <p className="glance-price">
        <strong>{basis.label}</strong>
        {basis.note ? <span className="glance-basis">{basis.note}</span> : null}
      </p>
      <dl className="glance-list">
        <Row label={own ? 'Eigene Position' : 'Kaufzeitpunkt'}>
          {own ? <PositionBadge p={own} /> : <EntryBadge a={entry} />}
          <span className="glance-text">{own ? own.reason : entry.reason}</span>
          {own ? (
            <span className="glance-sub">
              Kaufzeitpunkt für weitere Käufe: <EntryBadge a={entry} compact />
            </span>
          ) : null}
        </Row>
        <Row label="Kurzfristig">
          <LightTag light={data.kurz_ampel[k]} compact />
          <span className="glance-text">{lightSentence(data.kurz_ampel[k], data.kurz_grund[k], 'Tage bis wenige Wochen')}</span>
        </Row>
        <Row label="Langfristig">
          <LightTag light={data.lang_ampel[k]} compact />
          <span className="glance-text">{lightSentence(data.lang_ampel[k], data.lang_grund[k], 'etwa 12 Monate')}</span>
        </Row>
        {up5 !== null || up20 !== null ? (
          <Row label="Anstieg danach">
            <span className="glance-text">
              Ähnliche Fälle stiegen {up5 !== null ? `in 5 Handelstagen in ${f.plainPct(up5 * 100, 0)}` : ''}
              {up5 !== null && up20 !== null ? ', ' : ''}
              {up20 !== null ? `in 20 Handelstagen in ${f.plainPct(up20 * 100, 0)}` : ''} der Fälle – Häufigkeit aus der Vergangenheit, keine Zusage.
            </span>
          </Row>
        ) : null}
        {history ? (
          <Row label="Bisher">
            <span className="glance-text">{history}</span>
            {ownHist ? <span className="glance-sub">{ownHist.text}</span> : null}
          </Row>
        ) : null}
        {risk ? (
          <Row label="Risiko">
            <span className={`assess-risk ${RISK_CLASS[risk.level]}`}>{risk.label}</span>
            {risk.reasons.length ? (
              <ul className="glance-reasons">
                {risk.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            ) : null}
          </Row>
        ) : null}
        {good || bad ? (
          <Row label="Nachrichten">
            <ul className="glance-reasons">
              {good ? <NewsLine item={good} tone="plus" /> : null}
              {bad ? <NewsLine item={bad} tone="minus" /> : null}
            </ul>
          </Row>
        ) : null}
      </dl>
      <div className="toolbar">
        <button type="button" className="btn btn-quiet" onClick={() => setEditing(!editing)} aria-expanded={editing}>
          {position ? 'Eigene Position ändern' : 'Eigene Position eintragen'}
        </button>
      </div>
      {editing ? <PositionForm isin={isin} unit={unit} onDone={() => setEditing(false)} /> : null}
      <Disclosure summary="Einzelheiten: Marken, Lage, Rückblick, Regeln">
        <GlanceDetails a={a} own={own} />
      </Disclosure>
    </section>
  );
}

function GlanceDetails({ a, own }: { a: Assessment; own: PositionAssessment | null }) {
  const { data, k, entry, basis, unit, gate } = a;
  const h = data.handel;
  const rows = historyRows(data.rueckblick, h?.status[k] ?? null);
  const lines = positionLines(data, k, basis.price, unit);
  const risk = riskOf(data, k);
  const min = data.rueckblick?.mindestens_faelle ?? 30;
  return (
    <div className="prose glance-details">
      {h ? (
        <>
          <h4>Marken der Signalregel ({h.regeln.version})</h4>
          <ul>
            <li>Einstiegslimit {f.price(h.einstieg[k], unit)}{entry.vsEntry !== null ? ` – Kurs ${f.pct(entry.vsEntry, 1)} dazu` : ''}</li>
            <li>Stop {f.price(h.stop[k], unit)}{entry.toStop !== null ? ` – möglicher Verlust ${f.pct(entry.toStop, 1)}` : ''}</li>
            <li>Ziel {f.price(h.ziel[k], unit)}{entry.toTarget !== null ? ` – mögliche Steigerung ${f.pct(entry.toTarget, 1)}` : ''}{h.ziel_basis[k] === 'analysten' ? ' (Ø Kursziel der Analysten)' : ''}</li>
            <li>Chance-Risiko-Verhältnis {crvText(h.crv[k])}</li>
            {own && own.stop !== null ? (
              <li>
                Eigene Position: Stop {f.price(own.stop, unit)}, Ziel {f.price(own.target, unit)} (Einstand − {f.integer(h.regeln.stop_atr)} ATR bzw. + {f.integer(h.regeln.ziel_r)} R)
              </li>
            ) : null}
          </ul>
          <p>
            Grün nur bei einem Kaufsignal der Regel und einem Kurs zwischen Stop und Einstiegslimit; über dem Limit „Abwarten“, am Stop „Kein Kaufsignal“. Ein gefallener Kurs allein
            macht nie grün. {gate.open ? '' : `Derzeit: ${gate.reason ?? 'Daten nicht aktuell'}`}
          </p>
        </>
      ) : null}
      {lines.length ? (
        <>
          <h4>Lage zum Kurs</h4>
          <ul>
            {lines.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </>
      ) : null}
      {rows ? (
        <>
          <h4>{GROUP_TITLE[rows.group]} – Rückblick ohne Vorgriff</h4>
          {rows.plan.length ? (
            <>
              <p>Mit Stop und Ziel (Limitkauf am Folgetag, Stop zuerst, nach Kosten):</p>
              <ul>
                {rows.plan.map((r) => (
                  <li key={`p${r.key}`}>{statsText(r.stats, r.label, min)}</li>
                ))}
              </ul>
            </>
          ) : null}
          <p>Nur gehalten (Schlusskurs nach der Haltedauer, nach Kosten):</p>
          <ul>
            {rows.hold.map((r) => (
              <li key={`h${r.key}`}>{statsText(r.stats, r.label, min)}</li>
            ))}
          </ul>
          {data.rueckblick?.status.vergleich?.halten['10'] ? <p>Zum Vergleich alle Aktien mit Mindestumsatz: {statsText(data.rueckblick.status.vergleich.halten['10'], '10 Tagen', min)}.</p> : null}
          <p className="section-note">
            Zeitraum {f.day(data.rueckblick?.zeitraum.von)} bis {f.day(data.rueckblick?.zeitraum.bis)}. {(data.rueckblick?.hinweise ?? []).join(' ')}
          </p>
        </>
      ) : (
        <p className="section-note">Für diesen Signal-Stand gibt es noch keinen Rückblick der Regel – er kommt mit dem nächsten täglichen Lauf.</p>
      )}
      {risk ? (
        <>
          <h4>So entsteht die Risikostufe ({data.risiko?.version})</h4>
          <p>{data.risiko?.regel}</p>
          {!risk.complete ? <p>Für diese Aktie fehlen Kennzahlen – die Stufe ist unvollständig und deshalb nie „niedrig“.</p> : null}
        </>
      ) : null}
      <p className="section-note">Keine Anlageberatung. Kurse laut Yahoo (inoffiziell, nicht der Handelsplatz von Trade Republic); Signal-Stand vom {f.day(data.cutoff_day)}.</p>
    </div>
  );
}

const ZONE = { guenstig: 'go', abwarten: 'wait', kein: 'stop', unklar: 'none' } as const;

/** Marken für den Kurschart: Einstieg, Stop und Ziel der Signalregel; Widerstand = 20-Tage-Hoch des Signal-Stands,
 * Unterstützung = tiefster Schlusskurs der letzten 20 Sitzungen. Zone wie die Ampel am angezeigten Kurs (DEMO grau). */
export function useChartLevels(idx: number | null | undefined, closes: number[]): ChartLevels | null {
  const a = useAssessment(idx);
  const recent = closes.slice(-20);
  const support = recent.length >= 10 ? Math.min(...recent) : null;
  return useMemo(() => {
    if (!a?.data.handel) return null;
    const { data, k, entry } = a;
    const h = data.handel!;
    const resistance = data.merkmale.hoch20?.[k] ?? null;
    return {
      entry: h.einstieg[k],
      stop: h.stop[k],
      target: h.ziel[k],
      support,
      resistance,
      zone: entry.demo ? 'none' : ZONE[entry.light],
      note: `Marken der Signalregel vom ${f.day(data.kurs_tag[k])} (Schlusskursbasis), Zone nach ${a.basis.label}${entry.demo ? ' – DEMO' : ''}.`,
    };
  }, [a, support]);
}
