/* GitHub-Schnittstelle für „Jetzt aktualisieren“ (ab 1.21).
 *
 * Die App startet Läufe mit dem Zugang, den du in den Einstellungen hinterlegt hast (feingranulares Token nur für dieses
 * Repository, nur „Actions: Lesen und Schreiben“), liest den Fortschritt des Laufs und lädt die verschlüsselten
 * Lieferungen vom Branch „kurse-aktuell“. Die Schnittstelle erlaubt Aufrufe aus dem Browser (CORS, laut GitHub für jede
 * Herkunft). Das Token steht nur im Kopf „Authorization“ – nie in einer Adresse, einem Protokoll oder einem Cache. */

export const API = 'https://api.github.com';
const HEADERS = { Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' };

export type GitHubErrorKind = 'offline' | 'zugang_ungueltig' | 'rechte_fehlen' | 'nicht_gefunden' | 'limit' | 'server';

export class GitHubError extends Error {
  constructor(
    public readonly kind: GitHubErrorKind,
    message: string,
    public readonly status: number | null = null,
  ) {
    super(message);
  }
}

export function errorText(error: unknown): string {
  if (!(error instanceof GitHubError)) return 'Unbekannter Fehler bei der GitHub-Schnittstelle.';
  switch (error.kind) {
    case 'offline':
      return 'Keine Verbindung zu GitHub. Netz prüfen und noch einmal versuchen.';
    case 'zugang_ungueltig':
      return 'GitHub lehnt den Zugang ab (abgelaufen, widerrufen oder falsch eingegeben). Unter Einstellungen einen neuen Zugang eintragen.';
    case 'rechte_fehlen':
      return 'Dem Zugang fehlt die Berechtigung „Actions: Lesen und Schreiben“ für dieses Repository.';
    case 'nicht_gefunden':
      return 'GitHub kennt diesen Lauf oder diese Datei nicht (noch nicht vorhanden oder Repository nicht freigegeben).';
    case 'limit':
      return 'Das Abfragelimit von GitHub ist erreicht. In einigen Minuten noch einmal versuchen.';
    default:
      return `GitHub antwortet mit einem Fehler${error.status ? ` (HTTP ${error.status})` : ''}. Später noch einmal versuchen.`;
  }
}

/** Gültiges Repository „konto/name“. */
export function validRepository(repo: string | null | undefined): repo is string {
  return typeof repo === 'string' && /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo);
}

/** Feingranulares Token („github_pat_…“) oder klassisches Token („ghp_…“). */
export function plausibleToken(token: string): boolean {
  return /^github_pat_[A-Za-z0-9_]{20,255}$/.test(token) || /^ghp_[A-Za-z0-9]{36}$/.test(token);
}

type Fetcher = (input: string, init?: RequestInit) => Promise<Response>;

