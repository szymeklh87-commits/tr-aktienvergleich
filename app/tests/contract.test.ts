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
import { cohortFor, entryScores, exactScoreKey, FIXED_WINDOWS, memberIndex, orderFor, pctFromDoubled, weightedScore, WEIGHTS } from '../src/lib/scoring.ts';
import { listEntries, quietList, type ReturnList } from '../src/lib/turnover.ts';
import { rankSubgroup } from '../src/lib/subgroup.ts';
import { allocationAfter, allocationNow, candidates, changes, compareRows, holdings, parseChoice, rebalanceDays, variantKey } from '../src/lib/rotation.ts';
import { cohortKey, groupFrequency, hasGroups, markers, matrixRows, sameSetRep, tenWindowCounts, tenWindowRows } from '../src/lib/groups.ts';
import type { CryptoDescriptor, FrequencyData, FxData, Group, Instruments, Manifest, Overview, Policy, RotationIndex, RotationVariant, SeriesData, Status, WindowData, WindowMembers, WinnerRow } from '../src/lib/types.ts';
import { computeDepot, fxLookup, reportDepots, topLists } from '../src/lib/depots.ts';

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

test('Gruppe B: Scores der App bitgleich zum Server, Häufigkeit A und B wie Serverreferenz, Matrix wie Ranglisten', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  assert.ok(hasGroups(snap.overview), 'Gruppe B im DEMO-Stand vorhanden');
  let compared = 0;
  for (const win of snap.windows) {
    const positions = memberIndex(win);
    for (const weight of WEIGHTS) {
      const occ = weight === 0 ? snap.frequency.occ.v0l! : snap.frequency.occ.ul![String(weight)];
      const cohort = weight === 0 ? 'v0l' : 'ul';
      const order = weight === 0 ? win.orders.v0l! : win.orders.ul![String(weight)];
      for (let k = 0; k < occ.h.length; k += 1) {
        if (occ.h[k] !== win.h) continue;
        assert.equal(order[occ.rank[k] - 1], occ.idx[k], `Reihenfolge B h=${win.h} w=${weight}`);
        const score = entryScores(win, positions.get(occ.idx[k])!, cohort, weight).score;
        assert.ok(Object.is(score, occ.score[k]), `Score B h=${win.h} w=${weight} Platz ${occ.rank[k]}: ${score} ≠ ${occ.score[k]}`);
        compared += 1;
      }
      const row = weight === 0 ? snap.overview.v0l![win.h - 1] : snap.overview.ul![String(weight)][win.h - 1];
      if (order.length) {
        assert.equal(row.idx, order[0]);
        assert.ok(Object.is(entryScores(win, positions.get(order[0])!, cohort, weight).score, row.score), `Spitzenreiter-Score B h=${win.h} w=${weight}`);
      } else {
        assert.equal(row.idx, undefined);
      }
    }
  }
  assert.ok(compared > 500, `zu wenige Vergleiche (${compared})`);
  // Zählung der App = Serverreferenz (natives Feld, alle Gewichtungen, 1–90 Tage) für beide Gruppen
  for (const [group, reference] of [['a', snap.frequency.server_reference], ['b', snap.frequency.server_reference_b!]] as const) {
    const result = groupFrequency(snap.frequency, snap.instruments, { groups: group, weights: [...WEIGHTS], from: 1, to: 90, dedupe: false });
    const byIdx = new Map(result.entries.map((e) => [e.idx, e[group]]));
    assert.equal(group === 'a' ? result.validA : result.validB, reference.E);
    for (const ref of reference.entries) {
      const mine = byIdx.get(ref.idx);
      assert.ok(mine, `Aktie ${ref.idx} fehlt in Gruppe ${group}`);
      assert.deepEqual([mine!.n1, mine!.n3, mine!.n10, mine!.available], [ref.n1, ref.n3, ref.n10, ref.A], `Gruppe ${group}, Aktie ${ref.idx}`);
    }
  }
  // Matrix 1–30: Zellen = Platz 1 der Ranglisten, Kennzeichnung über beide Gruppen
  const rows = matrixRows(snap.overview, 'b', 1, 30);
  const marks = markers(snap.overview, snap.instruments, 1, 30);
  for (const row of rows) {
    for (const cell of row.cells) {
      if (cell.row.idx === undefined) continue;
      assert.ok(snap.instruments.turnover!.liquid[cell.row.idx], 'Gruppe B nur Aktien aus L');
      assert.ok(marks.get(cell.row.idx)!.countB >= 1);
    }
  }
  // Identische Kursfenster: gleiche Spitzenaktie mit gleichem Start in derselben Spalte
  const a = matrixRows(snap.overview, 'a', 1, 30);
  const marked = a.flatMap((row) => row.cells).filter((cell) => cell.same.length);
  // Ab tr-methode-1.9.0 enden Aktien ohne Kurs am Stichtag (DEMO: eine Börse mit Feiertag am Montag) an ihrem letzten
  // Schlusskurs – ihre Startdaten unterscheiden sich dann je Zeitraum, identische Kursfenster sind selten
  if (!snap.manifest.letzter_schlusskurs?.aktien) assert.ok(marked.length > 0, 'DEMO-Stichtag Montag: 1–3 Tage beginnen am Freitag');
  for (const cell of marked) {
    for (const other of cell.same) {
      const twin = a[other - 1].cells.find((c) => c.weight === cell.weight)!;
      assert.equal(twin.row.idx, cell.row.idx);
      assert.equal(twin.row.start, cell.row.start);
    }
  }
});

