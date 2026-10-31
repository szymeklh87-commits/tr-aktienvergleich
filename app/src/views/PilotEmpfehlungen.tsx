/* Depot-Empfehlungen unter „Pilot“ (Aufträge vom 31.10.2026, 18 und 19; Abschnitt 16): oben das aktuell empfohlene Depot
 * mit Datenstand, Horizont, Risikoprofil, Erwartung und Unsicherheit, in der Mitte die sortierbare Tabelle der Aktien, unten
 * die empfohlenen Veränderungen mit Begründung; darunter Rangliste je Horizont, Variantenvergleich, Risikoverteilung,
 * Prognosekontrolle, Strategieforschung, geprüfte Informationen und Depotparameter. Nur Anzeige – gerechnet wird im
 * Forschungslauf und im täglichen Lauf; Änderungen der Parameter gehen als verschlüsselter Eingang an den Robo. */

import { useMemo, useState, type ReactNode } from 'react';
import { PilotSenden } from '../components/pilotsenden';
import { Disclosure, EmptyState, KeyValues, Notice, SectionTitle, Segmented } from '../components/ui';
import * as f from '../lib/format';
import {
  anteile,
  ART_TEXT,
  belastbarkeitTon,
  bestaetigte,
  einstellungenFehler,
  freigabePruefung,
  depotErwartung,
  HERKUNFT_TEXT,
  HORIZONTE,
  ic,
  merkmalName,
  modellPruefung,
  pp,
  rangliste,
  sortieren,
  spanne,
  standardVariante,
  STRATEGIE_REIHENFOLGE,
  UMSCHICHTUNG_TEXT,
  variante as varianteVon,
  VARIANTEN,
  variantenListe,
  type Belastbarkeit,
  type Horizont,
  type OptArt,
  type OptEinstellungen,
  type OptStand,
  type OptVariante,
  type OptZeile,
  type Spalte,
  type VarianteId,
} from '../lib/optimierer';
import type { PilotStand } from '../lib/pilot';
import { updateParams, type Route } from '../lib/router';

const pct1 = (v: number | null | undefined) => f.signedPctValue(v ?? null, 1);
const KURZ: Record<Horizont, string> = { w1: '1 W', w2: '2 W', w4: '4 W', w12: '12 W', w26: '26 W', w52: '52 W' };
/** kurze Namen für die Auswahl (die vollen Namen stehen im Kopf) */
const KURZNAME: Record<VarianteId, string> = {
  ausgewogen: 'Ausgewogen',
  rendite: 'Rendite',
  stabil: 'Stabil',
  kurz: 'Kurzfristig',
  mittel: 'Mittelfristig',
  lang: 'Langfristig',
};
/** Bindestrich, der in Zahlenschrift nicht ziffernbreit wird und nicht umbricht */
const nb = (text: string) => text.replace(/-/g, '‑');

type Ansicht = 'depot' | 'rangliste' | 'varianten' | 'kontrolle' | 'forschung' | 'informationen' | 'parameter';
const ANSICHTEN: { value: Ansicht; label: string; title: string }[] = [
  { value: 'depot', label: 'Depot', title: 'Empfohlene Aktien, Veränderungen und Risikoverteilung' },
  { value: 'rangliste', label: 'Rangliste', title: 'Aktuell aussichtsreichste Aktien je Prognosezeitraum' },
  { value: 'varianten', label: 'Varianten', title: 'Depotvarianten im Vergleich' },
  { value: 'kontrolle', label: 'Kontrolle', title: 'Prognosekontrolle: frühere Prognosen gegen die tatsächliche Entwicklung' },
  { value: 'forschung', label: 'Forschung', title: 'Strategieforschung: geprüfte Merkmale, Modelle, Kalibrierung, Rückblick' },
  { value: 'informationen', label: 'Infos', title: 'Geprüfte Informationen und Rechenaufwand' },
  { value: 'parameter', label: 'Parameter', title: 'Depotparameter ansehen und ändern' },
];

function Belastbar({ b }: { b: Belastbarkeit | null | undefined }) {
  const ton = belastbarkeitTon(b);
  return <span className={`badge badge-wrap${ton === 'ok' ? ' badge-ok' : ton === 'warn' ? ' badge-warn' : ''}`}>{b ?? 'nicht belastbar'}</span>;
}

export function PilotEmpfehlungen({ stand, route }: { stand: PilotStand; route: Route }) {
  const o = stand.optimierer;
  if (!o) {
    return (
      <EmptyState title="Noch keine Depot-Empfehlungen">
        <p>
          Der Depot-Optimierer prüft in einem Forschungslauf alle Kennzahlen der App über mehrere Jahre auf ihren Prognosenutzen, vergleicht Modelle zeitlich
          getrennt und rechnet danach täglich ein Empfehlungsdepot. Sobald ein Forschungsergebnis übernommen ist, stehen hier das empfohlene Depot, die
          aussichtsreichsten Aktien je Zeitraum und die Kontrolle früherer Prognosen.
        </p>
      </EmptyState>
    );
  }
  return <Empfehlungen o={o} stand={stand} route={route} />;
}

