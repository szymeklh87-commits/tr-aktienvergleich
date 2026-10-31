"""Verschlüsselter Bericht des Depot-Optimierers als eine HTML-Datei (Nachtrag vom 31.10.2026, 20:16 Uhr, Punkt 9: „ein
tatsächlich berechnetes Empfehlungsdepot mit echten Aktien und nachvollziehbaren Daten“).

Inhalt: Empfehlungsdepot je Variante mit Aktien, Gewichten, Kursen, erwarteten Renditen, Unsicherheit und Begründung;
Rangliste je Horizont; wie viele Aktien, Kennzahlen, Kombinationen und Modelle geprüft wurden; was unabhängig validiert ist;
Rückblick gegen Welt-ETF und einfache Strategien. Der Inhalt ist mit dem Datenschlüssel verschlüsselt (wie alle Daten der
App, AES-256-GCM, Schlüssel aus der Passphrase); die Datei entschlüsselt erst im Browser mit der Passphrase. Öffentlich
liegen nur Chiffretext und Zählungen – die Passphrase verlässt das Gerät nicht.
"""

from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path

from ..util import crypto
from . import forschung as fo
from . import optimierer as op

AAD_PREFIX = "bericht/"


def inhalt(conn: sqlite3.Connection, modus: str) -> dict:
    """Kompakter Berichtsinhalt aus dem neuesten Forschungsergebnis und der neuesten gespeicherten Empfehlung."""
    payload = op.neuester(conn, modus)
    if payload is None:
        raise op.OptimiererFehler("kein Forschungsergebnis im Zustand")
    forsch = payload["forschung"]
    namen = forsch.get("namen") or {}
    row = conn.execute("SELECT MAX(datentag) FROM ap_empfehlung WHERE modus = ?", (modus,)).fetchone()
    varianten = {}
    if row and row[0] is not None:
        for v, raw in conn.execute("SELECT variante, inhalt FROM ap_empfehlung WHERE modus = ? AND datentag = ?", (modus, int(row[0]))):
            varianten[v] = json.loads(raw)
    rangliste = varianten.pop("rangliste", None)
    from . import portfolio

    varianten = {v: varianten[v] for v in portfolio.VARIANTEN if v in varianten}  # feste Reihenfolge (gespeichert sortiert)
    horizonte = {}
    for h, info in (forsch.get("horizonte") or {}).items():
        faktoren = [z for z in forsch["faktoren"]["zeilen"] if z["horizont"] == h and z["bestaetigt"]]
        faktoren.sort(key=lambda z: -abs(z["entwicklung"]["t"] or 0))
        horizonte[h] = {
            "text": fo.HORIZONT_TEXT[h], "modell": info.get("modell"), "modell_name": fo.MODELLE.get(info.get("modell") or "", None),
            "grund": info.get("modell_grund"), "belastbarkeit": info.get("belastbarkeit"), "unabhaengig": info.get("unabhaengig"),
            "zeitraeume": info.get("zeitraeume"), "walk_forward": info.get("walk_forward"), "kalibrierung": info.get("kalibrierung"),
            "rueckblick": info.get("rueckblick"),
            "auswahl": [{"merkmal": namen.get(m, m), "richtung": r} for m, r in zip(info["auswahl"]["merkmale"], info["auswahl"]["richtungen"])],
            "bestaetigt": [{"merkmal": namen.get(z["merkmal"], z["merkmal"]), "richtung": z["richtung"], "entwicklung": z["entwicklung"]["ic"],
                            "validierung": z["validierung"]["ic"], "test": z["test"]["ic"], "t": z["entwicklung"]["t"]} for z in faktoren[:12]],
            "bestaetigt_anzahl": len(faktoren),
        }
    horizonte = _ordnen(horizonte)
    return {
        "titel": "Depot-Optimierer – Empfehlungsdepot", "modus": payload["modus"], "synthetisch": payload["synthetisch"],
        "datenstand": payload["datenstand"], "datentag": payload["datentag"], "erstellt_utc": payload["erstellt_utc"], "zeitraum": payload["zeitraum"],
        "zaehlung": payload["zaehlung"], "historie": payload.get("historie"), "hinweise": payload["hinweise"], "horizonte": horizonte,
        "redundanz": len(forsch["redundanz"]["paare"]), "inventar": {"verwendet": sum(1 for x in payload["inventar"] if x["verwendet"]),
                                                                       "ausgeschlossen": [{"kennzahl": x["name"], "grund": x["grund"]} for x in payload["inventar"] if not x["verwendet"]]},
        "empfehlung": {"datentag": payload["empfehlung"]["datentag"], "standard": payload["empfehlung"]["standard"],
                       "einstellungen": payload["empfehlung"]["einstellungen"], "varianten": varianten or payload["empfehlung"]["varianten"],
                       "rangliste": _ordnen((rangliste or {}).get("horizonte") or payload["empfehlung"]["horizonte"])},
        "laufzeit_s": payload.get("laufzeit_s"),
    }