/** Rangliste einer Gruppe und Gewichtung aus der vollständigen Fensterdatei. */
function fullOrder(win: WindowData, group: Group, weight: number): number[] {
  if (group === 'a') return weight === 0 ? win.orders.v0 : win.orders.u[String(weight)];
  return weight === 0 ? win.orders.v0l! : win.orders.ul![String(weight)];
}

test('Prüfung 20: „Sieger nach Zeitraum“ = Platz 1 der vollständigen Ranglisten (alle Gewichtungen, A und B), eigene Zählung', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  assert.deepEqual([...FIXED_WINDOWS], [7, 14, 21, 30, 40, 50, 60, 70, 80, 90]);
  assert.ok(hasGroups(snap.overview));
  let compared = 0;
  let empty = 0;
  for (const weight of WEIGHTS) {
    const rows = tenWindowRows(snap.overview, weight);
    assert.deepEqual(
      rows.map((row) => row.h),
      [...FIXED_WINDOWS],
      'genau die zehn festen Zeiträume in fester Reihenfolge',
    );
    for (const row of rows) {
      const win = snap.windows[row.h - 1];
      assert.equal(win.h, row.h, '„30 Tage“ = Fensterdatei 30');
      const positions = memberIndex(win);
      for (const group of ['a', 'b'] as Group[]) {
        const cell = group === 'a' ? row.a : row.b;
        assert.ok(cell, `Gruppe ${group} vorhanden`);
        const order = fullOrder(win, group, weight);
        assert.equal(cell!.M, order.length, `Größe der Rangliste ${group} h=${row.h} w=${weight}`);
        if (!order.length) {
          assert.equal(cell!.idx, undefined);
          empty += 1;
          continue;
        }
        const p = positions.get(order[0])!;
        assert.equal(cell!.idx, order[0], `Platz 1 ${group} h=${row.h} w=${weight}`);
        assert.ok(Object.is(entryScores(win, p, cohortKey(group, weight), weight).score, cell!.score), `Rangscore ${group} h=${row.h} w=${weight}`);
        assert.ok(Object.is(cell!.r, win.m.r[p]), 'Kursrendite');
        assert.equal(cell!.start, win.m.start[p], 'tatsächlicher Anfang');
        assert.equal(cell!.n, win.m.n[p], 'Zahl der Schlusskurse');
        compared += 1;
      }
    }
    // eigene Zählung nur über diese zehn Zeiträume (nicht mit der Zählung über 1–90 Tage vermischt)
    const manual = new Map<number, { a: number; b: number }>();
    for (const row of rows) {
      for (const [group, cell] of [['a', row.a], ['b', row.b]] as const) {
        if (!cell || cell.idx === undefined) continue;
        const entry = manual.get(cell.idx) ?? { a: 0, b: 0 };
        entry[group] += 1;
        manual.set(cell.idx, entry);
      }
    }
    const counts = tenWindowCounts(rows, snap.instruments);
    assert.equal(counts.length, [...manual.values()].filter((e) => e.a + e.b >= 2).length);
    for (const c of counts) {
      assert.deepEqual([c.a, c.b], [manual.get(c.idx)!.a, manual.get(c.idx)!.b], `Zählung Aktie ${c.idx} w=${weight}`);
      assert.ok(c.a <= 10 && c.b <= 10);
      assert.ok(c.windows.every((h) => (FIXED_WINDOWS as readonly number[]).includes(h)));
    }
  }
  assert.ok(compared >= 150, `zu wenige Vergleiche (${compared}, leer ${empty})`);
});

test('1.14: „Auffällige ausblenden“ – Filter der App ergibt dieselben Spitzenreiter wie winners_klar des Servers, Plätze wie vollständig', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  const ov = snap.overview;
  assert.ok(ov.winners_klar && ov.winners_l_klar, 'Stand enthält die Spitzenreiter ohne Auffällige');
  assert.equal(ov.klar_regel?.umsatz_unter_usd, snap.manifest.turnover!.sehr_niedrig_usd, 'gleiche Umsatzgrenze wie „sehr niedrig“');
  assert.equal(ov.klar_regel?.einzelsprung_bit, 0, 'Bit 0 der Fensterhinweise');
  let compared = 0;
  let hidden = 0;
  let behind = 0;
  for (const win of snap.windows) {
    const lists: [ReturnList, WinnerRow[]][] = [
      ['alle', ov.winners_klar!],
      ['umsatz', ov.winners_l_klar!],
    ];
    for (const [list, rows] of lists) {
      const row: WinnerRow = rows[win.h - 1];
      assert.equal(row.h, win.h);
      const full = listEntries(win, list, 0, list === 'alle' ? win.counts.V : win.counts.L ?? 0, snap.instruments.last_close_day);
      const quiet = quietList(win, list, snap.instruments, snap.manifest);
      hidden += full.length - quiet.length;
      assert.equal(row.M, quiet.length, `Zahl der Unauffälligen ${list} h=${win.h}`);
      if (!quiet.length) {
        assert.deepEqual(row.entries, []);
        assert.ok(row.empty === 'nur_auffaellige' || row.empty === 'keine_vergleichbare_aktie', `Grund ${row.empty}`);
        continue;
      }
      assert.equal(row.entries[0].idx, quiet[0].idx, `Spitzenreiter ohne Auffällige ${list} h=${win.h}`);
      assert.equal(row.rank, quiet[0].rank, `Platz in der vollständigen Rangliste ${list} h=${win.h}`);
      assert.ok(Object.is(row.entries[0].r, quiet[0].r), 'gleiche Kursrendite');
      assert.equal(row.entries[0].end, quiet[0].end, 'gleiches Ende (Stichtag oder letzter Schlusskurs)');
      assert.equal(row.entries.length, quiet.filter((e) => e.r === quiet[0].r).length, 'Gleichstand vollständig');
      if (row.rank! > 1) behind += 1;
      compared += 1;
    }
  }
  assert.ok(compared >= 120, `zu wenige Vergleiche (${compared})`);
  assert.ok(hidden > 0, 'DEMO enthält auffällige Aktien in den Ranglisten');
  console.log(`  Auffällige: ${compared} Spitzenreiter verglichen, ${behind} stehen hinter Auffälligen, ${hidden} Einträge ausgeblendet`);
});

