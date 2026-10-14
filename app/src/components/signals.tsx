/* Bausteine für Signale, Ampeln, Kursziele und Prognose (ab 1.6).
 * Farbe ist nie allein bedeutungstragend: jede Ampel trägt ihr Wort, jeder Balken seine Zahl. */

import { useId, useState } from 'react';
import type { ReactNode } from 'react';
import * as f from '../lib/format';
import { GRADE_WORD, LIGHT_MEANING, LIGHT_WORD, MONTH_LABEL, ratingShares, type ConsistencyCell } from '../lib/signals';
import type { Light, RatingMonth, TotalGrade } from '../lib/types';

/** Ampel als Punkt mit Wort, z. B. „● grün“. ``label`` steht davor („Kurzfristig“). */
export function LightTag({ light, label, compact = false }: { light: Light; label?: string; compact?: boolean }) {
  return (
    <span className={`light light-${light}${compact ? ' light-compact' : ''}`} aria-label={`${label ? `${label}: ` : ''}${LIGHT_WORD[light]} – ${LIGHT_MEANING[light]}`}>
      {label ? <span className="light-label">{label}</span> : null}
      <span className="light-dot" aria-hidden="true" />
      <span className="light-word">{LIGHT_WORD[light]}</span>
    </span>
  );
}

/** Kleines ⓘ, das eine Erklärung direkt darunter auf- und zuklappt. */
export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <>
      <button type="button" className={`info-tip${open ? ' is-open' : ''}`} aria-expanded={open} aria-controls={id} aria-label={`Erklärung: ${label}`} onClick={() => setOpen(!open)}>
        i
      </button>
      {open ? (
        <span className="info-text" id={id} role="note">
          {children}
        </span>
      ) : null}
    </>
  );
}

/** Überschrift mit Erklärung zum Antippen. */
export function ExplainedTitle({ id, title, children }: { id?: string; title: string; children: ReactNode }) {
  return (
    <h2 className="section-title explained" id={id}>
      <span>{title}</span>
      <InfoTip label={title}>{children}</InfoTip>
    </h2>
  );
}

/** Punktebalken 0–100 mit Mittellinie bei 50. */
export function ScoreBar({ points, label }: { points: number | null; label: string }) {
  if (points === null) {
    return (
      <span className="score score-none" aria-label={`${label}: keine Daten`}>
        <span className="score-track" aria-hidden="true" />
        <span className="score-num">–</span>
      </span>
    );
  }
  const tone = points >= 60 ? 'pos' : points <= 40 ? 'neg' : 'neu';
  return (
    <span className={`score score-${tone}`} role="img" aria-label={`${label}: ${Math.round(points)} von 100 Punkten`}>
      <span className="score-track" aria-hidden="true">
        <span className="score-fill" style={{ width: `${Math.max(2, Math.min(100, points))}%` }} />
        <span className="score-center" />
      </span>
      <span className="score-num">{Math.round(points)}</span>
    </span>
  );
}

/** Große Punktzahl mit Ampel für ein Urteil (kurz- oder langfristig). */
export function VerdictCard({ title, light, points, sentence, hint }: { title: string; light: Light; points: number | null; sentence: string; hint: ReactNode }) {
  return (
    <div className={`verdict verdict-${light}`}>
      <div className="verdict-head">
        <span className="verdict-title">
          {title}
          <InfoTip label={`Regel ${title}`}>{hint}</InfoTip>
        </span>
        <LightTag light={light} />
      </div>
      <div className="verdict-points">
        <strong>{points === null ? '–' : Math.round(points)}</strong>
        <span>von 100 Punkten</span>
      </div>
      <p className="verdict-text">{sentence}</p>
    </div>
  );
}

