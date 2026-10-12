import { useEffect, useMemo } from 'react';
import { WindowRuler } from '../components/controls';
import { ErrorNote, IsinCopy, Loading, Notice, Segmented, SectionTitle } from '../components/ui';
import * as f from '../lib/format';
import { useWindowFull } from '../lib/hooks';
import { instName } from '../lib/instruments';
import { buildHash, updateParams, type Route } from '../lib/router';
import { cohortFor, entryScores, memberIndex, orderFor, parsePolicy, parseWeight, parseWindow, WEIGHTS } from '../lib/scoring';
import type { Policy, WindowData } from '../lib/types';
import { useApp } from '../state/AppState';

const TOP = 10;

function parseColumns(text: string | null): number[] {
  const list = (text ?? '')
    .split(',')
    .filter((x) => /^\d{1,3}$/.test(x.trim()))
    .map((x) => Number(x))
    .filter((w) => (WEIGHTS as readonly number[]).includes(w));
  const unique = [...new Set(list)].slice(0, 11);
  return unique.length ? unique : [0, 50, 60];
}

interface RankTable {
  rank: (w: number, idx: number) => number | null;
  score: (w: number, idx: number) => number | null;
  top: (w: number, n: number) => number[];
  size: (w: number) => number;
}

function rankTable(win: WindowData, policy: Policy): RankTable {
  const positions = memberIndex(win);
  const rankMaps = new Map<number, Map<number, number>>();
  for (const w of WEIGHTS) {
    const order = orderFor(win, policy, w);
    rankMaps.set(w, new Map(order.map((idx, k) => [idx, k + 1])));
  }
  return {
    rank: (w, idx) => rankMaps.get(w)?.get(idx) ?? null,
    score: (w, idx) => {
      const member = positions.get(idx);
      if (member === undefined || rankMaps.get(w)?.get(idx) === undefined) return null;
      return entryScores(win, member, cohortFor(policy, w), w).score;
    },
    top: (w, n) => orderFor(win, policy, w).slice(0, n),
    size: (w) => orderFor(win, policy, w).length,
  };
}

function weightHead(w: number) {
  return (
    <span className="wcol-head">
      {w} %<br />
      <span className="muted">{100 - w} %</span>
    </span>
  );
}

