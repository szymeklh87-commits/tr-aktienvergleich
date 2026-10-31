/* Regel-Baukasten in der App (Gesamtauftrag, Abschnitte 27.4 und 31): sofortige Prüfung beim Bearbeiten. Sie folgt der
 * Prüfung im Lauf (``backend/traktien/aktienpilot/regeln.py``, gleiche Grenzen und Meldungen); verbindlich bleibt die
 * Prüfung im Lauf – eine dort abgelehnte Regel wird nie ausgeführt. Kein freier Code, nur Bausteine aus dem Katalog. */

import type { Ausdruck, Katalog, KatalogKennzahl, KatalogParam, KennzahlRef, Quelle, Regel } from './pilot';

export const GRENZEN = {
  max_tiefe: 6,
  max_bedingungen: 40,
  max_quellen: 8,
  max_sortierung: 6,
  max_anzahl: 50,
  max_isins: 250,
  max_stufen: 6,
  max_groesse_byte: 64_000,
};

export const ID_RE = /^r-[a-z0-9][a-z0-9-]{1,38}$/;
export const GEWICHTE = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

export interface Fehler {
  pfad: string;
  text: string;
}

type Rolle = 'filter' | 'sortierung' | 'kapital' | 'ausstieg';
const ROLLENTEXT: Record<Rolle, string> = { filter: 'Filter', sortierung: 'Sortierung', kapital: 'Kapitalverteilung', ausstieg: 'Ausstiegsbedingung' };

