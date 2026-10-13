import { useEffect } from 'react';
import { CompareBlock } from '../components/compare';
import { WeightControl, WindowRuler } from '../components/controls';
import { IconDownload, IconGrid } from '../components/icons';
import { InstrumentRow } from '../components/rows';
import { Disclosure, ErrorNote, Loading, Notice, Pager, Pct, Segmented } from '../components/ui';
import { EMPTY_REASONS } from '../lib/codes';
import { downloadText, safeFilename, toCsv, type CsvValue } from '../lib/csv';
import * as f from '../lib/format';
import { useOverview, useWindowFull, useWindowHead } from '../lib/hooks';
import { instName } from '../lib/instruments';
import { buildHash, navigate, updateParams, type Route } from '../lib/router';
import { overviewRow } from '../lib/groups';
import { cohortFor, cohortSize, hasGroupB, parseGroup, parsePolicy, parseWeight, parseWindow, rankedEntries } from '../lib/scoring';
import type { Group, Policy, WindowData } from '../lib/types';
import { useApp } from '../state/AppState';
import { PREVIEW } from '../lib/env';

const PAGE = 50;

/** Beschreibt die Vergleichsmenge der gewählten Rangliste in Alltagssprache. */
export function CohortNote({ win, policy, weight, universe, group = 'a' }: { win: WindowData; policy: Policy; weight: number; universe: number; group?: Group }) {
  const cohort = cohortFor(policy, weight);
  const v = win.counts.V;
  const u = win.counts.U;
  if (group === 'b') {
    const vl = win.counts.L ?? 0;
    const ul = win.counts.UL ?? 0;
    return (
      <div className="section-note">
        <p>
          Gruppe B: nur Aktien mit Ø Tagesumsatz ab 10 Mio. USD (20 Sitzungen) – {f.integer(vl)} von {f.integer(v)} vergleichbaren Aktien für {f.windowLabel(win.h)}.
        </p>
        {cohort === 'v0' ? (
          <p>Diese Liste ist nur nach Kursrendite sortiert; Reihenfolge und Renditen wie in Gruppe A, ohne die übrigen Aktien.</p>
        ) : (
          <p>
            Bewertet werden {f.plural(ul, 'gleichmäßig gestiegene Aktie', 'gleichmäßig gestiegene Aktien')} dieser Gruppe. Perzentile und Score beziehen sich nur auf die Gruppe B; die Scores sind deshalb nicht
            mit Gruppe A vergleichbar.
          </p>
        )}
      </div>
    );
  }
  return (
    <div className="section-note">
      <p>
        Teiluniversum: {f.integer(v)} von {f.integer(universe)} gelisteten Instrumenten für {f.windowLabel(win.h)} vergleichbar (veröffentlichte Kursrendite).
      </p>
      {cohort === 'v0' ? (
        <p>Diese Liste umfasst alle {f.integer(v)} und ist nur nach Kursrendite sortiert.</p>
      ) : (
        <p>
          Bewertet werden {f.plural(u, 'gleichmäßig gestiegene Aktie', 'gleichmäßig gestiegene Aktien')} (mindestens 15 echte Tageskurse, positive Rendite und positive Trendsteigung).
          {policy === 'common_trend' ? ' Gleiches Vergleichsfeld: alle elf Gewichtungen nutzen dieselben Aktien.' : ''}
          {policy === 'common_trend' && weight === 0 ? ' Dadurch ist auch 0/100 hier eingeschränkt.' : ''}
        </p>
      )}
    </div>
  );
}

