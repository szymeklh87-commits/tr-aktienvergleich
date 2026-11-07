"""Website auf GitHub Pages bereitstellen – mit längerer Wartezeit und eigener Kennung je Versuch (ab 1.20.5).

Warum nicht mehr ``actions/deploy-pages``: Seit dem 06.11.2026 braucht GitHub Pages zeitweise länger als zehn Minuten für eine
Bereitstellung („deployment_queued“, „syncing_files“), auch in anderen Repositorys. ``deploy-pages`` wartet höchstens zehn
Minuten, bricht die Bereitstellung danach ab, und jeder weitere Versuch mit demselben Commit trägt dieselbe Kennung (die
Commit-Kennung) – am 07.11.2026 lieferte GitHub für sie danach nur noch einen leeren Status (drei Läufe, 04:20, 04:36 und
05:04 UTC, je 10 Minuten bis zum Abbruch). Dieses Skript

* legt die Bereitstellung über die Schnittstelle von GitHub an (wie ``deploy-pages``: Artefakt, OIDC-Token, Version),
  mit einer **eigenen Version je Lauf und Versuch** – ein früherer, hängengebliebener Versuch stört so nicht,
* wartet bis ``WARTEN_MINUTEN`` (Standard 20) auf das Ergebnis und fragt in wachsenden Abständen nach,
* versucht es nach einem endgültigen Fehler von GitHub **genau einmal** erneut (neue Kennung), nie öfter,
* bricht nach Ablauf der Wartezeit ab (wie ``deploy-pages``, damit keine Bereitstellung im Hintergrund hängen bleibt) und
  meldet den Schritt rot – nichts wird als erfolgreich gemeldet, was GitHub nicht bestätigt hat.

Gerechnete Kurse gehen dabei nicht verloren: Der Zustand ist vorher schon im Release „datenstand“ gesichert, und der Job
„Kennzahlen“ stellt die Website danach ein zweites Mal bereit (eigener Versuch, eigene Kennung).

Eingaben (Umgebung): ``GITHUB_TOKEN`` (Berechtigung ``pages: write``), ``ARTEFAKT_ID`` (Ausgabe von
``actions/upload-artifact``), ``WARTEN_MINUTEN``; von GitHub Actions: ``GITHUB_REPOSITORY``, ``GITHUB_SHA``,
``GITHUB_RUN_ID``, ``GITHUB_RUN_ATTEMPT``, ``GITHUB_API_URL``, ``ACTIONS_ID_TOKEN_REQUEST_URL`` und
``ACTIONS_ID_TOKEN_REQUEST_TOKEN`` (Berechtigung ``id-token: write``). Ausgaben (``GITHUB_OUTPUT``): ``page_url``,
``status``. Kein Schlüssel und kein Token erscheint im Protokoll.

Nur Standardbibliothek (läuft auch ohne die Umgebung des Projekts). Rückgabe: 0 bereitgestellt, 1 nicht bereitgestellt.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

API_VERSION = "2022-11-28"
SUCCESS = "succeed"
# Endgültige Fehler laut GitHub (wie in deploy-pages); danach höchstens ein neuer Versuch
FINAL_ERRORS = {
    "deployment_failed": "Bereitstellung gescheitert",
    "deployment_content_failed": "Inhalt nicht bereitstellbar (Verweise, harte Links oder mehr als 10 GB)",
    "deployment_cancelled": "Bereitstellung abgebrochen",
    "deployment_lost": "GitHub hat kein Endergebnis gemeldet",
}
MAX_CREATES = 2            # erster Versuch + genau ein neuer nach einem endgültigen Fehler
MAX_POLL_ERRORS = 10       # Abfragefehler in Folge, dann Abbruch
FIRST_INTERVAL_S = 5.0
MAX_INTERVAL_S = 30.0
RETRY_PAUSE_S = 60.0


class DeployError(Exception):
    """Fehler mit einer Meldung ohne Token und ohne Antworttext von GitHub."""


@dataclass
class HttpResult:
    status: int
    data: dict


Opener = Callable[[urllib.request.Request, float], HttpResult]


def _default_open(request: urllib.request.Request, timeout: float) -> HttpResult:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - feste https-Adressen von GitHub
            raw = response.read()
            try:
                data = json.loads(raw) if raw else {}
            except ValueError:
                data = {}
            return HttpResult(response.status, data if isinstance(data, dict) else {})
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read() or b"{}")
        except ValueError:
            body = {}
        return HttpResult(exc.code, body if isinstance(body, dict) else {})


@dataclass
class Settings:
    token: str
    repository: str
    sha: str
    run_id: str
    run_attempt: str
    api_url: str
    artifact_id: int
    oidc_url: str
    oidc_token: str
    wait_minutes: float = 20.0

    @classmethod
    def from_env(cls, env: dict) -> "Settings":
        missing = [name for name in ("GITHUB_TOKEN", "GITHUB_REPOSITORY", "GITHUB_SHA", "ARTEFAKT_ID", "ACTIONS_ID_TOKEN_REQUEST_URL",
                                     "ACTIONS_ID_TOKEN_REQUEST_TOKEN") if not env.get(name)]
        if missing:
            raise DeployError("Angaben fehlen: " + ", ".join(missing) + (" (Berechtigung „id-token: write“?)" if any(m.startswith("ACTIONS_ID") for m in missing) else ""))
        try:
            artifact_id = int(env["ARTEFAKT_ID"])
        except ValueError:
            raise DeployError("ARTEFAKT_ID ist keine Zahl") from None
        return cls(
            token=env["GITHUB_TOKEN"],
            repository=env["GITHUB_REPOSITORY"],
            sha=env["GITHUB_SHA"],
            run_id=env.get("GITHUB_RUN_ID", "0"),
            run_attempt=env.get("GITHUB_RUN_ATTEMPT", "1"),
            api_url=env.get("GITHUB_API_URL", "https://api.github.com").rstrip("/"),
            artifact_id=artifact_id,
            oidc_url=env["ACTIONS_ID_TOKEN_REQUEST_URL"],
            oidc_token=env["ACTIONS_ID_TOKEN_REQUEST_TOKEN"],
            wait_minutes=float(env.get("WARTEN_MINUTEN") or 20),
        )

    def build_version(self, attempt: int) -> str:
        """Eigene Version je Lauf und Versuch: „<Commit>-<Lauf>-<Wiederholung>-<Versuch>“."""
        return f"{self.sha}-{self.run_id}-{self.run_attempt}-{attempt}"


@dataclass
class Report:
    lines: list[str] = field(default_factory=list)
    status: str = "nicht_bereitgestellt"
    page_url: str = ""

    def log(self, text: str) -> None:
        self.lines.append(text)
        print(text, flush=True)


class Deployer:
    def __init__(self, settings: Settings, *, opener: Opener = _default_open, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.s = settings
        self.open = opener
        self.clock = clock
        self.sleep = sleep
        self.report = Report()

    # ---------------------------------------------------------------- Schnittstelle

    def _api(self, method: str, path: str, body: dict | None = None) -> HttpResult:
        request = urllib.request.Request(
            f"{self.s.api_url}/repos/{self.s.repository}{path}",
            data=None if body is None else json.dumps(body).encode("utf-8"),
            method=method,
            headers={"Authorization": f"Bearer {self.s.token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION,
                     "Content-Type": "application/json", "User-Agent": "tr-aktienvergleich-pages"},
        )
        try:
            return self.open(request, 60.0)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DeployError(f"Verbindung zu GitHub fehlgeschlagen ({type(exc).__name__})") from None

    def _oidc(self) -> str:
        request = urllib.request.Request(self.s.oidc_url, headers={"Authorization": f"Bearer {self.s.oidc_token}", "Accept": "application/json",
                                                                    "User-Agent": "tr-aktienvergleich-pages"})
        try:
            result = self.open(request, 60.0)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DeployError(f"OIDC-Token nicht erhalten ({type(exc).__name__})") from None
        value = result.data.get("value") if result.status == 200 else None
        if not value:
            raise DeployError(f"OIDC-Token nicht erhalten (HTTP {result.status})")
        return str(value)

    def create(self, attempt: int) -> str:
        """Bereitstellung anlegen; Rückgabe: Kennung. Lehnt GitHub die eigene Version ab (400/422), dann mit der Commit-Kennung."""
        oidc = self._oidc()
        versions = [self.s.build_version(attempt), self.s.sha]
        for k, version in enumerate(versions):
            for tries in range(3):
                result = self._api("POST", "/pages/deployments", {"artifact_id": self.s.artifact_id, "pages_build_version": version, "oidc_token": oidc})
                if result.status in (200, 201):
                    deployment_id = str(result.data.get("id") or version)
                    self.report.page_url = str(result.data.get("page_url") or self.report.page_url)
                    self.report.log(f"Bereitstellung angelegt (Versuch {attempt}, Version {'eigene' if k == 0 else 'Commit'}): Kennung {deployment_id}")
                    return deployment_id
                if result.status in (400, 422) and k == 0:
                    self.report.log(f"GitHub lehnt die eigene Version ab (HTTP {result.status}) – neuer Versuch mit der Commit-Kennung")
                    break
                if result.status >= 500 or result.status == 429:
                    pause = 30.0 * (2 ** tries)
                    self.report.log(f"Anlegen: HTTP {result.status} – neuer Versuch in {pause:.0f} s")
                    self.sleep(pause)
                    continue
                raise DeployError(f"Bereitstellung nicht angelegt (HTTP {result.status}{': ' + str(result.data.get('message'))[:120] if result.data.get('message') else ''})")
            else:
                raise DeployError("Bereitstellung nicht angelegt (GitHub antwortet wiederholt mit einem Serverfehler)")
        raise DeployError("Bereitstellung nicht angelegt")

    def cancel(self, deployment_id: str) -> None:
        try:
            result = self._api("POST", f"/pages/deployments/{deployment_id}/cancel")
            self.report.log(f"Bereitstellung {deployment_id} abgebrochen (HTTP {result.status})")
        except DeployError as exc:
            self.report.log(f"Abbruch nicht bestätigt: {exc}")

    # ---------------------------------------------------------------- Ablauf

    def run(self) -> int:
        started = self.clock()
        deadline = started + self.s.wait_minutes * 60.0
        attempt = 1
        try:
            deployment_id = self.create(attempt)
        except DeployError as exc:
            self.report.log(f"::error title=Website nicht bereitgestellt::{exc}")
            return 1
        interval = FIRST_INTERVAL_S
        last_status = None
        errors = 0
        while True:
            self.sleep(interval)
            elapsed_min = (self.clock() - started) / 60.0
            try:
                result = self._api("GET", f"/pages/deployments/{deployment_id}")
            except DeployError as exc:
                result = None
                error_text = str(exc)
            else:
                error_text = f"HTTP {result.status}" if result.status != 200 else ""
            if result is None or result.status != 200:
                errors += 1
                self.report.log(f"Status nicht abrufbar ({error_text}), {errors}/{MAX_POLL_ERRORS}")
                if errors >= MAX_POLL_ERRORS:
                    self.cancel(deployment_id)
                    self.report.log(f"::error title=Website nicht bereitgestellt::Status {MAX_POLL_ERRORS}-mal nicht abrufbar")
                    return 1
            else:
                errors = 0
                status = str(result.data.get("status") or "")
                if status != last_status:
                    self.report.log(f"{elapsed_min:4.1f} min: Status {status or '(leer)'}")
                    last_status = status
                if status == SUCCESS:
                    self.report.status = "bereitgestellt"
                    self.report.log(f"::notice title=Website bereitgestellt::nach {elapsed_min:.1f} min (Versuch {attempt})")
                    return 0
                if status in FINAL_ERRORS:
                    if attempt < MAX_CREATES and self.clock() + RETRY_PAUSE_S < deadline:
                        self.report.log(f"{FINAL_ERRORS[status]} – genau ein neuer Versuch mit neuer Kennung in {RETRY_PAUSE_S:.0f} s")
                        self.sleep(RETRY_PAUSE_S)
                        attempt += 1
                        try:
                            deployment_id = self.create(attempt)
                        except DeployError as exc:
                            self.report.log(f"::error title=Website nicht bereitgestellt::{exc}")
                            return 1
                        interval, last_status = FIRST_INTERVAL_S, None
                        continue
                    self.report.log(f"::error title=Website nicht bereitgestellt::{FINAL_ERRORS[status]} (Versuch {attempt})")
                    return 1
            if self.clock() >= deadline:
                self.cancel(deployment_id)
                self.report.log(f"::error title=Website nicht bereitgestellt::GitHub Pages hat die Bereitstellung nach {self.s.wait_minutes:.0f} min nicht "
                                f"abgeschlossen (letzter Status {last_status or '(leer)'}); der gerechnete Stand ist gesichert, der nächste Job oder Lauf "
                                f"stellt ihn erneut bereit")
                return 1
            interval = min(MAX_INTERVAL_S, interval * 1.5, max(1.0, deadline - self.clock()))


def write_outputs(report: Report, path: str | None) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"page_url={report.page_url}\n")
        handle.write(f"status={report.status}\n")


def main(env: dict | None = None) -> int:
    env = dict(os.environ if env is None else env)
    try:
        settings = Settings.from_env(env)
    except DeployError as exc:
        print(f"::error title=Website nicht bereitgestellt::{exc}", flush=True)
        return 1
    deployer = Deployer(settings)
    try:
        code = deployer.run()
    except Exception as exc:  # unerwarteter Fehler: rot melden, ohne Einzelheiten aus Antworten oder Umgebung
        deployer.report.log(f"::error title=Website nicht bereitgestellt::unerwarteter Fehler ({type(exc).__name__})")
        code = 1
    write_outputs(deployer.report, env.get("GITHUB_OUTPUT"))
    return code


if __name__ == "__main__":
    sys.exit(main())
