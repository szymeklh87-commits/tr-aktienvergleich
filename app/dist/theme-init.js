/* Setzt das gewählte Farbschema vor dem ersten Zeichnen (verhindert kurzes Aufblitzen).
 * Eigene Datei statt Inline-Skript, damit die Content-Security-Policy streng bleiben kann. */
(function () {
  try {
    var stored = JSON.parse(window.localStorage.getItem('tr-vergleich:einstellungen:v1') || '{}');
    if (stored && (stored.theme === 'hell' || stored.theme === 'dunkel')) {
      document.documentElement.setAttribute('data-theme', stored.theme);
    }
  } catch (e) {
    /* ohne Speicher: Systemeinstellung */
  }
})();