export function RankingView({ route }: { route: Route }) {
  const { manifest, instruments, prefs, setPrefs, isDemo } = useApp();
  const h = parseWindow(route.params.get('h'), prefs.h);
  const weight = parseWeight(route.params.get('w'), prefs.w);
  const policy = parsePolicy(route.params.get('p') ?? prefs.policy);
  const limitParam = route.params.get('n');
  const limit: '10' | '50' | 'alle' = limitParam === '50' || limitParam === 'alle' ? limitParam : '10';
  const page = Math.max(1, Number(route.params.get('seite') ?? 1) || 1);
  const showChart = route.params.get('chart') === '1';
  const requestedGroup = parseGroup(route.params.get('g'));

  const head = useWindowHead(h);
  const full = useWindowFull(h, limit === 'alle');
  const overview = useOverview();

  useEffect(() => {
    if (prefs.h !== h || prefs.w !== weight || prefs.policy !== policy) setPrefs({ h, w: weight, policy });
  }, [h, weight, policy]);

  if (!manifest || !instruments) return null;
  const groupsAvailable = head.data ? hasGroupB(head.data) : false;
  const group: Group = requestedGroup === 'b' && groupsAvailable ? 'b' : 'a';
  const win = limit === 'alle' ? full.data : head.data;
  const size = head.data ? cohortSize(head.data, policy, weight, group) : 0;
  const pages = limit === 'alle' ? Math.max(1, Math.ceil(size / PAGE)) : 1;
  const currentPage = Math.min(page, pages);
  const offset = limit === 'alle' ? (currentPage - 1) * PAGE : 0;
  const count = limit === 'alle' ? PAGE : Number(limit);
  const entries = win ? rankedEntries(win, policy, weight, offset, count, group) : [];
  const cohort = cohortFor(policy, weight, group);
  const emptyRow = overview.data
    ? cohort === 'v0' || cohort === 'v0l'
      ? overviewRow(overview.data, group, 0, h)
      : (group === 'b' ? overview.data.ul?.[String(weight)] : overview.data.u[String(weight)])?.[h - 1]
    : undefined;
  const loadError = head.error ?? (limit === 'alle' ? full.error : null);

  const setWindow = (next: number) => updateParams(route, { h: next, seite: null });

  const exportCsv = () => {
    const source = limit === 'alle' ? full.data : head.data;
    if (!source) return;
    const all = rankedEntries(source, policy, weight, 0, limit === 'alle' ? size : Number(limit), group);
    const start = new Map(source.m.idx.map((idx, pos) => [idx, source.m.start[pos]]));
    const rows: CsvValue[][] = all.map((e) => [
      e.rank,
      instName(instruments, e.idx),
      instruments.isin[e.idx],
      100 * e.r,
      e.r2,
      e.score,
      e.g,
      e.rPct,
      f.day(start.get(e.idx) ?? null),
      f.day(source.cutoff_day),
      e.tie ? 'Gleichstand' : '',
    ]);
    const csv = toCsv(
      [
        ['Ansicht', 'Ranking nach Gewichtung'],
        ['Zeitraum', f.windowLabel(h)],
        ['Gewichtung', f.weightLabel(weight)],
        ['Aktiengruppe', group === 'b' ? 'B: Ø Tagesumsatz ≥ 10 Mio. USD (eigene Perzentile)' : 'A: alle vergleichbaren Aktien'],
        ['Vergleichsfeld', policy === 'native' ? 'nativ (0/100 auf V, sonst U)' : 'gleiches Feld (alle auf U)'],
        ['Vergleichsfeld M', String(size)],
        ['Snapshot', manifest.snapshot_id],
        ['Kursstichtag', manifest.cutoff_session_date],
        ['Datenmodus', manifest.data_mode === 'demo' ? 'DEMO – synthetische Testdaten' : manifest.data_mode],
        ['Methode', manifest.versions.method ?? ''],
      ],
      ['Rang', 'Unternehmen', 'ISIN', 'Kursrendite %', 'R²', 'Score', 'Gleichmäßigkeit-Perzentil', 'Rendite-Perzentil', 'Beginn', 'Ende', 'Hinweis'],
      rows,
      [undefined, undefined, undefined, 6, 6, 4, 4, 4],
    );
    downloadText(safeFilename(`ranking_${h}T_w${weight}_${policy}${group === 'b' ? '_gruppeB' : ''}_${manifest.snapshot_id}.csv`), csv);
  };

  return (
    <div className="view">
      <WindowRuler value={h} onChange={setWindow}>
        {head.data ? (
          <p>
            Rückblick ab <strong>{f.dayWithWeekday(head.data.target_start_day)}</strong> bis Kursstand <strong>{f.dayWithWeekday(head.data.cutoff_day)}</strong>. Startkurs ist der letzte Börsenschluss am oder vor dem Ziel-Startdatum.
          </p>
        ) : null}
      </WindowRuler>
      <WeightControl weight={weight} onWeight={(w) => updateParams(route, { w, seite: null })} policy={policy} onPolicy={(p) => updateParams(route, { p, seite: null })} />
      {groupsAvailable ? (
        <Segmented
          label="Aktiengruppe"
          options={[
            { value: 'a', label: 'A: alle Aktien' },
            { value: 'b', label: 'B: Ø Umsatz ≥ 10 Mio. USD' },
          ]}
          value={group}
          onChange={(g) => updateParams(route, { g: g === 'b' ? 'b' : null, seite: null })}
        />
      ) : null}

      {loadError ? <ErrorNote error={loadError} /> : null}
      {head.data ? <CohortNote win={head.data} policy={policy} weight={weight} universe={manifest.coverage.universe_total} group={group} /> : null}

      {head.data && size === 1 ? (
        <Notice tone="info" title="Einziger qualifizierter Titel – keine relative Konkurrenzbewertung">
          <p>Score 100 bedeutet hier nur, dass keine andere Aktie die Bedingungen erfüllt.</p>
        </Notice>
      ) : null}
      {head.data && size > 1 && size < 10 ? (
        <Notice tone="info" title="Kleines Vergleichsfeld">
          <p>Nur {f.plural(size, 'Aktie erfüllt', 'Aktien erfüllen')} die Bedingungen. Ein Platz unter den ersten zehn ist hier keine Platzierung gegenüber dem gesamten TR-Angebot.</p>
        </Notice>
      ) : null}

      {head.data && size === 0 ? (
        <Notice tone="info" title="Keine Rangliste für diese Auswahl">
          <p>{EMPTY_REASONS[emptyRow?.empty ?? ''] ?? EMPTY_REASONS.keine_vergleichbare_aktie}</p>
          {cohortFor(policy, weight) === 'u' && head.data.counts.V > 0 ? (
            <div className="notice-actions">
              <a className="btn btn-primary" href={buildHash('/ranking', { h, w: 0, p: 'native', g: group === 'b' ? 'b' : null })}>
                Reine Renditeliste (0/100) zeigen
              </a>
            </div>
          ) : null}
        </Notice>
      ) : null}

      {size > 0 ? (
        <>
          <div className="toolbar no-print">
            <Segmented
              label="Umfang"
              hideLabel
              options={[
                { value: '10', label: 'Top 10' },
                { value: '50', label: 'Top 50' },
                { value: 'alle', label: `Alle ${f.integer(size)}` },
              ]}
              value={limit}
              onChange={(value) => updateParams(route, { n: value === '10' ? null : value, seite: null })}
            />
          </div>
          {!win && !loadError ? <Loading height={limit === '10' ? 760 : 1400} label="Rangliste wird geladen" /> : null}
          {win ? (
            <ol className="rows" aria-label={`Rangliste ${f.windowLabel(h)}, ${f.weightLabel(weight)}${group === 'b' ? ', Gruppe B' : ''}`} start={offset + 1}>
              {entries.map((entry) => (
                <InstrumentRow
                  key={entry.idx}
                  idx={entry.idx}
                  rank={entry.rank}
                  tie={entry.tie}
                  href={buildHash(`/aktie/${instruments.isin[entry.idx]}`, { h, w: weight, p: policy })}
                  meta={entry.tie ? <span className="badge">gleichauf</span> : null}
                  figs={
                    <>
                      <Pct value={entry.r} strong />
                      {entry.r2 !== null ? <span className="row-fig-sub">R² {f.r2(entry.r2)}</span> : null}
                      <span className="row-fig-sub">Score {f.score(entry.score)}</span>
                    </>
                  }
                />
              ))}
            </ol>
          ) : null}
          {limit === 'alle' ? <Pager page={currentPage} pages={pages} onChange={(p) => updateParams(route, { seite: p })} label="Seiten der Rangliste" /> : null}
          {limit !== 'alle' && size > Number(limit) ? (
            <p className="section-note">
              Gezeigt: Platz 1 bis {f.integer(Math.min(size, Number(limit)))} von {f.integer(size)}.
            </p>
          ) : null}

          <div className="toolbar no-print">
            <button type="button" className="btn" onClick={() => navigate('/raster', { quelle: 'ranking', n: limit === '10' ? 10 : 50, h, w: weight, p: policy, g: group === 'b' ? 'b' : null })}>
              <IconGrid /> Im Chart-Raster öffnen
            </button>
            {!PREVIEW ? (
              <button type="button" className="btn btn-quiet" onClick={exportCsv} disabled={limit === 'alle' ? !full.data : !head.data}>
                <IconDownload /> CSV
              </button>
            ) : null}
          </div>

          {head.data ? (
            <Disclosure summary="Kursverlauf der ersten fünf, gemeinsam indexiert" defaultOpen={showChart}>
              <CompareBlock
                isins={rankedEntries(head.data, policy, weight, 0, 5, group).map((e) => instruments.isin[e.idx])}
                h={h}
                cutoffDay={head.data.cutoff_day}
                rankingReturns={new Map(rankedEntries(head.data, policy, weight, 0, 5, group).map((e) => [instruments.isin[e.idx], e.r]))}
              />
            </Disclosure>
          ) : null}
        </>
      ) : null}

      {isDemo ? <p className="section-note">DEMO: synthetische Testdaten, keine echten Unternehmen.</p> : null}
    </div>
  );
}
