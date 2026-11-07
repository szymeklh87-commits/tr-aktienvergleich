/* Öffentliche GitHub-Schnittstelle für „Jetzt aktualisieren“ und den Spielgeld-Robo (ab 1.22: nur lesen, ohne Zugang).
 *
 * Die App enthält keinen GitHub-Zugang – kein Token, auch nicht verschlüsselt. Gestartet wird ein Lauf auf GitHub mit der
 * eigenen Anmeldung („Run workflow“); die App bereitet nur die verschlüsselte Eingabe vor (siehe ``githubstart``). Lesen geht
 * ohne Anmeldung, weil das Repository öffentlich ist: Fortschritt eines Laufs über die Schnittstelle (höchstens 60 Abfragen
 * je Stunde und Netz – die App fragt sparsam), gelieferte Dateien über raw.githubusercontent.com zu einem festen Commit
 * (unveränderlich, keine veralteten Zwischenspeicher). Kein Kopf „Authorization“, keine Cookies, kein Referrer. */

export const API = 'https://api.github.com';
export const RAW = 'https://raw.githubusercontent.com';
export const WEB = 'https://github.com';
const HEADERS = { Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' };

export type GitHubErrorKind = 'offline' | 'nicht_gefunden' | 'limit' | 'server';

export class GitHubError extends Error {
  constructor(
    public readonly kind: GitHubErrorKind,
    message: string,
    public readonly status: number | null = null,
    /** bei „limit“: ab wann GitHub wieder antwortet (ms seit 1970), sonst null */
    public readonly resetAt: number | null = null,
  ) {
    super(message);
  }
}

const clock = new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Berlin' });

export function errorText(error: unknown): string {
  if (!(error instanceof GitHubError)) return 'Unbekannter Fehler bei der GitHub-Schnittstelle.';
  switch (error.kind) {
    case 'offline':
      return 'Keine Verbindung zu GitHub. Netz prüfen – die App schaut gleich noch einmal nach.';
    case 'nicht_gefunden':
      return 'GitHub kennt diesen Lauf oder diese Datei (noch) nicht.';
    case 'limit':
      return `GitHub beantwortet von diesem Netz gerade keine Abfragen mehr (Grenze ohne Anmeldung: 60 je Stunde)${
        error.resetAt ? ` – die App schaut ab ${clock.format(new Date(error.resetAt))} Uhr wieder nach` : ''
      }. Den Lauf siehst du direkt auf GitHub.`;
    default:
      return `GitHub antwortet mit einem Fehler${error.status ? ` (HTTP ${error.status})` : ''}. Die App versucht es später noch einmal.`;
  }
}

/** Gültiges Repository „konto/name“. */
export function validRepository(repo: string | null | undefined): repo is string {
  return typeof repo === 'string' && /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo);
}

/** Seite des Workflows auf GitHub – dort „Run workflow“ (mit der eigenen Anmeldung). */
export function workflowPage(repo: string, workflow: string): string {
  return `${WEB}/${repo}/actions/workflows/${encodeURIComponent(workflow)}`;
}

type Fetcher = (input: string, init?: RequestInit) => Promise<Response>;