def _ordnen(d: dict) -> dict:
    """Horizonte in fester Reihenfolge 1 → 52 Wochen (gespeichert ist JSON mit sortierten Schlüsseln)."""
    return {h: d[h] for h in fo.HORIZONTE if h in d}


def schreiben(conn: sqlite3.Connection, *, key: crypto.KeyMaterial | None, descriptor: dict, modus: str, ziel: Path) -> dict:
    """Bericht verschlüsselt in ``ziel`` (HTML) schreiben. Rückgabe nur mit Zahlen."""
    daten = inhalt(conn, modus)
    if key is None and not daten["synthetisch"]:
        raise op.OptimiererFehler("ohne Datenschlüssel wird kein Bericht mit echten Kursen geschrieben")
    raw = json.dumps(daten, ensure_ascii=False, separators=(",", ":"), default=op._json_default).encode("utf-8")
    aad = AAD_PREFIX + daten["datentag"]
    blob = crypto.pack(raw, key, aad)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(html(base64.b64encode(blob).decode("ascii"), descriptor, aad), encoding="utf-8")
    v = daten["empfehlung"]["varianten"]
    return {"bytes": ziel.stat().st_size, "varianten": len(v), "verfuegbar": sum(1 for x in v.values() if x.get("verfuegbar")),
            "positionen": sum(len(x.get("positionen") or []) for x in v.values())}


def html(blob_b64: str, descriptor: dict, aad: str) -> str:
    desc = json.dumps({k: descriptor.get(k) for k in ("enabled", "iterations", "salt_b64", "check_b64", "check_aad")})
    return TEMPLATE.replace("__BLOB__", blob_b64).replace("__DESC__", desc).replace("__AAD__", json.dumps(aad))


