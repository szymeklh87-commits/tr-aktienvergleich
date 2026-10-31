/* Bericht je Spielgelddepot (Abschnitte 14, 21, 22): fertige Kennzahlen aus dem täglichen Lauf mit Gründen für nicht definierte
 * Werte, Vergleich, Rückgang, Monatsrenditen, Hälftenvergleich, Block-Bootstrap, Prüfhürden, Warnungen, Steuer-Modellrechnung,
 * Annahmen; Export aller Ausführungen als CSV (mit FIFO-Losen) und des Berichts als eigenständige HTML-Datei. */

import { MiniChart } from '../components/charts';
import { Disclosure, EmptyState, KeyValues, Notice } from '../components/ui';
import { downloadText, safeFilename } from '../lib/csv';
import * as f from '../lib/format';
import type { PilotDepot, PilotStand } from '../lib/pilot';
import { ausfuehrungenCsv, berichtHtml, huerdeWert, huerdeZeichen, KENNZAHL_ZEILEN, kennzahlWert, monatText, zahl } from '../lib/pilotbericht';

function Exporte({ d, stand }: { d: PilotDepot; stand: PilotStand }) {
  const n = d.ausfuehrungen?.length ?? 0;
  return (
    <div className="pilot-actions">
      <button
        type="button"
        className="btn"
        disabled={!n}
        onClick={() => downloadText(`${safeFilename(`spielgeld-ausfuehrungen-${d.id}-${stand.datentag}`)}.csv`, ausfuehrungenCsv(d, stand))}
      >
        Ausführungen als CSV ({f.integer(n)})
      </button>
      <button
        type="button"
        className="btn"
        onClick={() => downloadText(`${safeFilename(`spielgeld-bericht-${d.id}-${stand.datentag}`)}.html`, berichtHtml(d, stand), 'text/html;charset=utf-8')}
      >
        Bericht als HTML-Datei
      </button>
    </div>
  );
}

