import { useEffect, useMemo, useRef, useState } from 'react';
import { LadderStrip } from '../components/charts';
import { InfoTip, TotalBadge } from '../components/signals';
import { WindowRuler } from '../components/controls';
import { InstrumentRow } from '../components/rows';
import { Disclosure, ErrorNote, IsinCopy, Loading, Pct, Segmented, SectionTitle } from '../components/ui';
import { EMPTY_REASONS } from '../lib/codes';
import * as f from '../lib/format';
import { GROUP_TEXT, hasGroups, overviewRow, tenWindowRows } from '../lib/groups';
import { useOverview, useRotationIndex, useSignals, useWindowHead } from '../lib/hooks';
import { LIST_INFO, LIST_KINDS, rankSignals, totalsByIsin, type ListKind } from '../lib/signals';
import { reportLeaders, reportMarkers } from '../lib/report';
import { rhythmText } from '../lib/rotation';
import { instName } from '../lib/instruments';
import { joinNames, partialSummary } from '../lib/markets';
import { berlinClock, closeLabel, intradayBanner, intradayExplanation, isIntraday } from '../lib/intraday';
import { centerActive } from '../lib/scroll';
import { buildHash, navigate } from '../lib/router';
import { cohortSize, rankedEntries, WEIGHTS } from '../lib/scoring';
import { canHideNoisy, hasCleanWinners, quietRanked, thresholdLabel, winnersOf } from '../lib/turnover';
import type { Group, Instruments, Manifest, Overview, RotationIndex } from '../lib/types';
import { useApp } from '../state/AppState';
import { SignalRows } from './PotentialView';
import { TopThree } from '../components/top';

/** Hinweis „Teilstand“: welche Börsen fehlen (oder, wenn das die kürzere Liste ist, welche enthalten sind) und warum. */
function PartialNotice({ manifest }: { manifest: Manifest }) {
  const s = partialSummary(manifest);
  return (
    <p className="stamp-meta stamp-partial">
      <strong>Teilstand:</strong>{' '}
      {s.mode === 'delivered' ? (
        <>
          {manifest.letzter_schlusskurs ? 'Schlusskurse vom Stichtag nur von' : 'Enthalten sind nur Aktien von'} {f.integer(s.delivered)} der {f.integer(s.markets)} Börsen mit Handel am Stichtag:{' '}
          {joinNames(s.names)}. Für die übrigen {f.integer(s.missing)} lieferte der Kursanbieter keine vollständigen Schlusskurse.
        </>
      ) : (
        <>
          Für {f.plural(s.missing, 'Börse', 'Börsen')} lieferte der Kursanbieter am Stichtag keine vollständigen Schlusskurse ({s.names.join(', ')}).
        </>
      )}{' '}
      {manifest.letzter_schlusskurs
        ? 'Deren Aktien zählen mit ihrem letzten Schlusskurs (in der Zeile „Schlusskurs …“), wenn er höchstens eine Börsensitzung zurückliegt; sonst fehlen sie wegen fehlender Daten, nicht wegen ihrer Kursentwicklung.'
        : 'Deren Aktien fehlen in diesem Stand in den Ranglisten – wegen fehlender Daten, nicht wegen ihrer Kursentwicklung.'}
    </p>
  );
}