function isNum(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

function isInt(v: unknown): v is number {
  return isNum(v) && Math.floor(v) === v;
}

/** Parameter wie ``Param.pruefen`` im Lauf; fehlende Parameter bekommen den Standardwert. */
export function parameterPruefen(k: KatalogKennzahl, werte: Record<string, unknown> | undefined, pfad: string, fehler: Fehler[]): Record<string, unknown> | null {
  const given = werte ?? {};
  const known = new Set(k.parameter.map((p) => p.name));
  const unknown = Object.keys(given).filter((n) => !known.has(n));
  if (unknown.length) {
    fehler.push({ pfad, text: `${k.name}: unbekannte Parameter ${unknown.sort().join(', ')}` });
    return null;
  }
  const out: Record<string, unknown> = {};
  for (const p of k.parameter) {
    const v = p.name in given ? given[p.name] : p.standard;
    if (v === undefined || v === null) {
      fehler.push({ pfad, text: `${k.name}: Parameter „${p.name}“ fehlt` });
      return null;
    }
    const msg = paramFehler(p, v);
    if (msg) {
      fehler.push({ pfad, text: msg });
      return null;
    }
    out[p.name] = normalize(p, v);
  }
  return out;
}

function normalize(p: KatalogParam, v: unknown): unknown {
  if (p.art === 'gewichte') return [...new Set((v as number[]).map(Number))].sort((a, b) => a - b);
  if (p.art === 'bereich') return { von: (v as { von: number }).von, bis: (v as { bis: number }).bis };
  return v;
}

function paramFehler(p: KatalogParam, v: unknown): string | null {
  const range = (x: number) =>
    (p.minimum !== undefined && p.minimum !== null && x < p.minimum) || (p.maximum !== undefined && p.maximum !== null && x > p.maximum)
      ? `„${p.name}“ muss zwischen ${p.minimum} und ${p.maximum} liegen (${p.erklaerung})`
      : null;
  switch (p.art) {
    case 'ganzzahl':
      return isInt(v) ? range(v) : `„${p.name}“ muss eine ganze Zahl sein`;
    case 'zahl':
      return isNum(v) ? range(v) : `„${p.name}“ muss eine Zahl sein`;
    case 'auswahl':
      return (p.werte ?? []).some((w) => w === v) ? null : `„${p.name}“ muss einer der Werte ${(p.werte ?? []).join(', ')} sein`;
    case 'gewichte': {
      if (!Array.isArray(v) || !v.length) return `„${p.name}“: mindestens eine Gewichtung wählen`;
      return v.every((w) => (p.werte ?? []).includes(Number(w))) ? null : `„${p.name}“: nur die Gewichtungen ${(p.werte ?? []).join(', ')}`;
    }
    case 'bereich': {
      const b = v as { von?: unknown; bis?: unknown };
      if (!b || typeof b !== 'object' || !isInt(b.von) || !isInt(b.bis)) return `„${p.name}“ braucht „von“ und „bis“ als ganze Zahlen`;
      if (!((p.minimum ?? -Infinity) <= b.von && b.von <= b.bis && b.bis <= (p.maximum ?? Infinity))) return `„${p.name}“: ${b.von}–${b.bis} liegt nicht in ${p.minimum}–${p.maximum} (von ≤ bis)`;
      return null;
    }
    default:
      return `unbekannte Parameterart ${p.art}`;
  }
}

class Pruefer {
  fehler: Fehler[] = [];
  bedingungen = 0;
  private index: Map<string, KatalogKennzahl>;

  constructor(katalog: Katalog) {
    this.index = new Map(katalog.kennzahlen.map((k) => [k.id, k]));
  }

  err(pfad: string, text: string) {
    this.fehler.push({ pfad, text });
  }

  kennzahl(id: string): KatalogKennzahl | undefined {
    return this.index.get(id);
  }

  ref(value: KennzahlRef | undefined, pfad: string, rolle: Rolle): KatalogKennzahl | null {
    if (!value || typeof value !== 'object' || typeof value.id !== 'string') {
      this.err(pfad, 'Kennzahl fehlt');
      return null;
    }
    const k = this.index.get(value.id);
    if (!k) {
      this.err(pfad, `unbekannte Kennzahl „${value.id}“`);
      return null;
    }
    if (k.rueckblickend) {
      this.err(pfad, `„${k.name}“ ist nur rückblickend bekannt – für Entscheidungen gesperrt (sonst Blick in die Zukunft)`);
      return null;
    }
    if (!k.rollen.includes(rolle)) {
      this.err(pfad, `„${k.name}“ ist als ${ROLLENTEXT[rolle]} nicht zulässig`);
      return null;
    }
    return parameterPruefen(k, value.parameter as Record<string, unknown>, pfad, this.fehler) ? k : null;
  }

  ausdruck(a: Ausdruck | null | undefined, pfad: string, rolle: Rolle, tiefe = 1): void {
    if (tiefe > GRENZEN.max_tiefe) {
      this.err(pfad, `höchstens ${GRENZEN.max_tiefe} verschachtelte Gruppen`);
      return;
    }
    if (!a || typeof a !== 'object') {
      this.err(pfad, 'muss eine Gruppe oder Bedingung sein');
      return;
    }
    if ('und' in a || 'oder' in a) {
      const op = 'und' in a ? 'und' : 'oder';
      const items = (a as Record<string, Ausdruck[]>)[op];
      if (!Array.isArray(items) || !items.length) {
        this.err(pfad, `„${op}“ braucht mindestens eine Bedingung`);
        return;
      }
      items.forEach((x, i) => this.ausdruck(x, `${pfad}.${op}[${i}]`, rolle, tiefe + 1));
      return;
    }
    if ('nicht' in a) {
      this.ausdruck(a.nicht, `${pfad}.nicht`, rolle, tiefe + 1);
      return;
    }
    this.bedingungen += 1;
    if (this.bedingungen > GRENZEN.max_bedingungen) {
      if (this.bedingungen === GRENZEN.max_bedingungen + 1) this.err(pfad, `höchstens ${GRENZEN.max_bedingungen} Bedingungen je Regel`);
      return;
    }
    const k = this.ref(a.kennzahl, `${pfad}.kennzahl`, rolle);
    if (!k) return;
    if (!k.operatoren.includes(a.op)) {
      this.err(`${pfad}.op`, `„${a.op}“ passt nicht zu „${k.name}“ (erlaubt: ${k.operatoren.join(', ')})`);
      return;
    }
    if (a.op === 'ist_wahr' || a.op === 'ist_falsch') return;
    if (a.op === 'in' || a.op === 'nicht_in') {
      const w = a.werte;
      if (!Array.isArray(w) || !w.length || w.length > 100 || !w.every((x) => typeof x === 'string' && x.length > 0 && x.length <= 80)) this.err(`${pfad}.werte`, 'Liste mit 1–100 Texten');
      else if (k.werte?.length) {
        const fremd = [...new Set(w.map(String).filter((x) => !k.werte!.includes(x)))].sort();
        if (fremd.length) this.err(`${pfad}.werte`, `unbekannter Wert ${fremd.join(', ')} (erlaubt: ${k.werte.join(', ')})`);
      }
      return;
    }
    if (a.op === 'zwischen') {
      if (!isNum(a.von) || !isNum(a.bis)) this.err(pfad, '„von“ und „bis“ müssen Zahlen sein');
      else if (a.von > a.bis) this.err(pfad, '„von“ muss kleiner oder gleich „bis“ sein');
      return;
    }
    if (a.op === 'neu_eingetreten' || a.op === 'verlassen') {
      if (!isInt(a.wert) || a.wert < 1 || a.wert > 500) this.err(`${pfad}.wert`, 'Platz zwischen 1 und 500');
      return;
    }
    if (a.vergleich) {
      if (a.wert !== undefined && a.wert !== null) {
        this.err(pfad, 'entweder „wert“ oder „vergleich“');
        return;
      }
      const o = this.ref(a.vergleich, `${pfad}.vergleich`, rolle);
      if (!o) return;
      if (!k.vergleichsklasse || k.vergleichsklasse !== o.vergleichsklasse) {
        this.err(pfad, `„${k.name}“ (${k.einheit || 'ohne Einheit'}) ist mit „${o.name}“ (${o.einheit || 'ohne Einheit'}) nicht vergleichbar`);
        return;
      }
      if (a.op.startsWith('gekreuzt') && !(k.reihe && o.reihe)) this.err(pfad, '„gekreuzt“ braucht zwei Kursreihen mit Vortageswert (z. B. Schlusskurs und Durchschnitt)');
      return;
    }
    if (a.op.startsWith('gekreuzt') && !k.reihe) {
      this.err(pfad, '„gekreuzt“ braucht eine Kursreihe mit Vortageswert');
      return;
    }
    if (!isNum(a.wert)) {
      this.err(`${pfad}.wert`, 'muss eine Zahl sein');
      return;
    }
    if (k.typ === 'rang' && (a.wert < 1 || !isInt(a.wert))) this.err(`${pfad}.wert`, 'Rang ist eine ganze Zahl ab 1');
  }

  quelle(q: Quelle, pfad: string): void {
    switch (q.art) {
      case 'rangliste': {
        if (!Array.isArray(q.gewichte) || !q.gewichte.length || q.gewichte.some((w) => !GEWICHTE.includes(w))) this.err(pfad, `Gewichtungen aus ${GEWICHTE.join(', ')}`);
        if (!q.fenster || !isInt(q.fenster.von) || !isInt(q.fenster.bis) || q.fenster.von < 1 || q.fenster.bis > 90 || q.fenster.von > q.fenster.bis) this.err(pfad, 'Zeitraum 1–90 Kalendertage (von ≤ bis)');
        if (!isInt(q.platz_bis) || q.platz_bis < 1 || q.platz_bis > 100) this.err(`${pfad}.platz_bis`, 'muss zwischen 1 und 100 liegen');
        if (q.variante === 'stichtage' && (!isInt(q.stichtage) || q.stichtage < 1 || q.stichtage > 60)) this.err(`${pfad}.stichtage`, 'muss zwischen 1 und 60 liegen');
        return;
      }
      case 'haeufigkeit': {
        if (![1, 3, 10].includes(Number(q.k))) this.err(pfad, '„k“ muss einer der Werte 1, 3, 10 sein');
        if (!q.fenster || !isInt(q.fenster.von) || !isInt(q.fenster.bis) || q.fenster.von < 1 || q.fenster.bis > 90 || q.fenster.von > q.fenster.bis) this.err(pfad, 'Zeitraum 1–90 Kalendertage (von ≤ bis)');
        if (!Array.isArray(q.gewichte) || !q.gewichte.length) this.err(pfad, 'mindestens eine Gewichtung wählen');
        const cells = q.fenster && Array.isArray(q.gewichte) ? (q.fenster.bis - q.fenster.von + 1) * q.gewichte.length : 1;
        if (!isInt(q.mindestens) || q.mindestens < 1 || q.mindestens > cells) this.err(`${pfad}.mindestens`, `muss zwischen 1 und ${cells} liegen`);
        return;
      }
      case 'universum':
        return;
      case 'isins': {
        if (!Array.isArray(q.isins) || !q.isins.length || q.isins.length > GRENZEN.max_isins) this.err(`${pfad}.isins`, `Liste mit 1–${GRENZEN.max_isins} ISINs`);
        else {
          const bad = q.isins.filter((i) => !/^[A-Z]{2}[A-Z0-9]{9}\d$/.test(i));
          if (bad.length) this.err(`${pfad}.isins`, `ungültige ISIN: ${bad.slice(0, 5).join(', ')}`);
        }
        return;
      }
      default:
        this.err(pfad, `unbekannte Quelle „${String((q as Quelle).art)}“ (rangliste, haeufigkeit, universum, isins)`);
    }
  }
}

function stopPruefen(p: Pruefer, s: Regel['stop']['initial'] | null | undefined, pfad: string, required: boolean) {
  if (!s) {
    if (required) p.err(pfad, 'Initialstop ist Pflicht – der zentrale Risiko-Manager kauft ohne Stop nicht');
    return;
  }
  if (s.art === 'atr') {
    if (!isNum(s.faktor) || s.faktor < 0.5 || s.faktor > 10) p.err(`${pfad}.faktor`, 'muss zwischen 0.5 und 10 liegen');
    if (s.sitzungen !== undefined && (!isInt(s.sitzungen) || s.sitzungen < 5 || s.sitzungen > 50)) p.err(`${pfad}.sitzungen`, 'muss zwischen 5 und 50 liegen');
  } else if (s.art === 'prozent') {
    if (!isNum(s.wert) || s.wert < 1 || s.wert > 50) p.err(`${pfad}.wert`, 'muss zwischen 1 und 50 liegen');
  } else p.err(pfad, '„art“: atr oder prozent');
}

/** Prüft eine Regel wie der Lauf; leere Liste = gültig. */
export function regelPruefen(r: Regel, katalog: Katalog): Fehler[] {
  const p = new Pruefer(katalog);
  if (r.schema !== 'tr-regel/1') p.err('schema', 'muss „tr-regel/1“ sein');
  if (!ID_RE.test(r.id ?? '')) p.err('id', '„r-“ und 2–39 Kleinbuchstaben, Ziffern oder Bindestriche');
  if (!isInt(r.version) || r.version < 1) p.err('version', 'muss eine ganze Zahl ab 1 sein');
  if (!r.name || !r.name.trim()) p.err('name', 'Name fehlt');
  else if (r.name.length > 80) p.err('name', 'höchstens 80 Zeichen');
  if ((r.beschreibung ?? '').length > 500) p.err('beschreibung', 'höchstens 500 Zeichen');
  if (!Array.isArray(r.kandidaten) || !r.kandidaten.length || r.kandidaten.length > GRENZEN.max_quellen) p.err('kandidaten', `1–${GRENZEN.max_quellen} Kandidatenquellen`);
  else r.kandidaten.forEach((q, i) => p.quelle(q, `kandidaten[${i}]`));
  if (r.filter) p.ausdruck(r.filter, 'filter', 'filter');
  const s = r.sortierung as Record<string, unknown>;
  if (s && 'schluessel' in s && Array.isArray(s.schluessel)) {
    const keys = s.schluessel as { kennzahl: KennzahlRef; richtung: string }[];
    if (!keys.length || keys.length > GRENZEN.max_sortierung) p.err('sortierung.schluessel', `1–${GRENZEN.max_sortierung} Sortierschlüssel`);
    keys.forEach((k, i) => {
      p.ref(k.kennzahl, `sortierung.schluessel[${i}].kennzahl`, 'sortierung');
      if (!['ab', 'auf'].includes(k.richtung)) p.err(`sortierung.schluessel[${i}].richtung`, 'ab oder auf');
    });
  } else if (s && 'score' in s && Array.isArray(s.score)) {
    const parts = s.score as { kennzahl: KennzahlRef; gewicht: number; richtung: string }[];
    if (!parts.length || parts.length > GRENZEN.max_sortierung) p.err('sortierung.score', `1–${GRENZEN.max_sortierung} Bestandteile`);
    parts.forEach((k, i) => {
      p.ref(k.kennzahl, `sortierung.score[${i}].kennzahl`, 'sortierung');
      if (!isNum(k.gewicht) || k.gewicht < 0.01 || k.gewicht > 100) p.err(`sortierung.score[${i}].gewicht`, 'muss zwischen 0.01 und 100 liegen');
      if (!['ab', 'auf'].includes(k.richtung)) p.err(`sortierung.score[${i}].richtung`, 'ab oder auf');
    });
  } else p.err('sortierung', '„schluessel“ (Reihenfolge) oder „score“ (gewichtete Perzentile)');
  if (!isInt(r.auswahl?.anzahl) || r.auswahl.anzahl < 1 || r.auswahl.anzahl > GRENZEN.max_anzahl) p.err('auswahl.anzahl', `muss zwischen 1 und ${GRENZEN.max_anzahl} liegen`);
  if (r.auswahl?.max_je_branche !== null && r.auswahl?.max_je_branche !== undefined && (!isInt(r.auswahl.max_je_branche) || r.auswahl.max_je_branche < 1)) p.err('auswahl.max_je_branche', 'ganze Zahl ab 1 oder leer');
  if (!['gleich', 'risiko', 'ziel'].includes(r.kapital?.art)) p.err('kapital.art', 'gleich, risiko oder ziel');
  if (r.kapital?.art === 'ziel') {
    const z = r.kapital.ziele_pct ?? [];
    if (z.length !== r.auswahl?.anzahl) p.err('kapital.ziele_pct', `genau ${r.auswahl?.anzahl} Zielgewichte (je Platz eines)`);
    else if (z.some((x) => !isNum(x) || x <= 0) || Math.abs(z.reduce((a, b) => a + b, 0) - 100) > 0.01) p.err('kapital.ziele_pct', 'positive Anteile mit Summe 100 %');
  }
  if (!['termin', 'neues_signal', 'eintritt_top_n', 'auffuellen'].includes(r.kauf?.ausloeser)) p.err('kauf.ausloeser', 'termin, neues_signal, eintritt_top_n oder auffuellen');
  const v = r.verkauf ?? {};
  if (v.herausfallen && (!isInt(v.herausfallen.puffer) || v.herausfallen.puffer < 0 || v.herausfallen.puffer > 50)) p.err('verkauf.herausfallen.puffer', 'muss zwischen 0 und 50 liegen');
  if (v.ausstieg) p.ausdruck(v.ausstieg, 'verkauf.ausstieg', 'ausstieg');
  if (v.max_haltedauer_sitzungen !== null && v.max_haltedauer_sitzungen !== undefined && (!isInt(v.max_haltedauer_sitzungen) || v.max_haltedauer_sitzungen < 1 || v.max_haltedauer_sitzungen > 2000)) {
    p.err('verkauf.max_haltedauer_sitzungen', 'muss zwischen 1 und 2000 liegen');
  }
  const g = v.gewinnmitnahme;
  if (g) {
    if (g.art === 'ganz') {
      if (!isNum(g.schwelle_pct) || g.schwelle_pct < 0.1 || g.schwelle_pct > 10_000) p.err('verkauf.gewinnmitnahme.schwelle_pct', 'muss zwischen 0.1 und 10000 liegen');
      const u = g.umfang;
      if (u && u.art === 'anteil' && (!isNum(u.pct) || u.pct < 1 || u.pct > 100)) p.err('verkauf.gewinnmitnahme.umfang.pct', 'muss zwischen 1 und 100 liegen');
      if (u && u.art === 'stueck' && (!isInt(u.stueck) || u.stueck < 1)) p.err('verkauf.gewinnmitnahme.umfang.stueck', 'ganze Zahl ab 1');
    } else if (g.art === 'leiter') {
      const st = g.stufen ?? [];
      if (!st.length || st.length > GRENZEN.max_stufen) p.err('verkauf.gewinnmitnahme.stufen', `1–${GRENZEN.max_stufen} Stufen`);
      st.forEach((x, i) => {
        if (!isNum(x.schwelle_pct) || x.schwelle_pct < 0.1 || x.schwelle_pct > 10_000) p.err(`verkauf.gewinnmitnahme.stufen[${i}].schwelle_pct`, 'muss zwischen 0.1 und 10000 liegen');
        if (!isNum(x.anteil_pct) || x.anteil_pct < 1 || x.anteil_pct > 100) p.err(`verkauf.gewinnmitnahme.stufen[${i}].anteil_pct`, 'muss zwischen 1 und 100 liegen');
      });
      const sch = st.map((x) => x.schwelle_pct);
      if (sch.some((x, i) => i > 0 && !(x > sch[i - 1]))) p.err('verkauf.gewinnmitnahme.stufen', 'Schwellen müssen aufsteigend und verschieden sein');
      if ((g.bezug ?? 'urspruenglich') === 'urspruenglich' && st.reduce((a, x) => a + (x.anteil_pct || 0), 0) > 100 + 1e-9) p.err('verkauf.gewinnmitnahme.stufen', 'Summe der Anteile über 100 % der ursprünglichen Stückzahl');
    } else p.err('verkauf.gewinnmitnahme', '„art“: ganz oder leiter');
  }
  const w = v.wiedereinstieg;
  if (w && w.art === 'pause' && (!isInt(w.pause_sitzungen) || (w.pause_sitzungen ?? 0) < 0 || (w.pause_sitzungen ?? 0) > 250)) p.err('verkauf.wiedereinstieg.pause_sitzungen', 'muss zwischen 0 und 250 liegen');
  stopPruefen(p, r.stop?.initial, 'stop.initial', true);
  if (r.stop?.trailing) stopPruefen(p, r.stop.trailing, 'stop.trailing', false);
  if (!['taeglich', 'woechentlich'].includes(r.zeitplan?.intervall)) p.err('zeitplan.intervall', 'taeglich oder woechentlich');
  if (r.zeitplan?.intervall === 'woechentlich' && (!isInt(r.zeitplan.wochentag) || r.zeitplan.wochentag < 0 || r.zeitplan.wochentag > 4)) p.err('zeitplan.wochentag', 'muss zwischen 0 (Montag) und 4 (Freitag) liegen');
  if (!['FOLGETAG-SCHLUSS', 'TAGESDATEN'].includes(r.profil)) p.err('profil', 'FOLGETAG-SCHLUSS oder TAGESDATEN');
  const o = r.optionen ?? {};
  if (o.mindesthaltedauer_sitzungen !== undefined && (!isInt(o.mindesthaltedauer_sitzungen) || o.mindesthaltedauer_sitzungen < 0 || o.mindesthaltedauer_sitzungen > 250)) p.err('optionen.mindesthaltedauer_sitzungen', 'muss zwischen 0 und 250 liegen');
  if (o.mindestorderwert_eur !== undefined && (!isNum(o.mindestorderwert_eur) || o.mindestorderwert_eur < 0 || o.mindestorderwert_eur > 100_000)) p.err('optionen.mindestorderwert_eur', 'muss zwischen 0 und 100000 liegen');
  if (new TextEncoder().encode(JSON.stringify(r)).length > GRENZEN.max_groesse_byte) p.err('', `Regel größer als ${GRENZEN.max_groesse_byte} Bytes`);
  return p.fehler;
}

/** „r-mein-momentum“ aus einem Namen (Umlaute umschrieben, höchstens 40 Zeichen). */
export function idAusName(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/ä/g, 'ae')
    .replace(/ö/g, 'oe')
    .replace(/ü/g, 'ue')
    .replace(/ß/g, 'ss')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 38)
    .replace(/-+$/g, '');
  return `r-${slug.length >= 2 ? slug : `eigene-${slug || 'regel'}`}`;
}

