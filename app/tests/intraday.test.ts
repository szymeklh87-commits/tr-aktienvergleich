/* Zwischenstand (ab 1.8): Texte und Entscheidungen der Anzeige – ohne Browser. Aufruf: npm test */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { berlinClock, intradayBanner, intradayExplanation, intradayLabel, isIntraday, isOlderStand } from '../src/lib/intraday.ts';
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

test('Hinweisleiste nennt Aktien, noch geschlossene Börsen und den offiziellen Stand', () => {
  const text = norm(intradayBanner(manifest()));
  assert.match(text, /für 2.345 Aktien/);
  assert.match(text, /noch nicht geöffnet/);
  assert.match(text, /Schlusskurse vom 12\.10\.2026/);
  const closedOnly = manifest();
  closedOnly.zwischenstand!.oeffnung_utc = {};
  assert.match(norm(intradayBanner(closedOnly)), /3 Börsen ohne Kurs von heute/);
});

test('Erklärung: Kurse bis, Börsen mit und ohne Kurs (mit Öffnungszeit), offizieller Stand', () => {
  const lines = intradayExplanation(manifest()).map(norm);
  assert.match(lines[0], /bis 12:15 Uhr/);
  assert.match(lines[1], /^2.345 Aktien haben einen Kurs von heute/);
  assert.match(lines[2], /\(öffnet 15:30 Uhr\)/);
  assert.match(lines[3], /Offizieller Stand mit Schlusskursen: 12\.10\.2026/);
});

test('Der offizielle Stand gilt neben einem Zwischenstand nicht als „älterer Stand“', () => {
  const status = { latest_snapshot_id: 'Z', latest_official_snapshot_id: 'O', zwischenstand: { snapshot_id: 'Z' } } as unknown as Status;
  assert.equal(isOlderStand(status, 'Z'), false);
  assert.equal(isOlderStand(status, 'O'), false);
  assert.equal(isOlderStand(status, 'ALT'), true);
  assert.equal(isOlderStand({ ...status, zwischenstand: null } as Status, 'O'), true);
});
