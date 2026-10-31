/* Bericht je Spielgelddepot (Abschnitte 14, 21, 22): Darstellung der Kennzahlen, CSV-Export aller Ausführungen mit FIFO-Losen
 * und ein eigenständiger HTML-Bericht (Kapitalkurve, Vergleich, Rückgang, Monatsrenditen, Kosten, Datenabdeckung,
 * Steuerannahmen, Einschränkungen, Reproduzierbarkeit). Alle Zahlen kommen fertig aus dem täglichen Lauf
 * (backend/traktien/aktienpilot/bericht.py) – hier wird nur formatiert, nichts nachgerechnet. */

import { formatNumber, toCsv, type CsvValue } from './csv';
import * as f from './format';
import type { PilotAusfuehrung, PilotBericht, PilotDepot, PilotStand } from './pilot';

const zahlFmt = (digits: number) => new Intl.NumberFormat('de-DE', { minimumFractionDigits: digits, maximumFractionDigits: digits });

export function zahl(v: number | null | undefined, digits = 2): string {
  return v === null || v === undefined || !Number.isFinite(v) ? '–' : zahlFmt(digits).format(v);
}

export interface KennzahlZeile {
  key: string;
  label: string;
  text: (v: number) => string;
}

export const KENNZAHL_ZEILEN: KennzahlZeile[] = [
  { key: 'rendite_pct', label: 'Rendite (zeitgewichtet)', text: (v) => f.signedPctValue(v, 2) },
  { key: 'cagr_pct', label: 'Rendite pro Jahr (CAGR)', text: (v) => f.signedPctValue(v, 2) },
  { key: 'volatilitaet_pct', label: 'Schwankung pro Jahr', text: (v) => f.plainPct(v, 1) },
  { key: 'sharpe', label: 'Sharpe-Kennzahl', text: (v) => zahl(v, 2) },
  { key: 'sortino', label: 'Sortino-Kennzahl', text: (v) => zahl(v, 2) },
  { key: 'max_rueckgang_pct', label: 'Größter Rückgang', text: (v) => f.plainPct(v, 1) },
  { key: 'unter_wasser_tage', label: 'Längste Zeit unter dem Höchststand', text: (v) => `${f.integer(v)} Bewertungstage` },
  { key: 'trades', label: 'Abgeschlossene Trades', text: (v) => f.integer(v) },
  { key: 'trefferquote_pct', label: 'Trefferquote', text: (v) => f.plainPct(v, 1) },
  { key: 'profitfaktor', label: 'Profitfaktor', text: (v) => zahl(v, 2) },
  { key: 'gewinn_mittel_eur', label: 'Ø Gewinn je Gewinntrade', text: (v) => f.signedEuro(v) },
  { key: 'verlust_mittel_eur', label: 'Ø Verlust je Verlusttrade', text: (v) => f.signedEuro(v) },
  { key: 'kapitalbindung_pct', label: 'Kapitalbindung (Ø investiert)', text: (v) => f.plainPct(v, 1) },
  { key: 'kosten_eur', label: 'Kosten', text: (v) => f.euro(v, true) },
  { key: 'kosten_pct_start', label: 'Kosten in % des Startkapitals', text: (v) => f.plainPct(v, 2) },
  { key: 'ausfuehrungen', label: 'Ausführungen', text: (v) => f.integer(v) },
];

/** Text einer Kennzahl oder „nicht definiert“ mit dem Grund aus dem Lauf (nie 0 oder ein erfundener Wert). */
export function kennzahlWert(b: PilotBericht, z: KennzahlZeile): { text: string; grund: string | null } {
  const v = b.kennzahlen?.[z.key];
  if (v === null || v === undefined || !Number.isFinite(v)) return { text: 'nicht definiert', grund: b.nicht_definiert?.[z.key] ?? null };
  let text = z.text(v);
  const unbekannt = b.kennzahlen?.trades_unbekannt ?? 0;
  if (z.key === 'trades' && unbekannt) text += ` (dazu ${f.integer(unbekannt)} mit unbekannten Kosten)`;
  return { text, grund: null };
}

const monatFmt = new Intl.DateTimeFormat('de-DE', { month: 'long', year: 'numeric', timeZone: 'UTC' });

/** „2026-09“ → „September 2026“ */
export function monatText(monat: string): string {
  const [y, m] = monat.split('-').map(Number);
  return Number.isFinite(y) && Number.isFinite(m) ? monatFmt.format(new Date(Date.UTC(y, m - 1, 1))) : monat;
}

