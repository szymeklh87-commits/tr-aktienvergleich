/* „Jetzt aktualisieren“ (ab 1.21): Anfragen, Fortschritt, Automatik, Zeitangaben der Kurse – ohne Browser. Aufruf: npm test */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { autoDue, marketMaybeOpen, newKennung, progress, requestPayload, stepLabel, valuesFor, type AutoInput, type UpdateJob } from '../src/lib/aktualisierung.ts';
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
    kennung: 'k1', scope: 'merkliste', label: 'Merkliste', isins: [], automatic: false, requestedAt: at('2026-10-31T12:00:00Z'), dispatchedAt: null, runId: null, runUrl: null,
    runStartedAt: null, phase: 'wartet', stepName: null, stepIndex: 0, stepCount: 0, partsReceived: 0, partsTotal: null, quotesReceived: 0, missing: 0, finishedAt: null, error: null, ...over,
  };
}

test('Fortschritt: jede Phase mit Text, Anteil und Ende', () => {
  const now = at('2026-10-31T12:00:12Z');
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

function auto(over: Partial<AutoInput> = {}): AutoInput {
  const now = at('2026-11-03T10:00:00Z');
  return { now, settings: { minutes: 15 }, visible: true, lastInteraction: now - 60_000, lastAutomatic: null, automaticTimes: [], running: false, failuresInRow: 0, marketOpen: true, hasAccess: true, count: 5, ...over };
}

test('Automatik: nur mit Zugang, sichtbar, bei Nutzung, während des Handels, mit Abstand und Obergrenze', () => {
  assert.deepEqual(autoDue(auto()), { due: true });
  const now = auto().now;
  const reasons: [Partial<AutoInput>, string][] = [
    [{ hasAccess: false }, 'kein Zugang eingerichtet'],
    [{ settings: { minutes: 0 } }, 'ausgeschaltet'],
    [{ visible: false }, 'App im Hintergrund'],
    [{ lastInteraction: now - 11 * 60_000 }, 'seit 10 Minuten nicht benutzt'],
    [{ running: true }, 'Aktualisierung läuft schon'],
    [{ failuresInRow: 3 }, 'drei Fehler nacheinander – pausiert bis zum nächsten Tippen'],
    [{ count: 0 }, 'keine Aktien sichtbar'],
    [{ marketOpen: false }, 'Börsen geschlossen'],
    [{ lastAutomatic: now - 5 * 60_000 }, 'noch nicht fällig'],
    [{ automaticTimes: [1, 2, 3, 4, 5, 6].map((k) => now - k * 60_000), lastAutomatic: now - 16 * 60_000 }, 'Obergrenze je Stunde erreicht'],
  ];
  for (const [change, reason] of reasons) assert.deepEqual(autoDue(auto(change)), { due: false, reason }, reason);
});

test('Handelszeiten ungefähr: Xetra werktags 9–17:30, Wochenende geschlossen, USA am Nachmittag', () => {
  assert.equal(marketMaybeOpen('XETR', at('2026-11-03T09:00:00Z')), true); // Di 10:00 Berlin
  assert.equal(marketMaybeOpen('XETR', at('2026-11-03T19:00:00Z')), false); // Di 20:00
  assert.equal(marketMaybeOpen('XETR', at('2026-10-31T10:00:00Z')), false); // Samstag
  assert.equal(marketMaybeOpen('XNYS', at('2026-11-03T15:00:00Z')), true); // 10:00 New York
  assert.equal(marketMaybeOpen('XNYS', at('2026-11-03T13:00:00Z')), false); // 08:00 New York
  assert.equal(marketMaybeOpen(null, at('2026-11-03T12:00:00Z')), true);
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
