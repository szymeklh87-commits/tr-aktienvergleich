/* „Jetzt aktualisieren“ (ab 1.21): Zugang, laufende Aktualisierungen mit Fortschritt, gelieferte Kurse, Automatik.
 *
 * Der Zugang (GitHub-Token mit „Actions: Lesen und Schreiben“ nur für dieses Repository) liegt verschlüsselt mit dem
 * Datenschlüssel in IndexedDB; gesperrt ist er nicht lesbar. Anfragen sind ebenfalls verschlüsselt (öffentlich sichtbar
 * sind nur Kennung und Chiffretext). Gelieferte Kurse bleiben so verschlüsselt gespeichert, wie sie ankommen. */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import {
  autoDue,
  DELIVERY_BRANCH,
  deliveryPath,
  errorFor,
  errorPath,
  marketMaybeOpen,
  newKennung,
  requestAad,
  requestPayload,
  stepLabel,
  valuesFor,
  WORKFLOW_ALLES,
  WORKFLOW_KURSE,
  type UpdateJob,
  type UpdateScope,
} from '../lib/aktualisierung';
import { bytesToBase64, decodeJson, encodeJson, NeedKeyError } from '../lib/container';
import { errorText, GitHubClient, GitHubError, plausibleToken, validRepository } from '../lib/github';
import { allValues, clearStore, deleteValue, getValue, putValue, STORE_LIEFERUNGEN, STORE_ZUGANG } from '../lib/keystore';
import { coursesFromDelivery, mergeQuotes, quotesFromDelivery, type DayCourse, type Delivery, type LiveQuote } from '../lib/livekurse';
import { useApp } from './AppState';

const ACCESS_ID = 'github';
const ACCESS_AAD = 'zugang/github';
const JOBS_KEY = 'tr-vergleich:aktualisierungen:v1';
const KEEP_MS = 2 * 24 * 3600_000;
const JOB_TIMEOUT_MS = 12 * 60_000;
const POLL_MS = 2_000;

export type AccessState = 'laedt' | 'keiner' | 'gesperrt' | 'bereit';

export interface RequestOptions {
  label?: string;
  /** so viele der ISINs (vorne) sind gerade sichtbar und kommen zuerst */
  visible?: number;
  /** ISINs, für die zusätzlich der Tagesverlauf kommt (höchstens 3) */
  courses?: string[];
  automatic?: boolean;
}

export interface UpdateStateValue {
  repo: string | null;
  access: AccessState;
  saveAccess: (token: string) => Promise<{ ok: boolean; text: string }>;
  removeAccess: () => Promise<void>;
  testAccess: () => Promise<{ ok: boolean; text: string }>;
  jobs: UpdateJob[];
  request: (scope: Exclude<UpdateScope, 'alles'>, isins: string[], options?: RequestOptions) => Promise<UpdateJob | string>;
  requestAll: () => Promise<UpdateJob | string>;
  dismiss: (kennung: string) => void;
  quotes: ReadonlyMap<string, LiveQuote>;
  courses: ReadonlyMap<string, DayCourse>;
  /** gerade sichtbare Aktien (von der Ansicht gemeldet) – für „sichtbare zuerst“ und die Automatik */
  setVisible: (source: string, isins: string[]) => void;
  autoReason: string | null;
  lastAutomatic: number | null;
  /** Spielgeld-Robo (Gesamtauftrag): Eingang verschlüsselt an den Workflow „Spielgeld-Eingang“ senden. */
  sendPilot: (art: PilotEingangArt, inhalt: Record<string, unknown>) => Promise<{ ok: boolean; text: string; kennung?: string }>;
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
  | 'pilot_einrichten';

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
export const PILOT_BRANCH = 'spielgeld-eingang';
const PILOT_MAX_TEXT = 60_000;

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
    return Array.isArray(list) ? list.filter((j) => j && typeof j.kennung === 'string' && Date.now() - j.requestedAt < KEEP_MS).slice(0, 10) : [];
  } catch {
    return [];
  }
}

function saveJobs(jobs: UpdateJob[]): void {
  try {
    // ohne ISINs: die laufende Aktualisierung lässt sich nach dem Neuladen weiterverfolgen, ohne die Merkliste zu speichern
    localStorage.setItem(JOBS_KEY, JSON.stringify(jobs.slice(0, 10).map((j) => ({ ...j, isins: [] }))));
  } catch {
    /* privater Modus */
  }
}

