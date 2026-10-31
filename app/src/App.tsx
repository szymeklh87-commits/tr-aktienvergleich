import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { IconBack, IconClose, IconLadder, IconMatrix, IconMore, IconPilot, IconStart, IconStocks, IconTarget } from './components/icons';
import { ViewBoundary } from './components/boundary';
import { Loading, Notice } from './components/ui';
import * as f from './lib/format';
import { navigate, useRoute, type Route } from './lib/router';
import { centerActive, useScrollMemory } from './lib/scroll';
import { useApp } from './state/AppState';
import { CorrectionsView } from './views/CorrectionsView';
import { CoverageView } from './views/CoverageView';
import { DetailView } from './views/DetailView';
import { FrequencyMatrixView, FrequencyView } from './views/FrequencyView';
import { GridView } from './views/GridView';
import { GroupFrequencyView } from './views/GroupFrequencyView';
import { InstallView } from './views/InstallView';
import { MatrixView } from './views/MatrixView';
import { MethodView } from './views/MethodView';
import { RankingView } from './views/RankingView';
import { RotationView } from './views/RotationView';
import { ReturnListView, ReturnRankingsView } from './views/ReturnRankingsView';
import { SettingsView } from './views/SettingsView';
import { StartView } from './views/StartView';
import { StatusView } from './views/StatusView';
import { UnlockView } from './views/UnlockView';
import { UpdateView } from './views/UpdateView';
import { outcomeText } from './lib/update';
import { berlinClock, closeLabel, isIntraday, isOlderStand, scheduleNote } from './lib/intraday';
import { WatchlistView } from './views/WatchlistView';
import { WeightCompareView } from './views/WeightCompareView';
import { WinnersView } from './views/WinnersView';
import { AnalyseView } from './views/AnalyseView';
import { PotentialView } from './views/PotentialView';
import { ReportView } from './views/ReportView';
import { DepotsView } from './views/DepotsView';
import { HelpView } from './views/HelpView';
import { describeError } from './lib/errors';
import { TopView } from './views/TopView';
import { PilotView } from './views/PilotView';
import { MusterView } from './views/MusterView';
import { PREVIEW } from './lib/env';

/** Hauptnavigation: sechs Bereiche (ab Gesamtauftrag mit „Pilot“ – Spielgeld-Robo). Zu welchem Bereich eine Ansicht gehört, steht in GROUP. */
const NAV = [
  { path: '/', label: 'Start', icon: IconStart },
  { path: '/rendite', label: 'Rendite', icon: IconLadder },
  { path: '/potenzial', label: 'Potenzial', icon: IconTarget },
  { path: '/aktien', label: 'Aktien', icon: IconStocks },
  { path: '/analyse', label: 'Analyse', icon: IconMatrix },
  { path: '/pilot', label: 'Pilot', icon: IconPilot },
];

const GROUP: Record<string, string> = {
  '': '/',
  top: '/',
  rendite: '/rendite',
  ranking: '/rendite',
  sieger: '/rendite',
  bericht: '/rendite',
  depots: '/rendite',
  potenzial: '/potenzial',
  muster: '/potenzial',
  aktien: '/aktien',
  watchlist: '/aktien',
  aktie: '/aktien',
  analyse: '/analyse',
  matrix: '/analyse',
  haeufig: '/analyse',
  raster: '/analyse',
  vergleich: '/analyse',
  regel: '/analyse',
  pilot: '/pilot',
};

/** Unterreiter je Bereich (oberhalb der Ansicht). */
const SUBNAV: Record<string, { path: string; label: string }[]> = {
  '/rendite': [
    { path: '/rendite', label: 'Rendite 1–90' },
    { path: '/bericht', label: 'Bericht 1–30' },
    { path: '/depots', label: 'Depots' },
    { path: '/ranking', label: 'Gleichmäßig + Rendite' },
    { path: '/sieger', label: 'Sieger' },
  ],
  '/aktien': [
    { path: '/aktien', label: 'Alle Aktien' },
    { path: '/watchlist', label: 'Watchlist' },
  ],
  '/potenzial': [
    { path: '/potenzial', label: 'Kandidaten' },
    { path: '/muster', label: 'Muster und Volumen' },
  ],
  '/pilot': [
    { path: '/pilot', label: 'Übersicht' },
    { path: '/pilot/regeln', label: 'Regeln' },
    { path: '/pilot/chronik', label: 'Chronik' },
  ],
};