test('frequency-v2: identische Kursfenster = gleicher Bestand aus ISIN und tatsächlichem Startdatum, gleiche Ranglisten', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  const sets = snap.frequency.same_set;
  assert.ok(sets && sets.v0l && sets.ul, 'same_set für V, U, V ∩ L und U ∩ L');
  assert.deepEqual(snap.overview.same_set, sets, 'Übersicht und Häufigkeit nutzen dieselbe Zuordnung');
  const member: Record<'v0' | 'u' | 'v0l' | 'ul', (m: WindowMembers, p: number) => boolean> = {
    v0: () => true,
    u: (m, p) => m.a_gu[p] !== null,
    v0l: (m, p) => m.a_rvl![p] !== null,
    ul: (m, p) => m.a_gul![p] !== null,
  };
  const weightsOf = { v0: [0], u: WEIGHTS.filter((w) => w > 0), v0l: [0], ul: WEIGHTS.filter((w) => w > 0) };
  const groupOf = { v0: 'a', u: 'a', v0l: 'b', ul: 'b' } as const;
  let identical = 0;
  for (const cohort of ['v0', 'u', 'v0l', 'ul'] as const) {
    const reps: number[] = sets![cohort]!;
    assert.equal(reps.length, 90);
    const first = new Map<string, number>();
    snap.windows.forEach((win, k) => {
      const h = k + 1;
      const parts: string[] = [];
      win.m.idx.forEach((idx, p) => {
        if (member[cohort](win.m, p)) parts.push(`${idx}@${win.m.start[p]}`);
      });
      const key = parts.join(',');
      let expected = h;
      if (parts.length) {
        expected = first.get(key) ?? h;
        if (!first.has(key)) first.set(key, h);
      }
      assert.equal(reps[k], expected, `${cohort} h=${h}`);
      for (const weight of weightsOf[cohort]) assert.equal(sameSetRep(snap.frequency, groupOf[cohort], weight, h), expected);
      if (expected !== h) {
        identical += 1;
        const rep = snap.windows[expected - 1];
        for (const weight of weightsOf[cohort]) {
          assert.deepEqual(fullOrder(win, groupOf[cohort], weight), fullOrder(rep, groupOf[cohort], weight), `gleiche Rangliste ${cohort} h=${h} wie h=${expected}, w=${weight}`);
        }
      }
    });
  }
  if (!snap.manifest.letzter_schlusskurs?.aktien) assert.ok(identical > 0, 'DEMO-Stichtag Montag: 1–3 Tage beginnen am Freitag');
  // „nur einmal zählen“: nie mehr Nennungen als ohne Zusammenfassung, Gesamtzahl = verschiedene Fenster
  for (const group of ['a', 'b'] as const) {
    const plain = groupFrequency(snap.frequency, snap.instruments, { groups: group, weights: [...WEIGHTS], from: 1, to: 90, dedupe: false });
    const once = groupFrequency(snap.frequency, snap.instruments, { groups: group, weights: [...WEIGHTS], from: 1, to: 90, dedupe: true });
    const plainBy = new Map(plain.entries.map((e) => [e.idx, e[group]]));
    for (const e of once.entries) {
      const c = e[group];
      const p = plainBy.get(e.idx)!;
      assert.ok(c.n1 <= p.n1 && c.n3 <= p.n3 && c.n10 <= p.n10 && c.available <= p.available, `einmal ≤ mehrfach (${group}, ${e.idx})`);
      assert.ok(c.n1 <= c.n3 && c.n3 <= c.n10 && c.n10 <= c.available);
    }
    let distinct = 0;
    for (const weight of WEIGHTS) {
      const reps = new Set<number>();
      for (let h = 1; h <= 90; h += 1) if (fullOrder(snap.windows[h - 1], group, weight).length) reps.add(sameSetRep(snap.frequency, group, weight, h));
      distinct += reps.size;
    }
    assert.equal(group === 'a' ? once.validA : once.validB, distinct, `verschiedene Kursfenster ${group}`);
    // ohne Aktien mit eigenem Endtag gibt es am DEMO-Montag immer gleiche Fenster (1–3 Tage); mit ihnen (ab 1.9.0) nicht zwingend
    if (snap.manifest.letzter_schlusskurs?.aktien) assert.ok((group === 'a' ? once.validA : once.validB) <= (group === 'a' ? plain.validA : plain.validB));
    else assert.ok((group === 'a' ? once.validA : once.validB) < (group === 'a' ? plain.validA : plain.validB));
  }
});

