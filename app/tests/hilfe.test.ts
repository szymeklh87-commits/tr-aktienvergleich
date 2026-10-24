/* Verständlichkeit und Fehlerfälle (ab 1.16): Begriffe der Hilfe, Fehlermeldungen, Beträge, Zeitplan-Hinweis. */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { NotFoundError, OfflineError, ServerError } from '../src/lib/api.ts';
import { DecodeError } from '../src/lib/container.ts';
import { describeError } from '../src/lib/errors.ts';
import { parseAmount } from '../src/lib/format.ts';
import { GLOSSARY, glossaryEntry, searchGlossary } from '../src/lib/glossary.ts';
import { scheduleNote } from '../src/lib/intraday.ts';
import type { Status } from '../src/lib/types.ts';

const words = (sentence: string) => sentence.split(/\s+/).filter((w) => /[\p{L}\d]/u.test(w)).length;
/** Sätze grob trennen: Punkt, Fragezeichen oder Doppelpunkt vor Leerzeichen und Großbuchstabe (nicht „z. B.“, „Ø“-Zahlen). */
const sentences = (text: string) => text.split(/(?<=[.?!])\s+(?=[A-ZÄÖÜ„])/u);

test('Begriffe: eindeutige Kennungen, jeder mit Erklärung, Beispiele mit Zahl', () => {
  const ids = GLOSSARY.map((e) => e.id);
  assert.equal(new Set(ids).size, ids.length);
  for (const entry of GLOSSARY) {
    assert.ok(entry.text.length > 40, entry.id);
    if (entry.example) assert.match(entry.example, /\d/, `${entry.id}: Beispiel ohne Zahl`);
  }
  for (const id of ['kursrendite', 'gleichmaessigkeit', 'rangscore', 'gewichtung', 'perzentil', 'gruppe', 'tagesumsatz', 'kursstand', 'zwischenstand', 'teilstand', 'musterdepot', 'beitrag', 'kursziel', 'passphrase', 'gleichstand', 'fehlende-kurstage']) {
    assert.ok(glossaryEntry(id), `Begriff ${id} fehlt`);
  }
});

test('Begriffe in einfachem Deutsch: kein Satz länger als 30 Wörter', () => {
  const long: string[] = [];
  for (const entry of GLOSSARY) {
    for (const sentence of [...sentences(entry.text), ...sentences(entry.example ?? '')]) {
      if (words(sentence) > 30) long.push(`${entry.id}: ${words(sentence)} Wörter – ${sentence.slice(0, 60)} …`);
    }
  }
  assert.deepEqual(long, []);
});

test('Begriffe suchen: Fachwort, Synonym, Text; alphabetisch ohne Suchwort', () => {
  assert.equal(searchGlossary('R²')[0].id, 'gleichmaessigkeit');
  assert.equal(searchGlossary('überkauft')[0].id, 'rsi');
  assert.equal(searchGlossary('Zugangsschlüssel')[0].id, 'passphrase');
  assert.deepEqual(searchGlossary('xyzzy'), []);
  const all = searchGlossary('');
  assert.equal(all.length, GLOSSARY.length);
  const terms = all.map((e) => e.term);
  assert.deepEqual(terms, [...terms].sort((a, b) => a.localeCompare(b, 'de')));
});

test('Gleichstand- und Lücken-Beispiel der Hilfe stimmen mit den Regeln überein', () => {
  // 60/40: X (G 50, R 90) und Y (G 80, R 45) – beide 66, exakt (ganzzahlig in Hundertsteln gerechnet)
  assert.equal(60 * 50 + 40 * 90, 6600);
  assert.equal(60 * 80 + 40 * 45, 6600);
  assert.match(glossaryEntry('gleichstand')!.example!, /Beide Rangscores sind 66/);
  // höchstens 20 % fehlende Börsentage: 19 von 23 Kursen reichen (19 · 5 ≥ 23 · 4), 18 nicht
  assert.ok(19 * 5 >= 23 * 4 && !(18 * 5 >= 23 * 4));
  assert.match(glossaryEntry('fehlende-kurstage')!.example!, /19 Kurse reichen \(4 fehlen, 17 %\), 18 Kurse nicht \(5 fehlen, 22 %\)/);
});

test('Rangscore-Beispiel der Hilfe stimmt mit der Formel überein', () => {
  // Score(w) = w/100 · G + (1 − w/100) · R  (03_Methodik, Abschnitt 7)
  const score = (w: number, g: number, r: number) => (w / 100) * g + (1 - w / 100) * r;
  assert.equal(score(60, 50, 90), 66);
  assert.match(glossaryEntry('rangscore')!.example!, /= 66/);
  assert.equal(score(60, 100, 50), 80);
  assert.equal(score(60, 0, 100), 40);
  assert.equal(score(60, 50, 0), 30);
});

test('Fehlermeldungen nennen Ursache und nächsten Schritt statt Technik', () => {
  const offline = describeError(new OfflineError());
  assert.equal(offline.kind, 'offline');
  assert.match(offline.text, /Erneut versuchen/);
  const server = describeError(new ServerError(500, 'status.json'));
  assert.equal(server.kind, 'server');
  assert.match(server.title, /Server antwortet nicht/);
  assert.match(server.text, /500/);
  assert.match(server.text, /nicht an deinem Gerät/);
  const missing = describeError(new NotFoundError('snapshots/x/manifest.bin'));
  assert.equal(missing.kind, 'fehlt');
  assert.doesNotMatch(missing.text, /manifest\.bin/);
  assert.match(missing.detail, /manifest\.bin/);
  assert.equal(describeError(new DecodeError('Unbekanntes Dateiformat')).kind, 'unlesbar');
  assert.equal(describeError(new SyntaxError('Unexpected token')).kind, 'unlesbar');
  assert.equal(describeError(new Error('irgendwas')).kind, 'unbekannt');
  assert.equal(describeError(new TypeError('Failed to fetch')).kind, 'offline');
});

test('Beträge: deutsche und englische Schreibweise, ungültige Eingaben', () => {
  assert.equal(parseAmount('1000'), 1000);
  assert.equal(parseAmount('2.500'), 2500);
  assert.equal(parseAmount('1.000,50'), 1000.5);
  assert.equal(parseAmount('1000,5'), 1000.5);
  assert.equal(parseAmount('1000.5'), 1000.5);
  assert.equal(parseAmount(' 1 000 '), 1000);
  for (const bad of ['', '   ', 'abc', '-5', '1,2,3', '12a', '1e6']) assert.equal(parseAmount(bad), null, bad);
});

test('Zeitplan-Hinweis: ehrlich über die Verspätung, mit tatsächlicher Startzeit', () => {
  const base = { schedule: { uhrzeit: '07:00', zeitzone: 'Europe/Berlin', wiederholungen_minuten: [15, 45, 120] } } as unknown as Status;
  assert.match(scheduleNote(base), /ab 07:00 Uhr geplant/);
  assert.match(scheduleNote(base), /oft einige Stunden später\.$/);
  const late = {
    ...base,
    last_run: { planned_start_utc: '2026-10-23T05:00:00Z', started_at_utc: '2026-10-23T09:44:41Z' },
  } as unknown as Status;
  assert.match(scheduleNote(late), /zuletzt um 11:44 Uhr statt 07:00 Uhr/);
  const punctual = { ...base, last_run: { planned_start_utc: '2026-10-23T05:00:00Z', started_at_utc: '2026-10-23T05:10:00Z' } } as unknown as Status;
  assert.doesNotMatch(scheduleNote(punctual), /zuletzt/);
});