function active(job: UpdateJob): boolean {
  return job.phase === 'senden' || job.phase === 'wartet' || job.phase === 'laeuft' || job.phase === 'teil';
}

export function UpdateStateProvider({ children }: { children: ReactNode }) {
  const { status, dataKey, keyCanEncrypt, instruments, isinIndex, watchlist, prefs, checkNow } = useApp();
  const repo = validRepository(status?.aktualisieren?.repository) ? status!.aktualisieren!.repository : null;
  const [access, setAccessState] = useState<AccessState>('laedt');
  const tokenRef = useRef<string | null>(null);
  const [jobs, setJobsState] = useState<UpdateJob[]>(() => loadJobs());
  const jobsRef = useRef<UpdateJob[]>(jobs);
  const [quotes, setQuotes] = useState<ReadonlyMap<string, LiveQuote>>(new Map());
  const [courses, setCourses] = useState<ReadonlyMap<string, DayCourse>>(new Map());
  const visibleRef = useRef(new Map<string, string[]>());
  const lastInteraction = useRef(Date.now());
  const autoTimes = useRef<number[]>([]);
  const failures = useRef(0);
  const [autoReason, setAutoReason] = useState<string | null>(null);
  const [lastAutomatic, setLastAutomatic] = useState<number | null>(null);
  const statusRef = useRef(status);
  statusRef.current = status;

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

  // Zugang laden, sobald der Datenschlüssel da ist (gesperrt: nicht lesbar)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const stored = await getValue<Uint8Array>(STORE_ZUGANG, ACCESS_ID);
      if (cancelled) return;
      if (!stored) {
        tokenRef.current = null;
        setAccessState('keiner');
        return;
      }
      if (!dataKey) {
        tokenRef.current = null;
        setAccessState('gesperrt');
        return;
      }
      try {
        const value = await decodeJson<{ token: string }>(stored, dataKey, ACCESS_AAD);
        tokenRef.current = plausibleToken(value.token) ? value.token : null;
        setAccessState(tokenRef.current ? 'bereit' : 'keiner');
      } catch {
        tokenRef.current = null;
        setAccessState('gesperrt');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [dataKey]);

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

  const client = useCallback((): GitHubClient | null => (repo && tokenRef.current ? new GitHubClient(repo, tokenRef.current) : null), [repo]);

  const saveAccess = useCallback(
    async (token: string): Promise<{ ok: boolean; text: string }> => {
      const value = token.trim();
      if (!plausibleToken(value)) return { ok: false, text: 'Das sieht nicht wie ein GitHub-Token aus (beginnt mit „github_pat_“).' };
      if (!repo) return { ok: false, text: 'Das Repository ist unbekannt – „Jetzt aktualisieren“ gibt es nur in der eingerichteten App (GitHub Pages).' };
      if (!dataKey || !keyCanEncrypt) return { ok: false, text: 'Zum Speichern einmal die Passphrase eingeben (unten), damit der Zugang verschlüsselt abgelegt werden kann.' };
      let check: { ok: boolean; workflowFound: boolean; tooBroad: boolean };
      try {
        check = await new GitHubClient(repo, value).check(WORKFLOW_KURSE);
      } catch (error) {
        return { ok: false, text: errorText(error) };
      }
      const blob = await encodeJson({ token: value, gespeichert_utc: new Date().toISOString() }, dataKey, ACCESS_AAD);
      if (!(await putValue(STORE_ZUGANG, ACCESS_ID, blob))) return { ok: false, text: 'Der Speicher des Browsers ist nicht verfügbar (privater Modus?). Der Zugang wurde nicht gespeichert.' };
      tokenRef.current = value;
      setAccessState('bereit');
      failures.current = 0;
      const notes = [
        'Zugang gespeichert (verschlüsselt, nur auf diesem Gerät).',
        check.workflowFound ? '' : 'Hinweis: Der Workflow „Kursaktualisierung“ ist auf GitHub noch nicht vorhanden – Kurse einzelner Aktien gehen erst nach der Freigabe der neuen Version.',
        check.tooBroad ? 'Achtung: Dieser Zugang darf mehr als nötig (z. B. Secrets lesen). Besser ein neues Token nur mit „Actions: Lesen und Schreiben“ anlegen und dieses widerrufen.' : '',
      ];
      return { ok: true, text: notes.filter(Boolean).join(' ') };
    },
    [repo, dataKey, keyCanEncrypt],
  );

  const removeAccess = useCallback(async () => {
    await deleteValue(STORE_ZUGANG, ACCESS_ID);
    await clearStore(STORE_LIEFERUNGEN);
    tokenRef.current = null;
    setAccessState('keiner');
    setQuotes(new Map());
    setCourses(new Map());
  }, []);

  const testAccess = useCallback(async (): Promise<{ ok: boolean; text: string }> => {
    const api = client();
    if (!api) return { ok: false, text: 'Kein Zugang eingerichtet.' };
    try {
      const check = await api.check(WORKFLOW_KURSE);
      return {
        ok: true,
        text: [
          'Zugang gültig.',
          check.workflowFound ? 'Workflow „Kursaktualisierung“ vorhanden.' : 'Workflow „Kursaktualisierung“ noch nicht auf GitHub (erst nach Freigabe der neuen Version).',
          check.tooBroad ? 'Achtung: Der Zugang darf mehr als nötig.' : '',
        ]
          .filter(Boolean)
          .join(' '),
      };
    } catch (error) {
      return { ok: false, text: errorText(error) };
    }
  }, [client]);

  const symbolOf = useCallback((isin: string) => {
    const i = isinIndex.get(isin);
    return i !== undefined && instruments ? instruments.symbol[i] : null;
  }, [instruments, isinIndex]);

  const request = useCallback(
    async (scope: Exclude<UpdateScope, 'alles'>, isins: string[], options: RequestOptions = {}): Promise<UpdateJob | string> => {
      const api = client();
      if (!api) return 'Für „Jetzt aktualisieren“ fehlt der Zugang (Einstellungen).';
      if (!dataKey || !keyCanEncrypt) return 'Zum Senden einmal die Passphrase eingeben (Einstellungen → Zugang), damit die Anfrage verschlüsselt werden kann.';
      const { values } = valuesFor(isins, symbolOf);
      if (!values.length) return 'Für diese Aktien gibt es kein Kurssymbol – sie lassen sich nicht einzeln aktualisieren.';
      const running = jobsRef.current.find((j) => active(j) && j.scope !== 'alles');
      if (running && options.automatic) return 'Es läuft schon eine Aktualisierung.';
      const now = Date.now();
      const kennung = newKennung(now);
      const payload = requestPayload(kennung, scope, values, options.visible ?? values.length, options.courses ?? [], now);
      const job: UpdateJob = {
        kennung,
        scope,
        label: options.label ?? scope,
        isins: payload.werte.map((v) => v.isin),
        automatic: Boolean(options.automatic),
        requestedAt: now,
        dispatchedAt: null,
        runId: null,
        runUrl: null,
        runStartedAt: null,
        phase: 'senden',
        stepName: null,
        stepIndex: 0,
        stepCount: 0,
        partsReceived: 0,
        partsTotal: null,
        quotesReceived: 0,
        missing: 0,
        finishedAt: null,
        error: null,
      };
      setJobs((list) => [job, ...list].slice(0, 10));
      try {
        const encrypted = await encodeJson(payload, dataKey, requestAad(kennung));
        const result = await api.dispatch(WORKFLOW_KURSE, { kennung, anfrage: bytesToBase64(encrypted) });
        patchJob(kennung, { phase: 'wartet', dispatchedAt: Date.now(), runId: result.runId, runUrl: result.runUrl });
        if (options.automatic) {
          autoTimes.current = [...autoTimes.current.filter((t) => now - t < 3_600_000), now];
          setLastAutomatic(now);
        }
        failures.current = 0;
        return { ...job, phase: 'wartet' };
      } catch (error) {
        failures.current += 1;
        const text = error instanceof GitHubError && error.kind === 'nicht_gefunden' ? 'Der Workflow „Kursaktualisierung“ ist auf GitHub noch nicht vorhanden (neue Version noch nicht freigegeben).' : errorText(error);
        patchJob(kennung, { phase: 'fehler', error: text, finishedAt: Date.now() });
        return text;
      }
    },
    [client, dataKey, keyCanEncrypt, symbolOf, setJobs, patchJob],
  );

  const requestAll = useCallback(async (): Promise<UpdateJob | string> => {
    const api = client();
    if (!api) return 'Für „Jetzt aktualisieren“ aus der App fehlt der Zugang (Einstellungen).';
    if (jobsRef.current.some((j) => active(j) && j.scope === 'alles')) return 'Der gesamte Datenbestand wird schon aktualisiert.';
    const now = Date.now();
    const job: UpdateJob = {
      kennung: newKennung(now),
      scope: 'alles',
      label: 'Gesamter Datenbestand',
      isins: [],
      automatic: false,
      requestedAt: now,
      dispatchedAt: null,
      runId: null,
      runUrl: null,
      runStartedAt: null,
      phase: 'senden',
      stepName: null,
      stepIndex: 0,
      stepCount: 0,
      partsReceived: 0,
      partsTotal: null,
      quotesReceived: 0,
      missing: 0,
      finishedAt: null,
      error: null,
      baselineSnapshot: statusRef.current?.latest_snapshot_id ?? null,
    };
    setJobs((list) => [job, ...list].slice(0, 10));
    try {
      const result = await api.dispatch(WORKFLOW_ALLES, { zwischenstand: true });
      patchJob(job.kennung, { phase: 'wartet', dispatchedAt: Date.now(), runId: result.runId, runUrl: result.runUrl });
      return { ...job, phase: 'wartet' };
    } catch (error) {
      const text = errorText(error);
      patchJob(job.kennung, { phase: 'fehler', error: text, finishedAt: Date.now() });
      return text;
    }
  }, [client, setJobs, patchJob]);

  const dismiss = useCallback((kennung: string) => setJobs((list) => list.filter((j) => j.kennung !== kennung)), [setJobs]);

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

  // Fortschritt verfolgen: alle 2 Sekunden, solange etwas läuft und die App sichtbar ist
  const tick = useRef(0);
  useEffect(() => {
    let timer: number | undefined;
    let stopped = false;
    const step = async () => {
      if (stopped) return;
      const api = client();
      const running = jobsRef.current.filter(active);
      if (api && running.length && document.visibilityState === 'visible') {
        tick.current += 1;
        for (const job of running) {
          try {
            await follow(api, job);
          } catch (error) {
            if (error instanceof GitHubError && (error.kind === 'zugang_ungueltig' || error.kind === 'rechte_fehlen')) {
              patchJob(job.kennung, { phase: 'fehler', error: errorText(error), finishedAt: Date.now() });
            }
            // offline oder Limit: beim nächsten Durchgang erneut
          }
          if (Date.now() - job.requestedAt > JOB_TIMEOUT_MS && active(jobsRef.current.find((j) => j.kennung === job.kennung) ?? job)) {
            patchJob(job.kennung, { phase: 'fehler', error: 'Nach 12 Minuten kein Ergebnis. Auf GitHub nachsehen, ob der Lauf gestartet ist.', finishedAt: Date.now() });
          }
        }
      }
      timer = window.setTimeout(() => void step(), POLL_MS);
    };

    const follow = async (api: GitHubClient, job: UpdateJob) => {
      let runId = job.runId;
      if (runId === null) {
        const since = new Date(job.requestedAt - 60_000).toISOString().replace(/\.\d{3}Z$/, 'Z');
        const runs = await api.recentRuns(job.scope === 'alles' ? WORKFLOW_ALLES : WORKFLOW_KURSE, since);
        const match =
          job.scope === 'alles'
            ? runs.filter((r) => Date.parse(r.created_at) >= (job.dispatchedAt ?? job.requestedAt) - 15_000).sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))[0]
            : runs.find((r) => r.display_title === `Kursaktualisierung ${job.kennung}`);
        if (!match) return;
        runId = match.id;
        patchJob(job.kennung, { runId, runUrl: match.html_url });
      }
      const run = await api.run(runId);
      const changes: Partial<UpdateJob> = { runUrl: run.html_url };
      if (run.status === 'in_progress' || run.status === 'completed') {
        changes.runStartedAt = Date.parse(run.run_started_at ?? run.created_at);
        if (job.phase === 'wartet') changes.phase = 'laeuft';
      }
      if (tick.current % 2 === 0 || run.status === 'completed') {
        const jobsInfo = await api.jobs(runId);
        const steps = jobsInfo.flatMap((j) => j.steps).filter((s) => !s.name.startsWith('Post ') && s.name !== 'Complete job');
        const current = steps.find((s) => s.status === 'in_progress') ?? [...steps].reverse().find((s) => s.status === 'completed');
        if (current) {
          changes.stepName = stepLabel(current.name);
          changes.stepIndex = steps.indexOf(current) + 1;
          changes.stepCount = steps.length;
        }
      }
      if (job.scope !== 'alles') {
        // Lieferungen: nächster Teil, sobald vorhanden
        let received = job.partsReceived;
        let total = job.partsTotal;
        let quotesReceived = job.quotesReceived;
        let missing = job.missing;
        while (total === null || received < total) {
          const path = deliveryPath(job.kennung, received + 1);
          const bytes = await api.file(path, DELIVERY_BRANCH);
          if (!bytes) break;
          const delivery = await applyDelivery(path, bytes);
          if (!delivery) break;
          received += 1;
          total = delivery.teile;
          quotesReceived += delivery.kurse.length;
          missing += delivery.fehlend.length;
        }
        if (received !== job.partsReceived) Object.assign(changes, { partsReceived: received, partsTotal: total, quotesReceived, missing, phase: 'teil' as const });
        if (total !== null && received >= total) Object.assign(changes, { phase: 'fertig' as const, finishedAt: Date.now() });
        else if (run.status === 'completed') {
          const error = await api.file(errorPath(job.kennung), DELIVERY_BRANCH);
          if (error) {
            let code = 'unbekannt';
            try {
              code = String((JSON.parse(new TextDecoder().decode(error)) as { grund?: string }).grund ?? 'unbekannt');
            } catch {
              /* unlesbar */
            }
            Object.assign(changes, { phase: 'fehler' as const, error: errorFor(code), finishedAt: Date.now() });
          } else if (run.conclusion !== 'success') {
            Object.assign(changes, { phase: 'fehler' as const, error: `Lauf ${run.conclusion === 'cancelled' ? 'abgebrochen (eine neuere Anfrage hat ihn ersetzt?)' : 'fehlgeschlagen'} – Einzelheiten auf GitHub.`, finishedAt: Date.now() });
          }
        }
      } else if (run.status === 'completed') {
        if (run.conclusion !== 'success') {
          Object.assign(changes, { phase: 'fehler' as const, error: 'Der Lauf ist fehlgeschlagen – der bisherige Stand bleibt. Einzelheiten auf GitHub.', finishedAt: Date.now() });
        } else {
          await checkNow();
          const latest = statusRef.current?.latest_snapshot_id ?? null;
          if (latest && latest !== job.baselineSnapshot) Object.assign(changes, { phase: 'fertig' as const, finishedAt: Date.now() });
          else if (Date.now() - Date.parse(run.updated_at) > 90_000) {
            const message = statusRef.current?.last_run?.message ?? null;
            Object.assign(changes, { phase: 'ohne_ergebnis' as const, error: message ?? 'Kein neuer Stand – seit dem letzten Stand gibt es keine neuen Kurse.', finishedAt: Date.now() });
          }
        }
      }
      patchJob(job.kennung, changes);
    };

    void step();
    return () => {
      stopped = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [client, patchJob, applyDelivery, checkNow]);

  const setVisible = useCallback((source: string, isins: string[]) => {
    if (isins.length) visibleRef.current.set(source, isins);
    else visibleRef.current.delete(source);
  }, []);

  // Automatische Aktualisierung während der Nutzung (nur mit Zugang)
  useEffect(() => {
    const touch = () => {
      lastInteraction.current = Date.now();
    };
    window.addEventListener('pointerdown', touch, { passive: true });
    window.addEventListener('keydown', touch);
    window.addEventListener('scroll', touch, { passive: true });
    const timer = window.setInterval(() => {
      const visible = [...new Set([...visibleRef.current.values()].flat())];
      const wanted = [...new Set([...visible, ...watchlist])].slice(0, 60);
      const marketOpen = wanted.some((isin) => {
        const i = isinIndex.get(isin);
        return marketMaybeOpen(i !== undefined && instruments?.calendar ? instruments.calendar[i] : null);
      });
      const decision = autoDue({
        now: Date.now(),
        settings: { minutes: prefs.autoKurseMin },
        visible: document.visibilityState === 'visible',
        lastInteraction: lastInteraction.current,
        lastAutomatic: autoTimes.current.length ? autoTimes.current[autoTimes.current.length - 1] : null,
        automaticTimes: autoTimes.current,
        running: jobsRef.current.some(active),
        failuresInRow: failures.current,
        marketOpen,
        hasAccess: tokenRef.current !== null,
        count: wanted.length,
      });
      setAutoReason(decision.due ? null : decision.reason);
      if (decision.due) void request('sichtbar', wanted, { visible: visible.length, label: 'Automatisch: sichtbare Aktien und Merkliste', automatic: true });
    }, 30_000);
    return () => {
      window.removeEventListener('pointerdown', touch);
      window.removeEventListener('keydown', touch);
      window.removeEventListener('scroll', touch);
      window.clearInterval(timer);
    };
  }, [prefs.autoKurseMin, watchlist, isinIndex, instruments, request]);

  const sendPilot = useCallback(
    async (art: PilotEingangArt, inhalt: Record<string, unknown>): Promise<{ ok: boolean; text: string; kennung?: string }> => {
      const api = client();
      if (!api) return { ok: false, text: 'Zum Senden an den Robo fehlt der Zugang (Einstellungen → Zugang, derselbe wie für „Jetzt aktualisieren“).' };
      if (!dataKey || !keyCanEncrypt) return { ok: false, text: 'Zum Senden einmal die Passphrase eingeben (Einstellungen → Zugang), damit der Eingang verschlüsselt werden kann.' };
      const now = Date.now();
      const kennung = newKennung(now);
      const payload = { schema: 'tr-spielgeld-eingang/1', kennung, erstellt_utc: new Date(Math.floor(now / 1000) * 1000).toISOString().replace('.000Z', 'Z'), art, inhalt };
      try {
        const text = bytesToBase64(await encodeJson(payload, dataKey, `eingang/${kennung}`));
        if (text.length > PILOT_MAX_TEXT) return { ok: false, text: 'Der Eingang ist zu groß zum Senden (weniger Bedingungen oder eine kürzere Liste wählen).' };
        await api.dispatch(WORKFLOW_PILOT, { kennung, nutzlast: text });
        return { ok: true, text: 'Gesendet – GitHub prüft den Eingang (meist unter einer Minute). Wirksam wird er mit dem nächsten täglichen Lauf.', kennung };
      } catch (error) {
        return {
          ok: false,
          text: error instanceof GitHubError && error.kind === 'nicht_gefunden' ? 'Der Workflow „Spielgeld-Eingang“ ist auf GitHub noch nicht vorhanden (neue Version noch nicht freigegeben).' : errorText(error),
        };
      }
    },
    [client, dataKey, keyCanEncrypt],
  );

  const readPilotResult = useCallback(
    async (kennung: string): Promise<PilotEingangErgebnis | null> => {
      const api = client();
      if (!api || !dataKey || !/^k[0-9a-z]{6,8}-[0-9a-z]{16}$/.test(kennung)) return null;
      const bytes = await api.file(`ergebnis/${kennung}.bin`, PILOT_BRANCH);
      return bytes ? decodeJson<PilotEingangErgebnis>(bytes, dataKey, `ergebnis/${kennung}`) : null;
    },
    [client, dataKey],
  );

  const value = useMemo<UpdateStateValue>(
    () => ({ repo, access, saveAccess, removeAccess, testAccess, jobs, request, requestAll, dismiss, quotes, courses, setVisible, autoReason, lastAutomatic, sendPilot, readPilotResult }),
    [repo, access, saveAccess, removeAccess, testAccess, jobs, request, requestAll, dismiss, quotes, courses, setVisible, autoReason, lastAutomatic, sendPilot, readPilotResult],
  );
  return <UpdateContext.Provider value={value}>{children}</UpdateContext.Provider>;
}
