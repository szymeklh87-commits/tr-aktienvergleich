"""Wahrscheinlichkeit für steigende Kurse in 1 bis 30 Handelstagen (ab 1.25.0, ``wahrscheinlichkeit-1``).

Auftrag vom 07.11.2026 (17:58 und 19:06 Uhr): Wahrscheinlichkeiten nur nach einem Test ohne Zukunftsdaten, mit Brier-Wert,
Log-Loss, Kalibrierung, Fallzahl und Fehler je Horizont; ohne ausreichende Güte „Nicht ausreichend zuverlässig“; höchstens
drei Gründe; eine hohe Wahrscheinlichkeit ist nie allein ein Kaufsignal.

Vorgehen je Horizont h (Handelstage der Aktie, kumuliert: Schlusskurs nach h Sitzungen über dem heutigen):
* Merkmale je Aktie und Tag nur aus Daten bis zu diesem Tag (Renditen 1/5/20/60 Tage, Abstand zu 20-/50-Tage-Linie und
  20-Tage-Hoch, RSI, Umsatz zum Durchschnitt, Tagesspanne, Marktlage = Median der 20-Tage-Rendite aller Aktien mit
  Mindestumsatz). Nur Aktien-Tage mit nachgewiesenem Ø Tagesumsatz ab 10 Mio. USD.
* Logistische Regression (L2), standardisiert mit Werten des Trainingszeitraums.
* Walk-forward: die letzten 40 % der Handelstage in vier Testblöcken; trainiert wird jeweils nur mit Fällen, deren Ergebnis
  vor Beginn des Testblocks feststand (Abstand h Sitzungen). Vergleich mit der Grundrate des Trainingszeitraums.
* Zuverlässig nur mit mindestens 3.000 Testfällen, einer Brier-Verbesserung gegenüber der Grundrate, die mindestens zwei
  Standardfehler beträgt (Standardfehler aus den Tagesmitteln, weil Fälle desselben Tages zusammenhängen), einem
  Kalibrierungsfehler von höchstens 3 Prozentpunkten und keiner Verschlechterung in steigenden oder fallenden Märkten.
* Für die Anzeige: Modell auf allen Fällen mit bekanntem Ergebnis, Vorhersage zum letzten Kurstag. Erwartete Veränderung
  und Spanne kommen aus den Testfällen mit ähnlicher Wahrscheinlichkeit (Kalibrierungsklasse), nicht aus dem Modell.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

VERSION = "wahrscheinlichkeit-1"
HORIZONS = tuple(range(1, 31))
SHOWN = (1, 5, 10, 20, 30)
REASON_HORIZON = 10
FOLDS = 4
TEST_SHARE = 0.4
L2 = 1.0
TRAIN_STEP = 2  # jeder zweite Tag im Training (überlappende Ergebnisse tragen kaum zusätzliche Information)
MIN_TEST = 3000
MIN_SKILL = 0.001
MIN_T = 2.0  # Verbesserung gegenüber der Grundrate mindestens zwei Standardfehler (je Testtag gemittelt)
MAX_ECE = 0.03
MIN_TRAIN = 2000
BINS = 10
MIN_TURNOVER_USD = 10_000_000.0

FEATURES = (
    ("r1", "Veränderung am letzten Tag"),
    ("r5", "Veränderung 5 Tage"),
    ("r20", "Veränderung 20 Tage"),
    ("r60", "Veränderung 60 Tage"),
    ("d_sma20", "Abstand zur 20-Tage-Linie"),
    ("d_sma50", "Abstand zur 50-Tage-Linie"),
    ("d_high20", "Abstand zum 20-Tage-Hoch"),
    ("rsi", "RSI"),
    ("rvol", "Umsatz zum 20-Tage-Durchschnitt"),
    ("atr", "übliche Tagesspanne"),
    ("markt", "Marktlage (Median 20 Tage)"),
)
PERCENT = {"r1", "r5", "r20", "r60", "d_sma20", "d_sma50", "d_high20", "atr", "markt"}

REGEL = (
    "Logistische Regression je Horizont aus elf Kursmerkmalen (Renditen 1/5/20/60 Tage, Abstand zu 20-/50-Tage-Linie und "
    "20-Tage-Hoch, RSI, Umsatz zum Durchschnitt, Tagesspanne, Marktlage), nur Aktien mit Ø Tagesumsatz ab 10 Mio. USD. "
    "Geprüft ohne Zukunftsdaten in vier Testblöcken (letzte 40 % der Handelstage). Angezeigt nur, wenn der Brier-Wert "
    "nachweisbar besser ist als die Grundrate (mindestens zwei Standardfehler, aus Tagesmitteln), der Kalibrierungsfehler "
    "höchstens 3 Prozentpunkte beträgt, mindestens 3.000 Testfälle vorliegen und das Modell weder in steigenden noch in "
    "fallenden Märkten schlechter ist als die Grundrate."
)


@dataclass
class StockPanel:
    """Kursreihe einer Aktie mit den Merkmalen je Sitzung (Index wie ``days``)."""

    isin: str
    days: np.ndarray
    close: np.ndarray
    feats: dict[str, np.ndarray]
    liquid: np.ndarray  # bool je Sitzung: Ø Tagesumsatz ab 10 Mio. USD nachgewiesen


@dataclass
class Result:
    payload: dict
    probabilities: dict[int, list[int | None]] = field(default_factory=dict)  # h → je Aktie (Reihenfolge der Eingabe)
    reasons: list[list[str]] = field(default_factory=list)


def _ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where((b > 0) & np.isfinite(a) & np.isfinite(b), a / b - 1.0, np.nan)


def stock_panel(isin: str, days, ts, turnover_usd: np.ndarray) -> StockPanel:
    """Merkmale aus einer ``signals.TechSeries`` (Marktlage wird später ergänzt)."""
    close = np.asarray(ts.close, dtype=np.float64)
    feats = {
        "r1": np.asarray(ts.r1, dtype=np.float64),
        "r5": np.asarray(ts.r5, dtype=np.float64),
        "r20": np.asarray(ts.r20, dtype=np.float64),
        "r60": np.asarray(ts.r60, dtype=np.float64),
        "d_sma20": _ratio(close, np.asarray(ts.sma20, dtype=np.float64)),
        "d_sma50": _ratio(close, np.asarray(ts.sma50, dtype=np.float64)),
        "d_high20": _ratio(close, np.asarray(ts.high20, dtype=np.float64)),
        "rsi": np.asarray(ts.rsi, dtype=np.float64),
        "rvol": np.log(np.clip(np.asarray(ts.rvol, dtype=np.float64), 0.05, 20.0)),
        "atr": np.asarray(ts.atr_pct, dtype=np.float64),
    }
    usd = np.asarray(turnover_usd, dtype=np.float64)
    liquid = np.isfinite(usd) & (usd >= MIN_TURNOVER_USD)
    return StockPanel(isin=isin, days=np.asarray(days, dtype=np.int64), close=close, feats=feats, liquid=liquid)


def _market(stocks: list[StockPanel]) -> dict[int, float]:
    by_day: dict[int, list[float]] = {}
    for s in stocks:
        r20 = s.feats["r20"]
        for k in np.nonzero(s.liquid & np.isfinite(r20))[0].tolist():
            by_day.setdefault(int(s.days[k]), []).append(float(r20[k]))
    return {d: float(np.median(v)) for d, v in by_day.items() if len(v) >= 5}


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35.0, 35.0)))


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = L2, iters: int = 30) -> np.ndarray:
    """Newton-Verfahren mit L2-Strafe (ohne Achsenabschnitt); X standardisiert."""
    n, d = X.shape
    Xb = np.hstack([np.ones((n, 1)), X])
    w = np.zeros(d + 1)
    w[0] = math.log(max(y.mean(), 1e-6) / max(1.0 - y.mean(), 1e-6))
    penalty = np.r_[0.0, np.full(d, l2)]
    for _ in range(iters):
        p = _sigmoid(Xb @ w)
        g = Xb.T @ (p - y) + penalty * w
        H = (Xb * (p * (1.0 - p))[:, None]).T @ Xb + np.diag(penalty + 1e-9)
        step = np.linalg.solve(H, g)
        w -= step
        if float(np.max(np.abs(step))) < 1e-7:
            break
    return w


def _predict(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    return _sigmoid(w[0] + X @ w[1:])


def _brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def _logloss(p: np.ndarray, y: np.ndarray) -> float:
    q = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def calibration_bins(p: np.ndarray, y: np.ndarray, ret: np.ndarray, bins: int = BINS) -> list[dict]:
    """Klassen gleicher Breite der vorhergesagten Wahrscheinlichkeit (nur besetzte): Ø Vorhersage, beobachteter Anteil,
    Zahl, Ø Veränderung und mittlere Hälfte der Veränderungen."""
    edges = np.linspace(0.0, 1.0, bins + 1)
    out = []
    which = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    for b in range(bins):
        m = which == b
        n = int(m.sum())
        if n == 0:
            continue
        r = ret[m]
        out.append({
            "von": round(float(edges[b]), 2),
            "bis": round(float(edges[b + 1]), 2),
            "p": round(float(p[m].mean()), 4),
            "beob": round(float(y[m].mean()), 4),
            "n": n,
            "mittel": round(float(r.mean()), 5),
            "q25": round(float(np.quantile(r, 0.25)), 5),
            "q75": round(float(np.quantile(r, 0.75)), 5),
        })
    return out


def _ece(bins: list[dict], n: int) -> float:
    return float(sum(b["n"] * abs(b["p"] - b["beob"]) for b in bins) / n) if n else 1.0


@dataclass
class _Samples:
    X: np.ndarray  # (S, F) roh
    pos: np.ndarray  # (S,) Index des Tages in der gemeinsamen Tagesliste
    stock: np.ndarray  # (S,) Index der Aktie
    fwd: dict[int, np.ndarray]  # h → Veränderung bis h Sitzungen später (NaN = noch unbekannt)
    days: np.ndarray  # gemeinsame Tagesliste (sortiert)


def _samples(stocks: list[StockPanel], market: dict[int, float]) -> _Samples:
    keys = [k for k, _ in FEATURES]
    all_days = sorted({int(d) for s in stocks for d in s.days.tolist()})
    index = {d: i for i, d in enumerate(all_days)}
    xs, pos, who = [], [], []
    fwd: dict[int, list[np.ndarray]] = {h: [] for h in HORIZONS}
    for si, s in enumerate(stocks):
        n = len(s.close)
        mk = np.array([market.get(int(d), np.nan) for d in s.days.tolist()], dtype=np.float64)
        cols = [s.feats[k] if k != "markt" else mk for k in keys]
        X = np.column_stack(cols) if n else np.zeros((0, len(keys)))
        ok = s.liquid & np.all(np.isfinite(X), axis=1) & np.isfinite(s.close) & (s.close > 0)
        rows = np.nonzero(ok)[0]
        if not len(rows):
            continue
        xs.append(X[rows].astype(np.float32))  # float32: halber Speicher bei rund einer Million Aktien-Tagen
        pos.append(np.array([index[int(d)] for d in s.days[rows].tolist()], dtype=np.int64))
        who.append(np.full(len(rows), si, dtype=np.int64))
        for h in HORIZONS:
            later = rows + h
            ret = np.full(len(rows), np.nan)
            inside = later < n
            ret[inside] = s.close[later[inside]] / s.close[rows[inside]] - 1.0
            fwd[h].append(ret.astype(np.float32))
    if not xs:
        return _Samples(np.zeros((0, len(keys))), np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64), {h: np.zeros(0) for h in HORIZONS}, np.array(all_days))
    return _Samples(np.vstack(xs), np.concatenate(pos), np.concatenate(who), {h: np.concatenate(v) for h, v in fwd.items()}, np.array(all_days))


def _standardize(X: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return np.clip((X - mean) / std, -5.0, 5.0)


def _scaler(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    return mean, np.where(std > 1e-12, std, 1.0)


def walk_forward(sm: _Samples, h: int) -> list[tuple[np.ndarray, np.ndarray, float]]:
    """Testblöcke eines Horizonts: (Maske der Testfälle, Vorhersage, Grundrate des Trainings). Trainiert wird nur mit Fällen,
    deren Ergebnis vor Beginn des Testblocks feststand (Sitzung + h vor dem ersten Testtag)."""
    ret = sm.fwd[h]
    known = np.isfinite(ret)
    y_all = (ret > 0).astype(np.float64)
    n_days = len(sm.days)
    first_test = int(n_days * (1.0 - TEST_SHARE))
    bounds = np.linspace(first_test, n_days, FOLDS + 1).astype(int)
    out = []
    for k in range(FOLDS):
        a, b = int(bounds[k]), int(bounds[k + 1])
        train = known & (sm.pos + h < a) & (sm.pos % TRAIN_STEP == 0)
        test = known & (sm.pos >= a) & (sm.pos < b)
        if train.sum() < MIN_TRAIN or not test.any():
            continue
        mean, std = _scaler(sm.X[train])
        w = fit_logistic(_standardize(sm.X[train], mean, std), y_all[train])
        out.append((test, _predict(w, _standardize(sm.X[test], mean, std)), float(y_all[train].mean())))
    return out


def evaluate_horizon(sm: _Samples, h: int) -> dict:
    """Walk-forward-Test eines Horizonts: Kennzahlen der Testfälle und das Urteil „zuverlässig“."""
    ret = sm.fwd[h]
    y_all = (ret > 0).astype(np.float64)
    preds, ys, rets, mkts, base_preds, days = [], [], [], [], [], []
    for test, p_test, base_rate in walk_forward(sm, h):
        preds.append(p_test)
        base_preds.append(np.full(int(test.sum()), base_rate))
        ys.append(y_all[test])
        rets.append(ret[test])
        mkts.append(sm.X[test][:, -1])
        days.append(sm.pos[test])
    if not preds:
        return {"n": 0, "zuverlaessig": False, "grund": "zu kurze Kurshistorie für einen Test ohne Zukunftsdaten"}
    p = np.concatenate(preds)
    y = np.concatenate(ys)
    r = np.concatenate(rets)
    base = np.concatenate(base_preds)
    mk = np.concatenate(mkts)
    brier, brier_base = _brier(p, y), _brier(base, y)
    skill = 1.0 - brier / brier_base if brier_base > 0 else 0.0
    # Verbesserung je Fall, je Testtag gemittelt (Fälle eines Tages hängen zusammen) → Standardfehler über die Tage
    gain = (base - y) ** 2 - (p - y) ** 2
    pos = np.concatenate(days)
    uniq, inv = np.unique(pos, return_inverse=True)
    per_day = np.bincount(inv, weights=gain) / np.bincount(inv)
    t_value = float(per_day.mean() / (per_day.std(ddof=1) / math.sqrt(len(per_day)))) if len(per_day) > 2 and per_day.std(ddof=1) > 0 else 0.0
    bins = calibration_bins(p, y, r)
    ece = _ece(bins, len(p))
    regimes = {}
    for name, m in (("steigend", mk > 0), ("fallend", mk <= 0)):
        if m.sum() >= 200:
            b1, b0 = _brier(p[m], y[m]), _brier(base[m], y[m])
            regimes[name] = {"n": int(m.sum()), "skill": round(1.0 - b1 / b0, 4) if b0 > 0 else 0.0, "beob": round(float(y[m].mean()), 4)}
        else:
            regimes[name] = {"n": int(m.sum()), "skill": None, "beob": round(float(y[m].mean()), 4) if m.any() else None}
    reasons = []
    if len(p) < MIN_TEST:
        reasons.append(f"nur {len(p)} Testfälle (mindestens {MIN_TEST})")
    if skill <= 0:
        reasons.append("nicht besser als die Grundrate")
    elif skill < MIN_SKILL or t_value < MIN_T:
        reasons.append("Verbesserung gegenüber der Grundrate nicht gesichert")
    if ece > MAX_ECE:
        reasons.append("Wahrscheinlichkeiten weichen zu stark von den beobachteten Häufigkeiten ab")
    if any(v["skill"] is not None and v["skill"] < 0 for v in regimes.values()):
        reasons.append("in steigenden oder fallenden Märkten schlechter als die Grundrate")
    return {
        "n": int(len(p)),
        "grundrate": round(float(base.mean()), 4),
        "beob": round(float(y.mean()), 4),
        "brier": round(brier, 5),
        "brier_grundrate": round(brier_base, 5),
        "skill": round(skill, 4),
        "t": round(t_value, 2),
        "testtage": int(len(per_day)),
        "logloss": round(_logloss(p, y), 5),
        "logloss_grundrate": round(_logloss(base, y), 5),
        "ece": round(ece, 4),
        "treffer": round(float(((p > 0.5) == (y > 0.5)).mean()), 4),
        "maerkte": regimes,
        "klassen": bins,
        "zuverlaessig": not reasons,
        "grund": "; ".join(reasons) if reasons else None,
    }


def _reason_texts(w: np.ndarray, x_std: np.ndarray, x_raw: np.ndarray) -> list[str]:
    contrib = w[1:] * x_std
    order = np.argsort(-np.abs(contrib))
    out = []
    for j in order[:3].tolist():
        if abs(float(contrib[j])) < 0.02:
            continue
        key, label = FEATURES[j]
        raw = float(x_raw[j])
        if key in PERCENT:
            value = f"{raw * 100:+.1f} %".replace(".", ",").replace("-", "−")
        elif key == "rvol":
            value = f"{math.exp(raw):.1f}-fach".replace(".", ",")
        else:
            value = f"{raw:.0f}"
        direction = "spricht für Anstieg" if contrib[j] > 0 else "spricht für Rückgang"
        out.append(f"{label} {value} – {direction}")
    return out


def compute(stocks: list[StockPanel], *, cutoff_day: int | None = None) -> Result:
    """Test aller Horizonte und Vorhersage zum letzten Kurstag je Aktie (Reihenfolge wie ``stocks``)."""
    market = _market(stocks)
    sm = _samples(stocks, market)
    quality: dict[str, dict] = {}
    probabilities: dict[int, list[int | None]] = {}
    base_rates: dict[str, float | None] = {}
    reasons: list[list[str]] = [[] for _ in stocks]
    # letzte Sitzung je Aktie (nur wenn sie zum Mindestumsatz und zu vollständigen Merkmalen gehört)
    latest: dict[int, int] = {}
    for i in range(len(sm.pos)):
        s = int(sm.stock[i])
        if s not in latest or sm.pos[i] > sm.pos[latest[s]]:
            latest[s] = i
    newest = int(sm.pos.max()) if len(sm.pos) else -1
    for s in list(latest):
        idx_stock = latest[s]
        last_day_stock = int(stocks[s].days[-1])
        if int(sm.days[sm.pos[idx_stock]]) != last_day_stock:
            del latest[s]  # letzte Sitzung ohne Mindestumsatz oder ohne vollständige Merkmale: keine Vorhersage
    test_days = None
    if len(sm.days):
        first_test = int(len(sm.days) * (1.0 - TEST_SHARE))
        test_days = (int(sm.days[first_test]) if first_test < len(sm.days) else None, int(sm.days[-1]))
    for h in HORIZONS:
        q = evaluate_horizon(sm, h)
        quality[str(h)] = q
        ret = sm.fwd[h]
        known = np.isfinite(ret)
        column: list[int | None] = [None] * len(stocks)
        base_rates[str(h)] = round(float((ret[known] > 0).mean()), 4) if known.any() else None
        if q.get("zuverlaessig") and known.sum() >= MIN_TRAIN and latest:
            train = known & (sm.pos % TRAIN_STEP == 0)
            mean, std = _scaler(sm.X[train])
            y = (ret[train] > 0).astype(np.float64)
            w = fit_logistic(_standardize(sm.X[train], mean, std), y)
            rows = np.array(list(latest.values()), dtype=np.int64)
            xs = _standardize(sm.X[rows], mean, std)
            p = _predict(w, xs)
            for (s, _), value in zip(latest.items(), p.tolist()):
                column[s] = int(round(100.0 * value))
            if h == REASON_HORIZON:
                for k, (s, row) in enumerate(latest.items()):
                    reasons[s] = _reason_texts(w, xs[k], sm.X[row])
        probabilities[h] = column
    payload = {
        "version": VERSION,
        "regel": REGEL,
        "horizonte": list(HORIZONS),
        "gezeigt": list(SHOWN),
        "grund_horizont": REASON_HORIZON,
        "testzeitraum": {"von": test_days[0] if test_days else None, "bis": test_days[1] if test_days else None, "stichtag": cutoff_day},
        "faelle": int(len(sm.pos)),
        "letzter_tag": int(sm.days[newest]) if newest >= 0 else None,
        "merkmale": [label for _, label in FEATURES],
        "grenzen": {
            "mindestens_testfaelle": MIN_TEST,
            "mindestens_verbesserung": MIN_SKILL,
            "mindestens_standardfehler": MIN_T,
            "hoechstens_kalibrierungsfehler": MAX_ECE,
        },
        "grundrate": base_rates,
        "qualitaet": quality,
        "hinweise": [
            "Kumuliert: Schlusskurs nach h Handelstagen über dem heutigen Schlusskurs; Einzeltage werden nicht vorhergesagt.",
            "Heute: ohne Kurse im Tagesverlauf der Vergangenheit lässt sich eine Vorhersage für den laufenden Tag nicht prüfen – sie entfällt.",
            "Grundlage sind nur Kurse und Umsätze; Nachrichten, Termine und Analystenziele fließen nicht ein.",
            "Eine hohe Wahrscheinlichkeit ist kein Kaufsignal und keine Zusage.",
        ],
    }
    return Result(payload=payload, probabilities=probabilities, reasons=reasons)
