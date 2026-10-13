import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { IconBack, IconClose, IconFrequency, IconGrid, IconLadder, IconMatrix, IconMore, IconRanking, IconStart } from './components/icons';
import { ViewBoundary } from './components/boundary';
import { Loading, Notice } from './components/ui';
import * as f from './lib/format';
import { navigate, useRoute, type Route } from './lib/router';
import { useScrollMemory } from './lib/scroll';
import { useApp } from './state/AppState';
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
import { WatchlistView } from './views/WatchlistView';
import { WeightCompareView } from './views/WeightCompareView';
import { WinnersView } from './views/WinnersView';
import { PREVIEW } from './lib/env';

const NAV = [
  { path: '/', label: 'Start', icon: IconStart },
  { path: '/rendite', label: 'Rendite', icon: IconLadder },
  { path: '/ranking', label: 'Ranking', icon: IconRanking },
  { path: '/matrix', label: 'Matrix', icon: IconMatrix },
  { path: '/haeufig', label: 'Häufig', icon: IconFrequency },
  { path: '/raster', label: 'Raster', icon: IconGrid },
];

const MORE = [
  { path: '/sieger', label: 'Sieger nach Zeitraum (7–90 Tage)' },
  { path: '/aktualisieren', label: 'Jetzt aktualisieren' },
  { path: '/regel', label: 'Umschichtungs-Regel' },
  { path: '/vergleich', label: 'Gewichtungen vergleichen' },
  { path: '/aktien', label: 'Alle Aktien & Abdeckung' },
  { path: '/watchlist', label: 'Watchlist' },
  { path: '/status', label: 'Datenstand & Betrieb' },
  { path: '/methodik', label: 'So wird gerechnet' },
  { path: '/einstellungen', label: 'Einstellungen' },
  { path: '/installieren', label: 'Auf dem Startbildschirm installieren' },
];

const TITLES: Record<string, [string, string]> = {
  '': ['Heute', 'TR-Aktienvergleich'],
  rendite: ['Rendite 1–90', 'Höchste Kursrendite 1–90 Tage'],
  ranking: ['Ranking', 'Ranking nach Gewichtung'],
  matrix: ['Matrix A/B', 'Gruppenvergleich: Matrix, Liste und Häufigkeit'],
  sieger: ['Sieger', 'Sieger nach Zeitraum'],
  vergleich: ['Gewichtungen', 'Gewichtungen vergleichen'],
  aktien: ['Alle Aktien', 'Alle Aktien und Abdeckung'],
  haeufig: ['Häufigste', 'Häufigste Aktien'],
  raster: ['Chart-Raster', 'Chart-Raster'],
  aktie: ['Aktie', 'Aktie im Detail'],
  watchlist: ['Watchlist', 'Watchlist'],
  status: ['Datenstand', 'Datenstand und Betrieb'],
  aktualisieren: ['Aktualisieren', 'Daten jetzt aktualisieren'],
  regel: ['Umschichten', 'Umschichtungs-Regel'],
  methodik: ['Methodik', 'So wird gerechnet'],
  einstellungen: ['Einstellungen', 'Einstellungen'],
  installieren: ['Installieren', 'Auf dem Startbildschirm installieren'],
};

/** [kurzer Titel für die App-Leiste, vollständiger Titel für Fenster und Screenreader] */
function titleFor(route: Route): [string, string] {
  return TITLES[route.segments[0] ?? ''] ?? ['TR-Vergleich', 'TR-Aktienvergleich'];
}

function StandChip() {
  const { active, offline, status, isDemo } = useApp();
  if (!active) return null;
  const isLatest = status?.latest_snapshot_id === active.snapshot_id;
  return (
    <button type="button" className="stand-chip" onClick={() => navigate('/status')} aria-label={`Kursstand ${f.isoDate(active.cutoff_session_date)}. Details zum Datenstand öffnen`}>
      <span className="stand-date">
        <small>Kursstand</small>
        {f.isoDate(active.cutoff_session_date)}
      </span>
      {isDemo ? <span className="badge badge-demo">DEMO</span> : null}
      {active.completeness === 'teilstand' ? <span className="badge badge-warn">Teilstand</span> : null}
      {!isLatest ? <span className="badge">älterer Stand</span> : null}
      {offline ? <span className="badge badge-warn">offline</span> : null}
    </button>
  );
}

