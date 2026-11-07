/* „Jetzt aktualisieren“ für einzelne Aktien und Eingänge an den Spielgeld-Robo (ab 1.21; ab 1.22 ohne Zugang in der App).
 *
 * Die App enthält keinen GitHub-Zugang – kein Token, auch nicht verschlüsselt. Sie verschlüsselt Anfragen und Eingänge mit
 * dem Datenschlüssel und bereitet sie als eine Zeile „<Kennung>.<verschlüsselt>“ vor; gestartet wird auf GitHub mit der
 * eigenen Anmeldung. Danach liest die App ohne Anmeldung (öffentliches Repository): den Lauf und die verschlüsselten
 * Lieferungen. Gelieferte Kurse bleiben so verschlüsselt gespeichert, wie sie ankommen. Ein Zugang, den eine frühere
 * Entwicklungsfassung gespeichert haben könnte, wird beim Öffnen der Datenbank gelöscht (``keystore``). */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import {
  DELIVERY_BRANCH,
  deliveryPath,
  eingabeZeile,
  errorFor,
  errorPath,
  MAX_EINGABE,
  newKennung,
  requestAad,
  requestPayload,
  stepLabel,
  valuesFor,
  WORKFLOW_KURSE,
  type UpdateJob,
  type UpdateScope,
} from '../lib/aktualisierung';
import { bytesToBase64, decodeJson, encodeJson, NeedKeyError } from '../lib/container';
import { errorText, GitHubError, PublicGitHub, validRepository } from '../lib/github';
import { allValues, deleteValue, putValue, STORE_LIEFERUNGEN } from '../lib/keystore';
import { coursesFromDelivery, mergeQuotes, quotesFromDelivery, type DayCourse, type Delivery, type LiveQuote } from '../lib/livekurse';
import { useApp } from './AppState';

const JOBS_KEY = 'tr-vergleich:aktualisierungen:v2';
const KEEP_MS = 2 * 24 * 3600_000;
/** so lange gilt eine Anfrage (der Server nimmt höchstens 20 Minuten alte Anfragen an) */
const START_MAX_MS = 20 * 60_000;
/** so lange darf ein gefundener Lauf ohne Ergebnis dauern */
const RUN_MAX_MS = 12 * 60_000;
/** Abstand der Abfragen, solange etwas läuft und die App sichtbar ist (ohne Anmeldung erlaubt GitHub 60 je Stunde) */
export const POLL_MS = 20_000;

export interface RequestOptions {
  label?: string;
  /** so viele der ISINs (vorne) sind gerade sichtbar und kommen zuerst */
  visible?: number;
  /** ISINs, für die zusätzlich der Tagesverlauf kommt (höchstens 3) */
  courses?: string[];
}

export interface UpdateStateValue {
  repo: string | null;
  jobs: UpdateJob[];
  /** Anfrage verschlüsseln und für den Start auf GitHub vorbereiten – oder ein Grund, warum es nicht geht. */
  request: (scope: UpdateScope, isins: string[], options?: RequestOptions) => Promise<UpdateJob | string>;
  /** Zeile zum Einfügen auf GitHub (nur im Speicher, solange die Anfrage gilt) */
  eingabeFor: (kennung: string) => string | null;
  /** GitHub wurde geöffnet – ab jetzt sucht die App den Lauf */
  markOpened: (kennung: string) => void;
  dismiss: (kennung: string) => void;
  quotes: ReadonlyMap<string, LiveQuote>;
  courses: ReadonlyMap<string, DayCourse>;
  /** gerade sichtbare Aktien (von der Ansicht gemeldet) – für „sichtbare zuerst“ */
  setVisible: (source: string, isins: string[]) => void;
  /** Spielgeld-Robo: Eingang verschlüsseln und als Zeile für den Workflow „Spielgeld-Eingang“ vorbereiten. */
  preparePilot: (art: PilotEingangArt, inhalt: Record<string, unknown>) => Promise<{ ok: boolean; text: string; kennung?: string; eingabe?: string }>;
  /** Ergebnis der Prüfung auf GitHub (null, solange es noch keins gibt). */
  readPilotResult: (kennung: string) => Promise<PilotEingangErgebnis | null>;
}

