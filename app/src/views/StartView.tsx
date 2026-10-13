import { LadderStrip } from '../components/charts';
import { WindowRuler } from '../components/controls';
import { InstrumentRow } from '../components/rows';
import { ErrorNote, IsinCopy, Loading, Pct, Segmented, SectionTitle } from '../components/ui';
import { EMPTY_REASONS } from '../lib/codes';
import * as f from '../lib/format';
import { GROUP_TEXT, hasGroups, overviewRow, tenWindowRows } from '../lib/groups';
import { useOverview, useRotationIndex, useWindowHead } from '../lib/hooks';
import { rhythmText } from '../lib/rotation';
import { instName } from '../lib/instruments';
import { joinNames, partialSummary } from '../lib/markets';
import { buildHash, navigate } from '../lib/router';
import { cohortSize, rankedEntries, WEIGHTS } from '../lib/scoring';
import { thresholdLabel } from '../lib/turnover';
import type { Group, Manifest, RotationIndex } from '../lib/types';
import { useApp } from '../state/AppState';

/** Hinweis „Teilstand“: welche Börsen fehlen (oder, wenn das die kürzere Liste ist, welche enthalten sind) und warum. */
function PartialNotice({ manifest }: { manifest: Manifest }) {
  const s = partialSummary(manifest);
  return (
    <p className="stamp-meta stamp-partial">
      <strong>Teilstand:</strong>{' '}
      {s.mode === 'delivered' ? (
        <>
          Enthalten sind nur Aktien von {f.integer(s.delivered)} der {f.integer(s.markets)} Börsen mit Handel am Stichtag: {joinNames(s.names)}. Für die übrigen {f.integer(s.missing)} lieferte der Kursanbieter
          keine vollständigen Schlusskurse.
        </>
      ) : (
        <>
          Für {f.plural(s.missing, 'Börse', 'Börsen')} lieferte der Kursanbieter am Stichtag keine vollständigen Schlusskurse ({s.names.join(', ')}).
        </>
      )}{' '}
      Deren Aktien fehlen in diesem Stand in den Ranglisten – wegen fehlender Daten, nicht wegen ihrer Kursentwicklung.
    </p>
  );
}

