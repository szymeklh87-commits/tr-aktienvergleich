/* Musterbereiche unter „Potenzial“ (Gesamtauftrag Abschnitt 26, Auftrag vom 31.10.2026 Abschnitte 8 und 16): Screening A
 * Vor-Ausbruch, C Seitwärtsbasis, B positiver Volumensprung (Tag) – Top 10, alle Treffer, Zustände, nicht prüfbare Aktien mit
 * Gründen, Nachrechnung früherer Signale, Journal der Zustandswechsel und die Regel dahinter. Nur Anzeige des Laufs. */

import { Explain } from '../components/explain';
import { InstrumentRow } from '../components/rows';
import { Disclosure, EmptyState, ErrorNote, KeyValues, Loading, Notice, Pager, Segmented } from '../components/ui';
import { linkMuster } from '../lib/analyseregel';
import * as f from '../lib/format';
import { unitOf } from '../lib/instruments';
import { AKTIV, auswahl, MODULE, nichtPruefbarSumme, regelText, ZUSTAENDE, type Modul, type MusterStand, type MusterTreffer, type Sortierung } from '../lib/muster';
import { buildHash, updateParams, type Route } from '../lib/router';
import { useAsync } from '../lib/useAsync';
import { useApp } from '../state/AppState';

const PAGE = 25;

function parseModul(text: string | null): Modul {
  return text === 'B' || text === 'C' ? text : 'A';
}

export function MusterView({ route }: { route: Route }) {
  const { musterClient, status } = useApp();
  const state = useAsync(musterClient ? () => musterClient.stand() : null, [musterClient]);
  if (!status?.muster) {
    return (
      <div className="view">
        <EmptyState title="Noch kein Musterstand veröffentlicht">
          <p>Vor-Ausbruch, Seitwärtsbasis und Volumensprung werden im täglichen Lauf aus den Tageskerzen berechnet. Sobald ein Stand veröffentlicht ist, stehen sie hier.</p>
        </EmptyState>
      </div>
    );
  }
  if (state.error && !state.data) return <ErrorNote error={state.error} />;
  if (!state.data) return <Loading label="Musterstand wird geladen" />;
  return <MusterInhalt stand={state.data} route={route} />;
}

