/* Datenvertrag App ↔ Server, gegen einen echt erzeugten DEMO-Snapshot.
 *
 * Wird von tests/integration/test_app_contract.py gestartet, das vorher mit der Python-Pipeline
 * einen unverschlüsselten und einen verschlüsselten DEMO-Stand erzeugt und die Erwartungswerte
 * des Python-Untergruppenrankings schreibt. Ohne diese Umgebungsvariablen werden die Tests
 * übersprungen.
 */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';
import { decodeJson, deriveKey, NeedKeyError, verifyKey } from '../src/lib/container.ts';
import { aggregateFrequency, membershipCounts, nK, type TopK } from '../src/lib/frequency.ts';
import { cohortFor, entryScores, memberIndex, orderFor, WEIGHTS } from '../src/lib/scoring.ts';
import { rankSubgroup } from '../src/lib/subgroup.ts';
import type { CryptoDescriptor, FrequencyData, Instruments, Manifest, Overview, Policy, Status, WindowData } from '../src/lib/types.ts';

const DATA = process.env.TR_FIXTURE_DIR;
const ENC = process.env.TR_FIXTURE_ENC_DIR;
const PASS = process.env.TR_FIXTURE_PASSPHRASE;
const SUBGROUP = process.env.TR_SUBGROUP_EXPECTED;

function plainJson<T>(dir: string, rel: string): T {
  return JSON.parse(readFileSync(join(dir, rel), 'utf8')) as T;
}

async function load<T>(dir: string, id: string, rel: string, key: CryptoKey | null = null): Promise<T> {
  return decodeJson<T>(readFileSync(join(dir, 'snapshots', id, rel)), key, `snapshots/${id}/${rel}`);
}

async function snapshot(dir: string) {
  const status = plainJson<Status>(dir, 'status.json');
  const id = status.latest_snapshot_id!;
  const [manifest, instruments, overview, frequency] = await Promise.all([
    load<Manifest>(dir, id, 'manifest.bin'),
    load<Instruments>(dir, id, 'instruments.bin'),
    load<Overview>(dir, id, 'overview.bin'),
    load<FrequencyData>(dir, id, 'frequency.bin'),
  ]);
  const windows: WindowData[] = [];
  for (let h = 1; h <= 90; h += 1) windows.push(await load<WindowData>(dir, id, `windows/${h}.full.bin`));
  return { id, status, manifest, instruments, overview, frequency, windows };
}

test('Datenvertrag: Scores der App sind bitgleich zur Serverberechnung', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  let compared = 0;
  for (const win of snap.windows) {
    const positions = memberIndex(win);
    const cohorts: [Policy, number][] = [['native', 0], ...WEIGHTS.map((w) => ['common_trend', w] as [Policy, number])];
    for (const [policy, weight] of cohorts) {
      const cohort = cohortFor(policy, weight);
      const occ = cohort === 'v0' ? snap.frequency.occ.v0 : snap.frequency.occ.u[String(weight)];
      const order = orderFor(win, policy, weight);
      for (let k = 0; k < occ.h.length; k += 1) {
        if (occ.h[k] !== win.h) continue;
        const idx = order[occ.rank[k] - 1];
        assert.equal(idx, occ.idx[k], `Reihenfolge h=${win.h} w=${weight} Platz ${occ.rank[k]}`);
        const score = entryScores(win, positions.get(idx)!, cohort, weight).score;
        assert.ok(Object.is(score, occ.score[k]), `Score h=${win.h} w=${weight} Platz ${occ.rank[k]}: ${score} ≠ ${occ.score[k]}`);
        compared += 1;
      }
      const row = (cohort === 'v0' ? snap.overview.v0 : snap.overview.u[String(weight)])[win.h - 1];
      if (row.idx !== undefined) {
        assert.equal(row.idx, order[0]);
        assert.ok(Object.is(entryScores(win, positions.get(row.idx)!, cohort, weight).score, row.score), `Spitzenreiter-Score h=${win.h} w=${weight}`);
      } else {
        assert.equal(order.length, 0);
      }
    }
  }
  assert.ok(compared > 1000, `zu wenige Vergleiche (${compared})`);
});

test('T94: Renditesieger hat genau 90 Zeilen = Platz 1 der nativen 0/100-Liste', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  assert.equal(snap.overview.winners.length, 90);
  snap.overview.winners.forEach((row, k) => {
    const win = snap.windows[k];
    assert.equal(row.h, k + 1);
    assert.equal(row.M, win.counts.V);
    if (win.counts.V === 0) {
      assert.equal(row.entries.length, 0);
      assert.ok(row.empty);
    } else {
      assert.equal(row.entries[0].idx, win.orders.v0[0]);
      const positions = memberIndex(win);
      assert.ok(Object.is(row.entries[0].r, win.m.r[positions.get(row.entries[0].idx)!]));
    }
  });
  const best = snap.overview.overall_max.entries[0];
  let max = -Infinity;
  for (const win of snap.windows) for (const r of win.m.r) max = Math.max(max, r);
  assert.ok(Object.is(best.r, max), 'T95: Gesamtmaximum über alle Paare');
});

