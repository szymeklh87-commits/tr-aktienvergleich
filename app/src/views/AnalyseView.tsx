/* Analyse-Werkzeuge: Einstieg mit je einem Satz, was das Werkzeug zeigt und wofür es gut ist. */

import { buildHash } from '../lib/router';
import { useApp } from '../state/AppState';

const TOOLS = [
  {
    path: '/matrix',
    title: 'Matrix A/B',
    what: 'Spitzenreiter für jeden Zeitraum von 1 bis 90 Tagen und jede der elf Gewichtungen – Gruppe A (alle Aktien) und Gruppe B (hoher Umsatz) nebeneinander.',
    when: 'Wenn du sehen willst, welche Aktien über viele Zeiträume vorne liegen.',
  },
  {
    path: '/haeufig',
    title: 'Häufigste Aktien',
    what: 'Wie oft eine Aktie auf Platz 1, unter den ersten 3 oder ersten 10 liegt – über alle Zeiträume und Gewichtungen.',
    when: 'Wenn du Dauerbrenner statt Eintagsfliegen suchst.',
  },
  {
    path: '/raster',
    title: 'Chart-Raster',
    what: 'Die ersten zehn einer Rangliste als kleine Kursgrafiken, alle mit Startwert 100.',
    when: 'Wenn du Verläufe auf einen Blick vergleichen willst.',
  },
  {
    path: '/vergleich',
    title: 'Gewichtungen vergleichen',
    what: 'Dieselbe Rangliste mit unterschiedlicher Gewichtung von Gleichmäßigkeit und Rendite nebeneinander.',
    when: 'Wenn du wissen willst, wie stark die Gewichtung die Reihenfolge verändert.',
  },
  {
    path: '/regel',
    title: 'Umschichtungs-Regel',
    what: 'Eine feste Rechenregel: welche Aktien sie heute halten würde und wie sie sich im Rückblick nach Kosten und Steuern entwickelt hätte.',
    when: 'Wenn du eine regelbasierte Strategie im Rückblick prüfen willst.',
  },
];

export function AnalyseView() {
  const { prefs } = useApp();
  return (
    <div className="view">
      <header className="view-head">
        <h2 className="view-title">Analyse-Werkzeuge</h2>
        <p className="view-intro">Vertiefende Auswertungen der Kursrenditen. Für den schnellen Überblick reichen Start, Rendite und Potenzial – hier geht es ins Detail.</p>
      </header>
      <ul className="tool-list">
        {TOOLS.map((tool) => (
          <li key={tool.path}>
            <a href={tool.path === '/raster' ? buildHash(tool.path, { h: prefs.h, w: prefs.w }) : `#${tool.path}`}>
              <strong>{tool.title}</strong>
              <span>{tool.what}</span>
              <small>{tool.when}</small>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