export function DepotBericht({ d, stand }: { d: PilotDepot; stand: PilotStand }) {
  const b = d.bericht;
  if (!b || b.grund || !b.zeitraum) {
    return (
      <>
        <EmptyState title="Noch kein Bericht">{b?.grund ? `${b.grund}.` : 'Der Bericht kommt mit dem nächsten Spielgeld-Stand.'}</EmptyState>
        <Exporte d={d} stand={stand} />
      </>
    );
  }
  const z = b.zeitraum;
  const rg = b.rueckgang;
  const pts = rg ? rg.tag.map((t, i) => ({ day: f.isoToDay(t), close: rg.pct[i] ?? Number.NaN, open: null, high: null, low: null, volume: null, closeRaw: null })).filter((p) => Number.isFinite(p.close)) : [];
  const tiefst = pts.length ? pts.reduce((a, p) => (p.close < a.close ? p : a)) : null;
  const bo = b.bootstrap;
  const st = b.steuern;
  return (
    <div className="pilot-bericht">
      <p className="section-note">
        {f.isoDate(z.von)} bis {f.isoDate(z.bis)}: {f.integer(z.kalendertage)} Kalendertage, {f.integer(z.renditetage)} Tagesrenditen; vollständig bewertet an{' '}
        {f.integer(b.bewertungstage - b.unvollstaendig)} von {f.integer(b.bewertungstage)} Tagen. Alle Werte nach simulierten Kosten, ohne Dividenden.
      </p>
      <Exporte d={d} stand={stand} />
      {b.warnungen?.length ? (
        <Notice tone="warn" compact title="Vorsicht beim Lesen">
          <ul className="plain-list">
            {b.warnungen.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Notice>
      ) : null}
      <h3 className="subsection-title">Kennzahlen</h3>
      <KeyValues
        items={KENNZAHL_ZEILEN.map((k) => {
          const w = kennzahlWert(b, k);
          return [
            k.label,
            w.grund ? (
              <>
                nicht definiert
                <br />
                <span className="muted">{w.grund}</span>
              </>
            ) : (
              w.text
            ),
          ];
        })}
      />
      <p className="section-note">
        Risikofreier Zins für Sharpe und Sortino: {b.zins?.quelle ?? 'nicht konfiguriert'}
        {b.zins?.rendite_pct !== undefined && b.zins?.rendite_pct !== null ? ` (${f.signedPctValue(b.zins.rendite_pct, 3)} im Zeitraum)` : b.zins?.grund ? ` – ${b.zins.grund}` : ''}.
      </p>
      {b.vergleiche?.length ? (
        <>
          <h3 className="subsection-title">Vergleich im selben Zeitraum</h3>
          <ul className="plain-list">
            {b.vergleiche.map((v) => (
              <li key={v.depot}>
                <a href={`#/pilot/depot/${encodeURIComponent(v.depot)}`}>{v.name}</a>
                <br />
                <span className="muted">
                  {v.grund
                    ? v.grund
                    : `${f.isoDate(v.von)} – ${f.isoDate(v.bis)}: eigen ${f.signedPctValue(v.eigen_pct ?? null, 2)}, Vergleich ${f.signedPctValue(v.vergleich_pct ?? null, 2)}, Abstand ${zahl(v.abstand_pp ?? null, 2)} Prozentpunkte; größter Rückgang des Vergleichs ${f.plainPct(v.max_rueckgang_vergleich_pct ?? null, 1)}`}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <h3 className="subsection-title">Rückgang vom Höchststand</h3>
      <MiniChart
        pts={pts}
        gaps={[]}
        yDomain={tiefst ? [Math.min(tiefst.close, -0.5), 0] : null}
        height={84}
        label={`Rückgang vom Höchststand je Bewertungstag, tiefster Punkt ${tiefst ? f.signedPctValue(tiefst.close, 1) : '–'}`}
        mode="absolut"
        emptyText="Kein Rückgang messbar"
      />
      <p className="section-note">
        {tiefst && tiefst.close < 0 ? `Tiefster Punkt ${f.signedPctValue(tiefst.close, 1)} am ${f.day(tiefst.day)}. ` : 'Bisher kein Rückgang. '}
        Gemessen am Renditeindex (Zu- und Abflüsse herausgerechnet).
      </p>
      {b.monate?.length ? (
        <>
          <h3 className="subsection-title">Monatsrenditen</h3>
          <div className="table-wrap">
            <table className="table pilot-table">
              <thead>
                <tr>
                  <th>Monat</th>
                  <th className="n">Rendite</th>
                  <th className="n">Tage</th>
                </tr>
              </thead>
              <tbody>
                {b.monate.map((m) => (
                  <tr key={m.monat}>
                    <td>
                      {monatText(m.monat)}
                      {m.angebrochen ? <span className="muted"> (angebrochen)</span> : null}
                    </td>
                    <td className="n">{f.signedPctValue(m.rendite_pct, 2)}</td>
                    <td className="n">{f.integer(m.tage)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
      <h3 className="subsection-title">Prüfhürden</h3>
      <ul className="plain-list">
        {(b.huerden ?? []).map((x) => (
          <li key={x.id}>
            <span className={`badge badge-wrap ${x.erfuellt === false ? 'badge-warn' : ''}`}>{huerdeZeichen(x.erfuellt)}</span> {x.text}
            <br />
            <span className="muted">
              Wert {huerdeWert(x)}
              {x.grund ? ` · ${x.grund}` : ''}
            </span>
          </li>
        ))}
      </ul>
      <p className="section-note">Hürden aus Abschnitt 22 nur zur Einordnung – Echtgeld bleibt ausgeschlossen, auch wenn alle erfüllt sind.</p>
      <Disclosure summary="Hälftenvergleich und Walk-Forward">
        <p className="section-note">
          {b.haelften?.grund
            ? b.haelften.grund
            : `Erste Hälfte (${f.isoDate(b.haelften?.erste?.von)} – ${f.isoDate(b.haelften?.erste?.bis)}) ${f.signedPctValue(b.haelften?.erste?.rendite_pct ?? null, 2)}, zweite Hälfte (${f.isoDate(b.haelften?.zweite?.von)} – ${f.isoDate(b.haelften?.zweite?.bis)}) ${f.signedPctValue(b.haelften?.zweite?.rendite_pct ?? null, 2)}.`}{' '}
          {b.walk_forward}
        </p>
      </Disclosure>
      <Disclosure summary="Block-Bootstrap (Verlaufsrisiko)">
        {!bo || bo.grund ? (
          <p className="section-note">{bo?.grund ?? 'nicht berechnet'}</p>
        ) : (
          <>
            <KeyValues
              items={[
                ['Rendite (5 / 50 / 95 %)', `${f.signedPctValue(bo.rendite_pct?.p5 ?? null, 1)} / ${f.signedPctValue(bo.rendite_pct?.p50 ?? null, 1)} / ${f.signedPctValue(bo.rendite_pct?.p95 ?? null, 1)}`],
                ['Größter Rückgang (5 / 50 / 95 %)', `${f.plainPct(bo.max_rueckgang_pct?.p5 ?? null, 1)} / ${f.plainPct(bo.max_rueckgang_pct?.p50 ?? null, 1)} / ${f.plainPct(bo.max_rueckgang_pct?.p95 ?? null, 1)}`],
              ]}
            />
            <p className="section-note">
              {f.integer(bo.pfade ?? 0)} zufällige Pfade aus Blöcken von {bo.block} aufeinanderfolgenden Tagesrenditen (Startwert {bo.startwert}, reproduzierbar). Das zeigt, wie
              unterschiedlich derselbe Verlauf hätte ausgehen können – es beweist keinen Handelsvorteil.
            </p>
          </>
        )}
      </Disclosure>
      {st ? (
        <Disclosure summary="Steuer-Modellrechnung">
          {st.jahre.length ? (
            <div className="table-wrap">
              <table className="table pilot-table">
                <thead>
                  <tr>
                    <th>Jahr</th>
                    <th className="n">steuerpflichtig</th>
                    <th className="n">Steuer</th>
                  </tr>
                </thead>
                <tbody>
                  {st.jahre.map((j) => (
                    <tr key={j.jahr}>
                      <td>
                        {j.jahr}
                        <br />
                        <span className="muted">
                          Aktien {f.euro(j.aktien_gewinne_eur, true)} / {f.euro(j.aktien_verluste_eur, true)}, Fonds {f.euro(j.fonds_ergebnis_eur, true)}
                          {j.unbekannte_kosten ? `, ${j.unbekannte_kosten} mit unbekannten Kosten` : ''}
                        </span>
                      </td>
                      <td className="n">{f.euro(j.steuerpflichtig_eur, true)}</td>
                      <td className="n">{f.euro(j.steuer_eur, true)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="section-note">Noch keine realisierten Ergebnisse.</p>
          )}
          {st.verkauf_am_ende ? (
            <p className="section-note">
              Angenommene Veräußerung aller offenen Positionen am Ende ({st.verkauf_am_ende.jahr}): zusätzlich {f.euro(st.verkauf_am_ende.zusaetzliche_steuer_eur, true)}
              {st.verkauf_am_ende.unbekannte_kosten ? ` (${st.verkauf_am_ende.unbekannte_kosten} Positionen mit unbekannten Kosten nicht enthalten)` : ''}.
            </p>
          ) : null}
          <ul className="plain-list section-note">
            {st.hinweise.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </Disclosure>
      ) : null}
      <Disclosure summary="Annahmen und Reproduzierbarkeit">
        <ul className="plain-list section-note">
          {(b.annahmen ?? []).map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
        {b.reproduzierbar ? (
          <p className="section-note">
            Datenstand {b.reproduzierbar.datenstand ?? '–'} · Programm {b.reproduzierbar.programm} · Bericht {b.reproduzierbar.bericht} · Zufallsstartwert {b.reproduzierbar.startwert} ·
            Regeln {b.reproduzierbar.regeln.join(', ') || '–'}
          </p>
        ) : null}
      </Disclosure>
    </div>
  );
}