test('T92/T93: Häufigkeitszählung der App stimmt mit der Serverreferenz überein', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  const membership = membershipCounts(snap.instruments, 1, 90);
  const result = aggregateFrequency(snap.frequency, snap.instruments, { policy: 'native', weights: [...WEIGHTS], from: 1, to: 90, topK: 10, sort: 'occurrences' }, membership);
  const ref = snap.frequency.server_reference;
  assert.equal(result.validCells, ref.E);
  assert.equal(result.theoreticalCells, ref.cells);
  assert.ok(ref.entries.length > 0);
  ref.entries.forEach((e, k) => {
    const mine = result.entries[k];
    assert.deepEqual(
      [mine.idx, mine.n1, mine.n3, mine.n10, mine.available, mine.distinctWindows, mine.distinctWeights, mine.distinctEffective],
      [e.idx, e.n1, e.n3, e.n10, e.A, e.H, e.W, e.dew],
      `Eintrag ${k + 1}`,
    );
  });
});

test('T90: Invarianten der Häufigkeitszählung in allen Varianten', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  const ranges: [number, number][] = [
    [1, 90],
    [1, 14],
    [15, 45],
    [60, 90],
  ];
  for (const [from, to] of ranges) {
    const membership = membershipCounts(snap.instruments, from, to);
    for (const policy of ['native', 'common_trend'] as Policy[]) {
      for (const weights of [[...WEIGHTS], [0], [60], [100]]) {
        for (const topK of [1, 3, 10] as TopK[]) {
          for (const sort of ['occurrences', 'distinct_windows'] as const) {
            const r = aggregateFrequency(snap.frequency, snap.instruments, { policy, weights, from, to, topK, sort }, membership);
            assert.ok(r.validCells <= r.theoreticalCells && r.theoreticalCells <= 990);
            for (const e of r.entries) {
              assert.ok(e.n1 <= e.n3 && e.n3 <= e.n10 && e.n10 <= e.available && e.available <= r.validCells, `N1≤N3≤N10≤A≤E (${e.idx})`);
              assert.ok(e.distinctWindows <= to - from + 1 && e.distinctWeights <= weights.length);
              assert.ok(e.distinctEffective <= e.distinctWindows);
              assert.ok(nK(e, topK) > 0);
              const counted = e.occurrences.length;
              assert.equal(counted, nK(e, topK), 'T92: Fundstellen nachzählbar');
            }
            for (let k = 1; k < r.entries.length; k += 1) {
              const a = r.entries[k - 1];
              const b = r.entries[k];
              const key = (e: typeof a) =>
                sort === 'distinct_windows'
                  ? [e.distinctWindows, nK(e, topK), e.n1]
                  : weights.length === 1
                    ? topK === 10
                      ? [e.n10, e.n3, e.n1]
                      : topK === 3
                        ? [e.n3, e.n1, e.n10]
                        : [e.n1, e.n3, e.n10]
                    : topK === 10
                      ? [e.n10, e.distinctWindows, e.n3, e.n1]
                      : topK === 3
                        ? [e.n3, e.distinctWindows, e.n1, e.n10]
                        : [e.n1, e.distinctWindows, e.n3, e.n10];
              const ka = key(a);
              const kb = key(b);
              const cmp = ka.findIndex((v, i) => v !== kb[i]);
              if (cmp === -1) assert.ok(a.idx < b.idx, 'Gleichstand nach ISIN');
              else assert.ok(ka[cmp] > kb[cmp], 'T93: Sortierregel');
            }
          }
        }
      }
    }
  }
});

test('Untergruppenranking (Watchlist) entspricht traktien.rank_subgroup', { skip: !DATA || !SUBGROUP }, async () => {
  const snap = await snapshot(DATA!);
  const expected = JSON.parse(readFileSync(SUBGROUP!, 'utf8')) as { h: number; policy: Policy; weight: number; subset: number[]; order: number[]; scores: number[]; ties: number[] }[];
  assert.ok(expected.length > 10);
  for (const item of expected) {
    const result = rankSubgroup(snap.windows[item.h - 1], item.subset, item.policy, item.weight, 'Test');
    assert.deepEqual(
      result.entries.map((e) => e.idx),
      item.order,
      `Reihenfolge h=${item.h} ${item.policy} w=${item.weight}`,
    );
    result.entries.forEach((e, k) => assert.ok(Object.is(e.score, item.scores[k]), `Score h=${item.h} w=${item.weight} Platz ${k + 1}: ${e.score} ≠ ${item.scores[k]}`));
    assert.deepEqual(
      result.entries.flatMap((e, k) => (e.tie ? [k] : [])),
      item.ties,
    );
  }
});

test('Verschlüsselter Stand: richtige Passphrase entschlüsselt, falsche und vertauschte Dateien scheitern', { skip: !ENC || !PASS }, async () => {
  const descriptor = plainJson<CryptoDescriptor>(ENC!, 'crypto.json');
  assert.equal(descriptor.enabled, true);
  assert.ok((descriptor.iterations ?? 0) >= 600_000);
  const status = plainJson<Status>(ENC!, 'status.json');
  const id = status.latest_snapshot_id!;
  await assert.rejects(load<Manifest>(ENC!, id, 'manifest.bin', null), NeedKeyError);
  const wrong = await deriveKey(`${PASS}x`, descriptor);
  await assert.rejects(verifyKey(wrong, descriptor));
  const key = await deriveKey(PASS!, descriptor);
  await verifyKey(key, descriptor);
  const manifest = await load<Manifest>(ENC!, id, 'manifest.bin', key);
  assert.equal(manifest.snapshot_id, id);
  const swapped = readFileSync(join(ENC!, 'snapshots', id, 'windows', '1.bin'));
  await assert.rejects(decodeJson(swapped, key, `snapshots/${id}/windows/2.bin`), /Entschlüsselung fehlgeschlagen/);
});