/* Menü ☰ (ab 1.15 gestrafft, Simons Wahl „übersichtlicher“): oben die Ansichten, die man oft braucht, darunter die App
 * selbst. „Kandidaten mit Potenzial“ und „Analyse-Werkzeuge“ stehen nur noch unten in der Leiste (Potenzial, Analyse). */
const MORE: { path: string; label: string; group: 'ansicht' | 'app'; locked?: boolean }[] = [
  { path: '/aktualisieren', label: 'Jetzt aktualisieren', group: 'ansicht' },
  { path: '/top', label: 'Top nach Zahlen', group: 'ansicht' },
  { path: '/bericht', label: 'Bericht 1–30 Tage', group: 'ansicht' },
  { path: '/depots', label: 'Musterdepots', group: 'ansicht' },
  { path: '/watchlist', label: 'Watchlist', group: 'ansicht' },
  { path: '/hilfe', label: 'Hilfe und Begriffe', group: 'app', locked: true },
  { path: '/status', label: 'Datenstand & Betrieb', group: 'app' },
  { path: '/kursabgleich', label: 'Kursabgleich mit den Börsen', group: 'app' },
  { path: '/methodik', label: 'So wird gerechnet', group: 'app' },
  { path: '/einstellungen', label: 'Einstellungen', group: 'app' },
  { path: '/installieren', label: 'Auf dem Startbildschirm installieren', group: 'app', locked: true },
];

/** Seiten ohne Datenstand und ohne Passphrase (reiner Text) – ab 1.16 auch vor dem Entsperren erreichbar. */
const STATIC_PAGES = new Set(['hilfe', 'installieren']);

const TITLES: Record<string, [string, string]> = {
  '': ['Heute', 'TR-Aktienvergleich'],
  top: ['Rangfolge', 'Top nach Zahlen: Rangfolge nach fester Regel'],
  potenzial: ['Potenzial', 'Kandidaten mit Potenzial'],
  analyse: ['Analyse', 'Analyse-Werkzeuge'],
  rendite: ['Rendite 1–90', 'Höchste Kursrendite 1–90 Tage'],
  ranking: ['Ranking', 'Ranking nach Gewichtung'],
  matrix: ['Matrix A/B', 'Gruppenvergleich: Matrix, Liste und Häufigkeit'],
  sieger: ['Sieger', 'Sieger nach Zeitraum'],
  bericht: ['Bericht 1–30', 'Bericht 1–30 Tage: Rendite und Gleichmäßigkeit'],
  depots: ['Depots', 'Musterdepots: Depotrendite und Beiträge'],
  vergleich: ['Gewichtungen', 'Gewichtungen vergleichen'],
  aktien: ['Alle Aktien', 'Alle Aktien und Abdeckung'],
  haeufig: ['Häufigste', 'Häufigste Aktien'],
  raster: ['Chart-Raster', 'Chart-Raster'],
  aktie: ['Aktie', 'Aktie im Detail'],
  watchlist: ['Watchlist', 'Watchlist'],
  status: ['Datenstand', 'Datenstand und Betrieb'],
  kursabgleich: ['Kursabgleich', 'Kursabgleich mit den Börsen'],
  aktualisieren: ['Aktualisieren', 'Daten jetzt aktualisieren'],
  regel: ['Umschichten', 'Umschichtungs-Regel'],
  methodik: ['Methodik', 'So wird gerechnet'],
  einstellungen: ['Einstellungen', 'Einstellungen'],
  installieren: ['Installieren', 'Auf dem Startbildschirm installieren'],
  hilfe: ['Hilfe', 'Hilfe und Begriffe'],
  pilot: ['Autopilot', 'Autopilot – Spielgeld-Robo'],
  muster: ['Muster', 'Muster und Volumen: Vor-Ausbruch, Seitwärtsbasis, Volumensprung'],
};

/** [kurzer Titel für die App-Leiste, vollständiger Titel für Fenster und Screenreader] */
function titleFor(route: Route): [string, string] {
  return TITLES[route.segments[0] ?? ''] ?? ['TR-Vergleich', 'TR-Aktienvergleich'];
}

