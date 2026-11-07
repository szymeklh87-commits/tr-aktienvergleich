/* Aktualität und Aktualisierungsfehler (ab 1.17) – ohne Browser. Aufruf: npm test */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { freshness, nextBerlinHour, nextMorningRun, nextNightRun, OVERDUE_HOURS, overdueAt, plainReason, sessionName, whenBerlin } from '../src/lib/freshness.ts';
import type { Status } from '../src/lib/types.ts';

const norm = (text: string | null | undefined) => (text ?? '').replace(/[  ]/g, ' ');
const at = (iso: string) => Date.parse(iso);

function status(over: Partial<Status> = {}): Status {
  return {
    schema: 'tr-status/1',
    generated_at_utc: '2026-10-24T11:05:00Z',
    app_mode: 'produktiv',
    latest_snapshot_id: '2026-10-23_aaaa',
    latest_complete_snapshot_id: '2026-10-23_aaaa',
    last_price_session: '2026-10-23',
    last_successful_check_utc: '2026-10-24T11:05:00Z',
    last_run: {
      run_id: 'r1',
      trigger: 'zeitplan',
      planned_start_utc: '2026-10-24T05:00:00Z',
      started_at_utc: '2026-10-24T09:17:00Z',
      finished_at_utc: '2026-10-24T10:40:00Z',
      status: 'veroeffentlicht',
      message: null,
      cutoff_session_date: '2026-10-23',
      attempt: 1,
    },
    schedule: { uhrzeit: '07:00', zeitzone: 'Europe/Berlin', wiederholungen_minuten: [15, 45, 120], nachtlauf_utc: '22:37', nachtlauf_wochentage: [1, 2, 3, 4, 5] },
    heartbeat_max_age_hours: 30,
    software_version: '1.17.0',
    // Montag 26.10.: letzte Börse schließt 21:00 UTC, plus eine Stunde Frist
    naechster_kursstand: { datum: '2026-10-26', ab_utc: '2026-10-26T22:00:00Z', boersen: ['XNYS'] },
    ...over,
  } as Status;
}

test('Datumsnamen und Zeitpunkte in Berliner Zeit (mit Ende der Sommerzeit am 25.10.2026)', () => {
  assert.equal(sessionName('2026-10-23'), 'Freitag, 23. Oktober');
  const now = at('2026-10-24T12:00:00Z'); // Samstag 14:00 Uhr Sommerzeit
  assert.equal(norm(whenBerlin(at('2026-10-24T22:00:00Z'), now)), 'morgen, 00:00 Uhr');
  assert.equal(norm(whenBerlin(at('2026-10-24T13:00:00Z'), now)), 'heute, 15:00 Uhr');
  assert.equal(norm(whenBerlin(at('2026-10-26T22:37:00Z'), now)), 'Montag, 26. Oktober, 23:37 Uhr');
});

test('Nächster Nachtlauf (Mo–Fr 22:37 UTC) und Morgenlauf (07:00 Uhr Berlin)', () => {
  const sat = at('2026-10-24T12:00:00Z');
  assert.equal(new Date(nextNightRun(status(), sat)!).toISOString(), '2026-10-26T22:37:00.000Z');
  assert.equal(new Date(nextMorningRun(status(), sat)!).toISOString(), '2026-10-25T06:00:00.000Z', 'Sonntag 07:00 Uhr Winterzeit');
  const monLate = at('2026-10-26T23:00:00Z');
  assert.equal(new Date(nextNightRun(status(), monLate)!).toISOString(), '2026-10-27T22:37:00.000Z');
  const fri = at('2026-10-23T05:30:00Z'); // Freitag 07:30 Uhr Sommerzeit
  assert.equal(new Date(nextMorningRun(status(), fri)!).toISOString(), '2026-10-24T05:00:00.000Z');
  assert.equal(nextNightRun(status({ schedule: { uhrzeit: '07:00', zeitzone: 'Europe/Berlin', wiederholungen_minuten: [] } }), sat), null, 'ohne Nachtlauf');
});

