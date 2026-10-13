/* Laufumgebung der App.
 *
 * PREVIEW = Vorschau als Claude-Artifact (eigener Build: scripts/build_preview.mjs). Dort läuft
 * die Seite in einem abgeschotteten Rahmen: kein Service Worker, keine Downloads, kein Drucken,
 * keine Installation. Die installierte App auf GitHub Pages ist davon nicht betroffen. */

declare const __PREVIEW__: boolean | undefined;

export const PREVIEW: boolean = typeof __PREVIEW__ !== 'undefined' && __PREVIEW__ === true;