function StandChip() {
  const { active, offline, status, isDemo } = useApp();
  if (!active) return null;
  const intraday = isIntraday(active);
  const older = isOlderStand(status, active.snapshot_id);
  const label = intraday
    ? `Zwischenstand vom ${f.isoDate(active.cutoff_session_date)}, Kurse bis ${berlinClock(active.kurse_bis_utc)}, vorläufig`
    : isDemo
      ? `DEMO-Stand ${f.isoDate(active.cutoff_session_date)}, synthetische Testdaten`
      : `Kursstand ${f.isoDate(active.cutoff_session_date)}`;
  return (
    <button type="button" className={`stand-chip${intraday ? ' stand-intraday' : ''}`} onClick={() => navigate('/status')} aria-label={`${label}. Details zum Datenstand öffnen`}>
      <span className="stand-date">
        {/* DEMO steht schon in der Beschriftung: das Kennzeichen daneben entfällt auf dem Handy aus Platzgründen, das Datum darf
            dort nie wie ein echter Kursstand aussehen (Gesamtauftrag 31.10.2026, Abschnitt 4.2) */}
        <small>{intraday ? 'Zwischenstand' : isDemo ? 'DEMO-Stand' : 'Kursstand'}</small>
        {intraday ? `${f.isoDate(active.cutoff_session_date).slice(0, 6)} ${berlinClock(active.kurse_bis_utc).replace(' Uhr', '')}` : f.isoDate(active.cutoff_session_date)}
      </span>
      {isDemo ? <span className="badge badge-demo">DEMO</span> : null}
      {!intraday && active.completeness === 'teilstand' ? <span className="badge badge-warn">Teilstand</span> : null}
      {older ? <span className="badge">älterer Stand</span> : null}
      {offline ? <span className="badge badge-warn">offline</span> : null}
    </button>
  );
}