function Banners({ swUpdate, onUpdate, route }: { swUpdate: boolean; onUpdate: () => void; route: Route }) {
  const { isDemo, newerId, reload, status, offline, active, updateWait, updateResult, clearUpdateResult } = useApp();
  const out: ReactNode[] = [];
  const onUpdatePage = route.segments[0] === 'aktualisieren';
  if (isDemo) {
    out.push(
      <Notice key="demo" tone="demo" title="DEMO – synthetische Testdaten">
        <p>Alle Namen beginnen mit „DEMO“, alle ISINs mit „ZZ“. Es sind keine echten Kurse und keine echten Unternehmen.</p>
        {PREVIEW ? <p>Vorschau in Claude: Export, Drucken, Offline-Speicher und Installation gibt es erst in der eingerichteten App.</p> : null}
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
        <p>Der tägliche Lauf hat sich seit {f.relativeAge(status.last_successful_check_utc ?? status.generated_at_utc)} nicht erfolgreich gemeldet. Angezeigt wird der letzte veröffentlichte Stand.</p>
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
        <p>Die App schaut jede Minute nach, ob der Lauf fertig ist.</p>
      </Notice>,
    );
  }
  if (newerId && !(updateResult?.outcome === 'neuer_stand')) {
    out.push(
      <Notice key="newer" tone="info" title="Neuer Datenstand verfügbar" actions={<button type="button" className="btn btn-primary" onClick={reload}>Neuen Stand anzeigen</button>}>
        <p>Die aktuelle Liste bleibt unverändert, bis du wechselst.</p>
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

function MoreSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
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
        <ul className="sheet-list">
          {MORE.filter((item) => !(PREVIEW && item.path === '/installieren')).map((item) => (
            <li key={item.path}>
              <a href={`#${item.path}`} onClick={onClose}>
                {item.label}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
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
    case 'methodik':
      return <MethodView />;
    case 'einstellungen':
      return <SettingsView />;
    case 'installieren':
      return <InstallView />;
    default:
      return <Notice tone="warn" title="Seite nicht gefunden"><p>Diese Adresse gibt es in der App nicht.</p></Notice>;
  }
}

export function App({ swUpdate, onUpdate }: { swUpdate: boolean; onUpdate: () => void }) {
  const route = useRoute();
  const app = useApp();
  const [menu, setMenu] = useState(false);
  const mainRef = useRef<HTMLElement | null>(null);
  const isRoot = route.segments.length === 0;
  const navActive = '/' + (route.segments[0] ?? '');

  useScrollMemory(route.path);
  useEffect(() => {
    document.title = `${titleFor(route)[1]} – TR-Aktienvergleich`;
    mainRef.current?.focus({ preventScroll: true });
  }, [route.path]);

  let content: ReactNode;
  if (route.segments[0] === 'aktualisieren' && app.phase !== 'laden') {
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
        <p>Nächster geplanter Lauf: täglich {app.status?.schedule?.uhrzeit ?? '07:00'} Uhr ({app.status?.schedule?.zeitzone ?? 'Europe/Berlin'}). Du kannst ihn auch jetzt selbst starten.</p>
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
          <Notice tone="info" title="Zugangsschlüssel gespeichert">
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
      <Notice tone="warn" title="Offline und noch kein gespeicherter Stand">
        <p>Beim ersten Öffnen ist eine Internetverbindung nötig. Danach bleibt der zuletzt geladene Stand offline lesbar.</p>
        <button type="button" className="btn btn-primary" onClick={app.reload}>Erneut versuchen</button>
      </Notice>
    );
  } else if (app.phase === 'fehler') {
    content = (
      <Notice tone="error" title="Daten konnten nicht geladen werden">
        <p>{app.error}</p>
        <button type="button" className="btn btn-primary" onClick={app.reload}>Erneut versuchen</button>
      </Notice>
    );
  } else {
    content = (
      <ViewBoundary resetKey={route.path}>
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
        <h1 className="appbar-title" aria-label={titleFor(route)[1]}>
          {titleFor(route)[0]}
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
      <nav className="bottomnav" aria-label="Hauptnavigation">
        {NAV.map((item) => {
          const Icon = item.icon;
          const current = navActive === item.path || (item.path === '/' && isRoot);
          return (
            <a key={item.path} href={`#${item.path}`} className={current ? 'is-active' : ''} aria-current={current ? 'page' : undefined}>
              <Icon />
              <span>{item.label}</span>
            </a>
          );
        })}
      </nav>
      <MoreSheet open={menu} onClose={() => setMenu(false)} />
    </div>
  );
}
