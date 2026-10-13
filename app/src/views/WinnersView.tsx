/* Sieger nach Zeitraum: die zehn festen Zeiträume 7, 14, 21, 30, 40, 50, 60, 70, 80 und 90 Tage
 * parallel, Gruppe A und Gruppe B nebeneinander, für eine wählbare Gewichtung (ab 1.5).
 *
 * Bei 0/100 steht der tatsächliche Renditesieger, sonst der Sieger nach Rangscore mit seiner
 * tatsächlichen Kursrendite in genau diesem Fenster. Alle Werte kommen unverändert aus der
 * Übersicht des Snapshots (dieselben Ranglisten wie in der vollständigen Liste); hier wird nur
 * angeordnet und gezählt.
 */

import { useMemo } from 'react';
import { ErrorNote, IsinCopy, KeyValues, Loading, Notice, Pct, SectionTitle } from '../components/ui';
import { EMPTY_REASONS } from '../lib/codes';
import * as f from '../lib/format';
import { hasGroups, markerSlots, tenWindowCounts, tenWindowRows, type Marker, type TenWindowRow } from '../lib/groups';
import { useOverview } from '../lib/hooks';
import { instName } from '../lib/instruments';
import { buildHash, updateParams, type Route } from '../lib/router';
import { parseWeight, WEIGHTS } from '../lib/scoring';
import { thresholdLabel } from '../lib/turnover';
import type { Group, Instruments, Manifest, OverviewRow } from '../lib/types';
import { useApp } from '../state/AppState';
import { MarkBadge } from '../components/marks';

/** Wiederholungen derselben ISIN über die zehn Zeilen (beide Gruppen); Farbe wie in allen Ansichten. */
function tenMarkers(rows: TenWindowRow[], instruments: Instruments, slots: Map<number, number>): Map<number, Marker> {
  const map = new Map<number, Marker>();
  for (const entry of tenWindowCounts(rows, instruments)) {
    map.set(entry.idx, { idx: entry.idx, slot: slots.get(entry.idx) ?? null, count: entry.a + entry.b, countA: entry.a, countB: entry.b });
  }
  return map;
}

