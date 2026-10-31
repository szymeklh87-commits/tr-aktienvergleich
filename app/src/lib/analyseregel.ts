/* „Als Robo-Regel verwenden“ aus den Analyseansichten (Abschnitte 31.2–31.5 und 31.8): Rangliste, reine Renditeliste, Häufigkeiten
 * und Merkliste öffnen den Regel-Baukasten mit genau diesen Einstellungen als Kandidatenquelle. Die Regel bekommt dieselben
 * Bausteine wie jede andere (Prüfung in der App und im Lauf); Stop, Zeitplan und Kapital kommen aus der Lineal-Vorlage und
 * bleiben im Baukasten änderbar. Nichts wird gekauft, bevor die Regel gesendet, geprüft und im täglichen Lauf gestartet ist. */

import type { PilotStand, Quelle, Regel } from './pilot';
import { buildHash } from './router';
import { ableiten, idAusName } from './regelpruefung';

export type Politik = 'native' | 'common_trend';
export type Gruppe = 'A' | 'B';

const WEIGHTS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

export function linkRangliste(o: { h: number; w: number; gruppe: Gruppe; politik: Politik; platz?: number }): string {
  return buildHash('/pilot/neu', { quelle: 'rangliste', h: o.h, w: o.w, gruppe: o.gruppe, politik: o.politik, platz: o.platz ?? 10 });
}

export function linkHaeufigkeit(o: { von: number; bis: number; gewichte: number[]; k: number; gruppe: Gruppe; politik: Politik; mindestens?: number }): string {
  return buildHash('/pilot/neu', { quelle: 'haeufigkeit', von: o.von, bis: o.bis, gewichte: o.gewichte.join(','), k: o.k, gruppe: o.gruppe, politik: o.politik, mindestens: o.mindestens ?? 1 });
}

export function linkListe(o: { isins: string[]; bezeichnung: string }): string {
  return buildHash('/pilot/neu', { quelle: 'isins', isins: o.isins.join(','), bezeichnung: o.bezeichnung });
}

/** Musterbereiche (Abschnitt 26): alle Aktien im gewählten Zustand, nach dem Muster-Score bzw. Volumenfaktor sortiert. */
export function linkMuster(o: { modul: 'A' | 'B' | 'C'; zustaende: string[] }): string {
  return buildHash('/pilot/neu', { quelle: 'muster', modul: o.modul, zustaende: o.zustaende.join(',') });
}

const MUSTER: Record<'A' | 'B' | 'C', { kennzahl: string; score: string; name: string; zustaende: string[]; aktiv: string[] }> = {
  A: { kennzahl: 'muster_vor_ausbruch', score: 'muster_vor_ausbruch_score', name: 'Vor-Ausbruch', zustaende: ['kandidat', 'vorlaeufig', 'bestaetigt', 'ungueltig', 'abgelaufen'], aktiv: ['kandidat', 'vorlaeufig', 'bestaetigt'] },
  C: { kennzahl: 'muster_seitwaertsbasis', score: 'muster_seitwaertsbasis_score', name: 'Seitwärtsbasis', zustaende: ['basis', 'naehert', 'vorlaeufig', 'bestaetigt', 'zurueck'], aktiv: ['naehert', 'vorlaeufig', 'bestaetigt'] },
  B: { kennzahl: 'volumensprung', score: 'volumenfaktor', name: 'Volumensprung', zustaende: ['sprung'], aktiv: ['sprung'] },
};

function zahlIn(text: string | null, lo: number, hi: number, fallback: number): number {
  const n = Number(text);
  return Number.isInteger(n) && n >= lo && n <= hi ? n : fallback;
}

const ISIN = /^[A-Z]{2}[A-Z0-9]{9}[0-9]$/;

