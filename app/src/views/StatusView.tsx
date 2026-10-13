import { IconDownload } from '../components/icons';
import { Disclosure, KeyValues, Notice, SectionTitle } from '../components/ui';
import { READY_LEVEL, statusInfo } from '../lib/codes';
import { downloadText, safeFilename } from '../lib/csv';
import { PREVIEW } from '../lib/env';
import * as f from '../lib/format';
import { cutoffCoverage, marketName, missingMarketNames } from '../lib/markets';
import { venueDayRule } from '../lib/venue';
import { useApp } from '../state/AppState';

const CHECK_LABELS: Record<string, string> = {
  fenster_1_bis_90: 'Alle 90 Zeiträume berechnet',
  elf_gewichtungen: 'Elf Gewichtungen 0/100 bis 100/0',
  abdeckung_summe_gleich_universum: 'Abdeckungsbilanz ergibt das Universum',
  u_teilmenge_von_v: 'Gleichmäßig gestiegene Aktien sind Teil der Renditeliste',
  ranglistengroessen: 'Ranglistengrößen stimmen',
  eindeutige_plaetze: 'Jeder Platz eindeutig',
  sortierregeln: 'Sortierregeln eingehalten',
  scores_0_bis_100: 'Rangscores zwischen 0 und 100',
  aufwaertsbedingungen_und_endliche_werte: 'Aufwärtsbedingungen und endliche Werte',
  renditesieger_90_zeilen: 'Renditesiegerliste mit 90 Zeilen',
  haeufigkeit_invarianten: 'Häufigkeitszählung widerspruchsfrei',
  ranking2_teilmenge_gleiche_rendite: 'Ranking mit Umsatzfilter = Renditeliste ohne die nicht aufgenommenen Aktien (gleiche Renditen und Reihenfolge)',
  boersenplatz_kennzeichen: 'Kennzeichen „Börsenplatz-Abweichung“ genau bei den auffälligen Vergleichen',
  gruppe_b_eigene_vergleichsmenge: 'Gruppe B: eigene Vergleichsmenge (Ø Umsatz ≥ Schwelle), alle elf Gewichtungen, Sortierregeln',
  umschichtung_regel_eingehalten: 'Umschichtungs-Regel: alle Varianten gerechnet, Regel eingehalten',
};

