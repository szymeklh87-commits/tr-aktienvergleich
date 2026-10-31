/* Kursabgleich mit den Kursarchiven der Börsen (ab 1.20.0).
 *
 * Simons Auftrag vom 25.10.2026, 19:31 Uhr (erneut 31.10.2026): „Liefere die aktualisierte App mit einer kurzen
 * Gegenüberstellung: tatsächlich korrigierte Kurse, geänderte Spitzenplätze und verbleibende ungeklärte Fälle.“
 *
 * Alles hier stammt aus dem Stand selbst (kursabgleich.bin, vom täglichen Lauf geschrieben): je Korrektur der bisherige Kurs der
 * Hauptquelle, der Kurs der Börse, Aktie, Handelsplatz, Datum, Quelle und Grund. Die Ranglisten der App rechnen bereits mit den
 * korrigierten Kursen; die Gegenüberstellung zeigt, was sich dadurch gegenüber der Hauptquelle allein geändert hat. */

import { useMemo, useState } from 'react';
import { ErrorNote, KeyValues, Loading, Notice, SectionTitle } from '../components/ui';
import * as f from '../lib/format';
import { buildHash } from '../lib/router';
import { useAsync } from '../lib/useAsync';
import type { Instruments, KursabgleichData, KursCorrection } from '../lib/types';
import { useApp } from '../state/AppState';

const PAGE = 60;

const REASON_SHORT: Record<string, string> = {
  amtlicher_schlusskurs: 'anderer Schlusskurs als die Börse',
  tag_ohne_umsatz: 'Tag ohne Umsatz an der Börse',
  fehlender_kurstag: 'Handelstag fehlte',
  umsatz_laut_boerse: 'Umsatz laut Börse',
};

const STATUS_SHORT: Record<string, string> = {
  uebernommen: 'Kurse der Börse übernommen',
  bestaetigt: 'bestätigt, keine Abweichung',
  nicht_vergleichbar: 'nicht vergleichbar',
  abdeckung_unvollstaendig: 'Börse deckt den Zeitraum nicht ab',
  ohne_kurse: 'Quelle ohne Kurse',
};

function groupLabel(g: string): string {
  return g === 'A' ? 'Gruppe A (alle Aktien)' : 'Gruppe B (Ø Umsatz ≥ Schwelle)';
}

/** „30 Tage, alle Aktien, 50/50“ – Gewichtung Gleichmäßigkeit/Rendite wie in den Ranglisten. */
export function rankingLabel(h: number, group: string, w: number): string {
  return `${h} ${h === 1 ? 'Tag' : 'Tage'}, ${groupLabel(group)}, ${w}/${100 - w}`;
}

function stockName(instruments: Instruments | null, idx: number | null | undefined, isin?: string | null): string {
  if (instruments && idx !== null && idx !== undefined && instruments.name[idx]) return instruments.name[idx];
  return isin ?? '–';
}

function StockLink({ instruments, idx, isin }: { instruments: Instruments | null; idx: number | null | undefined; isin?: string | null }) {
  const code = isin ?? (instruments && idx !== null && idx !== undefined ? instruments.isin[idx] : null);
  const name = stockName(instruments, idx, code);
  if (!code) return <>{name}</>;
  return (
    <a href={buildHash(`/aktie/${code}`)}>
      {name} <span className="muted">{code}</span>
    </a>
  );
}

function change(c: KursCorrection): string {
  if (c.alt === null || c.alt === undefined || !c.alt) return 'neu';
  return f.signedPctValue(100 * (c.alt / c.neu - 1), 2);
}

