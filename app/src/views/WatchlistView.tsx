import { useMemo, useState } from 'react';
import { WeightControl, WindowRuler } from '../components/controls';
import { IconGrid } from '../components/icons';
import { InstrumentRow } from '../components/rows';
import { EmptyState, ErrorNote, Loading, Notice, Pct, ReturnBasis, Segmented } from '../components/ui';
import { Explain } from '../components/explain';
import { statusInfo } from '../lib/codes';
import * as f from '../lib/format';
import { useWindowFull } from '../lib/hooks';
import { downloadText, safeFilename, toCsv } from '../lib/csv';
import { PREVIEW } from '../lib/env';
import { idxList, instName, parseIsinImport } from '../lib/instruments';
import type { Instruments, Manifest } from '../lib/types';
import { buildHash, navigate, updateParams, type Route } from '../lib/router';
import { cohortFor, cohortSize, decodeStatus, entryScores, memberIndex, orderFor, parsePolicy, parseWeight, parseWindow } from '../lib/scoring';
import { rankSubgroup } from '../lib/subgroup';
import { useApp } from '../state/AppState';

export function WatchlistView({ route }: { route: Route }) {
  const { manifest, instruments, isinIndex, watchlist, prefs } = useApp();
  const h = parseWindow(route.params.get('h'), prefs.h);
  const weight = parseWeight(route.params.get('w'), prefs.w);
  const policy = parsePolicy(route.params.get('p') ?? prefs.policy);
  const subgroup = route.params.get('rang') === 'gruppe';
  const full = useWindowFull(h, watchlist.length > 0);
  const members = useMemo(() => idxList(isinIndex, watchlist), [isinIndex, watchlist]);
  const unknown = watchlist.filter((isin) => !isinIndex.has(isin));
  // Rückmeldung des ISIN-Imports hier gehalten: Nach dem ersten Import wechselt die Ansicht vom leeren
  // Zustand zur Liste, die Meldung soll dabei sichtbar bleiben.
  const [importMessage, setImportMessage] = useState<string | null>(null);

  const view = useMemo(() => {
    const win = full.data;
    if (!win) return null;
    const positions = memberIndex(win);
    const order = orderFor(win, policy, weight);
    const globalRank = new Map(order.map((idx, k) => [idx, k + 1]));
    const statuses = win.status_b64 ? decodeStatus(win.status_b64) : null;
    const group = rankSubgroup(win, members, policy, weight, 'Watchlist');
    return { win, positions, globalRank, statuses, group };
  }, [full.data, members, policy, weight]);

  if (!manifest || !instruments) return null;

  const header = (
    <>
    <header className="view-head">
      <Explain
        kinds={['rueckblick', 'rang']}
        term="watchlist"
        sees={<>Deine gemerkten Aktien mit ihrem Platz in der gesamten Rangliste des gewählten Zeitraums und der Gewichtung. Die Watchlist liegt nur auf diesem Gerät und ist nicht mit Trade Republic verbunden.</>}
        todo={<>Merken: bei einer Aktie auf den Stern ☆ tippen. Zeitraum und Gewichtung oben ändern die Plätze aller gemerkten Aktien.</>}
      />
    </header>
    <ReturnBasis />
    </>
  );

  if (!watchlist.length) {
    return (
      <div className="view">
        {header}
        <EmptyState title="Noch keine Aktien gemerkt" action={<a className="btn btn-primary" href="#/ranking">Zur Rangliste</a>}>
          <p>Tippe in einer Liste oder in der Detailansicht auf den Stern, um eine Aktie hier zu sammeln – oder füge unten ISINs ein. Unter „Einstellungen“ lässt sich die Watchlist sichern und auf ein anderes Gerät übertragen.</p>
        </EmptyState>
        <IsinTransfer manifest={manifest} instruments={instruments} message={importMessage} onMessage={setImportMessage} />
      </div>
    );
  }

  const rows = view
    ? subgroup
      ? [...view.group.entries.map((e) => e.idx), ...members.filter((idx) => !view.group.entries.some((e) => e.idx === idx))]
      : [...members].sort((a, b) => (view.globalRank.get(a) ?? 1e9) - (view.globalRank.get(b) ?? 1e9) || a - b)
    : members;

  return (
    <div className="view">
      {header}
      <WindowRuler value={h} onChange={(next) => updateParams(route, { h: next })} compact />
      <WeightControl weight={weight} onWeight={(w) => updateParams(route, { w })} policy={policy} onPolicy={(p) => updateParams(route, { p })} />
      <Segmented
        label="Rangfolge"
        options={[
          { value: 'global', label: 'Platz in der Gesamtliste' },
          { value: 'gruppe', label: 'Nur innerhalb der Watchlist' },
        ]}
        value={subgroup ? 'gruppe' : 'global'}
        onChange={(value) => updateParams(route, { rang: value === 'gruppe' ? value : null })}
      />
      {subgroup && view ? (
        <Notice tone="info" title={`${view.group.label} (${f.plural(view.group.size, 'Aktie', 'Aktien')} im Vergleichsfeld)`}>
          <p>Ränge und Scores sind hier nur innerhalb deiner Watchlist neu berechnet. Das ist keine Bewertung gegenüber dem gesamten TR-Angebot.</p>
        </Notice>
      ) : null}
      {unknown.length ? <p className="section-note">Nicht in diesem Datenstand: {unknown.join(', ')}.</p> : null}
      {full.error ? <ErrorNote error={full.error} /> : null}
      {!view && !full.error ? <Loading height={Math.min(800, 90 * members.length + 40)} label="Ränge werden geladen" /> : null}
      {view ? (
        <ul className="rows">
          {rows.map((idx) => {
            const pos = view.positions.get(idx);
            const cohort = cohortFor(policy, weight);
            const globalRank = view.globalRank.get(idx) ?? null;
            const groupEntry = view.group.entries.find((e) => e.idx === idx);
            const status = view.statuses ? view.statuses[idx] : null;
            let score: number | null = null;
            if (pos !== undefined && globalRank !== null) score = entryScores(view.win, pos, cohort, weight).score;
            const shownRank = subgroup ? groupEntry?.rank ?? null : globalRank;
            return (
              <InstrumentRow
                key={idx}
                idx={idx}
                rank={shownRank ?? '–'}
                rankNote={shownRank !== null ? (subgroup ? `von ${view.group.size}` : `von ${f.integer(cohortSize(view.win, policy, weight))}`) : undefined}
                href={buildHash(`/aktie/${instruments.isin[idx]}`, { h, w: weight, p: policy })}
                figs={
                  pos !== undefined ? (
                    <>
                      <Pct value={view.win.m.r[pos]} strong />
                      {subgroup && groupEntry ? <span className="row-fig-sub">Rangscore in der Gruppe {f.score(groupEntry.score)}</span> : null}
                      {!subgroup && score !== null ? <span className="row-fig-sub">Rangscore {f.score(score)}</span> : null}
                    </>
                  ) : (
                    <span className="row-fig-sub">keine Rendite</span>
                  )
                }
              >
                {shownRank === null ? <span>Kein Rang in dieser Gewichtung: {status !== null ? statusInfo(manifest, status).kurz : 'keine Daten'}.</span> : null}
                {subgroup && globalRank !== null ? <span>In der Gesamtliste Platz {globalRank}.</span> : null}
              </InstrumentRow>
            );
          })}
        </ul>
      ) : null}
      <div className="toolbar">
        <button type="button" className="btn" onClick={() => navigate('/raster', { quelle: 'watchlist', h })}>
          <IconGrid /> Im Chart-Raster öffnen
        </button>
        <a className="btn btn-quiet" href="#/einstellungen">
          Sichern und übertragen
        </a>
      </div>
      <IsinTransfer manifest={manifest} instruments={instruments} message={importMessage} onMessage={setImportMessage} />
    </div>
  );
}