TEMPLATE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Depot-Optimierer – Bericht</title>
<style>
:root { --bg: #f6f5f1; --card: #ffffff; --ink: #1d2024; --muted: #5d636b; --line: #dedad2; --accent: #1f5f8b; --plus: #17703f; --minus: #a63030; --warn: #8a5a00; }
@media (prefers-color-scheme: dark) { :root { --bg: #15171a; --card: #1e2125; --ink: #ecebe7; --muted: #a3a8ae; --line: #33373c; --accent: #7fb6dd; --plus: #6fcf97; --minus: #ef8a8a; --warn: #e3b35c; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 16px; }
h1 { font-size: 1.35rem; margin: 8px 0 4px; }
h2 { font-size: 1.1rem; margin: 28px 0 8px; }
h3 { font-size: 1rem; margin: 16px 0 6px; }
p, li { color: var(--ink); }
.muted { color: var(--muted); }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; margin: 10px 0; }
.row { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.name { font-weight: 600; min-width: 0; overflow-wrap: anywhere; }
.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
.plus { color: var(--plus); } .minus { color: var(--minus); } .warn { color: var(--warn); }
.small { font-size: .875rem; }
.tag { display: inline-block; border: 1px solid var(--line); border-radius: 999px; padding: 0 8px; font-size: .8rem; color: var(--muted); }
.tabs { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
.tabs button { border: 1px solid var(--line); background: var(--card); color: var(--ink); border-radius: 999px; padding: 6px 12px; font: inherit; font-size: .9rem; }
.tabs button[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: #fff; }
table { width: 100%; border-collapse: collapse; font-size: .875rem; }
th, td { text-align: left; padding: 6px 4px; border-bottom: 1px solid var(--line); vertical-align: top; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
form { display: flex; flex-direction: column; gap: 10px; margin-top: 16px; }
input { font: inherit; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--line); background: var(--card); color: var(--ink); }
button.go { font: inherit; padding: 10px 14px; border-radius: 10px; border: 0; background: var(--accent); color: #fff; }
.err { color: var(--minus); }
</style>
</head>
<body>
<main id="app">
  <h1>Depot-Optimierer – Bericht</h1>
  <p class="muted">Der Inhalt ist verschlüsselt. Mit der Passphrase der App wird er hier im Browser entschlüsselt – sie verlässt das Gerät nicht.</p>
  <form id="f">
    <input id="pw" type="password" autocomplete="current-password" placeholder="Passphrase der App" aria-label="Passphrase der App">
    <button class="go" type="submit">Bericht öffnen</button>
    <p id="msg" class="small" role="status"></p>
  </form>
</main>
<script>
const BLOB = "__BLOB__";
const DESC = __DESC__;
const AAD = __AAD__;
const te = new TextEncoder();
const b64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
async function key(pw) {
  const base = await crypto.subtle.importKey("raw", te.encode(pw), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "PBKDF2", hash: "SHA-256", salt: b64(DESC.salt_b64), iterations: DESC.iterations }, base, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
}
async function unpack(bytes, k, aad) {
  if (bytes[0] !== 84 || bytes[1] !== 82 || bytes[2] !== 65 || bytes[3] !== 49) throw new Error("Format");
  const flags = bytes[4];
  let payload = bytes.slice(5);
  if (flags & 1) {
    const iv = payload.slice(0, 12);
    payload = new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv, additionalData: te.encode(aad) }, k, payload.slice(12)));
  }
  if (flags & 2) {
    const ds = new DecompressionStream("gzip");
    payload = new Uint8Array(await new Response(new Blob([payload]).stream().pipeThrough(ds)).arrayBuffer());
  }
  return payload;
}
const de = (x, d = 1) => (x === null || x === undefined || !isFinite(x)) ? "–" : x.toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (x, d = 1) => (x === null || x === undefined || !isFinite(x)) ? "–" : (x > 0 ? "+" : x < 0 ? "−" : "") + de(Math.abs(x), d) + " %";
const cls = (x) => x > 0 ? "plus" : x < 0 ? "minus" : "";
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ART = { kaufen: "kaufen", halten: "halten", aufstocken: "höher gewichten", reduzieren: "reduzieren", verkaufen: "verkaufen", nicht_aufnehmen: "nicht aufnehmen" };
function datum(iso) { return iso ? iso.slice(8, 10) + "." + iso.slice(5, 7) + "." + iso.slice(0, 4) : "–"; }
function render(d) {
  const app = document.getElementById("app");
  const e = d.empfehlung;
  let html = `<h1>${esc(d.titel)}</h1><p class="muted">${d.synthetisch ? "<b class='warn'>DEMO – synthetische Kurse.</b> " : ""}Kursstand ${datum(d.datentag)} · Datenstand ${esc(d.datenstand)} · nur Spielgeld, keine Anlageberatung</p>`;
  html += `<div class="tabs" role="group" aria-label="Depotvariante">` + Object.entries(e.varianten).map(([k, v]) => `<button type="button" data-v="${k}" aria-pressed="${k === e.standard}">${esc(v.name)}</button>`).join("") + `</div><div id="var"></div>`;
  html += `<h2>Aktuell aussichtsreichste Aktien</h2><div class="tabs" role="group" aria-label="Horizont">` + Object.entries(e.rangliste).map(([h, x], i) => `<button type="button" data-h="${h}" aria-pressed="${i === 0}">${esc(x.text)}</button>`).join("") + `</div><div id="rl"></div>`;
  const z = d.zaehlung;
  html += `<h2>Was geprüft wurde</h2><div class="card small"><p>${de(z.aktien_panel, 0)} Aktien (mindestens 1 Mio. EUR Tagesumsatz) an ${de(z.entscheidungstage, 0)} Entscheidungstagen (${datum(d.zeitraum.von)} – ${datum(d.zeitraum.bis)}), ${de(z.merkmale, 0)} Merkmale aus ${de(z.kennzahlen_verwendet, 0)} von ${de(z.kennzahlen_katalog, 0)} Katalogkennzahlen; ${de(z.pruefungen, 0)} Prüfungen Merkmal × Horizont, davon ${de(z.bestaetigt, 0)} unabhängig bestätigt; ${de(z.kombinationen, 0)} Kombinationsschritte; ${de(z.modelle, 0)} Modellvergleiche im Walk-forward; Rechenkern ${de(z.rechenkern, 0)}-mal. ${d.redundanz} Merkmalspaare überschneiden sich (Rangkorrelation ≥ 0,8).</p>`;
  if (d.historie && d.historie.jahre) { const j = d.historie.jahre; html += `<p>Kurshistorie: ${de(j.aktien, 0)} Aktien; mindestens 1 Jahr: ${de(j.ab_1, 0)}, 2 Jahre: ${de(j.ab_2, 0)}, 3 Jahre: ${de(j.ab_3, 0)}, 5 Jahre: ${de(j.ab_5, 0)}.</p>`; }
  html += `</div>`;
  html += `<h2>Unabhängig validiert – je Horizont</h2>`;
  for (const [h, x] of Object.entries(d.horizonte)) {
    const wf = (x.walk_forward && x.walk_forward.modelle) || {};
    html += `<div class="card"><div class="row"><span class="name">${esc(x.text)}</span><span class="tag">${esc(x.belastbarkeit)}</span></div><p class="small">${esc(x.modell_name || "kein Modell")} – ${esc(x.grund || "")}; ${de(x.unabhaengig, 0)} unabhängige Zeiträume in Entwicklung und Validierung; ${x.bestaetigt_anzahl} Merkmale bestätigt.</p>`;
    if (Object.keys(wf).length) html += `<table><thead><tr><th>Modell (Walk-forward)</th><th class="n">Rang-IC</th><th class="n">t</th><th class="n">Bestes Zehntel</th></tr></thead><tbody>` + Object.entries(wf).filter(([k]) => k !== "null").map(([k, m]) => `<tr><td>${esc(m.name)}</td><td class="n">${de(m.ic, 3)}</td><td class="n">${de(m.t, 1)}</td><td class="n">${pct(m.top_ueberschuss_pp, 2).replace("%", "pp")}</td></tr>`).join("") + `</tbody></table>`;
    if (x.auswahl.length) html += `<p class="small">Merkmale im Modell: ${x.auswahl.map((a) => esc(a.merkmal) + (a.richtung < 0 ? " (niedrig besser)" : "")).join(", ")}</p>`;
    if (x.rueckblick && x.rueckblick.perioden) {
      const rb = x.rueckblick;
      html += `<h3>Rückblick: ${rb.perioden} nicht überlappende Zeiträume (je ${esc(rb.text)}, ${rb.anzahl} Aktien gleich gewichtet, ${de(rb.kosten_pct)} % Kosten)</h3><table><thead><tr><th>Strategie</th><th class="n">Ø</th><th class="n">kumuliert</th><th class="n">besser als Welt-ETF</th></tr></thead><tbody>` +
        Object.entries(rb.strategien).filter(([, s]) => s.perioden).map(([k, s]) => `<tr><td>${esc(s.text)}${k === rb.beste ? " <b>(beste)</b>" : ""}</td><td class="n ${cls(s.mittel_pct)}">${pct(s.mittel_pct)}</td><td class="n ${cls(s.kumuliert_pct)}">${pct(s.kumuliert_pct)}</td><td class="n">${s.besser_als_welt === null || s.besser_als_welt === undefined ? "–" : s.besser_als_welt + " von " + s.perioden}</td></tr>`).join("") + `</tbody></table><p class="small muted">${esc(rb.hinweis)}</p>`;
    }
    html += `</div>`;
  }
  html += `<h2>Grenzen</h2><ul class="small">` + d.hinweise.map((h) => `<li>${esc(h)}</li>`).join("") + `</ul>`;
  html += `<p class="small muted">Nicht verwendete Katalogkennzahlen: ${d.inventar.ausgeschlossen.map((x) => esc(x.kennzahl)).join(", ")} – jeweils mit Grund im Ergebnis. Erstellt ${esc(d.erstellt_utc)}.</p>`;
  app.innerHTML = html;
  const showVar = (k) => {
    document.querySelectorAll("[data-v]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === k)));
    const v = e.varianten[k];
    let s = `<div class="card"><div class="row"><span class="name">${esc(v.name)}</span><span class="tag">${esc(v.horizont_text)}</span></div><p class="small muted">${esc(v.erklaerung)}</p>`;
    if (!v.verfuegbar) { document.getElementById("var").innerHTML = s + `<p class="warn">${esc(v.grund)}</p></div>`; return; }
    const kz = v.kennzahlen;
    s += `<p>Erwartete Depotrendite nach Kosten <b class="${cls(kz.erwartet_nach_kosten_pct)}">${pct(kz.erwartet_nach_kosten_pct)}</b> über ${esc(v.horizont_text)} · Schwankung ±${de(kz.schwankung_pct)} % · Verlustszenario (5 % der Fälle) ${pct(kz.verlustszenario_pct)} · ${kz.positionen} Positionen (wirksam ${de(kz.effektive_anzahl)}), mittlere Korrelation ${de(kz.mittlere_korrelation, 2)}.</p></div>`;
    for (const p of v.positionen) {
      s += `<div class="card"><div class="row"><span class="name">${esc(p.name || p.isin)}</span><span class="num"><b>${de(p.gewicht_pct)} %</b></span></div><p class="small muted">${esc(p.isin)} · ${esc(p.branche || "Branche unbekannt")} · Kurs ${p.kurs ? de(p.kurs.kurs, 2) + " " + esc(p.kurs.waehrung) + " (" + datum(p.kurs.datum) + ")" : "–"}</p><p class="small">Erwartet <b class="${cls(p.erwartet_pct)}">${pct(p.erwartet_pct)}</b> (10–90 %: ${pct(p.q10_pct)} bis ${pct(p.q90_pct)}), positiv in ${de(p.positiv_pct, 0)} % ähnlicher Fälle, Kosten ${de(p.kosten_pct)} %, Eignung ${de(p.eignung, 0)}/100</p>${p.dafuer.length ? `<p class="small plus">Dafür: ${p.dafuer.map(esc).join("; ")}</p>` : ""}${p.dagegen.length ? `<p class="small minus">Dagegen: ${p.dagegen.map(esc).join("; ")}</p>` : ""}</div>`;
    }
    if (v.veraenderungen && v.veraenderungen.length) s += `<h3>Veränderungen</h3><table><tbody>` + v.veraenderungen.map((z) => `<tr><td>${esc(z.name || z.isin)}<br><span class="muted small">${esc(z.grund || "")}</span></td><td>${esc(ART[z.art] || z.art)}</td><td class="n">${de(z.gewicht_alt_pct)} → ${de(z.gewicht_neu_pct)} %</td></tr>`).join("") + `</tbody></table>`;
    document.getElementById("var").innerHTML = s;
  };
  const showH = (h) => {
    document.querySelectorAll("[data-h]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.h === h)));
    const x = e.rangliste[h];
    if (!x.rangliste || !x.rangliste.length) { document.getElementById("rl").innerHTML = `<div class="card"><p class="warn">Für ${esc(x.text)} ist die Prognose nicht belastbar – keine Rangliste ohne geprüfte Grundlage.</p></div>`; return; }
    document.getElementById("rl").innerHTML = `<p class="small muted">${esc(x.belastbarkeit)} · ${de(x.aktien, 0)} Aktien bewertet · Eignung = Rang der Erwartung nach Kosten je Unsicherheit (keine Gewinnwahrscheinlichkeit)</p><table><thead><tr><th>#</th><th>Aktie</th><th class="n">erwartet</th><th class="n">Eignung</th></tr></thead><tbody>` +
      x.rangliste.slice(0, 20).map((r) => `<tr><td class="n">${r.platz}</td><td>${esc(r.name || r.isin)}<br><span class="muted small">${esc(r.isin)}${r.dafuer.length ? " · " + esc(r.dafuer[0]) : ""}</span></td><td class="n ${cls(r.erwartet_pct)}">${pct(r.erwartet_pct)}<br><span class="muted small">${pct(r.q10_pct)}…${pct(r.q90_pct)}</span></td><td class="n">${de(r.eignung, 0)}</td></tr>`).join("") + `</tbody></table>`;
  };
  document.querySelectorAll("[data-v]").forEach((b) => b.addEventListener("click", () => showVar(b.dataset.v)));
  document.querySelectorAll("[data-h]").forEach((b) => b.addEventListener("click", () => showH(b.dataset.h)));
  showVar(e.standard in e.varianten ? e.standard : Object.keys(e.varianten)[0]);
  const first = Object.keys(e.rangliste)[0];
  if (first) showH(first);
}
document.getElementById("f").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const msg = document.getElementById("msg");
  msg.textContent = "Entschlüssele …";
  try {
    const bytes = b64(BLOB);
    let data;
    if (bytes[4] & 1) {
      const k = await key(document.getElementById("pw").value);
      data = await unpack(bytes, k, AAD);
    } else {
      data = await unpack(bytes, null, AAD);
    }
    render(JSON.parse(new TextDecoder().decode(data)));
  } catch (err) {
    msg.innerHTML = '<span class="err">Passphrase falsch oder Datei beschädigt.</span>';
  }
});
</script>
</body>
</html>
"""
