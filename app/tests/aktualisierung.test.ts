/* „Jetzt aktualisieren“ (ab 1.21; ab 1.22 Start auf GitHub ohne Zugang in der App): Anfragen, Zeile zum Einfügen, Fortschritt,
 * öffentliche Schnittstelle, Zeitangaben der Kurse – ohne Browser. Aufruf: npm test */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { eingabeZeile, newKennung, progress, requestPayload, stepLabel, valuesFor, type UpdateJob } from '../src/lib/aktualisierung.ts';
import { errorText, GitHubError, PublicGitHub, workflowPage } from '../src/lib/github.ts';
import { bytesToBase64, decodeJson, deriveKey, encodeJson } from '../src/lib/container.ts';
import { knownDelay, mergeQuotes, newerQuote, quoteStatus, quotesFromDelivery, type Delivery, type LiveQuote } from '../src/lib/livekurse.ts';

const at = (iso: string) => Date.parse(iso);

test('Kennung: „k“, Sekunden in Basis 36, Bindestrich, 16 Zufallszeichen – wie der Server sie prüft', () => {
  const now = at('2026-10-31T12:00:00Z');
  const kennung = newKennung(now, (n) => new Uint8Array(n).fill(35));
  assert.match(kennung, /^k[0-9a-z]{6,8}-[0-9a-z]{16}$/);
  assert.equal(parseInt(kennung.slice(1, kennung.indexOf('-')), 36), now / 1000);
  assert.notEqual(newKennung(now), newKennung(now));
});

test('Anfrage: doppelte ISINs einmal, höchstens 250, sichtbare Zahl begrenzt, Tagesverlauf nur für angefragte Aktien', () => {
  const values = Array.from({ length: 300 }, (_, i) => ({ isin: `DE${String(i).padStart(9, '0')}0`, symbol: `S${i}.DE` }));
  const payload = requestPayload('kabc123-0123456789abcdef', 'merkliste', [values[0], ...values], 400, [values[1].isin, 'US0378331005', values[2].isin, values[3].isin, values[4].isin], at('2026-10-31T12:00:00.789Z'));
  assert.equal(payload.werte.length, 250);
  assert.equal(new Set(payload.werte.map((v) => v.isin)).size, 250);
  assert.equal(payload.sichtbar, 250);
  assert.deepEqual(payload.kursverlauf, [values[1].isin, values[2].isin, values[3].isin]);
  assert.equal(payload.erstellt_utc, '2026-10-31T12:00:00Z');
  assert.equal(payload.schema, 'tr-aktualisierung-anfrage/1');
});

test('Werte: nur Aktien mit gültigem Kurssymbol, Reihenfolge bleibt', () => {
  const symbols: Record<string, string | null> = { A: 'SAP.DE', B: null, C: '$(x)', D: 'AAPL' };
  const result = valuesFor(['A', 'B', 'C', 'D'], (isin) => symbols[isin]);
  assert.deepEqual(result.values, [{ isin: 'A', symbol: 'SAP.DE' }, { isin: 'D', symbol: 'AAPL' }]);
  assert.deepEqual(result.without, ['B', 'C']);
});

function job(over: Partial<UpdateJob> = {}): UpdateJob {
  return {
    kennung: 'k1', scope: 'merkliste', label: 'Merkliste', isins: [], requestedAt: at('2026-10-31T12:00:00Z'), openedAt: at('2026-10-31T12:00:02Z'), runId: null, runUrl: null,
    runStartedAt: null, phase: 'wartet', stepName: null, stepIndex: 0, stepCount: 0, partsReceived: 0, partsTotal: null, quotesReceived: 0, missing: 0, finishedAt: null, error: null, ...over,
  };
}