export function CorrectionsView() {
  const { manifest, client, instruments } = useApp();
  const available = Boolean(manifest?.kursabgleich);
  const state = useAsync<KursabgleichData>(available && client ? () => client.kursabgleich() : null, [client?.id, available]);
  const [shown, setShown] = useState(PAGE);
  const [onlyTop, setOnlyTop] = useState(true);
  const data = state.data;

  const volumeDays = useMemo(() => (data ? data.faelle.reduce((n, k) => n + k.korrekturen.filter((c) => c.grund === 'umsatz_laut_boerse').length, 0) : 0), [data]);
  const rows = useMemo(() => {
    if (!data) return [];
    const out: { idx: number | null; isin: string; boerse: string | null; quelle: string; c: KursCorrection }[] = [];
    for (const k of data.faelle) {
      for (const c of k.korrekturen) {
        if (c.grund === 'umsatz_laut_boerse') continue;
        out.push({ idx: k.idx, isin: k.isin, boerse: k.boerse, quelle: k.quelle, c });
      }
    }
    return out;
  }, [data]);

  const topIdx = useMemo(() => {
    const set = new Set<number>();
    for (const r of data?.ranglisten ?? []) for (const i of [...r.vorher, ...r.nachher]) set.add(i);
    for (const g of data?.luecken ?? []) set.add(g.idx);
    return set;
  }, [data]);

  if (!manifest) return null;
  if (!available) {
    return (
      <div className="view">
        <Notice tone="info" title="Für diesen Stand liegt kein Kursabgleich vor">
          <p>Der Abgleich mit den Kursarchiven der Börsen gehört ab Version 1.20.0 zu jedem täglichen Lauf. Ältere Stände wurden ohne ihn gerechnet.</p>
        </Notice>
      </div>
    );
  }
  const s = manifest.kursabgleich!;
  const sourceName = (key: string) => data?.quellen.find((q) => q.key === key)?.name ?? key;
  const filtered = onlyTop ? rows.filter((r) => r.idx !== null && (topIdx.has(r.idx) || (instruments?.best_r[r.idx] ?? null) !== null)) : rows;
  const leadChanges = (data?.ranglisten ?? []).filter((r) => r.platz1_anders);
  const unit = (idx: number | null) => (instruments && idx !== null ? instruments.price_unit[idx] ?? instruments.currency[idx] : null);

  return (
    <div className="view">
      <header className="view-head">
        <p className="lede">
          Die App vergleicht die Kurse ihrer Hauptquelle (Yahoo) jeden Tag mit den Kursarchiven der Börsen, wo diese frei zugänglich sind. Weicht ein Kurs ab, rechnet die App
          mit dem amtlichen Kurs der Börse. Hier steht jede Korrektur dieses Stands, was sie an den Ranglisten geändert hat und wo kein Abgleich möglich ist.
        </p>
      </header>

      <section className="section" aria-labelledby="ka-regel">
        <SectionTitle id="ka-regel">Regel</SectionTitle>
        <KeyValues
          items={[
            ['Kursdefinition', s.kursdefinition],
            ['Regel', `${s.regel}: übernommen wird nur, wenn Aktie, Gattung, Börse, Währung und Bereinigung übereinstimmen und die Börse den ganzen Rechenzeitraum (${s.zeitraum_tage} Tage) abdeckt. „Gleich“ heißt gleich bis auf die letzte veröffentlichte Nachkommastelle – keine prozentuale Toleranz, keine Mittelwerte.`],
            ['Abgerufen', `alle Aktien an der Warschauer Börse; an Toronto, TSX Venture und Nasdaq die Aktien unter den ersten ${s.erste_plaetze} einer Rangliste (${s.durchgaenge} ${s.durchgaenge === 1 ? 'Durchgang' : 'Durchgänge'})`],
          ]}
        />
        {data ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Quelle</th>
                  <th scope="col">Rolle</th>
                  <th scope="col">Kursdefinition der Quelle</th>
                </tr>
              </thead>
              <tbody>
                {data.quellen.filter((q) => q.key !== 'demo_boerse' || q.key in s.quellen).map((q) => (
                  <tr key={q.key}>
                    <td>
                      {q.name}
                      <div className="muted">{q.betreiber}</div>
                    </td>
                    <td>{q.rolle === 'amtlich' ? 'amtlich (Börse)' : 'nur Vergleich'}</td>
                    <td>{q.definition}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <section className="section" aria-labelledby="ka-zahlen">
        <SectionTitle id="ka-zahlen">Ergebnis dieses Stands</SectionTitle>
        <KeyValues
          items={[
            ['Aktien mit korrigiertem Kurs', f.integer(s.aktien_mit_kurskorrektur)],
            ...(s.aktien_mit_korrektur_kurs_oder_umsatz !== undefined
              ? ([['Aktien mit korrigiertem Kurs oder Umsatz', f.integer(s.aktien_mit_korrektur_kurs_oder_umsatz)]] as [string, string][])
              : []),
            ['Ranglisten mit anderem Platz 1', `${f.integer(s.ranglisten.platz1_anders ?? 0)} von ${f.integer(s.ranglisten.ranglisten ?? 0)}`],
            ['Ranglisten mit anderen ersten 10', f.integer(s.ranglisten.erste10_andere_aktien ?? 0)],
            ...Object.entries(s.quellen).map(([key, c]): [string, string] => [
              sourceName(key),
              `${f.integer(c.notierungen ?? 0)} Aktien abgeglichen: ${Object.entries(c)
                .filter(([k]) => k.startsWith('status:'))
                .map(([k, v]) => `${STATUS_SHORT[k.slice(7)] ?? k.slice(7)} ${f.integer(v)}`)
                .join(', ')}`,
            ]),
          ]}
        />
      </section>

      <section className="section" aria-labelledby="ka-korrekturen">
        <SectionTitle id="ka-korrekturen">Korrigierte Kurse</SectionTitle>
        {state.loading && !data ? <Loading /> : null}
        {state.error ? <ErrorNote error={state.error} /> : null}
        {data ? (
          <>
            <p className="section-note">
              {f.integer(rows.length)} Kurstage mit dem Kurs der Börse statt des Kurses der Hauptquelle. „Abweichung“: bisheriger Kurs gegenüber dem Kurs der Börse.
              {volumeDays > 0
                ? ` Dazu ${f.integer(volumeDays)} Tage, an denen der Umsatz laut Börse gilt (die Hauptquelle meldete keinen Umsatz an einem Handelstag oder Umsatz an einem Tag ohne Abschluss) – das entscheidet mit, ob ein Zeitraum in die Rangliste kommt.`
                : ''}
            </p>
            <label className="check">
              <input type="checkbox" checked={onlyTop} onChange={(e: Event) => setOnlyTop((e.target as HTMLInputElement).checked)} /> nur Aktien in Ranglisten dieses Stands
            </label>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Aktie</th>
                    <th scope="col">Datum</th>
                    <th scope="col" className="n">
                      bisher
                    </th>
                    <th scope="col" className="n">
                      Börse
                    </th>
                    <th scope="col" className="n">
                      Abweichung
                    </th>
                    <th scope="col">Grund</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.slice(0, shown).map((r) => (
                    <tr key={`${r.isin}-${r.c.d}-${r.c.grund}`}>
                      <td>
                        <StockLink instruments={instruments} idx={r.idx} isin={r.isin} />
                        <div className="muted">
                          {r.boerse ?? '–'} · {sourceName(r.quelle)}
                        </div>
                      </td>
                      <td>{f.day(r.c.d)}</td>
                      <td className="n">{r.c.alt === null ? '–' : f.price(r.c.alt, unit(r.idx))}</td>
                      <td className="n">{f.price(r.c.neu, unit(r.idx))}</td>
                      <td className="n">{change(r.c)}</td>
                      <td>{REASON_SHORT[r.c.grund] ?? r.c.grund}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {filtered.length > shown ? (
              <button type="button" className="btn" onClick={() => setShown(shown + PAGE)}>
                Weitere {f.integer(Math.min(PAGE, filtered.length - shown))} von {f.integer(filtered.length - shown)} anzeigen
              </button>
            ) : null}
          </>
        ) : null}
      </section>

      <section className="section" aria-labelledby="ka-ranglisten">
        <SectionTitle id="ka-ranglisten">Geänderte Spitzenplätze</SectionTitle>
        {data ? (
          leadChanges.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Rangliste</th>
                    <th scope="col">Platz 1 nur mit Hauptquelle</th>
                    <th scope="col">Platz 1 jetzt</th>
                  </tr>
                </thead>
                <tbody>
                  {leadChanges.map((r) => (
                    <tr key={`${r.h}-${r.gruppe}-${r.w}`}>
                      <td>
                        <a href={buildHash('/ranking', { h: r.h, g: r.gruppe.toLowerCase(), w: r.w })}>{rankingLabel(r.h, r.gruppe, r.w)}</a>
                      </td>
                      <td>{stockName(instruments, r.vorher[0])}</td>
                      <td>
                        {stockName(instruments, r.nachher[0])}
                        {r.ausloeser.length === 0 ? <div className="muted">über die Plätze anderer Aktien</div> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="section-note">Kein Platz 1 hat sich durch den Abgleich geändert.</p>
          )
        ) : null}
        {data && (s.ranglisten.erste10_andere_aktien ?? 0) > 0 ? (
          <p className="section-note">Dazu {f.integer(s.ranglisten.erste10_andere_aktien ?? 0)} Ranglisten mit anderen Aktien unter den ersten 10.</p>
        ) : null}
      </section>

      <section className="section" aria-labelledby="ka-luecken">
        <SectionTitle id="ka-luecken">Ohne Abgleich mit der Börse</SectionTitle>
        {data ? (
          <>
            <p className="section-note">
              Aktien unter den ersten 10 einer Rangliste, deren Kurse nicht mit dem Archiv ihrer Börse abgeglichen sind – meist, weil die Börse ihre amtlichen Schlusskurse
              nur kostenpflichtig abgibt. Diese Kurse sind nicht falsch, aber nicht bestätigt. {f.integer(data.luecken_gesamt)} Aktien.
            </p>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Aktie</th>
                    <th scope="col" className="n">
                      Platz 1
                    </th>
                    <th scope="col">Warum kein Abgleich</th>
                  </tr>
                </thead>
                <tbody>
                  {data.luecken.slice(0, 40).map((g) => (
                    <tr key={g.isin}>
                      <td>
                        <StockLink instruments={instruments} idx={g.idx} isin={g.isin} />
                        <div className="muted">{g.boerse ?? '–'}</div>
                      </td>
                      <td className="n">{f.integer(g.platz1)}</td>
                      <td>{g.fehlende_quelle ?? (g.grund === 'keine_freie_amtliche_quelle' ? 'keine frei zugängliche amtliche Quelle' : (data.nicht_vergleichbar[g.grund.split(':')[1] ?? ''] ?? STATUS_SHORT[g.grund.split(':')[0]] ?? g.grund))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </section>

      {data && data.us_zuordnung.length ? (
        <section className="section" aria-labelledby="ka-us">
          <SectionTitle id="ka-us">US-Börsenzuordnung</SectionTitle>
          <p className="section-note">
            Notierungen, deren Börse laut Wertpapierliste von Nasdaq Trader (alle börsennotierten US-Werte) eine andere ist oder die dort fehlen (dann meist OTC-Handel).
            Für sie gilt kein offizieller Schlusskurs der Nasdaq.
          </p>
          <ul className="plain-list">
            {data.us_zuordnung.slice(0, 40).map((u) => (
              <li key={`${u.isin}-${u.ergebnis}`}>
                <StockLink instruments={instruments} idx={u.idx} isin={u.isin} />: {u.ergebnis === 'nicht_gelistet' ? 'nicht börsennotiert (OTC oder nicht mehr gelistet)' : `laut Liste ${u.ergebnis.split(':')[1]}`}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
