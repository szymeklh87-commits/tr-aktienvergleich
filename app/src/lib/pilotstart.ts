/* Robo-Startseite (Gesamtauftrag vom 31.10.2026, Abschnitt 16): die zwölf Angaben „auf einen Blick“ aus dem Spielgeld-Stand
 * und dem Status der Website – reine Funktion, damit die Ansicht nur darstellt und ein Test die Herleitung prüft. */

import * as f from './format';
import { abstandPp, benchmark, STUFE_TEXT, type DepotGruppe, type PilotAusfuehrung, type PilotDepot, type PilotStand } from './pilot';
import type { Status } from './types';

export interface Kachel {
  id: string;
  titel: string;
  wert: string;
  zusatz: string;
  ton?: 'plus' | 'minus' | 'warn';
  link?: string;
  /** Wert ist ein Name oder Satz (kleiner, mit Silbentrennung) statt einer Zahl */
  text?: boolean;
}

/** Rückgänge sind positiv gespeichert (25 = −25 %); −0 nie als „-0,0 %“ zeigen. */
const rueckgang = (v: number | null | undefined) => f.plainPct(v === null || v === undefined ? null : Math.abs(v), 1);

function ton(v: number | null | undefined): Kachel['ton'] {
  return v === null || v === undefined || !Number.isFinite(v) || v === 0 ? undefined : v > 0 ? 'plus' : 'minus';
}

function depotLink(d: PilotDepot): string {
  return `#/pilot/depot/${encodeURIComponent(d.id)}`;
}

/** Neueste Ausführung einer Art über alle Depots einer Gruppe (Datum, dann Zeit). */
export function letzteAusfuehrung(depots: PilotDepot[], art: 'kauf' | 'verkauf'): { a: PilotAusfuehrung; d: PilotDepot } | null {
  let best: { a: PilotAusfuehrung; d: PilotDepot } | null = null;
  for (const d of depots) {
    for (const a of d.ausfuehrungen ?? []) {
      if (a.art !== art) continue;
      const key = `${a.datum}T${a.zeit ?? ''}`;
      if (!best || key > `${best.a.datum}T${best.a.zeit ?? ''}`) best = { a, d };
    }
  }
  return best;
}

/** Warnungen des Vorwärtstests: Pause, Verluststufe, unvollständige Bewertung, gescheiterter oder alter Lauf. */
export function warnungen(g: DepotGruppe, status: Status | null): string[] {
  const out: string[] = [];
  const p = g.pilot;
  if (p?.pausiert) out.push('Neue Käufe pausiert');
  if (p && p.verlust?.stufe && p.verlust.stufe !== 'normal') out.push(`Verluststufe: ${STUFE_TEXT[p.verlust.stufe] ?? p.verlust.stufe}`);
  const unvollstaendig = [p, ...g.forschung].filter((d): d is PilotDepot => Boolean(d?.wert && !d.wert.vollstaendig));
  if (unvollstaendig.length) out.push(`Bewertung unvollständig in ${f.plural(unvollstaendig.length, 'Depot', 'Depots')} (Kurs fehlt)`);
  const run = status?.last_run;
  if (run && ['fehlgeschlagen', 'abgebrochen'].includes(run.status)) out.push(`Letzter Lauf: ${f.runStatus(run.status)}`);
  return out;
}