test('Fortschritt: jede Phase mit Text, Anteil und Ende', () => {
  const now = at('2026-10-31T12:00:12Z');
  const waiting = progress(job({ phase: 'start', openedAt: null }), now);
  assert.equal(waiting.title, 'Start auf GitHub');
  assert.match(waiting.detail, /Zeile kopieren und GitHub öffnen/);
  assert.match(progress(job({ phase: 'start' }), now).detail, /GitHub geöffnet vor 10 s – dort „Run workflow“, Zeile einfügen, starten/);
  assert.equal(progress(job({ phase: 'start' }), now).fraction, null, 'kein Fortschrittsbalken, solange niemand gestartet hat');
  assert.match(progress(job(), now).title, /Wartet auf einen GitHub-Rechner/);
  const running = progress(job({ phase: 'laeuft', stepName: 'Kurse werden abgerufen und geliefert', stepIndex: 5, stepCount: 6 }), now);
  assert.match(running.detail, /Schritt 5 von 6: Kurse werden abgerufen/);
  assert.ok(running.fraction !== null && running.fraction > 0 && running.fraction < 1);
  const part = progress(job({ phase: 'teil', partsReceived: 1, partsTotal: 2, quotesReceived: 10 }), now);
  assert.match(part.title, /Teil 1 von 2/);
  const done = progress(job({ phase: 'fertig', quotesReceived: 12, missing: 1, finishedAt: at('2026-10-31T12:00:40Z') }), now);
  assert.equal(done.done, true);
  assert.match(done.detail, /12 Kurse, 1 ohne Kurs – nach 40 s/);
  const failed = progress(job({ phase: 'fehler', error: 'Grund' }), now);
  assert.deepEqual([failed.failed, failed.detail], [true, 'Grund']);
  assert.equal(stepLabel('Kurse abrufen und liefern (sichtbare Aktien zuerst)'), 'Kurse werden abgerufen und geliefert');
  assert.equal(stepLabel('Website bereitstellen'), 'Website wird bereitgestellt');
});

test('Zeile zum Einfügen: Kennung, Punkt, Base64 – wie der Server sie trennt (util/eingabe.py)', () => {
  const line = eingabeZeile('kt3x9a0b-0123456789abcdef', 'QUJD+/==');
  assert.equal(line, 'kt3x9a0b-0123456789abcdef.QUJD+/==');
  const [kennung, rest] = [line.slice(0, line.indexOf('.')), line.slice(line.indexOf('.') + 1)];
  assert.match(kennung, /^k[0-9a-z]{6,8}-[0-9a-z]{16}$/);
  assert.match(rest, /^[A-Za-z0-9+/]+={0,2}$/);
});

interface Call {
  url: string;
  init: RequestInit | undefined;
}

function fakeFetch(answers: (url: string) => { status: number; body?: string | Uint8Array; headers?: Record<string, string> }) {
  const calls: Call[] = [];
  const fetcher = async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const a = answers(url);
    return new Response(a.status === 204 ? null : ((a.body ?? '{}') as BodyInit), { status: a.status, headers: a.headers });
  };
  return { calls, fetcher };
}