/** Regel aus den Parametern einer Analyseansicht; ``null``, wenn die Adresse keine Analysequelle enthält. */
export function regelAusAnalyse(stand: PilotStand, params: URLSearchParams): Regel | null {
  const quelle = params.get('quelle');
  const basis = stand.vorlagen?.lineal ?? Object.values(stand.vorlagen ?? {})[0];
  if (!quelle || !basis) return null;
  const max = Math.max(1, Math.min(stand.grenzen?.max_einzelaktien ?? 8, stand.grenzen?.max_anzahl ?? 8));
  const gruppe: Gruppe = params.get('gruppe') === 'B' ? 'B' : 'A';
  const politik: Politik = params.get('politik') === 'common_trend' ? 'common_trend' : 'native';
  const r = ableiten(basis, 'kopie');
  r.filter = null;
  r.herkunft = { vorlage: basis.herkunft?.vorlage ?? basis.id };
  let q: Quelle;
  if (quelle === 'rangliste') {
    const h = zahlIn(params.get('h'), 1, 90, 30);
    const w = WEIGHTS.includes(Number(params.get('w'))) ? Number(params.get('w')) : 60;
    const platz = zahlIn(params.get('platz'), 1, 100, 10);
    q = { art: 'rangliste', gruppe, politik, gewichte: [w], fenster: { von: h, bis: h }, platz_bis: platz };
    r.sortierung = { schluessel: [{ kennzahl: { id: 'rang', parameter: { fenster: h, gewicht: w, gruppe, politik } }, richtung: 'auf' }] };
    r.auswahl = { ...r.auswahl, anzahl: Math.min(platz, max) };
    r.name = `${w === 0 ? 'Renditeliste' : 'Rangliste'} ${h} Tage${w === 0 ? '' : `, ${w}/${100 - w}`}, Gruppe ${gruppe}, Top ${platz}`;
    r.beschreibung = `Aus der Ansicht übernommen: die ersten ${platz} der ${w === 0 ? 'reinen Renditeliste' : `Lineal-Rangliste ${w}/${100 - w}`} über ${h} Kalendertage (Gruppe ${gruppe}, ${politik === 'native' ? 'natives Vergleichsfeld' : 'gleiches Vergleichsfeld'}), nach Platz sortiert.`;
  } else if (quelle === 'haeufigkeit') {
    let von = zahlIn(params.get('von'), 1, 90, 1);
    let bis = zahlIn(params.get('bis'), 1, 90, 30);
    if (von > bis) [von, bis] = [bis, von];
    const gewichte = [...new Set((params.get('gewichte') ?? '').split(',').map(Number).filter((w) => WEIGHTS.includes(w)))].sort((a, b) => a - b);
    const k = [1, 3, 10].includes(Number(params.get('k'))) ? Number(params.get('k')) : 10;
    const zellen = (bis - von + 1) * Math.max(1, gewichte.length);
    const mindestens = zahlIn(params.get('mindestens'), 1, zellen, 1);
    const g = gewichte.length ? gewichte : [...WEIGHTS];
    q = { art: 'haeufigkeit', k, fenster: { von, bis }, gewichte: g, gruppe, politik, mindestens };
    r.sortierung = { schluessel: [{ kennzahl: { id: 'haeufigkeit', parameter: { k, fenster: { von, bis }, gewichte: g, gruppe, politik } }, richtung: 'ab' }] };
    r.auswahl = { ...r.auswahl, anzahl: Math.min(5, max) };
    r.name = `Häufig in den Top ${k}, ${von}–${bis} Tage, Gruppe ${gruppe}`;
    r.beschreibung = `Aus der Häufigkeitsansicht übernommen: Aktien, die in den Ranglisten ${von}–${bis} Kalendertage (${g.length === 11 ? 'alle elf Gewichtungen' : g.map((w) => `${w}/${100 - w}`).join(', ')}) mindestens ${mindestens}-mal unter den ersten ${k} stehen, nach Häufigkeit sortiert.`;
  } else if (quelle === 'isins') {
    const isins = [...new Set((params.get('isins') ?? '').split(',').map((s) => s.trim().toUpperCase()).filter((s) => ISIN.test(s)))].slice(0, 250);
    if (!isins.length) return null;
    const bezeichnung = (params.get('bezeichnung') ?? 'Eigene Liste').slice(0, 60);
    q = { art: 'isins', isins, bezeichnung };
    r.sortierung = { schluessel: [{ kennzahl: { id: 'rendite', parameter: { fenster: 30 } }, richtung: 'ab' }] };
    r.auswahl = { ...r.auswahl, anzahl: Math.min(isins.length, max) };
    r.name = `${bezeichnung}: ${isins.length} Aktien`;
    r.beschreibung = `Kandidaten aus „${bezeichnung}“ (${isins.length} Aktien), nach der Rendite der letzten 30 Kalendertage sortiert.`;
  } else if (quelle === 'muster') {
    const modul = params.get('modul') === 'B' ? 'B' : params.get('modul') === 'C' ? 'C' : 'A';
    const def = MUSTER[modul];
    const gewaehlt = (params.get('zustaende') ?? '').split(',').filter((z) => def.zustaende.includes(z));
    const zustaende = gewaehlt.length ? gewaehlt : def.aktiv;
    q = { art: 'universum' };
    if (modul === 'B') {
      r.filter = { kennzahl: { id: def.kennzahl, parameter: {} }, op: 'ist_wahr' };
      r.sortierung = { schluessel: [{ kennzahl: { id: def.score, parameter: { sitzungen: 20 } }, richtung: 'ab' }] };
    } else {
      r.filter = { kennzahl: { id: def.kennzahl, parameter: {} }, op: 'in', werte: zustaende };
      r.sortierung = { schluessel: [{ kennzahl: { id: def.score, parameter: {} }, richtung: 'ab' }] };
    }
    r.auswahl = { ...r.auswahl, anzahl: Math.min(5, max) };
    r.name = `Muster ${modul}: ${def.name} (${zustaende.join(', ')})`;
    r.beschreibung = `Aus den Musterbereichen übernommen: alle geprüften Aktien im Zustand ${zustaende.join(', ')} (${def.name}, Tagesdaten), nach ${modul === 'B' ? 'Volumenfaktor' : 'Muster-Score'} sortiert. Ein Musterfund ist keine Gewinnwahrscheinlichkeit.`;
  } else {
    return null;
  }
  r.kandidaten = [q];
  r.name = r.name.slice(0, 80);
  r.id = idAusName(r.name);
  return r;
}