export function roboKacheln(stand: PilotStand, g: DepotGruppe, status: Status | null): Kachel[] {
  const p = g.pilot;
  const welt = benchmark(g);
  const vorwaerts = [p, ...g.forschung].filter((d): d is PilotDepot => Boolean(d));
  const out: Kachel[] = [];
  if (p) {
    const gesamt = p.wert?.gesamt_eur ?? null;
    const gv = gesamt === null ? null : gesamt - p.startkapital_eur;
    out.push({ id: 'kapital', titel: 'Spielgeldkapital', wert: f.euro(gesamt), zusatz: `${gv === null ? '–' : `${gv >= 0 ? '+' : '−'}${f.euro(Math.abs(gv))}`} seit Start (${f.euro(p.startkapital_eur)})`, ton: ton(gv), link: depotLink(p) });
    const diff = abstandPp(p, welt);
    out.push({
      id: 'rendite',
      titel: 'Rendite nach Kosten',
      wert: f.signedPctValue(p.kennzahlen.rendite_zeitgewichtet_pct, 2),
      zusatz: welt ? (diff === null ? 'Welt-ETF: anderer Zeitraum' : `${f.signedPctValue(diff, 1).replace('%', 'pp')} zum Welt-ETF`) : 'kein Welt-ETF-Vergleich',
      ton: ton(p.kennzahlen.rendite_zeitgewichtet_pct),
      link: depotLink(p),
    });
    const aktiv = p.positionen.filter((x) => x.zuordnung !== 'kern').length;
    out.push({ id: 'positionen', titel: 'Offene Positionen', wert: f.integer(p.positionen.length), zusatz: `${f.integer(aktiv)} aktiv, ${f.integer(p.positionen.length - aktiv)} Robo-Kern`, link: depotLink(p) });
    out.push({
      id: 'strategie',
      titel: 'Aktive Strategie',
      wert: p.strategien.length ? p.strategien.map((s) => s.name.split(' ')[0]).join(' · ') : 'nur Robo-Kern',
      zusatz: `höchstens ${f.plainPct(100 * p.aktiver_anteil, 0)} des Depots aktiv`,
      link: '#/pilot/regeln',
      text: !p.strategien.length,
    });
  }
  const forschung = g.forschung.filter((d) => d.kennzahlen.rendite_zeitgewichtet_pct !== null).sort((a, b) => (b.kennzahlen.rendite_zeitgewichtet_pct ?? 0) - (a.kennzahlen.rendite_zeitgewichtet_pct ?? 0) || a.id.localeCompare(b.id));
  const beste = forschung[0];
  out.push(
    beste
      ? {
          id: 'beste',
          titel: 'Beste Forschungsstrategie',
          wert: beste.name.replace(/^Vorlage: /, ''),
          zusatz: `${f.signedPctValue(beste.kennzahlen.rendite_zeitgewichtet_pct, 1)}, Rückgang ${rueckgang(beste.kennzahlen.max_rueckgang_pct)} – nach Rendite`,
          ton: ton(beste.kennzahlen.rendite_zeitgewichtet_pct),
          link: depotLink(beste),
          text: true,
        }
      : { id: 'beste', titel: 'Beste Forschungsstrategie', wert: '–', zusatz: 'noch keine bewertete Forschungsstrategie' },
  );
  const kauf = letzteAusfuehrung(vorwaerts, 'kauf');
  const verkauf = letzteAusfuehrung(vorwaerts, 'verkauf');
  const nameOf = (isin: string) => stand.namen[isin] ?? isin;
  const teile = [kauf ? `Kauf ${f.isoDate(kauf.a.datum)}` : 'noch kein Kauf', verkauf ? `Verkauf ${nameOf(verkauf.a.isin)} ${f.isoDate(verkauf.a.datum)}` : 'noch kein Verkauf'];
  out.push({
    id: 'entscheidungen',
    titel: 'Letzter Kauf / Verkauf',
    wert: kauf ? nameOf(kauf.a.isin) : verkauf ? nameOf(verkauf.a.isin) : 'noch keine Ausführung',
    zusatz: kauf || verkauf ? teile.join(' · ') : 'Käufe und Verkäufe erscheinen nach der ersten Ausführung',
    link: kauf ? depotLink(kauf.d) : verkauf ? depotLink(verkauf.d) : undefined,
    text: true,
  });
  const offen = vorwaerts.flatMap((d) => d.orders_offen);
  const frueh = offen.map((o) => o.frueheste).filter((x): x is string => Boolean(x)).sort()[0];
  out.push({
    id: 'naechste',
    titel: 'Nächste Ausführung',
    wert: offen.length ? f.plural(offen.length, 'offene Order', 'offene Orders') : 'keine offene Order',
    zusatz: offen.length && frueh ? `frühestens ${f.isoDate(frueh.slice(0, 10))}; danach täglicher Lauf nach Börsenschluss` : 'nächste Entscheidung im täglichen Lauf nach Börsenschluss',
  });
  const run = status?.last_run;
  out.push({
    id: 'kurse',
    titel: 'Letzte Kursaktualisierung',
    wert: status?.last_successful_check_utc ? f.berlinTime(status.last_successful_check_utc) : '–',
    zusatz: `Kursstand ${status?.last_price_session ? f.isoDate(status.last_price_session) : '–'}${run ? ` · letzter Lauf ${f.runStatus(run.status)}` : ''}`,
    link: '#/status',
  });
  const w = warnungen(g, status);
  out.push({ id: 'warnungen', titel: 'Warnungen', wert: w.length ? f.integer(w.length) : 'keine', zusatz: w.length ? w.join(' · ') : 'Robo läuft ohne Auffälligkeiten', ton: w.length ? 'warn' : undefined });
  const lab = stand.labor;
  out.push(
    lab
      ? {
          id: 'optimierung',
          titel: 'Optimierung (Labor)',
          wert: `${f.integer(lab.zaehlung.validiert + lab.zaehlung.vorwaerts)} validiert`,
          zusatz: `Lauf vom ${f.isoDate(lab.erstellt_utc.slice(0, 10))}: ${f.integer(lab.kennzahlen.varianten)} Varianten, ${f.integer(lab.zaehlung.vorwaerts)} im Vorwärtstest`,
          link: '#/pilot/labor',
        }
      : { id: 'optimierung', titel: 'Optimierung (Labor)', wert: 'noch kein Lauf', zusatz: 'läuft nur auf Anforderung', link: '#/pilot/labor' },
  );
  return out;
}