/** Neue Regel aus einer Vorlage oder Kopie: eigene ID (oder nächste Version derselben ID), Herkunft vermerkt. */
export function ableiten(basis: Regel, art: 'kopie' | 'version'): Regel {
  const copy = JSON.parse(JSON.stringify(basis)) as Regel;
  if (art === 'version') {
    copy.version = basis.version + 1;
    copy.herkunft = { ...(basis.herkunft ?? {}), vorgaenger: `${basis.id}@${basis.version}` };
    return copy;
  }
  copy.name = basis.name.replace(/^Vorlage: /, '').slice(0, 72) + ' (eigene)';
  copy.id = idAusName(copy.name);
  copy.version = 1;
  copy.herkunft = basis.herkunft?.vorlage ? { vorlage: basis.herkunft.vorlage } : { kopie_von: `${basis.id}@${basis.version}` };
  return copy;
}

/** Standardparameter einer Kennzahl (für eine neue Bedingung). */
export function standardRef(k: KatalogKennzahl): KennzahlRef {
  const parameter: Record<string, unknown> = {};
  for (const p of k.parameter) {
    if (p.standard !== undefined && p.standard !== null) parameter[p.name] = p.standard;
  }
  return { id: k.id, parameter };
}

/** Erste Bedingung für „Als Robo-Regel verwenden“ aus dem Katalog: gültig ohne weitere Eingabe, wo das geht – Rang „≤ 10“
 * (ein Rang ist eine ganze Zahl ab 1), feste Kategorien mit ihrem ersten Wert, sonst „> 0“. Freie Kategorien (Branche, Land)
 * brauchen eine Eingabe. */
export function startBedingung(kz: KatalogKennzahl, ref: KennzahlRef): Extract<Ausdruck, { kennzahl: KennzahlRef }> {
  const op = kz.typ === 'rang' && kz.operatoren.includes('<=') ? '<=' : kz.operatoren.includes('>') ? '>' : kz.operatoren[0];
  if (op === 'ist_wahr' || op === 'ist_falsch') return { kennzahl: ref, op };
  if (op === 'in' || op === 'nicht_in') return { kennzahl: ref, op, werte: (kz.werte ?? []).slice(0, 1) };
  return { kennzahl: ref, op, wert: kz.typ === 'rang' ? 10 : 0 };
}
