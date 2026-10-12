/* Produktions-Build der App (ohne Entwicklungsserver).
 *
 *   node build.mjs            → dist/ (App-Hülle für GitHub Pages)
 *
 * Schritte: Bundle mit Inhalts-Hash, CSS, index.html aus Vorlage, öffentliche Dateien,
 * Service Worker mit Versionskennung und Vorab-Cache-Liste, version.json.
 * Der Build ist deterministisch: gleiche Quellen → gleiche Dateinamen und Version.
 */

import { createHash } from 'node:crypto';
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as esbuild from 'esbuild';

const root = dirname(fileURLToPath(import.meta.url));
const dist = join(root, 'dist');
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
const target = ['es2022', 'chrome111', 'firefox115', 'safari16'];

function listFiles(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) out.push(...listFiles(path));
    else out.push(path);
  }
  return out;
}

function hashOf(paths) {
  const hash = createHash('sha256');
  for (const path of [...paths].sort()) {
    hash.update(relative(dist, path));
    hash.update(readFileSync(path));
  }
  return hash.digest('hex').slice(0, 10);
}

rmSync(dist, { recursive: true, force: true });
mkdirSync(join(dist, 'assets'), { recursive: true });

// 1) App-Bundle: Version wird nach dem Bundle aus dem Inhalt bestimmt; das Bundle selbst
//    liest sie zur Laufzeit aus version.json nicht – daher zweistufig: zuerst ohne Version
//    hashen, dann mit endgültiger Version bauen.
async function bundleApp(version) {
  return esbuild.build({
    absWorkingDir: root,
    entryPoints: ['src/main.tsx'],
    bundle: true,
    outdir: join(dist, 'assets'),
    entryNames: 'app-[hash]',
    assetNames: 'asset-[hash]',
    format: 'esm',
    platform: 'browser',
    target,
    jsx: 'automatic',
    minify: true,
    sourcemap: false,
    legalComments: 'none',
    charset: 'utf8',
    metafile: true,
    logLevel: 'warning',
    define: { __APP_VERSION__: JSON.stringify(version), 'process.env.NODE_ENV': '"production"' },
  });
}

const probe = await esbuild.build({
  absWorkingDir: root,
  entryPoints: ['src/main.tsx', 'src/sw.ts'],
  bundle: true,
  write: false,
  outdir: 'probe',
  format: 'esm',
  target,
  jsx: 'automatic',
  minify: true,
  define: { __APP_VERSION__: '"probe"', __PRECACHE__: '[]', 'process.env.NODE_ENV': '"production"' },
  logLevel: 'silent',
});
const contentHash = createHash('sha256');
for (const file of probe.outputFiles.sort((a, b) => a.path.localeCompare(b.path))) contentHash.update(file.contents);
for (const file of listFiles(join(root, 'public')).sort()) contentHash.update(readFileSync(file));
const version = `${pkg.version}+${contentHash.digest('hex').slice(0, 8)}`;

const result = await bundleApp(version);
let appJs = null;
let appCss = null;
for (const [out, meta] of Object.entries(result.metafile.outputs)) {
  if (meta.entryPoint === 'src/main.tsx') {
    appJs = out.split('/').pop();
    if (meta.cssBundle) appCss = meta.cssBundle.split('/').pop();
  }
}
if (!appJs || !appCss) throw new Error('Bundle unvollständig (JS oder CSS fehlt)');

// 2) Öffentliche Dateien und index.html
cpSync(join(root, 'public'), dist, { recursive: true });
const template = readFileSync(join(root, 'public', 'index.html'), 'utf8');
writeFileSync(join(dist, 'index.html'), template.replace('%APP_JS%', appJs).replace('%APP_CSS%', appCss));

// 3) Service Worker mit Vorab-Cache-Liste (alle Dateien der Hülle, keine Daten)
const shellFiles = listFiles(dist)
  .map((path) => relative(dist, path).split('\\').join('/'))
  .filter((path) => !path.startsWith('data/') && path !== 'sw.js')
  .sort();
const precache = ['./', ...shellFiles.map((path) => `./${path}`)];
await esbuild.build({
  absWorkingDir: root,
  entryPoints: ['src/sw.ts'],
  bundle: true,
  outfile: join(dist, 'sw.js'),
  format: 'iife',
  platform: 'browser',
  target,
  minify: true,
  legalComments: 'none',
  charset: 'utf8',
  logLevel: 'warning',
  define: { __APP_VERSION__: JSON.stringify(version), __PRECACHE__: JSON.stringify(precache) },
});

// 4) Versionsbeleg
const files = listFiles(dist).filter((path) => !path.endsWith('version.json'));
writeFileSync(
  join(dist, 'version.json'),
  JSON.stringify({ app: pkg.name, version, shell_hash: hashOf(files), files: files.map((p) => relative(dist, p).split('\\').join('/')).sort() }, null, 2) + '\n',
);

if (!existsSync(join(dist, 'manifest.webmanifest'))) throw new Error('Manifest fehlt');
const size = files.reduce((n, path) => n + statSync(path).size, 0);
console.log(`Build ${version}: ${files.length} Dateien, ${(size / 1024).toFixed(0)} KiB → ${relative(process.cwd(), dist) || 'dist'}`);