test('Aktuell: wann die nächsten Schlusskurse kommen und welche Läufe geplant sind', () => {
  const fr = freshness({ status: status(), shownSession: '2026-10-23', now: at('2026-10-24T12:00:00Z') });
  assert.equal(fr.tone, 'ok');
  assert.equal(fr.problem, null);
  assert.equal(norm(fr.headline), 'Schlusskurse vom Freitag, 23. Oktober');
  assert.match(norm(fr.next), /^Neue Schlusskurse \(Montag, 26\. Oktober\) gibt es ab Montag, 26\. Oktober, 23:00 Uhr\./);
  // Am Wochenende nicht der Sonntagmorgen (da gibt es nichts Neues), sondern der Nachtlauf nach dem nächsten Börsentag und
  // als Ersatz der Morgenlauf danach
  assert.match(norm(fr.next), /Geplant: Nachtlauf Montag, 26\. Oktober, 23:37 Uhr; fällt er aus, Morgenlauf Dienstag, 27\. Oktober, 07:00 Uhr – GitHub startet geplante Läufe oft einige Stunden später\./);
  assert.doesNotMatch(norm(fr.next), /morgen, 07:00/);
});

test('Berechenbar, aber noch nicht da: Hinweis; nach zwölf Stunden: überfällig mit nächstem Schritt', () => {
  const beat = { last_successful_check_utc: '2026-10-26T09:00:00Z' };
  const soon = freshness({ status: status(beat), shownSession: '2026-10-23', now: at('2026-10-27T03:00:00Z') });
  assert.equal(soon.tone, 'info');
  assert.match(norm(soon.next), /sind seit gestern, 23:00 Uhr berechenbar und kommen mit dem nächsten Lauf/);
  assert.match(norm(soon.next), /Sofort geht es mit „Kurse jetzt aktualisieren“/);
  // Der Nachtlauf dafür war geplant (GitHub verzögert ihn) – sonst der nächste Morgenlauf
  assert.match(norm(soon.next), /Der Nachtlauf war für gestern, 23:37 Uhr geplant; GitHub startet ihn oft einige Stunden später, sonst kommt der Stand mit dem Morgenlauf heute, 07:00 Uhr\./);
  // Kurz nach „berechenbar“, vor dem Nachtlauf: der Nachtlauf gleich und der Morgenlauf als Ersatz
  const early = freshness({ status: status(beat), shownSession: '2026-10-23', now: at('2026-10-26T22:10:00Z') });
  assert.match(norm(early.next), /Geplant: Nachtlauf heute, 23:37 Uhr; fällt er aus, Morgenlauf morgen, 07:00 Uhr/);
  const late = freshness({ status: status(beat), shownSession: '2026-10-23', now: at('2026-10-26T22:00:00Z') + (OVERDUE_HOURS + 1) * 3_600_000 });
  assert.equal(late.tone, 'warn');
  assert.equal(late.problem?.title, 'Neuer Kursstand überfällig');
  assert.match(norm(late.problem?.todo), /„Kurse jetzt aktualisieren“ startet den Lauf sofort/);
});

test('Gescheiterter Lauf: Grund in Alltagssprache, letzter Stand bleibt, was zu tun ist', () => {
  const failed = status({
    last_run: { ...status().last_run!, status: 'fehlgeschlagen', message: 'Anbieter drosselt bei XYZ – Checkpoint gesetzt', finished_at_utc: '2026-10-24T10:40:00Z' },
  });
  const fr = freshness({ status: failed, shownSession: '2026-10-23', now: at('2026-10-24T12:00:00Z') });
  assert.equal(fr.tone, 'warn');
  assert.equal(fr.problem?.title, 'Letzte Aktualisierung fehlgeschlagen');
  assert.match(norm(fr.problem?.text), /^Der Lauf von heute, 12:40 Uhr ist nicht fertig geworden: Der Kursanbieter hat zu viele Abfragen auf einmal abgelehnt \(Drosselung\)\. Angezeigt wird weiter der letzte geprüfte Stand\.$/);
  assert.match(norm(fr.problem?.todo), /Actions → Täglicher Lauf/);
  assert.equal(plainReason('Zeitbudget erreicht – Rest wird im nächsten Versuch fortgesetzt'), 'Die erlaubte Laufzeit war erreicht, bevor alle Kurse geladen waren.');
  assert.equal(plainReason(null), null);
  assert.equal(plainReason('x'.repeat(300))!.length, 158);
});

