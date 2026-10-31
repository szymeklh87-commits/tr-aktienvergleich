/* Autopilot – Spielgeld (Gesamtauftrag, Abschnitte 20, 29, 31): Pilotdepot mit Robo-Kern und aktiven Strategien,
 * Forschungsdepots je Regel, Vergleichsdepots, Positionen mit Stops, Orders, Journal mit Begründung, Regeln und Chronik.
 * Nur Anzeige eines verschlüsselten Standes aus dem täglichen Lauf – die App führt keine Orders aus. */

import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { CompareChart, type CompareLine } from '../components/charts';
import { Disclosure, EmptyState, ErrorNote, KeyValues, Loading, Notice, SectionTitle, Segmented } from '../components/ui';
import * as f from '../lib/format';
import {
  abstandPp,
  ART_TEXT,
  benchmark,
  bedingungAusPfad,
  ERGEBNIS_TEXT,
  gruppieren,
  journalNachTag,
  kernReferenz,
  ORDER_STATUS,
  regelZusammenfassung,
  sortiereDepots,
  STUFE_TEXT,
  type DepotGruppe,
  type PilotDepot,
  type PilotDepotKopf,
  type PilotEntscheidung,
  type PilotJournal,
  type PilotOrder,
  type PilotStand,
  type Regel,
  type Sortierung,
} from '../lib/pilot';
import { navigate, type Route } from '../lib/router';
import { useAsync } from '../lib/useAsync';
import { useApp } from '../state/AppState';
import { DepotBericht } from './PilotBericht';
import { PilotEditor } from './PilotEditor';
import { PilotEinrichtung } from './PilotEinrichtung';
import { GesendeteListe, PilotSenden } from '../components/pilotsenden';

const pctPlain = (v: number | null | undefined, digits = 2) => f.signedPctValue(v, digits);

function ModusBadge({ d }: { d: PilotDepotKopf }) {
  return (
    <>
      {d.modus === 'DEMO' ? <span className="badge badge-warn badge-wrap">DEMO · synthetische Kurse</span> : <span className="badge badge-wrap">Spielgeld · PAPER</span>}{' '}
      {d.historisch ? <span className="badge badge-warn badge-wrap">historische Simulation · nachgerechnet, kein Vorwärtstest</span> : null}
      {d.status === 'pausiert' ? <span className="badge badge-warn badge-wrap">pausiert</span> : null}
    </>
  );
}

