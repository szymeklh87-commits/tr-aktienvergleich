#!/usr/bin/env node
// Programmieraufgabe mit automatisierten Tests für Pi, danach unabhängige Nachprüfung.
//   node ops/pi/selbsttest.mjs                      Prüfmodell: lokale, festgelegte Gegenstelle (kein KI-Modell,
//                                                   prüft Pis Werkzeugschleife write/bash/read/edit ohne Netz)
//   node ops/pi/selbsttest.mjs --modell openai-codex/<id>  echtes, angemeldetes Modell
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import http from "node:http";
import assert from "node:assert/strict";

const AUFGABE =
  "Lege in diesem Ordner slug.js an, das per module.exports (CommonJS) slugify(text) exportiert: Kleinbuchstaben, " +
  "ä->ae, ö->oe, ü->ue, ß->ss, jede Folge anderer Zeichen als a-z0-9 wird zu einem '-', kein '-' am Anfang oder Ende. " +
  "Lege test.js an, das mit node:assert mindestens 6 Fälle prüft und am Ende 'ALLE TESTS OK' ausgibt. " +
  "Führe node test.js aus und behebe Fehler, bis alle Tests bestehen.";

const i = process.argv.indexOf("--modell");
const modell = i > 0 ? process.argv[i + 1] : null;
const arbeit = mkdtempSync(join(tmpdir(), "pi-test-"));
const env = { ...process.env };

// ---- Prüfmodell: OpenAI-kompatible Gegenstelle mit festem Ablauf inkl. absichtlichem Fehler ----
const BUGGY = `function slugify(t) {
  return t.toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}
module.exports = { slugify };
`;
const TEST = `const assert = require("node:assert/strict");
const { slugify } = require("./slug.js");
const faelle = [["Hallo Welt", "hallo-welt"], ["Größe", "groesse"], ["Übermaß!!", "uebermass"],
  ["  -a--b-  ", "a-b"], ["Lüdinghausen 2026", "luedinghausen-2026"], ["", ""], ["ÄÖÜ äöü", "aeoeue-aeoeue"]];
let fehler = 0;
for (const [ein, soll] of faelle) {
  try { assert.equal(slugify(ein), soll); } catch { fehler++; console.log("FEHLER", JSON.stringify(ein), "->", slugify(ein)); }
}
if (fehler) { console.log(fehler + " Tests fehlgeschlagen"); process.exit(1); }
console.log("ALLE TESTS OK");
`;
const SCHRITTE = [
  { tool: "write", args: { path: "slug.js", content: BUGGY } },
  { tool: "write", args: { path: "test.js", content: TEST } },
  { tool: "bash", args: { command: "node test.js" }, erwartet: /Tests fehlgeschlagen/ },
  { tool: "read", args: { path: "slug.js" }, erwartet: /replace\(\/ü\/g/ },
  { tool: "edit", args: { path: "slug.js", edits: [{ oldText: '.replace(/ü/g, "ue")', newText: '.replace(/ü/g, "ue").replace(/ß/g, "ss")' }] } },
  { tool: "bash", args: { command: "node test.js" }, erwartet: /ALLE TESTS OK/ },
];

function pruefmodell() {
  return new Promise((ok) => {
    const s = http.createServer((q, r) => {
      let b = "";
      q.on("data", (d) => (b += d)).on("end", () => {
        const msgs = JSON.parse(b).messages || [];
        const ergebnisse = msgs.filter((m) => m.role === "tool");
        const n = ergebnisse.length;
        const letzte = ergebnisse.at(-1);
        const text = (c) => (typeof c === "string" ? c : (c || []).map((x) => x.text || "").join(""));
        let delta, ende;
        const vorher = SCHRITTE[n - 1];
        if (vorher?.erwartet && !vorher.erwartet.test(text(letzte?.content))) {
          delta = { content: `PRUEFMODELL-FEHLER: Werkzeugergebnis von Schritt ${n} unerwartet` }; ende = "stop";
        } else if (n < SCHRITTE.length) {
          const st = SCHRITTE[n];
          delta = { tool_calls: [{ index: 0, id: `call_${n}`, type: "function", function: { name: st.tool, arguments: JSON.stringify(st.args) } }] };
          ende = "tool_calls";
        } else { delta = { content: "Fertig: slug.js korrigiert (ß), alle Tests bestehen." }; ende = "stop"; }
        const chunk = (d, f) => `data: ${JSON.stringify({ id: "p", object: "chat.completion.chunk", choices: [{ index: 0, delta: d, finish_reason: f }] })}\n\n`;
        r.writeHead(200, { "content-type": "text/event-stream" });
        r.end(chunk({ role: "assistant", ...delta }, null) + chunk({}, ende) + "data: [DONE]\n\n");
      });
    });
    s.listen(0, "127.0.0.1", () => ok(s));
  });
}

let server;
let ziel = modell;
if (!modell) {
  server = await pruefmodell();
  const agent = join(arbeit, ".agent");
  mkdirSync(agent);
  writeFileSync(join(agent, "models.json"), JSON.stringify({ providers: { pruefmodell: {
    name: "Prüfmodell (lokal)", baseUrl: `http://127.0.0.1:${server.address().port}/v1`, api: "openai-completions", apiKey: "lokal",
    models: [{ id: "skript", contextWindow: 32000, maxTokens: 4000, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } }] } } }));
  env.PI_CODING_AGENT_DIR = agent;
  ziel = "pruefmodell/skript";
}

const t0 = Date.now();
const ausgabe = await new Promise((ok) => {
  let out = "";
  const p = spawn("pi", ["-p", "--no-session", "--model", ziel, AUFGABE], { cwd: arbeit, env, stdio: ["ignore", "pipe", "pipe"] });
  const zeit = setTimeout(() => p.kill(), modell ? 600_000 : 120_000);
  p.stdout.on("data", (d) => (out += d)); p.stderr.on("data", (d) => (out += d));
  p.on("close", (code) => { clearTimeout(zeit); ok({ code, out: out.trim() }); });
});
server?.close();

console.log(`Modell: ${ziel} · Pi-Exit ${ausgabe.code} · ${((Date.now() - t0) / 1000).toFixed(1)} s`);
console.log(`Pi: ${ausgabe.out.split("\n").slice(-3).join(" | ")}`);

// ---- Unabhängige Nachprüfung ----
try {
  assert.ok(existsSync(join(arbeit, "slug.js")) && existsSync(join(arbeit, "test.js")), "slug.js/test.js fehlen");
  const { slugify } = createRequire(join(arbeit, "x.js"))("./slug.js");
  for (const [ein, soll] of [["  Größe & Übermaß!  ", "groesse-uebermass"], ["Lüdinghausen 2026", "luedinghausen-2026"], ["A__B", "a-b"], ["---", ""]])
    assert.equal(slugify(ein), soll, `slugify(${JSON.stringify(ein)})`);
  const t = await new Promise((ok) => { let o = ""; const p = spawn("node", ["test.js"], { cwd: arbeit }); p.stdout.on("data", (d) => (o += d)); p.on("close", (c) => ok({ c, o })); });
  assert.ok(t.c === 0 && /ALLE TESTS OK/.test(t.o), "test.js besteht nicht");
  console.log(`BESTANDEN – Dateien in ${arbeit}`);
} catch (e) {
  console.log(`NICHT BESTANDEN: ${e.message} – Ordner ${arbeit}`);
  process.exit(1);
}