test('Methodenvergleich (tr-methode-1.9.0 → 1.10.0) im Manifest stimmt mit den Fenstern überein, positive Schlusskursvergleiche plausibel', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  const mc = snap.manifest.method_comparison;
  assert.ok(mc, 'Methodenvergleich vorhanden');
  assert.equal(mc!.jetzt, snap.manifest.versions.method);
  assert.equal(mc!.jetzt, 'tr-methode-1.10.0');
  assert.equal(mc!.vorher, 'tr-methode-1.9.0');
  assert.equal(snap.manifest.versions.ranking, 'ranking-11w-v3');
  assert.equal(mc!.ausgangsmodell, snap.manifest.versions.reference_model);
  assert.ok(mc!.regeln.length >= 1 && mc!.regeln.every((t) => t.length > 20), 'Änderungen benannt');
  const sumV = snap.windows.reduce((a, w) => a + w.counts.V, 0);
  const sumU = snap.windows.reduce((a, w) => a + w.counts.U, 0);
  assert.equal(mc!.paare.jetzt_V, sumV, 'V nach neuen Regeln = Summe der Fenster');
  assert.equal(mc!.paare.jetzt_U, sumU);
  assert.equal(mc!.paare.jetzt_V - mc!.paare.vorher_V, mc!.paare.neu_bewertet - mc!.paare.nicht_mehr_bewertet);
  // Gründe über Statusnummern: jede Veränderung genau einmal gezählt, nur bekannte Status
  const sum = (counts: Record<string, number> | undefined) => Object.values(counts ?? {}).reduce((a, b) => a + b, 0);
  assert.equal(sum(mc!.paare.weggefallen_nach_status), mc!.paare.nicht_mehr_bewertet);
  assert.equal(sum(mc!.paare.hinzugekommen_aus_status), mc!.paare.neu_bewertet);
  const publishable = new Set(snap.manifest.codes.return_publishable.map(String));
  for (const code of Object.keys(mc!.paare.weggefallen_nach_status ?? {})) assert.ok(snap.manifest.codes.status[code] && !publishable.has(code), `Status ${code}`);
  for (const code of Object.keys(mc!.paare.hinzugekommen_aus_status ?? {})) assert.ok(snap.manifest.codes.status[code] && !publishable.has(code), `Status ${code}`);
  assert.equal(mc!.paare.grund, undefined, 'Format von 1.7.0 nicht mehr verwendet');
  assert.ok(mc!.ranglisten.verglichen <= 2 * 90 * WEIGHTS.length && mc!.ranglisten.spitze_geaendert <= mc!.ranglisten.verglichen);
  assert.ok(mc!.ranglisten.beispiele.length <= 12);
  // 1.9.0 → 1.10.0: dieselben Zulassungsregeln – anders sein kann nur die Reihenfolge rechnerisch gleicher Scores.
  // Eigene Gegenrechnung in der App: die alte Regel (Gleitkomma-Score) auf den veröffentlichten Rängen nachbilden.
  assert.equal(mc!.paare.neu_bewertet, 0);
  assert.equal(mc!.paare.nicht_mehr_bewertet, 0);
  const own = { verglichen: 0, spitze_geaendert: 0, top10_andere_aktien: 0, top10_andere_reihenfolge: 0, reihenfolge_geaendert: 0 };
  for (const win of snap.windows) {
    const pos = memberIndex(win);
    const groups = [
      { v0: win.orders.v0, u: win.orders.u, g: win.m.a_gu, r: win.m.a_ru, size: win.counts.U },
      ...(win.orders.ul ? [{ v0: win.orders.v0l ?? [], u: win.orders.ul, g: win.m.a_gul!, r: win.m.a_rul!, size: win.counts.UL ?? 0 }] : []),
    ];
    for (const grp of groups) {
      if (grp.v0.length) own.verglichen += 1; // 0/100 auf V: unverändert
      for (const w of WEIGHTS.filter((x) => x > 0)) {
        const exact = grp.u[String(w)] ?? [];
        if (!exact.length) continue;
        own.verglichen += 1;
        if (w === 100) continue; // 100/0: unverändert
        const score = (i: number) => weightedScore(w, pctFromDoubled(grp.g[pos.get(i)!]!, grp.size), pctFromDoubled(grp.r[pos.get(i)!]!, grp.size));
        const ret = (i: number) => win.m.r[pos.get(i)!];
        const old = [...exact].sort((a, b) => score(b) - score(a) || (ret(b) > ret(a) ? 1 : ret(b) < ret(a) ? -1 : 0) || a - b);
        // die veröffentlichte Reihenfolge ist exakt sortiert: Schlüssel w·(dG − 2) + (100 − w)·(dR − 2) absteigend
        const key = (i: number) => exactScoreKey(w, grp.g[pos.get(i)!]!, grp.r[pos.get(i)!]!);
        exact.forEach((i, k) => k === 0 || assert.ok(key(exact[k - 1]) >= key(i), `exakt sortiert h=${win.h} w=${w}`));
        if (old[0] !== exact[0]) own.spitze_geaendert += 1;
        const a10 = old.slice(0, 10);
        const b10 = exact.slice(0, 10);
        if (new Set(a10).size !== new Set([...a10, ...b10]).size || a10.length !== b10.length) own.top10_andere_aktien += 1;
        else if (a10.some((x, k) => x !== b10[k])) own.top10_andere_reihenfolge += 1;
        if (old.some((x, k) => x !== exact[k])) own.reihenfolge_geaendert += 1;
      }
    }
  }
  assert.deepEqual(
    {
      verglichen: mc!.ranglisten.verglichen,
      spitze_geaendert: mc!.ranglisten.spitze_geaendert,
      top10_andere_aktien: mc!.ranglisten.top10_andere_aktien,
      top10_andere_reihenfolge: mc!.ranglisten.top10_andere_reihenfolge,
      reihenfolge_geaendert: mc!.ranglisten.reihenfolge_geaendert,
    },
    own,
  );
  let members = 0;
  for (const win of snap.windows) {
    const up = win.m.up!;
    assert.equal(up.length, win.m.idx.length, 'up für jedes Mitglied');
    up.forEach((u, p) => {
      const n = win.m.n[p];
      assert.ok(Number.isInteger(u) && u >= 0 && u <= n - 1, `0 ≤ up ≤ n−1 (h=${win.h})`);
      if (win.m.r[p] > 0) assert.ok(u >= 1, 'Kursanstieg ⇒ mindestens ein positiver Vergleich');
      if (win.m.r[p] < 0) assert.ok(u <= n - 2, 'Kursrückgang ⇒ mindestens ein nicht positiver Vergleich');
      members += 1;
    });
  }
  assert.ok(members > 1000);
});