export function PilotView({ route }: { route: Route }) {
  const { pilotClient, status } = useApp();
  const state = useAsync(pilotClient ? () => pilotClient.stand() : null, [pilotClient]);
  if (!status?.spielgeld) {
    return (
      <div className="view pilot-view">
        <EmptyState title="Noch kein Spielgeld-Stand veröffentlicht">
          <p>
            Der Spielgeld-Robo führt seine virtuellen Depots im täglichen Lauf weiter. Sobald ein Stand veröffentlicht ist, stehen hier Pilotdepot, Strategien,
            Positionen, Orders und das Journal mit allen Begründungen.
          </p>
        </EmptyState>
      </div>
    );
  }
  if (state.error && !state.data) return <ErrorNote error={state.error} />;
  if (!state.data) return <Loading label="Spielgeld-Stand wird geladen" />;
  const stand = state.data;
  const sub = route.segments[1] ?? '';
  return (
    <div className="view pilot-view">
      <Notice tone={stand.modus === 'DEMO' ? 'demo' : 'info'} compact>
        <strong>Spielgeld</strong> · keine echten Orders, keine Anlageberatung · Datenstand {f.isoDate(stand.datentag)}
      </Notice>
      {sub === 'depot' ? <DepotDetail stand={stand} id={route.segments[2] ?? ''} /> : null}
      {sub === 'regeln' ? <RegelnListe stand={stand} /> : null}
      {sub === 'regel' ? <RegelDetail stand={stand} key_={route.segments[2] ?? ''} /> : null}
      {sub === 'chronik' ? <Chronik stand={stand} /> : null}
      {sub === 'neu' ? <PilotEditor key={route.params.toString()} stand={stand} route={route} /> : null}
      {sub === 'einrichten' ? <PilotEinrichtung stand={stand} /> : null}
      {sub === '' ? <Uebersicht stand={stand} /> : null}
      {!['', 'depot', 'regeln', 'regel', 'chronik', 'neu', 'einrichten'].includes(sub) ? (
        <Notice tone="warn" title="Seite nicht gefunden" actions={<a className="btn btn-primary" href="#/pilot">Zur Übersicht</a>} />
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ Übersicht */

function Uebersicht({ stand }: { stand: PilotStand }) {
  const groups = useMemo(() => gruppieren(stand.depots), [stand]);
  const [order, setOrder] = useState<Sortierung>('rendite');
  if (!groups.length) {
    return <EmptyState title="Keine aktiven Spielgelddepots">Alle Läufe sind archiviert – siehe Chronik.</EmptyState>;
  }
  return (
    <>
      {groups.map((g) => (
        <section className="section" key={String(g.historisch)} aria-labelledby={`pg-${g.historisch ? 'h' : 'v'}`}>
          <SectionTitle id={`pg-${g.historisch ? 'h' : 'v'}`}>{g.historisch ? 'Historische Simulation' : 'Vorwärtstest mit Spielgeld'}</SectionTitle>
          {g.historisch ? (
            <p className="section-note">
              Derselbe Motor über vergangene Handelstage, Ranglisten je Tag mit den Kursen bis zu diesem Tag nachgerechnet (heutige Datenrevision und heutiges
              Universum – Rückschau-Verzerrung möglich). Kein Vorwärtstest und kein Leistungsnachweis.
            </p>
          ) : (
            <p className="section-note">
              {stand.hinweis} {stand.ueberwachung}
            </p>
          )}
          {g.pilot ? <PilotKarte d={g.pilot} g={g} /> : null}
          {g.pilot && !g.historisch ? <Steuerung d={g.pilot} /> : null}
          <VerlaufVergleich g={g} />
          <StrategieTabelle g={g} order={order} setOrder={setOrder} />
        </section>
      ))}
      <Eingaenge stand={stand} />
      <p className="section-note">
        <a href="#/pilot/regeln">Regeln ansehen</a> · <a href="#/pilot/chronik">Archivierte Läufe ({stand.chronik.length})</a> · Software {stand.version}
      </p>
    </>
  );
}

/** Automatik des Pilotdepots steuern (Abschnitt 29.3): wirkt ab dem nächsten täglichen Lauf; Stops laufen immer weiter. */
function Steuerung({ d }: { d: PilotDepot }) {
  const offeneKaeufe = d.orders_offen.filter((o) => o.richtung === 'kauf').length;
  return (
    <Disclosure summary="Automatik steuern">
      <p className="section-note">
        Wirkt ab dem nächsten täglichen Lauf. Stops und Schutzverkäufe laufen immer weiter; Echtgeld und echte Orders gibt es nicht.
      </p>
      <a className="btn" href="#/pilot/einrichten">
        Einrichtung ändern (Startkapital, fünf Fragen, aktiver Anteil)
      </a>
      {d.pausiert ? (
        <PilotSenden art="fortsetzen" inhalt={{}} bezeichnung="Automatik fortsetzen" label="Automatik fortsetzen" primary />
      ) : (
        <PilotSenden art="pausieren" inhalt={{}} bezeichnung="Neue Käufe pausieren" label="Neue Käufe pausieren" />
      )}
      {offeneKaeufe ? <PilotSenden art="offene_kaeufe_stornieren" inhalt={{}} bezeichnung={`${offeneKaeufe} offene Käufe stornieren`} label={`${offeneKaeufe} offene Käufe stornieren`} /> : null}
      {d.positionen.some((p) => p.zuordnung !== 'kern') ? (
        <>
          <PilotSenden art="positionen_schliessen" inhalt={{}} bezeichnung="Aktive Positionen schließen" label="Aktive Positionen schließen" />
          <p className="section-note">Verkauft alle Positionen der aktiven Strategien in der nächsten Sitzung und pausiert neue Käufe. Der Robo-Kern bleibt.</p>
        </>
      ) : null}
      <PilotSenden art="neuer_test" inhalt={{}} bezeichnung="Neuen Test starten" label="Neuen Test starten" />
      <p className="section-note">
        Startet Pilotdepot und Vergleichsdepots mit derselben Einrichtung neu (neue Test-Kennung, Startkapital wieder voll). Der bisherige Lauf bleibt vollständig in der Chronik.
      </p>
    </Disclosure>
  );
}

function Eingaenge({ stand }: { stand: PilotStand }) {
  const list = stand.eingaenge ?? [];
  return (
    <Disclosure summary={`Eingänge aus der App (${list.length} verarbeitet)`}>
      {list.length ? (
        <ul className="plain-list">
          {list.map((e) => (
            <li key={e.kennung} className="pilot-entry">
              <b>{e.status === 'verarbeitet' ? 'übernommen' : 'abgelehnt'}</b> · {e.art ?? 'unbekannt'} · {f.isoDate(e.verarbeitet_utc.slice(0, 10))}
              {e.grund ? <span className="muted"> · {e.grund}</span> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="section-note">Noch keine Eingänge im täglichen Lauf verarbeitet.</p>
      )}
      <h3 className="subsection-title">Von diesem Gerät gesendet</h3>
      <GesendeteListe />
    </Disclosure>
  );
}

function PilotKarte({ d, g }: { d: PilotDepot; g: DepotGruppe }) {
  const welt = benchmark(g);
  const kern = kernReferenz(g);
  const w = d.wert;
  const k = d.kennzahlen;
  return (
    <div className="pilot-card">
      <div className="pilot-card-head">
        <a className="pilot-card-name" href={`#/pilot/depot/${encodeURIComponent(d.id)}`}>
          {d.name}
        </a>
        <ModusBadge d={d} />
      </div>
      <p className="pilot-total">
        <span className="pilot-total-value">{f.euro(w?.gesamt_eur ?? null)}</span>
        <span className={`pilot-total-change ${f.direction((k.rendite_zeitgewichtet_pct ?? NaN) / 100)}`}>{pctPlain(k.rendite_zeitgewichtet_pct)}</span>
      </p>
      <p className="section-note">
        Zeitgewichtete Rendite seit {f.isoDate(d.start)} mit {f.euro(d.startkapital_eur)} Spielgeld, nach simulierten Kosten. Letzter Tag {f.isoDate(w?.datum)}.
      </p>
      <KeyValues
        items={[
          ['Abstand zum Welt-ETF', abstandText(d, welt)],
          ['Abstand zum Robo-Kern allein', abstandText(d, kern)],
          ['Robo-Kern / aktiv / frei', `${f.euro(w?.kern_eur ?? null)} / ${f.euro(w?.aktiv_eur ?? null)} / ${f.euro(w?.guthaben_eur ?? null)}`],
          ['Reserviert für offene Käufe', f.euro(d.reserviert_eur ?? 0)],
          ['Größter Rückgang', f.plainPct(k.max_rueckgang_pct, 1)],
          ['Kosten bisher', f.euro(k.kosten_eur, true)],
          ['Käufe / Verkäufe', `${f.integer(k.kaeufe)} / ${f.integer(k.verkaeufe)}`],
          ['Verluststufe des aktiven Teils', STUFE_TEXT[d.verlust?.stufe ?? 'normal'] ?? d.verlust?.stufe ?? '–'],
        ]}
      />
      {w && !w.vollstaendig ? <p className="section-note">Bewertung unvollständig: für {w.fehlend.length} Positionen fehlt ein Kurs oder Wechselkurs.</p> : null}
    </div>
  );
}

function abstandText(d: PilotDepotKopf, ref: PilotDepotKopf | null): string {
  if (!ref) return 'kein Vergleichsdepot';
  const diff = abstandPp(d, ref);
  if (diff === null) return 'nicht vergleichbar (anderer Zeitraum)';
  return `${f.signedPctValue(diff, 2).replace('%', 'Prozentpunkte')} (Vergleich ${pctPlain(ref.kennzahlen.rendite_zeitgewichtet_pct)})`;
}

function linesFor(depots: PilotDepot[]): CompareLine[] {
  return depots
    .map((d, slot) => {
      const pts = d.verlauf.tag
        .map((t, i) => ({ day: f.isoToDay(t), close: d.verlauf.gesamt[i] ?? NaN, open: null, high: null, low: null, volume: null, closeRaw: null }))
        .filter((p) => Number.isFinite(p.close));
      return { isin: d.id, name: d.name, slot, pts, basePrice: d.startkapital_eur, currency: 'EUR', note: d.art === 'vergleich' ? 'Vergleich' : d.art === 'pilot' ? 'Pilot' : 'Strategie' };
    })
    .filter((l) => l.pts.length >= 2);
}

function VerlaufVergleich({ g }: { g: DepotGruppe }) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [highlight, setHighlight] = useState<string | null>(null);
  const shown = [g.pilot, benchmark(g), kernReferenz(g)].filter((d): d is PilotDepot => Boolean(d));
  const lines = linesFor(shown.length ? shown : g.forschung.slice(0, 4));
  if (!lines.length) return <p className="section-note">Verlauf erscheint ab dem zweiten bewerteten Tag.</p>;
  const first = Math.min(...lines.map((l) => l.pts[0].day));
  const last = Math.max(...lines.map((l) => l.pts[l.pts.length - 1].day));
  const toggle = (id: string) => {
    const next = new Set(hidden);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setHidden(next);
  };
  return (
    <>
      <CompareChart
        lines={lines}
        baseDay={first}
        end={last}
        hidden={hidden}
        highlight={highlight}
        onHighlight={setHighlight}
        onToggle={toggle}
        height={240}
        ariaLabel={`Gesamtwert von Pilotdepot und Vergleichsdepots vom ${f.day(first)} bis ${f.day(last)}, 100 = Startkapital`}
        formatValue={(close, l) => `${f.euro(close)} (${f.signedPctValue(100 * (close / l.basePrice - 1), 1)})`}
      />
      <p className="section-note">100 = Startkapital. Werte je Handelstag nach dem täglichen Lauf, Kosten eingerechnet, Dividenden nicht erfasst.</p>
    </>
  );
}

function StrategieTabelle({ g, order, setOrder }: { g: DepotGruppe; order: Sortierung; setOrder: (s: Sortierung) => void }) {
  const welt = benchmark(g);
  const rows = sortiereDepots([...g.forschung, ...g.vergleich], order);
  if (!rows.length) return null;
  return (
    <>
      <h3 className="subsection-title">Strategien im Vergleich (je eigenes Forschungsdepot)</h3>
      <Segmented<Sortierung>
        label="Sortieren nach"
        value={order}
        onChange={setOrder}
        options={[
          { value: 'rendite', label: 'Rendite' },
          { value: 'rueckgang', label: 'Rückgang' },
          { value: 'kosten', label: 'Kosten' },
          { value: 'name', label: 'Name' },
        ]}
      />
      <div className="table-wrap">
        <table className="table pilot-table">
          <thead>
            <tr>
              <th>Depot</th>
              <th className="n">Rendite</th>
              <th className="n">zum Welt-ETF</th>
              <th className="n">Rückgang</th>
              <th className="n">Käufe</th>
              <th className="n">Kosten</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => {
              const diff = d === welt ? null : abstandPp(d, welt);
              return (
                <tr key={d.id}>
                  <td>
                    <a href={`#/pilot/depot/${encodeURIComponent(d.id)}`}>{d.name.replace(/ \(historische Simulation\)$/, '')}</a>
                    {d.art === 'vergleich' ? <span className="muted"> · Vergleich</span> : null}
                  </td>
                  <td className="n">{pctPlain(d.kennzahlen.rendite_zeitgewichtet_pct)}</td>
                  <td className="n">{diff === null ? '–' : `${f.signedPctValue(diff, 1).replace('%', 'pp')}`}</td>
                  <td className="n">{f.plainPct(d.kennzahlen.max_rueckgang_pct, 1)}</td>
                  <td className="n">{f.integer(d.kennzahlen.kaeufe)}</td>
                  <td className="n">{f.euro(d.kennzahlen.kosten_eur, true)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="section-note">
        Jede Strategie handelt in einem eigenen Spielgelddepot mit gleichem Startkapital (Forschung, Abschnitt 29.7); die beste übernimmt nie automatisch das
        Pilotdepot. „zum Welt-ETF“: Abstand in Prozentpunkten zum Vergleichsdepot über denselben Zeitraum.
      </p>
    </>
  );
}

/* ------------------------------------------------------------------ Depot */

function DepotDetail({ stand, id }: { stand: PilotStand; id: string }) {
  const d = stand.depots.find((x) => x.id === id);
  const [tab, setTab] = useState<'positionen' | 'orders' | 'journal' | 'regeln' | 'bericht'>('positionen');
  if (!d) {
    return (
      <Notice tone="warn" title="Depot nicht im aktuellen Stand" actions={<a className="btn btn-primary" href="#/pilot">Zur Übersicht</a>}>
        <p>Vielleicht wurde der Lauf inzwischen archiviert – archivierte Läufe stehen in der Chronik.</p>
      </Notice>
    );
  }
  const k = d.kennzahlen;
  return (
    <>
      <div className="view-head">
        <h2 className="section-title">{d.name}</h2>
        <p>
          <ModusBadge d={d} />
        </p>
        {d.beschreibung ? <p className="section-note">{d.beschreibung}</p> : null}
      </div>
      <KeyValues
        items={[
          ['Gesamtwert', `${f.euro(d.wert?.gesamt_eur ?? null)} (${pctPlain(k.rendite_zeitgewichtet_pct)} zeitgewichtet)`],
          ['Zeitraum', `${f.isoDate(d.start)} – ${f.isoDate(d.wert?.datum)} (${f.integer(k.sitzungen)} bewertete Tage)`],
          ['Realisiert / offen', `${f.signedEuro(k.gewinn_realisiert_eur)} / ${f.signedEuro(k.gewinn_offen_eur)}`],
          ['Kosten', f.euro(k.kosten_eur, true)],
          ['Größter Rückgang', f.plainPct(k.max_rueckgang_pct, 1)],
          ['Verluststufe', STUFE_TEXT[d.verlust?.stufe ?? 'normal'] ?? '–'],
          ['Test-Kennung', d.test_id],
        ]}
      />
      <Segmented
        label="Ansicht"
        hideLabel
        value={tab}
        onChange={setTab}
        options={[
          { value: 'positionen', label: `Positionen (${d.positionen.length})` },
          { value: 'orders', label: `Orders (${d.orders_offen.length})` },
          { value: 'journal', label: 'Journal' },
          { value: 'regeln', label: 'Regeln' },
          { value: 'bericht', label: 'Bericht' },
        ]}
      />
      {tab === 'positionen' ? <Positionen d={d} /> : null}
      {tab === 'orders' ? <Orders d={d} stand={stand} /> : null}
      {tab === 'journal' ? <Journal d={d} stand={stand} /> : null}
      {tab === 'regeln' ? <DepotRegeln d={d} stand={stand} /> : null}
      {tab === 'bericht' ? <DepotBericht d={d} stand={stand} /> : null}
    </>
  );
}

function Positionen({ d }: { d: PilotDepot }) {
  if (!d.positionen.length) return <EmptyState title="Keine offenen Positionen">Das Spielgeld liegt als Guthaben im Depot.</EmptyState>;
  return (
    <div className="table-wrap">
      <table className="table pilot-table">
        <thead>
          <tr>
            <th>Aktie</th>
            <th className="n">Stück</th>
            <th className="n">Wert</th>
            <th className="n">Gewinn</th>
            <th className="n">Stop</th>
          </tr>
        </thead>
        <tbody>
          {d.positionen.map((p) => (
            <tr key={`${p.zuordnung}|${p.isin}`}>
              <td>
                <a href={`#/aktie/${p.isin}`}>{p.name ?? p.isin}</a>
                <br />
                <span className="muted">
                  {p.zuordnung === 'kern' ? 'Robo-Kern' : p.regel ?? p.zuordnung} · seit {f.isoDate(p.eroeffnet)}
                </span>
              </td>
              <td className="n">{f.integer(p.stueck)}</td>
              <td className="n">
                {f.euro(p.wert_eur)}
                <br />
                <span className="muted">Einstand {f.euro(p.einstand_eur)}</span>
              </td>
              <td className="n">
                {f.signedEuro(p.gewinn_eur)}
                <br />
                <span className="muted">{pctPlain(p.gewinn_pct, 1)}</span>
              </td>
              <td className="n">{p.stop === null ? '–' : f.price(p.stop)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="section-note">
        Gewinn nach Kaufkosten, ohne Verkaufskosten und Steuern. Stop in der Währung der Börse; geprüft wird mit der fertigen Tageskerze im täglichen Lauf.
      </p>
    </div>
  );
}

function OrderZeile({ o, stand }: { o: PilotOrder; stand: PilotStand }) {
  const name = stand.namen[o.isin] ?? o.isin;
  return (
    <li className="pilot-order">
      <span className={`badge ${o.richtung === 'kauf' ? '' : 'badge-warn'}`}>{o.richtung === 'kauf' ? 'Kauf' : 'Verkauf'}</span> {f.integer(o.stueck)} × {name}
      <br />
      <span className="muted">
        {o.grund_text ?? o.grund} · Daten vom {f.day(o.datentag)}
        {o.sitzung ? ` · Sitzung ${f.day(o.sitzung)} (${o.preispunkt === 'open' ? 'Eröffnung' : 'Schlusskurs'})` : ''} · {ORDER_STATUS[o.status] ?? o.status}
        {o.status === 'offen' && o.reserviert_eur ? ` · reserviert ${f.euro(o.reserviert_eur)}` : ''}
        {o.schutz ? ' · Schutzverkauf' : ''}
      </span>
    </li>
  );
}

function Orders({ d, stand }: { d: PilotDepot; stand: PilotStand }) {
  return (
    <>
      <h3 className="subsection-title">Offene Orders</h3>
      {d.orders_offen.length ? (
        <ul className="plain-list">
          {d.orders_offen.map((o) => (
            <OrderZeile key={o.id} o={o} stand={stand} />
          ))}
        </ul>
      ) : (
        <p className="section-note">Keine offenen Orders.</p>
      )}
      <h3 className="subsection-title">Zuletzt</h3>
      {d.orders_zuletzt.length ? (
        <ul className="plain-list">
          {[...d.orders_zuletzt].reverse().map((o) => (
            <OrderZeile key={o.id} o={o} stand={stand} />
          ))}
        </ul>
      ) : (
        <p className="section-note">Noch keine abgeschlossenen Orders.</p>
      )}
      <p className="section-note">Virtuelle Orders: ausgeführt nur im Spielgelddepot zum Kurs der genannten Sitzung, mit simulierten Kosten. Es gibt keinen Weg zu einem Broker.</p>
    </>
  );
}

function Journal({ d, stand }: { d: PilotDepot; stand: PilotStand }) {
  const days = useMemo(() => journalNachTag(d.journal), [d]);
  const [limit, setLimit] = useState(10);
  if (!days.length) return <p className="section-note">Noch keine Einträge.</p>;
  return (
    <>
      <ol className="pilot-journal">
        {days.slice(0, limit).map((day) => (
          <li key={day.datum}>
            <h3 className="subsection-title">{f.isoDate(day.datum)}</h3>
            <ul className="plain-list">
              {day.eintraege.map((e, i) => (
                <JournalEintrag key={i} e={e} stand={stand} />
              ))}
            </ul>
          </li>
        ))}
      </ol>
      {days.length > limit ? (
        <button type="button" className="btn" onClick={() => setLimit(limit + 10)}>
          Ältere Einträge zeigen
        </button>
      ) : null}
    </>
  );
}

function JournalEintrag({ e, stand }: { e: PilotJournal; stand: PilotStand }) {
  const label = ART_TEXT[e.art] ?? e.art;
  if (e.art === 'entscheidung' && e.daten && 'statistik' in e.daten) {
    const data = e.daten as PilotEntscheidung;
    const regel = data.regel ? stand.regeln[data.regel] : undefined;
    return (
      <li className="pilot-entry">
        <Disclosure
          summary={
            <>
              <b>{label}</b> {regel?.name ?? e.zuordnung}: {e.text}
            </>
          }
        >
          <Entscheidung data={data} regel={regel} stand={stand} />
        </Disclosure>
      </li>
    );
  }
  return (
    <li className="pilot-entry">
      <b>{label}</b> {e.text}
      {e.daten && typeof (e.daten as Record<string, unknown>).isin === 'string' ? (
        <span className="muted"> · {stand.namen[(e.daten as { isin: string }).isin] ?? (e.daten as { isin: string }).isin}</span>
      ) : null}
      {e.daten && typeof (e.daten as Record<string, unknown>).grund_text === 'string' ? (
        <span className="muted"> · {(e.daten as { grund_text: string }).grund_text}</span>
      ) : null}
    </li>
  );
}

function Entscheidung({ data, regel, stand }: { data: PilotEntscheidung; regel?: Regel; stand: PilotStand }) {
  const s = data.statistik;
  const name = (isin: string) => stand.namen[isin] ?? isin;
  const items: [ReactNode, ReactNode][] = [];
  if (s) {
    items.push(['Kandidaten', `${f.integer(s.kandidaten)} geprüft, ${f.integer(s.zugelassen)} erfüllen alle Bedingungen, ${f.integer(s.ausgewaehlt)} ausgewählt`]);
    if (s.nicht_erfuellt || s.nicht_pruefbar) items.push(['Ausgeschlossen', `${f.integer(s.nicht_erfuellt)} nicht erfüllt, ${f.integer(s.nicht_pruefbar)} nicht prüfbar (fehlende Daten)`]);
  }
  if (data.budget_eur !== null && data.budget_eur !== undefined) items.push(['Budget der Strategie', f.euro(data.budget_eur)]);
  if (data.kaeufe?.length) items.push(['Käufe beauftragt', data.kaeufe.map((k) => `${f.integer(k.stueck)} × ${name(k.isin)}`).join(', ')]);
  if (data.verkaeufe?.length) items.push(['Verkäufe beauftragt', data.verkaeufe.map((k) => `${f.integer(k.stueck)} × ${name(k.isin)} (${k.grund})`).join(', ')]);
  if (data.abgelehnt?.length) items.push(['Nicht gekauft', data.abgelehnt.map((a) => `${name(a.isin)}: ${a.grund}`).join('; ')]);
  return (
    <>
      <KeyValues items={items} />
      {data.kandidaten?.length ? (
        <div className="table-wrap">
          <table className="table pilot-table">
            <thead>
              <tr>
                <th>Kandidat</th>
                <th className="n">Platz</th>
                <th>Ergebnis</th>
              </tr>
            </thead>
            <tbody>
              {data.kandidaten.map((c) => (
                <tr key={c.isin}>
                  <td>
                    {name(c.isin)}
                    {c.ausgewaehlt ? <span className="badge">ausgewählt</span> : null}
                  </td>
                  <td className="n">{c.platz ?? '–'}</td>
                  <td>
                    {c.grund ?? (c.ausgewaehlt ? 'alle Bedingungen erfüllt' : '–')}
                    {c.bedingungen?.length ? (
                      <ul className="plain-list pilot-conditions">
                        {c.bedingungen.map((b, i) => (
                          <li key={i} className={`cond-${b.ergebnis}`}>
                            {ERGEBNIS_TEXT[b.ergebnis]}: {bedingungAusPfad(regel, b.pfad, stand.katalog)}
                            {typeof b.wert === 'number' ? ` (Wert ${f.score(b.wert)}${typeof b.vergleichswert === 'number' ? `, Vergleich ${f.score(b.vergleichswert)}` : ''})` : ''}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <p className="section-note">Festgehalten vor der Ausführung, mit Daten bis zum Stichtag; spätere Kurse ändern diese Begründung nicht.</p>
    </>
  );
}

function DepotRegeln({ d, stand }: { d: PilotDepot; stand: PilotStand }) {
  return (
    <>
      {d.kern ? (
        <section className="section">
          <h3 className="subsection-title">Robo-Kern</h3>
          <KeyValues
            items={[
              ...Object.entries(d.kern.ziele).map(([isin, w]) => [d.kern?.namen[isin] ?? isin, f.plainPct(100 * w, 0)] as [ReactNode, ReactNode]),
              ['Umschichten ab', `${f.plainPct(d.kern.schwelle_pp, 0).replace('%', 'Prozentpunkten')} Abweichung`],
            ]}
          />
        </section>
      ) : null}
      {d.strategien.map((s) => {
        const regel = stand.regeln[s.regel];
        return (
          <section className="section" key={s.zuordnung}>
            <h3 className="subsection-title">
              {s.name} <span className="muted">({s.regel}, Anteil am aktiven Teil {f.plainPct(100 * s.anteil, 0)})</span>
            </h3>
            {regel ? <RegelText regel={regel} stand={stand} /> : <p className="section-note">Regel nicht im Stand.</p>}
          </section>
        );
      })}
    </>
  );
}

/* ------------------------------------------------------------------ Regeln */

function RegelText({ regel, stand }: { regel: Regel; stand: PilotStand }) {
  return <KeyValues items={regelZusammenfassung(regel, stand.katalog)} />;
}

function RegelnListe({ stand }: { stand: PilotStand }) {
  const entries = Object.entries(stand.regeln).sort((a, b) => a[1].name.localeCompare(b[1].name, 'de'));
  return (
    <section className="section">
      <SectionTitle>Regeln der Spielgelddepots</SectionTitle>
      <p className="section-note">
        Jede fachliche Änderung ergibt eine neue Version mit neuem Test; alte Versionen und Läufe bleiben erhalten. Bausteine aus dem Kennzahlenkatalog (
        {stand.katalog?.kennzahlen.length ?? 0} Kennzahlen, {stand.katalog_version}).
      </p>
      <div className="toolbar">
        <a className="btn btn-primary" href="#/pilot/neu">
          Neue Regel bauen
        </a>
      </div>
      <ul className="plain-list">
        {entries.map(([key, r]) => (
          <li key={key} className="pilot-rule">
            <a href={`#/pilot/regel/${encodeURIComponent(key)}`}>{r.name}</a> <span className="muted">{key}</span>
            {r.beschreibung ? <p className="section-note">{r.beschreibung}</p> : null}
          </li>
        ))}
      </ul>
      <KatalogListe stand={stand} />
    </section>
  );
}

/** Alle Kennzahlen des Katalogs mit „Als Robo-Regel verwenden“ (Abschnitt 31.8): öffnet den Baukasten mit dieser Kennzahl. */
function KatalogListe({ stand }: { stand: PilotStand }) {
  const k = stand.katalog;
  if (!k) return null;
  const groups = new Map<string, typeof k.kennzahlen>();
  for (const x of k.kennzahlen) {
    if (x.rueckblickend) continue;
    groups.set(x.gruppe, [...(groups.get(x.gruppe) ?? []), x]);
  }
  return (
    <Disclosure summary={`Kennzahlenkatalog (${k.kennzahlen.length} Kennzahlen) – als Regel verwenden`}>
      {[...groups.entries()].map(([g, list]) => (
        <section key={g} className="section">
          <h3 className="subsection-title">{g}</h3>
          <ul className="plain-list">
            {list.map((x) => (
              <li key={x.id} className="pilot-rule">
                <b>{x.name}</b>
                {x.einheit ? <span className="muted"> ({x.einheit})</span> : null}
                <p className="section-note">
                  {x.erklaerung} {x.backtest === 'ja' ? 'Historisch testbar.' : 'Nur vorwärts prüfbar.'}
                </p>
                <a className="btn btn-quiet" href={`#/pilot/neu?kennzahl=${encodeURIComponent(x.id)}`}>
                  Als Robo-Regel verwenden
                </a>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </Disclosure>
  );
}

function RegelDetail({ stand, key_ }: { stand: PilotStand; key_: string }) {
  const regel = stand.regeln[key_];
  if (!regel) return <Notice tone="warn" title="Regel nicht im Stand" actions={<a className="btn" href="#/pilot/regeln">Alle Regeln</a>} />;
  const depots = stand.depots.filter((d) => d.strategien.some((s) => s.regel === key_));
  return (
    <section className="section">
      <SectionTitle>{regel.name}</SectionTitle>
      <p className="section-note">
        {key_}
        {regel.beschreibung ? ` – ${regel.beschreibung}` : ''}
      </p>
      <RegelText regel={regel} stand={stand} />
      <h3 className="subsection-title">Verwendet in</h3>
      <ul className="plain-list">
        {depots.map((d) => (
          <li key={d.id}>
            <a href={`#/pilot/depot/${encodeURIComponent(d.id)}`}>{d.name}</a> · {pctPlain(d.kennzahlen.rendite_zeitgewichtet_pct)}
          </li>
        ))}
      </ul>
      <div className="toolbar">
        <a className="btn btn-primary" href={`#/pilot/neu?von=${encodeURIComponent(key_)}&art=version`}>
          Als neue Version bearbeiten
        </a>
        <a className="btn" href={`#/pilot/neu?von=${encodeURIComponent(key_)}`}>
          Als Kopie bearbeiten
        </a>
      </div>
      {depots.some((d) => d.id.startsWith('e-')) ? (
        <PilotSenden art="regel_beenden" inhalt={{ regel_id: regel.id }} bezeichnung={`Test beenden: ${regel.name}`} label="Test dieser Regel beenden" />
      ) : null}
      <Disclosure summary="Regel als Daten (JSON)">
        <pre className="pilot-json">{JSON.stringify(regel, null, 1)}</pre>
      </Disclosure>
      <button type="button" className="btn" onClick={() => navigate('/pilot/regeln')}>
        Alle Regeln
      </button>
    </section>
  );
}

/* ------------------------------------------------------------------ Chronik */

function Chronik({ stand }: { stand: PilotStand }) {
  if (!stand.chronik.length) return <EmptyState title="Noch keine archivierten Läufe">Ein neuer Test archiviert den vorigen Lauf vollständig.</EmptyState>;
  return (
    <section className="section">
      <SectionTitle>Archivierte Läufe</SectionTitle>
      <div className="table-wrap">
        <table className="table pilot-table">
          <thead>
            <tr>
              <th>Depot</th>
              <th>Zeitraum</th>
              <th className="n">Rendite</th>
              <th className="n">Rückgang</th>
            </tr>
          </thead>
          <tbody>
            {stand.chronik.map((d) => (
              <tr key={d.id}>
                <td>
                  {d.name}
                  <br />
                  <span className="muted">{d.test_id}</span>
                </td>
                <td>
                  {f.isoDate(d.start)} – {f.isoDate(d.wert?.datum)}
                  <br />
                  <span className="muted">archiviert {f.isoDate(d.archiviert_am?.slice(0, 10))}</span>
                </td>
                <td className="n">{pctPlain(d.kennzahlen.rendite_zeitgewichtet_pct)}</td>
                <td className="n">{f.plainPct(d.kennzahlen.max_rueckgang_pct, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="section-note">Nichts wird gelöscht: jeder Lauf bleibt mit seinem Journal im Zustand erhalten.</p>
    </section>
  );
}
