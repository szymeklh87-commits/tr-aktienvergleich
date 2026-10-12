import type { ReactNode } from 'react';
import { instName, trNameIfDifferent } from '../lib/instruments';
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
          {meta}
          {watch && rank === undefined ? <WatchButton isin={isin} name={name} /> : null}
        </div>
      </div>
      <div className="row-figs">{figs}</div>
      {children ? <div className="row-extra row-wide">{children}</div> : null}
    </li>
  );
}
