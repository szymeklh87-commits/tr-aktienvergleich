/* Zwischenstand (ab 1.8): vorläufiger Stand mit aktuellen (verzögerten) Kursen des laufenden Handelstags.
 * Reine Funktionen für Texte und Entscheidungen der Anzeige – testbar ohne Browser. */

import * as f from './format';
import { joinNames, marketName } from './markets';
import type { IntradayInfo, Manifest, SnapshotSummary, Status } from './types';

const clockFmt = new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Berlin' });

/** „12:25 Uhr“ (Berliner Zeit) aus einem UTC-Zeitpunkt. */
export function berlinClock(isoUtc: string | null | undefined): string {
  if (!isoUtc) return '–';
  const ms = Date.parse(isoUtc);
  return Number.isFinite(ms) ? `${clockFmt.format(new Date(ms))} Uhr` : '–';
}

export function isIntraday(item: Pick<Manifest, 'art'> | Pick<SnapshotSummary, 'art'> | null | undefined): boolean {
  return item?.art === 'zwischenstand';
}

/** Name des Stands mit Schlusskursen neben einem Zwischenstand: „Schlusskurse 13.10.“ (ab 1.12.1 statt „Offiziell“ –
 * die Knöpfe sagen, was man bekommt). */
export function closeLabel(isoDay: string | null | undefined): string {
  return isoDay ? `Schlusskurse ${f.isoDate(isoDay).slice(0, 6)}` : 'Schlusskurse';
}

/** Kurzbezeichnung für Kopfzeile und Listen: „Zwischenstand 14.10., 12:25 Uhr“. */
export function intradayLabel(summary: Pick<SnapshotSummary, 'cutoff_session_date' | 'kurse_bis_utc'>): string {
  return `Zwischenstand ${f.isoDate(summary.cutoff_session_date)}, ${berlinClock(summary.kurse_bis_utc ?? null)}`;
}

/** Erklärung eines Zwischenstands in drei Sätzen: Stand der Kurse, Börsen mit und ohne Kurs, Bezug zum Stand mit Schlusskursen. */
export function intradayExplanation(manifest: Manifest): string[] {
  const info = manifest.zwischenstand;
  if (!info) return [];
  const withQuotes = [...info.boersen_mit_kurs].map(marketName).sort((a, b) => a.localeCompare(b, 'de'));
  const fetched = Date.parse(info.abgerufen_utc);
  const opensLater = (code: string) => {
    const at = info.oeffnung_utc?.[code];
    return at && Number.isFinite(Date.parse(at)) && Date.parse(at) > fetched ? ` (öffnet ${berlinClock(at)})` : '';
  };
  const without = [...info.boersen_ohne_kurs].sort((a, b) => marketName(a).localeCompare(marketName(b), 'de')).map((code) => `${marketName(code)}${opensLater(code)}`);
  const lines = [
    `Vorläufige Ranglisten mit Kursen vom ${f.dayLong(manifest.cutoff_day)} bis ${berlinClock(info.kurse_bis_utc)} (je nach Börse etwa 15–20 Minuten verzögert). Der letzte Kurs ist kein Schlusskurs – bis Börsenschluss ändert er sich noch.`,
    `${f.integer(info.aktien_mit_kurs)} Aktien haben einen Kurs von heute${withQuotes.length ? ` (${joinNames(withQuotes.slice(0, 6))}${withQuotes.length > 6 ? ` und ${withQuotes.length - 6} weitere Börsen` : ''})` : ''}.`,
  ];
  if (without.length) {
    const markets = `${joinNames(without.slice(0, 6))}${without.length > 6 ? ` und ${without.length - 6} weiteren Börsen` : ''}`;
    lines.push(
      countsWithClose(info)
        ? `Noch ohne Kurs von heute: Aktien aus ${markets}. Sie zählen mit dem Schlusskurs ${closeDaysText(info)} – ihre Zeiträume enden dort. Ein Zwischenstand nach der Öffnung rechnet sie mit dem Kurs von heute.`
        : `Noch ohne Kurs von heute und deshalb nicht in den Ranglisten: Aktien aus ${markets}. Ein Zwischenstand nach der Öffnung nimmt sie mit.`,
    );
  }
  lines.push(
    `Schlusskurse aller Börsen gibt es im Stand vom ${f.isoDate(info.offizieller_stichtag)} (Knopf „${closeLabel(info.offizieller_stichtag)}“). Morgen früh ersetzt der tägliche Lauf den Zwischenstand.`,
  );
  return lines;
}