test('1.9: Euro-Referenzkurse und Musterdepots – Aktienrendite = Fensterrendite der Ranglisten, USD-Aktien in USD unverändert', { skip: !DATA }, async () => {
  const snap = await snapshot(DATA!);
  assert.ok(snap.manifest.fx, 'Wechselkurse im Manifest genannt');
  const fx = await load<FxData>(DATA!, snap.id, 'fx.bin');
  assert.equal(fx.schema, 'tr-fx/1');
  assert.equal(fx.snapshot_id, snap.id);
  for (let k = 1; k < fx.tage.length; k += 1) assert.ok(fx.tage[k] > fx.tage[k - 1], 'Tage aufsteigend');
  assert.ok(fx.tage[fx.tage.length - 1] <= snap.manifest.cutoff_day, 'keine Kurse nach dem Stichtag');
  assert.ok(fx.tage[0] >= snap.manifest.cutoff_day - 100);
  for (const [currency, column] of Object.entries(fx.je_eur)) {
    assert.equal(column.length, fx.tage.length, currency);
    assert.ok(column.every((v) => v === null || v > 0), `${currency}: nur positive Kurse`);
  }
  assert.deepEqual(snap.manifest.fx!.waehrungen, [...new Set(['EUR', ...Object.keys(fx.je_eur)])].sort());

  const lists = topLists(snap.frequency, snap.instruments, 'bericht');
  assert.ok(lists.firsts.length > 0 && lists.tops.length > 0, 'Häufigkeitslisten im DEMO-Stand');
  const depots = reportDepots(lists);
  const isins = [...new Set(depots.flatMap((d) => d.isins))];
  const series = new Map<string, SeriesData>();
  for (const isin of isins) series.set(isin, await load<SeriesData>(DATA!, snap.id, `series/${isin}.bin`));
  const look = fxLookup(fx);
  let compared = 0;
  for (const h of [1, 7, 14, 30]) {
    const win = snap.windows[h - 1];
    const position = new Map(win.m.idx.map((idx, p) => [snap.instruments.isin[idx], p]));
    for (const depot of depots) {
      const local = computeDepot(depot.isins, series, snap.manifest.cutoff_day, h, 'lokal', null, 1000);
      const usd = computeDepot(depot.isins, series, snap.manifest.cutoff_day, h, 'usd', look, 1000);
      const sum = local.positions.reduce((acc, p) => acc + p.contribution, 0);
      if (local.ret !== null) assert.ok(Math.abs(sum - local.ret) < 1e-12, 'Summe der Beiträge = Depotrendite');
      for (const p of local.positions) {
        const s = series.get(p.isin)!;
        const at = position.get(p.isin);
        // Gleicher Starttag wie in der Rangliste ⇒ gleiche Kursrendite (Originalwährung)
        if (at !== undefined && s.window_start[h - 1] === p.startDay && win.m.start[at] === p.startDay) {
          assert.ok(Math.abs(p.ret - win.m.r[at]) <= 1e-9 * Math.max(1, Math.abs(win.m.r[at])), `${p.isin} h=${h}: ${p.ret} ≠ ${win.m.r[at]}`);
          compared += 1;
        }
        const inUsd = usd.positions.find((q) => q.isin === p.isin);
        if (inUsd && s.listing.currency === 'USD') assert.ok(Math.abs(inUsd.ret - p.ret) < 1e-12, 'USD-Aktie in USD ohne Umrechnung');
      }
    }
  }
  assert.ok(compared >= 10, `zu wenige Vergleiche (${compared})`);
});

/* ------------------------------------------------------------------ Spielgeld-Robo (Gesamtauftrag, Abschnitte 29, 31) */

