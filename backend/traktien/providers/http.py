"""HTTP-Client mit Drosselung, Zeitlimits und Wiederholungen.

* Mindestabstand je Host (begrenzte Rate), zusätzlich serverseitige Hinweise
  ``Retry-After`` und ``X-RateLimit-Reset`` werden beachtet.
* Exponentielle Wiederholung mit Zufallsanteil bei 429, 5xx, Zeitüberschreitungen und
  Verbindungsabbrüchen; feste Obergrenze, kein endloser Prozess.
* Nach zu vielen aufeinanderfolgenden 429-Antworten wird ``ProviderThrottled``
  ausgelöst, damit der Lauf einen Checkpoint setzen und später fortsetzen kann.
* Für Yahoo kann optional ``curl_cffi`` mit Browser-TLS-Profil genutzt werden.
"""

from __future__ import annotations

import email.utils
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from ..util.log import get_logger, redact
from .base import ProviderThrottled

LOG = get_logger(__name__)
RETRY_STATUS = {429, 500, 502, 503, 504}


@dataclass
class HttpStats:
    requests: int = 0
    retries: int = 0
    throttled: int = 0
    errors: int = 0
    by_host: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"requests": self.requests, "retries": self.retries, "throttled": self.throttled, "errors": self.errors, "by_host": dict(self.by_host)}


@dataclass
class SimpleResponse:
    status_code: int
    headers: dict[str, str]
    content: bytes
    url: str

    def json(self) -> Any:
        import json

        return json.loads(self.content.decode("utf-8"))


