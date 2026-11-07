/* Hinweis bei einem Problem mit der Aktualisierung (ab 1.17): was passiert ist und was du tun kannst. Ab 1.20.5 dazu der
 * Datenstand in vier Zeilen (Befund F02): offizieller Kursstand, Zwischenstand, letzte erfolgreiche Aktualisierung und
 * letzter fehlgeschlagener Lauf – ein Zwischenstand verdeckt nie einen gescheiterten offiziellen Tageslauf. */

import { lastOfficialSuccess, officialFailure, plainReason, sessionName, whenBerlin, type FreshnessProblem } from '../lib/freshness';
import { berlinClock } from '../lib/intraday';
import type { Status } from '../lib/types';
import { Notice } from './ui';

export function FreshnessNotice({ problem }: { problem: FreshnessProblem }) {
  return (
    <Notice tone="warn" title={problem.title}>
      <p>{problem.text}</p>
      <p>
        <strong>Was du tun kannst:</strong> {problem.todo}
      </p>
    </Notice>
  );
}

/** Hinweis: Der angezeigte Zwischenstand baut auf ungeprüften Schlusskursen auf (ab 1.20.5, Befund F05). */
export function UnverifiedBaseNotice({ text }: { text: string }) {
  return (
    <Notice tone="warn" title="Ungeprüfte Grundlage – keine Kaufsignale">
      <p>{text}</p>
    </Notice>
  );
}

function when(iso: string | null | undefined, now: number): string {
  const ms = iso ? Date.parse(iso) : NaN;
  return Number.isFinite(ms) ? whenBerlin(ms, now) : '–';
}

/** Die vier Angaben zum Datenstand (ab 1.20.5). */
export function StandFacts({ status, now = Date.now() }: { status: Status | null | undefined; now?: number }) {
  if (!status) return null;
  const official = status.offiziell ?? null;
  const session = official?.kursstand ?? status.last_price_session ?? null;
  const intraday = status.zwischenstand ?? null;
  const success = lastOfficialSuccess(status);
  const failure = officialFailure(status);
  const count = official?.fehlschlaege_seit_erfolg ?? (failure ? 1 : 0);
  const reason = failure ? plainReason(failure.message) : null;
  return (
    <dl className="stand-facts">
      <div>
        <dt>Offizieller Kursstand</dt>
        <dd>
          {session ? `Schlusskurse vom ${sessionName(session)}` : 'noch keiner'}
          {official?.veroeffentlicht_utc ? `, veröffentlicht ${when(official.veroeffentlicht_utc, now)}` : ''}
          {official?.vollstaendigkeit === 'teilstand' ? ' (Teilstand)' : ''}
        </dd>
      </div>
      <div>
        <dt>Zwischenstand</dt>
        <dd>
          {intraday ? (
            <>
              {sessionName(intraday.stichtag)}, Kurse bis {berlinClock(intraday.kurse_bis_utc)}
              {intraday.basis_geprueft === false ? <strong className="fact-warn"> – ungeprüfte Grundlage</strong> : null}
            </>
          ) : (
            'keiner (der offizielle Stand ist der neueste)'
          )}
        </dd>
      </div>
      <div>
        <dt>Letzte erfolgreiche Aktualisierung</dt>
        <dd>{success ? when(success, now) : 'noch keine'}</dd>
      </div>
      <div>
        <dt>Letzter fehlgeschlagener Lauf</dt>
        <dd>
          {failure ? (
            <strong className="fact-warn">
              {when(failure.finished_at_utc ?? failure.started_at_utc, now)}
              {count > 1 ? ` (${count}-mal seit der letzten erfolgreichen Aktualisierung)` : ''}
              {reason ? ` – ${reason}` : ''}
            </strong>
          ) : (
            'keiner seit der letzten erfolgreichen Aktualisierung'
          )}
        </dd>
      </div>
    </dl>
  );
}