/** Wert einer Prüfhürde mit Einheit. */
export function huerdeWert(x: { id: string; wert: number | null }): string {
  if (x.wert === null || !Number.isFinite(x.wert)) return '–';
  switch (x.id) {
    case 'profitfaktor':
      return zahl(x.wert, 2);
    case 'rueckgang':
      return f.plainPct(x.wert, 1);
    case 'benchmark':
      return `${f.signedPctValue(x.wert, 2).replace(/\u00a0%$/, '')}\u00a0Prozentpunkte`;
    default:
      return f.integer(x.wert);
  }
}

export function huerdeZeichen(erfuellt: boolean | null): string {
  return erfuellt === true ? 'erfüllt' : erfuellt === false ? 'nicht erfüllt' : 'nicht anwendbar';
}

export function zuordnungText(z: string): string {
  return z === 'kern' ? 'Robo-Kern' : z === 'extern' ? 'extern' : z;
}

export function loseText(lose: PilotAusfuehrung['lose']): string {
  if (!lose) return '';
  return lose
    .map((l) => `${l.kauf ?? 'Anschaffungstag unbekannt'}: ${l.stueck === null ? '?' : formatNumber(l.stueck)} Stück, ${l.kosten_eur === null ? 'Kosten unbekannt' : `${formatNumber(l.kosten_eur, 2)} EUR`}`)
    .join(' | ');
}

const CSV_HEADER = [
  'Datum',
  'Buchungszeit (UTC)',
  'Art',
  'ISIN',
  'Name',
  'Stück',
  'Kurs',
  'Währung',
  'EUR je Einheit',
  'Quelle der Umrechnung',
  'Gebühren EUR',
  'Betrag EUR',
  'Zuordnung',
  'Order',
  'Ergebnis EUR (FIFO, nach Kosten)',
  'Anschaffungslose (FIFO)',
  'Hinweis',
];

/** CSV (Excel, deutsch) aller Ausführungen eines Depots – Abschnitt 21: ISIN, Menge, Zeit, Währung, Kurs, Gebühren, Eurobetrag,
 * Quelle der Umrechnung und Anschaffungslos nach FIFO; unbekannte Lose oder Umrechnungen sind gekennzeichnet. */
export function ausfuehrungenCsv(d: PilotDepot, stand: PilotStand): string {
  const rows: CsvValue[][] = (d.ausfuehrungen ?? []).map((a) => {
    const hinweise: string[] = [];
    if (a.lose?.some((l) => l.kosten_eur === null)) hinweise.push('Anschaffungskosten unbekannt');
    if (a.waehrung && a.waehrung !== 'EUR' && (a.fx_eur === null || !a.fx_quelle)) hinweise.push('Umrechnung unbekannt');
    const quelle = a.fx_quelle ?? (a.waehrung === 'EUR' ? 'keine Umrechnung (EUR)' : '');
    return [a.datum, a.zeit, a.art === 'kauf' ? 'Kauf' : 'Verkauf', a.isin, stand.namen[a.isin] ?? '', a.stueck, a.kurs, a.waehrung, a.fx_eur, quelle,
      a.gebuehren_eur, a.betrag_eur, zuordnungText(a.zuordnung), a.order, a.ergebnis_eur, loseText(a.lose), hinweise.join(', ')];
  });
  const meta: [string, string][] = [
    ['Depot', `${d.name} (${d.id})`],
    ['Modus', d.modus === 'DEMO' ? 'DEMO – synthetische Kurse' : 'Spielgeld (PAPER)'],
    ['Datenstand', stand.datentag],
    ['Hinweis', 'Spielgeld – keine echten Orders. Belegexport einer Modellrechnung, keine Steuerabrechnung.'],
  ];
  return toCsv(meta, CSV_HEADER, rows, [undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, 2, 2, undefined, undefined, 2]);
}

/* ------------------------------------------------------------------ HTML-Bericht */

const esc = (text: unknown): string =>
  String(text ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string);

interface Linie {
  name: string;
  farbe: string;
  pts: { day: number; v: number }[];
}