function Banners({ swUpdate, onUpdate, route }: { swUpdate: boolean; onUpdate: () => void; route: Route }) {
  const { isDemo, newerId, reload, status, offline, active, manifest, updateWait, updateResult, clearUpdateResult, switchSnapshot, keyNotStored } = useApp();
  const out: ReactNode[] = [];
  const onUpdatePage = route.segments[0] === 'aktualisieren';
  const onStatusPage = route.segments[0] === 'status';
  const intradayStatus = status?.zwischenstand ?? null;
  // Hinweise als schmale Zeile – auch auf der Startseite, damit dort die Top 3 oben stehen (ab 1.11);
  // die ausführliche Erklärung des Zwischenstands steht im Kopf der Startseite und unter „Datenstand“.
  if (isDemo) {
    out.push(
      <Notice key="demo" tone="demo" compact>
        <p>
          <strong>DEMO – synthetische Testdaten</strong>, keine echten Kurse{PREVIEW ? '; Export, Drucken und Installation erst in der eingerichteten App' : ''}
        </p>
      </Notice>,
    );
  }
  if (active && isIntraday(active) && manifest?.snapshot_id === active.snapshot_id && !onStatusPage) {
    const officialId = manifest.zwischenstand?.offizieller_stand ?? status?.latest_official_snapshot_id ?? null;
    const officialDay = manifest.zwischenstand?.offizieller_stichtag ?? null;
    // Ab 1.12.1: der Knopf nennt, was er zeigt („Schlusskurse 13.10.“) – „Offiziell“ war missverständlich
    out.push(
      <Notice
        key="intraday"
        tone="info"
        compact
        actions={
          officialId ? (
            <button
              type="button"
              className="btn"
              aria-label={`Stand mit den Schlusskursen vom ${officialDay ? f.isoDate(officialDay) : 'letzten Börsentag'} anzeigen`}
              onClick={() => switchSnapshot(officialId)}
            >
              {closeLabel(officialDay)}
            </button>
          ) : null
        }
      >
        <p>
          <strong>Zwischenstand</strong> – vorläufige Kurse vom {f.isoDate(active.cutoff_session_date).slice(0, 6)} bis {berlinClock(active.kurse_bis_utc)}
        </p>
      </Notice>,
    );
  } else if (active && !isIntraday(active) && intradayStatus && newerId !== intradayStatus.snapshot_id && !onStatusPage) {
    out.push(
      <Notice
        key="intraday-available"
        tone="info"
        compact
        actions={
          <button type="button" className="btn btn-primary" aria-label="Zwischenstand anzeigen" onClick={reload}>
            Anzeigen
          </button>
        }
      >
        <p>
          <strong>Zwischenstand</strong> vom {f.isoDate(intradayStatus.stichtag).slice(0, 6)} verfügbar (Kurse bis {berlinClock(intradayStatus.kurse_bis_utc)})
        </p>
      </Notice>,
    );
  }
  if (keyNotStored) {
    out.push(
      <Notice key="key-not-stored" tone="warn" title="Passphrase nicht gespeichert">
        <p>Die App ist entsperrt, konnte den Schlüssel auf diesem Gerät aber nicht speichern – zum Beispiel im Inkognito-Modus. Beim nächsten Öffnen fragt sie wieder nach der Passphrase.</p>
      </Notice>,
    );
  }
  if (offline && active) {
    out.push(
      <Notice key="offline" tone="warn" title="Offline – gespeicherter Stand">
        <p>Angezeigt wird der auf diesem Gerät gespeicherte Stand vom {f.isoDate(active.cutoff_session_date)}. Nicht gespeicherte Details sind offline nicht verfügbar.</p>
      </Notice>,
    );
  }
  const age = f.ageHours(status?.last_successful_check_utc ?? status?.generated_at_utc);
  if (status && !offline && age !== null && age > (status.heartbeat_max_age_hours ?? 30)) {
    out.push(
      <Notice key="stale" tone="warn" title="Keine aktuelle Prüfung">
        <p>Der tägliche Lauf hat sich zuletzt {f.relativeAge(status.last_successful_check_utc ?? status.generated_at_utc)} erfolgreich gemeldet. Angezeigt wird der letzte veröffentlichte Stand. Neu starten kannst du ihn unter ☰ → Jetzt aktualisieren.</p>
      </Notice>,
    );
  }
  if (updateResult && !onUpdatePage) {
    const text = outcomeText(updateResult);
    const fresh = updateResult.outcome === 'neuer_stand';
    out.push(
      <Notice
        key="update-result"
        tone={fresh ? 'info' : 'warn'}
        title={text.title}
        actions={
          <>
            {fresh ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  clearUpdateResult();
                  reload();
                }}
              >
                Neuen Stand anzeigen
              </button>
            ) : (
              <button type="button" className="btn" onClick={() => navigate('/aktualisieren')}>
                Details
              </button>
            )}
            <button type="button" className="btn btn-quiet" onClick={clearUpdateResult}>
              Ausblenden
            </button>
          </>
        }
      >
        <p>{text.text}</p>
      </Notice>,
    );
  } else if (updateWait && !onUpdatePage) {
    out.push(
      <Notice key="update-wait" tone="info" title="Aktualisierung angefordert" actions={<button type="button" className="btn" onClick={() => navigate('/aktualisieren')}>Details</button>}>
        <p>Die App schaut alle 15 Sekunden nach, ob der Lauf fertig ist.</p>
      </Notice>,
    );
  }
  if (newerId && !(updateResult?.outcome === 'neuer_stand')) {
    const intradayNew = intradayStatus?.snapshot_id === newerId;
    out.push(
      <Notice
        key="newer"
        tone="info"
        title={intradayNew ? `Zwischenstand verfügbar (Kurse bis ${berlinClock(intradayStatus?.kurse_bis_utc)})` : 'Neuer Datenstand verfügbar'}
        actions={
          <button type="button" className="btn btn-primary" onClick={reload}>
            {intradayNew ? 'Zwischenstand anzeigen' : 'Neuen Stand anzeigen'}
          </button>
        }
      >
        <p>{intradayNew ? 'Vorläufige Ranglisten mit aktuellen Kursen. ' : ''}Die aktuelle Liste bleibt unverändert, bis du wechselst.</p>
      </Notice>,
    );
  }
  if (swUpdate) {
    out.push(
      <Notice key="sw" tone="info" title="Neue App-Version verfügbar" actions={<button type="button" className="btn btn-primary" onClick={onUpdate}>Aktualisieren</button>}>
        <p>Watchlist und Einstellungen bleiben erhalten.</p>
      </Notice>,
    );
  }
  return out.length ? <div className="banners">{out}</div> : null;
}