/** Kursziel-Spanne: tiefstes bis höchstes Ziel, Durchschnitt und aktueller Kurs auf einer Achse. */
export function TargetRange({ close, low, mean, high, unit }: { close: number; low: number | null; mean: number; high: number | null; unit: string | null }) {
  const values = [close, mean, low ?? mean, high ?? mean];
  const min = Math.min(...values) * 0.94;
  const max = Math.max(...values) * 1.06;
  const x = (v: number) => ((v - min) / (max - min)) * 100;
  const up = mean >= close;
  return (
    <figure className="target-range" aria-label={`Kursziel: Durchschnitt ${f.price(mean, unit)}${low !== null && high !== null ? `, Spanne ${f.price(low, unit)} bis ${f.price(high, unit)}` : ''}, aktueller Kurs ${f.price(close, unit)}`}>
      <div className="tr-axis" aria-hidden="true">
        {low !== null && high !== null ? <span className="tr-span" style={{ left: `${x(low)}%`, width: `${Math.max(1, x(high) - x(low))}%` }} /> : null}
        <span className={`tr-gap ${up ? 'tr-gap-up' : 'tr-gap-down'}`} style={{ left: `${Math.min(x(close), x(mean))}%`, width: `${Math.abs(x(mean) - x(close))}%` }} />
        <span className="tr-mark tr-close" style={{ left: `${x(close)}%` }}>
          <small>Kurs</small>
        </span>
        <span className="tr-mark tr-mean" style={{ left: `${x(mean)}%` }}>
          <small>Ø Ziel</small>
        </span>
      </div>
      <figcaption className="tr-legend">
        {low !== null ? (
          <span>
            tiefstes <strong>{f.price(low, unit)}</strong>
          </span>
        ) : null}
        <span>
          Ø <strong>{f.price(mean, unit)}</strong>
        </span>
        {high !== null ? (
          <span>
            höchstes <strong>{f.price(high, unit)}</strong>
          </span>
        ) : null}
      </figcaption>
    </figure>
  );
}

/** Verteilung Kaufen/Halten/Verkaufen eines Monats als gestapelter Balken mit Zahlen. */
export function RatingBar({ row, label }: { row: RatingMonth; label?: string }) {
  const s = ratingShares(row);
  if (!s) return null;
  const buy = row.stark_kaufen + row.kaufen;
  const sell = row.verkaufen + row.stark_verkaufen;
  return (
    <div className="rating" role="img" aria-label={`${label ?? MONTH_LABEL[row.monat] ?? row.monat}: ${buy} Kaufen, ${row.halten} Halten, ${sell} Verkaufen`}>
      <span className="rating-label">{label ?? MONTH_LABEL[row.monat] ?? row.monat}</span>
      <span className="rating-bar" aria-hidden="true">
        {buy ? <span className="rating-buy" style={{ width: `${s.kaufen * 100}%` }} /> : null}
        {row.halten ? <span className="rating-hold" style={{ width: `${s.halten * 100}%` }} /> : null}
        {sell ? <span className="rating-sell" style={{ width: `${s.verkaufen * 100}%` }} /> : null}
      </span>
      <span className="rating-nums">
        {buy} · {row.halten} · {sell}
      </span>
    </div>
  );
}

/** Stimmung der Community: bullish gegen bearish, dazu Beiträge je Tag. */
export function CommunityBar({ bull, bear, perDay, posts }: { bull: number; bear: number; perDay: number | null; posts: number }) {
  const tagged = bull + bear;
  const share = tagged ? bull / tagged : 0;
  return (
    <div className="community">
      <div className="community-bar" role="img" aria-label={`${bull} bullish, ${bear} bearish von ${posts} Beiträgen`}>
        {tagged ? (
          <>
            <span className="community-bull" style={{ width: `${share * 100}%` }}>
              {share >= 0.15 ? `${Math.round(share * 100)} % bullish` : ''}
            </span>
            <span className="community-bear" style={{ width: `${(1 - share) * 100}%` }}>
              {1 - share >= 0.15 ? `${Math.round((1 - share) * 100)} % bearish` : ''}
            </span>
          </>
        ) : (
          <span className="community-none">keine markierten Beiträge</span>
        )}
      </div>
      <p className="community-meta">
        {f.integer(posts)} letzte Beiträge, davon {bull} steigend („bullish“) und {bear} fallend („bearish“) markiert
        {perDay !== null ? ` · etwa ${perDay.toFixed(perDay < 10 ? 1 : 0).replace('.', ',')} Beiträge pro Tag` : ''}
      </p>
    </div>
  );
}

