import { Disclosure, KeyValues, Notice, SectionTitle } from '../components/ui';
import { READY_LEVEL, statusInfo } from '../lib/codes';
import * as f from '../lib/format';
import { useApp } from '../state/AppState';

const RUN_STATUS: Record<string, string> = {
  geplant: 'geplant',
  laeuft: 'läuft',
  wartet_auf_provider: 'wartet auf Kursdaten – Wiederholung geplant',
  teilweise_berechnet: 'teilweise berechnet',
  vollstaendig_berechnet: 'berechnet, Prüfung läuft',
  geprueft: 'geprüft',
  veroeffentlicht: 'veröffentlicht',
  keine_neuen_daten: 'geprüft – kein neuer Börsenschluss',
  fehlgeschlagen: 'fehlgeschlagen – letzter Stand bleibt sichtbar',
  abgebrochen: 'abgebrochen',
};

const CHECK_LABELS: Record<string, string> = {
  fenster_1_bis_90: 'Alle 90 Zeiträume berechnet',
  elf_gewichtungen: 'Elf Gewichtungen 0/100 bis 100/0',
  abdeckung_summe_gleich_universum: 'Abdeckungsbilanz ergibt das Universum',
  u_teilmenge_von_v: 'Gleichmäßig gestiegene Aktien sind Teil der Renditeliste',
  ranglistengroessen: 'Ranglistengrößen stimmen',
  eindeutige_plaetze: 'Jeder Platz eindeutig',
  sortierregeln: 'Sortierregeln eingehalten',
  scores_0_bis_100: 'Scores zwischen 0 und 100',
  aufwaertsbedingungen_und_endliche_werte: 'Aufwärtsbedingungen und endliche Werte',
  renditesieger_90_zeilen: 'Renditesiegerliste mit 90 Zeilen',
  haeufigkeit_invarianten: 'Häufigkeitszählung widerspruchsfrei',
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
          Die Berechnung läuft auf dem Server, auch wenn die App geschlossen ist: täglich um {status?.schedule.uhrzeit ?? '06:00'} Uhr ({status?.schedule.zeitzone ?? 'Europe/Berlin'}), mit Wiederholungen nach {(status?.schedule.wiederholungen_minuten ?? [15, 45, 120]).join(', ')} Minuten, falls Kurse noch fehlen.
        </p>
        {stale ? (
          <Notice tone="warn" title="Keine aktuelle Prüfung">
            <p>Der Lauf hat sich seit {f.relativeAge(status?.last_successful_check_utc)} nicht erfolgreich gemeldet.</p>
          </Notice>
        ) : null}
        <KeyValues
          items={[
            ['Letzte erfolgreiche Prüfung', f.berlinTime(status?.last_successful_check_utc)],
            ['Letzter Lauf', run ? `${RUN_STATUS[run.status] ?? run.status}${run.attempt > 1 ? `, Versuch ${run.attempt}` : ''}` : 'noch keiner'],
            ['Meldung', run?.message ?? '–'],
            ['Gestartet', run ? `${f.berlinTime(run.started_at_utc)}${run.planned_start_utc ? ` (geplant ${f.berlinTime(run.planned_start_utc)})` : ' (manuell)'}` : '–'],
            ['Beendet', f.berlinTime(run?.finished_at_utc)],
            ['Letzter Börsenschluss', f.isoDate(status?.last_price_session)],
            ['Verbindung', offline ? 'offline – gespeicherter Stand' : 'online'],
            ['App-Version', status?.software_version ?? '–'],
          ]}
        />
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
            ['Vollständigkeit', manifest.completeness.status === 'vollstaendig' ? `vollständig für das benannte Universum (${f.plainPct(100 * manifest.completeness.share, 1)} der erwarteten Schlusskurse)` : `Teilstand (${f.plainPct(100 * manifest.completeness.share, 1)}); fehlende Märkte: ${manifest.completeness.missing_markets.join(', ') || '–'}`],
            ['Snapshot', manifest.snapshot_id],
            ['Ersetzt', manifest.supersedes ?? '–'],
            ['Methode', `${manifest.versions.method ?? ''}, Kennzahlen ${manifest.versions.metrics ?? ''}, Ranking ${manifest.versions.ranking ?? ''}, Häufigkeit ${manifest.versions.frequency ?? ''}`],
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

      <section className="section" aria-labelledby="historie">
        <SectionTitle id="historie">Frühere Stände</SectionTitle>
        <p className="section-note">Ein älterer Stand bleibt unverändert lesbar. Alle Ansichten zeigen immer genau einen Stand.</p>
        <ul className="rows">
          {index.map((s) => (
            <li key={s.snapshot_id} className="row row-nr">
              <div className="row-main">
                <span className="row-name">
                  Kursstand {f.isoDate(s.cutoff_session_date)}
                  {s.snapshot_id === activeId ? ' (angezeigt)' : ''}
                </span>
                <span className="row-alt">
                  {s.completeness === 'vollstaendig' ? 'vollständig' : 'Teilstand'}, berechnet {f.berlinTime(s.computed_at_utc)}, {f.integer(s.return_eligible_30)} Aktien im 30-Tage-Fenster vergleichbar.
                  {s.data_mode === 'demo' ? ' DEMO.' : ''}
                </span>
              </div>
              <div className="row-figs">
                {s.snapshot_id !== activeId ? (
                  <button type="button" className="btn btn-quiet" onClick={() => switchSnapshot(s.snapshot_id === status?.latest_snapshot_id ? null : s.snapshot_id)}>
                    Anzeigen
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

