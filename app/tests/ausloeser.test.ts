/* Externer Auslöser für den Nachtlauf (ops/externer-ausloeser/nachtlauf-ausloeser.gs, ab 1.17) – mit nachgebildeten
 * Google-Diensten, ohne Google-Konto und ohne Netz. Geprüft werden Adresse, Kopfzeilen und Nutzlast des Aufrufs an
 * GitHub, die Wochentagsregel (nur in Nächten nach einem Börsentag, über das Ende der Sommerzeit), das fehlende Token,
 * Fehlerantworten ohne Ausnahme (sonst schickt Google Fehler-E-Mails), dass das Token nie im Protokoll steht, und der
 * Zeitplan. Nicht geprüft werden kann hier, ob Google und GitHub selbst so antworten. Aufruf: npm test */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const SOURCE = readFileSync(new URL('../../ops/externer-ausloeser/nachtlauf-ausloeser.gs', import.meta.url), 'utf8');
const TOKEN = 'github_pat_nur-im-test';
const DISPATCH = 'https://api.github.com/repos/szymeklh87-commits/tr-aktienvergleich/actions/workflows/nachtlauf.yml/dispatches';

interface FetchCall {
  url: string;
  options: { method: string; contentType: string; headers: Record<string, string>; payload: string; muteHttpExceptions: boolean };
}

interface Trigger {
  handler: string;
  settings: Record<string, unknown>;
}

interface Sandbox {
  calls: FetchCall[];
  logs: string[];
  triggers: Trigger[];
  run: (fn: string) => unknown;
}

/** Lädt das Skript wie Apps Script: alle Funktionen global, Google-Dienste nachgebildet, „jetzt“ fest. */
function sandbox({ now, token = TOKEN, code = 204, body = '', offline = false }: { now: string; token?: string | null; code?: number; body?: string; offline?: boolean }): Sandbox {
  const calls: FetchCall[] = [];
  const logs: string[] = [];
  const triggers: Trigger[] = [{ handler: 'alterAusloeser', settings: {} }];
  const context = vm.createContext({
    NOW: now,
    console: { log: (...parts: unknown[]) => logs.push(parts.map(String).join(' ')) },
    Utilities: {
      // Wie Apps Script für das Muster „yyyy-MM-dd“: Kalenderdatum in der angegebenen Zeitzone
      formatDate: (date: Date, timeZone: string, pattern: string) => {
        assert.equal(pattern, 'yyyy-MM-dd');
        return new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
      },
    },
    PropertiesService: {
      getScriptProperties: () => ({ getProperty: (name: string) => (name === 'GITHUB_TOKEN' ? token : null) }),
    },
    UrlFetchApp: {
      fetch: (url: string, options: FetchCall['options']) => {
        calls.push({ url, options });
        // Wie UrlFetchApp ohne Netz: Ausnahme trotz muteHttpExceptions (diese gilt nur für HTTP-Fehlercodes)
        if (offline) throw new Error(`Address unavailable: ${url} (${options.headers.Authorization})`);
        return { getResponseCode: () => code, getContentText: () => body };
      },
    },
    ScriptApp: {
      getProjectTriggers: () => [...triggers],
      deleteTrigger: (trigger: Trigger) => {
        triggers.splice(triggers.indexOf(trigger), 1);
      },
      newTrigger: (handler: string) => {
        const settings: Record<string, unknown> = {};
        const builder = {
          timeBased: () => builder,
          everyDays: (n: number) => ((settings.everyDays = n), builder),
          atHour: (h: number) => ((settings.atHour = h), builder),
          nearMinute: (m: number) => ((settings.nearMinute = m), builder),
          inTimezone: (tz: string) => ((settings.inTimezone = tz), builder),
          create: () => {
            const trigger = { handler, settings };
            triggers.push(trigger);
            return trigger;
          },
        };
        return builder;
      },
    },
  });
  // „new Date()“ ohne Angabe = festes „jetzt“; mit Angabe wie üblich
  vm.runInContext(
    `(() => {
      const RealDate = Date;
      function FixedDate(...args) { return args.length ? new RealDate(...args) : new RealDate(NOW); }
      FixedDate.prototype = RealDate.prototype;
      FixedDate.UTC = RealDate.UTC;
      FixedDate.parse = RealDate.parse;
      FixedDate.now = () => RealDate.parse(NOW);
      globalThis.Date = FixedDate;
    })();`,
    context,
  );
  vm.runInContext(SOURCE, context, { filename: 'nachtlauf-ausloeser.gs' });
  return { calls, logs, triggers, run: (fn: string) => vm.runInContext(`${fn}()`, context) };
}

test('Nacht nach einem Börsentag: startet den Nachtlauf mit Token im Kopf, Zweig main, ohne das Token zu protokollieren', () => {
  // Dienstag 27.10.2026, 00:40 Uhr Berliner Winterzeit = Montag 23:40 UTC (nach Montags Börsenschluss)
  const s = sandbox({ now: '2026-10-26T23:40:00Z' });
  s.run('nachtlaufStarten');
  assert.equal(s.calls.length, 1);
  const { url, options } = s.calls[0];
  assert.equal(url, DISPATCH);
  assert.equal(options.method, 'post');
  assert.equal(options.contentType, 'application/json');
  assert.equal(options.headers.Authorization, `Bearer ${TOKEN}`);
  assert.equal(options.headers.Accept, 'application/vnd.github+json');
  assert.equal(options.headers['X-GitHub-Api-Version'], '2022-11-28');
  assert.deepEqual(JSON.parse(options.payload), { ref: 'main' });
  assert.equal(options.muteHttpExceptions, true);
  assert.ok(s.logs.some((line) => line.includes('gestartet (HTTP 204)')), s.logs.join('\n'));
  assert.ok(!s.logs.join('\n').includes(TOKEN));
});