function MoreSheet({ open, onClose, locked }: { open: boolean; onClose: () => void; locked: boolean }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!open) return;
    const first = ref.current?.querySelector('a, button') as HTMLElement | null;
    first?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label="Weitere Ansichten" ref={ref} onClick={(e: Event) => e.stopPropagation()}>
        <div className="sheet-head">
          <span>Weitere Ansichten</span>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Menü schließen">
            <IconClose />
          </button>
        </div>
        {(['ansicht', 'app'] as const).map((group) => (
          <ul key={group} className={`sheet-list${group === 'app' ? ' sheet-list-app' : ''}`}>
            {MORE.filter((item) => item.group === group && !(PREVIEW && item.path === '/installieren') && (!locked || item.locked)).map((item) => (
              <li key={item.path}>
                <a href={`#${item.path}`} onClick={onClose}>
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        ))}
      </div>
    </div>
  );
}

/** Unterreiter im Bereich Pilot: Regeldetails gehören zu „Regeln“, Depotdetails zur Übersicht. */
function pilotSubActive(route: Route): string {
  const sub = route.segments[1] ?? '';
  if (sub === 'regeln' || sub === 'regel' || sub === 'neu') return '/pilot/regeln';
  if (sub === 'chronik') return '/pilot/chronik';
  return '/pilot';
}

/** Unterreiter eines Bereichs; der aktive Reiter wird in die Mitte gescrollt (Handy). */
function SubNav({ items, active }: { items: { path: string; label: string }[]; active: string }) {
  const ref = useRef<HTMLElement | null>(null);
  useEffect(() => centerActive(ref.current), [active]);
  return (
    <nav className="subnav" aria-label="Unterbereiche" ref={ref}>
      {items.map((item) => (
        <a key={item.path} href={`#${item.path}`} className={active === item.path ? 'is-active' : ''} aria-current={active === item.path ? 'page' : undefined}>
          {item.label}
        </a>
      ))}
    </nav>
  );
}

function Screen({ route }: { route: Route }) {
  const first = route.segments[0] ?? '';
  switch (first) {
    case '':
      return <StartView />;
    case 'rendite':
      return route.segments[1] === 'liste' ? <ReturnListView route={route} /> : <ReturnRankingsView route={route} />;
    case 'ranking':
      return <RankingView route={route} />;
    case 'bericht':
      return <ReportView route={route} />;
    case 'top':
      return <TopView route={route} />;
    case 'depots':
      return <DepotsView route={route} />;
    case 'potenzial':
      return <PotentialView route={route} />;
    case 'analyse':
      return <AnalyseView />;
    case 'matrix':
      return <MatrixView route={route} />;
    case 'vergleich':
      return <WeightCompareView route={route} />;
    case 'aktien':
      return <CoverageView route={route} />;
    case 'haeufig':
      if (route.segments[1] === 'erweitert') return <FrequencyView route={route} />;
      return route.segments[1] ? <FrequencyMatrixView route={route} isin={route.segments[1]} /> : <GroupFrequencyView route={route} />;
    case 'sieger':
      return <WinnersView route={route} />;
    case 'raster':
      return <GridView route={route} />;
    case 'aktie':
      return <DetailView route={route} isin={route.segments[1] ?? ''} />;
    case 'watchlist':
      return <WatchlistView route={route} />;
    case 'regel':
      return <RotationView route={route} />;
    case 'status':
      return <StatusView />;
    case 'kursabgleich':
      return <CorrectionsView />;
    case 'methodik':
      return <MethodView />;
    case 'einstellungen':
      return <SettingsView />;
    case 'installieren':
      return <InstallView />;
    case 'hilfe':
      return <HelpView route={route} />;
    case 'pilot':
      return <PilotView route={route} />;
    case 'muster':
      return <MusterView route={route} />;
    default:
      return (
        <Notice
          tone="warn"
          title="Seite nicht gefunden"
          actions={
            <>
              <a className="btn btn-primary" href="#/">
                Zur Startseite
              </a>
              <a className="btn" href="#/hilfe">
                Hilfe öffnen
              </a>
            </>
          }
        >
          <p>Diese Adresse gibt es in der App nicht. Vielleicht wurde ein Link falsch kopiert. Über die Leiste unten erreichst du alle Bereiche.</p>
        </Notice>
      );
  }
}

/** Bildschirmtastatur (ab 1.17): Verkleinert der Browser beim Tippen die Seite (Tastatur schiebt alles nach oben),
 * steht ``data-tastatur="offen"`` am Dokument – die Leiste unten blendet sich dann aus (styles.css), damit sie weder
 * Feld noch Knopf verdeckt. Browser, die die Tastatur über die Seite legen (Chrome ab Version 108), verkleinern die
 * Seite nicht; dort bleibt die Leiste hinter der Tastatur und es ändert sich nichts.
 *
 * Geprüft wird erst kurz nach Fokuswechsel und Größenänderung: Tippt man bei offener Tastatur auf einen Knopf, darf
 * die Leiste nicht mitten im Tippen wieder erscheinen und den Knopf verdecken (sonst landet der Tipp auf der Leiste).
 * Kontrollkästchen, Schieberegler und Knöpfe öffnen keine Tastatur und zählen nicht. */
const TEXT_INPUT = 'input:not([type=checkbox]):not([type=radio]):not([type=range]):not([type=button]):not([type=submit]), textarea, select';
/** So viel niedriger als ohne Tastatur muss die Seite sein (Anteil der Höhe), damit sie als „Tastatur offen“ gilt. */
const KEYBOARD_SHRINK = 0.75;
const KEYBOARD_SETTLE_MS = 350;

function useKeyboardMark() {
  useEffect(() => {
    const root = document.documentElement;
    let width = window.innerWidth;
    let tall = window.innerHeight; // Höhe ohne Tastatur bei dieser Breite
    let timer: number | undefined;
    const typing = () => {
      const active = document.activeElement;
      return active instanceof Element && active.matches(TEXT_INPUT);
    };
    const update = () => {
      if (window.innerWidth !== width) {
        // gedreht oder Fenster geändert: neue Grundhöhe
        width = window.innerWidth;
        tall = window.innerHeight;
      }
      if (!typing()) tall = Math.max(tall, window.innerHeight);
      if (typing() && window.innerHeight < tall * KEYBOARD_SHRINK) root.dataset.tastatur = 'offen';
      else delete root.dataset.tastatur;
    };
    const later = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(update, KEYBOARD_SETTLE_MS);
    };
    window.addEventListener('resize', later);
    document.addEventListener('focusin', later);
    document.addEventListener('focusout', later);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('resize', later);
      document.removeEventListener('focusin', later);
      document.removeEventListener('focusout', later);
      delete root.dataset.tastatur;
    };
  }, []);
}