test('Server meldet sich nicht (Herzschlag älter als erlaubt) und Kurse noch nicht geliefert', () => {
  const quiet = freshness({ status: status({ last_successful_check_utc: '2026-10-22T08:00:00Z', naechster_kursstand: null }), shownSession: '2026-10-23', now: at('2026-10-24T12:00:00Z') });
  assert.equal(quiet.problem?.title, 'Server meldet sich nicht');
  const waiting = freshness({ status: status({ last_run: { ...status().last_run!, status: 'wartet_auf_provider' } }), shownSession: '2026-10-23', now: at('2026-10-24T12:00:00Z') });
  assert.equal(waiting.tone, 'info');
  assert.match(norm(waiting.next), /^Einige Börsen haben ihre Schlusskurse noch nicht geliefert/);
  const intraday = freshness({ status: status(), shownSession: '2026-10-26', intraday: true, now: at('2026-10-26T12:00:00Z') });
  assert.equal(norm(intraday.headline), 'Zwischenstand mit vorläufigen Kursen; letzte Schlusskurse vom Freitag, 23. Oktober');
});

// Ab 1.20.5 (Befund F02): offizieller Tageslauf getrennt vom Zwischenstand
function official(over: Partial<NonNullable<Status['offiziell']>> = {}): NonNullable<Status['offiziell']> {
  return {
    snapshot_id: '2026-11-02_aaaa',
    kursstand: '2026-11-02',
    vollstaendigkeit: 'vollstaendig',
    veroeffentlicht_utc: '2026-11-03T15:58:00Z',
    letzte_erfolgreiche_pruefung_utc: '2026-11-03T15:58:00Z',
    letzter_lauf: null,
    letzter_fehlschlag: null,
    fehlschlaege_seit_erfolg: 0,
    erster_fehlschlag_seit_erfolg_utc: null,
    ...over,
  };
}

test('Gescheiterter offizieller Lauf bleibt sichtbar, auch wenn danach ein Zwischenstand gelang (03.–07.11.2026)', () => {
  const failedRun = {
    run_id: 'r9',
    trigger: 'nachtlauf',
    planned_start_utc: null,
    started_at_utc: '2026-11-07T01:59:00Z',
    finished_at_utc: '2026-11-07T02:41:00Z',
    status: 'fehlgeschlagen',
    message: 'NoDataError: XYZ: keine gültigen Tageskurse im Zeitraum',
    cutoff_session_date: '2026-11-06',
    attempt: 1,
  };
  const s = status({
    last_price_session: '2026-11-02',
    // letzter Lauf überhaupt: ein erfolgreicher Zwischenstand – bis 1.20.4 verdeckte er den Fehlschlag
    last_run: { ...status().last_run!, run_id: 'z1', trigger: 'zwischenstand', status: 'veroeffentlicht', finished_at_utc: '2026-11-07T03:10:00Z' },
    last_successful_check_utc: '2026-11-03T15:58:00Z',
    naechster_kursstand: { datum: '2026-11-03', ab_utc: '2026-11-03T22:00:00Z', boersen: ['XNYS'] },
    offiziell: official({ letzter_lauf: failedRun, letzter_fehlschlag: failedRun, fehlschlaege_seit_erfolg: 17, erster_fehlschlag_seit_erfolg_utc: '2026-11-03T15:58:30Z' }),
  });
  const fr = freshness({ status: s, shownSession: '2026-11-06', intraday: true, basisChecked: false, basisNote: 'Ungeprüfte Grundlage: … Keine Kaufsignale auf dieser Grundlage.', now: at('2026-11-07T03:30:00Z') });
  assert.equal(fr.tone, 'warn');
  assert.equal(fr.problem?.kind, 'fehlgeschlagen');
  assert.equal(fr.problem?.title, 'Tägliche Aktualisierung scheitert wiederholt');
  assert.match(norm(fr.problem?.text), /^Der Lauf von heute, 03:41 Uhr ist nicht fertig geworden: NoDataError: XYZ: keine gültigen Tageskurse im Zeitraum\. Seit/);
  assert.match(norm(fr.problem?.text), /Seit Dienstag, 3\. November, 16:58 Uhr ist er 17-mal gescheitert\./);
  assert.match(norm(fr.problem?.text), /letzte geprüfte Stand mit den Schlusskursen vom Montag, 2\. November\.$/);
  assert.equal(fr.unverifiedBase, 'Ungeprüfte Grundlage: … Keine Kaufsignale auf dieser Grundlage.');
  assert.equal(norm(fr.headline), 'Zwischenstand auf ungeprüfter Grundlage; letzte geprüfte Schlusskurse vom Montag, 2. November');
});