export function WinnersView({ route }: { route: Route }) {
  const { manifest, instruments, prefs, setPrefs } = useApp();
  const overview = useOverview();
  const weight = parseWeight(route.params.get('w'), prefs.w);
  const selected = route.params.get('isin');
  const open = route.params.get('offen');
  const data = overview.data;
  const rows = useMemo(() => (data ? tenWindowRows(data, weight) : []), [data, weight]);
  const markerMap = useMemo(
    () => (instruments && data ? tenMarkers(rows, instruments, markerSlots(data, instruments)) : new Map<number, Marker>()),
    [rows, instruments, data],
  );
  const counts = useMemo(() => (instruments ? tenWindowCounts(rows, instruments) : []), [rows, instruments]);

  if (!manifest || !instruments) return null;
  const set = (changes: Record<string, string | number | null>) => updateParams(route, changes);
  const selectedIdx = selected ? instruments.isin.indexOf(selected) : -1;
  const withB = data ? hasGroups(data) : false;
  const pick = (h: number, group: Group, idx: number) => {
    const key = `${h}${group}`;
    set({ offen: open === key ? null : key, isin: instruments.isin[idx] });
  };

  return (
    <div className="view winners-view">
      <header className="view-head">
        <p className="lede">Wer vorne lag – in zehn festen Zeiträumen nebeneinander, für alle Aktien (Gruppe A) und für Aktien mit Ø Tagesumsatz ab {thresholdLabel(manifest)} (Gruppe B).</p>
        <p className="section-note">
          Kursstand {f.dayLong(manifest.cutoff_day)}, berechnet {f.berlinTime(manifest.computed_at_utc)}. Historische Tagesschlusskurse, keine Livekurse. „30 Tage“ heißt 30 Kalendertage.
        </p>
      </header>

      <section className="weight-pick" aria-labelledby="sieger-gewichtung">
        <h2 className="control-label" id="sieger-gewichtung">
          Gewichtung Gleichmäßigkeit/Kursrendite
        </h2>
        <div className="wgrid" role="radiogroup" aria-labelledby="sieger-gewichtung">
          {WEIGHTS.map((w) => (
            <button
              key={w}
              type="button"
              role="radio"
              aria-checked={w === weight}
              className={`wchip-w${w === weight ? ' is-active' : ''}`}
              onClick={() => {
                setPrefs({ w });
                set({ w, offen: null });
              }}
            >
              {w}/{100 - w}
            </button>
          ))}
        </div>
        <p className="section-note">
          <strong>{f.weightLabel(weight)}.</strong>{' '}
          {weight === 0
            ? 'Gezeigt wird der tatsächliche Renditesieger jedes Zeitraums.'
            : 'Gezeigt wird der Sieger nach Rangscore (0–100) und daneben seine tatsächliche Kursrendite in genau diesem Zeitraum – er muss nicht die höchste reine Rendite haben.'}
        </p>
      </section>

      {overview.error ? <ErrorNote error={overview.error} /> : null}
      {!data && !overview.error ? <Loading height={520} label="Sieger werden geladen" /> : null}
      {data && !withB ? (
        <Notice tone="info" title="Gruppe B in diesem Datenstand noch nicht berechnet">
          <p>Die Ranglisten der Gruppe B gibt es ab Version 1.4. Der nächste tägliche Lauf rechnet sie mit.</p>
        </Notice>
      ) : null}

      {data ? (
        <ol className="tenw" aria-label={`Sieger nach Zeitraum, ${f.weightLabel(weight)}`}>
          {rows.map((row) => (
            <li key={row.h} className="tenw-row">
              <h3 className="tenw-h">
                <span className="tenw-days">{row.h}</span> Tage
              </h3>
              <WinnerCell
                manifest={manifest}
                instruments={instruments}
                row={row.a}
                h={row.h}
                group="a"
                weight={weight}
                marker={row.a.idx !== undefined ? markerMap.get(row.a.idx) : undefined}
                selected={row.a.idx !== undefined && row.a.idx === selectedIdx}
                expanded={open === `${row.h}a`}
                onPick={pick}
                onPure={() => set({ w: 0, offen: null })}
              />
              {row.b ? (
                <WinnerCell
                  manifest={manifest}
                  instruments={instruments}
                  row={row.b}
                  h={row.h}
                  group="b"
                  weight={weight}
                  marker={row.b.idx !== undefined ? markerMap.get(row.b.idx) : undefined}
                  selected={row.b.idx !== undefined && row.b.idx === selectedIdx}
                  expanded={open === `${row.h}b`}
                  onPick={pick}
                  onPure={() => set({ w: 0, offen: null })}
                />
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}

      {data ? (
        <section className="section" aria-labelledby="zehn-zaehlung">
          <SectionTitle id="zehn-zaehlung">Zählung nur über diese zehn Zeiträume</SectionTitle>
          <p className="section-note">
            Wie oft dieselbe Aktie (gleiche ISIN) in den zehn Zeilen oben bei {f.weightShort(weight)} auf Platz 1 steht. Das ist eine eigene, kleine Zählung – nicht die Häufigkeit über alle 90
            Zeiträume (dafür: <a href={buildHash('/haeufig', { w: null })}>Häufigste Aktien</a>). Benachbarte Zeiträume überlappen; mehrere Treffer sind keine unabhängigen Bestätigungen.
          </p>
          {counts.length === 0 ? (
            <p className="empty-body">Keine Aktie steht in mehr als einem dieser Zeiträume vorne.</p>
          ) : (
            <div className="table-wrap">
              <table className="table tenw-count">
                <thead>
                  <tr>
                    <th scope="col" className="sticky">
                      Aktie, ISIN
                    </th>
                    <th scope="col" className="n">
                      Platz 1 in A
                    </th>
                    {withB ? (
                      <th scope="col" className="n">
                        Platz 1 in B
                      </th>
                    ) : null}
                    <th scope="col">Zeiträume</th>
                  </tr>
                </thead>
                <tbody>
                  {counts.map((entry) => (
                    <tr key={entry.idx} className={entry.idx === selectedIdx ? 'is-selected' : ''}>
                      <th scope="row" className="sticky">
                        <button type="button" className="table-pick" aria-pressed={entry.idx === selectedIdx} onClick={() => set({ isin: entry.idx === selectedIdx ? null : instruments.isin[entry.idx] })}>
                          <span>{instName(instruments, entry.idx)}</span>
                        </button>
                        <MarkBadge marker={markerMap.get(entry.idx)} context="in diesen zehn Zeiträumen" />
                        <span className="gcell-isin" translate="no">
                          {instruments.isin[entry.idx]}
                        </span>
                      </th>
                      <td className="n">{f.integer(entry.a)}</td>
                      {withB ? <td className="n">{f.integer(entry.b)}</td> : null}
                      <td>{[...entry.windows].sort((x, y) => x - y).join(', ')} Tage</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}

function WinnerCell({
  manifest,
  instruments,
  row,
  h,
  group,
  weight,
  marker,
  selected,
  expanded,
  onPick,
  onPure,
}: {
  manifest: Manifest;
  instruments: Instruments;
  row: OverviewRow;
  h: number;
  group: Group;
  weight: number;
  marker: Marker | undefined;
  selected: boolean;
  expanded: boolean;
  onPick: (h: number, group: Group, idx: number) => void;
  onPure: () => void;
}) {
  const label = group === 'a' ? 'A – alle Aktien' : `B – Ø Umsatz ≥ ${thresholdLabel(manifest)}`;
  if (row.idx === undefined) {
    const reason = row.empty ?? 'keine_vergleichbare_aktie';
    return (
      <div className={`tenw-cell is-empty tenw-${group}`}>
        <span className="tenw-group">{label}</span>
        <p className="tenw-reason">
          <strong>{reason === 'zu_wenig_tagesdaten' ? 'Gleichmäßigkeit nicht berechenbar' : 'Keine Rangliste'}</strong>
          <span>{EMPTY_REASONS[reason] ?? 'Für diese Auswahl gibt es keine Rangliste.'}</span>
        </p>
        {weight !== 0 && reason === 'zu_wenig_tagesdaten' && group === 'a' ? (
          <button type="button" className="btn btn-quiet" onClick={onPure}>
            0/100-Renditesieger ansehen
          </button>
        ) : null}
      </div>
    );
  }
  const idx = row.idx;
  const isin = instruments.isin[idx];
  const currency = instruments.price_unit?.[idx] ?? instruments.currency[idx];
  return (
    <div className={`tenw-cell tenw-${group}${selected ? ' is-selected' : ''}`}>
      <span className="tenw-group">{label}</span>
      <button
        type="button"
        className="tenw-pick"
        aria-expanded={expanded}
        aria-label={`${h} Tage, ${label}: ${instName(instruments, idx)}, Kursrendite ${f.pct(row.r ?? null)}${weight ? `, Rangscore ${f.score(row.score ?? null)}` : ''}. Details ${expanded ? 'schließen' : 'öffnen'}`}
        onClick={() => onPick(h, group, idx)}
      >
        <span className="tenw-top">
          <MarkBadge marker={marker} context="in diesen zehn Zeiträumen" />
          {row.tie ? <span className="badge">gleichauf</span> : null}
          {row.sole ? <span className="badge">einziger Titel</span> : null}
        </span>
        <span className="tenw-name">{instName(instruments, idx)}</span>
        <span className="gcell-isin" translate="no">
          {isin}
        </span>
        <span className="tenw-figs">
          <Pct value={row.r ?? null} strong />
          {weight !== 0 ? (
            <span className="muted">
              Rangscore {f.score(row.score ?? null)} · R² {f.r2(row.r2 ?? null)}
            </span>
          ) : null}
        </span>
      </button>
      {expanded ? (
        <div className="tenw-detail">
          <KeyValues
            items={[
              ['Beginn (tatsächlich)', f.day(row.start ?? null)],
              ['Ende (Kursstichtag)', f.day(manifest.cutoff_day)],
              ['Schlusskurse im Fenster', row.n !== undefined ? f.integer(row.n) : '–'],
              ['Referenzmarkt', [instruments.exchange[idx], currency].filter(Boolean).join(', ') || '–'],
              ['Vergleichsfeld', `${f.integer(row.M)} Aktien`],
            ]}
          />
          <IsinCopy isin={isin} compact />
          <div className="toolbar">
            <a className="btn btn-primary" href={buildHash('/ranking', { h, w: weight, p: 'native', g: group === 'b' ? 'b' : null })}>
              Ganze Rangliste
            </a>
            <a className="btn" href={buildHash(`/aktie/${isin}`, { h, w: weight, p: 'native' })}>
              Kursverlauf
            </a>
          </div>
        </div>
      ) : null}
    </div>
  );
}
