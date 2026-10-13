import { seriesColor } from '../lib/colors';
import type { Marker } from '../lib/groups';
import { useDark } from './charts';

/** Wiederholungszeichen „↻ 14“ (lang: „↻ 14 erste Plätze“) mit fester Farbe für die häufigsten ISINs.
 * Die Farbe ist nur Zusatz – maßgeblich sind Zahl und ISIN. */
export function MarkBadge({ marker, context = 'in der Matrix', long = false, split = true }: { marker: Marker | undefined; context?: string; long?: boolean; split?: boolean }) {
  const dark = useDark();
  if (!marker || marker.count < 2) return null;
  const color = marker.slot !== null ? seriesColor(marker.slot, dark) : undefined;
  const text = `${marker.count} erste Plätze ${context}${split ? ` (Gruppe A: ${marker.countA}, Gruppe B: ${marker.countB})` : ''}`;
  return (
    <span className={`mark${marker.slot === null ? ' mark-neutral' : ''}`} title={text}>
      <i style={color ? { background: color } : undefined} aria-hidden="true" />
      <span aria-hidden="true">
        ↻ {marker.count}
        {long ? ' erste Plätze' : ''}
      </span>
      <span className="visually-hidden">{text}</span>
    </span>
  );
}