export type PilotEingangArt =
  | 'regel_testen'
  | 'regel_beenden'
  | 'pausieren'
  | 'fortsetzen'
  | 'offene_kaeufe_stornieren'
  | 'positionen_schliessen'
  | 'neuer_test'
  | 'pilot_einrichten'
  /** eine Strategie (ihr Forschungsdepot) einzeln schalten – Gesamtauftrag 31.10.2026, Abschnitt 17 */
  | 'strategie_pausieren'
  | 'strategie_fortsetzen'
  /** Depotparameter des Depot-Optimierers (Auftrag 18, Abschnitt 17) – dieselben Grenzen wie auf dem Server */
  | 'optimierer_einstellungen';

export interface PilotEingangErgebnis {
  kennung: string;
  status: 'angenommen' | 'abgelehnt';
  code: string;
  text: string;
  art: string | null;
  regel: string | null;
  geprueft_utc: string;
}

export const WORKFLOW_PILOT = 'spielgeld-eingang.yml';
export const WORKFLOW_LABOR = 'spielgeld-labor.yml';
export const PILOT_BRANCH = 'spielgeld-eingang';
const PILOT_MAX_TEXT = 60_000;
const KENNUNG_RE = /^k[0-9a-z]{6,8}-[0-9a-z]{16}$/;

const UpdateContext = createContext<UpdateStateValue | null>(null);

export function useUpdates(): UpdateStateValue {
  const value = useContext(UpdateContext);
  if (!value) throw new Error('UpdateState fehlt');
  return value;
}

