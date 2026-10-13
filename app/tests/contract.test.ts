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
import { listEntries } from '../src/lib/turnover.ts';
import { rankSubgroup } from '../src/lib/subgroup.ts';
import { allocationAfter, allocationNow, candidates, changes, compareRows, holdings, parseChoice, rebalanceDays, variantKey } from '../src/lib/rotation.ts';
import type { CryptoDescriptor, FrequencyData, Instruments, Manifest, Overview, Policy, RotationIndex, RotationVariant, Status, WindowData } from '../src/lib/types.ts';

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
  // Umschichtungs-Regel: ebenfalls verschlüsselt, an den eigenen Pfad gebunden
  await assert.rejects(load<RotationIndex>(ENC!, id, 'rotation/index.bin', null), NeedKeyError);
  const index = await load<RotationIndex>(ENC!, id, 'rotation/index.bin', key);
  assert.equal(index.snapshot_id, id);
  const variantFile = readFileSync(join(ENC!, 'snapshots', id, 'rotation', `${index.standard}.bin`));
  await assert.rejects(decodeJson(variantFile, key, `snapshots/${id}/rotation/index.bin`), /Entschlüsselung fehlgeschlagen/);
});

test('Umschichtungs-Regel: Dateien passen zur App, Standardvariante aus leerer Adresse, Orders und Aufteilung stimmig', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  assert.ok(snap.manifest.rotation, 'Regel im DEMO-Stand vorhanden');
  const index = await load<RotationIndex>(DATA!, snap.id, 'rotation/index.bin');
  assert.equal(index.snapshot_id, snap.id);
  assert.equal(variantKey(parseChoice(new URLSearchParams(''), index)), index.standard);
  const rule = index.regel;
  assert.equal(index.varianten.length, rule.aktien.length * rule.rhythmus.length * rule.trend_wochen.length * rule.kapital.length);
  for (const capital of rule.kapital) assert.equal(compareRows(index, capital).length, rule.aktien.length * rule.rhythmus.length * rule.trend_wochen.length);
  let decidedSeen = false;
  for (const info of index.varianten) {
    const variant = await load<RotationVariant>(DATA!, snap.id, `rotation/${info.key}.bin`);
    assert.equal(variant.key, info.key);
    const days = rebalanceDays(variant);
    assert.equal(days.reduce((n, d) => n + d.orders.length, 0), info.kennzahlen.orders);
    for (const d of days) {
      assert.ok(variant.umschichtungen.includes(d.day));
      for (const o of d.orders) {
        assert.ok(o.execDay > d.day && o.execDay <= d.day + 7, 'Ausführung am nächsten Handelstag');
        assert.ok(snap.instruments.isin[o.idx], 'Instrument im Datenstand');
      }
    }
    const preview = variant.vorschlag!;
    const n = info.aktien;
    assert.ok(holdings(preview).length <= n);
    const sumNow = allocationNow(preview).reduce((a, slot) => a + slot.share, 0);
    assert.ok(Math.abs(sumNow - 1) < 1e-4, `Aufteilung heute ${info.key}: ${sumNow}`);
    const after = allocationAfter(preview, n);
    assert.ok(after.filter((slot) => slot.idx !== null).length <= n);
    assert.ok(Math.abs(after.reduce((a, slot) => a + slot.share, 0) - 1) < 1e-4);
    const list = changes(preview);
    const firstBuy = list.findIndex((c) => c.action === 'kauf' || c.action === 'aufstocken');
    if (firstBuy >= 0) assert.ok(list.slice(firstBuy).every((c) => c.action === 'kauf' || c.action === 'aufstocken'), 'Verkäufe vor Käufen');
    for (const c of list.filter((c) => c.action === 'kauf')) assert.ok((c.rank ?? 99) <= n);
    const ranked = candidates(preview);
    ranked.forEach((c, k) => assert.equal(c.rank, k + 1));
    if (preview.beschlossen_am !== null) {
      decidedSeen = true;
      assert.ok(variant.umschichtungen.every((d) => d < preview.beschlossen_am!), 'beschlossene Umschichtung ist noch nicht im Rückblick ausgeführt');
    }
  }
  assert.ok(decidedSeen, 'DEMO enthält eine beschlossene, noch nicht ausgeführte Umschichtung (wöchentlich)');
});

