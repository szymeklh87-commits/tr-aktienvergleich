/* Umschichtungs-Regel: Tagesvorschlag und Rückblick-Test (ab Version 1.3).
 *
 * Eine feste Rechenregel, keine Anlageberatung: Der Server hält gedanklich die N Aktien mit der
 * höchsten Kursrendite der letzten Wochen (nur ausreichend gehandelte Aktien) zu gleichen Teilen
 * und schichtet zu festen Terminen um. Die App zeigt, was diese Regel heute ändern würde und wie
 * sie sich im Rückblick nach Kosten und Steuern entwickelt hätte.
 */

import { useMemo, useState } from 'react';
import { CompareChart, type CompareLine } from '../components/charts';
import { Disclosure, EmptyState, ErrorNote, KeyValues, Loading, Notice, Pct, SectionTitle, Segmented } from '../components/ui';
import { Explain } from '../components/explain';
import * as f from '../lib/format';
import { useRotationIndex, useRotationVariant } from '../lib/hooks';
import { instName } from '../lib/instruments';
import { closeLabel } from '../lib/intraday';
import {
  actionLabel,
  actionPast,
  allocationAfter,
  allocationNow,
  candidates,
  changes,
  changesTitle,
  compareRows,
  curve,
  holdings,
  isSell,
  lookbackText,
  nextText,
  parseChoice,
  parseEuro,
  rebalanceDays,
  reasonText,
  rhythmLabel,
  rhythmText,
  scaled,
  spanMonths,
  targetShare,
  variantInfo,
  variantKey,
  type Slot,
  type VariantChoice,
} from '../lib/rotation';
import { buildHash, updateParams, type Route } from '../lib/router';
import type { Instruments, RotationIndex, RotationPreview, RotationStats, RotationVariant, RotationVariantInfo } from '../lib/types';
import { useApp } from '../state/AppState';

const DAYS_SHOWN = 6;