/** Prognose-Grafik: Kursverlauf bis heute, danach 12 Monate mit Schwankungsband und Kurszielen der Analysten. */
export function ForecastChart({
  days,
  closes,
  close,
  today,
  targetLow,
  targetMean,
  targetHigh,
  band,
  unit,
}: {
  days: number[];
  closes: number[];
  close: number;
  today: number;
  targetLow: number | null;
  targetMean: number | null;
  targetHigh: number | null;
  band: [number | null, number | null] | null;
  unit: string | null;
}) {
  const W = 360;
  const H = 210;
  const padL = 46;
  const padR = 10;
  const padT = 14;
  const padB = 26;
  const start = days.length ? days[0] : today - 120;
  const end = today + 365;
  const lo = band && band[0] !== null ? band[0] : null;
  const hi = band && band[1] !== null ? band[1] : null;
  const ys = [...closes, close, ...(targetLow !== null ? [targetLow] : []), ...(targetHigh !== null ? [targetHigh] : []), ...(targetMean !== null ? [targetMean] : []), ...(lo !== null ? [lo] : []), ...(hi !== null ? [hi] : [])];
  let yMin = Math.min(...ys);
  let yMax = Math.max(...ys);
  const pad = (yMax - yMin) * 0.08 || yMax * 0.05;
  yMin = Math.max(0, yMin - pad);
  yMax = yMax + pad;
  const x = (d: number) => padL + ((d - start) / (end - start)) * (W - padL - padR);
  const y = (v: number) => padT + (1 - (v - yMin) / (yMax - yMin)) * (H - padT - padB);
  const path = days.map((d, k) => `${k ? 'L' : 'M'}${x(d).toFixed(1)},${y(closes[k]).toFixed(1)}`).join('');
  const ticks = [yMin + (yMax - yMin) * 0.1, (yMin + yMax) / 2, yMax - (yMax - yMin) * 0.1];
  const xEnd = x(end);
  const xNow = x(today);
  const caption = [
    targetMean !== null ? `Ø Kursziel ${f.price(targetMean, unit)} (${f.pct(targetMean / close - 1, 0)})` : 'keine Kursziele',
    lo !== null && hi !== null ? `übliche Schwankung in 12 Monaten ${f.price(lo, unit)} bis ${f.price(hi, unit)}` : null,
  ]
    .filter(Boolean)
    .join('; ');
  return (
    <figure className="forecast" aria-label={`Prognose-Grafik: Kursverlauf bis heute (${f.price(close, unit)}) und Ausblick 12 Monate. ${caption}.`}>
      <svg viewBox={`0 0 ${W} ${H}`} role="presentation" aria-hidden="true">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} className="fc-grid" />
            <text x={padL - 6} y={y(t) + 3} className="fc-label" textAnchor="end">
              {f.price(t, null)}
            </text>
          </g>
        ))}
        <rect x={xNow} y={padT} width={xEnd - xNow} height={H - padT - padB} className="fc-future" />
        {lo !== null && hi !== null ? <path d={`M${xNow},${y(close)}L${xEnd},${y(hi)}L${xEnd},${y(lo)}Z`} className="fc-band" /> : null}
        {targetLow !== null && targetHigh !== null ? <line x1={xEnd - 6} x2={xEnd - 6} y1={y(targetHigh)} y2={y(targetLow)} className="fc-target-range" /> : null}
        {targetMean !== null ? <line x1={xNow} y1={y(close)} x2={xEnd - 6} y2={y(targetMean)} className="fc-target-line" /> : null}
        {targetMean !== null ? <circle cx={xEnd - 6} cy={y(targetMean)} r={4.5} className="fc-target-dot" /> : null}
        <path d={path} className="fc-line" />
        <circle cx={xNow} cy={y(close)} r={3.5} className="fc-now" />
        <line x1={xNow} x2={xNow} y1={padT} y2={H - padB} className="fc-today" />
        <text x={x(start)} y={H - 8} className="fc-label">
          {f.dayShort(start)}
        </text>
        <text x={xNow} y={H - 8} className="fc-label" textAnchor="middle">
          heute
        </text>
        <text x={xEnd} y={H - 8} className="fc-label" textAnchor="end">
          +12 Monate
        </text>
      </svg>
      <figcaption className="fc-legend">
        <span className="fc-key fc-key-line">Kurs bisher</span>
        {targetMean !== null ? <span className="fc-key fc-key-target">Kursziele der Analysten (Ø, Spanne)</span> : null}
        {lo !== null ? <span className="fc-key fc-key-band">übliche Schwankung (2 von 3 Fällen)</span> : null}
      </figcaption>
    </figure>
  );
}

/** Gesamtwertung als Zahl mit Stufe (Farbe nie allein: Zahl und Wort). */
export function TotalBadge({ total, grade, size = 'row' }: { total: number | null; grade: TotalGrade; size?: 'row' | 'big' }) {
  return (
    <span className={`total total-${grade} total-${size}`} role="img" aria-label={total === null ? 'Gesamtwertung: keine' : `Gesamtwertung ${Math.round(total)} von 100 – ${GRADE_WORD[grade]}`}>
      <strong aria-hidden="true">{total === null ? '–' : Math.round(total)}</strong>
      {size === 'big' ? <span aria-hidden="true">{GRADE_WORD[grade]}</span> : null}
    </span>
  );
}