/** Ab 1.13: zählen Aktien ohne Kurs von heute mit dem letzten Schlusskurs (statt zu fehlen)? */
export function countsWithClose(info: IntradayInfo | null | undefined): boolean {
  return Boolean(info?.boersen_mit_schlusskurs);
}

/** „vom 13.10.“ – Tag(e) der Schlusskurse noch nicht geöffneter Börsen; ohne Angabe der Handelstag vor dem Stichtag. */
export function closeDaysText(info: IntradayInfo): string {
  const days = [...new Set(Object.values(info.boersen_mit_schlusskurs ?? {}))].sort();
  if (!days.length) return 'des Handelstags davor';
  return `vom ${days.map((day) => f.isoDate(day).slice(0, 6)).join(' bzw. ')}`;
}

/** Ist der aktive Stand ein älterer Stand? Der offizielle Stand gilt neben einem Zwischenstand nicht als „älter“. */
export function isOlderStand(status: Status | null, activeId: string): boolean {
  if (!status) return false;
  if (status.latest_snapshot_id === activeId) return false;
  if (status.zwischenstand && status.latest_official_snapshot_id === activeId) return false;
  return true;
}

/** Ein Satz für die Hinweisleiste: Kurse bis wann, wie viele Aktien, welche Börsen noch fehlen. */
export function intradayBanner(manifest: Manifest): string {
  const info = manifest.zwischenstand;
  if (!info) return 'Vorläufige Ranglisten mit aktuellen Kursen.';
  const fetched = Date.parse(info.abgerufen_utc);
  const later = info.boersen_ohne_kurs
    .filter((code) => {
      const at = info.oeffnung_utc?.[code];
      return at && Date.parse(at) > fetched;
    })
    .map(marketName);
  const missing = info.boersen_ohne_kurs.length;
  const parts = [`Ranglisten mit Kursen von heute (verzögert) für ${f.plural(info.aktien_mit_kurs, 'Aktie', 'Aktien')}`];
  const withClose = countsWithClose(info) ? ` – mit Schlusskurs ${closeDaysText(info)}` : '';
  if (later.length) parts.push(`${joinNames([...new Set(later)].slice(0, 3))}${later.length > 3 ? ' u. a.' : ''} noch nicht geöffnet${withClose}`);
  else if (missing) parts.push(`${f.plural(missing, 'Börse', 'Börsen')} ohne Kurs von heute${withClose}`);
  const head = parts.join('; ');
  // „… vom 13.10.“ endet schon mit einem Punkt
  return `${head}${head.endsWith('.') ? '' : '.'} Schlusskurse aller Börsen: Stand vom ${f.isoDate(info.offizieller_stichtag)}.`;
}

/** Wann der tägliche Lauf kommt – ehrlich (ab 1.16): GitHub startet geplante Läufe oft einige Stunden später.
 *  Mit der tatsächlichen Startzeit des letzten geplanten Laufs, wenn er mehr als 30 Minuten zu spät kam. */
export function scheduleNote(status: Status | null | undefined): string {
  const time = status?.schedule?.uhrzeit ?? '07:00';
  const run = status?.last_run;
  const planned = run?.planned_start_utc ? Date.parse(run.planned_start_utc) : NaN;
  const started = run?.started_at_utc ? Date.parse(run.started_at_utc) : NaN;
  const late = Number.isFinite(planned) && Number.isFinite(started) && started - planned > 30 * 60 * 1000;
  return `Der tägliche Lauf ist ab ${time} Uhr geplant. GitHub startet geplante Läufe aber oft einige Stunden später${late ? ` – zuletzt um ${berlinClock(run?.started_at_utc)} statt ${berlinClock(run?.planned_start_utc)}` : ''}.`;
}