/** Einfaches Liniendiagramm als SVG (ohne Skript; druckbar). */
export function svgLinien(linien: Linie[], { width = 720, height = 220, einheit = '', null_linie = null as number | null } = {}): string {
  const all = linien.flatMap((l) => l.pts);
  if (all.length < 2) return '<p class="note">Zu wenige Punkte für eine Grafik.</p>';
  const m = { l: 56, r: 12, t: 10, b: 26 };
  const d0 = Math.min(...all.map((p) => p.day));
  const d1 = Math.max(...all.map((p) => p.day));
  let lo = Math.min(...all.map((p) => p.v));
  let hi = Math.max(...all.map((p) => p.v));
  if (null_linie !== null) {
    lo = Math.min(lo, null_linie);
    hi = Math.max(hi, null_linie);
  }
  if (lo === hi) {
    lo -= 1;
    hi += 1;
  }
  const x = (day: number) => m.l + ((day - d0) / Math.max(1, d1 - d0)) * (width - m.l - m.r);
  const y = (v: number) => m.t + (1 - (v - lo) / (hi - lo)) * (height - m.t - m.b);
  const paths = linien
    .filter((l) => l.pts.length > 1)
    .map((l) => `<polyline fill="none" stroke="${l.farbe}" stroke-width="2" stroke-linejoin="round" points="${l.pts.map((p) => `${x(p.day).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ')}"/>`)
    .join('');
  const ref = null_linie === null ? '' : `<line x1="${m.l}" x2="${width - m.r}" y1="${y(null_linie).toFixed(1)}" y2="${y(null_linie).toFixed(1)}" stroke="#9a9a9a" stroke-dasharray="3 3"/>`;
  const label = (v: number) => `${zahl(v, Math.abs(hi - lo) < 10 ? 1 : 0)}${einheit}`;
  const axes =
    `<text x="${m.l - 6}" y="${y(hi) + 4}" text-anchor="end">${esc(label(hi))}</text>` +
    `<text x="${m.l - 6}" y="${y(lo) + 4}" text-anchor="end">${esc(label(lo))}</text>` +
    `<text x="${m.l}" y="${height - 6}">${esc(f.day(d0))}</text>` +
    `<text x="${width - m.r}" y="${height - 6}" text-anchor="end">${esc(f.day(d1))}</text>`;
  const legend = linien.map((l) => `<span class="key"><i style="background:${l.farbe}"></i>${esc(l.name)}</span>`).join('');
  return `<svg viewBox="0 0 ${width} ${height}" width="100%" role="img" aria-label="${esc(linien.map((l) => l.name).join(', '))}">${ref}${paths}<g class="ax">${axes}</g></svg><p class="legend">${legend}</p>`;
}

function indexLinie(d: PilotDepot, name: string, farbe: string, von?: number): Linie {
  const pts: { day: number; v: number }[] = [];
  d.verlauf.tag.forEach((t, i) => {
    const v = d.verlauf.gesamt[i];
    const day = f.isoToDay(t);
    if (v !== null && Number.isFinite(v) && (von === undefined || day >= von)) pts.push({ day, v });
  });
  const base = pts.length ? pts[0].v : 1;
  return { name, farbe, pts: pts.map((p) => ({ day: p.day, v: (100 * p.v) / base })) };
}

const FARBEN = ['#1f5fbf', '#6b6b6b', '#a86b00'];

function tabelle(kopf: string[], zeilen: string[][], rechts: number[] = []): string {
  const th = kopf.map((h, i) => `<th${rechts.includes(i) ? ' class="n"' : ''}>${esc(h)}</th>`).join('');
  const tr = zeilen.map((z) => `<tr>${z.map((c, i) => `<td${rechts.includes(i) ? ' class="n"' : ''}>${c}</td>`).join('')}</tr>`).join('');
  return `<table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`;
}

/** Eigenständige HTML-Datei des Berichts (ohne Skripte, ohne externe Dateien). */
export function berichtHtml(d: PilotDepot, stand: PilotStand, erstellt = new Date()): string {
  const b = d.bericht;
  const titel = `Spielgeld-Bericht: ${d.name}`;
  const teile: string[] = [];
  teile.push(`<h1>${esc(titel)}</h1>`);
  teile.push(
    `<p class="note">${esc(d.modus === 'DEMO' ? 'DEMO – synthetische Kurse.' : 'Spielgeld (PAPER) – virtuelle Orders mit echten verfügbaren Kursen.')} ` +
      `${d.historisch ? 'Historische Simulation – nachgerechnet, kein Vorwärtstest. ' : ''}Keine echten Orders, keine Anlageberatung; kein offizielles Produkt von Trade Republic.</p>`,
  );
  if (!b || b.grund) {
    teile.push(`<p>${esc(b?.grund ?? 'Für dieses Depot liegt noch kein Bericht vor.')}</p>`);
  } else {
    const z = b.zeitraum!;
    teile.push(
      `<p>Zeitraum ${esc(f.isoDate(z.von))} bis ${esc(f.isoDate(z.bis))} (${esc(f.integer(z.kalendertage))} Kalendertage, ${esc(f.integer(z.renditetage))} Tagesrenditen) · ` +
        `Datenabdeckung: ${esc(f.integer(b.bewertungstage - b.unvollstaendig))} von ${esc(f.integer(b.bewertungstage))} Bewertungstagen vollständig · Startkapital ${esc(f.euro(d.startkapital_eur))}</p>`,
    );
    // Kapitalkurve mit Vergleich
    const von = f.isoToDay(z.von);
    const linien = [indexLinie(d, d.name, FARBEN[0], von)];
    (b.vergleiche ?? []).forEach((v, i) => {
      const ref = stand.depots.find((x) => x.id === v.depot);
      if (ref && v.von) linien.push(indexLinie(ref, ref.name, FARBEN[(i + 1) % FARBEN.length], f.isoToDay(v.von)));
    });
    teile.push(`<h2>Kapitalkurve und Vergleich (100 = Beginn)</h2>${svgLinien(linien, { null_linie: 100 })}`);
    const rg = b.rueckgang;
    if (rg) {
      const pts = rg.tag.map((t, i) => ({ day: f.isoToDay(t), v: rg.pct[i] })).filter((p): p is { day: number; v: number } => p.v !== null);
      teile.push(`<h2>Rückgang vom Höchststand</h2>${svgLinien([{ name: 'Rückgang in %', farbe: '#b3261e', pts }], { height: 160, einheit: ' %', null_linie: 0 })}`);
    }
    teile.push(
      `<h2>Kennzahlen</h2>${tabelle(
        ['Kennzahl', 'Wert'],
        KENNZAHL_ZEILEN.map((k) => {
          const w = kennzahlWert(b, k);
          return [esc(k.label), w.grund ? `${esc(w.text)} – ${esc(w.grund)}` : esc(w.text)];
        }),
      )}`,
    );
    teile.push(`<p class="note">Risikofreier Zins: ${esc(b.zins?.quelle ?? 'nicht konfiguriert')}${b.zins?.rendite_pct !== undefined && b.zins?.rendite_pct !== null ? ` (${esc(f.signedPctValue(b.zins.rendite_pct, 3))} im Zeitraum)` : b.zins?.grund ? ` – ${esc(b.zins.grund)}` : ''}.</p>`);
    if (b.vergleiche?.length) {
      teile.push(
        `<h2>Vergleichsdepots</h2>${tabelle(
          ['Vergleich', 'Zeitraum', 'eigen', 'Vergleich', 'Abstand'],
          b.vergleiche.map((v) =>
            v.grund
              ? [esc(v.name), esc(v.grund), '–', '–', '–']
              : [esc(v.name), `${esc(f.isoDate(v.von))} – ${esc(f.isoDate(v.bis))}`, esc(f.signedPctValue(v.eigen_pct ?? null, 2)), esc(f.signedPctValue(v.vergleich_pct ?? null, 2)), `${esc(zahl(v.abstand_pp ?? null, 2))} pp`],
          ),
          [2, 3, 4],
        )}`,
      );
    }
    if (b.monate?.length) {
      teile.push(
        `<h2>Monatsrenditen</h2>${tabelle(
          ['Monat', 'Rendite', 'Tage'],
          b.monate.map((m) => [esc(monatText(m.monat) + (m.angebrochen ? ' (angebrochen)' : '')), esc(f.signedPctValue(m.rendite_pct, 2)), esc(f.integer(m.tage))]),
          [1, 2],
        )}`,
      );
    }
    const h = b.haelften;
    if (h) {
      teile.push(
        `<h2>Hälftenvergleich</h2><p>${
          h.grund
            ? esc(h.grund)
            : `Erste Hälfte ${esc(f.signedPctValue(h.erste?.rendite_pct ?? null, 2))}, zweite Hälfte ${esc(f.signedPctValue(h.zweite?.rendite_pct ?? null, 2))}.`
        } ${esc(b.walk_forward ?? '')}</p>`,
      );
    }
    const bo = b.bootstrap;
    if (bo) {
      teile.push(
        `<h2>Block-Bootstrap</h2>${
          bo.grund
            ? `<p>${esc(bo.grund)}</p>`
            : `${tabelle(
                ['Größe', '5 %', '50 %', '95 %'],
                [
                  ['Rendite', esc(f.signedPctValue(bo.rendite_pct?.p5 ?? null, 2)), esc(f.signedPctValue(bo.rendite_pct?.p50 ?? null, 2)), esc(f.signedPctValue(bo.rendite_pct?.p95 ?? null, 2))],
                  ['Größter Rückgang', esc(f.plainPct(bo.max_rueckgang_pct?.p5 ?? null, 1)), esc(f.plainPct(bo.max_rueckgang_pct?.p50 ?? null, 1)), esc(f.plainPct(bo.max_rueckgang_pct?.p95 ?? null, 1))],
                ],
                [1, 2, 3],
              )}<p class="note">${esc(`${f.integer(bo.pfade ?? 0)} Pfade aus Blöcken von ${bo.block} Tagesrenditen, Startwert ${bo.startwert}. Untersucht Verlaufsrisiken – kein Nachweis eines Handelsvorteils.`)}</p>`
        }`,
      );
    }
    if (b.huerden?.length) {
      teile.push(
        `<h2>Prüfhürden (Abschnitt 22, nur zur Einordnung – Echtgeld bleibt ausgeschlossen)</h2>${tabelle(
          ['Hürde', 'Wert', 'Ergebnis'],
          b.huerden.map((x) => [esc(x.text), esc(huerdeWert(x)), esc(huerdeZeichen(x.erfuellt) + (x.grund ? ` (${x.grund})` : ''))]),
        )}`,
      );
    }
    if (b.warnungen?.length) teile.push(`<h2>Warnungen</h2><ul>${b.warnungen.map((w) => `<li>${esc(w)}</li>`).join('')}</ul>`);
    const st = b.steuern;
    if (st) {
      teile.push(
        `<h2>Steuer-Modellrechnung</h2>${
          st.jahre.length
            ? tabelle(
                ['Jahr', 'Aktien +', 'Aktien −', 'Fonds', 'steuerpflichtig', 'Steuer'],
                st.jahre.map((j) => [esc(j.jahr), esc(f.euro(j.aktien_gewinne_eur, true)), esc(f.euro(j.aktien_verluste_eur, true)), esc(f.euro(j.fonds_ergebnis_eur, true)), esc(f.euro(j.steuerpflichtig_eur, true)), esc(f.euro(j.steuer_eur, true))]),
                [1, 2, 3, 4, 5],
              )
            : '<p>Noch keine realisierten Ergebnisse.</p>'
        }${st.verkauf_am_ende ? `<p>Angenommene Veräußerung aller offenen Positionen am Ende (${esc(st.verkauf_am_ende.jahr)}): zusätzliche Steuer ${esc(f.euro(st.verkauf_am_ende.zusaetzliche_steuer_eur, true))}${st.verkauf_am_ende.unbekannte_kosten ? `, ${esc(st.verkauf_am_ende.unbekannte_kosten)} Positionen mit unbekannten Kosten nicht enthalten` : ''}.</p>` : ''}<ul>${st.hinweise.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`,
      );
    }
    if (b.annahmen?.length) teile.push(`<h2>Annahmen und Einschränkungen</h2><ul>${b.annahmen.map((a) => `<li>${esc(a)}</li>`).join('')}</ul>`);
    const r = b.reproduzierbar;
    if (r) {
      teile.push(
        `<h2>Reproduzierbarkeit</h2><p>Datenstand ${esc(r.datenstand ?? '–')} · Programm ${esc(r.programm)} · Bericht ${esc(r.bericht)} · Zufallsstartwert ${esc(r.startwert)} · Regeln ${esc(r.regeln.join(', ') || '–')}</p>`,
      );
    }
  }
  teile.push(`<p class="note">Erstellt ${esc(erstellt.toLocaleString('de-DE', { timeZone: 'Europe/Berlin' }))} aus dem Spielgeld-Stand ${esc(stand.id)}.</p>`);
  const css =
    'body{font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#1d1d1f;background:#fff;max-width:760px;margin:24px auto;padding:0 16px}' +
    'h1{font-size:1.4rem;margin:0 0 8px}h2{font-size:1.05rem;margin:22px 0 8px}table{border-collapse:collapse;width:100%;font-size:.9rem}' +
    'th,td{text-align:left;padding:5px 6px;border-bottom:1px solid #e3e3e3;vertical-align:top}th{font-weight:600}.n{text-align:right;white-space:nowrap}' +
    '.note{color:#555;font-size:.85rem}svg text{font-size:11px;fill:#555}.legend{font-size:.85rem;color:#444}.key{margin-right:14px;white-space:nowrap}' +
    '.key i{display:inline-block;width:14px;height:3px;margin:0 6px 3px 0;vertical-align:middle}@media print{body{margin:0}}';
  return `<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(titel)}</title><style>${css}</style></head><body>${teile.join('\n')}</body></html>`;
}