test('Öffentliche Schnittstelle: nie ein Kopf „Authorization“, keine Cookies, kein Referrer; Dateien zu einem festen Commit', async () => {
  const sha = 'a'.repeat(40);
  const { calls, fetcher } = fakeFetch((url) => {
    if (url.includes('/commits/kurse-aktuell')) return { status: 200, body: `${sha}\n`, headers: { 'x-ratelimit-remaining': '57', 'x-ratelimit-reset': '1793700000' } };
    if (url.includes('/actions/workflows/aktualisieren.yml/runs?')) return { status: 200, body: JSON.stringify({ workflow_runs: [{ id: 7, status: 'queued' }] }) };
    if (url === `https://raw.githubusercontent.com/konto/repo/${sha}/aktuell/k1-1.bin`) return { status: 200, body: new Uint8Array([1, 2, 3]) };
    return { status: 404 };
  });
  const api = new PublicGitHub('konto/repo', fetcher);
  assert.equal(await api.branchHead('kurse-aktuell'), sha);
  assert.equal(api.remaining, 57);
  assert.deepEqual([...(await api.file('aktuell/k1-1.bin', sha))!], [1, 2, 3]);
  assert.equal(await api.file('aktuell/k1-2.bin', sha), null);
  assert.equal(await api.file('aktuell/k1-1.bin', 'main'), null, 'nur zu einem festen Commit – nie über einen Branch-Namen (Zwischenspeicher)');
  assert.equal((await api.recentRuns('aktualisieren.yml', '2026-11-08T10:00:00Z'))[0].id, 7);
  assert.equal(await api.branchHead('gibt-es-nicht'), null);
  for (const call of calls) {
    const headers = new Headers(call.init?.headers);
    assert.equal(headers.has('authorization'), false, call.url);
    assert.equal(call.init?.credentials, 'omit');
    assert.equal(call.init?.referrerPolicy, 'no-referrer');
  }
  assert.ok(calls.some((c) => c.url.includes('created=%3E%3D2026-11-08T10%3A00%3A00Z')));
  assert.equal(workflowPage('konto/repo', 'aktualisieren.yml'), 'https://github.com/konto/repo/actions/workflows/aktualisieren.yml');
});

test('Öffentliche Schnittstelle: Abfragegrenze erkannt, danach bis zum Zurücksetzen keine weiteren Abfragen', async () => {
  const reset = Math.floor(Date.now() / 1000) + 600;
  const { calls, fetcher } = fakeFetch(() => ({ status: 403, body: '{"message":"API rate limit exceeded"}', headers: { 'x-ratelimit-remaining': '0', 'x-ratelimit-reset': String(reset) } }));
  const api = new PublicGitHub('konto/repo', fetcher);
  await assert.rejects(api.run(1), (e: unknown) => e instanceof GitHubError && e.kind === 'limit' && e.resetAt === reset * 1000);
  await assert.rejects(api.run(1), (e: unknown) => e instanceof GitHubError && e.kind === 'limit');
  assert.equal(calls.length, 1, 'zweite Abfrage gar nicht erst gesendet');
  assert.match(errorText(new GitHubError('limit', 'x', 403, reset * 1000)), /60 je Stunde\) – die App schaut ab \d\d:\d\d Uhr wieder nach/);
  const offline = new PublicGitHub('konto/repo', async () => {
    throw new TypeError('Failed to fetch');
  });
  await assert.rejects(offline.run(1), (e: unknown) => e instanceof GitHubError && e.kind === 'offline');
  assert.throws(() => new PublicGitHub('kein repo'));
});

const delivery = (over: Record<string, unknown> = {}): Delivery => ({
  schema: 'tr-kursaktualisierung/1', kennung: 'k1', teil: 1, teile: 1, umfang: 'aktie', angefragt_utc: '2026-11-03T09:59:00Z', erstellt_utc: '2026-11-03T10:00:05Z',
  quelle: { name: 'Yahoo Finance', weg: 'quote', hinweis: '' }, fehlend: [], kursverlauf: {},
  kurse: [
    { isin: 'DE0007164600', symbol: 'SAP.DE', kurs: 230.5, einheit: 'EUR', kurszeit_utc: '2026-11-03T09:45:00Z', sitzung: '2026-11-03', marktstatus: 'REGULAR', verzoegerung_min: 15, verzoegerung_quelle: 'yahoo_antwort', vortag: 228, abrufzeit_utc: '2026-11-03T10:00:04Z', ...over },
    { isin: 'XX123', kurs: 1, kurszeit_utc: '2026-11-03T09:45:00Z', abrufzeit_utc: '2026-11-03T10:00:04Z' },
    { isin: 'US0378331005', kurs: Number.NaN, kurszeit_utc: '2026-11-03T09:45:00Z', abrufzeit_utc: '2026-11-03T10:00:04Z' },
  ],
});

