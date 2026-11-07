"""Nachgebildetes GitHub für die Browser-Tests ab 1.22: nur die öffentliche, lesende Schnittstelle und raw.githubusercontent.com.

Die App enthält keinen GitHub-Zugang mehr. Wie in Wirklichkeit startet nicht die App einen Lauf, sondern du auf GitHub („Run
workflow“, die von der App kopierte Zeile einfügen) – im Test übernimmt das ``start_*``: Die Zeile geht an den echten
Server-Code, dessen Dateien landen auf dem nachgebildeten Branch, und der Lauf erscheint in der Laufliste. Gelesen wird nur
ohne Anmeldung; jede Anfrage wird mit ihren Köpfen festgehalten, damit die Tests prüfen können, dass nie ein Kopf
„Authorization“ und nie ein schreibender Aufruf vorkommt.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import threading
from pathlib import Path

REPO = "beispiel/tr-aktienvergleich"
API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
WEB = "https://github.com"

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Accept, X-GitHub-Api-Version, Content-Type",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Expose-Headers": "x-ratelimit-remaining, x-ratelimit-reset",
}


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class OeffentlichesGitHub:
    """Läufe, Branches mit Dateien (je Stand ein Commit) und ein Protokoll aller Anfragen der App."""

    def __init__(self, repo: str = REPO) -> None:
        self.repo = repo
        self.runs: list[dict] = []
        self.branches: dict[str, str] = {}
        self.commits: dict[str, dict[str, bytes]] = {}
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.opened: list[str] = []
        self.lock = threading.Lock()
        self._next_id = 4711

    # ------------------------------------------------------------------ Einrichtung im Browser
    def attach(self, context) -> None:
        context.route(f"{API}/**", self._api)
        context.route(f"{RAW}/**", self._raw)
        context.route(f"{WEB}/**", self._web)

    # ------------------------------------------------------------------ „auf GitHub“
    def put(self, branch: str, files: dict[str, bytes]) -> str:
        """Dateien auf einen Branch legen (neuer Commit mit allen bisherigen und den neuen Dateien)."""
        with self.lock:
            current = dict(self.commits.get(self.branches.get(branch, ""), {}))
            current.update(files)
            digest = hashlib.sha1(json.dumps(sorted((k, hashlib.sha1(v).hexdigest()) for k, v in current.items())).encode() + branch.encode()).hexdigest()
            self.commits[digest] = current
            self.branches[branch] = digest
            return digest

    def add_run(self, workflow: str, title: str, created: dt.datetime, status: str = "completed", conclusion: str | None = "success") -> dict:
        with self.lock:
            run = {
                "id": self._next_id,
                "workflow": workflow,
                "status": status,
                "conclusion": conclusion if status == "completed" else None,
                "created_at": iso(created),
                "run_started_at": iso(created),
                "updated_at": iso(created),
                "html_url": f"{WEB}/{self.repo}/actions/runs/{self._next_id}",
                "display_title": title,
                "event": "workflow_dispatch",
            }
            self._next_id += 1
            self.runs.append(run)
            return run

    # ------------------------------------------------------------------ Prüfungen
    def writes(self) -> list[tuple[str, str]]:
        return [(m, u) for m, u, _ in self.requests if m not in ("GET", "OPTIONS", "HEAD")]

    def authorization_headers(self) -> list[str]:
        return [h["authorization"] for _, _, h in self.requests if "authorization" in h]

    # ------------------------------------------------------------------ Antworten
    def _log(self, route) -> None:
        request = route.request
        with self.lock:
            self.requests.append((request.method, request.url, {k.lower(): v for k, v in request.headers.items()}))

    def _json(self, route, status: int, body) -> None:
        headers = dict(CORS, **{"x-ratelimit-remaining": "55", "x-ratelimit-reset": str(int(dt.datetime.now(dt.timezone.utc).timestamp()) + 3600)})
        route.fulfill(status=status, content_type="application/json", body=json.dumps(body), headers=headers)

    def _api(self, route) -> None:
        self._log(route)
        request = route.request
        if request.method == "OPTIONS":
            route.fulfill(status=204, body="", headers=CORS)
            return
        if request.method != "GET":
            self._json(route, 404, {"message": "Not Found"})
            return
        path, _, query = request.url.split(API, 1)[1].partition("?")
        prefix = f"/repos/{self.repo}"
        if path.startswith(f"{prefix}/actions/workflows/") and path.endswith("/runs"):
            workflow = path.split("/actions/workflows/", 1)[1].rsplit("/runs", 1)[0]
            since = ""
            for part in query.split("&"):
                key, _, value = part.partition("=")
                if key == "created":
                    since = value.replace("%3E", ">").replace("%3D", "=").replace("%3A", ":").lstrip(">=")
            runs = [r for r in self.runs if r["workflow"] == workflow and (not since or r["created_at"] >= since)]
            self._json(route, 200, {"total_count": len(runs), "workflow_runs": list(reversed(runs))})
            return
        if path.startswith(f"{prefix}/actions/runs/"):
            rest = path.split("/actions/runs/", 1)[1]
            run_id, _, tail = rest.partition("/")
            run = next((r for r in self.runs if str(r["id"]) == run_id), None)
            if run is None:
                self._json(route, 404, {"message": "Not Found"})
            elif tail == "jobs":
                done = run["status"] == "completed"
                steps = [
                    {"name": "Set up job", "status": "completed", "conclusion": "success", "number": 1, "started_at": None, "completed_at": None},
                    {"name": "Kurse abrufen und liefern (sichtbare Aktien zuerst)", "status": "completed" if done else "in_progress", "conclusion": "success" if done else None, "number": 2,
                     "started_at": None, "completed_at": None},
                ]
                self._json(route, 200, {"jobs": [{"name": "lauf", "status": run["status"], "conclusion": run["conclusion"], "started_at": None, "completed_at": None, "steps": steps}]})
            else:
                self._json(route, 200, {k: v for k, v in run.items() if k != "workflow"})
            return
        if path.startswith(f"{prefix}/commits/"):
            branch = path.split("/commits/", 1)[1]
            sha = self.branches.get(branch)
            if sha is None:
                self._json(route, 422, {"message": "No commit found for SHA"})
            else:
                route.fulfill(status=200, content_type="application/vnd.github.sha", body=sha, headers=dict(CORS, **{"x-ratelimit-remaining": "54"}))
            return
        self._json(route, 404, {"message": "Not Found"})

    def _raw(self, route) -> None:
        self._log(route)
        request = route.request
        if request.method == "OPTIONS":
            route.fulfill(status=204, body="", headers=CORS)
            return
        rest = request.url.split(f"{RAW}/{self.repo}/", 1)[1] if f"{RAW}/{self.repo}/" in request.url else ""
        sha, _, path = rest.partition("/")
        data = self.commits.get(sha, {}).get(path.split("?", 1)[0])
        if data is None:
            route.fulfill(status=404, body="404: Not Found", headers=CORS)
        else:
            route.fulfill(status=200, content_type="application/octet-stream", body=data, headers=CORS)

    def _web(self, route) -> None:
        # Seite des Workflows auf GitHub (dort „Run workflow“) – im Test nur festhalten, welche geöffnet wurde
        with self.lock:
            self.opened.append(route.request.url)
        route.fulfill(status=200, content_type="text/html", body="<!doctype html><title>GitHub</title><p>Run workflow</p>")


def eingabe_aus_app(page, scope=None) -> str:
    """Die von der App vorbereitete Zeile – wie du sie auf GitHub einfügen würdest."""
    area = (scope or page).locator(".gh-start-line textarea").first
    return area.input_value()


def github_oeffnen(page, scope=None):
    """„Kopieren und GitHub öffnen“ antippen; die geöffnete Seite wieder schließen und zur App zurückkehren."""
    with page.context.expect_page() as popup:
        (scope or page).locator("a[target=_blank][href*='/actions/workflows/']").first.click()
    opened = popup.value
    opened.close()
    page.bring_to_front()


def zurueck_zur_app(page) -> None:
    """Rückkehr zur App: Sie sucht dann sofort nach dem Lauf (wie beim Wechsel zurück aus dem Browser-Tab)."""
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")


def work_dir(base: Path, name: str) -> Path:
    path = base / name
    path.mkdir(parents=True, exist_ok=True)
    return path