test('Wochentagsregel nach Berliner Datum: Dienstag- bis Samstagnacht ja, Sonntag- und Montagnacht nein – auch über das Ende der Sommerzeit', () => {
  const cases: [string, boolean, string][] = [
    ['2026-10-23T22:40:00Z', true, 'Samstag 24.10., 00:40 Uhr Sommerzeit (nach Freitag)'],
    ['2026-10-24T22:40:00Z', false, 'Sonntag 25.10., 00:40 Uhr Sommerzeit (nach Samstag)'],
    ['2026-10-25T23:40:00Z', false, 'Montag 26.10., 00:40 Uhr Winterzeit (nach Sonntag)'],
    ['2026-10-26T23:25:00Z', true, 'Dienstag 27.10., 00:25 Uhr (frühester Zeitpunkt des Auslösers)'],
    ['2026-10-27T23:55:00Z', true, 'Mittwoch 28.10., 00:55 Uhr (spätester Zeitpunkt)'],
    ['2026-10-29T23:40:00Z', true, 'Freitag 30.10., 00:40 Uhr'],
    ['2026-10-30T23:40:00Z', true, 'Samstag 31.10., 00:40 Uhr'],
    ['2026-10-31T23:40:00Z', false, 'Sonntag 01.11., 00:40 Uhr'],
    ['2026-03-29T22:40:00Z', false, 'Montag 30.03.2026, 00:40 Uhr Sommerzeit (nach Sonntag)'],
    ['2026-03-30T22:40:00Z', true, 'Dienstag 31.03.2026, 00:40 Uhr Sommerzeit'],
  ];
  for (const [now, starts, label] of cases) {
    const s = sandbox({ now });
    s.run('nachtlaufStarten');
    assert.equal(s.calls.length, starts ? 1 : 0, label);
    if (!starts) assert.ok(s.logs.some((line) => line.includes('nichts gestartet')), label);
  }
});

test('ohne Token: kein Aufruf, Hinweis auf die Skripteigenschaft', () => {
  const s = sandbox({ now: '2026-10-26T23:40:00Z', token: null });
  assert.equal(s.run('jetztTesten'), undefined);
  assert.equal(s.calls.length, 0);
  assert.ok(s.logs.some((line) => line.includes('GITHUB_TOKEN fehlt')));
});

test('Fehlerantworten: keine Ausnahme, Grund und nächster Schritt im Protokoll, Token nie', () => {
  // Antworttexte wie von GitHub (404 und 422 am 24.10.2026 mit falschem Workflow bzw. Zweig abgefragt)
  const expected: [number, string, string][] = [
    [401, '{"message":"Bad credentials","status":"401"}', 'Token ungültig, abgelaufen'],
    [403, '{"message":"Resource not accessible by personal access token","status":"403"}', 'Actions: Read and write'],
    [404, '{"message":"Not Found","status":"404"}', 'Repository oder Workflow-Datei nicht gefunden'],
    [422, '{"message":"No ref found for: main","status":"422"}', 'Zweig in BRANCH falsch'],
    [429, 'kein JSON', 'Unerwartete Antwort'],
    [500, '', 'gestört oder überlastet'],
    [503, `{"message":"Service unavailable ${TOKEN}"}`, 'gestört oder überlastet'],
  ];
  for (const [code, body, hint] of expected) {
    const s = sandbox({ now: '2026-10-26T23:40:00Z', code, body });
    assert.doesNotThrow(() => s.run('nachtlaufStarten'));
    assert.equal(s.calls.length, 1);
    const log = s.logs.join('\n');
    assert.ok(log.includes(`HTTP ${code}`) && log.includes(hint), `${code}: ${log}`);
    const message = body.startsWith('{') ? (JSON.parse(body) as { message: string }).message.split(TOKEN).join('…') : '';
    if (message) assert.ok(log.includes(`„${message}“`), `${code}: ${log}`);
    assert.ok(!log.includes(TOKEN), `${code}: ${log}`);
  }
  // Neuere GitHub-Schnittstelle antwortet mit 200 statt 204
  const ok = sandbox({ now: '2026-10-26T23:40:00Z', code: 200 });
  ok.run('nachtlaufStarten');
  assert.ok(ok.logs.some((line) => line.includes('gestartet (HTTP 200)')));
});

test('ohne Netz: keine Ausnahme (keine Fehler-E-Mail von Google), Hinweis im Protokoll, Token unkenntlich', () => {
  const s = sandbox({ now: '2026-10-26T23:40:00Z', offline: true });
  assert.doesNotThrow(() => s.run('nachtlaufStarten'));
  assert.equal(s.calls.length, 1);
  const log = s.logs.join('\n');
  assert.ok(log.includes('GitHub nicht erreichbar') && log.includes('nächste Termin'), log);
  assert.ok(!log.includes(TOKEN), log);
});

test('jetztTesten startet sofort – auch in einer Sonntagnacht', () => {
  const s = sandbox({ now: '2026-10-24T22:40:00Z' });
  s.run('jetztTesten');
  assert.equal(s.calls.length, 1);
  assert.equal(s.calls[0].url, DISPATCH);
});

test('zeitplanEinrichten: ersetzt vorhandene Auslöser durch einen täglichen gegen 00:40 Uhr Berliner Zeit', () => {
  const s = sandbox({ now: '2026-10-24T10:00:00Z' });
  s.run('zeitplanEinrichten');
  assert.equal(s.triggers.length, 1);
  assert.equal(s.triggers[0].handler, 'nachtlaufStarten');
  assert.deepEqual(s.triggers[0].settings, { everyDays: 1, atHour: 0, nearMinute: 40, inTimezone: 'Europe/Berlin' });
  assert.equal(s.calls.length, 0);
});
