import { useMemo, useState } from 'react';
import { WindowRuler } from '../components/controls';
import { InstrumentRow } from '../components/rows';
import { Disclosure, ErrorNote, Loading, Pager, Pct, SectionTitle } from '../components/ui';
import { READY_LEVEL, statusInfo } from '../lib/codes';
import * as f from '../lib/format';
import { useWindowFull } from '../lib/hooks';
import { listingShort, typeLabel } from '../lib/instruments';
import { buildHash, updateParams, type Route } from '../lib/router';
import { decodeStatus, parseWindow } from '../lib/scoring';
import { search } from '../lib/search';
import { useApp } from '../state/AppState';

const PAGE = 50;

const IconSearch = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" aria-hidden="true" focusable="false">
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4.5 4.5" />
  </svg>
);

export function CoverageView({ route }: { route: Route }) {
  const { manifest, instruments, searchIndex, prefs } = useApp();
  const h = parseWindow(route.params.get('h'), prefs.h);
  const query = route.params.get('q') ?? '';
  const filter = route.params.get('status');
  const page = Math.max(1, Number(route.params.get('seite') ?? 1) || 1);
  const [draft, setDraft] = useState(query);
  const full = useWindowFull(h);

  const windowStatus = useMemo(() => (full.data?.status_b64 ? decodeStatus(full.data.status_b64) : null), [full.data]);
  const returns = useMemo(() => {
    const map = new Map<number, number>();
    full.data?.m.idx.forEach((idx, pos) => map.set(idx, full.data!.m.r[pos]));
    return map;
  }, [full.data]);

  if (!manifest || !instruments || !searchIndex) return null;
  const cov = manifest.coverage;
  const perWindow = cov.per_window.find((x) => x.h === h);
  const levelEntries = Object.entries(cov.instrument_level).sort((x, y) => Number(x[0]) - Number(y[0]));
  const levelSum = levelEntries.reduce((n, [, count]) => n + count, 0);
  const windowEntries = Object.entries(perWindow?.by_status ?? {}).sort((x, y) => Number(x[0]) - Number(y[0]));
  const statusOf = (i: number): number => (windowStatus ? windowStatus[i] : instruments.level_status[i]);

  let list: number[] = query.trim() ? search(searchIndex, instruments, query, instruments.count) : Array.from({ length: instruments.count }, (_, i) => i);
  if (filter !== null && filter !== '') {
    const [scope, code] = filter.split(':');
    const value = Number(code);
    list = list.filter((i) => (scope === 'ebene' ? instruments.level_status[i] === value : statusOf(i) === value));
  }
  const pages = Math.max(1, Math.ceil(list.length / PAGE));
  const current = Math.min(page, pages);
  const visible = list.slice((current - 1) * PAGE, current * PAGE);

  const filterLabel = (() => {
    if (!filter) return null;
    const [scope, code] = filter.split(':');
    const info = statusInfo(manifest, Number(code));
    return scope === 'ebene' ? `Hauptstatus: ${info.kurz ?? info.key}` : `${f.windowLabel(h)}: ${info.kurz ?? info.key}`;
  })();

  return (
    <div className="view">
      <header className="view-head">
        <p className="lede">Das ganze Aktienuniversum der TR-Liste – auch Aktien ohne Kurshistorie, mit unklarer Identität oder ohne Aufwärtstrend. Jede Aktie hat genau einen Hauptstatus; die Summe ergibt das Universum.</p>
      </header>

      <div className="stats">
        <div className="stat">
          <span className="stat-value">{f.integer(cov.universe_total)}</span>
          <span className="stat-label">ISINs in der TR-Aktienliste</span>
        </div>
        <div className="stat">
          <span className="stat-value">{f.integer(cov.identified)}</span>
          <span className="stat-label">eindeutig einer Börsennotierung zugeordnet</span>
        </div>
        <div className="stat">
          <span className="stat-value">{f.integer(cov.histories_loaded)}</span>
          <span className="stat-label">Kurshistorien geladen</span>
        </div>
        <div className="stat">
          <span className="stat-value">{f.integer(cov.with_any_return_window)}</span>
          <span className="stat-label">mit mindestens einem gültigen Renditezeitraum</span>
        </div>
      </div>

      <Disclosure summary={`Hauptstatus je Aktie (Summe ${f.integer(levelSum)} = Universum ${levelSum === cov.universe_total ? '✓' : '✗'})`}>
        <ul className="link-list">
          {levelEntries.map(([code, count]) => {
            const info = statusInfo(manifest, Number(code));
            return (
              <li key={code}>
                <a href={buildHash('/aktien', { h, status: `ebene:${code}` })}>
                  {Number(code) === READY_LEVEL ? 'Schlusskurs am Stichtag vorhanden' : info.kurz ?? info.key} <span>{f.integer(count)}</span>
                </a>
              </li>
            );
          })}
        </ul>
        <p className="section-note">Ein Instrument kann zusätzlich mehrere Hinweise haben (zum Beispiel Kurs in Pence oder Split in der Historie); diese stehen in der Detailansicht und unter „Datenstand & Betrieb“.</p>
      </Disclosure>

      <section className="section" aria-labelledby="fenster">
        <SectionTitle id="fenster">Status je Zeitraum</SectionTitle>
        <WindowRuler value={h} onChange={(next) => updateParams(route, { h: next, seite: null, status: filter?.startsWith('fenster:') ? null : filter })} compact />
        {perWindow ? (
          <p className="section-note">
            {f.windowLabel(h)}: {f.integer(perWindow.return_eligible)} Aktien mit veröffentlichter Kursrendite, davon {f.integer(perWindow.trend_eligible)} gleichmäßig gestiegen und für alle Gewichtungen bewertbar.
          </p>
        ) : null}
        <ul className="link-list">
          {windowEntries.map(([code, count]) => {
            const info = statusInfo(manifest, Number(code));
            return (
              <li key={code}>
                <a href={buildHash('/aktien', { h, status: `fenster:${code}` })} title={info.text}>
                  {info.kurz ?? info.key} <span>{f.integer(count)}</span>
                </a>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="section" aria-labelledby="suche">
        <SectionTitle id="suche">Suchen</SectionTitle>
        <form
          className="search"
          role="search"
          onSubmit={(e: Event) => {
            e.preventDefault();
            updateParams(route, { q: draft.trim() || null, seite: null });
          }}
        >
          <label className="visually-hidden" htmlFor="suche-feld">
            Name, Ticker oder ISIN
          </label>
          <IconSearch />
          <input
            id="suche-feld"
            className="input"
            type="search"
            inputMode="search"
            autoComplete="off"
            placeholder="Name, Ticker oder ISIN"
            value={draft}
            onChange={(e: Event) => setDraft((e.target as HTMLInputElement).value)}
            onBlur={() => {
              if (draft.trim() !== query) updateParams(route, { q: draft.trim() || null, seite: null });
            }}
          />
        </form>
        <div className="toolbar">
          <span className="section-note">
            {f.plural(list.length, 'Treffer', 'Treffer')}
            {filterLabel ? `, Filter: ${filterLabel}` : ''}
          </span>
          {filter || query ? (
            <button
              type="button"
              className="btn btn-quiet"
              onClick={() => {
                setDraft('');
                updateParams(route, { q: null, status: null, seite: null });
              }}
            >
              Filter löschen
            </button>
          ) : null}
        </div>
        {full.error ? <ErrorNote error={full.error} /> : null}
        {!full.data && !full.error ? <Loading height={80} label="Status je Zeitraum wird geladen" /> : null}
        <ul className="rows">
          {visible.map((i) => {
            const status = statusOf(i);
            const info = statusInfo(manifest, status);
            const r = returns.get(i);
            return (
              <InstrumentRow
                key={i}
                idx={i}
                href={buildHash(`/aktie/${instruments.isin[i]}`, { h })}
                meta={<span>{[typeLabel(instruments, i), listingShort(instruments, i)].filter(Boolean).join(', ')}</span>}
                figs={r !== undefined ? <Pct value={r} strong /> : <span className="row-fig-sub">keine Rendite</span>}
              >
                <span>
                  {windowStatus ? `${f.windowLabel(h)}: ` : ''}
                  <strong>{status === READY_LEVEL ? 'Schlusskurs am Stichtag vorhanden' : info.kurz ?? info.key}</strong>
                  {info.text ? ` – ${info.text}` : ''}
                </span>
              </InstrumentRow>
            );
          })}
        </ul>
        <Pager page={current} pages={pages} onChange={(p) => updateParams(route, { seite: p })} label="Seiten der Aktienliste" />
      </section>
    </div>
  );
}