test('Zwei Rendite-Ranglisten: Ranking 2 = Ranking 1 ohne nicht aufgenommene Aktien, gleiche Renditen und Kurse', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  const turnover = snap.instruments.turnover!;
  const threshold = snap.manifest.turnover!.schwelle_usd;
  assert.ok(turnover && turnover.status.length === snap.instruments.count);
  assert.ok(turnover.liquid.some(Boolean) && turnover.liquid.some((x) => !x), 'DEMO enthält Aktien mit und ohne Umsatzfilter');
  turnover.liquid.forEach((liquid, i) => assert.equal(liquid, turnover.status[i] === 'ok' && turnover.usd[i]! >= threshold));
  assert.equal(snap.overview.winners_l!.length, 90);
  let differentWinner = 0;
  snap.windows.forEach((win, k) => {
    const expected = win.orders.v0.filter((i) => turnover.liquid[i]);
    assert.deepEqual(win.orders.v0l, expected, `h=${k + 1}`);
    assert.equal(win.counts.L, expected.length);
    assert.equal(snap.overview.counts.L![k], expected.length);
    const pos = memberIndex(win);
    for (const e of listEntries(win, 'umsatz', 0, expected.length)) {
      const p = pos.get(e.idx)!;
      assert.ok(Object.is(e.r, win.m.r[p]));
      assert.ok(Math.abs(e.p1! / e.p0! - 1 - e.r) <= 1e-12 * Math.max(1, Math.abs(e.r)), 'Rendite = Endkurs / Startkurs − 1');
      assert.equal(e.end, win.cutoff_day);
    }
    const row = snap.overview.winners_l![k];
    if (expected.length) {
      assert.equal(row.entries[0].idx, expected[0]);
      const p = pos.get(expected[0])!;
      assert.ok(Object.is(row.entries[0].r, win.m.r[p]));
      assert.ok(Object.is(row.entries[0].p0, win.m.p0![p]));
      assert.ok(Object.is(row.entries[0].p1, win.m.p1![p]));
      if (row.entries[0].idx !== snap.overview.winners[k].entries[0]?.idx) differentWinner += 1;
    } else {
      assert.equal(row.entries.length, 0);
    }
  });
  assert.ok(differentWinner > 0, 'mindestens ein Zeitraum, in dem der Umsatzfilter den Sieger ändert');
  const check = snap.manifest.checks.find((c) => c.name === 'ranking2_teilmenge_gleiche_rendite');
  assert.ok(check && check.passed);
  assert.ok(snap.manifest.turnover!.wechselkurse.quelle, 'Wechselkursquelle dokumentiert');
  assert.ok(snap.manifest.turnover!.wechselkurse.letzter_kurstag, 'Datenzeit der Wechselkurse dokumentiert');
});

test('Häufigkeit mit Umsatzfilter zählt nur aufgenommene Aktien und nennt das Universum', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  const liquid = snap.instruments.turnover!.liquid;
  const membership = membershipCounts(snap.instruments, 1, 90);
  const result = aggregateFrequency(snap.frequency, snap.instruments, { policy: 'native', weights: [0], from: 1, to: 90, topK: 10, sort: 'occurrences', universe: 'umsatz' }, membership);
  assert.ok(result.entries.length > 0);
  for (const e of result.entries) {
    assert.ok(liquid[e.idx], 'nur Aktien mit Ø Umsatz ≥ Schwelle');
    assert.ok(e.n1 <= e.n3 && e.n3 <= e.n10 && e.n10 <= e.available && e.available <= result.validCells);
  }
  assert.ok(result.validCells <= 90);
  assert.ok(snap.frequency.universe?.v0l?.includes('Mio. USD'));
  assert.throws(() => aggregateFrequency(snap.frequency, snap.instruments, { policy: 'native', weights: [...WEIGHTS], from: 1, to: 90, topK: 10, sort: 'occurrences', universe: 'umsatz' }, membership));
});

test('Zweiter Börsenplatz: Kennzeichen genau bei auffälligen Vergleichen, nur erste Plätze geprüft', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  const venue = snap.instruments.venue!;
  const summary = snap.manifest.venue_check!;
  assert.ok(venue && summary, 'Abgleich im DEMO-Stand vorhanden');
  assert.equal(venue.idx.length, summary.anzahl.kandidaten);
  const checked = new Set(venue.idx);
  const top = new Set<number>();
  for (const win of snap.windows) {
    for (const i of win.orders.v0.slice(0, summary.plaetze)) top.add(i);
    for (const i of (win.orders.v0l ?? []).slice(0, summary.plaetze)) top.add(i);
  }
  assert.deepEqual([...top].sort((a, b) => a - b), [...checked].sort((a, b) => a - b), 'geprüft = erste Plätze beider Ranglisten');
  let flagged = 0;
  snap.windows.forEach((win, k) => {
    const xv = win.xv!;
    const pos = memberIndex(win);
    xv.idx.forEach((idx, j) => {
      assert.ok(checked.has(idx));
      const wf = win.m.wf[pos.get(idx)!];
      assert.equal(Boolean((wf >> 5) & 1), xv.status[j] === 'abweichung', `h=${k + 1}, idx=${idx}`);
      if (xv.status[j] === 'abweichung') flagged += 1;
      if (xv.r[j] !== null) assert.ok(xv.d0[j]! < xv.d1[j]! && xv.d1[j]! <= win.cutoff_day);
    });
    win.m.idx.forEach((idx, p) => {
      if (!checked.has(idx)) assert.equal((win.m.wf[p] >> 5) & 1, 0, 'nicht geprüfte Aktien ohne Kennzeichen');
    });
  });
  assert.equal(flagged, summary.anzahl.aktie_zeitraum.abweichung ?? 0);
  assert.ok(flagged > 0, 'DEMO enthält auffällige Vergleiche');
  const check = snap.manifest.checks.find((c) => c.name === 'boersenplatz_kennzeichen');
  assert.ok(check && check.passed);
});