export function StartView() {
  const { manifest, instruments, prefs, setPrefs, watchlist, status } = useApp();
  const overview = useOverview();
  const head = useWindowHead(prefs.h);
  const rotation = useRotationIndex();
  if (!manifest || !instruments) return null;

  const ov = overview.data;
  const withB = ov ? hasGroups(ov) : false;
  const group: Group = prefs.group === 'b' && withB ? 'b' : 'a';
  const ladderValues = ov ? ov.winners.map((row) => (row.entries.length ? row.entries[0].r : null)) : [];
  const ladderLabels = ov ? ov.winners.map((row) => (row.entries.length ? instName(instruments, row.entries[0].idx) : null)) : [];
  const top = head.data ? rankedEntries(head.data, prefs.policy, prefs.w, 0, 5, group) : [];
  const fieldSize = head.data ? cohortSize(head.data, prefs.policy, prefs.w, group) : 0;
  const emptyRow =
    ov && prefs.policy === 'common_trend' && prefs.w === 0 ? (group === 'b' ? ov.ul?.['0'] : ov.u['0'])?.[prefs.h - 1] : ov ? overviewRow(ov, group, prefs.w, prefs.h) : undefined;
  const emptyReason = emptyRow?.empty;
  const maxEntry = ov?.overall_max.entries[0];
  const cov = manifest.coverage;
  const counts = ov?.counts;
  const lastRun = status?.last_run;
  const rankingLink = buildHash('/ranking', { h: prefs.h, w: prefs.w, p: prefs.policy, g: group === 'b' ? 'b' : null });

  return (
    <div className="view">
      <header className="stamp">
        <p className="stamp-date">Kursstand {f.dayLong(manifest.cutoff_day)}</p>
        <p className="stamp-meta">
          Berechnet: {f.berlinTime(manifest.computed_at_utc)}. Tagesschlusskurse, keine Livekurse.
          {lastRun ? ` Tageslauf: ${f.runStatus(lastRun.status)} (${f.berlinTime(lastRun.finished_at_utc ?? lastRun.started_at_utc)}).` : ''}
          {status?.schedule ? ` Nächster planmäßiger Lauf ${status.schedule.uhrzeit} Uhr.` : ''}
        </p>
        {manifest.completeness.status === 'teilstand' ? <PartialNotice manifest={manifest} /> : null}
        <p className="stamp-meta coverage-counts">
          Berechnet {f.integer(cov.with_any_return_window)} / identifiziert {f.integer(cov.identified)} – von {f.integer(cov.universe_total)} Einträgen der TR-Liste ({f.integer(cov.histories_loaded)} Kursreihen
          geladen).
          {counts
            ? ` Bei ${prefs.h} Tagen: Gruppe A ${f.integer(counts.V[prefs.h - 1])} Kursrenditen, davon ${f.integer(counts.U[prefs.h - 1])} mit Gleichmäßigkeit${
                withB ? `; Gruppe B ${f.integer(counts.L?.[prefs.h - 1] ?? 0)} bzw. ${f.integer(counts.UL?.[prefs.h - 1] ?? 0)}` : ''
              }.`
            : ''}{' '}
          <a href="#/aktien">Abdeckung im Detail</a>
        </p>
      </header>

      <section className="section" aria-labelledby="auswahl">
        <SectionTitle id="auswahl">Auswahl</SectionTitle>
        {withB ? (
          <Segmented
            label="Aktiengruppe"
            options={[
              { value: 'a', label: 'A: alle Aktien' },
              { value: 'b', label: `B: Ø Umsatz ≥ ${thresholdLabel(manifest)}` },
            ]}
            value={group}
            onChange={(g) => setPrefs({ group: g as Group })}
          />
        ) : null}
        <WindowRuler value={prefs.h} onChange={(h) => setPrefs({ h })} compact />
        <div className="weight-pick">
          <span className="control-label" id="start-gewichtung">
            Gewichtung Gleichmäßigkeit/Kursrendite
          </span>
          <div className="wgrid" role="radiogroup" aria-labelledby="start-gewichtung">
            {WEIGHTS.map((w) => (
              <button key={w} type="button" role="radio" aria-checked={w === prefs.w} className={`wchip-w${w === prefs.w ? ' is-active' : ''}`} onClick={() => setPrefs({ w })}>
                {w}/{100 - w}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="eigene">
        <SectionTitle id="eigene">
          {f.windowLabel(prefs.h)}, {f.weightShort(prefs.w)} · Gruppe {group.toUpperCase()}
        </SectionTitle>
        <p className="section-note">
          {f.weightLabel(prefs.w)}. {GROUP_TEXT[group][0].toUpperCase() + GROUP_TEXT[group].slice(1)}.{' '}
          {head.data ? `Vergleichsfeld: ${f.plural(fieldSize, 'Aktie', 'Aktien')}.` : null}
        </p>
        {head.error ? <ErrorNote error={head.error} /> : null}
        {!head.data && !head.error ? <Loading height={260} /> : null}
        {head.data && top.length === 0 ? <p className="empty-body">{EMPTY_REASONS[emptyReason ?? 'keine_vergleichbare_aktie'] ?? 'Für diese Auswahl gibt es keine Rangliste.'}</p> : null}
        {top.length ? (
          <ol className="rows" aria-label={`Erste fünf Plätze, ${f.windowLabel(prefs.h)}`}>
            {top.map((entry) => (
              <InstrumentRow
                key={entry.idx}
                idx={entry.idx}
                rank={entry.rank}
                tie={entry.tie}
                href={buildHash(`/aktie/${instruments.isin[entry.idx]}`, { h: prefs.h, w: prefs.w, p: prefs.policy })}
                figs={
                  <>
                    <Pct value={entry.r} strong />
                    {entry.r2 !== null ? <span className="row-fig-sub">R² {f.r2(entry.r2)}</span> : null}
                    <span className="row-fig-sub">Rangscore {f.score(entry.score)}</span>
                  </>
                }
              />
            ))}
          </ol>
        ) : null}
        <div className="toolbar">
          <a className="btn btn-primary" href={rankingLink}>
            Ganze Rangliste öffnen
          </a>
        </div>
      </section>

      <nav className="entry-grid" aria-label="Direkte Einstiege">
        <a className="entry" href={buildHash('/rendite', { h: prefs.h })}>
          <strong>Höchste Rendite</strong>
          <span>Sieger A und B für alle 90 Zeiträume</span>
        </a>
        <a className="entry" href={rankingLink}>
          <strong>Gleichmäßigkeit + Rendite</strong>
          <span>Rangliste mit {f.weightShort(prefs.w)}</span>
        </a>
        <a className="entry" href={buildHash('/haeufig', { gruppen: group === 'b' ? 'b' : null })}>
          <strong>Häufigste Aktien</strong>
          <span>Platz 1, Top 3, Top 10 über alle Vergleiche</span>
        </a>
        <a className="entry" href={buildHash('/raster', { h: prefs.h, w: prefs.w, p: prefs.policy, g: group === 'b' ? 'b' : null })}>
          <strong>Kursvergleich</strong>
          <span>Erste 10 als Charts, Start = 100</span>
        </a>
      </nav>

      {ov ? <TenWindowTeaser overview={ov} weight={prefs.w} /> : null}

      <section className="section" aria-labelledby="leiter">
        <SectionTitle id="leiter">Höchste Kursrendite je Zeitraum</SectionTitle>
        <p className="section-note">Ein Balken je Rückblick von 1 bis 90 Kalendertagen: die Aktie mit der höchsten reinen Kursrendite (Gruppe A). Antippen öffnet die Renditeliste dieses Zeitraums.</p>
        {overview.error ? <ErrorNote error={overview.error} /> : null}
        {ov ? (
          <LadderStrip values={ladderValues} labels={ladderLabels} onPick={(h) => navigate('/ranking', { h, w: 0, p: 'native', chart: 1 })} />
        ) : (
          <Loading height={168} label="Rendite-Leiter wird geladen" />
        )}
      </section>

      {maxEntry ? (
        <section className="section" aria-labelledby="maximum">
          <div className="maxbox">
            <SectionTitle id="maximum">Höchste beobachtete Kursrendite in einem der 90 Fenster</SectionTitle>
            <div className="maxbox-value">
              <Pct value={maxEntry.r} />
              <span>
                in {f.windowLabel(maxEntry.h)} ({f.dayRange(maxEntry.start, maxEntry.end)})
                {maxEntry.same_h?.length ? `, gleicher tatsächlicher Zeitraum auch bei ${maxEntry.same_h.join(', ')} Tagen` : ''}
              </span>
            </div>
            <a className="row-name" href={buildHash(`/aktie/${instruments.isin[maxEntry.idx]}`, { h: maxEntry.h })}>
              {instName(instruments, maxEntry.idx)}
            </a>
            <IsinCopy isin={instruments.isin[maxEntry.idx]} />
            <p className="section-note">
              Rückblickendes Maximum über {f.integer(ov!.overall_max.pairs_evaluated)} geprüfte Aktie-Zeitraum-Paare dieses Stands. Keine erwartete künftige Rendite, keine einheitliche Haltedauer und kein Depotgewinn.
              {ov!.overall_max.tie ? ' Mehrere Aktien erreichen exakt denselben Wert (Gleichstand).' : ''}
            </p>
          </div>
        </section>
      ) : null}

      {manifest.rotation ? <RotationTeaser index={rotation.data} /> : null}

      <section className="section" aria-labelledby="weiter">
        <SectionTitle id="weiter">Weitere Ansichten</SectionTitle>
        <ul className="link-list">
          <li>
            <a href="#/matrix">
              Matrix A/B <span>Spitzenreiter 1–90 Tage × 11 Gewichtungen für alle Aktien und für Ø Umsatz ≥ 10 Mio. USD</span>
            </a>
          </li>
          <li>
            <a href="#/watchlist">
              Watchlist <span>{f.plural(watchlist.length, 'Aktie', 'Aktien')}</span>
            </a>
          </li>
          <li>
            <a href="#/aktien">
              Alle Aktien & Abdeckung <span>{f.integer(manifest.coverage.universe_total)} in der TR-Liste</span>
            </a>
          </li>
          <li>
            <a href="#/methodik">
              So wird gerechnet <span>Formeln und Grenzen</span>
            </a>
          </li>
        </ul>
      </section>
    </div>
  );
}

/** Kurzfassung „Sieger nach Zeitraum“: zehn feste Zeiträume, Gruppe A und B. */
function TenWindowTeaser({ overview, weight }: { overview: import('../lib/types').Overview; weight: number }) {
  const { instruments } = useApp();
  if (!instruments) return null;
  const rows = tenWindowRows(overview, weight);
  return (
    <section className="section" aria-labelledby="sieger">
      <SectionTitle id="sieger">Sieger nach Zeitraum, {f.weightShort(weight)}</SectionTitle>
      <p className="section-note">{weight === 0 ? 'Tatsächlicher Renditesieger je Zeitraum.' : 'Sieger nach Rangscore und seine tatsächliche Kursrendite im selben Zeitraum.'}</p>
      <ol className="tenw-mini">
        {rows.map((row) => (
          <li key={row.h}>
            <span className="tenw-mini-h">{row.h} T</span>
            {[row.a, row.b].map((cell, k) =>
              cell === null ? null : (
                <span key={k} className="tenw-mini-cell">
                  <small>{k === 0 ? 'A' : 'B'}</small>
                  {cell.idx !== undefined ? (
                    <>
                      <span className="tenw-mini-name">{instName(instruments, cell.idx)}</span>
                      <Pct value={cell.r ?? null} digits={1} />
                    </>
                  ) : (
                    <span className="muted">{cell.empty === 'zu_wenig_tagesdaten' ? 'Gleichmäßigkeit nicht berechenbar' : 'keine Rangliste'}</span>
                  )}
                </span>
              ),
            )}
          </li>
        ))}
      </ol>
      <div className="toolbar">
        <a className="btn" href={buildHash('/sieger', { w: weight })}>
          Sieger nach Zeitraum öffnen
        </a>
      </div>
    </section>
  );
}

/** Kurzfassung der Umschichtungs-Regel (Standardvariante) mit Link zur ganzen Seite. */
function RotationTeaser({ index }: { index: RotationIndex | null }) {
  const info = index ? index.varianten.find((v) => v.key === index.standard) ?? null : null;
  const stats = info?.kennzahlen;
  return (
    <section className="section" aria-labelledby="umschichten">
      <SectionTitle id="umschichten">Umschichtungs-Regel</SectionTitle>
      {info && info.status === 'ok' && stats ? (
        <p className="section-note">
          {info.aktien} Aktien mit der höchsten Kursrendite der letzten {info.trend_wochen} Wochen, je {f.plainPct(100 / info.aktien, 0)}, umgeschichtet {rhythmText(info.rhythmus)}.{' '}
          {info.aenderungen_heute
            ? info.beschlossen_am
              ? `Sie ändert jetzt ${f.plural(info.aenderungen_heute, 'Position', 'Positionen')}`
              : `Nach heutigem Stand würde sie ${f.plural(info.aenderungen_heute, 'Position', 'Positionen')} ändern`
            : 'Nach heutigem Stand keine Änderung'}
          {info.beschlossen_am ? ` (beschlossen am ${f.day(info.beschlossen_am)})` : ''}
          {info.naechste_entscheidung ? `; nächste Entscheidung ${f.day(info.naechste_entscheidung)}.` : '.'} Rückblick seit {f.day(stats.start_day)}: {f.pct(stats.rendite, 1)} nach Kosten und Steuern
          (alle Kandidaten {f.pct(stats.vergleich_rendite, 1)}). Eine Rechenregel, keine Empfehlung.
        </p>
      ) : (
        <p className="section-note">Eine feste Rechenregel zum Ausprobieren: welche Aktien sie heute hielte und wie sie sich im Rückblick nach Kosten und Steuern entwickelt hätte.</p>
      )}
      <div className="toolbar">
        <a className="btn" href="#/regel">
          Regel ansehen
        </a>
      </div>
    </section>
  );
}