test('Erfolg nach Fehlschlägen: kein Problem; „Server meldet sich nicht“ nur nach dem offiziellen Herzschlag', () => {
  const okRun = { ...status().last_run!, finished_at_utc: '2026-11-07T06:30:00Z' };
  const fine = freshness({
    status: status({ offiziell: official({ letzter_lauf: okRun, letzte_erfolgreiche_pruefung_utc: '2026-11-07T06:30:00Z' }), naechster_kursstand: null }),
    shownSession: '2026-11-06',
    now: at('2026-11-07T08:00:00Z'),
  });
  assert.equal(fine.problem, null);
  assert.equal(fine.unverifiedBase, null);
  // Zwischenstände halten die alte status.json-Angabe frisch, der offizielle Lauf meldet sich aber seit 40 Stunden nicht
  const quiet = freshness({
    status: status({ last_successful_check_utc: '2026-11-07T07:00:00Z', offiziell: official({ letzte_erfolgreiche_pruefung_utc: '2026-11-05T16:00:00Z' }), naechster_kursstand: null }),
    shownSession: '2026-11-06',
    intraday: true,
    basisChecked: true,
    now: at('2026-11-07T08:00:00Z'),
  });
  assert.equal(quiet.problem?.kind, 'stumm');
  assert.equal(quiet.unverifiedBase, null, 'geprüfte Grundlage: kein Hinweis');
});

test('Überfällig spätestens um 07:00 Uhr Berliner Zeit am Morgen danach (ab 1.22, F06)', () => {
  const beat = { last_successful_check_utc: '2026-10-26T09:00:00Z' };
  // berechenbar Mo 22:00 UTC (23:00 Berlin, Winterzeit): bis Di 06:59 UTC noch unterwegs, ab 07:00 Berlin (06:00 UTC) überfällig
  const ready = at('2026-10-26T22:00:00Z');
  assert.equal(overdueAt(ready), at('2026-10-27T06:00:00Z'));
  assert.equal(freshness({ status: status(beat), shownSession: '2026-10-23', now: at('2026-10-27T05:59:00Z') }).tone, 'info');
  const late = freshness({ status: status(beat), shownSession: '2026-10-23', now: at('2026-10-27T06:01:00Z') });
  assert.equal(late.problem?.title, 'Neuer Kursstand überfällig');
  assert.match(late.problem?.text ?? '', /normalerweise ist der neue Stand bis 07:00 Uhr da/);
  // Sommerzeit: 07:00 Berlin = 05:00 UTC
  assert.equal(nextBerlinHour(at('2026-07-01T00:30:00Z'), 7), at('2026-07-01T05:00:00Z'));
  // nie später als zwölf Stunden nach „berechenbar“
  assert.ok(overdueAt(at('2026-10-27T00:00:00Z')) <= at('2026-10-27T00:00:00Z') + OVERDUE_HOURS * 3_600_000);
});