const NO_CREDENTIALS: RequestInit = { cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer', mode: 'cors' };

export interface RunInfo {
  id: number;
  status: string; // queued | in_progress | completed | waiting | requested | pending
  conclusion: string | null; // success | failure | cancelled | skipped | timed_out …
  created_at: string;
  run_started_at: string | null;
  updated_at: string;
  html_url: string;
  display_title: string;
  event?: string;
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

/** Lesender Zugriff ohne Anmeldung. ``remaining`` zeigt, wie viele Abfragen GitHub diesem Netz in dieser Stunde noch erlaubt. */
export class PublicGitHub {
  remaining: number | null = null;
  resetAt: number | null = null;

  constructor(
    public readonly repo: string,
    private readonly fetcher: Fetcher = (input, init) => fetch(input, init),
  ) {
    if (!validRepository(repo)) throw new GitHubError('nicht_gefunden', 'Repository unbekannt');
  }

  private async api(path: string, accept?: string): Promise<Response> {
    if (this.remaining !== null && this.remaining <= 1 && this.resetAt !== null && Date.now() < this.resetAt) {
      throw new GitHubError('limit', 'Abfragegrenze erreicht', 403, this.resetAt);
    }
    let response: Response;
    try {
      response = await this.fetcher(`${API}${path}`, { ...NO_CREDENTIALS, headers: accept ? { ...HEADERS, Accept: accept } : HEADERS });
    } catch {
      throw new GitHubError('offline', 'Keine Verbindung zu GitHub');
    }
    const remaining = Number(response.headers.get('x-ratelimit-remaining'));
    const reset = Number(response.headers.get('x-ratelimit-reset'));
    if (response.headers.has('x-ratelimit-remaining') && Number.isFinite(remaining)) this.remaining = remaining;
    if (response.headers.has('x-ratelimit-reset') && Number.isFinite(reset) && reset > 0) this.resetAt = reset * 1000;
    if (response.ok) return response;
    if (response.status === 404 || response.status === 422) throw new GitHubError('nicht_gefunden', 'Nicht gefunden', response.status);
    if (response.status === 429 || (response.status === 403 && this.remaining === 0)) throw new GitHubError('limit', 'Abfragegrenze erreicht', response.status, this.resetAt);
    throw new GitHubError('server', 'Serverfehler', response.status);
  }

  /** Neueste von Hand gestartete Läufe eines Workflows seit einem Zeitpunkt. */
  async recentRuns(workflow: string, sinceIso: string): Promise<RunInfo[]> {
    const query = new URLSearchParams({ event: 'workflow_dispatch', per_page: '20', created: `>=${sinceIso}` });
    const response = await this.api(`/repos/${this.repo}/actions/workflows/${encodeURIComponent(workflow)}/runs?${query}`);
    const body = (await response.json()) as { workflow_runs?: RunInfo[] };
    return body.workflow_runs ?? [];
  }

  async run(id: number): Promise<RunInfo> {
    const response = await this.api(`/repos/${this.repo}/actions/runs/${id}`);
    return (await response.json()) as RunInfo;
  }

  async jobs(id: number): Promise<JobInfo[]> {
    const response = await this.api(`/repos/${this.repo}/actions/runs/${id}/jobs?per_page=20`);
    const body = (await response.json()) as { jobs?: JobInfo[] };
    return body.jobs ?? [];
  }

  /** Neuester Commit eines Branches (40 Zeichen) – null, solange es den Branch nicht gibt. */
  async branchHead(branch: string): Promise<string | null> {
    try {
      const response = await this.api(`/repos/${this.repo}/commits/${encodeURIComponent(branch)}`, 'application/vnd.github.sha');
      const sha = (await response.text()).trim();
      return /^[0-9a-f]{40}$/.test(sha) ? sha : null;
    } catch (error) {
      if (error instanceof GitHubError && error.kind === 'nicht_gefunden') return null;
      throw error;
    }
  }

  /** Datei zu einem festen Commit (roh); null, wenn es sie dort nicht gibt. Zählt nicht zur Abfragegrenze der Schnittstelle. */
  async file(path: string, commit: string): Promise<Uint8Array | null> {
    if (!/^[0-9a-f]{40}$/.test(commit)) return null;
    let response: Response;
    try {
      response = await this.fetcher(`${RAW}/${this.repo}/${commit}/${path.split('/').map(encodeURIComponent).join('/')}`, NO_CREDENTIALS);
    } catch {
      throw new GitHubError('offline', 'Keine Verbindung zu GitHub');
    }
    if (response.status === 404) return null;
    if (!response.ok) throw new GitHubError(response.status === 429 ? 'limit' : 'server', 'Datei nicht abrufbar', response.status);
    return new Uint8Array(await response.arrayBuffer());
  }
}