test('Lieferung: nur gültige Kurse; neuere Kurszeit gewinnt', () => {
  const quotes = quotesFromDelivery(delivery());
  assert.equal(quotes.length, 1);
  assert.equal(quotes[0].delayMin, 15);
  const older = { ...quotes[0], quoteTime: quotes[0].quoteTime - 60_000, price: 1 };
  assert.equal(newerQuote(quotes[0], older).price, 230.5);
  assert.equal(newerQuote(older, quotes[0]).price, 230.5);
  const map = mergeQuotes(new Map([[older.isin, older]]), quotes);
  assert.equal(map.get('DE0007164600')!.price, 230.5);
  assert.deepEqual(quotesFromDelivery({ ...delivery(), schema: 'anders' }), []);
});

test('Zeitangaben getrennt; „aktuell“ wird bei jeder Anzeige neu gerechnet – ein gespeicherter Kurs ist nach dem Neuladen nicht mehr aktuell', () => {
  const quote = quotesFromDelivery(delivery())[0] as LiveQuote;
  const fresh = quoteStatus(quote, at('2026-11-03T10:01:00Z'));
  assert.equal(fresh.state, 'aktuell');
  assert.match(fresh.quoteText, /^Kurszeit 10:45 Uhr \(Handelstag 03\.11\.2026\)$/);
  assert.match(fresh.fetchText, /^abgerufen 11:00 Uhr \(vor 1 Min\.\)$/);
  assert.equal(fresh.delayText, '15 Min. verzögert laut Yahoo-Antwort');
  // dieselbe gespeicherte Lieferung zwei Stunden später geöffnet
  const later = quoteStatus(quote, at('2026-11-03T12:00:00Z'));
  assert.equal(later.state, 'nicht_aktuell');
  assert.match(later.badge, /^nicht aktuell \(Kurs 2,3 Std\. alt\)$/);
  // Abruf zu lange her, auch wenn der Kurs selbst noch im Rahmen der Verzögerung läge (SIX: 30 Minuten)
  const six = { ...quote, delayMin: 30, quoteTime: at('2026-11-03T10:00:00Z'), fetchedAt: at('2026-11-03T10:00:00Z') };
  assert.equal(quoteStatus(six, at('2026-11-03T10:35:00Z')).state, 'nicht_aktuell');
  // Börse geschlossen: nie „aktuell“
  const closed = quoteStatus({ ...quote, marketState: 'CLOSED' }, at('2026-11-03T10:01:00Z'));
  assert.deepEqual([closed.state, closed.badge], ['boerse_zu', 'Börse geschlossen – letzter Kurs']);
});

test('Bekannte Verzögerungen laut Yahoo-Hilfe je Symbol-Endung', () => {
  assert.equal(knownDelay('SAP.DE'), 15);
  assert.equal(knownDelay('AZN.L'), 20);
  assert.equal(knownDelay('SHOP.TO'), 0);
  assert.equal(knownDelay('AAPL'), null);
  assert.equal(knownDelay(null), null);
});

test('Verschlüsselung wie auf dem Server (TRA1): an den Pfad gebunden', async () => {
  const key = await deriveKey('Testpassphrase-nur-fuer-Tests', { enabled: true, salt_b64: Buffer.from('0123456789abcdef').toString('base64'), iterations: 1000 } as never);
  const blob = await encodeJson({ a: 1, text: 'Ä' }, key, 'anfrage/k1');
  assert.deepEqual([...blob.subarray(0, 5)], [0x54, 0x52, 0x41, 0x31, 0x03]);
  assert.deepEqual(await decodeJson(blob, key, 'anfrage/k1'), { a: 1, text: 'Ä' });
  await assert.rejects(decodeJson(blob, key, 'anfrage/k2'));
  assert.equal(bytesToBase64(new Uint8Array([0, 255, 1])), 'AP8B');
});