class HttpClient:
    def __init__(
        self,
        *,
        user_agent: str = "TR-Aktienvergleich/1.0 (+private Analyse)",
        timeout: float = 25.0,
        max_retries: int = 5,
        backoff_base: float = 1.6,
        backoff_cap: float = 120.0,
        min_interval: dict[str, float] | None = None,
        impersonate: str | None = None,
        max_consecutive_429: int = 8,
        session: Any = None,
        sleep=time.sleep,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.min_interval = dict(min_interval or {})
        self.max_consecutive_429 = max_consecutive_429
        self.stats = HttpStats()
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_allowed: dict[str, float] = {}
        self._consecutive_429 = 0
        self._impersonate = impersonate
        self._session = session or self._make_session(impersonate)

    def clone(self, *, min_interval: dict[str, float] | None = None) -> "HttpClient":
        """Zweiter Client für parallele Abrufe (ab 1.12): eigene Sitzung mit den Cookies dieser Sitzung und
        gemeinsamer Drosselung – der Mindestabstand je Host gilt über alle Klone zusammen (gemeinsame Sperre und
        Zeitplan). Mit einer übergebenen Test-Sitzung teilen sich die Klone diese Sitzung."""
        twin = HttpClient(
            user_agent=self.user_agent,
            timeout=self.timeout,
            max_retries=self.max_retries,
            backoff_base=self.backoff_base,
            backoff_cap=self.backoff_cap,
            min_interval=self.min_interval if min_interval is None else min_interval,
            impersonate=self._impersonate,
            max_consecutive_429=self.max_consecutive_429,
            session=self._session_twin(),
            sleep=self._sleep,
        )
        twin._lock = self._lock
        twin._next_allowed = self._next_allowed
        return twin

    def _session_twin(self):
        """Neue Sitzung gleicher Art mit kopierten Cookies; unbekannte Sitzungsarten (Tests) werden geteilt."""
        module = type(self._session).__module__
        if module.startswith("curl_cffi") or module.startswith("requests"):
            twin = self._make_session(self._impersonate if module.startswith("curl_cffi") else None)
            try:
                twin.cookies.update(self._session.cookies)
            except Exception:  # pragma: no cover - je nach Bibliotheksversion; ohne Cookies holt der Klon sie selbst
                try:
                    for cookie in self._session.cookies.jar:
                        twin.cookies.jar.set_cookie(cookie)
                except Exception:
                    LOG.info("Cookies nicht übertragbar – der parallele Abruf meldet sich selbst an")
            return twin
        return self._session

    @staticmethod
    def _make_session(impersonate: str | None):
        if impersonate:
            try:
                from curl_cffi import requests as curl_requests  # type: ignore

                return curl_requests.Session(impersonate=impersonate)
            except Exception:  # pragma: no cover - abhängig von der Installation
                LOG.warning("curl_cffi nicht verfügbar – normaler HTTP-Client wird verwendet")
        import requests

        return requests.Session()

    def _throttle(self, host: str) -> None:
        interval = self.min_interval.get(host, 0.0)
        if interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed.get(host, 0.0) - now
            self._next_allowed[host] = max(now, self._next_allowed.get(host, 0.0)) + interval
        if wait > 0:
            self._sleep(wait)

    def _retry_after(self, headers: dict[str, str]) -> float | None:
        lowered = {k.lower(): v for k, v in headers.items()}
        value = lowered.get("retry-after")
        if value:
            value = value.strip()
            if value.isdigit():
                return float(value)
            try:
                parsed = email.utils.parsedate_to_datetime(value)
                return max(0.0, parsed.timestamp() - time.time())
            except (TypeError, ValueError):
                return None
        reset = lowered.get("x-ratelimit-reset")
        if reset:
            try:
                number = float(reset)
                return number if number < 3600 else max(0.0, number - time.time())
            except ValueError:
                return None
        return None

    def _backoff(self, attempt: int) -> float:
        base = min(self.backoff_cap, self.backoff_base ** attempt)
        return base * (0.5 + random.random())

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> SimpleResponse:
        host = urlparse(url).netloc
        merged_headers = {"User-Agent": self.user_agent, "Accept": "application/json, */*"}
        if self._impersonate:
            merged_headers.pop("User-Agent")
        merged_headers.update(headers or {})
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._throttle(host)
            self.stats.requests += 1
            self.stats.by_host[host] = self.stats.by_host.get(host, 0) + 1
            try:
                response = self._session.request(
                    method, url, params=params, json=json_body, headers=merged_headers, timeout=self.timeout
                )
            except Exception as exc:  # Zeitüberschreitung oder Verbindungsfehler
                last_error = exc
                self.stats.errors += 1
                if attempt >= self.max_retries:
                    break
                self.stats.retries += 1
                delay = self._backoff(attempt + 1)
                LOG.info("Netzwerkfehler bei %s (%s) – neuer Versuch in %.1fs", redact(url), type(exc).__name__, delay)
                self._sleep(delay)
                continue

            status = int(response.status_code)
            resp_headers = {str(k): str(v) for k, v in dict(response.headers).items()}
            if status == 429:
                self.stats.throttled += 1
                self._consecutive_429 += 1
                if self._consecutive_429 >= self.max_consecutive_429:
                    raise ProviderThrottled(f"Dauerhafte Drosselung durch {host}")
            else:
                self._consecutive_429 = 0
            if status in RETRY_STATUS and attempt < self.max_retries:
                self.stats.retries += 1
                delay = self._retry_after(resp_headers)
                delay = self._backoff(attempt + 1) if delay is None else min(delay + random.random(), self.backoff_cap)
                LOG.info("HTTP %s von %s – neuer Versuch in %.1fs", status, host, delay)
                self._sleep(delay)
                continue
            if status == 429:
                raise ProviderThrottled(f"Drosselung durch {host} nach {attempt + 1} Versuchen")
            return SimpleResponse(status, resp_headers, bytes(response.content), str(getattr(response, "url", url)))

        raise ConnectionError(f"Anfrage an {host} endgültig fehlgeschlagen: {type(last_error).__name__ if last_error else 'unbekannt'}")

    def get(self, url: str, **kwargs) -> SimpleResponse:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> SimpleResponse:
        return self.request("POST", url, **kwargs)