async function request(fetcher: Fetcher, token: string | null, path: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = { ...HEADERS, ...((init.headers as Record<string, string>) ?? {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  let response: Response;
  try {
    response = await fetcher(`${API}${path}`, { ...init, headers, cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer' });
  } catch {
    throw new GitHubError('offline', 'Keine Verbindung zu GitHub');
  }
  if (response.ok) return response;
  if (response.status === 401) throw new GitHubError('zugang_ungueltig', 'Zugang abgelehnt', 401);
  if (response.status === 404) throw new GitHubError('nicht_gefunden', 'Nicht gefunden', 404);
  if (response.status === 403 || response.status === 429) {
    const remaining = response.headers.get('x-ratelimit-remaining');
    if (response.status === 429 || remaining === '0') throw new GitHubError('limit', 'Abfragelimit erreicht', response.status);
    throw new GitHubError('rechte_fehlen', 'Berechtigung fehlt', 403);
  }
  if (response.status === 422) throw new GitHubError('rechte_fehlen', 'Lauf lässt sich nicht starten (Workflow fehlt auf main oder Eingaben passen nicht)', 422);
  throw new GitHubError('server', 'Serverfehler', response.status);
}

export interface RunInfo {
  id: number;
  status: string; // queued | in_progress | completed | waiting | requested | pending
  conclusion: string | null; // success | failure | cancelled | skipped | timed_out …
  created_at: string;
  run_started_at: string | null;
  updated_at: string;
  html_url: string;
  display_title: string;
}

export interface StepInfo {
  name: string;
  status: string;
  conclusion: string | null;
  number: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface JobInfo {
  name: string;
  status: string;
  conclusion: string | null;
  started_at: string | null;
  completed_at: string | null;
  steps: StepInfo[];
}

export interface DispatchResult {
  runId: number | null;
  runUrl: string | null;
}

export class GitHubClient {
  constructor(
    public readonly repo: string,
    private readonly token: string | null,
    private readonly fetcher: Fetcher = (input, init) => fetch(input, init),
  ) {
    if (!validRepository(repo)) throw new GitHubError('nicht_gefunden', 'Repository unbekannt');
  }

  /** Lauf starten. Neuere GitHub-Versionen melden die Laufnummer direkt (HTTP 200), sonst kommt 204 ohne Inhalt. */
  async dispatch(workflow: string, inputs: Record<string, string | boolean>, ref = 'main'): Promise<DispatchResult> {
    const response = await request(this.fetcher, this.token, `/repos/${this.repo}/actions/workflows/${encodeURIComponent(workflow)}/dispatches`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ref, inputs, return_run_details: true }),
    });
    if (response.status === 200) {
      try {
        const body = (await response.json()) as { workflow_run_id?: number; html_url?: string };
        return { runId: typeof body.workflow_run_id === 'number' ? body.workflow_run_id : null, runUrl: typeof body.html_url === 'string' ? body.html_url : null };
      } catch {
        return { runId: null, runUrl: null };
      }
    }
    return { runId: null, runUrl: null };
  }

  /** Neueste Läufe eines Workflows, die per Schnittstelle oder von Hand gestartet wurden. */
  async recentRuns(workflow: string, sinceIso: string): Promise<RunInfo[]> {
    const query = new URLSearchParams({ event: 'workflow_dispatch', per_page: '20', created: `>=${sinceIso}` });
    const response = await request(this.fetcher, this.token, `/repos/${this.repo}/actions/workflows/${encodeURIComponent(workflow)}/runs?${query}`);
    const body = (await response.json()) as { workflow_runs?: RunInfo[] };
    return body.workflow_runs ?? [];
  }

  async run(id: number): Promise<RunInfo> {
    const response = await request(this.fetcher, this.token, `/repos/${this.repo}/actions/runs/${id}`);
    return (await response.json()) as RunInfo;
  }

  async jobs(id: number): Promise<JobInfo[]> {
    const response = await request(this.fetcher, this.token, `/repos/${this.repo}/actions/runs/${id}/jobs?per_page=20`);
    const body = (await response.json()) as { jobs?: JobInfo[] };
    return body.jobs ?? [];
  }

  /** Datei vom Lieferkanal (roh); null, solange es sie nicht gibt. */
  async file(path: string, ref: string): Promise<Uint8Array | null> {
    try {
      const response = await request(this.fetcher, this.token, `/repos/${this.repo}/contents/${path.split('/').map(encodeURIComponent).join('/')}?ref=${encodeURIComponent(ref)}`, {
        headers: { Accept: 'application/vnd.github.raw' },
      });
      return new Uint8Array(await response.arrayBuffer());
    } catch (error) {
      if (error instanceof GitHubError && error.kind === 'nicht_gefunden') return null;
      throw error;
    }
  }

  /** Prüft den Zugang: gültig, Workflow erreichbar – und warnt, wenn er mehr darf als nötig (z. B. Secrets lesen). */
  async check(workflow: string): Promise<{ ok: boolean; workflowFound: boolean; tooBroad: boolean }> {
    await request(this.fetcher, this.token, `/repos/${this.repo}`);
    let workflowFound = true;
    try {
      await request(this.fetcher, this.token, `/repos/${this.repo}/actions/workflows/${encodeURIComponent(workflow)}`);
    } catch (error) {
      if (error instanceof GitHubError && error.kind === 'nicht_gefunden') workflowFound = false;
      else throw error;
    }
    let tooBroad = false;
    try {
      await request(this.fetcher, this.token, `/repos/${this.repo}/actions/secrets/public-key`);
      tooBroad = true; // nur mit „Secrets“-Recht lesbar – das braucht die App nicht
    } catch {
      tooBroad = false;
    }
    return { ok: true, workflowFound, tooBroad };
  }
}

/** Vorlage für ein neues feingranulares Token mit genau dem nötigen Recht (GitHub-Vorlagenadressen seit 26.08.2025). */
export function tokenTemplateUrl(repo: string): string {
  const params = new URLSearchParams({
    name: 'TR-Aktienvergleich – Jetzt aktualisieren',
    description: `Nur Läufe in ${repo} starten und ihren Fortschritt lesen (App „Jetzt aktualisieren“).`,
    actions: 'write',
  });
  return `https://github.com/settings/personal-access-tokens/new?${params}`;
}