test('Spielgeld-Stand: Format, Kennzeichnung, Regeltexte aus dem Katalog, keine echten Orders', { skip: !DATA }, async () => {
  const { regelZusammenfassung, gruppieren, benchmark } = await import('../src/lib/pilot.ts');
  type PilotStand = import('../src/lib/pilot.ts').PilotStand;
  const status = plainJson<Status>(DATA!, 'status.json');
  assert.ok(status.spielgeld, 'status.json nennt den Spielgeld-Stand');
  assert.deepEqual(Object.keys(status.spielgeld!).sort(), ['erstellt_utc', 'id', 'schema'], 'öffentlich nur Kennung, Zeit und Schema');
  const id = status.spielgeld!.id;
  const rel = `pilot/${id}/pilot.bin`;
  const stand = await decodeJson<PilotStand>(readFileSync(join(DATA!, rel)), null, rel);
  assert.equal(stand.schema, 'tr-spielgeld/1');
  assert.equal(stand.id, id);
  assert.equal(stand.modus, 'DEMO');
  assert.match(stand.hinweis, /Keine echten Orders/);
  assert.ok(stand.depots.length >= 10, 'Pilot-, Forschungs- und Vergleichsdepots');
  for (const d of stand.depots) {
    assert.ok(['PAPER', 'SIGNAL', 'DEMO'].includes(d.modus), `${d.id}: nur Spielgeld-Modi`);
    assert.ok(d.synthetisch, `${d.id}: DEMO ist synthetisch gekennzeichnet`);
  }
  const g = gruppieren(stand.depots);
  assert.ok(g.length >= 1 && g[0].pilot && benchmark(g[0]), 'Pilotdepot und Welt-ETF-Vergleich im Vorwärtstest');
  // Jede Regel: alle Kennzahlen im mitgelieferten Katalog, deutscher Text ohne Lücken
  const ids = new Set(stand.katalog!.kennzahlen.map((k) => k.id));
  const refs: string[] = [];
  const walk = (node: unknown) => {
    if (Array.isArray(node)) node.forEach(walk);
    else if (node && typeof node === 'object') {
      const o = node as Record<string, unknown>;
      if (o.kennzahl && typeof o.kennzahl === 'object' && typeof (o.kennzahl as { id?: unknown }).id === 'string') refs.push((o.kennzahl as { id: string }).id);
      Object.values(o).forEach(walk);
    }
  };
  const rules = [...Object.values(stand.regeln), ...Object.values(stand.vorlagen ?? {})];
  assert.ok(rules.length >= 8);
  for (const r of rules) {
    walk(r);
    const text = regelZusammenfassung(r, stand.katalog).map(([a, b]) => `${a}: ${b}`).join('\n');
    assert.doesNotMatch(text, /undefined|NaN|\[object Object\]/, `${r.id}: ${text}`);
    assert.match(text, /Stop: /, `${r.id}: Initialstop ist Pflicht`);
  }
  for (const ref of refs) assert.ok(ids.has(ref), `Kennzahl ${ref} fehlt im Katalog`);
});

test('Bericht je Depot (Abschnitte 14, 21, 22): jede Kennzahl als Wert oder mit Grund, Vergleiche, Exporte aus echten Laufdaten', { skip: !DATA }, async () => {
  const { KENNZAHL_ZEILEN, kennzahlWert, ausfuehrungenCsv, berichtHtml } = await import('../src/lib/pilotbericht.ts');
  type PilotStand = import('../src/lib/pilot.ts').PilotStand;
  const status = plainJson<Status>(DATA!, 'status.json');
  const rel = `pilot/${status.spielgeld!.id}/pilot.bin`;
  const stand = await decodeJson<PilotStand>(readFileSync(join(DATA!, rel)), null, rel);
  const hist = stand.depots.filter((d) => d.historisch);
  assert.ok(hist.length >= 10, 'historische Simulation im Stand');
  for (const d of stand.depots) {
    assert.ok(d.bericht, `${d.id}: Bericht vorhanden`);
    assert.ok(Array.isArray(d.ausfuehrungen), `${d.id}: Ausführungen vorhanden`);
  }
  for (const d of hist) {
    const b = d.bericht!;
    assert.equal(b.grund, undefined, `${d.id}: ${b.grund}`);
    assert.equal(b.zeitraum!.renditetage, 24);
    for (const z of KENNZAHL_ZEILEN) {
      assert.ok(z.key in b.kennzahlen!, `${d.id}: Kennzahl ${z.key} fehlt`);
      const w = kennzahlWert(b, z);
      if (w.text === 'nicht definiert') assert.ok(w.grund, `${d.id}: ${z.key} ohne Grund`);
      else assert.doesNotMatch(w.text, /NaN|undefined|Infinity/);
    }
    assert.equal(b.kennzahlen!.rendite_pct, d.kennzahlen.rendite_zeitgewichtet_pct, `${d.id}: eine Rendite für Übersicht und Bericht`);
    for (const a of d.ausfuehrungen!) {
      if (a.art === 'verkauf') assert.ok(Math.abs((a.lose ?? []).reduce((s, l) => s + (l.stueck ?? 0), 0) - (a.stueck ?? 0)) < 1e-6, `${d.id}: FIFO-Lose decken den Verkauf`);
    }
    const csv = ausfuehrungenCsv(d, stand);
    assert.doesNotMatch(csv, /undefined|NaN/);
    assert.equal(csv.trim().split('\r\n').length, 5 + d.ausfuehrungen!.length, `${d.id}: Kopf, Metadaten und eine Zeile je Ausführung`);
    const html = berichtHtml(d, stand);
    assert.doesNotMatch(html, /undefined|NaN|<script/i);
  }
  const pilot = hist.find((d) => d.art === 'pilot')!;
  const ref = pilot.bericht!.vergleiche!.map((v) => v.depot.replace(/-\d{3}$/, '')).sort();
  assert.deepEqual(ref, ['h-v-kern', 'h-v-welt']);
  assert.ok(pilot.bericht!.vergleiche!.every((v) => typeof v.abstand_pp === 'number'));
});

