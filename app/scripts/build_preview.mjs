/* Vorschau der App als eine einzige HTML-Datei (Claude-Artifact), ausschließlich mit DEMO-Daten.
 *
 *   node scripts/build_preview.mjs [Datenordner] [Zieldatei]
 *   Standard: ../build/demo-site/data  →  ../build/vorschau/tr-aktienvergleich.html
 *
 * Unterschiede zur installierbaren App (dist/): App-Code, CSS und alle Datendateien stehen in
 * der Datei selbst; Anfragen an data/… beantwortet ein kleiner Ersatz für fetch aus diesen
 * eingebetteten Dateien. Kein Service Worker, keine Downloads, kein Drucken, keine Installation
 * (Build-Schalter __PREVIEW__). Die Datei beginnt ohne <html>/<head>/<body>, weil der
 * Artifact-Dienst sie in ein eigenes Grundgerüst einbettet.
 *
 * Sicherheitsregel: Es werden nur unverschlüsselte DEMO-Stände eingebettet. Ein produktiver oder
 * verschlüsselter Stand bricht den Build ab – echte Kursdaten gehören nicht in eine Vorschau.
 */

import { mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as esbuild from 'esbuild';

const root = dirname(fileURLToPath(import.meta.url)).replace(/[\\/]scripts$/, '');
const dataDir = resolve(process.argv[2] ?? join(root, '..', 'build', 'demo-site', 'data'));
const target = resolve(process.argv[3] ?? join(root, '..', 'build', 'vorschau', 'tr-aktienvergleich.html'));
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));

function fail(message) {
  console.error(`Vorschau nicht gebaut: ${message}`);
  process.exit(1);
}

function listFiles(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) out.push(...listFiles(path));
    else out.push(path);
  }
  return out.sort();
}

// 1) Nur DEMO, nur unverschlüsselt
const status = JSON.parse(readFileSync(join(dataDir, 'status.json'), 'utf8'));
const cryptoDescriptor = JSON.parse(readFileSync(join(dataDir, 'crypto.json'), 'utf8'));
if (status.app_mode !== 'demo') fail(`Datenmodus ist „${status.app_mode}“, erlaubt ist nur „demo“.`);
if (cryptoDescriptor.enabled) fail('der Datenstand ist verschlüsselt; die Vorschau bettet nur unverschlüsselte DEMO-Daten ein.');

const files = {};
let dataBytes = 0;
for (const path of listFiles(dataDir)) {
  const bytes = readFileSync(path);
  dataBytes += bytes.length;
  files[relative(dataDir, path).split('\\').join('/')] = bytes.toString('base64');
}

// 2) App mit Vorschau-Schalter bündeln (JS und CSS im Speicher). Der Rahmen erlaubt keine
//    Downloads; die Knöpfe sind in der Vorschau ausgeblendet, und die Speicherfunktionen werden
//    durch leere Fassungen ersetzt, damit kein toter Download-Pfad in der Seite bleibt.
const ohneDownloads = {
  name: 'ohne-downloads',
  setup(build) {
    build.onLoad({ filter: /[\\/]src[\\/]lib[\\/]csv\.ts$/ }, (args) => {
      const source = readFileSync(args.path, 'utf8');
      const start = source.indexOf('export function downloadText');
      const end = source.indexOf('export function safeFilename');
      if (start < 0 || end < start) fail('lib/csv.ts hat einen unerwarteten Aufbau.');
      const stubs =
        'export function downloadText(_filename: string, _text: string, _mime?: string): void {}\n' +
        'export function downloadBlob(_filename: string, _blob: Blob): void {}\n\n';
      return { contents: source.slice(0, start) + stubs + source.slice(end), loader: 'ts' };
    });
  },
};

const result = await esbuild.build({
  plugins: [ohneDownloads],
  absWorkingDir: root,
  entryPoints: ['src/main.tsx'],
  bundle: true,
  write: false,
  outdir: 'vorschau',
  format: 'esm',
  platform: 'browser',
  target: ['es2022', 'chrome111', 'firefox115', 'safari16'],
  jsx: 'automatic',
  minify: true,
  legalComments: 'none',
  charset: 'utf8',
  logLevel: 'warning',
  define: {
    __APP_VERSION__: JSON.stringify(`${pkg.version}-vorschau`),
    __PREVIEW__: 'true',
    'process.env.NODE_ENV': '"production"',
  },
});
const js = result.outputFiles.find((f) => f.path.endsWith('.js'))?.text;
const css = result.outputFiles.find((f) => f.path.endsWith('.css'))?.text;
if (!js || !css) fail('Bündel unvollständig.');
for (const [label, text] of [['JavaScript', js], ['CSS', css]]) {
  if (/<\/(script|style)/i.test(text) || text.includes('<!--')) fail(`${label} enthält eine Zeichenfolge, die eingebettet das HTML beenden würde.`);
}

// 3) Vorschau-spezifische Ergänzungen
const previewCss = `
/* Vorschau in Claude: Der Rahmen hält oben bereits Abstand zur Statusleiste. */
.appbar { top: env(safe-area-inset-top, 0px); padding-top: 0; }
`;

const themeInit = `(function () {
  try {
    var stored = JSON.parse(window.localStorage.getItem('tr-vergleich:einstellungen:v1') || '{}');
    if (stored && (stored.theme === 'hell' || stored.theme === 'dunkel')) document.documentElement.setAttribute('data-theme', stored.theme);
  } catch (e) { /* ohne Speicher: Farbschema des Rahmens bzw. des Handys */ }
})();`;

const fetchShim = `(function () {
  var element = document.getElementById('tr-vorschau-daten');
  var files = JSON.parse(element.textContent);
  element.remove();
  var original = window.fetch.bind(window);
  function bytesOf(b64) {
    var binary = atob(b64);
    var out = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
    return out;
  }
  window.fetch = function (input, init) {
    var url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    var match = /(?:^|\\/)data\\/([^?#]+)/.exec(url);
    if (!match) return original(input, init);
    var path = decodeURIComponent(match[1]);
    if (!Object.prototype.hasOwnProperty.call(files, path)) {
      return Promise.resolve(new Response('Nicht in der Vorschau enthalten: ' + path, { status: 404 }));
    }
    var type = /\\.json$/.test(path) ? 'application/json' : 'application/octet-stream';
    return Promise.resolve(new Response(bytesOf(files[path]), { status: 200, headers: { 'content-type': type } }));
  };
})();`;

const dataJson = JSON.stringify(files).replace(/</g, '\\u003c');

const html = `<title>TR-Aktienvergleich</title>
<style>
${css}
${previewCss}
</style>
<script>
${themeInit}
</script>
<script type="application/json" id="tr-vorschau-daten">${dataJson}</script>
<script>
${fetchShim}
</script>
<div id="root"></div>
<noscript>Diese App benötigt JavaScript.</noscript>
<script type="module">
${js}
</script>
`;

mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, html, 'utf8');
const mb = (n) => (n / 1e6).toFixed(2);
console.log(
  `Vorschau: ${target}\n  ${Object.keys(files).length} Datendateien (${mb(dataBytes)} MB), Snapshot ${status.latest_snapshot_id}, Seite ${mb(Buffer.byteLength(html))} MB`,
);
