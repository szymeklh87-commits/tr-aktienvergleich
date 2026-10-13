import { WeightControl } from '../components/controls';
import { IconDownload } from '../components/icons';
import { ErrorNote, IsinCopy, Loading, Notice, Pct, Segmented } from '../components/ui';
import { downloadText, safeFilename, toCsv, type CsvValue } from '../lib/csv';
import { EMPTY_REASONS } from '../lib/codes';
import * as f from '../lib/format';
import { useOverview } from '../lib/hooks';
import { instName } from '../lib/instruments';
import { buildHash, updateParams, type Route } from '../lib/router';
import { parsePolicy, parseWeight } from '../lib/scoring';
import type { Manifest, Overview, OverviewRow } from '../lib/types';
import { useApp } from '../state/AppState';
import { PREVIEW } from '../lib/env';

function exportMeta(manifest: Manifest, filter: string): [string, string][] {
  return [
    ['Ansicht', 'Höchste Rendite 1–90 Tage'],
    ['Filter', filter],
    ['Snapshot', manifest.snapshot_id],
    ['Kursstichtag', manifest.cutoff_session_date],
    ['Berechnet (UTC)', manifest.computed_at_utc],
    ['Datenmodus', manifest.data_mode === 'demo' ? 'DEMO – synthetische Testdaten' : manifest.data_mode],
    ['Methode', manifest.versions.method ?? ''],
    ['Kursquelle', manifest.provider.prices],
    ['Basis', manifest.currency_basis],
  ];
}

function FieldRange({ counts }: { counts: number[] }) {
  const filled = counts.filter((n) => n > 0);
  if (!filled.length) return <p className="section-note">In keinem Zeitraum gibt es vergleichbare Aktien.</p>;
  const lo = Math.min(...filled);
  const hi = Math.max(...filled);
  return (
    <p className="section-note">
      Verglichen werden je Zeitraum {lo === hi ? f.integer(lo) : `${f.integer(lo)} bis ${f.integer(hi)}`} Aktien
      {filled.length < counts.length ? `; ${counts.length - filled.length} Zeiträume ohne vergleichbare Aktie` : ''}.
    </p>
  );
}