export function StatusView() {
  const { manifest, status, index, activeId, switchSnapshot, offline, crypto, isDemo } = useApp();
  if (!manifest) return null;
  const run = status?.last_run ?? null;
  const age = f.ageHours(status?.last_successful_check_utc ?? null);
  const stale = age !== null && status ? age > (status.heartbeat_max_age_hours ?? 30) : false;
  const cov = manifest.coverage;
  const levels = Object.entries(cov.instrument_level).sort((a, b) => Number(a[0]) - Number(b[0]));
  const levelSum = levels.reduce((n, [, c]) => n + c, 0);
  const warnings = Object.entries(cov.warnings ?? {}).sort((a, b) => Number(a[0]) - Number(b[0]));
  const comp = manifest.completeness;

  return (
    <div className="view">
      <section className="section" aria-labelledby="lauf">
        <SectionTitle id="lauf">Täglicher Serverlauf</SectionTitle>
        <p className="section-note">
          Die Berechnung läuft auf dem Server, auch wenn die App geschlossen ist: täglich um {status?.schedule.uhrzeit ?? '07:00'} Uhr ({status?.schedule.zeitzone ?? 'Europe/Berlin'}), mit Wiederholungen nach {(status?.schedule.wiederholungen_minuten ?? [15, 45, 120]).join(', ')} Minuten, falls Kurse noch fehlen.
        </p>
        {stale ? (
          <Notice tone="warn" title="Keine aktuelle Prüfung">
            <p>Der Lauf hat sich seit {f.relativeAge(status?.last_successful_check_utc)} nicht erfolgreich gemeldet.</p>
          </Notice>
        ) : null}
        <KeyValues
          items={[
            ['Letzte erfolgreiche Prüfung', f.berlinTime(status?.last_successful_check_utc)],
            ['Letzter Lauf', run ? `${f.runStatus(run.status)}${run.attempt > 1 ? `, Versuch ${run.attempt}` : ''}` : 'noch keiner'],
            ['Meldung', run?.message ?? '–'],
            ['Gestartet', run ? `${f.berlinTime(run.started_at_utc)}${run.planned_start_utc ? ` (geplant ${f.berlinTime(run.planned_start_utc)})` : ' (manuell)'}` : '–'],
            ['Beendet', f.berlinTime(run?.finished_at_utc)],
            ['Letzter Börsenschluss', f.isoDate(status?.last_price_session)],
            ['Verbindung', offline ? 'offline – gespeicherter Stand' : 'online'],
            ['App-Version', status?.software_version ?? '–'],
          ]}
        />
        <div className="toolbar">
          <a className="btn btn-primary" href="#/aktualisieren">
            Jetzt aktualisieren
          </a>
        </div>
      </section>

      <section className="section" aria-labelledby="stand">
        <SectionTitle id="stand">Angezeigter Datenstand</SectionTitle>
        {isDemo ? (
          <Notice tone="demo" title="DEMO – synthetische Testdaten">
            <p>Dieser Stand wurde aus erfundenen Kursen erzeugt, um die App ohne Datenanbieter zu prüfen.</p>
          </Notice>
        ) : null}
        <KeyValues
          items={[
            ['Kursstichtag', f.dayWithWeekday(manifest.cutoff_day)],
            ['Berechnet', f.berlinTime(manifest.computed_at_utc)],
            ['Veröffentlicht', f.berlinTime(manifest.published_at_utc)],
            [
              'Vollständigkeit',
              (() => {
                const c = cutoffCoverage(manifest);
                const base = `${f.integer(c.delivered)} von ${f.integer(c.markets)} Börsen mit Stichtagskursen, ${f.integer(c.present)} von ${f.integer(c.expected)} Aktien mit Schlusskurs am Stichtag`;
                return manifest.completeness.status === 'vollstaendig' ? `vollständig: ${base}` : `Teilstand: ${base}; ohne Stichtagskurse: ${missingMarketNames(manifest).join(', ') || '–'}`;
              })(),
            ],
            ['Snapshot', manifest.snapshot_id],
            ['Ersetzt', manifest.supersedes ?? '–'],
            ['Methode', `${manifest.versions.method ?? ''}, Kennzahlen ${manifest.versions.metrics ?? ''}, Ranking ${manifest.versions.ranking ?? ''}, Häufigkeit ${manifest.versions.frequency ?? ''}${manifest.versions.turnover ? `, Umsatz ${manifest.versions.turnover}` : ''}${manifest.versions.groups ? `, Gruppen ${manifest.versions.groups}` : ''}`],
            ['Ausgangsmodell', manifest.versions.reference_model ? `${manifest.versions.reference_model} (dokumentierte Regeln übernommen; Reproduktion des historischen Prüffalls offen)` : '–'],
            ['Software', manifest.versions.software ?? '–'],
            ['Kursquelle', manifest.provider.prices],
            ['Lizenzhinweis', manifest.provider.license_note],
            ['Live- oder Intradaydaten', manifest.provider.live_data || manifest.provider.intraday ? 'eingerichtet' : 'nicht eingerichtet – nur Tagesschlusskurse'],
            ['Verschlüsselung', crypto?.enabled ? 'Daten verschlüsselt (Zugangsschlüssel auf diesem Gerät)' : 'unverschlüsselt veröffentlicht'],
          ]}
        />
        {comp.per_market ? (
          <Disclosure summary="Schlusskurse je Börse am Stichtag">
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Börsenkalender</th>
                    <th scope="col" className="n">
                      erwartet
                    </th>
                    <th scope="col" className="n">
                      vorhanden
                    </th>
                    <th scope="col" className="n">
                      Börse geschlossen
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(comp.per_market).map(([key, value]) => (
                    <tr key={key}>
                      <td>{key}</td>
                      <td className="n">{f.integer(value.expected)}</td>
                      <td className="n">{f.integer(value.present)}</td>
                      <td className="n">{f.integer(value.closed)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Disclosure>
        ) : null}
      </section>

      {manifest.turnover ? (
        <section className="section" aria-labelledby="umsatz">
          <SectionTitle id="umsatz">Ø Tagesumsatz und Wechselkurse</SectionTitle>
          <KeyValues
            items={[
              ['Berechnung', manifest.turnover.berechnung],
              ['Aufnahme in das Ranking mit Umsatzfilter', `Ø mindestens ${f.money(manifest.turnover.schwelle_usd, 'USD')} über ${manifest.turnover.sitzungen} Sitzungen, davon mindestens ${manifest.turnover.min_sitzungen_mit_umsatz} mit Umsatz`],
              ['Ø Umsatz bestimmt', `${f.integer(manifest.turnover.anzahl.status.ok ?? 0)} Aktien, davon ${f.integer(manifest.turnover.anzahl.aufgenommen)} aufgenommen und ${f.integer(manifest.turnover.anzahl.sehr_niedrig)} mit sehr niedrigem Umsatz (unter ${f.money(manifest.turnover.sehr_niedrig_usd, 'USD')})`],
              [
                'Nicht bestimmbar',
                Object.entries(manifest.turnover.anzahl.status)
                  .filter(([key]) => key !== 'ok')
                  .map(([key, n]) => `${manifest.codes.turnover_status?.[key]?.kurz ?? key}: ${f.integer(n)}`)
                  .join('; ') || 'keine',
              ],
              ['Wechselkursquelle', manifest.turnover.wechselkurse.quelle ?? 'keine – nur USD-Notierungen bestimmbar'],
              ['Kurstage', manifest.turnover.wechselkurse.letzter_kurstag ? `${f.isoDate(manifest.turnover.wechselkurse.erster_kurstag)} bis ${f.isoDate(manifest.turnover.wechselkurse.letzter_kurstag)} (je Sitzung der Kurs des Tages oder der letzte davor, höchstens ${manifest.turnover.wechselkurse.max_alter_tage} Tage alt)` : '–'],
              ['Abgerufen', f.berlinTime(manifest.turnover.wechselkurse.abgerufen_utc)],
              ['Währungen', manifest.turnover.wechselkurse.waehrungen.join(', ') || '–'],
              ['Hinweis', manifest.turnover.wechselkurse.hinweis],
            ]}
          />
          {manifest.turnover.wechselkurse.url ? (
            <p className="section-note">
              Quelle: <a href={manifest.turnover.wechselkurse.url}>{manifest.turnover.wechselkurse.url}</a>
            </p>
          ) : null}
        </section>
      ) : null}

      {manifest.venue_check ? (
        <section className="section" aria-labelledby="boersenplatz">
          <SectionTitle id="boersenplatz">Abgleich mit einem zweiten Börsenplatz</SectionTitle>
          <KeyValues
            items={[
              ['Geprüft', manifest.venue_check.beschreibung],
              [
                'Umfang',
                `${f.integer(manifest.venue_check.anzahl.aktien.geprueft ?? 0)} von ${f.integer(manifest.venue_check.anzahl.kandidaten)} Aktien unter den ersten ${manifest.venue_check.plaetze} Plätzen beider Rendite-Ranglisten`,
              ],
              [
                'Auffällig',
                `${f.integer(manifest.venue_check.anzahl.auffaellige_aktien)} Aktien in ${f.integer(manifest.venue_check.anzahl.aktie_zeitraum.abweichung ?? 0)} Zeiträumen (Abweichung über ${Math.round(manifest.venue_check.schwelle_wertentwicklung * 100)} % bei Wertentwicklung oder Endkurs)`,
              ],
              [
                'Verglichene Zeiträume',
                (() => {
                  const pairs = manifest.venue_check.anzahl.aktie_zeitraum;
                  const compared = (pairs.ok ?? 0) + (pairs.abweichung ?? 0);
                  const total = Object.values(pairs).reduce((sum, value) => sum + value, 0);
                  const without = Object.entries(pairs)
                    .filter(([key, value]) => key !== 'ok' && key !== 'abweichung' && value > 0)
                    .map(([key, value]) => `${manifest.codes.venue_pair_status?.[key]?.kurz ?? key}: ${f.integer(value)}`);
                  return `${f.integer(compared)} von ${f.integer(total)}${without.length ? ` (${without.join('; ')})` : ''}`;
                })(),
              ],
              [
                'Nicht verglichen',
                Object.entries(manifest.venue_check.anzahl.aktien)
                  .filter(([key]) => key !== 'geprueft')
                  .map(([key, n]) => `${manifest.codes.venue_status?.[key]?.kurz ?? key}: ${f.integer(n)}`)
                  .join('; ') || 'keine',
              ],
              ['Bevorzugte Börsenplätze', `${manifest.venue_check.bevorzugt.map(marketName).join(', ')}, danach weitere (ohne OTC-Märkte)`],
              ['Vergleichskurs', venueDayRule(manifest.venue_check)],
              ...(manifest.venue_check.hinweis ? ([['Hinweis', manifest.venue_check.hinweis]] as [string, string][]) : []),
            ]}
          />
        </section>
      ) : null}

      <section className="section" aria-labelledby="universum">
        <SectionTitle id="universum">TR-Aktienuniversum</SectionTitle>
        <KeyValues
          items={[
            ['Quelle', manifest.universe.source_url],
            ['Abgerufen', f.berlinTime(manifest.universe.retrieved_at_utc)],
            ['Stand laut Server', manifest.universe.http_last_modified ?? '–'],
            ['PDF erstellt', manifest.universe.pdf_creation_date ?? '–'],
            ['ISINs im Aktienabschnitt', f.integer(manifest.universe.isin_count)],
            ['Nachweis', manifest.universe.nachweis],
          ]}
        />
      </section>

      <section className="section" aria-labelledby="bilanz">
        <SectionTitle id="bilanz">Abdeckungsbilanz</SectionTitle>
        <p className="section-note">
          Jede Aktie hat genau einen Hauptstatus. Summe: {f.integer(levelSum)} von {f.integer(cov.universe_total)} {levelSum === cov.universe_total ? '(stimmt)' : '(Abweichung!)'}.
        </p>
        <div className="table-wrap">
          <table className="table">
            <tbody>
              {levels.map(([code, count]) => (
                <tr key={code}>
                  <td>{Number(code) === READY_LEVEL ? 'Schlusskurs am Stichtag vorhanden' : statusInfo(manifest, Number(code)).kurz}</td>
                  <td className="n">{f.integer(count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {warnings.length ? (
          <Disclosure summary="Zusätzliche Hinweise (Mehrfachnennung möglich)">
            <div className="table-wrap">
              <table className="table">
                <tbody>
                  {warnings.map(([bit, count]) => (
                    <tr key={bit}>
                      <td>{manifest.codes.instrument_warnings[bit]?.text ?? `Hinweis ${bit}`}</td>
                      <td className="n">{f.integer(count)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Disclosure>
        ) : null}
      </section>

      {manifest.method_comparison ? (
        <section className="section" aria-labelledby="methodenwechsel">
          <SectionTitle id="methodenwechsel">Methodenwechsel {manifest.method_comparison.vorher} → {manifest.method_comparison.jetzt}</SectionTitle>
          <p className="section-note">
            Dieselben Kurse nach den Regeln beider Versionen: {f.integer(manifest.method_comparison.paare.neu_bewertet)} Aktie-Zeitraum-Paare werden neu bewertet,{' '}
            {f.integer(manifest.method_comparison.paare.nicht_mehr_bewertet)} nicht mehr; {f.integer(manifest.method_comparison.ranglisten.spitze_geaendert)} von{' '}
            {f.integer(manifest.method_comparison.ranglisten.verglichen)} Ranglisten haben einen anderen Spitzenreiter.{' '}
            <a href="#/methodik">Regeln und Beispiele</a>
          </p>
        </section>
      ) : null}

      <section className="section" aria-labelledby="pruefungen">
        <SectionTitle id="pruefungen">Prüfungen vor der Veröffentlichung</SectionTitle>
        <ul className="checklist">
          {manifest.checks.map((check) => (
            <li key={check.name}>
              <span className={check.passed ? 'check-ok' : 'check-fail'} aria-hidden="true">
                {check.passed ? '✓' : '✗'}
              </span>
              <span>
                {CHECK_LABELS[check.name] ?? check.name}
                <span className="visually-hidden">{check.passed ? ': bestanden' : ': nicht bestanden'}</span>
                {check.detail ? <span className="muted">. {check.detail}</span> : null}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {!PREVIEW ? (
        <section className="section no-print" aria-labelledby="export-meta">
          <SectionTitle id="export-meta">Berechnungsmetadaten</SectionTitle>
          <p className="section-note">Datenstand, Versionen, Methodik-Einstellungen, Abdeckung, Prüfungen und Methodenvergleich dieses Stands – ohne Kurse und ohne Schlüssel.</p>
          <div className="toolbar">
            <button
              type="button"
              className="btn btn-quiet"
              onClick={() =>
                downloadText(
                  safeFilename(`berechnungsmetadaten_${manifest.snapshot_id}.json`),
                  JSON.stringify({ format: 'tr-metadaten/1', exportiert_utc: new Date().toISOString(), manifest }, null, 2),
                  'application/json;charset=utf-8',
                )
              }
            >
              <IconDownload /> Als JSON
            </button>
            <button type="button" className="btn btn-quiet" onClick={() => window.print()}>
              Zusammenfassung drucken
            </button>
          </div>
        </section>
      ) : null}

      <section className="section" aria-labelledby="historie">
        <SectionTitle id="historie">Frühere Stände</SectionTitle>
        <p className="section-note">
          Ein älterer Stand bleibt unverändert lesbar. Alle Ansichten zeigen immer genau einen Stand. Ranglisten verschiedener Stände sind nur bei gleicher Methodenversion direkt vergleichbar; bei
          anderer Methode steht „eingeschränkt vergleichbar“.
        </p>
        <ul className="rows">
          {index.map((s) => {
            const method = s.versions?.method ?? null;
            const shown = manifest.versions.method ?? null;
            const limited = s.snapshot_id !== activeId && method !== shown;
            return (
              <li key={s.snapshot_id} className="row row-nr">
                <div className="row-main">
                  <span className="row-name">
                    Kursstand {f.isoDate(s.cutoff_session_date)}
                    {s.snapshot_id === activeId ? ' (angezeigt)' : ''}
                  </span>
                  <span className="row-alt">
                    {s.completeness === 'vollstaendig' ? 'vollständig' : 'Teilstand'}, berechnet {f.berlinTime(s.computed_at_utc)}, {f.integer(s.return_eligible_30)} Aktien im 30-Tage-Fenster
                    vergleichbar. Methode {method ?? 'unbekannt'}.
                    {s.data_mode === 'demo' ? ' DEMO.' : ''}
                  </span>
                  {limited ? <span className="badge badge-warn">eingeschränkt vergleichbar: andere Methodenversion als der angezeigte Stand</span> : null}
                </div>
                <div className="row-figs">
                  {s.snapshot_id !== activeId ? (
                    <button type="button" className="btn btn-quiet" onClick={() => switchSnapshot(s.snapshot_id === status?.latest_snapshot_id ? null : s.snapshot_id)}>
                      Anzeigen
                    </button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}

