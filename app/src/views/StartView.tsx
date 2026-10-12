import { LadderStrip } from '../components/charts';
import { InstrumentRow } from '../components/rows';
import { ErrorNote, IsinCopy, Loading, Pct, SectionTitle } from '../components/ui';
import { EMPTY_REASONS } from '../lib/codes';
import * as f from '../lib/format';
import { useFrequency, useOverview, useWindowHead } from '../lib/hooks';
import { instName } from '../lib/instruments';
import { buildHash, navigate } from '../lib/router';
import { cohortSize, rankedEntries } from '../lib/scoring';
import { useApp } from '../state/AppState';

export function StartView() {
  const { manifest, instruments, prefs, watchlist } = useApp();
  const overview = useOverview();
  const head = useWindowHead(prefs.h);
  const frequency = useFrequency();
  if (!manifest || !instruments) return null;

  const ov = overview.data;
  const ladderValues = ov ? ov.winners.map((row) => (row.entries.length ? row.entries[0].r : null)) : [];
  const ladderLabels = ov ? ov.winners.map((row) => (row.entries.length ? instName(instruments, row.entries[0].idx) : null)) : [];
  const vCount = ov ? ov.counts.V[prefs.h - 1] : null;
  const top = head.data ? rankedEntries(head.data, prefs.policy, prefs.w, 0, 5) : [];
  const fieldSize = head.data ? cohortSize(head.data, prefs.policy, prefs.w) : 0;
  const emptyReason = ov ? (prefs.policy === 'native' && prefs.w === 0 ? ov.v0 : ov.u[String(prefs.w)])[prefs.h - 1]?.empty : undefined;
  const maxEntry = ov?.overall_max.entries[0];

  return (
    <div className="view">
      <header className="stamp">
        <p className="stamp-date">Kursstand {f.dayLong(manifest.cutoff_day)}</p>
        <p className="stamp-meta">
          Letzter geprüfter Kursstand: {f.day(manifest.cutoff_day)}. Berechnet: {f.berlinTime(manifest.computed_at_utc)}.{' '}
          {vCount !== null ? `Teiluniversum: ${f.integer(vCount)} von ${f.integer(manifest.coverage.universe_total)} gelisteten Instrumenten für ${f.windowLabel(prefs.h)} vergleichbar.` : null}
        </p>
        {manifest.completeness.status === 'teilstand' ? (
          <p className="stamp-meta">
            Teilstand: Für {manifest.completeness.missing_markets.join(', ')} lagen am Stichtag noch keine vollständigen Schlusskurse vor.
          </p>
        ) : null}
      </header>

      <section className="section" aria-labelledby="leiter">
        <SectionTitle id="leiter">Höchste Kursrendite je Zeitraum</SectionTitle>
        <p className="section-note">Ein Balken je Rückblick von 1 bis 90 Kalendertagen: die Aktie mit der höchsten reinen Kursrendite. Antippen öffnet die Renditeliste dieses Zeitraums.</p>
        {overview.error ? <ErrorNote error={overview.error} /> : null}
        {ov ? (
          <LadderStrip values={ladderValues} labels={ladderLabels} onPick={(h) => navigate('/ranking', { h, w: 0, p: 'native', chart: 1 })} />
        ) : (
          <Loading height={168} label="Rendite-Leiter wird geladen" />
        )}
        <div className="toolbar">
          <a className="btn" href="#/rendite">
            Alle 90 Zeiträume als Tabelle
          </a>
        </div>
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

      <section className="section" aria-labelledby="eigene">
        <SectionTitle id="eigene">
          {f.windowLabel(prefs.h)}, {f.weightLabel(prefs.w)}
        </SectionTitle>
        <p className="section-note">
          {prefs.policy === 'common_trend' ? 'Gleiches Vergleichsfeld für alle Gewichtungen. ' : ''}
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
                    <span className="row-fig-sub">Score {f.score(entry.score)}</span>
                  </>
                }
              />
            ))}
          </ol>
        ) : null}
        <div className="toolbar">
          <a className="btn btn-primary" href={buildHash('/ranking', { h: prefs.h, w: prefs.w, p: prefs.policy })}>
            Ganze Rangliste öffnen
          </a>
          <a className="btn" href={buildHash('/vergleich', { h: prefs.h })}>
            Gewichtungen vergleichen
          </a>
        </div>
      </section>

      <section className="section" aria-labelledby="haeufig">
        <SectionTitle id="haeufig">Am häufigsten in den Top 10</SectionTitle>
        <p className="section-note">Über alle elf Gewichtungen und alle Zeiträume 1–90 dieses Stands gezählt. Viele Treffer sind keine unabhängigen Bestätigungen und keine Prognose.</p>
        {frequency.error ? <ErrorNote error={frequency.error} /> : null}
        {!frequency.data && !frequency.error ? <Loading height={200} /> : null}
        {frequency.data ? (
          frequency.data.server_reference.entries.length ? (
            <ol className="rows">
              {frequency.data.server_reference.entries.slice(0, 3).map((entry, k) => (
                <InstrumentRow
                  key={entry.idx}
                  idx={entry.idx}
                  rank={k + 1}
                  href={buildHash(`/haeufig/${instruments.isin[entry.idx]}`, { p: 'native', k: 10 })}
                  figs={
                    <>
                      <span className="pct pct-strong">{f.integer(entry.n10)}</span>
                      <span className="row-fig-sub">Top-10-Treffer</span>
                      <span className="row-fig-sub">in {f.plural(entry.H, 'Zeitraum', 'Zeiträumen')}</span>
                    </>
                  }
                />
              ))}
            </ol>
          ) : (
            <p className="empty-body">In diesem Stand gibt es keine veröffentlichte Rangliste.</p>
          )
        ) : null}
        <div className="toolbar">
          <a className="btn" href="#/haeufig">
            Häufigkeitsliste öffnen
          </a>
        </div>
      </section>

      <section className="section" aria-labelledby="weiter">
        <SectionTitle id="weiter">Weitere Ansichten</SectionTitle>
        <ul className="link-list">
          <li>
            <a href="#/raster">
              Chart-Raster <span>Kursverläufe nebeneinander</span>
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