function Empfehlungen({ o, stand, route }: { o: OptStand; stand: PilotStand; route: Route }) {
  const standard = standardVariante(o);
  const gewaehlt = (VARIANTEN as string[]).includes(route.params.get('variante') ?? '') ? (route.params.get('variante') as VarianteId) : standard;
  const v = varianteVon(o, gewaehlt);
  const rl = rangliste(o);
  const ansichtParam = route.params.get('ansicht') ?? '';
  const ansicht: Ansicht = ANSICHTEN.some((a) => a.value === ansichtParam) ? (ansichtParam as Ansicht) : 'depot';
  return (
    <div className="opt-view">
      <section className="section" aria-labelledby="opt-depot">
        <SectionTitle id="opt-depot">Optimiertes Depot – Aktuelle Empfehlungen</SectionTitle>
        <Segmented
          label="Depotvariante"
          value={gewaehlt}
          onChange={(x) => updateParams(route, { variante: x === standard ? null : x })}
          options={variantenListe(o).map((x) => ({
            value: x.variante,
            label: `${KURZNAME[x.variante]}${x.variante === standard ? '\u00a0★' : ''}`,
            title: x.verfuegbar ? `${x.name}: ${x.erklaerung} (${x.horizont_text})` : `${x.name}: ${x.grund}`,
          }))}
        />
        {v ? <Kopf o={o} v={v} stand={stand} /> : <p className="section-note">Für diese Variante liegt noch keine Empfehlung vor.</p>}
      </section>

      <Segmented label="Ansicht" hideLabel wrap value={ansicht} onChange={(x) => updateParams(route, { ansicht: x === 'depot' ? null : x })} options={ANSICHTEN} />

      {ansicht === 'depot' && v?.verfuegbar ? (
        <>
          <DepotTabelle v={v} route={route} />
          <Veraenderungen v={v} />
          {v.kennzahlen ? <Verteilung v={v} /> : null}
        </>
      ) : null}
      {ansicht === 'depot' && v && !v.verfuegbar ? (
        <p className="section-note opt-nicht">Ohne belastbare Prognose für {v.horizont_text} gibt es für diese Variante bewusst kein Depot.</p>
      ) : null}
      {ansicht === 'rangliste' && rl ? <Rangliste o={o} route={route} /> : null}
      {ansicht === 'varianten' ? <Varianten o={o} gewaehlt={gewaehlt} route={route} /> : null}
      {ansicht === 'kontrolle' ? (
        <>
          <Kontrolle o={o} />
          <Uebernahme o={o} stand={stand} />
        </>
      ) : null}
      {ansicht === 'forschung' ? <Forschung o={o} route={route} /> : null}
      {ansicht === 'informationen' ? (
        <>
          <Informationen o={o} />
          <section className="section" aria-labelledby="opt-lesen">
            <SectionTitle id="opt-lesen">So sind die Empfehlungen zu lesen</SectionTitle>
            <ul className="plain-list">
              {o.modell.hinweise.map((h) => (
                <li key={h}>{h}</li>
              ))}
              <li>
                Erwartete Renditen sind beobachtete Häufigkeiten aus dem zeitlich getrennten Test (Walk‑forward) für Aktien mit ähnlicher Wertung, nach Zehnteln
                geglättet – keine Zusage. Die Spanne zeigt, zwischen welchen Werten 80 % der damaligen Ergebnisse lagen.
              </li>
              <li>Das Spielgeld‑Pilotdepot handelt nach seinen eigenen Regeln; diese Empfehlungen ändern es nicht von selbst.</li>
            </ul>
          </section>
        </>
      ) : null}
      {ansicht === 'parameter' && rl ? <Parameter e={rl.einstellungen} herkunft={rl.herkunft} o={o} stand={stand} /> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ oben: das empfohlene Depot */

function Fakt({ label, children, breit = false }: { label: string; children: ReactNode; breit?: boolean }) {
  return (
    <div className={`opt-fact${breit ? ' is-wide' : ''}`}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function Kopf({ o, v, stand }: { o: OptStand; v: OptVariante; stand: PilotStand }) {
  const rl = rangliste(o);
  const h = o.modell.forschung.horizonte[v.horizont];
  const wf = modellPruefung(o, v.horizont);
  const k = v.kennzahlen;
  const rb = h?.rueckblick;
  const welt = rb?.strategien.welt;
  const modell = rb?.strategien.modell;
  if (!v.verfuegbar) {
    const alternativen = variantenListe(o).filter((x) => x.verfuegbar);
    return (
      <Notice tone="warn" title={`${v.name}: keine belastbare Prognose`}>
        <p>{v.grund}</p>
        {alternativen.length ? (
          <p>
            Belastbar gerechnet sind:{' '}
            {alternativen.map((x, i) => (
              <span key={x.variante}>
                {i ? ', ' : ''}
                <a href={`#/pilot/empfehlungen?variante=${x.variante}`}>
                  {x.name} ({x.horizont_text})
                </a>
              </span>
            ))}
            .
          </p>
        ) : (
          <p>Für keinen Zeitraum ist die Datenlage im Moment ausreichend – dann gibt es bewusst kein Empfehlungsdepot.</p>
        )}
      </Notice>
    );
  }
  return (
    <>
      {v.ersatz ? (
        <Notice tone="warn" compact>
          {v.ersatz}
        </Notice>
      ) : null}
      <div className="opt-hero" data-variante={v.variante}>
        <div className="opt-hero-main">
          <span className="opt-hero-label">
            {v.name} · erwartete Depotrendite nach Kosten über {v.horizont_text}
          </span>
          <span className="opt-hero-value">{k ? pct1(k.erwartet_nach_kosten_pct) : '–'}</span>
          <span className="opt-hero-note">
            Unsicherheit ± {k ? f.plainPct(k.schwankung_pct, 1) : '–'} · ungünstiger Fall (5 %) {k && k.verlustszenario_pct !== null ? pct1(k.verlustszenario_pct) : '–'}
          </span>
        </div>
        <Belastbar b={h?.belastbarkeit} />
      </div>
      <dl className="opt-facts">
        <Fakt label="Datenstand">{f.isoDate(o.heute?.datentag ?? stand.datentag)}</Fakt>
        <Fakt label="Anlagezeitraum">
          {v.horizont_text}
          {v.horizont_wunsch && v.horizont_wunsch !== v.horizont ? <span className="muted"> (eingestellt {KURZ[v.horizont_wunsch]})</span> : null}
        </Fakt>
        <Fakt label="Risikoprofil">
          {KURZNAME[v.variante]}
          {rl ? <span className="muted"> · {rl.herkunft === 'risikoprofil' ? 'aus der Einrichtung' : rl.herkunft === 'app' ? 'eingestellt' : 'Vorgabe'}</span> : null}
        </Fakt>
        <Fakt label="Aktien">
          {f.integer(v.positionen.length)}
          {k ? <span className="muted"> · wirksam wie {f.integer(Math.round(k.effektive_anzahl))}</span> : null}
        </Fakt>
        <Fakt label="Historisch getestet" breit>
          {modell && modell.perioden
            ? nb(`Top 10 nach Modell ${pct1(modell.mittel_pct)} je ${rb?.text}, Welt‑ETF ${pct1(welt?.mittel_pct)}; besser in ${modell.besser_als_welt ?? 0} von ${modell.perioden} unabhängigen Zeiträumen`)
            : 'Rückblick nur für 4, 12 und 26 Wochen'}
        </Fakt>
        <Fakt label="Prognosemodell" breit>
          {h?.modell && wf ? nb(`${wf.name}; Rang‑IC ${ic(wf.ic)} (t = ${f.decimal(wf.t, 1)}), Kosten ${f.plainPct(k?.kosten_pct ?? null, 2)} je Kauf und Verkauf`) : '–'}
        </Fakt>
        <Fakt label="Letzte Aktualisierung" breit>
          {f.berlinTime(stand.erstellt_utc)} <span className="muted">· Forschungslauf vom {f.isoDate(o.modell.erstellt_utc.slice(0, 10))}</span>
        </Fakt>
        <Fakt label="Spielgeld-Musterdepot" breit>
          <Musterdepot stand={stand} v={v} />
        </Fakt>
      </dl>
    </>
  );
}

/** Modus B (Auftrag 18, Abschnitt 14): Forschungsdepot mit Spielgeld, das dieser Empfehlung folgt – Vorwärtstest. */
function Musterdepot({ stand, v }: { stand: PilotStand; v: OptVariante }) {
  const id = `${stand.modus === 'DEMO' ? 'demo-' : ''}f-empfehlung-${v.variante}`;
  const d = stand.depots.find((x) => (x.id === id || x.id.startsWith(`${id}-`)) && x.status !== 'archiviert');
  if (!d) {
    return (
      <span className="muted">
        {rangliste_standard(stand) === v.variante
          ? 'startet mit dem nächsten täglichen Lauf und folgt dieser Empfehlung im Vorwärtstest'
          : 'nur für die Standardvariante (unter „Parameter“ wählbar)'}
      </span>
    );
  }
  const k = d.kennzahlen;
  return (
    <>
      <a href={`#/pilot/depot/${encodeURIComponent(d.id)}`}>{d.name}</a>
      <span className="muted">
        {' '}
        · seit {f.isoDate(d.start)} {pct1(k.rendite_zeitgewichtet_pct)} · {f.plural(k.kaeufe, 'Kauf', 'Käufe')}, {f.plural(k.verkaeufe, 'Verkauf', 'Verkäufe')}
      </span>
    </>
  );
}

function rangliste_standard(stand: PilotStand): VarianteId | null {
  return stand.optimierer?.heute?.varianten.rangliste?.einstellungen.variante ?? null;
}

/* ------------------------------------------------------------------ Mitte: sortierbare Tabelle */

function SortKopf({
  spalte,
  label,
  sort,
  setSort,
  text = false,
}: {
  spalte: Spalte;
  label: string;
  sort: { spalte: Spalte; ab: boolean };
  setSort: (s: { spalte: Spalte; ab: boolean }) => void;
  text?: boolean;
}) {
  const aktiv = sort.spalte === spalte;
  return (
    <th className={text ? undefined : 'n'} scope="col" aria-sort={aktiv ? (sort.ab ? 'descending' : 'ascending') : 'none'}>
      <button type="button" className="th-sort" onClick={() => setSort({ spalte, ab: aktiv ? !sort.ab : !text })}>
        {label}
        <span aria-hidden="true">{aktiv ? (sort.ab ? ' ↓' : ' ↑') : ''}</span>
      </button>
    </th>
  );
}

function DepotTabelle({ v, route }: { v: OptVariante; route: Route }) {
  const s = route.params.get('sortierung') ?? 'gewicht:ab';
  const [sp, richtung] = s.split(':');
  const sort = { spalte: (['gewicht', 'erwartet', 'risiko', 'eignung', 'name', 'kurs'].includes(sp) ? sp : 'gewicht') as Spalte, ab: richtung !== 'auf' };
  const setSort = (x: { spalte: Spalte; ab: boolean }) => updateParams(route, { sortierung: x.spalte === 'gewicht' && x.ab ? null : `${x.spalte}:${x.ab ? 'ab' : 'auf'}` });
  const zeilen = useMemo(() => sortieren(v.positionen, sort.spalte, sort.ab), [v, sort.spalte, sort.ab]);
  const reserve = 100 - v.positionen.reduce((a, z) => a + (z.gewicht_pct ?? 0), 0);
  return (
    <section className="section" aria-labelledby="opt-aktien">
      <SectionTitle id="opt-aktien">Empfohlene Aktien</SectionTitle>
      <div className="table-wrap">
        <table className="table pilot-table opt-table">
          <thead>
            <tr>
              <SortKopf spalte="name" label="Aktie" sort={sort} setSort={setSort} text />
              <SortKopf spalte="gewicht" label="Anteil" sort={sort} setSort={setSort} />
              <SortKopf spalte="erwartet" label="Erwartet" sort={sort} setSort={setSort} />
              <SortKopf spalte="risiko" label="Risiko" sort={sort} setSort={setSort} />
              <SortKopf spalte="eignung" label="Signal" sort={sort} setSort={setSort} />
            </tr>
          </thead>
          {zeilen.map((z) => (
            <tbody key={z.isin} className="opt-row" data-isin={z.isin}>
              <tr>
                <th scope="row">
                  <a href={`#/aktie/${z.isin}`}>{z.name ?? z.isin}</a>
                </th>
                <td className="n">{f.plainPct(z.gewicht_pct ?? null, 1)}</td>
                <td className="n">{pct1(z.erwartet_pct)}</td>
                <td className="n">±{f.plainPct(z.risiko_pct ?? null, 1)}</td>
                <td className="n">{f.integer(z.eignung)}</td>
              </tr>
              <tr className="opt-detail">
                <td colSpan={5}>
                  <span className="opt-isin">{z.isin}</span> · Kurs {z.kurs ? `${f.price(z.kurs.kurs, z.kurs.waehrung)} (${f.isoDate(z.kurs.datum)})` : '–'} · Spanne {spanne(z)} ·
                  Zehntel {z.dezil}
                  <Gruende z={z} />
                </td>
              </tr>
            </tbody>
          ))}
          {reserve > 0.5 ? (
            <tbody>
              <tr>
                <th scope="row">Reserve (Geldmarkt)</th>
                <td className="n">{f.plainPct(reserve, 1)}</td>
                <td className="n">–</td>
                <td className="n">–</td>
                <td className="n">–</td>
              </tr>
            </tbody>
          ) : null}
        </table>
      </div>
      <p className="section-note">
        Erwartet: kalibrierte Rendite über {v.horizont_text} vor Kosten, Spanne = 80 % der damaligen Ergebnisse; Risiko: übliche Schwankung über diesen Zeitraum;
        Signal 0–100: Rang der Erwartung nach Kosten je Unsicherheit unter allen bewerteten Aktien. Antippen öffnet die vollständige Analyse.
      </p>
    </section>
  );
}

function Gruende({ z }: { z: OptZeile }) {
  if (!z.dafuer.length && !z.dagegen.length) return <span className="opt-pro muted">Wertung im oberen Bereich ohne einzelnes herausragendes Merkmal</span>;
  return (
    <>
      {z.dafuer.length ? <span className="opt-pro">Dafür: {z.dafuer.join('; ')}</span> : null}
      {z.dagegen.length ? <span className="opt-contra">Dagegen: {z.dagegen.join('; ')}</span> : null}
    </>
  );
}

/* ------------------------------------------------------------------ unten: Veränderungen */

const ART_REIHENFOLGE: OptArt[] = ['kaufen', 'aufstocken', 'halten', 'reduzieren', 'verkaufen', 'nicht_aufnehmen'];

function Veraenderungen({ v }: { v: OptVariante }) {
  const rows = [...v.veraenderungen].sort((a, b) => ART_REIHENFOLGE.indexOf(a.art) - ART_REIHENFOLGE.indexOf(b.art) || b.gewicht_neu_pct - a.gewicht_neu_pct);
  const erste = rows.length > 0 && rows.every((r) => r.art === 'kaufen' && r.gewicht_alt_pct === 0);
  return (
    <section className="section" aria-labelledby="opt-aenderungen">
      <SectionTitle id="opt-aenderungen">Empfohlene Veränderungen</SectionTitle>
      {erste ? (
        <p className="section-note">
          Erste Empfehlung dieser Variante: alle {f.integer(rows.length)} Aktien neu kaufen, mit den Anteilen aus der Tabelle. Ab der nächsten Empfehlung stehen
          hier Käufe, Verkäufe, Aufstockungen und Reduzierungen mit ihrer Begründung.
        </p>
      ) : null}
      {!rows.length ? <p className="section-note">Keine Veränderung gegenüber der letzten Empfehlung.</p> : null}
      {rows.length && !erste ? (
        <ul className="opt-changes">
          {rows.map((r) => (
            <li key={`${r.art}-${r.isin}`} className={`opt-change is-${r.art}`} data-art={r.art}>
              <span className="opt-change-art">{ART_TEXT[r.art]}</span>
              <span className="opt-change-name">
                <a href={`#/aktie/${r.isin}`}>{r.name ?? r.isin}</a>
              </span>
              <span className="opt-change-w">
                {r.art === 'kaufen' || r.art === 'nicht_aufnehmen' ? '' : `${f.plainPct(r.gewicht_alt_pct, 1)} → `}
                {r.art === 'verkaufen' ? '0 %' : r.art === 'nicht_aufnehmen' ? '' : f.plainPct(r.gewicht_neu_pct, 1)}
              </span>
              <span className="opt-change-grund">{r.grund}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function Balken({ titel, werte }: { titel: string; werte: Record<string, number> }) {
  const rows = anteile(werte);
  return (
    <div className="opt-bars-wrap">
      <h3 className="opt-sub">{titel}</h3>
      <ul className="opt-bars">
        {rows.map((r) => (
          <li key={r.name}>
            <span className="opt-bar-name">{r.name}</span>
            <span className="opt-bar-track" aria-hidden="true">
              <span className="opt-bar-fill" style={{ width: `${Math.max(1, Math.min(100, r.pct))}%` }} />
            </span>
            <span className="opt-bar-val">{f.plainPct(r.pct, 0)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Verteilung({ v }: { v: OptVariante }) {
  const k = v.kennzahlen!;
  return (
    <section className="section" aria-labelledby="opt-risiko">
      <SectionTitle id="opt-risiko">Risikoverteilung</SectionTitle>
      <KeyValues
        items={[
          ['Mittlere Korrelation', f.decimal(k.mittlere_korrelation, 2)],
          ['Wirksame Anzahl Positionen', f.decimal(k.effektive_anzahl, 1)],
          ['Schwankung des Depots', `± ${f.plainPct(k.schwankung_pct, 1)} über ${v.horizont_text}`],
          ['Ungünstiger Fall (5 %)', k.verlustszenario_pct === null ? 'zu wenig Historie' : pct1(k.verlustszenario_pct)],
        ]}
      />
      <div className="opt-bars-grid">
        <Balken titel="Branchen" werte={k.branchen} />
        <Balken titel="Währungen" werte={k.waehrungen} />
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ weitere Ansichten */

function Rangliste({ o, route }: { o: OptStand; route: Route }) {
  const rl = rangliste(o)!;
  const param = route.params.get('horizont');
  const vorhanden = HORIZONTE.filter((h) => rl.horizonte[h]);
  const erster = vorhanden.find((h) => (rl.horizonte[h]?.rangliste.length ?? 0) > 0) ?? vorhanden[0] ?? 'w12';
  const h = (param && (HORIZONTE as string[]).includes(param) ? param : erster) as Horizont;
  const x = rl.horizonte[h];
  const [alle, setAlle] = useState(false);
  const rows = x?.rangliste ?? [];
  return (
    <section className="section" aria-labelledby="opt-rangliste">
      <SectionTitle id="opt-rangliste">Aktuell aussichtsreichste Aktien für mein Depot</SectionTitle>
      <Segmented
        label="Prognosezeitraum"
        value={h}
        onChange={(y) => updateParams(route, { horizont: y })}
        options={vorhanden.map((y) => ({ value: y, label: KURZ[y], title: `${rl.horizonte[y]?.text}: ${rl.horizonte[y]?.belastbarkeit}` }))}
      />
      {x ? (
        <p className="section-note">
          {x.text}: <Belastbar b={x.belastbarkeit} />{' '}
          {x.rangliste.length ? `${f.integer(x.aktien)} liquide Aktien bewertet, die besten ${rows.length > 10 && !alle ? 10 : rows.length}:` : null}
        </p>
      ) : null}
      {x && !x.rangliste.length ? (
        <p className="section-note opt-nicht">
          Für {x.text} ist keine Prognose belastbar{x.grund ? ` – ${x.grund}` : ''}. Deshalb gibt es hier bewusst keine Rangliste.
        </p>
      ) : (
        <ol className="opt-rank">
          {rows.slice(0, alle ? rows.length : 10).map((z) => (
            <li key={z.isin} className="opt-rank-item" data-isin={z.isin}>
              <div className="opt-rank-head">
                <span className="opt-rank-platz">{z.platz}</span>
                <a className="opt-rank-name" href={`#/aktie/${z.isin}`}>
                  {z.name ?? z.isin}
                </a>
                <span className="opt-rank-fig">{pct1(z.erwartet_pct)}</span>
              </div>
              <p className="opt-rank-meta">
                Eignung {f.integer(z.eignung)} · Spanne {spanne(z)} · positiv in {f.plainPct(z.positiv_pct, 0)} der Fälle · Kosten {f.plainPct(z.kosten_pct, 2)}
                {z.branche ? ` · ${z.branche}` : ''}
              </p>
              <p className="opt-rank-grund">
                <Gruende z={z} />
              </p>
            </li>
          ))}
        </ol>
      )}
      {rows.length > 10 ? (
        <button type="button" className="btn btn-quiet" onClick={() => setAlle(!alle)}>
          {alle ? 'Nur die besten 10' : `Alle ${rows.length} zeigen`}
        </button>
      ) : null}
    </section>
  );
}

function Varianten({ o, gewaehlt, route }: { o: OptStand; gewaehlt: VarianteId; route: Route }) {
  const liste = variantenListe(o);
  const gleich = (a: OptVariante, b: OptVariante) =>
    a.verfuegbar && b.verfuegbar && a.positionen.length === b.positionen.length && a.positionen.every((p, i) => p.isin === b.positionen[i]?.isin && p.gewicht_pct === b.positionen[i]?.gewicht_pct);
  return (
    <section className="section" aria-labelledby="opt-varianten">
      <SectionTitle id="opt-varianten">Depotvarianten im Vergleich</SectionTitle>
      <div className="table-wrap">
        <table className="table pilot-table opt-var-table">
          <thead>
            <tr>
              <th scope="col">Variante</th>
              <th scope="col" className="n">
                Erwartet n. K.
              </th>
              <th scope="col" className="n">
                Ungünstig
              </th>
              <th scope="col" className="n">
                Aktien
              </th>
            </tr>
          </thead>
          <tbody>
            {liste.map((x) => {
              const doppelt = liste.find((y) => y.variante !== x.variante && VARIANTEN.indexOf(y.variante) < VARIANTEN.indexOf(x.variante) && gleich(x, y));
              return (
                <tr key={x.variante} className={x.variante === gewaehlt ? 'is-chosen' : undefined} data-variante={x.variante}>
                  <td>
                    <button type="button" className="opt-link" onClick={() => updateParams(route, { variante: x.variante === standardVariante(o) ? null : x.variante })}>
                      {x.name}
                    </button>
                    <br />
                    <span className="muted">
                      {x.horizont_text}
                      {x.variante === standardVariante(o) ? ' · Standard' : ''}
                      {doppelt ? ` · gleich wie „${doppelt.name}“` : ''}
                    </span>
                  </td>
                  {x.verfuegbar && x.kennzahlen ? (
                    <>
                      <td className="n">{depotErwartung(x.kennzahlen)}</td>
                      <td className="n">{x.kennzahlen.verlustszenario_pct === null ? '–' : pct1(x.kennzahlen.verlustszenario_pct)}</td>
                      <td className="n">{f.integer(x.positionen.length)}</td>
                    </>
                  ) : (
                    <td colSpan={3} className="muted">
                      nicht belastbar
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="section-note">Erwartet nach Kosten ± übliche Schwankung über den Zeitraum der Variante; „Ungünstig“: 5-%-Fall der Depotrendite in der Kurshistorie.</p>
    </section>
  );
}

function Kontrolle({ o }: { o: OptStand }) {
  const k = o.kontrolle;
  return (
    <section className="section" aria-labelledby="opt-kontrolle">
      <SectionTitle id="opt-kontrolle">Prognosekontrolle</SectionTitle>
      <p className="section-note">
        Jede tägliche Prognose wird mit Zeitpunkt, Datenstand und Modellversion unveränderlich gespeichert und nach Ablauf ihres Zeitraums mit der tatsächlichen
        Kursentwicklung verglichen.
      </p>
      {!k || !k.ausgewertet.length ? (
        <p className="section-note opt-nicht">
          Noch keine Prognose ausgewertet: {f.plural(k?.gespeichert ?? 0, 'Prognose', 'Prognosen')} gespeichert, die ersten (1 Woche) sind nach fünf
          Handelstagen prüfbar.
        </p>
      ) : (
        <div className="table-wrap">
          <table className="table pilot-table">
            <thead>
              <tr>
                <th scope="col">Zeitraum</th>
                <th scope="col" className="n">
                  Prognosen
                </th>
                <th scope="col" className="n">
                  Richtung
                </th>
                <th scope="col" className="n">
                  Erwartet / tatsächlich
                </th>
                <th scope="col" className="n">
                  In Spanne
                </th>
                <th scope="col" className="n">
                  Rang‑IC
                </th>
              </tr>
            </thead>
            <tbody>
              {k.ausgewertet.map((x) => (
                <tr key={`${x.modell_id}-${x.horizont}`}>
                  <td>{x.text}</td>
                  <td className="n">
                    {f.integer(x.prognosen)}
                    <br />
                    <span className="muted">{f.plural(x.tage, 'Tag', 'Tage')}</span>
                  </td>
                  <td className="n">{f.plainPct(x.richtung_pct, 0)}</td>
                  <td className="n">
                    {pct1(x.mittel_erwartet_pct)} / {pct1(x.mittel_ist_pct)}
                  </td>
                  <td className="n">{f.plainPct(x.in_spanne_pct, 0)}</td>
                  <td className="n">{ic(x.rang_ic)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {k ? <p className="section-note">{k.hinweis} Offen (Zeitraum noch nicht vorbei): {f.integer(k.offen)}.</p> : null}
    </section>
  );
}

/** Modus C (Auftrag 18, Abschnitt 14): Übernahme ins Pilotdepot nur nach den Freigaberegeln des Labors – nicht eingeschaltet. */
function Uebernahme({ o, stand }: { o: OptStand; stand: PilotStand }) {
  const v = standardVariante(o);
  const id = `${stand.modus === 'DEMO' ? 'demo-' : ''}f-empfehlung-${v}`;
  const d = stand.depots.find((x) => (x.id === id || x.id.startsWith(`${id}-`)) && x.status !== 'archiviert');
  return (
    <section className="section" aria-labelledby="opt-uebernahme">
      <SectionTitle id="opt-uebernahme">Übernahme in den Spielgeld-Piloten</SectionTitle>
      <p className="section-note">
        Nicht eingeschaltet: Das Pilotdepot übernimmt die Empfehlung nicht von selbst. Eine Übernahme kommt erst in Frage, wenn das Spielgeld-Musterdepot im
        Vorwärtstest die Freigaberegeln erfüllt – und auch dann nur mit deiner Freigabe.
      </p>
      {!o.freigabe ? (
        <p className="section-note">Freigaberegeln nicht lesbar.</p>
      ) : !d ? (
        <p className="section-note opt-nicht">Das Musterdepot startet mit dem nächsten täglichen Lauf; vorher gibt es nichts zu prüfen.</p>
      ) : (
        <FreigabeListe d={d} r={o.freigabe} />
      )}
    </section>
  );
}

function FreigabeListe({ d, r }: { d: import('../lib/pilot').PilotDepot; r: NonNullable<OptStand['freigabe']> }) {
  const p = freigabePruefung(d, r);
  return (
    <>
      <p className="section-note">
        <a href={`#/pilot/depot/${encodeURIComponent(d.id)}`}>{d.name}</a>: {p.erfuellt} von {p.zeilen.length} Bedingungen erfüllt
        {p.pruefbar < p.zeilen.length ? `, ${p.zeilen.length - p.pruefbar} noch nicht prüfbar` : ''}.
      </p>
      <ul className="opt-changes">
        {p.zeilen.map((z) => (
          <li key={z.bedingung} className={`opt-change ${z.erfuellt === true ? 'is-kaufen' : z.erfuellt === false ? 'is-verkaufen' : 'is-halten'}`}>
            <span className="opt-change-art">{z.erfuellt === true ? 'erfüllt' : z.erfuellt === false ? 'nicht erfüllt' : 'offen'}</span>
            <span className="opt-change-name">{z.bedingung}</span>
            <span className="opt-change-w">{z.ist}</span>
            <span className="opt-change-grund">Soll: {z.soll}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

function Forschung({ o, route }: { o: OptStand; route: Route }) {
  const fo = o.modell.forschung;
  return (
    <section className="section" aria-labelledby="opt-forschung">
      <SectionTitle id="opt-forschung">Strategieforschung</SectionTitle>
      <p className="section-note">
        Je Zeitraum: welche Informationen den späteren Erfolg zeitlich getrennt vorhersagten (Entwicklung → Validierung → Test), welches Modell im Walk‑forward
        bestand und wie zuverlässig die Prognose ist. Bestätigt heißt: nach Korrektur für {f.integer(fo.faktoren.zeilen.length)} gleichzeitige Prüfungen
        auffällig und in der Validierung in derselben Richtung.
      </p>
      {HORIZONTE.map((h) => {
        const x = fo.horizonte[h];
        if (!x) return null;
        const best = bestaetigte(o, h);
        return (
          <div key={h} className="opt-forschung" data-horizont={h}>
            <Disclosure
              defaultOpen={route.params.get('forschung') === h}
              summary={
                <>
                  <b>{x.text}</b> <Belastbar b={x.belastbarkeit} /> <span className="muted">· {f.plural(best.length, 'bestätigtes Merkmal', 'bestätigte Merkmale')}</span>
                </>
              }
            >
              <KeyValues
                items={[
                  ['Modell', x.modell ? `${x.walk_forward?.modelle[x.modell]?.name ?? x.modell}` : 'keines (kein Modell schlug das Nullmodell)'],
                  ['Begründung', nb(x.modell_grund ?? '–')],
                  ['Unabhängige Zeiträume', `${f.decimal(x.unabhaengig, 1)} (belastbar ab 20, eingeschränkt ab 8)`],
                  ['Entscheidungstage mit bekanntem Ergebnis', f.integer(x.tage_bekannt)],
                ]}
              />
              {x.walk_forward ? (
                <div className="table-wrap">
                  <table className="table pilot-table">
                    <caption>Modellvergleich im Walk‑forward ({f.integer(x.walk_forward.faltungen)} Faltungen)</caption>
                    <thead>
                      <tr>
                        <th scope="col">Modell</th>
                        <th scope="col" className="n">
                          Rang‑IC
                        </th>
                        <th scope="col" className="n">
                          t
                        </th>
                        <th scope="col" className="n">
                          Top‑Zehntel
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(x.walk_forward.modelle).map(([id, mp]) => (
                        <tr key={id} className={id === x.modell ? 'is-chosen' : undefined}>
                          <td>{mp.name}</td>
                          <td className="n">{ic(mp.ic)}</td>
                          <td className="n">{f.decimal(mp.t, 1)}</td>
                          <td className="n">{pp(mp.top_ueberschuss_pp)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              {best.length ? (
                <>
                  <h3 className="opt-sub">Bestätigte Merkmale (Rang‑IC Entwicklung / Validierung / Test)</h3>
                  <ul className="plain-list opt-faktoren">
                    {best.slice(0, 12).map((z) => (
                      <li key={z.merkmal}>
                        <b>{merkmalName(o, z.merkmal)}</b>
                        {z.richtung < 0 ? ' (niedriger ist besser)' : ''}: {ic(z.entwicklung.ic)} / {ic(z.validierung.ic)} / {ic(z.test.ic)}
                      </li>
                    ))}
                  </ul>
                  {best.length > 12 ? <p className="section-note">… und {f.integer(best.length - 12)} weitere.</p> : null}
                </>
              ) : null}
              {x.auswahl?.merkmale.length ? (
                <p className="section-note">
                  Im Modell (mit nachgewiesenem Zusatznutzen in der Validierung): {x.auswahl.merkmale.map((k) => merkmalName(o, k)).join(', ')}. Wegen
                  Überschneidung oder ohne Zusatznutzen ausgelassen: {f.integer(x.auswahl.uebersprungen.length)}.
                </p>
              ) : null}
              {x.kalibrierung ? (
                <div className="table-wrap">
                  <table className="table pilot-table">
                    <caption>Kalibrierung: tatsächliche Ergebnisse je Zehntel der Wertung (Walk‑forward)</caption>
                    <thead>
                      <tr>
                        <th scope="col">Zehntel</th>
                        <th scope="col" className="n">
                          Mittel
                        </th>
                        <th scope="col" className="n">
                          positiv
                        </th>
                        <th scope="col" className="n">
                          10–90 %
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {x.kalibrierung.dezile.map((d) => (
                        <tr key={d.dezil}>
                          <td>{d.dezil === 10 ? '10 (beste)' : d.dezil}</td>
                          <td className="n">{pct1(d.mittel_pct)}</td>
                          <td className="n">{f.plainPct(d.positiv_pct, 0)}</td>
                          <td className="n">{spanne(d)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              {x.rueckblick && x.rueckblick.perioden ? (
                <div className="table-wrap">
                  <table className="table pilot-table">
                    <caption>
                      Bestes historisch getestetes Depot: je {x.rueckblick.anzahl} Aktien gleich gewichtet, {f.integer(x.rueckblick.perioden)} unabhängige
                      Zeiträume, Kosten {f.plainPct(x.rueckblick.kosten_pct, 1)} je Zeitraum
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Strategie</th>
                        <th scope="col" className="n">
                          Mittel
                        </th>
                        <th scope="col" className="n">
                          Schlechtester
                        </th>
                        <th scope="col" className="n">
                          Besser als Welt‑ETF
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {STRATEGIE_REIHENFOLGE.filter((s) => x.rueckblick!.strategien[s]).map((s) => {
                        const r = x.rueckblick!.strategien[s];
                        return (
                          <tr key={s} className={s === x.rueckblick!.beste ? 'is-chosen' : undefined} data-strategie={s}>
                            <td>{r.text}</td>
                            <td className="n">{r.perioden ? pct1(r.mittel_pct) : '–'}</td>
                            <td className="n">{r.perioden ? pct1(r.schlechteste_pct) : '–'}</td>
                            <td className="n">{r.besser_als_welt === null || !r.perioden ? '–' : `${r.besser_als_welt} von ${r.perioden}`}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </Disclosure>
          </div>
        );
      })}
    </section>
  );
}

function Informationen({ o }: { o: OptStand }) {
  const m = o.modell;
  const z = m.zaehlung;
  const j = m.historie.jahre;
  const gruppen = useMemo(() => {
    const out = new Map<string, typeof m.inventar>();
    for (const x of m.inventar) out.set(x.gruppe, [...(out.get(x.gruppe) ?? []), x]);
    return [...out.entries()];
  }, [m]);
  return (
    <section className="section" aria-labelledby="opt-info">
      <SectionTitle id="opt-info">Geprüfte Informationen und Rechenaufwand</SectionTitle>
      <KeyValues
        items={[
          ['Aktien', `${f.integer(z.universum)} im Universum, ${f.integer(z.aktien_gerechnet)} mit Kursen gerechnet, ${f.integer(z.aktien_panel)} liquide untersucht, heute ${f.integer(z.aktien_heute)} bewertet`],
          ['Kennzahlen', `${f.integer(z.kennzahlen_verwendet)} von ${f.integer(z.kennzahlen_katalog)} aus dem zentralen Katalog als Merkmal (die übrigen mit Grund unten)`],
          ['Merkmale', `${f.integer(z.merkmale)} (Kennzahlen mit verschiedenen Zeitfenstern)`],
          ['Prüfungen', `${f.integer(z.pruefungen)} (Merkmal × Zeitraum), davon ${f.integer(z.bestaetigt)} unabhängig bestätigt`],
          ['Kombinationen und Modelle', `${f.integer(z.kombinationen)} Merkmalskombinationen im Zusatznutzen‑Test, ${f.integer(z.modelle)} Modellvergleiche im Walk‑forward`],
          ['Historie', `${f.integer(z.entscheidungstage)} Entscheidungstage (${f.isoDate(m.zeitraum.von)} – ${f.isoDate(m.zeitraum.bis)}, alle ${m.zeitraum.schritt} Handelstage), Kurse ab ${f.isoDate(m.zeitraum.kurse_ab)}`],
          ['Längere Kurshistorie', m.historie.geladen && j ? `für ${f.integer(m.historie.ergaenzt ?? 0)} Aktien ergänzt; mindestens 2 Jahre: ${f.integer(j.ab_2 ?? 0)}, 3 Jahre: ${f.integer(j.ab_3 ?? 0)}, 5 Jahre: ${f.integer(j.ab_5 ?? 0)}` : 'nicht geladen'],
          ['Rechenzeit', `${f.integer(Math.round(m.laufzeit_s.gesamt ?? 0))} s (Rechenkern ${f.integer(z.rechenkern)}-mal)`],
          ['Version', `${m.version} · Datenstand ${m.datenstand}`],
        ]}
      />
      <Disclosure summary={`Alle ${m.inventar.length} Kennzahlen des Katalogs: genutzt oder mit Grund ausgelassen`}>
        {gruppen.map(([g, xs]) => (
          <div key={g} className="opt-inventar">
            <h3 className="opt-sub">{g}</h3>
            <ul className="plain-list">
              {xs.map((x) => (
                <li key={x.kennzahl} data-kennzahl={x.kennzahl}>
                  <b>{x.name}</b> – {x.verwendet ? `Merkmal${x.merkmale.length > 1 ? `e (${x.merkmale.length} Fenster)` : ''}; historisch: ${x.historisch}` : x.grund}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </Disclosure>
      {m.forschung.redundanz.paare.length ? (
        <p className="section-note">
          {f.plural(m.forschung.redundanz.paare.length, 'Merkmalspaar überschneidet', 'Merkmalspaare überschneiden')} sich stark (Rangkorrelation ab{' '}
          {String(m.forschung.redundanz.rho).replace('.', ',')}) – von solchen Paaren kommt höchstens eines ins Modell.
        </p>
      ) : null}
    </section>
  );
}

/* ------------------------------------------------------------------ Depotparameter (Abschnitt 17) */

const VARIANTE_TEXT: Record<VarianteId, string> = {
  ausgewogen: 'Ausgewogen',
  rendite: 'Maximale Renditechance',
  stabil: 'Stabiler Aufwärtstrend',
  kurz: 'Kurzfristige Chancen',
  mittel: 'Mittelfristige Chancen',
  lang: 'Langfristige Chancen',
};
const HORIZONT_LANG: Record<Horizont, string> = { w1: '1 Woche', w2: '2 Wochen', w4: '1 Monat (4 Wochen)', w12: '3 Monate (12 Wochen)', w26: '6 Monate (26 Wochen)', w52: '1 Jahr (52 Wochen)' };

function Zahl({ label, wert, setWert, schritt = 1, hinweis }: { label: string; wert: number; setWert: (x: number) => void; schritt?: number; hinweis?: string }) {
  return (
    <label className="field opt-field">
      <span className="field-label">{label}</span>
      <input className="input" type="number" inputMode="decimal" step={schritt} value={Number.isFinite(wert) ? wert : ''} onInput={(ev: Event) => {
          const t = (ev.target as HTMLInputElement).value;
          setWert(t === '' ? NaN : Number(t.replace(',', '.')));
        }}
      />
      {hinweis ? <span className="field-hint">{hinweis}</span> : null}
    </label>
  );
}

/** Pflichtregeln des Spielgeld-Robos aus dem Stand (config/aktienpilot.yaml, risiko) – nur zur Anzeige; gerechnet wird auf dem Server. */
function grenzen(stand: PilotStand): string {
  const g = stand.grenzen ?? {};
  const teile = [
    g.max_je_aktie_pct !== undefined ? `höchstens ${f.decimal(g.max_je_aktie_pct, 0)} % je Aktie` : null,
    g.max_einzelaktien !== undefined ? `${f.integer(g.max_einzelaktien)} Einzelaktien` : null,
    g.max_je_branche_pct !== undefined ? `${f.decimal(g.max_je_branche_pct, 0)} % je Branche` : null,
  ].filter(Boolean);
  return teile.length ? ` (${teile.join(', ')})` : '';
}

function Parameter({ e, herkunft, o, stand }: { e: OptEinstellungen; herkunft: keyof typeof HERKUNFT_TEXT; o: OptStand; stand: PilotStand }) {
  const [x, setX] = useState<OptEinstellungen>(e);
  const set = <K extends keyof OptEinstellungen>(k: K, v: OptEinstellungen[K]) => setX((alt) => ({ ...alt, [k]: v }));
  const fehler = einstellungenFehler(x);
  const geaendert = JSON.stringify(x) !== JSON.stringify(e);
  return (
    <section className="section" aria-labelledby="opt-parameter">
      <SectionTitle id="opt-parameter">Depotparameter</SectionTitle>
      <KeyValues
        items={[
          ['Standardvariante', `${VARIANTE_TEXT[e.variante]} (${HERKUNFT_TEXT[herkunft]})`],
          ['Anlagehorizont der Risikovarianten', HORIZONT_LANG[(e.horizont ?? 'w12') as Horizont]],
          ['Aktien im Depot', f.integer(e.anzahl)],
          ['Spielgeldkapital', f.euro(e.kapital_eur)],
          ['Höchstgewicht je Aktie / Branche', `${f.plainPct(e.max_gewicht_pct, 0)} / ${f.plainPct(e.max_branche_pct, 0)}`],
          ['Mindestliquidität', `${f.money(e.min_umsatz_eur, 'EUR')} Ø Tagesumsatz`],
          ['Reserve', f.plainPct(e.reserve_pct, 0)],
          ['Umschichtung', `${UMSCHICHTUNG_TEXT[e.umschichtung]}; Tausch nur bei mindestens ${pp(e.mindestverbesserung_pp).replace('+', '')} Vorteil nach Kosten`],
        ]}
      />
      <p className="section-note">
        Risikoprofil und Spielgeldkapital kommen aus der <a href="#/pilot/einrichten">Einrichtung des Pilotdepots</a>, solange hier nichts anderes eingestellt
        ist. Das Spielgeld-Musterdepot der Standardvariante folgt der Empfehlung; dort gelten zusätzlich Stops und die Pflichtregeln des Robos
        {grenzen(stand)} – reichen sie nicht für ein Gewicht der Empfehlung, bleibt der Rest Guthaben (im Journal begründet).
      </p>
      <Disclosure summary="Depotparameter ändern">
        <div className="opt-form">
          <label className="field opt-field">
            <span className="field-label">Standardvariante</span>
            <select className="select" value={x.variante} onChange={(ev: Event) => set('variante', (ev.target as HTMLSelectElement).value as VarianteId)}>
              {VARIANTEN.map((v) => (
                <option key={v} value={v}>
                  {VARIANTE_TEXT[v]}
                </option>
              ))}
            </select>
          </label>
          <label className="field opt-field">
            <span className="field-label">Anlagehorizont</span>
            <select className="select" value={x.horizont ?? 'w12'} onChange={(ev: Event) => set('horizont', (ev.target as HTMLSelectElement).value as Horizont)}>
              {HORIZONTE.map((h) => (
                <option key={h} value={h}>
                  {HORIZONT_LANG[h]} – {o.modell.forschung.horizonte[h]?.belastbarkeit ?? 'nicht geprüft'}
                </option>
              ))}
            </select>
          </label>
          <Zahl label="Aktien im Depot (3–20)" wert={x.anzahl} setWert={(v) => set('anzahl', v)} />
          <Zahl label="Spielgeldkapital (EUR)" wert={x.kapital_eur} setWert={(v) => set('kapital_eur', v)} schritt={500} />
          <Zahl label="Höchstgewicht je Aktie (%)" wert={x.max_gewicht_pct} setWert={(v) => set('max_gewicht_pct', v)} />
          <Zahl label="Höchstgewicht je Branche (%)" wert={x.max_branche_pct} setWert={(v) => set('max_branche_pct', v)} />
          <Zahl label="Mindestliquidität (Mio. EUR Ø Tagesumsatz)" wert={x.min_umsatz_eur / 1e6} setWert={(v) => set('min_umsatz_eur', v * 1e6)} schritt={0.5} />
          <Zahl label="Reserve (%)" wert={x.reserve_pct} setWert={(v) => set('reserve_pct', v)} />
          <label className="field opt-field">
            <span className="field-label">Umschichtung</span>
            <select className="select" value={x.umschichtung} onChange={(ev: Event) => set('umschichtung', (ev.target as HTMLSelectElement).value as OptEinstellungen['umschichtung'])}>
              <option value="taeglich">{UMSCHICHTUNG_TEXT.taeglich}</option>
              <option value="woechentlich">{UMSCHICHTUNG_TEXT.woechentlich}</option>
              <option value="signal">{UMSCHICHTUNG_TEXT.signal}</option>
            </select>
          </label>
          <Zahl label="Mindestvorteil eines Tauschs (Prozentpunkte)" wert={x.mindestverbesserung_pp} setWert={(v) => set('mindestverbesserung_pp', v)} schritt={0.5} />
          <Zahl label="Kleinere Gewichtsänderungen nicht umsetzen (Prozentpunkte)" wert={x.toleranz_pp} setWert={(v) => set('toleranz_pp', v)} schritt={0.5} />
        </div>
        {fehler ? (
          <p className="field-error" role="alert">
            {fehler}
          </p>
        ) : null}
        {!fehler && geaendert ? (
          <PilotSenden
            art="optimierer_einstellungen"
            inhalt={{ ...x }}
            bezeichnung={`Depotparameter: ${VARIANTE_TEXT[x.variante]}, ${x.anzahl} Aktien`}
            label="Depotparameter an den Robo senden"
            primary
          />
        ) : null}
        <p className="section-note">Wirkt ab der nächsten täglichen Empfehlung; bisherige Empfehlungen und Prognosen bleiben unverändert gespeichert.</p>
      </Disclosure>
    </section>
  );
}
