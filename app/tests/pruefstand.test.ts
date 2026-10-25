/* Unabhängige Kursprüfung (ab 1.19.0) – Hinweise je Rangliste nur für den geprüften Stand. Aufruf: npm test */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { PRICE_CHECK, REASON_TEXT, rankingKey, rankingNotes, sourceDependent } from '../src/lib/pruefstand.ts';

test('Hinweise nur für den geprüften Stand und genau die betroffenen Ranglisten', () => {
  assert.deepEqual(rankingNotes(PRICE_CHECK.stand, 45, 'a', 80), ['nocp']);
  assert.deepEqual(rankingNotes(PRICE_CHECK.stand, 33, 'a', 10), ['nocp', 'gpw'], 'eine Rangliste kann mehrere Gründe haben');
  assert.deepEqual(rankingNotes(PRICE_CHECK.stand, 58, 'a', 10), ['ungeprueft']);
  assert.deepEqual(rankingNotes(PRICE_CHECK.stand, 30, 'a', 60), [], 'ohne Befund kein Hinweis');
  assert.deepEqual(rankingNotes('2026-10-26_abcdef12', 45, 'a', 80), [], 'anderer Stand: nicht geprüft, kein Hinweis');
  assert.deepEqual(rankingNotes(null, 45, 'a', 80), []);
  assert.equal(rankingKey(58, 'b', 90), '58/B/90');
});

test('Zählwerte passen zueinander', () => {
  const lists = PRICE_CHECK.ranglisten_je_grund;
  assert.equal(PRICE_CHECK.platz1_abgesichert + lists.ungeprueft.length, PRICE_CHECK.ranglisten, 'abgesichert + ungeprüft = alle Ranglisten');
  assert.equal(sourceDependent(['nocp', 'gpw']), 13, 'drei Ranglisten stehen bei beiden Gründen');
  for (const [reason, keys] of Object.entries(lists)) {
    assert.equal(new Set(keys).size, keys.length, `${reason}: keine Doppelten`);
    for (const key of keys) assert.match(key, /^\d{1,2}\/[AB]\/(0|10|20|30|40|50|60|70|80|90|100)$/);
    assert.ok(REASON_TEXT[reason as keyof typeof REASON_TEXT].length > 40);
  }
  assert.ok(PRICE_CHECK.belegt + PRICE_CHECK.plausibel <= PRICE_CHECK.abweichend);
});
