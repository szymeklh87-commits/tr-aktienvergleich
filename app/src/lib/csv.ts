/* CSV-Export für Excel (deutsch): Semikolon, Dezimalkomma, UTF-8 mit BOM.
 * Schutz gegen Tabellenformel-Injection: Textzellen, die mit = + - @ Tab oder CR
 * beginnen, erhalten ein vorangestelltes Apostroph. Zahlen bleiben Zahlen; ISINs und
 * Namen werden sonst nicht verändert. */

const DANGEROUS = /^[=+\-@\t\r]/;

export type CsvValue = string | number | null | undefined | boolean;

export function formatNumber(value: number, digits?: number): string {
  if (!Number.isFinite(value)) return '';
  const text = digits === undefined ? String(value) : value.toFixed(digits);
  return text.replace('.', ',');
}

export function csvCell(value: CsvValue, digits?: number): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'boolean') return value ? 'ja' : 'nein';
  if (typeof value === 'number') return formatNumber(value, digits);
  let text = String(value);
  if (DANGEROUS.test(text)) text = `'${text}`;
  if (/[;"\n\r]/.test(text)) text = `"${text.replace(/"/g, '""')}"`;
  return text;
}

export function toCsv(meta: [string, string][], header: string[], rows: CsvValue[][], digits: (number | undefined)[] = []): string {
  const lines: string[] = [];
  for (const [k, v] of meta) lines.push(`${csvCell(`# ${k}`)};${csvCell(v)}`);
  lines.push(header.map((h) => csvCell(h)).join(';'));
  for (const row of rows) lines.push(row.map((value, i) => csvCell(value, digits[i])).join(';'));
  return '﻿' + lines.join('\r\n') + '\r\n';
}

export function downloadText(filename: string, text: string, mime = 'text/csv;charset=utf-8'): void {
  const blob = new Blob([text], { type: mime });
  downloadBlob(filename, blob);
}

export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function safeFilename(text: string): string {
  return text.replace(/[^A-Za-z0-9._-]+/g, '_').slice(0, 120);
}