export function ReturnLadderView({ route }: { route: Route }) {
  const { manifest, instruments, isDemo } = useApp();
  const overview = useOverview();
  const mode = route.params.get('modus') === 'gewichtung' ? 'gewichtung' : 'rendite';
  const weight = parseWeight(route.params.get('w'), 60);
  const policy = parsePolicy(route.params.get('p'));
  if (!manifest || !instruments) return null;
  const ov = overview.data;

  const exportCsv = (data: Overview) => {
    const name = (idx: number) => instName(instruments, idx);
    if (mode === 'rendite') {
      const rows: CsvValue[][] = [];
      for (const row of data.winners) {
        if (!row.entries.length) {
          rows.push([row.h, '', '', null, '', '', 'nein', row.M, EMPTY_REASONS[row.empty ?? ''] ?? row.empty ?? '']);
          continue;
        }
        row.entries.forEach((e, k) =>
          rows.push([
            row.h,
            name(e.idx),
            instruments.isin[e.idx],
            100 * e.r,
            f.day(e.start),
            f.day(e.end),
            row.tie ? 'ja' : 'nein',
            row.M,
            k > 0 ? 'gleichplatziert' : row.all_negative ? 'nur Verluste: geringster Verlust' : '',
          ]),
        );
      }
      const csv = toCsv(exportMeta(manifest, 'reine Kursrendite (native 0/100, Menge V)'), ['Tage', 'Unternehmen', 'ISIN', 'Höchste Kursrendite %', 'Beginn', 'Ende', 'Gleichstand', 'Vergleichsfeld M', 'Hinweis'], rows, [undefined, undefined, undefined, 6]);
      downloadText(safeFilename(`hoechste-rendite-1-90_${manifest.snapshot_id}.csv`), csv);
      return;
    }
    const list = policy === 'native' && weight === 0 ? data.v0 : data.u[String(weight)];
    const rows: CsvValue[][] = list.map((row) =>
      row.idx === undefined
        ? [row.h, '', '', null, null, null, '', '', row.M, EMPTY_REASONS[row.empty ?? ''] ?? row.empty ?? '']
        : [row.h, name(row.idx), instruments.isin[row.idx], 100 * (row.r ?? NaN), row.r2 ?? null, row.score ?? null, f.day(row.start ?? null), f.day(data.cutoff_day), row.M, row.tie ? 'Gleichstand' : row.sole ? 'Einziger qualifizierter Titel' : ''],
    );
    const csv = toCsv(
      exportMeta(manifest, `${f.weightLabel(weight)}; Vergleichsfeld ${policy === 'native' ? 'nativ' : 'gleiches Feld (U)'}`),
      ['Tage', 'Unternehmen', 'ISIN', 'Kursrendite %', 'R²', 'Score', 'Beginn', 'Ende', 'Vergleichsfeld M', 'Hinweis'],
      rows,
      [undefined, undefined, undefined, 6, 6, 4],
    );
    downloadText(safeFilename(`spitzenreiter-1-90_w${weight}_${policy}_${manifest.snapshot_id}.csv`), csv);
  };

  const weightedRows: OverviewRow[] = ov ? (policy === 'native' && weight === 0 ? ov.v0 : ov.u[String(weight)] ?? []) : [];

  return (
    <div className="view">
      <header className="view-head">
        <p className="lede">
          {mode === 'rendite'
            ? 'Je Zeitraum die Aktie mit der höchsten reinen Kursrendite. Gleichmäßigkeit spielt hier keine Rolle; auch ein schwankender Verlauf kann vorne liegen.'
            : 'Je Zeitraum der Spitzenreiter der gewählten Gewichtung.'}
        </p>
        <p className="section-note">
          Kursstand {f.day(manifest.cutoff_day)}. Kursrendite in der jeweiligen Notierungswährung, splitbereinigt, ohne Dividenden, Gebühren, Steuern und Wechselkurseffekt. Quelle: {manifest.provider.prices}
          {isDemo ? ' (synthetische DEMO-Daten)' : ''}. Tatsächlicher Beginn und Ende stehen in jeder Zeile.
        </p>
      </header>

      <Segmented
        label="Liste"
        hideLabel
        options={[
          { value: 'rendite', label: 'Reine Rendite' },
          { value: 'gewichtung', label: 'Andere Gewichtung' },
        ]}
        value={mode}
        onChange={(value) => updateParams(route, { modus: value === 'rendite' ? null : value })}
      />

      {mode === 'gewichtung' ? (
        <WeightControl weight={weight} onWeight={(w) => updateParams(route, { w })} policy={policy} onPolicy={(p) => updateParams(route, { p })} />
      ) : null}

      {!PREVIEW ? (
        <div className="toolbar toolbar-end no-print">
          <button type="button" className="btn btn-quiet" disabled={!ov} onClick={() => ov && exportCsv(ov)}>
            <IconDownload /> CSV
          </button>
        </div>
      ) : null}

      {ov ? <FieldRange counts={mode === 'rendite' || (policy === 'native' && weight === 0) ? ov.counts.V : ov.counts.U} /> : null}
      {overview.error ? <ErrorNote error={overview.error} /> : null}
      {!ov && !overview.error ? <Loading height={600} label="90 Zeiträume werden geladen" /> : null}

      {ov && mode === 'rendite' ? (
        <ol className="rows rank-ladder" aria-label="Höchste Kursrendite je Zeitraum, 90 Zeilen">
          {ov.winners.map((row) => {
            const first = row.entries[0];
            const rankingHref = buildHash('/ranking', { h: row.h, w: 0, p: 'native', chart: 1 });
            if (!first) {
              return (
                <li key={row.h} className="row row-empty">
                  <div className="row-rank">
                    {row.h}
                    <small>{row.h === 1 ? 'Tag' : 'Tage'}</small>
                  </div>
                  <div className="row-main">
                    <a className="row-link row-name" href={rankingHref}>
                      Keine vergleichbare Aktie
                    </a>
                    <span className="row-alt">{EMPTY_REASONS[row.empty ?? ''] ?? 'Für diesen Zeitraum gibt es keine veröffentlichte Rendite.'}</span>
                  </div>
                  <div className="row-figs">
                    <span className="pct pct-fehlt">–</span>
                  </div>
                </li>
              );
            }
            const isin = instruments.isin[first.idx];
            return (
              <li key={row.h} className={`row${row.tie ? ' row-tie' : ''}`}>
                <div className="row-rank">
                  {row.h}
                  <small>{row.h === 1 ? 'Tag' : 'Tage'}</small>
                </div>
                <div className="row-main">
                  <a className="row-link row-name" href={rankingHref} aria-label={`${f.windowLabel(row.h)}: ${instName(instruments, first.idx)}, ${f.pct(first.r)}. Renditeliste öffnen`}>
                    {instName(instruments, first.idx)}
                  </a>
                  <div className="row-meta">
                    <IsinCopy isin={isin} compact />
                    <a href={buildHash(`/aktie/${isin}`, { h: row.h, w: 0, p: 'native' })}>Kurschart</a>
                  </div>
                  <span className="row-alt">{f.dayRange(first.start, first.end)}</span>
                  {row.all_negative ? <span className="row-alt">Alle Renditen negativ: angezeigt wird der geringste Verlust.</span> : null}
                  {row.tie ? (
                    <div className="row-extra">
                      <span>
                        <span className="badge">Gleichstand</span> Exakt gleiche Rendite wie {row.entries.length - 1 === 1 ? 'eine weitere Aktie' : `${row.entries.length - 1} weitere Aktien`}:
                      </span>
                      {row.entries.slice(1).map((e) => (
                        <a key={e.idx} href={buildHash(`/aktie/${instruments.isin[e.idx]}`, { h: row.h, w: 0, p: 'native' })}>
                          {instName(instruments, e.idx)} ({instruments.isin[e.idx]})
                        </a>
                      ))}
                    </div>
                  ) : null}
                </div>
                <div className="row-figs">
                  <Pct value={first.r} strong />
                </div>
              </li>
            );
          })}
        </ol>
      ) : null}

      {ov && mode === 'gewichtung' ? (
        <>
          {policy === 'native' && weight > 0 ? (
            <p className="section-note">Für Gewichtungen mit Gleichmäßigkeitsanteil zählen nur gleichmäßig gestiegene Aktien (mindestens 15 Tageskurse, positive Rendite und Steigung). In kurzen Zeiträumen bleibt die Zeile deshalb oft leer.</p>
          ) : null}
          {policy === 'common_trend' && weight === 0 ? (
            <Notice tone="info" title="Eingeschränkte reine Rendite">
              <p>Im gleichen Vergleichsfeld nutzt auch 0/100 nur gleichmäßig gestiegene Aktien. Die uneingeschränkte Renditeliste steht unter „Reine Rendite“.</p>
            </Notice>
          ) : null}
          <ol className="rows rank-ladder" aria-label={`Spitzenreiter je Zeitraum, ${f.weightLabel(weight)}`}>
            {weightedRows.map((row) => {
              const rankingHref = buildHash('/ranking', { h: row.h, w: weight, p: policy, chart: 1 });
              if (row.idx === undefined) {
                return (
                  <li key={row.h} className="row row-empty">
                    <div className="row-rank">
                      {row.h}
                      <small>{row.h === 1 ? 'Tag' : 'Tage'}</small>
                    </div>
                    <div className="row-main">
                      <a className="row-link row-name" href={rankingHref}>
                        Keine Rangliste
                      </a>
                      <span className="row-alt">{EMPTY_REASONS[row.empty ?? ''] ?? 'Für diesen Zeitraum gibt es keine veröffentlichte Rangliste.'}</span>
                    </div>
                    <div className="row-figs">
                      <span className="pct pct-fehlt">–</span>
                    </div>
                  </li>
                );
              }
              const isin = instruments.isin[row.idx];
              return (
                <li key={row.h} className={`row${row.tie ? ' row-tie' : ''}`}>
                  <div className="row-rank">
                    {row.h}
                    <small>{row.h === 1 ? 'Tag' : 'Tage'}</small>
                  </div>
                  <div className="row-main">
                    <a className="row-link row-name" href={rankingHref}>
                      {instName(instruments, row.idx)}
                    </a>
                    <div className="row-meta">
                      <IsinCopy isin={isin} compact />
                      <a href={buildHash(`/aktie/${isin}`, { h: row.h, w: weight, p: policy })}>Kurschart</a>
                    </div>
                    <span className="row-alt">{f.dayRange(row.start ?? null, ov.cutoff_day)}</span>
                    {row.sole ? <span className="row-alt">Einziger qualifizierter Titel – keine relative Konkurrenzbewertung.</span> : null}
                    {row.tie ? <span className="row-alt">Gleichstand mit dem nächsten Platz (gleicher Score).</span> : null}
                  </div>
                  <div className="row-figs">
                    <Pct value={row.r} strong />
                    {row.r2 !== null && row.r2 !== undefined ? <span className="row-fig-sub">R² {f.r2(row.r2)}</span> : null}
                    <span className="row-fig-sub">Score {f.score(row.score)}</span>
                  </div>
                </li>
              );
            })}
          </ol>
        </>
      ) : null}
    </div>
  );
}