test('„Als Robo-Regel verwenden“ aus Rangliste, Renditeliste, Häufigkeiten und Merkliste: gültige Regeln mit den Einstellungen der Ansicht', { skip: !DATA }, async () => {
  const { regelAusAnalyse, linkRangliste, linkHaeufigkeit, linkListe } = await import('../src/lib/analyseregel.ts');
  const { regelPruefen } = await import('../src/lib/regelpruefung.ts');
  type PilotStand = import('../src/lib/pilot.ts').PilotStand;
  const status = plainJson<Status>(DATA!, 'status.json');
  const rel = `pilot/${status.spielgeld!.id}/pilot.bin`;
  const stand = await decodeJson<PilotStand>(readFileSync(join(DATA!, rel)), null, rel);
  const params = (hash: string) => new URLSearchParams(hash.split('?')[1] ?? '');
  const isins = stand.depots.flatMap((d) => (d.ausfuehrungen ?? []).map((a) => a.isin)).filter((x, i, a) => a.indexOf(x) === i).slice(0, 12);
  const faelle = [
    linkRangliste({ h: 30, w: 60, gruppe: 'A', politik: 'native', platz: 10 }),
    linkRangliste({ h: 7, w: 0, gruppe: 'B', politik: 'native', platz: 50 }),
    linkRangliste({ h: 90, w: 100, gruppe: 'A', politik: 'common_trend', platz: 3 }),
    linkHaeufigkeit({ von: 1, bis: 30, gewichte: [0, 40, 50, 60], k: 10, gruppe: 'A', politik: 'native' }),
    linkHaeufigkeit({ von: 5, bis: 90, gewichte: [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100], k: 1, gruppe: 'B', politik: 'common_trend', mindestens: 2 }),
    linkListe({ isins, bezeichnung: 'Merkliste' }),
  ];
  for (const link of faelle) {
    const r = regelAusAnalyse(stand, params(link));
    assert.ok(r, link);
    assert.deepEqual(regelPruefen(r!, stand.katalog!), [], `${link}: ${r!.name}`);
    assert.ok(r!.auswahl.anzahl <= 8, 'höchstens acht Einzelaktien');
    assert.ok(r!.stop.initial, 'Initialstop aus der Vorlage');
  }
  const r = regelAusAnalyse(stand, params(faelle[0]))!;
  assert.deepEqual(r.kandidaten, [{ art: 'rangliste', gruppe: 'A', politik: 'native', gewichte: [60], fenster: { von: 30, bis: 30 }, platz_bis: 10 }]);
  assert.equal(r.name, 'Rangliste 30 Tage, 60/40, Gruppe A, Top 10');
  assert.equal(regelAusAnalyse(stand, new URLSearchParams('quelle=unbekannt')), null);
  assert.equal(regelAusAnalyse(stand, new URLSearchParams('quelle=isins&isins=kein-isin')), null);
});

test('Musterbereiche: Format des Stands passt zur App, jede Regel aus der Ansicht ist mit dem Katalog des Laufs gültig', { skip: !DATA }, async () => {
  const { regelAusAnalyse, linkMuster } = await import('../src/lib/analyseregel.ts');
  const { regelPruefen } = await import('../src/lib/regelpruefung.ts');
  const { AKTIV, ZUSTAENDE, regelText, auswahl } = await import('../src/lib/muster.ts');
  type MusterStand = import('../src/lib/muster.ts').MusterStand;
  type PilotStand = import('../src/lib/pilot.ts').PilotStand;
  const status = plainJson<Status>(DATA!, 'status.json');
  assert.ok(status.muster, 'status.json nennt den Musterstand');
  assert.deepEqual(Object.keys(status.muster!).sort(), ['erstellt_utc', 'id', 'schema'], 'öffentlich nur Kennung, Zeit und Schema');
  const rel = `muster/${status.muster!.id}/muster.bin`;
  const stand = await decodeJson<MusterStand>(readFileSync(join(DATA!, rel)), null, rel);
  assert.equal(stand.schema, 'tr-muster/1');
  assert.equal(stand.id, status.muster!.id);
  for (const m of ['A', 'B', 'C'] as const) {
    const mod = stand.module[m];
    assert.ok(mod.treffer.every((t) => ZUSTAENDE[m].includes(t.zustand)), `${m}: nur bekannte Zustände`);
    assert.ok(mod.top.every((isin) => mod.treffer.some((t) => t.isin === isin && AKTIV[m].includes(t.zustand))), `${m}: Top 10 aus den aktiven Treffern`);
    assert.deepEqual(auswahl(mod, m, 'aktiv', 'score').slice(0, mod.top.length).map((t) => t.isin), mod.top, `${m}: Reihenfolge wie im Lauf`);
    assert.doesNotMatch(regelText(stand, m).join(' '), /undefined|NaN/);
    for (const t of mod.treffer) assert.ok(stand.zustaende[t.zustand], `${t.zustand}: Text für den Zustand`);
  }
  const prel = `pilot/${status.spielgeld!.id}/pilot.bin`;
  const pilot = await decodeJson<PilotStand>(readFileSync(join(DATA!, prel)), null, prel);
  for (const m of ['A', 'B', 'C'] as const) {
    const r = regelAusAnalyse(pilot, new URLSearchParams(linkMuster({ modul: m, zustaende: AKTIV[m] }).split('?')[1]));
    assert.ok(r, m);
    assert.deepEqual(regelPruefen(r!, pilot.katalog!), [], `${m}: ${r!.name}`);
  }
});