/** ISINs importieren (zusammenführen, Prüfziffer prüfen) und als Liste exportieren. */
function IsinTransfer({
  manifest,
  instruments,
  message,
  onMessage: setMessage,
}: {
  manifest: Manifest;
  instruments: Instruments;
  message: string | null;
  onMessage: (text: string | null) => void;
}) {
  const { watchlist, setWatchlist, isinIndex } = useApp();
  const [text, setText] = useState('');
  const apply = () => {
    const parsed = parseIsinImport(text);
    const fresh = parsed.valid.filter((isin) => !watchlist.includes(isin));
    const known = parsed.valid.length - fresh.length;
    setWatchlist([...watchlist, ...fresh]);
    const notInSnapshot = fresh.filter((isin) => !isinIndex.has(isin));
    const parts = [`${f.plural(fresh.length, 'ISIN', 'ISINs')} übernommen`];
    if (known) parts.push(`${known} schon gemerkt`);
    if (parsed.duplicates) parts.push(`${parsed.duplicates} doppelt eingegeben und zusammengeführt`);
    if (parsed.invalid.length) parts.push(`ungültig (keine ISIN oder falsche Prüfziffer): ${parsed.invalid.slice(0, 5).join(', ')}${parsed.invalid.length > 5 ? ' …' : ''}`);
    if (notInSnapshot.length) parts.push(`nicht in diesem Datenstand: ${notInSnapshot.join(', ')}`);
    setMessage(parts.join('; ') + '.');
    if (fresh.length || known) setText('');
  };
  const exportList = (format: 'txt' | 'csv') => {
    const day = manifest.cutoff_session_date;
    if (format === 'txt') {
      downloadText(safeFilename(`watchlist_isin_${day}.txt`), watchlist.join('\n') + '\n', 'text/plain;charset=utf-8');
      return;
    }
    const rows = watchlist.map((isin) => {
      const idx = isinIndex.get(isin);
      return [isin, idx !== undefined ? instName(instruments, idx) : '', idx !== undefined ? instruments.identity[idx] : 'nicht in diesem Datenstand'];
    });
    downloadText(safeFilename(`watchlist_${day}.csv`), toCsv([['Ansicht', 'Watchlist (nur dieses Gerät, kein Depotbestand)'], ['Kursstichtag', day]], ['ISIN', 'Name', 'Prüfstatus Identität'], rows));
  };
  return (
    <section className="section" aria-labelledby="isin-transfer">
      <h2 className="section-title" id="isin-transfer">
        ISINs importieren und exportieren
      </h2>
      <label className="field">
        <span className="field-label">ISINs einfügen – eine je Zeile oder durch Komma getrennt</span>
        <textarea className="input isin-input" rows={3} value={text} spellCheck={false} onChange={(e: Event) => setText((e.target as HTMLTextAreaElement).value)} placeholder="DE0007164600, US0378331005" />
      </label>
      <p className="section-note">Gezählt wird nur die ISIN (mit Prüfziffer). Namen oder Ticker werden nie einer Aktie zugeordnet; doppelte ISINs werden zusammengeführt.</p>
      <div className="toolbar">
        <button type="button" className="btn btn-primary" onClick={apply} disabled={!text.trim()}>
          In die Watchlist übernehmen
        </button>
        {!PREVIEW && watchlist.length ? (
          <>
            <button type="button" className="btn btn-quiet" onClick={() => exportList('txt')}>
              ISIN-Liste exportieren
            </button>
            <button type="button" className="btn btn-quiet" onClick={() => exportList('csv')}>
              Mit Namen als CSV
            </button>
          </>
        ) : null}
      </div>
      {message ? (
        <p className="section-note" role="status">
          {message}
        </p>
      ) : null}
    </section>
  );
}