/** Ansicht meldet ihre sichtbaren Aktien (Reihenfolge = Anzeige). */
export function useVisibleStocks(source: string, isins: string[]): void {
  const { setVisible } = useUpdates();
  const key = isins.join(',');
  useEffect(() => {
    setVisible(source, isins);
    return () => setVisible(source, []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, key, setVisible]);
}

interface StoredDelivery {
  bytes: Uint8Array;
  savedAt: number;
}

function loadJobs(): UpdateJob[] {
  try {
    const raw = localStorage.getItem(JOBS_KEY);
    const list = raw ? (JSON.parse(raw) as UpdateJob[]) : [];
    // Anfragen, deren Zeile nicht mehr im Speicher ist, lassen sich nach dem Neuladen nicht mehr starten
    return Array.isArray(list)
      ? list
          .filter((j) => j && typeof j.kennung === 'string' && Date.now() - j.requestedAt < KEEP_MS)
          .map((j) => (j.phase === 'start' && !j.openedAt ? { ...j, phase: 'fehler' as const, error: 'Nicht gestartet – bitte neu anfordern.', finishedAt: j.finishedAt ?? Date.now() } : j))
          .slice(0, 10)
      : [];
  } catch {
    return [];
  }
}

function saveJobs(jobs: UpdateJob[]): void {
  try {
    // ohne ISINs und ohne Zeile: die laufende Aktualisierung lässt sich nach dem Neuladen weiterverfolgen, ohne die Merkliste zu speichern
    localStorage.setItem(JOBS_KEY, JSON.stringify(jobs.slice(0, 10).map((j) => ({ ...j, isins: [] }))));
  } catch {
    /* privater Modus */
  }
}

function active(job: UpdateJob): boolean {
  return job.phase === 'start' || job.phase === 'wartet' || job.phase === 'laeuft' || job.phase === 'teil';
}

export function UpdateStateProvider({ children }: { children: ReactNode }) {
  const { status, dataKey, keyCanEncrypt, instruments, isinIndex } = useApp();
  const repo = validRepository(status?.aktualisieren?.repository) ? status!.aktualisieren!.repository : null;
  const [jobs, setJobsState] = useState<UpdateJob[]>(() => loadJobs());
  const jobsRef = useRef<UpdateJob[]>(jobs);
  const eingaben = useRef(new Map<string, string>());
  const [quotes, setQuotes] = useState<ReadonlyMap<string, LiveQuote>>(new Map());
  const [courses, setCourses] = useState<ReadonlyMap<string, DayCourse>>(new Map());
  const visibleRef = useRef(new Map<string, string[]>());
  const apiRef = useRef<PublicGitHub | null>(null);

  const api = useCallback((): PublicGitHub | null => {
    if (!repo) return null;
    if (!apiRef.current || apiRef.current.repo !== repo) apiRef.current = new PublicGitHub(repo);
    return apiRef.current;
  }, [repo]);

  const setJobs = useCallback((update: (jobs: UpdateJob[]) => UpdateJob[]) => {
    const next = update(jobsRef.current);
    jobsRef.current = next;
    saveJobs(next);
    setJobsState(next);
  }, []);

  const patchJob = useCallback(
    (kennung: string, changes: Partial<UpdateJob>) => setJobs((list) => list.map((j) => (j.kennung === kennung ? { ...j, ...changes } : j))),
    [setJobs],
  );

  // Gespeicherte Lieferungen der letzten zwei Tage lesen
  useEffect(() => {
    if (!dataKey) {
      setQuotes(new Map());
      setCourses(new Map());
      return;
    }
    let cancelled = false;
    (async () => {
      const items = await allValues<StoredDelivery>(STORE_LIEFERUNGEN);
      let quoteMap = new Map<string, LiveQuote>();
      const courseMap = new Map<string, DayCourse>();
      for (const { id, value } of items) {
        if (!value?.bytes || Date.now() - value.savedAt > KEEP_MS) {
          await deleteValue(STORE_LIEFERUNGEN, id);
          continue;
        }
        try {
          const delivery = await decodeJson<Delivery>(value.bytes, dataKey, id);
          quoteMap = mergeQuotes(quoteMap, quotesFromDelivery(delivery));
          for (const course of coursesFromDelivery(delivery)) {
            const old = courseMap.get(course.isin);
            if (!old || course.fetchedAt >= old.fetchedAt) courseMap.set(course.isin, course);
          }
        } catch {
          await deleteValue(STORE_LIEFERUNGEN, id);
        }
      }
      if (cancelled) return;
      setQuotes(quoteMap);
      setCourses(courseMap);
    })();
    return () => {
      cancelled = true;
    };
  }, [dataKey]);

  const symbolOf = useCallback(
    (isin: string) => {
      const i = isinIndex.get(isin);
      return i !== undefined && instruments ? instruments.symbol[i] : null;
    },
    [instruments, isinIndex],
  );

  const request = useCallback(
    async (scope: UpdateScope, isins: string[], options: RequestOptions = {}): Promise<UpdateJob | string> => {
      if (!repo) return 'Das Repository ist unbekannt – „Jetzt aktualisieren“ gibt es nur in der eingerichteten App (GitHub Pages).';
      if (!dataKey || !keyCanEncrypt) return 'Zum Anfordern einmal die Passphrase eingeben (Einstellungen), damit die Anfrage verschlüsselt werden kann.';
      const { values } = valuesFor(isins, symbolOf);
      if (!values.length) return 'Für diese Aktien gibt es kein Kurssymbol – sie lassen sich nicht einzeln aktualisieren.';
      const now = Date.now();
      const kennung = newKennung(now);
      const payload = requestPayload(kennung, scope, values, options.visible ?? values.length, options.courses ?? [], now);
      const encrypted = await encodeJson(payload, dataKey, requestAad(kennung));
      const line = eingabeZeile(kennung, bytesToBase64(encrypted));
      if (line.length > MAX_EINGABE) return 'Zu viele Aktien auf einmal für GitHub – bitte weniger auswählen.';
      eingaben.current.set(kennung, line);
      const job: UpdateJob = {
        kennung,
        scope,
        label: options.label ?? scope,
        isins: payload.werte.map((v) => v.isin),
        requestedAt: now,
        openedAt: null,
        runId: null,
        runUrl: null,
        runStartedAt: null,
        phase: 'start',
        stepName: null,
        stepIndex: 0,
        stepCount: 0,
        partsReceived: 0,
        partsTotal: null,
        quotesReceived: 0,
        missing: 0,
        finishedAt: null,
        error: null,
        lastHead: null,
      };
      // eine neue Anfrage für dieselben Aktien ersetzt eine noch nicht gestartete
      setJobs((list) => [job, ...list.filter((j) => !(j.phase === 'start' && !j.openedAt && j.scope === scope))].slice(0, 10));
      return job;
    },
    [repo, dataKey, keyCanEncrypt, symbolOf, setJobs],
  );

  const eingabeFor = useCallback((kennung: string) => eingaben.current.get(kennung) ?? null, []);

  const markOpened = useCallback(
    (kennung: string) => {
      const job = jobsRef.current.find((j) => j.kennung === kennung);
      if (job && job.phase === 'start') patchJob(kennung, { openedAt: job.openedAt ?? Date.now() });
    },
    [patchJob],
  );

  const dismiss = useCallback(
    (kennung: string) => {
      eingaben.current.delete(kennung);
      setJobs((list) => list.filter((j) => j.kennung !== kennung));
    },
    [setJobs],
  );

  const applyDelivery = useCallback(
    async (path: string, bytes: Uint8Array): Promise<Delivery | null> => {
      if (!dataKey) throw new NeedKeyError();
      const delivery = await decodeJson<Delivery>(bytes, dataKey, path);
      await putValue(STORE_LIEFERUNGEN, path, { bytes, savedAt: Date.now() } satisfies StoredDelivery);
      setQuotes((map) => mergeQuotes(map, quotesFromDelivery(delivery)));
      setCourses((map) => {
        const next = new Map(map);
        for (const course of coursesFromDelivery(delivery)) next.set(course.isin, course);
        return next;
      });
      return delivery;
    },
    [dataKey],
  );

  // Fortschritt verfolgen: alle 20 Sekunden, solange etwas läuft und die App sichtbar ist – und sofort beim Zurückkehren
  const tick = useRef(0);
  useEffect(() => {
    let timer: number | undefined;
    let stopped = false;
    let busy = false;

    const follow = async (client: PublicGitHub, job: UpdateJob) => {
      const changes: Partial<UpdateJob> = {};
      // 1) Lauf zuordnen: der erste nach dem Öffnen von GitHub angelegte Lauf, der noch keiner anderen Anfrage gehört
      let runId = job.runId;
      if (runId === null && job.openedAt !== null) {
        const since = new Date(job.openedAt - 60_000).toISOString().replace(/\.\d{3}Z$/, 'Z');
        const runs = await client.recentRuns(WORKFLOW_KURSE, since);
        const taken = new Set(jobsRef.current.filter((j) => j.kennung !== job.kennung && j.runId !== null).map((j) => j.runId));
        const match = runs
          .filter((r) => !taken.has(r.id) && Date.parse(r.created_at) >= job.requestedAt - 5_000)
          .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))[0];
        if (match) {
          runId = match.id;
          Object.assign(changes, { runId, runUrl: match.html_url, phase: job.phase === 'start' ? ('wartet' as const) : job.phase });
        }
      }
      // 2) Lieferungen: nur bei einem neuen Stand des Lieferkanals nach weiteren Teilen sehen (die Kennung ordnet sie sicher zu)
      let received = job.partsReceived;
      let total = job.partsTotal;
      let quotesReceived = job.quotesReceived;
      let missing = job.missing;
      let head = job.lastHead ?? null;
      let errorCode: string | null = null;
      if (job.openedAt !== null && (runId !== null || tick.current % 2 === 0)) {
        const current = await client.branchHead(DELIVERY_BRANCH);
        if (current && current !== head) {
          head = current;
          while (total === null || received < total) {
            const path = deliveryPath(job.kennung, received + 1);
            const bytes = await client.file(path, current);
            if (!bytes) break;
            const delivery = await applyDelivery(path, bytes);
            if (!delivery) break;
            received += 1;
            total = delivery.teile;
            quotesReceived += delivery.kurse.length;
            missing += delivery.fehlend.length;
          }
          if (total === null || received < total) {
            const error = await client.file(errorPath(job.kennung), current);
            if (error) {
              try {
                errorCode = String((JSON.parse(new TextDecoder().decode(error)) as { grund?: string }).grund ?? 'unbekannt');
              } catch {
                errorCode = 'unbekannt';
              }
            }
          }
          changes.lastHead = head;
        }
      }
      if (received !== job.partsReceived) Object.assign(changes, { partsReceived: received, partsTotal: total, quotesReceived, missing, phase: 'teil' as const });
      if (total !== null && received >= total) {
        Object.assign(changes, { phase: 'fertig' as const, finishedAt: Date.now() });
      } else if (errorCode) {
        Object.assign(changes, { phase: 'fehler' as const, error: errorFor(errorCode), finishedAt: Date.now() });
      } else if (runId !== null) {
        // 3) Laufstatus und Schritt (sparsam: der Status jeden zweiten, die Schritte jeden dritten Durchgang)
        if (tick.current % 2 === 0 || job.runId === null) {
          const run = await client.run(runId);
          changes.runUrl = run.html_url;
          if ((run.status === 'in_progress' || run.status === 'completed') && job.runStartedAt === null) {
            changes.runStartedAt = Date.parse(run.run_started_at ?? run.created_at);
          }
          if ((run.status === 'in_progress' || run.status === 'completed') && (changes.phase ?? job.phase) === 'wartet') changes.phase = 'laeuft';
          if (tick.current % 3 === 0 || run.status === 'completed') {
            const steps = (await client.jobs(runId)).flatMap((j) => j.steps).filter((s) => !s.name.startsWith('Post ') && s.name !== 'Complete job');
            const now = steps.find((s) => s.status === 'in_progress') ?? [...steps].reverse().find((s) => s.status === 'completed');
            if (now) Object.assign(changes, { stepName: stepLabel(now.name), stepIndex: steps.indexOf(now) + 1, stepCount: steps.length });
          }
          if (run.status === 'completed' && run.conclusion !== 'success') {
            Object.assign(changes, {
              phase: 'fehler' as const,
              error:
                run.conclusion === 'cancelled'
                  ? 'Lauf abgebrochen – Einzelheiten auf GitHub.'
                  : 'Lauf fehlgeschlagen – meist war die eingefügte Zeile unvollständig. Bitte neu anfordern; Einzelheiten auf GitHub.',
              finishedAt: Date.now(),
            });
          } else if (run.status === 'completed' && Date.now() - Date.parse(run.updated_at) > 90_000 && received === 0) {
            Object.assign(changes, { phase: 'ohne_ergebnis' as const, error: 'Lauf beendet, aber keine Lieferung für diese Anfrage gefunden.', finishedAt: Date.now() });
          }
        }
      }
      // 4) Zeitgrenzen
      const phase = changes.phase ?? job.phase;
      if (phase === 'start' && Date.now() - job.requestedAt > START_MAX_MS) {
        Object.assign(changes, { phase: 'fehler' as const, error: 'Auf GitHub wurde innerhalb von 20 Minuten kein Lauf gestartet – die Anfrage gilt nicht mehr. Bitte neu anfordern.', finishedAt: Date.now() });
      } else if (phase !== 'start' && active({ ...job, phase }) && Date.now() - (job.openedAt ?? job.requestedAt) > RUN_MAX_MS + START_MAX_MS) {
        Object.assign(changes, { phase: 'fehler' as const, error: 'Kein Ergebnis – auf GitHub nachsehen, ob der Lauf durchgelaufen ist.', finishedAt: Date.now() });
      }
      if (Object.keys(changes).length) patchJob(job.kennung, changes);
      if (changes.phase && !active({ ...job, ...changes })) eingaben.current.delete(job.kennung);
    };

    const step = async () => {
      if (stopped || busy) return;
      const client = api();
      const running = jobsRef.current.filter(active);
      if (client && running.length && document.visibilityState === 'visible') {
        busy = true;
        tick.current += 1;
        for (const job of running) {
          try {
            await follow(client, job);
          } catch (error) {
            // offline oder Abfragegrenze: beim nächsten Durchgang erneut; die Meldung steht beim Fortschritt
            if (error instanceof GitHubError && error.kind === 'limit') patchJob(job.kennung, { stepName: errorText(error) });
          }
        }
        busy = false;
      }
    };

    const loop = async () => {
      await step();
      if (!stopped) timer = window.setTimeout(() => void loop(), POLL_MS);
    };
    const onVisible = () => {
      if (document.visibilityState === 'visible') void step();
    };
    document.addEventListener('visibilitychange', onVisible);
    void loop();
    return () => {
      stopped = true;
      document.removeEventListener('visibilitychange', onVisible);
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [api, patchJob, applyDelivery]);

  const setVisible = useCallback((source: string, isins: string[]) => {
    if (isins.length) visibleRef.current.set(source, isins);
    else visibleRef.current.delete(source);
  }, []);

  const preparePilot = useCallback(
    async (art: PilotEingangArt, inhalt: Record<string, unknown>): Promise<{ ok: boolean; text: string; kennung?: string; eingabe?: string }> => {
      if (!repo) return { ok: false, text: 'Das Repository ist unbekannt – Senden an den Robo gibt es nur in der eingerichteten App (GitHub Pages).' };
      if (!dataKey || !keyCanEncrypt) return { ok: false, text: 'Zum Senden einmal die Passphrase eingeben (Einstellungen), damit der Eingang verschlüsselt werden kann.' };
      const now = Date.now();
      const kennung = newKennung(now);
      const payload = { schema: 'tr-spielgeld-eingang/1', kennung, erstellt_utc: new Date(Math.floor(now / 1000) * 1000).toISOString().replace('.000Z', 'Z'), art, inhalt };
      const text = bytesToBase64(await encodeJson(payload, dataKey, `eingang/${kennung}`));
      if (text.length > PILOT_MAX_TEXT) return { ok: false, text: 'Der Eingang ist zu groß für GitHub (weniger Bedingungen oder eine kürzere Liste wählen).' };
      return {
        ok: true,
        text: 'Vorbereitet – jetzt auf GitHub starten (Zeile einfügen). GitHub prüft den Eingang meist in unter einer Minute; wirksam wird er mit dem nächsten täglichen Lauf.',
        kennung,
        eingabe: eingabeZeile(kennung, text),
      };
    },
    [repo, dataKey, keyCanEncrypt],
  );

  const readPilotResult = useCallback(
    async (kennung: string): Promise<PilotEingangErgebnis | null> => {
      const client = api();
      if (!client || !dataKey || !KENNUNG_RE.test(kennung)) return null;
      const head = await client.branchHead(PILOT_BRANCH);
      if (!head) return null;
      const bytes = await client.file(`ergebnis/${kennung}.bin`, head);
      return bytes ? decodeJson<PilotEingangErgebnis>(bytes, dataKey, `ergebnis/${kennung}`) : null;
    },
    [api, dataKey],
  );

  const value = useMemo<UpdateStateValue>(
    () => ({ repo, jobs, request, eingabeFor, markOpened, dismiss, quotes, courses, setVisible, preparePilot, readPilotResult }),
    [repo, jobs, request, eingabeFor, markOpened, dismiss, quotes, courses, setVisible, preparePilot, readPilotResult],
  );
  return <UpdateContext.Provider value={value}>{children}</UpdateContext.Provider>;
}