/** Steig-Konstanz: je Zeitraum „▲ 15/21“ (an 15 von 21 Handelstagen gestiegen) mit Ton. */
export function ConsistencyStrip({ cells, wide = false }: { cells: ConsistencyCell[]; wide?: boolean }) {
  if (!cells.length) return null;
  const label = cells.map((c) => `${c.tage} Tage: an ${c.auf} von ${c.von} Handelstagen gestiegen${c.rendite !== null ? `, Kurs ${f.pct(c.rendite, 0)}` : ''}`).join('; ');
  return (
    <span className={`kons${wide ? ' kons-wide' : ''}`} role="img" aria-label={`Steig-Konstanz – ${label}`}>
      {cells.map((c) => (
        <span key={c.tage} className={`kons-cell kons-${c.ton}`} aria-hidden="true">
          <small>{c.tage} T</small>
          <span className="kons-bar">
            <span style={{ width: `${Math.round(c.anteil * 100)}%` }} />
          </span>
          <b>
            ▲{c.auf}/{c.von}
          </b>
        </span>
      ))}
    </span>
  );
}

/** Teil der Gesamtwertung: Name, Gewicht, Punktebalken (ohne Mittellinie) und Beitrag. */
export function TotalPartRow({ name, weight, points, contribution, explain }: { name: string; weight: number; points: number | null; contribution: number | null; explain: string }) {
  const tone = points === null ? 'none' : points >= 60 ? 'pos' : points <= 40 ? 'neg' : 'neu';
  return (
    <li className="tp-row">
      <span className="tp-name">
        {name} <small>{Math.round(weight * 100)} %</small>
        <InfoTip label={name}>{explain}</InfoTip>
      </span>
      <span className={`tp-bar tp-${tone}`} role="img" aria-label={points === null ? `${name}: keine Daten` : `${name}: ${Math.round(points)} von 100 Punkten`}>
        <span style={{ width: `${points === null ? 0 : Math.max(2, Math.min(100, points))}%` }} />
      </span>
      <span className="tp-num">{points === null ? '–' : Math.round(points)}</span>
      <span className="tp-contrib">{contribution === null ? '' : `+${contribution.toFixed(1).replace('.', ',')}`}</span>
    </li>
  );
}

/** Was dafür und was dagegen spricht – zwei Listen mit Zeichen und Wort (Farbe nie allein). */
export function ProContra({ pro, contra }: { pro: string[]; contra: string[] }) {
  if (!pro.length && !contra.length) return null;
  return (
    <div className="pc">
      <div className="pc-col pc-pro">
        <h3 className="pc-title">
          <span aria-hidden="true">▲</span> Dafür spricht
        </h3>
        {pro.length ? (
          <ul>
            {pro.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        ) : (
          <p className="pc-empty">kein deutliches positives Signal</p>
        )}
      </div>
      <div className="pc-col pc-con">
        <h3 className="pc-title">
          <span aria-hidden="true">▼</span> Dagegen spricht
        </h3>
        {contra.length ? (
          <ul>
            {contra.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        ) : (
          <p className="pc-empty">kein deutliches negatives Signal</p>
        )}
      </div>
    </div>
  );
}

const CHECK_MARK: Record<'ja' | 'nein' | 'neutral', { sign: string; word: string }> = {
  ja: { sign: '✓', word: 'spricht dafür' },
  nein: { sign: '✗', word: 'spricht dagegen' },
  neutral: { sign: '–', word: 'neutral' },
};

/** Checkliste: je Punkt Zeichen, Name mit Erklärung zum Antippen und Wert. */
export function CheckList({ items }: { items: { key: string; label: string; value: string; ok: boolean | null; why: string }[] }) {
  return (
    <ul className="checks">
      {items.map((item) => {
        const state = item.ok === true ? 'ja' : item.ok === false ? 'nein' : 'neutral';
        return (
          <li key={item.key} className={`check check-${state}`}>
            <span className="check-sign" role="img" aria-label={CHECK_MARK[state].word}>
              {CHECK_MARK[state].sign}
            </span>
            <span className="check-label">
              {item.label}
              <InfoTip label={item.label}>{item.why}</InfoTip>
            </span>
            <span className="check-value">{item.value}</span>
          </li>
        );
      })}
    </ul>
  );
}