export function RotationView({ route }: { route: Route }) {
  const { manifest, instruments, switchSnapshot } = useApp();
  const index = useRotationIndex();
  const choice = index.data ? parseChoice(route.params, index.data) : null;
  const key = choice ? variantKey(choice) : null;
  const info = index.data && key ? variantInfo(index.data, key) : null;
  const variant = useRotationVariant(info && info.status === 'ok' ? key : null);

  if (!manifest || !instruments) return null;

  const head = (
    <header className="view-head">
      <Explain
        kinds={['rueckblick', 'rang']}
        term="umschichtung"
        sees={
          <>
            Eine feste Rechenregel zum Ausprobieren: Sie hält die gut gehandelten Aktien mit dem stärksten Anstieg der letzten Wochen zu gleichen Teilen und tauscht sie zu
            festen Terminen. Oben steht, was die Regel heute ändern würde, darunter ihr Rückblick nach Kosten und Steuern.
          </>
        }
        todo={<>Anzahl der Aktien, Takt („Umschichten“), Trend-Zeitraum und Startkapital wählen. Die Regel kauft und verkauft nichts – sie rechnet nur.</>}
        numbers={[
          ['Endwert nach Kosten und Steuern', 'So viel wäre aus dem Startkapital geworden, wenn man die Regel im Rückblick befolgt hätte – nach Orderkosten, Kursabschlag und Steuern.'],
          ['Größter Rückgang', 'Der größte Verlust vom bisherigen Höchststand bis zum folgenden Tiefpunkt, gemessen an den Freitagswerten.'],
          ['Heute nach der Regel', 'Welche Aktien die Regel zum letzten Kursstand halten, kaufen oder verkaufen würde. Kein Auftrag und keine Empfehlung.'],
        ]}
        how={<>Zu jedem Termin werden die Kandidaten nach ihrer Kursrendite im Trend-Zeitraum geordnet; die ersten kommen ins Depot, jede mit gleichem Anteil. Umgesetzt wird zum Schlusskurs des nächsten Handelstags. Die genauen Schritte stehen unter „Die Regel“. Ein früheres gutes Ergebnis sagt nichts über künftige Ergebnisse.</>}
      />
    </header>
  );

  if (!manifest.rotation) {
    if (manifest.art === 'zwischenstand') {
      const officialId = manifest.zwischenstand?.offizieller_stand ?? null;
      return (
        <div className="view">
          {head}
          <EmptyState title="Im Zwischenstand nicht gerechnet">
            <p>Die Umschichtungs-Regel rechnet mit Wochenschlusskursen und steht deshalb nur im Stand mit Schlusskursen.</p>
            {officialId ? (
              <div className="toolbar">
                <button type="button" className="btn btn-primary" onClick={() => switchSnapshot(officialId)}>
                  {closeLabel(manifest.zwischenstand?.offizieller_stichtag)} anzeigen
                </button>
              </div>
            ) : null}
          </EmptyState>
        </div>
      );
    }
    return (
      <div className="view">
        {head}
        <EmptyState title="In diesem Datenstand noch nicht gerechnet">
          <p>Die Umschichtungs-Regel gibt es ab Version 1.3. Der nächste tägliche Lauf rechnet sie mit.</p>
        </EmptyState>
      </div>
    );
  }
  if (index.error) {
    return (
      <div className="view">
        {head}
        <ErrorNote error={index.error} />
      </div>
    );
  }
  if (!index.data || !choice || !key) {
    return (
      <div className="view">
        {head}
        <Loading height={320} label="Umschichtungs-Regel wird geladen" />
      </div>
    );
  }

  const data = index.data;
  const set = (changes: Partial<Record<'n' | 'r' | 'w' | 'k', string | number>>) => updateParams(route, changes);

  return (
    <div className="view rotation-view">
      {head}
      <RuleSummary index={data} choice={choice} />
      <VariantControls index={data} choice={choice} onChange={set} />
      {data.langhistorie && data.langhistorie.offen > 0 ? (
        <Notice tone="info" title="Rückblick noch vorläufig">
          <p>
            Die Kurshistorie ist für {f.integer(data.langhistorie.geladen)} von {f.integer(data.langhistorie.aktien)} Aktien geladen; {f.integer(data.langhistorie.offen)} folgen in den nächsten Läufen. Bis dahin
            fehlen diese Aktien in älteren Wochen des Rückblicks.
          </p>
        </Notice>
      ) : null}
      {data.hinweis && !data.varianten.length ? (
        <Notice tone="info" title="Noch keine Ergebnisse">
          <p>{data.hinweis}</p>
        </Notice>
      ) : null}
      {info === null ? (
        <Notice tone="warn" title="Diese Variante wurde nicht gerechnet">
          <p>Bitte eine andere Kombination wählen.</p>
        </Notice>
      ) : info.status !== 'ok' ? (
        <Notice tone="info" title="Für diese Variante reicht die Kurshistorie noch nicht">
          <p>
            Die Regel braucht Wochenwerte für {lookbackText(choice.lookback)} Trend und {data.regel.umsatz_wochen} Wochen Umsatz, bevor sie das erste Mal umschichten kann. Die Langhistorie (bis{' '}
            {data.regel.langhistorie_jahre} Jahre) wird in den nächsten Läufen nachgeladen.
          </p>
        </Notice>
      ) : variant.error ? (
        <ErrorNote error={variant.error} />
      ) : !variant.data ? (
        <Loading height={360} label="Variante wird geladen" />
      ) : (
        <>
          <TodaySection preview={variant.data.vorschlag} choice={choice} index={data} instruments={instruments} />
          <BacktestSection variant={variant.data} info={info} index={data} choice={choice} />
          <CompareSection index={data} choice={choice} onPick={(v) => set({ n: v.aktien, r: v.rhythmus, w: v.trend_wochen })} />
          <OrdersSection variant={variant.data} instruments={instruments} />
          {variant.data.vorschlag ? <CandidatesSection preview={variant.data.vorschlag} index={data} choice={choice} instruments={instruments} /> : null}
        </>
      )}
      <LimitsSection index={data} />
    </div>
  );
}

/* ------------------------------------------------------------------ Regel in einem Satz */

