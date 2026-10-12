/* Deutsche Darstellung. Gerundet wird ausschließlich hier, nie in den Daten. */

const MINUS = '−';
const NBSP = ' ';
const DAY_MS = 86_400_000;

const nf = (min: number, max: number) =>
  new Intl.NumberFormat('de-DE', { minimumFractionDigits: min, maximumFractionDigits: max, useGrouping: true });

const fmt2 = nf(2, 2);
const fmt1 = nf(1, 1);
const fmt4 = nf(4, 4);
const fmt0 = nf(0, 0);

function signed(value: number, formatter: Intl.NumberFormat): string {
  const text = formatter.format(Math.abs(value));
  if (text.replace(/[0,.]/g, '') === '') return text; // gerundet null → ohne Vorzeichen
  return (value > 0 ? '+' : value < 0 ? MINUS : '') + text;
}

/** Kursrendite als Prozent mit Vorzeichen: 0.12 → „+12,00 %“. Fehlender Wert → „–“. */
export function pct(fraction: number | null | undefined, digits = 2): string {
  if (fraction === null || fraction === undefined || !Number.isFinite(fraction)) return '–';
  const formatter = digits === 2 ? fmt2 : digits === 1 ? fmt1 : nf(digits, digits);
  return `${signed(fraction * 100, formatter)}${NBSP}%`;
}

/** Textliche Richtung zusätzlich zur Farbe (Barrierefreiheit). */
export function direction(fraction: number | null | undefined): 'plus' | 'minus' | 'null' | 'fehlt' {
  if (fraction === null || fraction === undefined || !Number.isFinite(fraction)) return 'fehlt';
  if (fraction > 0) return 'plus';
  if (fraction < 0) return 'minus';
  return 'null';
}

export function directionWord(fraction: number | null | undefined): string {
  switch (direction(fraction)) {
    case 'plus':
      return 'gestiegen';
    case 'minus':
      return 'gefallen';
    case 'null':
      return 'unverändert';
    default:
      return 'nicht berechenbar';
  }
}

export function r2(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '–';
  return fmt4.format(value);
}

export function score(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '–';
  return fmt1.format(value);
}

export function plainPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '–';
  return `${nf(digits, digits).format(value)}${NBSP}%`;
}

export function signedPctValue(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '–';
  return `${signed(value, nf(digits, digits))}${NBSP}%`;
}

export function integer(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '–';
  return fmt0.format(value);
}

/** Kurs mit sinnvoller Genauigkeit und Einheit (z. B. „1.234,50 EUR“, „512,4 GBp“). */
export function price(value: number | null | undefined, unit?: string | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '–';
  const abs = Math.abs(value);
  const digits = abs >= 1000 ? 2 : abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
  const text = nf(digits, digits).format(value);
  return unit ? `${text}${NBSP}${unit}` : text;
}

export function volume(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'unbekannt';
  return fmt0.format(value);
}

export function dayToDate(day: number): Date {
  return new Date(day * DAY_MS);
}

export function dateToDay(date: Date): number {
  return Math.floor(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()) / DAY_MS);
}

export function isoToDay(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number);
  return Math.floor(Date.UTC(y, m - 1, d) / DAY_MS);
}

const dateFmt = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC' });
const shortDateFmt = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', timeZone: 'UTC' });
const weekdayFmt = new Intl.DateTimeFormat('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC' });
const berlinFmt = new Intl.DateTimeFormat('de-DE', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'Europe/Berlin',
});

/** Sitzungsdatum (Epochentag) als TT.MM.JJJJ. */
export function day(dayNumber: number | null | undefined): string {
  if (dayNumber === null || dayNumber === undefined || dayNumber < 0) return '–';
  return dateFmt.format(dayToDate(dayNumber));
}

export function dayShort(dayNumber: number | null | undefined): string {
  if (dayNumber === null || dayNumber === undefined || dayNumber < 0) return '–';
  return shortDateFmt.format(dayToDate(dayNumber));
}

export function dayWithWeekday(dayNumber: number | null | undefined): string {
  if (dayNumber === null || dayNumber === undefined || dayNumber < 0) return '–';
  return weekdayFmt.format(dayToDate(dayNumber));
}

export function isoDate(iso: string | null | undefined): string {
  if (!iso) return '–';
  return day(isoToDay(iso));
}

/** UTC-Zeitstempel in Berliner Zeit. */
export function berlinTime(isoUtc: string | null | undefined): string {
  if (!isoUtc) return '–';
  const date = new Date(isoUtc);
  if (Number.isNaN(date.getTime())) return '–';
  return `${berlinFmt.format(date)} Uhr`;
}

export function ageHours(isoUtc: string | null | undefined, now = Date.now()): number | null {
  if (!isoUtc) return null;
  const t = new Date(isoUtc).getTime();
  if (Number.isNaN(t)) return null;
  return (now - t) / 3_600_000;
}

export function relativeAge(isoUtc: string | null | undefined, now = Date.now()): string {
  const hours = ageHours(isoUtc, now);
  if (hours === null) return 'unbekannt';
  if (hours < 1) return 'vor weniger als einer Stunde';
  if (hours < 48) return `vor ${Math.floor(hours)} Std.`;
  return `vor ${Math.floor(hours / 24)} Tagen`;
}

const longFmt = new Intl.DateTimeFormat('de-DE', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });

/** „Montag, 12. Oktober 2026“ */
export function dayLong(dayNumber: number | null | undefined): string {
  if (dayNumber === null || dayNumber === undefined || dayNumber < 0) return '–';
  return longFmt.format(dayToDate(dayNumber));
}

/** Tatsächlicher Zeitraum „11.09.2026 – 12.10.2026“. */
export function dayRange(from: number | null | undefined, to: number | null | undefined): string {
  return `${day(from)} – ${day(to)}`;
}

/** „1 Aktie“ / „159 Aktien“ */
export function plural(n: number, one: string, many: string): string {
  return `${integer(n)} ${n === 1 ? one : many}`;
}

/** Anteil als Prozent mit ausdrücklichem Nenner; Nenner 0 → nicht berechenbar. */
export function share(part: number, whole: number, digits = 1): string {
  if (!whole) return 'nicht berechenbar';
  return plainPct((100 * part) / whole, digits);
}

export function windowLabel(h: number): string {
  return h === 1 ? '1 Kalendertag' : `${h} Kalendertage`;
}

export function weightLabel(w: number): string {
  if (w === 0) return 'Nur Kursrendite (0 % Gleichmäßigkeit · 100 % Rendite)';
  if (w === 100) return 'Nur Gleichmäßigkeit (100 % Gleichmäßigkeit · 0 % Rendite)';
  return `${w} % Gleichmäßigkeit · ${100 - w} % Rendite`;
}

export function weightShort(w: number): string {
  return `${w}/${100 - w}`;
}