export function WeightCompareView({ route }: { route: Route }) {
  const { manifest, instruments, prefs, setPrefs } = useApp();
  const h = parseWindow(route.params.get('h'), prefs.h);
  const policy = parsePolicy(route.params.get('p') ?? prefs.policy);
  const allColumns = route.params.get('ansicht') === 'alle';
  const columns = allColumns ? [...WEIGHTS] : parseColumns(route.params.get('spalten')).slice(0, 3);
  const a = parseWeight(route.params.get('a'), prefs.compareA);
  const b = parseWeight(route.params.get('b'), prefs.compareB);
  const full = useWindowFull(h);
  const table = useMemo(() => (full.data ? rankTable(full.data, policy) : null), [full.data, policy]);

  useEffect(() => {
    if (prefs.compareA !== a || prefs.compareB !== b) setPrefs({ compareA: a, compareB: b });
  }, [a, b]);

  if (!manifest || !instruments) return null;
  const win = full.data;

  const rows: number[] = [];
  if (table) {
    for (const w of columns) for (const idx of table.top(w, TOP)) if (!rows.includes(idx)) rows.push(idx);
    const first = columns[0];
    rows.sort((x, y) => (table.rank(first, x) ?? 1e9) - (table.rank(first, y) ?? 1e9) || x - y);
  }

  const pairRows: number[] = [];
  if (table) {
    for (const idx of [...table.top(a, TOP), ...table.top(b, TOP)]) if (!pairRows.includes(idx)) pairRows.push(idx);
    pairRows.sort((x, y) => (table.rank(a, x) ?? 1e9) - (table.rank(a, y) ?? 1e9) || x - y);
  }
  const top1A = table?.top(a, 1)[0];
  const top1B = table?.top(b, 1)[0];
  const differentFields = policy === 'native' && (a === 0) !== (b === 0);

  const toggleColumn = (w: number) => {
    let next = columns.includes(w) ? columns.filter((x) => x !== w) : [...columns, w];
    if (next.length > 3) next = next.slice(next.length - 3);
    if (!next.length) next = [w];
    updateParams(route, { spalten: next.join(',') });
  };

  return (
    <div className="view">
      <WindowRuler value={h} onChange={(next) => updateParams(route, { h: next })} />
      <Segmented
        label="Vergleichsfeld"
        options={[
          { value: 'native', label: 'Nativ' },
          { value: 'common_trend', label: 'Gleiches Feld' },
        ]}
        value={policy}
        onChange={(p) => updateParams(route, { p })}
      />
      <p className="section-note">
        {policy === 'native'
          ? 'Nativ: 0/100 bewertet alle Aktien mit Kursrendite (V), alle anderen Gewichtungen nur gleichmäßig gestiegene Aktien (U). Beim Wechsel von oder zu 0/100 ändert sich deshalb auch das Vergleichsfeld.'
          : 'Gleiches Feld: alle elf Gewichtungen bewerten dieselben gleichmäßig gestiegenen Aktien (U). Rangunterschiede entstehen hier allein durch die Gewichtung.'}
      </p>

      {full.error ? <ErrorNote error={full.error} /> : null}
      {!win && !full.error ? <Loading height={700} label="Ranglisten werden geladen" /> : null}

      {win && table ? (
        <>
          <section className="section" aria-labelledby="elf">
            <SectionTitle id="elf">Rang und Score je Gewichtung</SectionTitle>
            <Segmented
              label="Spalten"
              hideLabel
              options={[
                { value: 'auswahl', label: 'Bis zu drei Spalten' },
                { value: 'alle', label: 'Alle elf, seitlich blättern' },
              ]}
              value={allColumns ? 'alle' : 'auswahl'}
              onChange={(value) => updateParams(route, { ansicht: value === 'alle' ? 'alle' : null })}
            />
            {!allColumns ? (
              <div className="chips" role="group" aria-label="Spalten wählen (höchstens drei)">
                {WEIGHTS.map((w) => (
                  <button key={w} type="button" className={`chip${columns.includes(w) ? ' is-active' : ''}`} aria-pressed={columns.includes(w)} onClick={() => toggleColumn(w)}>
                    {w}/{100 - w}
                  </button>
                ))}
              </div>
            ) : null}
            <p className="section-note">
              Spaltenkopf: oben Anteil Gleichmäßigkeit, darunter Anteil Rendite und Zahl der verglichenen Aktien (M). Zelle: Platz und darunter Score. Zeilen: alle Aktien, die in mindestens einer gezeigten Spalte unter den ersten {TOP} liegen, sortiert nach der ersten Spalte. „–“ heißt: in dieser Gewichtung nicht im Vergleichsfeld (kein erfundener Rang).
            </p>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th className="sticky" scope="col">
                      Aktie
                    </th>
                    {columns.map((w) => (
                      <th key={w} scope="col" className="n wcol" aria-label={`${f.weightLabel(w)}, ${f.integer(table.size(w))} Aktien im Vergleichsfeld`}>
                        {weightHead(w)}
                        <br />
                        <span className="muted">M {f.integer(table.size(w))}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((idx) => (
                    <tr key={idx}>
                      <th scope="row" className="sticky">
                        <a href={buildHash(`/aktie/${instruments.isin[idx]}`, { h, w: columns[0], p: policy })}>{instName(instruments, idx)}</a>
                        <br />
                        <span className="muted">{instruments.isin[idx]}</span>
                      </th>
                      {columns.map((w) => {
                        const rank = table.rank(w, idx);
                        const score = table.score(w, idx);
                        return (
                          <td key={w} className="n wcol">
                            {rank === null ? (
                              <span className="muted" title="nicht im Vergleichsfeld dieser Gewichtung">
                                –
                              </span>
                            ) : (
                              <>
                                <span className="cell-rank">{rank}</span>
                                <br />
                                <span className="muted">{f.score(score)}</span>
                              </>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="section" aria-labelledby="paar">
            <SectionTitle id="paar">Zwei Gewichtungen direkt vergleichen</SectionTitle>
            <div className="stack">
              <label className="field">
                <span className="field-label">Variante A</span>
                <select className="select" value={a} onChange={(e: Event) => updateParams(route, { a: Number((e.target as HTMLSelectElement).value) })}>
                  {WEIGHTS.map((w) => (
                    <option key={w} value={w}>
                      {f.weightLabel(w)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="field-label">Variante B</span>
                <select className="select" value={b} onChange={(e: Event) => updateParams(route, { b: Number((e.target as HTMLSelectElement).value) })}>
                  {WEIGHTS.map((w) => (
                    <option key={w} value={w}>
                      {f.weightLabel(w)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {top1A !== undefined && top1B !== undefined ? (
              <p className="lede">
                {top1A === top1B
                  ? `Platz 1 bleibt gleich (${instName(instruments, top1A)}).`
                  : `Platz 1 wechselt: in A ${instName(instruments, top1A)}, in B ${instName(instruments, top1B)}`}
              </p>
            ) : (
              <p className="lede">Mindestens eine der beiden Varianten hat in diesem Zeitraum keine Rangliste.</p>
            )}
            {differentFields ? (
              <Notice tone="info" title="Unterschiedliche Vergleichsfelder">
                <p>
                  0/100 bewertet hier {f.plural(win.counts.V, 'Aktie', 'Aktien')} (alle mit Kursrendite), die andere Variante nur {f.plural(win.counts.U, 'gleichmäßig gestiegene Aktie', 'gleichmäßig gestiegene Aktien')}. Rangunterschiede entstehen deshalb auch durch die andere Zulassung, nicht nur durch die Gewichtung. Für eine reine Gewichtungswirkung „Gleiches Feld“ wählen.
                </p>
              </Notice>
            ) : null}
            <p className="section-note">Rangverbesserung von A nach B = Rang in A minus Rang in B. Positiv heißt: in B weiter vorne.</p>
            <ul className="rows">
              {pairRows.map((idx) => {
                const rankA = table.rank(a, idx);
                const rankB = table.rank(b, idx);
                const diff = rankA !== null && rankB !== null ? rankA - rankB : null;
                return (
                  <li key={idx} className="row row-nr">
                    <div className="row-main">
                      <a className="row-link row-name" href={buildHash(`/aktie/${instruments.isin[idx]}`, { h, w: b, p: policy })}>
                        {instName(instruments, idx)}
                      </a>
                      <div className="row-meta">
                        <IsinCopy isin={instruments.isin[idx]} compact />
                      </div>
                      <span className="row-alt">
                        A: {rankA === null ? 'kein zulässiger Rang' : `Platz ${rankA}`}. B: {rankB === null ? 'kein zulässiger Rang' : `Platz ${rankB}`}.
                      </span>
                    </div>
                    <div className="row-figs">
                      {diff === null ? (
                        <span className="row-fig-sub">kein Rangunterschied berechenbar</span>
                      ) : (
                        <>
                          <span className={`pct pct-strong ${diff > 0 ? 'diff-better' : diff < 0 ? 'diff-worse' : ''}`}>{diff > 0 ? `+${diff}` : diff < 0 ? `−${Math.abs(diff)}` : '0'}</span>
                          <span className="row-fig-sub">{diff > 0 ? `in B ${f.plural(diff, 'Platz', 'Plätze')} weiter vorne` : diff < 0 ? `in B ${f.plural(-diff, 'Platz', 'Plätze')} weiter hinten` : 'gleicher Platz'}</span>
                        </>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        </>
      ) : null}
    </div>
  );
}