function RuleSummary({ index, choice }: { index: RotationIndex; choice: VariantChoice }) {
  const rule = index.regel;
  return (
    <section className="section rule-card" aria-labelledby="regel">
      <SectionTitle id="regel">Die Regel</SectionTitle>
      <ol className="rule-steps">
        <li>
          <strong>Auswahl:</strong> Aktien aus der TR-Liste mit Ø Tagesumsatz ab {f.money(rule.min_umsatz_usd, 'USD')} (letzte {rule.umsatz_wochen} Wochen), Kursen an mindestens{' '}
          {f.plainPct(rule.min_abdeckung * 100, 0)} der Börsentage und ohne Tagessprung über Faktor {f.integer(rule.max_sprung_faktor)} (Verdacht auf Datenfehler).
        </li>
        <li>
          <strong>Rangfolge:</strong> nach Kursrendite der letzten {lookbackText(choice.lookback)}.
        </li>
        <li>
          <strong>Depot:</strong> die ersten {choice.holdings} Plätze, je {f.plainPct(targetShare(choice.holdings) * 100, 0)} des Depotwerts.
        </li>
        <li>
          <strong>Umschichten</strong> {rhythmText(choice.rhythm)} nach Börsenschluss, umgesetzt zum Schlusskurs des nächsten Handelstags: Eine Aktie bleibt, solange sie unter den ersten{' '}
          {choice.holdings * rule.haltepuffer_faktor} Plätzen liegt; freie Plätze bekommen die besten noch nicht gehaltenen Aktien. Angeglichen wird erst ab {f.integer(rule.anteil_toleranz * 100)}{' '}
          Prozentpunkten Abweichung.
        </li>
      </ol>
    </section>
  );
}

function VariantControls({ index, choice, onChange }: { index: RotationIndex; choice: VariantChoice; onChange: (changes: Partial<Record<'n' | 'r' | 'w' | 'k', string | number>>) => void }) {
  const rule = index.regel;
  return (
    <section className="section rule-controls" aria-label="Variante wählen">
      <Segmented label="Anzahl Aktien" options={rule.aktien.map((n) => ({ value: n, label: `${n} Aktien je ${f.plainPct(100 / n, 0)}` }))} value={choice.holdings} onChange={(n) => onChange({ n })} />
      <Segmented label="Umschichten" options={rule.rhythmus.map((r) => ({ value: r, label: rhythmLabel(r), title: rhythmText(r) }))} value={choice.rhythm} onChange={(r) => onChange({ r })} />
      <Segmented label="Trend über" options={rule.trend_wochen.map((w) => ({ value: w, label: `${w} Wochen` }))} value={choice.lookback} onChange={(w) => onChange({ w })} />
      <Segmented label="Startkapital im Rückblick" options={rule.kapital.map((k) => ({ value: k, label: f.euro(k) }))} value={choice.capital} onChange={(k) => onChange({ k })} />
    </section>
  );
}

/* ------------------------------------------------------------------ Heute */