export function StartView() {
  const { manifest, instruments, prefs, setPrefs, status, switchSnapshot } = useApp();
  const overview = useOverview();
  const head = useWindowHead(prefs.h);
  if (!manifest || !instruments) return null;

  const ov = overview.data;
  const withB = ov ? hasGroups(ov) : false;
  const group: Group = prefs.group === 'b' && withB ? 'b' : 'a';
  // „Auffällige ausblenden“ (ab 1.14) gilt auch hier: erste fünf ohne Auffällige, Leiter aus den Spitzenreitern ohne Auffällige
  const clean = prefs.ohneAuffaellige && canHideNoisy(instruments);
  const top = head.data ? (clean ? quietRanked(head.data, prefs.policy, prefs.w, group, instruments, manifest).slice(0, 5) : rankedEntries(head.data, prefs.policy, prefs.w, 0, 5, group)) : [];
  const fieldSize = head.data ? cohortSize(head.data, prefs.policy, prefs.w, group) : 0;
  const emptyRow =
    ov && prefs.policy === 'common_trend' && prefs.w === 0 ? (group === 'b' ? ov.ul?.['0'] : ov.u['0'])?.[prefs.h - 1] : ov ? overviewRow(ov, group, prefs.w, prefs.h) : undefined;
  const emptyReason = emptyRow?.empty;
  const lastRun = status?.last_run;
  const rankingLink = buildHash('/ranking', { h: prefs.h, w: prefs.w, p: prefs.policy, g: group === 'b' ? 'b' : null });
  const officialId = manifest.zwischenstand?.offizieller_stand ?? status?.latest_official_snapshot_id ?? null;

  // Ab 1.15 (Simons Wahl „übersichtlicher“): wichtigste Zahlen zuerst – Top 3, Kursstand in einer Zeile, Kandidaten,
  // Bericht, die eigene Rangliste mit Auswahl in einem Abschnitt; Sieger je Zeitraum, Rendite-Leiter, Höchstwert,
  // Umschichtungs-Regel und Abdeckung unter „Mehr auf einen Blick“
  return (
    <div className="view">
      <TopThree />

      <header className="stamp">
        {isIntraday(manifest) ? (
          <>
            <p className="stamp-date">
              Zwischenstand {f.dayLong(manifest.cutoff_day)}, {berlinClock(manifest.zwischenstand?.kurse_bis_utc)}
            </p>
            <p className="stamp-meta">{intradayBanner(manifest)}</p>
            <Disclosure summary="Was ist ein Zwischenstand?">
              <p>
                Vorläufig: je Aktie der letzte gemeldete Kurs von heute (verzögert), noch kein Schlusskurs. Abgerufen {f.berlinTime(manifest.computed_at_utc)}.
                {status?.schedule ? ` Schlusskurse aller Börsen: täglich um ${status.schedule.uhrzeit} Uhr.` : ''}
              </p>
              {intradayExplanation(manifest).map((line) => (
                <p key={line}>{line}</p>
              ))}
            </Disclosure>
          </>
        ) : (
          <>
            <p className="stamp-date">Kursstand {f.dayLong(manifest.cutoff_day)}</p>
            <p className="stamp-meta">
              Schlusskurse, berechnet {f.berlinTime(manifest.computed_at_utc)}
              {lastRun ? ` · letzter Lauf ${f.runStatus(lastRun.status)}` : ''}
              {status?.schedule ? ` · nächster Lauf ${status.schedule.uhrzeit} Uhr` : ''}
            </p>
            {manifest.completeness.status === 'teilstand' ? <PartialNotice manifest={manifest} /> : null}
          </>
        )}
        <div className="toolbar stamp-actions no-print">
          <a className="btn" href="#/aktualisieren">
            Kurse jetzt aktualisieren
          </a>
          {isIntraday(manifest) && officialId ? (
            <button type="button" className="btn" onClick={() => switchSnapshot(officialId)}>
              {closeLabel(manifest.zwischenstand?.offizieller_stichtag)} anzeigen
            </button>
          ) : null}
        </div>
      </header>

      <CandidatesTeaser />

      <ReportTeaser overview={ov ?? null} instruments={instruments} />

      <section className="section start-ranking" aria-labelledby="eigene">
        <SectionTitle id="eigene">
          {f.windowLabel(prefs.h)}, {f.weightShort(prefs.w)} · Gruppe {group.toUpperCase()}
        </SectionTitle>
        <p className="section-note">
          {f.weightLabel(prefs.w)}. {GROUP_TEXT[group][0].toUpperCase() + GROUP_TEXT[group].slice(1)}.{' '}
          {head.data ? `Vergleichsfeld: ${f.plural(fieldSize, 'Aktie', 'Aktien')}${clean ? ', Auffällige ausgeblendet (Plätze wie vollständig)' : ''}.` : null}
        </p>
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
        <a className="entry entry-main" href="#/bericht">
          <strong>Bericht 1–30 Tage</strong>
          <span>Platz 1 je Zeitraum · 0/100, 40/60, 50/50, 60/40 · A und B · Häufigkeit</span>
        </a>
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

      <div className="start-more">
        <Disclosure summary="Mehr auf einen Blick: Sieger je Zeitraum, Rendite-Leiter, Höchstwert, Umschichtungs-Regel, Abdeckung">
          <MoreAtAGlance overview={ov ?? null} overviewError={overview.error} weight={prefs.w} h={prefs.h} withB={withB} clean={clean} />
        </Disclosure>
      </div>
    </div>
  );
}