function MusterInhalt({ stand, route }: { stand: MusterStand; route: Route }) {
  const modul = parseModul(route.params.get('modul'));
  const m = stand.module[modul];
  const filterParam = route.params.get('z');
  const filter = filterParam && ZUSTAENDE[modul].includes(filterParam) ? filterParam : 'aktiv';
  const sort: Sortierung = route.params.get('sort') === 'rendite' ? 'rendite' : 'score';
  const rows = auswahl(m, modul, filter, sort);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const page = Math.min(pages, Math.max(1, Number(route.params.get('seite') ?? 1) || 1));
  const set = (changes: Record<string, string | number | null>) => updateParams(route, { ...changes, seite: null });
  const aktivZahl = AKTIV[modul].reduce((s, z) => s + (m.zustaende[z] ?? 0), 0);
  const ohne = nichtPruefbarSumme(m);
  return (
    <div className="view muster-view">
      <header className="view-head">
        <h2 className="view-title">Muster und Volumen</h2>
        <Explain
          kinds={['rueckblick']}
          sees={<>Aktien in einer ruhigen Basis kurz vor dem Widerstand, Übergänge aus der Seitwärtsbasis und Tage mit sehr hohem Volumen bei steigendem Kurs – aus den Tageskerzen nach Börsenschluss.</>}
          todo={<>Bereich wählen, dann eine Aktie antippen. Ein Musterfund ist keine Gewinnwahrscheinlichkeit und keine Kaufempfehlung.</>}
        />
      </header>
      <Notice tone={stand.modus === 'DEMO' ? 'demo' : 'info'} compact>
        {stand.modus === 'DEMO' ? <strong>DEMO – synthetische Kurse. </strong> : null}
        Tagesdaten vom {f.isoDate(stand.datentag)} nach Börsenschluss · Regelversion {stand.version} (zu testende Ausgangsannahmen) · keine Intraday-Beobachtung
      </Notice>
      <Segmented<Modul>
        label="Bereich"
        hideLabel
        value={modul}
        onChange={(v) => updateParams(route, { modul: v === 'A' ? null : v, z: null, seite: null })}
        options={MODULE.map((x) => ({ value: x.value, label: `${x.label} (${f.integer(AKTIV[x.value].reduce((s, z) => s + (stand.module[x.value].zustaende[z] ?? 0), 0))})` }))}
      />
      <p className="section-note">
        {m.name}: {f.integer(m.geprueft)} von {f.integer(stand.universum)} Aktien geprüft, {f.integer(aktivZahl)} aktuell im Muster
        {ohne ? `, ${f.integer(ohne)} nicht prüfbar (Gründe unten)` : ''}.
      </p>
      {modul === 'B' && m.intraday ? (
        <Notice tone="info" compact>
          <p>
            <strong>5-/15-Minuten-Volumen: {m.intraday.status}.</strong> {m.intraday.grund} Die Zeitpunkte 15:30, 15:45 und 16:00 Uhr (US-Eröffnung, mit
            Zeitumstellung) bleiben ohne passende Kurse „nicht prüfbar“.
          </p>
        </Notice>
      ) : null}
      <div className="toolbar no-print">
        <Segmented
          label="Zustand"
          value={filter}
          onChange={(v) => set({ z: v === 'aktiv' ? null : v })}
          options={[
            { value: 'aktiv', label: `aktiv (${f.integer(aktivZahl)})` },
            ...(modul === 'B' ? [] : ZUSTAENDE[modul]).map((z) => ({ value: z, label: `${stand.zustaende[z] ?? z} (${f.integer(m.zustaende[z] ?? 0)})` })),
          ]}
        />
        <Segmented<Sortierung>
          label="Sortierung"
          value={sort}
          onChange={(v) => set({ sort: v === 'score' ? null : v })}
          options={[
            { value: 'score', label: modul === 'B' ? 'Volumenfaktor' : 'Muster-Score' },
            { value: 'rendite', label: 'Rendite 20 Sitzungen' },
          ]}
        />
        <a className="btn btn-quiet" href={linkMuster({ modul, zustaende: filter === 'aktiv' ? AKTIV[modul] : [filter] })}>
          Als Robo-Regel verwenden
        </a>
      </div>
      {sort === 'rendite' ? <p className="section-note">Sortiert nach der bisherigen Rendite der letzten 20 Sitzungen – eigene Ansicht, nicht mit dem Muster-Score vermischt.</p> : null}
      {rows.length ? (
        <ol className="rows" aria-label={`${m.name}: ${filter === 'aktiv' ? 'aktive Muster' : stand.zustaende[filter]}`} start={(page - 1) * PAGE + 1}>
          {rows.slice((page - 1) * PAGE, page * PAGE).map((t, i) => (
            <MusterZeile key={t.isin} t={t} rank={(page - 1) * PAGE + i + 1} stand={stand} modul={modul} />
          ))}
        </ol>
      ) : (
        <EmptyState title="Keine Aktie in diesem Zustand">Am {f.isoDate(stand.datentag)} erfüllt keine geprüfte Aktie diese Bedingungen.</EmptyState>
      )}
      <Pager page={page} pages={pages} onChange={(p) => updateParams(route, { seite: p })} label="Seiten der Trefferliste" />
      <Disclosure summary={`Nicht prüfbar (${f.integer(ohne)})`}>
        {Object.keys(m.nicht_pruefbar).length ? (
          <KeyValues items={Object.entries(m.nicht_pruefbar).map(([g, isins]) => [stand.gruende[g] ?? g, <NamenListe key={g} isins={isins} />])} />
        ) : (
          <p className="section-note">Alle Aktien mit Kursen waren prüfbar.</p>
        )}
      </Disclosure>
      <Nachrechnung stand={stand} modul={modul} />
      <Disclosure summary="Journal der Zustandswechsel">
        <Journal stand={stand} modul={modul} />
      </Disclosure>
      <Disclosure summary="Die Regel dahinter">
        <ul className="plain-list section-note">
          {regelText(stand, modul).map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
        <p className="section-note">
          Sortierung: fester Muster-Score 0–100 (35 % Nähe zum Widerstand, 25 % Enge der Basis, 25 % Volumen, 15 % Flachheit), danach ISIN. Parameter sind
          zu testende Ausgangsannahmen und werden nicht nach Fehlsignalen rückwirkend angepasst.
        </p>
      </Disclosure>
    </div>
  );
}

function MusterZeile({ t, rank, stand, modul }: { t: MusterTreffer; rank: number; stand: MusterStand; modul: Modul }) {
  const { isinIndex, instruments } = useApp();
  const idx = isinIndex.get(t.isin);
  const badges = (
    <>
      <span className={`badge badge-wrap${t.zustand === 'ungueltig' || t.zustand === 'zurueck' || t.zustand === 'abgelaufen' ? ' badge-warn' : ''}`}>{stand.zustaende[t.zustand] ?? t.zustand}</span>
      {t.ueberdehnt ? <span className="badge badge-warn badge-wrap">überdehnt</span> : null}
      {t.wenig_umsatz ? <span className="badge badge-warn badge-wrap">wenig Liquidität</span> : null}
      {t.volumen_fehlt ? <span className="badge badge-wrap">ohne Volumen</span> : null}
    </>
  );
  const unit = idx !== undefined && instruments ? unitOf(instruments, idx) : null;
  const details =
    modul === 'B' ? (
      <p className="section-note">
        Tagesvolumen {t.volumenfaktor === null ? '–' : `${t.volumenfaktor.toLocaleString('de-DE', { maximumFractionDigits: 1 })} ×`} Vergleichsvolumen · Rendite 20 Sitzungen{' '}
        {f.signedPctValue(t.rendite_n_pct, 1)}
      </p>
    ) : (
      <p className="section-note">
        Basis {f.isoDate(t.basis_von)} – {f.isoDate(t.basis_bis)}: Bandbreite {f.plainPct(t.bandbreite_pct ?? null, 1)} ({(t.bandbreite_atr ?? 0).toLocaleString('de-DE', { maximumFractionDigits: 1 })} ATR), Drift{' '}
        {f.signedPctValue(t.drift_pct ?? null, 1)} · Widerstand {f.price(t.widerstand ?? null, unit)}, Abstand {f.signedPctValue(t.abstand_pct ?? null, 1)} · Volumen{' '}
        {t.volumenfaktor === null ? 'unbekannt' : `${t.volumenfaktor.toLocaleString('de-DE', { maximumFractionDigits: 1 })} ×`}
        {t.vorlauf === 'aufwaertstrend' ? ' · Konsolidierung im Aufwärtstrend' : t.vorlauf === 'bodenbildung' ? ' · Bodenbildungsversuch nach Rückgang' : ''}
      </p>
    );
  const figs = (
    <>
      <strong className="row-fig">{modul === 'B' ? `${(t.volumenfaktor ?? 0).toLocaleString('de-DE', { maximumFractionDigits: 1 })} ×` : f.score(t.score)}</strong>
      <span className="row-fig-sub">{modul === 'B' ? 'Volumen' : 'Muster-Score'}</span>
    </>
  );
  if (idx === undefined) {
    return (
      <li className="row">
        <div className="row-main">
          <span className="row-name">{t.isin}</span>
          <div className="row-meta">{badges}</div>
        </div>
        <div className="row-figs">{figs}</div>
        <div className="row-extra row-wide">{details}</div>
      </li>
    );
  }
  return (
    <InstrumentRow idx={idx} rank={rank} href={buildHash(`/aktie/${t.isin}`, { h: 30 })} meta={badges} figs={figs}>
      {details}
    </InstrumentRow>
  );
}

function NamenListe({ isins }: { isins: string[] }) {
  const { isinIndex, instruments } = useApp();
  const names = isins.slice(0, 30).map((isin) => {
    const idx = isinIndex.get(isin);
    return idx !== undefined && instruments ? instruments.name[idx] : isin;
  });
  return (
    <>
      {f.integer(isins.length)} {isins.length === 1 ? 'Aktie' : 'Aktien'}
      <br />
      <span className="muted">
        {names.join(', ')}
        {isins.length > 30 ? ` und ${f.integer(isins.length - 30)} weitere` : ''}
      </span>
    </>
  );
}

function Nachrechnung({ stand, modul }: { stand: MusterStand; modul: Modul }) {
  const a = stand.auswertung[modul];
  const ereignis = modul === 'B' ? 'Volumensprünge' : 'bestätigte Übergänge';
  return (
    <Disclosure summary="Nachrechnung früherer Signale">
      <p className="section-note">{stand.auswertung.hinweis}</p>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Nach</th>
              <th className="n">{ereignis}</th>
              <th className="n">Ø Rendite</th>
              <th className="n">Vergleich Ø</th>
              <th className="n">positiv</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(a.horizonte).map(([h, x]) => (
              <tr key={h}>
                <td>{h} Sitzungen</td>
                <td className="n">{f.integer(x.n)}</td>
                <td className="n">{f.signedPctValue(x.mittel_pct, 2)}</td>
                <td className="n">{f.signedPctValue(x.vergleich_mittel_pct, 2)}</td>
                <td className="n">{f.plainPct(x.anteil_positiv_pct, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <KeyValues
        items={[
          ['Nachgerechnete Stichtage', f.integer(a.stichtage)],
          ...(a.folgequote_pct !== undefined
            ? ([['Kandidaten mit Übergang', a.folgequote_pct === null ? 'keine abgeschlossene Frist' : `${f.plainPct(a.folgequote_pct, 1)} von ${f.integer(a.kandidaten_abgeschlossen ?? 0)}`]] as [string, string][])
            : []),
          ...(a.fehlausbrueche_pct !== undefined
            ? ([['Fehlausbrüche (zurück unter den Widerstand)', a.fehlausbrueche_pct === null ? 'keine abgeschlossene Frist' : `${f.plainPct(a.fehlausbrueche_pct, 1)} von ${f.integer(a.uebergaenge_abgeschlossen ?? 0)}`]] as [string, string][])
            : []),
          ['Zustandswechsel im Zeitraum', Object.entries(a.signale).map(([z, n]) => `${stand.zustaende[z] ?? z}: ${f.integer(n)}`).join(' · ') || '–'],
        ]}
      />
    </Disclosure>
  );
}

function Journal({ stand, modul }: { stand: MusterStand; modul: Modul }) {
  const { isinIndex, instruments } = useApp();
  const events = (stand.journal ?? []).filter((e) => e.modul === modul).slice(0, 60);
  if (!events.length) return <p className="section-note">Noch keine Zustandswechsel im Journal.</p>;
  return (
    <ul className="plain-list">
      {events.map((e) => {
        const idx = isinIndex.get(e.isin);
        return (
          <li key={`${e.id}|${e.zustand}|${e.datum}`}>
            {f.isoDate(e.datum)}: {idx !== undefined && instruments ? instruments.name[idx] : e.isin} – {stand.zustaende[e.zustand] ?? e.zustand}
            <span className="muted"> · Muster {e.id}</span>
          </li>
        );
      })}
    </ul>
  );
}