function TodaySection({ preview, choice, index, instruments }: { preview: RotationPreview | null; choice: VariantChoice; index: RotationIndex; instruments: Instruments }) {
  const { prefs, setPrefs } = useApp();
  const [draft, setDraft] = useState<string>('');
  const [invalid, setInvalid] = useState(false);
  if (!preview) {
    return (
      <section className="section" aria-labelledby="heute">
        <SectionTitle id="heute">Heute nach der Regel</SectionTitle>
        <p className="section-note">Für den neuesten Kursstand liegt kein Vorschlag vor.</p>
      </section>
    );
  }
  const own = prefs.ruleDepot;
  const base = preview.depotwert;
  const money = (value: number | null) => f.euro(scaled(value, base, own));
  const held = holdings(preview);
  const todo = changes(preview);
  const numberOf = new Map<number, number>();
  held.forEach((h, k) => numberOf.set(h.idx, k + 1));
  todo.filter((c) => c.action === 'kauf').forEach((c) => numberOf.set(c.idx, numberOf.size + 1));
  const now = allocationNow(preview);
  const after = todo.length ? allocationAfter(preview, choice.holdings) : null;
  const buffer = choice.holdings * index.regel.haltepuffer_faktor;
  const cashShown = scaled(preview.bargeld, base, own);

  const save = () => {
    if (!draft.trim()) {
      setPrefs({ ruleDepot: null });
      setInvalid(false);
      return;
    }
    const value = parseEuro(draft);
    setInvalid(value === null);
    if (value !== null) {
      setPrefs({ ruleDepot: value });
      setDraft('');
    }
  };

  return (
    <section className="section" aria-labelledby="heute">
      <SectionTitle id="heute">Heute nach der Regel</SectionTitle>
      <p className="section-note">
        Kursstand {f.dayLong(preview.tag)}. {nextText(preview)} Das Regeldepot ist ein gedachtes Depot, das seit Beginn des Rückblicks genau nach der Regel gehandelt hat – dein eigenes Depot kennt die App
        nicht.
      </p>

      <div className="ruler-block alloc-block">
        <div className="alloc-head">
          <span className="alloc-title">Regeldepot heute</span>
          <span className="alloc-value">{money(base)}</span>
        </div>
        <AllocationBar slots={now} numberOf={numberOf} label="Aufteilung heute" instruments={instruments} />
        {after ? (
          <>
            <div className="alloc-head">
              <span className="alloc-title">Nach den Änderungen (ungefähr)</span>
            </div>
            <AllocationBar slots={after} numberOf={numberOf} label="Aufteilung nach den Änderungen" instruments={instruments} />
          </>
        ) : null}
        <p className="alloc-scale" aria-hidden="true">
          <span>0 %</span>
          <span>50 %</span>
          <span>100 %</span>
        </p>
      </div>

      <div className="own-depot">
        <label className="field-label" htmlFor="eigener-depotwert">
          Beträge umrechnen auf einen Depotwert von
        </label>
        <div className="own-depot-row">
          <input
            id="eigener-depotwert"
            className="input"
            inputMode="decimal"
            autoComplete="off"
            placeholder={own !== null ? f.euro(own) : `${f.integer(base)} (Regeldepot)`}
            value={draft}
            aria-invalid={invalid}
            aria-describedby="eigener-depotwert-hinweis"
            onChange={(e: Event) => setDraft((e.target as HTMLInputElement).value)}
            onKeyDown={(e: KeyboardEvent) => {
              if (e.key === 'Enter') save();
            }}
          />
          <button type="button" className="btn" onClick={save}>
            Übernehmen
          </button>
          {own !== null ? (
            <button
              type="button"
              className="btn btn-quiet"
              onClick={() => {
                setPrefs({ ruleDepot: null });
                setDraft('');
                setInvalid(false);
              }}
            >
              Zurücksetzen
            </button>
          ) : null}
        </div>
        <p id="eigener-depotwert-hinweis" className={`section-note${invalid ? ' field-error' : ''}`}>
          {invalid
            ? `Bitte einen Betrag zwischen ${f.euro(100)} und ${f.euro(100_000_000)} eingeben, z. B. 12.500.`
            : own !== null
              ? `Alle Beträge unten sind auf ${f.euro(own)} umgerechnet (gleiche Anteile). Gespeichert nur auf diesem Gerät.`
              : 'Ohne Angabe gelten die Beträge des Regeldepots.'}
        </p>
      </div>

      <h3 className="sub-title">{changesTitle(preview)}</h3>
      {todo.length ? (
        <ol className="change-list">
          {todo.map((c) => (
            <li key={`${c.action}-${c.idx}`} className={`change change-${isSell(c.action) ? 'sell' : 'buy'}`}>
              <span className="slot-no" aria-hidden="true">
                {numberOf.get(c.idx) ?? ''}
              </span>
              <div className="change-main">
                <p className="change-verb">{actionLabel(c.action)}</p>
                <a className="row-name" href={buildHash(`/aktie/${instruments.isin[c.idx]}`)}>
                  {instName(instruments, c.idx)}
                </a>
                <p className="change-figs">
                  Anteil {f.plainPct((c.before ?? 0) * 100, 1)} → {f.plainPct((c.after ?? 0) * 100, 1)}, etwa {money(c.value)}
                </p>
                <p className="section-note">
                  {reasonText(c.reason, { rank: c.rank, holdings: choice.holdings, keepFactor: index.regel.haltepuffer_faktor, band: index.regel.anteil_toleranz, before: c.before })}
                  {c.trend !== null ? `; Kursrendite ${choice.lookback} Wochen ${f.pct(c.trend, 1)}` : ''}.
                </p>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p className="section-note">
          Keine Änderung: Alle gehaltenen Aktien liegen unter den ersten {buffer} Plätzen und höchstens {f.integer(index.regel.anteil_toleranz * 100)} Prozentpunkte neben{' '}
          {f.plainPct(targetShare(choice.holdings) * 100, 0)}.
        </p>
      )}

      <h3 className="sub-title">Im Regeldepot</h3>
      {held.length ? (
        <ol className="rows hold-list">
          {held.map((h) => (
            <li key={h.idx} className="row hold-row">
              <span className="slot-no" aria-hidden="true">
                {numberOf.get(h.idx)}
              </span>
              <div className="row-main">
                <a className="row-link row-name" href={buildHash(`/aktie/${instruments.isin[h.idx]}`)}>
                  {instName(instruments, h.idx)}
                </a>
                <p className="row-meta">
                  seit {f.day(h.since)}, {h.rank !== null ? `heute Platz ${h.rank}` : 'heute nicht in der Auswahl'}
                  {h.trend !== null ? `, Kursrendite ${choice.lookback} Wochen ${f.pct(h.trend, 1)}` : ''}
                </p>
              </div>
              <div className="row-figs">
                <span className="pct pct-strong">{f.plainPct((h.share ?? 0) * 100, 1)}</span>
                <span className="row-fig-sub">{money(h.value)}</span>
                <span className="row-fig-sub">
                  seit Kauf <Pct value={h.ret} digits={1} />
                </span>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p className="section-note">Das Regeldepot hält gerade keine Aktie.</p>
      )}
      {cashShown !== null && cashShown >= 0.5 ? (
        <p className="section-note">
          Bargeld im Regeldepot: {f.euro(cashShown)}. Es entsteht, wenn gehaltene Aktien zusammen etwas unter ihrem Ziel liegen und noch nicht angeglichen werden, und aus Verkaufserlösen nach Steuern.
        </p>
      ) : null}
    </section>
  );
}

function AllocationBar({ slots, numberOf, label, instruments }: { slots: Slot[]; numberOf: Map<number, number>; label: string; instruments: Instruments }) {
  const text = slots
    .map((s) => (s.idx === null ? `Bargeld ${f.plainPct(s.share * 100, 1)}` : `${instName(instruments, s.idx)} ${f.plainPct(s.share * 100, 1)}`))
    .join(', ');
  return (
    <div className="alloc-bar" role="img" aria-label={`${label}: ${text}`}>
      {slots.map((s, k) => (
        <span
          key={s.idx ?? `bargeld-${k}`}
          className={`alloc-seg alloc-${s.kind}`}
          style={{ flexBasis: `${Math.max(0, s.share) * 100}%` }}
          title={s.idx === null ? `Bargeld ${f.plainPct(s.share * 100, 1)}` : `${instName(instruments, s.idx)}: ${f.plainPct(s.share * 100, 1)}`}
        >
          {s.share >= 0.06 ? <span className="alloc-num">{s.idx === null ? '€' : numberOf.get(s.idx)}</span> : null}
        </span>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Rückblick */

function BacktestSection({ variant, info, index, choice }: { variant: RotationVariant; info: RotationVariantInfo; index: RotationIndex; choice: VariantChoice }) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [highlight, setHighlight] = useState<string | null>(null);
  const stats = variant.kennzahlen;
  const capital = stats.startkapital ?? info.kapital;
  const lines = useMemo<CompareLine[]>(() => {
    const days = variant.verlauf.tage;
    return [
      { isin: 'regel', name: 'Regeldepot', note: 'nach Kosten und Steuern', slot: 0, pts: curve(days, variant.verlauf.depot), basePrice: capital, currency: 'EUR' },
      { isin: 'ohne', name: 'Regel ohne Kosten', note: 'ohne Orderkosten und Steuern', slot: 1, pts: curve(days, variant.verlauf.ohne_kosten), basePrice: capital, currency: 'EUR' },
      { isin: 'alle', name: 'Alle Kandidaten', note: 'zu gleichen Teilen, ohne Kosten', slot: 2, pts: curve(days, variant.verlauf.vergleich), basePrice: capital, currency: 'EUR' },
    ];
  }, [variant, capital]);
  const first = variant.verlauf.tage[0];
  const last = variant.verlauf.tage[variant.verlauf.tage.length - 1];
  const months = spanMonths(stats.tage);
  const toggle = (id: string) => {
    const next = new Set(hidden);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setHidden(next);
  };

  return (
    <section className="section" aria-labelledby="rueckblick">
      <SectionTitle id="rueckblick">Rückblick{months ? ` über ${f.plural(months, 'Monat', 'Monate')}` : ''}</SectionTitle>
      <p className="section-note">
        Start mit {f.euro(capital)} am {f.day(first)}, dann {rhythmText(choice.rhythm)} entschieden und am nächsten Handelstag umgesetzt, bis {f.day(last)}. Linien: Wert je Freitag, 100 =
        Startkapital.
      </p>
      {first !== undefined && last !== undefined ? (
        <CompareChart
          lines={lines}
          baseDay={first}
          end={last}
          hidden={hidden}
          highlight={highlight}
          onHighlight={setHighlight}
          onToggle={toggle}
          height={280}
          ariaLabel={`Wertverlauf des Regeldepots vom ${f.day(first)} bis ${f.day(last)}, 100 = Startkapital ${f.euro(capital)}`}
          formatValue={(close) => `${f.euro(close)} (${f.signedPctValue(100 * (close / capital - 1), 1)})`}
        />
      ) : null}
      <Figures stats={stats} />
      <Disclosure summary="Alle Kennzahlen dieser Variante">
        <KeyValues
          items={[
            ['Zeitraum', `${f.day(stats.start_day)} – ${f.day(stats.end_day)} (${f.integer(stats.tage)} Tage)`],
            ['Endwert nach Kosten und Steuern', `${f.euro(stats.endwert)} (${f.pct(stats.rendite, 1)})`],
            ['Endwert ohne Kosten und Steuern', `${f.euro(stats.endwert_ohne_kosten)} (${f.pct(stats.rendite_ohne_kosten, 1)})`],
            ['Alle Kandidaten zu gleichen Teilen', `${f.euro(stats.vergleich_endwert)} (${f.pct(stats.vergleich_rendite, 1)})`],
            ['Pro Jahr (nach Kosten)', stats.rendite_pro_jahr !== null && stats.rendite_pro_jahr !== undefined ? f.pct(stats.rendite_pro_jahr, 1) : 'erst ab einem Jahr Rückblick'],
            ['Pro Jahr (alle Kandidaten)', stats.vergleich_pro_jahr !== null && stats.vergleich_pro_jahr !== undefined ? f.pct(stats.vergleich_pro_jahr, 1) : 'erst ab einem Jahr Rückblick'],
            ['Größter Rückgang (Freitagswerte)', `${f.plainPct((stats.max_rueckgang ?? 0) * 100, 1)} (alle Kandidaten: ${f.plainPct((stats.vergleich_max_rueckgang ?? 0) * 100, 1)})`],
            ['Umschichtungstermine', f.integer(stats.umschichtungen)],
            ['Orders', `${f.integer(stats.orders)} (${f.integer(stats.kaeufe)} Käufe, ${f.integer(stats.verkaeufe)} Verkäufe)`],
            ['Orderkosten', `${f.euro(stats.gebuehren, true)} (${f.euro(index.kosten.order_eur, true)} je Order)`],
            ['Spanne (Kursabschlag)', `${f.euro(stats.spanne, true)} (${f.plainPct(index.kosten.spanne * 100, 1)} je Order)`],
            ['Steuern einbehalten (netto)', f.euro(stats.steuern, true)],
            ['Verlusttopf am Ende', f.euro(stats.verlusttopf, true)],
          ]}
        />
      </Disclosure>
    </section>
  );
}

function Figures({ stats }: { stats: Partial<RotationStats> }) {
  return (
    <div className="stats">
      <div className="stat">
        <span className="stat-value">{f.euro(stats.endwert)}</span>
        <span className="stat-label">Endwert nach Kosten und Steuern ({f.pct(stats.rendite, 1)})</span>
      </div>
      <div className="stat">
        <span className="stat-value">{f.pct(stats.vergleich_rendite, 1)}</span>
        <span className="stat-label">alle Kandidaten zu gleichen Teilen</span>
      </div>
      <div className="stat">
        <span className="stat-value">{f.plainPct((stats.max_rueckgang ?? 0) * 100, 1)}</span>
        <span className="stat-label">größter Rückgang zwischendurch</span>
      </div>
      <div className="stat">
        <span className="stat-value">{f.euro((stats.gebuehren ?? 0) + (stats.spanne ?? 0) + (stats.steuern ?? 0))}</span>
        <span className="stat-label">
          Kosten und Steuern bei {f.plural(stats.orders ?? 0, 'Order', 'Orders')}
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Varianten vergleichen */

function CompareSection({ index, choice, onPick }: { index: RotationIndex; choice: VariantChoice; onPick: (v: RotationVariantInfo) => void }) {
  const rows = compareRows(index, choice.capital);
  const current = variantKey(choice);
  return (
    <section className="section" aria-labelledby="varianten">
      <SectionTitle id="varianten">Alle Varianten mit {f.euro(choice.capital)} Startkapital</SectionTitle>
      <p className="section-note">Gleicher Zeitraum, gleiche Kosten. Antippen wählt die Variante. Ein besseres Ergebnis im Rückblick sagt nichts darüber, welche Variante künftig besser abschneidet.</p>
      <div className="table-wrap">
        <table className="table variant-table">
          <thead>
            <tr>
              <th scope="col">Variante</th>
              <th scope="col" className="n">
                nach Kosten
              </th>
              <th scope="col" className="n">
                alle Kandidaten
              </th>
              <th scope="col" className="n">
                größter Rückgang
              </th>
              <th scope="col" className="n">
                Orders
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ info }) => {
              const k = info.kennzahlen;
              const active = info.key === current;
              return (
                <tr key={info.key} className={active ? 'is-current' : ''} aria-current={active ? 'true' : undefined}>
                  <th scope="row">
                    <button type="button" className="table-pick" onClick={() => onPick(info)} aria-pressed={active}>
                      <span>
                        {info.aktien} Aktien, {rhythmLabel(info.rhythmus).toLowerCase()}
                      </span>
                      <span>Trend {info.trend_wochen} Wochen</span>
                    </button>
                  </th>
                  <td className="n">{info.status === 'ok' ? <Pct value={k.rendite ?? null} digits={1} /> : 'zu kurze Historie'}</td>
                  <td className="n">{info.status === 'ok' ? <Pct value={k.vergleich_rendite ?? null} digits={1} /> : '–'}</td>
                  <td className="n">{info.status === 'ok' ? f.plainPct((k.max_rueckgang ?? 0) * 100, 1) : '–'}</td>
                  <td className="n">{info.status === 'ok' ? f.integer(k.orders) : '–'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ Orders */

function OrdersSection({ variant, instruments }: { variant: RotationVariant; instruments: Instruments }) {
  const [all, setAll] = useState(false);
  const days = useMemo(() => rebalanceDays(variant), [variant]);
  const shown = all ? days : days.slice(0, DAYS_SHOWN);
  return (
    <section className="section" aria-labelledby="orders">
      <SectionTitle id="orders">Umschichtungen im Rückblick</SectionTitle>
      <p className="section-note">
        {f.plural(days.length, 'Termin', 'Termine')} mit Orders, neueste zuerst. Entschieden zum Freitagsschluss, ausgeführt zum Schlusskurs des nächsten Handelstags; Beträge vor Kosten, Gewinn nach Kosten
        und vor Steuern.
      </p>
      {days.length === 0 ? <p className="section-note">Im Rückblick gab es keine Orders.</p> : null}
      <div className="order-days">
        {shown.map((d) => (
          <Disclosure
            key={d.day}
            summary={
              <span className="order-day-summary">
                <strong>Entscheidung {f.dayWithWeekday(d.day)}</strong>
                <span>
                  ausgeführt ab {f.dayShort(d.execDay)}: {orderCount(d.orders.filter((o) => isSell(o.action)).length, d.orders.filter((o) => !isSell(o.action)).length)}
                  {Math.abs(d.taxes) >= 0.005 ? `, Steuer ${f.euro(d.taxes, true)}` : ''}
                </span>
              </span>
            }
          >
            <ul className="order-list">
              {d.orders.map((o, k) => (
                <li key={k} className="order">
                  <span className="order-verb">{actionPast(o.action)}</span>
                  <a className="row-name" href={buildHash(`/aktie/${instruments.isin[o.idx]}`)}>
                    {instName(instruments, o.idx)}
                  </a>
                  <span className="order-figs">
                    {f.euro(o.value)}, Anteil {f.plainPct((o.before ?? 0) * 100, 1)} → {f.plainPct((o.after ?? 0) * 100, 1)}
                    {o.rank !== null ? `, Platz ${o.rank}` : ', nicht mehr in der Auswahl'}
                    {o.gain !== null ? `, Gewinn ${f.signedEuro(o.gain)}` : ''}
                    {o.tax !== null && Math.abs(o.tax) >= 0.005 ? `, Steuer ${f.euro(o.tax, true)}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          </Disclosure>
        ))}
      </div>
      {days.length > DAYS_SHOWN ? (
        <div className="toolbar">
          <button type="button" className="btn" onClick={() => setAll(!all)}>
            {all ? 'Nur die letzten Termine' : `Alle ${days.length} Termine zeigen`}
          </button>
        </div>
      ) : null}
    </section>
  );
}

function orderCount(sells: number, buys: number): string {
  const parts = [];
  if (sells) parts.push(f.plural(sells, 'Verkauf', 'Verkäufe'));
  if (buys) parts.push(f.plural(buys, 'Kauf', 'Käufe'));
  return parts.join(', ') || 'keine Order';
}

/* ------------------------------------------------------------------ Kandidaten heute */

function CandidatesSection({ preview, index, choice, instruments }: { preview: RotationPreview; index: RotationIndex; choice: VariantChoice; instruments: Instruments }) {
  const list = candidates(preview);
  const buffer = choice.holdings * index.regel.haltepuffer_faktor;
  return (
    <section className="section" aria-labelledby="kandidaten">
      <SectionTitle id="kandidaten">Rangfolge heute</SectionTitle>
      <p className="section-note">
        Die ersten {list.length} Kandidaten nach Kursrendite der letzten {lookbackText(choice.lookback)}. Gekauft wird bis Platz {choice.holdings}, gehalten bis Platz {buffer}.
      </p>
      <ol className="rows">
        {list.map((c) => (
          <li key={c.idx} className={`row${c.rank === choice.holdings || c.rank === buffer ? ' row-cut' : ''}`}>
            <div className="row-rank">{c.rank}</div>
            <div className="row-main">
              <a className="row-link row-name" href={buildHash(`/aktie/${instruments.isin[c.idx]}`)}>
                {instName(instruments, c.idx)}
              </a>
              <p className="row-meta">
                Ø Umsatz {f.money(c.usd, 'USD')}
                {c.held ? ', im Regeldepot' : ''}
              </p>
            </div>
            <div className="row-figs">
              <Pct value={c.trend} digits={1} strong />
              <span className="row-fig-sub">{choice.lookback} Wochen</span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

/* ------------------------------------------------------------------ Grenzen */

function LimitsSection({ index }: { index: RotationIndex }) {
  const rule = index.regel;
  return (
    <section className="section" aria-labelledby="grenzen">
      <SectionTitle id="grenzen">Was die Rechnung nicht zeigt</SectionTitle>
      <ul className="prose limits">
        <li>
          <strong>Nur heutige Aktien:</strong> Der Rückblick rechnet mit Aktien, die heute in der TR-Liste stehen und heute mindestens {f.money(rule.vorauswahl_min_umsatz_usd, 'USD')} am Tag umsetzen. Aktien, die
          inzwischen pleite, übernommen oder abgestürzt sind, fehlen – das Ergebnis ist dadurch eher zu gut.
        </li>
        <li>
          <strong>Ausführung:</strong> gerechnet zum Schlusskurs des ersten Handelstags nach der Entscheidung, mit Bruchteilen von Aktien, {f.euro(index.kosten.order_eur, true)} Kosten und{' '}
          {f.plainPct(index.kosten.spanne * 100, 1)} Spanne je Order. Tatsächlich können Kurs, Uhrzeit und Kosten abweichen.
        </li>
        <li>
          <strong>Kursrendite ohne Dividenden</strong>, bewertet in Euro mit EZB-Referenzkursen ohne Umtauschkosten.
        </li>
        <li>
          <strong>Steuern vereinfacht:</strong> Abgeltungsteuer mit Solidaritätszuschlag ({f.plainPct(index.kosten.steuersatz * 100, 3)}), Sparerpauschbetrag {f.euro(index.kosten.freibetrag_eur)} je Jahr,
          Verlusttopf; ohne Kirchensteuer, ausländische Quellensteuer und andere Erträge.
        </li>
        <li>
          <strong>Trend-Regeln laufen nicht immer:</strong> Nach starken Anstiegen können die Spitzenreiter schnell und gemeinsam fallen. Ein gutes Ergebnis im Rückblick ist keine Vorhersage.
        </li>
        <li>Keine Anlageberatung, kein Angebot von Trade Republic. Die App kauft und verkauft nichts.</li>
      </ul>
      <p className="section-note">
        Version {index.version}, Rechenstand {f.day(index.stichtag)}, {f.plural(index.vorauswahl, 'Aktie', 'Aktien')} mit Wochenwerten. Formeln unter{' '}
        <a href="#/methodik">So wird gerechnet</a>.
      </p>
    </section>
  );
}