/** „Mehr auf einen Blick“ (ab 1.15): was früher die Startseite verlängerte – erst beim Aufklappen gezeigt und geladen. */
function MoreAtAGlance({ overview: ov, overviewError, weight, h, withB, clean }: { overview: Overview | null; overviewError: unknown; weight: number; h: number; withB: boolean; clean: boolean }) {
  const { manifest, instruments } = useApp();
  const rotation = useRotationIndex(Boolean(manifest?.rotation));
  if (!manifest || !instruments) return null;
  const ladderRows = ov ? winnersOf(ov, 'alle', clean && hasCleanWinners(ov)) : [];
  const ladderValues = ladderRows.map((row) => (row.entries.length ? row.entries[0].r : null));
  const ladderLabels = ladderRows.map((row) => (row.entries.length ? instName(instruments, row.entries[0].idx) : null));
  const maxEntry = ov?.overall_max.entries[0];
  const cov = manifest.coverage;
  const counts = ov?.counts;
  return (
    <>
      {ov ? <TenWindowTeaser overview={ov} weight={weight} /> : null}

      <section className="section" aria-labelledby="leiter">
        <SectionTitle id="leiter">Höchste Kursrendite je Zeitraum</SectionTitle>
        <p className="section-note">
          Ein Balken je Rückblick von 1 bis 90 Kalendertagen: die Aktie mit der höchsten reinen Kursrendite (Gruppe A{clean && ov && hasCleanWinners(ov) ? ', ohne Auffällige' : ''}). Antippen öffnet die
          Renditeliste dieses Zeitraums.
        </p>
        {overviewError ? <ErrorNote error={overviewError} /> : null}
        {ov ? (
          <LadderStrip values={ladderValues} labels={ladderLabels} onPick={(pick) => navigate('/ranking', { h: pick, w: 0, p: 'native', chart: 1 })} />
        ) : (
          <Loading height={168} label="Rendite-Leiter wird geladen" />
        )}
      </section>

      {maxEntry && ov ? (
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
              Rückblickendes Maximum über {f.integer(ov.overall_max.pairs_evaluated)} geprüfte Aktie-Zeitraum-Paare dieses Stands. Keine erwartete künftige Rendite, keine einheitliche Haltedauer und kein Depotgewinn.
              {ov.overall_max.tie ? ' Mehrere Aktien erreichen exakt denselben Wert (Gleichstand).' : ''}
            </p>
          </div>
        </section>
      ) : null}

      {manifest.rotation ? <RotationTeaser index={rotation.data} /> : null}

      <section className="section" aria-labelledby="abdeckung">
        <SectionTitle id="abdeckung">Abdeckung</SectionTitle>
        <p className="stamp-meta coverage-counts">
          Berechnet {f.integer(cov.with_any_return_window)} / identifiziert {f.integer(cov.identified)} – von {f.integer(cov.universe_total)} Einträgen der TR-Liste ({f.integer(cov.histories_loaded)} Kursreihen
          geladen).
          {counts
            ? ` Bei ${h} Tagen: Gruppe A ${f.integer(counts.V[h - 1])} Kursrenditen, davon ${f.integer(counts.U[h - 1])} mit Gleichmäßigkeit${
                withB ? `; Gruppe B ${f.integer(counts.L?.[h - 1] ?? 0)} bzw. ${f.integer(counts.UL?.[h - 1] ?? 0)}` : ''
              }.`
            : ''}{' '}
          <a href="#/aktien">Abdeckung im Detail</a>
        </p>
      </section>
    </>
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

/** Startseite: Bericht 1–30 in Kürze (ab 1.8.2) – die drei häufigsten Spitzenreiter und der Weg zum Bericht. */
function ReportTeaser({ overview, instruments }: { overview: Overview | null; instruments: Instruments }) {
  const signals = useSignals();
  const totals = useMemo(() => totalsByIsin(signals.data), [signals.data]);
  const leaders = useMemo(() => (overview ? reportLeaders(reportMarkers(overview, instruments), instruments, 3) : []), [overview, instruments]);
  return (
    <section className="section report-teaser" aria-labelledby="bericht-kurz">
      <SectionTitle id="bericht-kurz">Bericht 1–30 Tage</SectionTitle>
      <p className="section-note">Platz 1 je Zeitraum von 1 bis 30 Tagen für 0/100, 40/60, 50/50 und 60/40, Gruppe A und B. Am häufigsten vorne:</p>
      {!overview ? <Loading height={96} label="Bericht wird geladen" /> : null}
      {overview && !leaders.length ? <p className="section-note">In diesem Datenstand hat keine Rangliste einen Spitzenreiter.</p> : null}
      {leaders.length ? (
        <ol className="rep-teaser">
          {leaders.map((m) => {
            const entry = totals?.get(instruments.isin[m.idx]);
            return (
              <li key={m.idx}>
                <a href={buildHash('/bericht', { m: instruments.isin[m.idx] })}>
                  <span className="rep-teaser-name">
                    {instName(instruments, m.idx)}
                    {entry ? <TotalBadge total={entry.total} grade={entry.grade} size="mini" /> : null}
                  </span>
                  <b>{m.count}× Platz 1</b>
                </a>
              </li>
            );
          })}
        </ol>
      ) : null}
      <div className="toolbar">
        <a className="btn btn-primary" href="#/bericht">
          Bericht öffnen
        </a>
        <a className="btn" href="#/depots">
          Musterdepots
        </a>
      </div>
    </section>
  );
}

/** Startseite oben: Kandidaten mit Potenzial (Signal-Stand ab 1.6). */
function CandidatesTeaser() {
  const { status, instruments } = useApp();
  const signals = useSignals();
  const [kind, setKind] = useState<ListKind>('gesamt');
  const listStrip = useRef<HTMLDivElement | null>(null);
  useEffect(() => centerActive(listStrip.current), [kind]);
  if (!status?.signale || !instruments) {
    return (
      <section className="section candidates" aria-labelledby="kandidaten">
        <SectionTitle id="kandidaten">Kandidaten mit Potenzial</SectionTitle>
        <p className="section-note">Kursziele, Kennzahlen und Signale werden nach dem nächsten täglichen Lauf berechnet. Danach stehen hier die Aktien, bei denen die meisten Signale positiv sind.</p>
      </section>
    );
  }
  const data = signals.data;
  const order = data ? rankSignals(data, { kind, minAnalysts: kind === 'potenzial' ? 3 : 0, onlyGreen: false, liquidOnly: false, sector: null }) : [];
  return (
    <section className="section candidates" aria-labelledby="kandidaten">
      <h2 className="section-title explained" id="kandidaten">
        <span>Kandidaten mit Potenzial</span>
        <InfoTip label="Kandidaten mit Potenzial">
          Alle Aktien der Trade-Republic-Liste, automatisch bewertet. <strong>Gesamt</strong> sortiert nach der Gesamtwertung: Steig-Konstanz (an wie vielen Handelstagen der letzten
          30, 60 und 90 Tage die Aktie gestiegen ist), Kursziel-Potenzial der Analysten, Aufmerksamkeit und Qualität. Jede Aktie hat außerdem zwei Ampeln: <strong>kurz</strong> (Tage
          bis Wochen) und <strong>lang</strong> (etwa 12 Monate). Keine Kaufempfehlung – die Gründe stehen in der Einzelansicht.
        </InfoTip>
      </h2>
      <div className="segmented-wrap">
        <div className="segmented" role="radiogroup" aria-label="Liste" ref={listStrip}>
          {LIST_KINDS.map((value) => (
            <button key={value} type="button" role="radio" aria-checked={value === kind} className={value === kind ? 'is-active' : ''} onClick={() => setKind(value)}>
              {LIST_INFO[value].label}
            </button>
          ))}
        </div>
      </div>
      <p className="section-note">{LIST_INFO[kind].text}</p>
      {signals.error ? <ErrorNote error={signals.error} /> : null}
      {!data && !signals.error ? <Loading height={260} label="Signale werden geladen" /> : null}
      {data ? <SignalRows data={data} order={order} kind={kind} limit={3} /> : null}
      <div className="toolbar">
        <a className="btn btn-primary" href={buildHash('/potenzial', { liste: kind === 'gesamt' ? null : kind })}>
          Alle Kandidaten
        </a>
      </div>
    </section>
  );
}
