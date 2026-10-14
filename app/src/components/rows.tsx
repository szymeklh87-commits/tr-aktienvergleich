import type { ReactNode } from 'react';
import * as f from '../lib/format';
import { instName, trNameIfDifferent } from '../lib/instruments';
import { isIntraday } from '../lib/intraday';
import { useApp } from '../state/AppState';
import { IsinCopy, WatchButton } from './ui';

/** Listenzeile einer Aktie: voller Name (bricht um), ISIN mit Kopierfunktion, Kennzahlen rechts.
 * Die ganze Zeile ist mit einem Tippen erreichbar; Kopieren und Merken bleiben eigene Schalter. */
export function InstrumentRow({
  idx,
  href,
  rank,
  rankNote,
  figs,
  meta,
  children,
  tie = false,
  watch = true,
  className = '',
}: {
  idx: number;
  href: string;
  rank?: ReactNode;
  rankNote?: ReactNode;
  figs?: ReactNode;
  meta?: ReactNode;
  children?: ReactNode;
  tie?: boolean;
  watch?: boolean;
  className?: string;
}) {
  const { instruments } = useApp();
  if (!instruments) return null;
  const name = instName(instruments, idx);
  const trName = trNameIfDifferent(instruments, idx);
  const isin = instruments.isin[idx];
  return (
    <li className={`row${rank === undefined ? ' row-nr' : ''}${tie ? ' row-tie' : ''}${className ? ` ${className}` : ''}`}>
      {rank !== undefined ? (
        <div className="row-rank">
          {rank}
          {rankNote ? <small>{rankNote}</small> : null}
          {watch ? <WatchButton isin={isin} name={name} /> : null}
        </div>
      ) : null}
      <div className="row-main">
        <a className="row-link row-name" href={href}>
          {name}
        </a>
        {trName ? <span className="row-alt">In der TR-Liste: {trName}</span> : null}
        <div className="row-meta">
          <IsinCopy isin={isin} compact />
          <LastCloseBadge idx={idx} />
          {meta}
          {watch && rank === undefined ? <WatchButton isin={isin} name={name} /> : null}
        </div>
      </div>
      <div className="row-figs">{figs}</div>
      {children ? <div className="row-extra row-wide">{children}</div> : null}
    </li>
  );
}

/** „Schlusskurs 09.10.“: Die Aktie hat keinen Kurs am Stichtag und zählt mit ihrem letzten Schlusskurs (Zwischenstand ab
 * 1.13, alle Stände ab tr-methode-1.9.0) – in jeder Liste gleich sichtbar. */
export function LastCloseBadge({ idx }: { idx: number }) {
  const { instruments, manifest } = useApp();
  if (!instruments || !manifest) return null;
  const lastDay = instruments.last_close_day[idx];
  const withLastClose = isIntraday(manifest) || Boolean(manifest.letzter_schlusskurs);
  if (!withLastClose || lastDay === null || lastDay === undefined || lastDay >= manifest.cutoff_day) return null;
  const title = isIntraday(manifest)
    ? `Noch ohne Kurs von heute – gerechnet mit dem Schlusskurs vom ${f.day(lastDay)}`
    : `Kein Schlusskurs am Stichtag (Feiertag der Börse oder nicht geliefert) – gerechnet mit dem Schlusskurs vom ${f.day(lastDay)}`;
  return (
    <span className="badge row-close" title={title}>
      Schlusskurs {f.dayShort(lastDay)}
    </span>
  );
}
