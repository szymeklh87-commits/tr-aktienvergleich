/* Zwischenstand (ab 1.8): Texte und Entscheidungen der Anzeige – ohne Browser. Aufruf: npm test */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { berlinClock, closeDaysText, closeLabel, countsWithClose, intradayBanner, intradayExplanation, intradayLabel, isIntraday, isOlderStand } from '../src/lib/intraday.ts';
import type { Manifest, Status } from '../src/lib/types.ts';

const norm = (text: string) => text.replace(/[  ]/g, ' ');

function manifest(): Manifest {
  return {
    art: 'zwischenstand',
    cutoff_day: 20739, // 13.10.2026
    cutoff_session_date: '2026-10-13',
    zwischenstand: {
      stichtag: '2026-10-13',
      kurse_bis_utc: '2026-10-13T10:15:00Z',
      kurse_ab_utc: '2026-10-13T05:00:00Z',
      abgerufen_utc: '2026-10-13T10:30:00Z',
      aktien_mit_kurs: 2345,
      davon_sitzung_beendet: 900,
      abrufe: 120,
      gedrosselt: false,
      offizieller_stand: '2026-10-12_abcdef12',
      offizieller_stichtag: '2026-10-12',
      tagwahl: [],
      boersen_mit_kurs: ['XETR', 'XTKS'],
      boersen_ohne_kurs: ['XNYS', 'XNAS', 'XTSE'],
      oeffnung_utc: { XNYS: '2026-10-13T13:30:00Z', XNAS: '2026-10-13T13:30:00Z', XTSE: null },
      beschreibung: '',
    },
  } as unknown as Manifest;
}

test('Uhrzeit in Berliner Zeit und Kennzeichnung', () => {
  assert.equal(berlinClock('2026-10-13T10:15:00Z'), '12:15 Uhr');
  assert.equal(berlinClock(null), '–');
  assert.equal(isIntraday({ art: 'zwischenstand' }), true);
  assert.equal(isIntraday({}), false);
  assert.equal(norm(intradayLabel({ cutoff_session_date: '2026-10-13', kurse_bis_utc: '2026-10-13T10:15:00Z' })), 'Zwischenstand 13.10.2026, 12:15 Uhr');
});

test('Hinweisleiste nennt Aktien, noch geschlossene Börsen und den Stand mit Schlusskursen', () => {
  const text = norm(intradayBanner(manifest()));
  assert.match(text, /für 2.345 Aktien/);
  assert.match(text, /noch nicht geöffnet/);
  assert.match(text, /Schlusskurse aller Börsen: Stand vom 12\.10\.2026/);
  assert.doesNotMatch(text, /[Oo]ffiziell/);
  const closedOnly = manifest();
  closedOnly.zwischenstand!.oeffnung_utc = {};
  assert.match(norm(intradayBanner(closedOnly)), /3 Börsen ohne Kurs von heute/);
});

test('Erklärung: Kurse bis, Börsen mit und ohne Kurs (mit Öffnungszeit), Stand mit Schlusskursen', () => {
  const lines = intradayExplanation(manifest()).map(norm);
  assert.match(lines[0], /bis 12:15 Uhr/);
  assert.match(lines[1], /^2.345 Aktien haben einen Kurs von heute/);
  assert.match(lines[2], /\(öffnet 15:30 Uhr\)/);
  assert.match(lines[3], /Schlusskurse aller Börsen gibt es im Stand vom 12\.10\.2026 \(Knopf „Schlusskurse 12\.10\.“\)/);
  assert.ok(lines.every((line) => !/[Oo]ffiziell/.test(line)), 'ab 1.12.1 ohne „offiziell“');
});

test('Der offizielle Stand gilt neben einem Zwischenstand nicht als „älterer Stand“', () => {
  const status = { latest_snapshot_id: 'Z', latest_official_snapshot_id: 'O', zwischenstand: { snapshot_id: 'Z' } } as unknown as Status;
  assert.equal(isOlderStand(status, 'Z'), false);
  assert.equal(isOlderStand(status, 'O'), false);
  assert.equal(isOlderStand(status, 'ALT'), true);
  assert.equal(isOlderStand({ ...status, zwischenstand: null } as Status, 'O'), true);
});

test('Knopf zum Stand mit Schlusskursen nennt den Tag (ab 1.12.1 statt „Offiziell“)', () => {
  assert.equal(closeLabel('2026-10-13'), 'Schlusskurse 13.10.');
  assert.equal(closeLabel('2026-01-02'), 'Schlusskurse 02.01.');
  assert.equal(closeLabel(null), 'Schlusskurse');
});

test('Ab 1.13: Aktien ohne Kurs von heute zählen mit dem letzten Schlusskurs (Simons Wahl)', () => {
  const old = manifest();
  assert.equal(countsWithClose(old.zwischenstand), false, 'Stände bis 1.12: diese Aktien fehlen');
  assert.match(norm(intradayExplanation(old)[2]), /deshalb nicht in den Ranglisten/);
  const now = manifest();
  now.zwischenstand!.boersen_mit_schlusskurs = { XNYS: '2026-10-12', XNAS: '2026-10-12' };
  now.zwischenstand!.aktien_mit_schlusskurs = 3100;
  assert.equal(countsWithClose(now.zwischenstand), true);
  assert.equal(closeDaysText(now.zwischenstand!), 'vom 12.10.');
  const line = norm(intradayExplanation(now)[2]);
  assert.match(line, /^Noch ohne Kurs von heute: Aktien aus /);
  assert.match(line, /Sie zählen mit dem Schlusskurs vom 12\.10\. – ihre Zeiträume enden dort/);
  assert.doesNotMatch(line, /nicht in den Ranglisten/);
  assert.match(norm(intradayBanner(now)), /noch nicht geöffnet – mit Schlusskurs vom 12\.10\./);
  assert.doesNotMatch(intradayBanner(now), /\.\./, 'kein doppelter Punkt nach dem Datum');
  // Ohne Tagesangabe (keine Börse mehr geschlossen, nur einzelne Aktien ohne Handel)
  now.zwischenstand!.boersen_mit_schlusskurs = {};
  assert.equal(closeDaysText(now.zwischenstand!), 'des Handelstags davor');
});