export function App({ swUpdate, onUpdate }: { swUpdate: boolean; onUpdate: () => void }) {
  const route = useRoute();
  const app = useApp();
  const [menu, setMenu] = useState(false);
  const mainRef = useRef<HTMLElement | null>(null);
  const isRoot = route.segments.length === 0;
  const navActive = GROUP[route.segments[0] ?? ''] ?? '/' + (route.segments[0] ?? '');
  const subnav = SUBNAV[navActive] && route.segments[0] !== 'aktie' ? SUBNAV[navActive] : null;
  const subActive = route.segments[0] === 'pilot' ? pilotSubActive(route) : '/' + (route.segments[0] ?? '');

  useScrollMemory(route.path);
  useKeyboardMark();
  useEffect(() => {
    const full = titleFor(route)[1];
    document.title = full === 'TR-Aktienvergleich' ? full : `${full} – TR-Aktienvergleich`;
    mainRef.current?.focus({ preventScroll: true });
  }, [route.path]);

  let content: ReactNode;
  const locked = app.phase === 'schluessel';
  if (STATIC_PAGES.has(route.segments[0] ?? '')) {
    content = (
      <ViewBoundary resetKey={route.path}>
        <Screen route={route} />
      </ViewBoundary>
    );
  } else if (route.segments[0] === 'aktualisieren' && app.phase !== 'laden') {
    // Aktualisieren geht auch ohne Datenstand und ohne Schlüssel (liest nur status.json)
    content = <UpdateView />;
  } else if (app.phase === 'laden' || (app.phase === 'bereit' && (!app.manifest || !app.instruments))) {
    content = <Loading label="Datenstand wird geladen" height={240} />;
  } else if (app.phase === 'schluessel') {
    content = <UnlockView />;
  } else if (app.phase === 'kein_stand') {
    content = (
      <>
      <Notice tone="info" title="Noch kein Datenstand veröffentlicht">
        <p>Die App ist eingerichtet, aber der tägliche Serverlauf hat noch keine Rangliste veröffentlicht. Es werden keine Beispielgewinner angezeigt.</p>
        <p>{scheduleNote(app.status)} Du kannst ihn auch jetzt selbst starten.</p>
        {app.status?.last_run ? (
          <p>
            Letzter Lauf ({f.berlinTime(app.status.last_run.finished_at_utc ?? app.status.last_run.started_at_utc)}): {f.runStatus(app.status.last_run.status)}.
            {app.status.last_run.message ? <> Grund: {app.status.last_run.message}</> : null}
          </p>
        ) : null}
        <div className="toolbar">
          <a className="btn btn-primary" href="#/aktualisieren">
            Jetzt aktualisieren
          </a>
        </div>
      </Notice>
      {app.crypto?.enabled ? (
        app.hasKey ? (
          <Notice tone="info" title="Passphrase gespeichert">
            <p>Die Passphrase ist geprüft und auf diesem Gerät gespeichert. Sobald der erste Datenstand veröffentlicht ist, öffnen sich die Ranglisten ohne weitere Eingabe.</p>
          </Notice>
        ) : (
          <UnlockView early />
        )
      ) : null}
      </>
    );
  } else if (app.phase === 'offline_ohne_daten') {
    content = (
      <Notice
        tone="warn"
        title="Keine Internetverbindung"
        actions={
          <button type="button" className="btn btn-primary" onClick={app.reload}>
            Erneut versuchen
          </button>
        }
      >
        <p>Beim ersten Öffnen braucht die App eine Internetverbindung. Danach bleibt der zuletzt geladene Stand auch ohne Netz lesbar.</p>
        <p>Verbinde das Handy mit dem Internet (WLAN oder mobile Daten) und tippe auf „Erneut versuchen“.</p>
      </Notice>
    );
  } else if (app.phase === 'fehler') {
    const info = describeError(app.error);
    content = (
      <Notice
        tone={info.kind === 'offline' ? 'warn' : 'error'}
        title={info.title}
        actions={
          <>
            <button type="button" className="btn btn-primary" onClick={app.reload}>
              Erneut versuchen
            </button>
            <a className="btn" href="#/hilfe">
              Hilfe öffnen
            </a>
          </>
        }
      >
        <p>{info.text}</p>
        {info.detail ? <p className="error-detail">Technische Angabe: {info.detail}</p> : null}
      </Notice>
    );
  } else {
    content = (
      <ViewBoundary resetKey={route.path}>
        {subnav ? <SubNav items={subnav} active={subActive} /> : null}
        <Screen route={route} />
      </ViewBoundary>
    );
  }

  return (
    <div className="shell">
      <a href="#hauptinhalt" className="skip-link" onClick={(e: Event) => { e.preventDefault(); mainRef.current?.focus(); }}>
        Zum Inhalt springen
      </a>
      <header className="appbar">
        {isRoot ? (
          <span className="appbar-mark" aria-hidden="true">
            <IconLadder />
          </span>
        ) : (
          <button type="button" className="icon-btn" onClick={() => (history.length > 1 ? history.back() : navigate('/'))} aria-label="Zurück">
            <IconBack />
          </button>
        )}
        <h1 className="appbar-title" aria-label={locked && !STATIC_PAGES.has(route.segments[0] ?? '') ? 'TR-Aktienvergleich entsperren' : titleFor(route)[1]}>
          {locked && !STATIC_PAGES.has(route.segments[0] ?? '') ? 'TR-Vergleich' : titleFor(route)[0]}
        </h1>
        <StandChip />
        <button type="button" className="icon-btn" onClick={() => setMenu(true)} aria-label="Weitere Ansichten" aria-haspopup="dialog">
          <IconMore />
        </button>
      </header>
      <Banners swUpdate={swUpdate} onUpdate={onUpdate} route={route} />
      <main id="hauptinhalt" ref={mainRef} tabIndex={-1} className="main">
        {content}
      </main>
      <nav className="bottomnav" aria-label="Hauptnavigation" hidden={locked}>
        {NAV.map((item) => {
          const Icon = item.icon;
          const current = navActive === item.path;
          return (
            <a key={item.path} href={`#${item.path}`} className={current ? 'is-active' : ''} aria-current={current ? 'page' : undefined}>
              <Icon />
              <span>{item.label}</span>
            </a>
          );
        })}
      </nav>
      <MoreSheet open={menu} onClose={() => setMenu(false)} locked={locked} />
    </div>
  );
}