test('Spielgeld-Stand verschlüsselt: richtige Passphrase entschlüsselt, vertauschter Pfad scheitert', { skip: !ENC || !PASS }, async () => {
  type PilotStand = import('../src/lib/pilot.ts').PilotStand;
  const status = plainJson<Status>(ENC!, 'status.json');
  const descriptor = plainJson<CryptoDescriptor>(ENC!, 'crypto.json');
  const key = await deriveKey(PASS!, descriptor);
  const id = status.spielgeld!.id;
  const rel = `pilot/${id}/pilot.bin`;
  const blob = readFileSync(join(ENC!, rel));
  const stand = await decodeJson<PilotStand>(blob, key, rel);
  assert.equal(stand.id, id);
  await assert.rejects(decodeJson(blob, key, `pilot/${id}/anders.bin`));
  await assert.rejects(decodeJson(blob, null, rel), NeedKeyError);
});

test('Regel-Baukasten: App-Prüfung akzeptiert alle Vorlagen und Regeln des Laufs und findet typische Fehler wie der Lauf', { skip: !DATA }, async () => {
  const { regelPruefen, ableiten, idAusName } = await import('../src/lib/regelpruefung.ts');
  type PilotStand = import('../src/lib/pilot.ts').PilotStand;
  const status = plainJson<Status>(DATA!, 'status.json');
  const rel = `pilot/${status.spielgeld!.id}/pilot.bin`;
  const stand = await decodeJson<PilotStand>(readFileSync(join(DATA!, rel)), null, rel);
  const katalog = stand.katalog!;
  for (const r of [...Object.values(stand.regeln), ...Object.values(stand.vorlagen ?? {})]) {
    assert.deepEqual(regelPruefen(r, katalog), [], `${r.id}@${r.version} gilt im Lauf und in der App`);
    const kopie = ableiten(r, 'kopie');
    assert.deepEqual(regelPruefen(kopie, katalog), [], `${kopie.id}: Kopie gültig`);
    assert.equal(kopie.version, 1);
    assert.match(kopie.id, /^r-[a-z0-9][a-z0-9-]{1,38}$/);
  }
  const basis = ableiten(stand.vorlagen!.platz1_leiter, 'kopie');
  const ohneStop = JSON.parse(JSON.stringify(basis));
  ohneStop.stop.initial = null;
  assert.ok(regelPruefen(ohneStop, katalog).some((f) => f.pfad === 'stop.initial' && /Initialstop ist Pflicht/.test(f.text)));
  const rueck = JSON.parse(JSON.stringify(basis));
  rueck.filter = { kennzahl: { id: 'spaeterer_sieger', parameter: {} }, op: 'ist_wahr' };
  assert.ok(regelPruefen(rueck, katalog).some((f) => /rückblickend/.test(f.text)), 'rückblickende Kennzahl gesperrt');
  const leiter = JSON.parse(JSON.stringify(basis));
  leiter.verkauf.gewinnmitnahme.stufen = [{ schwelle_pct: 50, anteil_pct: 60 }, { schwelle_pct: 30, anteil_pct: 60 }];
  const msgs = regelPruefen(leiter, katalog).map((f) => f.text);
  assert.ok(msgs.some((m) => /aufsteigend/.test(m)));
  assert.ok(msgs.some((m) => /über 100 %/.test(m)));
  const op = JSON.parse(JSON.stringify(basis));
  op.filter = { kennzahl: { id: 'rendite', parameter: { fenster: 30 } }, op: 'ist_wahr' };
  assert.ok(regelPruefen(op, katalog).some((f) => /passt nicht/.test(f.text)), 'Operator passt nicht zur Kennzahl');
  assert.equal(idAusName('Mein Größtes Momentum!'), 'r-mein-groesstes-momentum');
});

test('Einrichtung: Fragen und Tabelle kommen aus dem Lauf, Tabelle vollständig und monoton', { skip: !DATA }, async () => {
  type PilotStand = import('../src/lib/pilot.ts').PilotStand;
  const status = plainJson<Status>(DATA!, 'status.json');
  const rel = `pilot/${status.spielgeld!.id}/pilot.bin`;
  const stand = await decodeJson<PilotStand>(readFileSync(join(DATA!, rel)), null, rel);
  const e = stand.einrichtung!;
  assert.deepEqual(e.fragen.map((q) => q.id), ['horizont', 'liquiditaet', 'verlust', 'risiko', 'erfahrung']);
  assert.ok(e.fragen.every((q) => q.antworten.length === 5));
  assert.equal(e.tabelle.length, 21);
  for (let v = 0; v < 5; v += 1) {
    for (let p = 1; p <= 20; p += 1) assert.ok(e.tabelle[p][v] >= e.tabelle[p - 1][v], `monoton (Punkte ${p}, Spalte ${v})`);
  }
  assert.equal(e.tabelle[20][4], 1);
  assert.ok(e.aktiv_anteile.every((a) => a <= e.aktiver_anteil_max + 1e-9 || a > e.aktiver_anteil_max));
  assert.equal(e.aktuell, null, 'DEMO ohne Einrichtung: Vorgabewerte, nichts erfunden');
});
