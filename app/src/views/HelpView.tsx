/* Hilfe und Begriffe (ab 1.16): wofür die App da ist, erste Schritte, wie man eine Rangliste liest,
 * welche Ansicht welche Frage beantwortet, Begriffe von A bis Z, häufige Fragen und was bei Meldungen zu tun ist.
 * Funktioniert ohne Datenstand und ohne Passphrase (reiner Text). */

import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Disclosure, SectionTitle } from '../components/ui';
import { GLOSSARY, searchGlossary } from '../lib/glossary';
import type { Route } from '../lib/router';

const SECTIONS: [string, string][] = [
  ['hilfe-zweck', 'Wofür ist die App?'],
  ['hilfe-schritte', 'Erste Schritte'],
  ['hilfe-lesen', 'Rangliste lesen'],
  ['hilfe-ansichten', 'Welche Ansicht wofür?'],
  ['hilfe-begriffe', 'Begriffe A–Z'],
  ['hilfe-fragen', 'Häufige Fragen'],
  ['hilfe-probleme', 'Wenn etwas nicht klappt'],
];

function jump(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ block: 'start' });
  // Fokus für Screenreader und Tastatur, ohne zweites Scrollen
  if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1');
  el.focus({ preventScroll: true });
}

/** Rechenbeispiel: drei Aktien, 30 Tage, Gewichtung 60/40 (Perzentile bei drei Aktien: 0, 50, 100). */
const EXAMPLE = [
  { name: 'Aktie A', r: '+12 %', pr: 50, r2: '0,95', pg: 100, score: '0,6 × 100 + 0,4 × 50 = 80' },
  { name: 'Aktie B', r: '+25 %', pr: 100, r2: '0,40', pg: 0, score: '0,6 × 0 + 0,4 × 100 = 40' },
  { name: 'Aktie C', r: '+5 %', pr: 0, r2: '0,80', pg: 50, score: '0,6 × 50 + 0,4 × 0 = 30' },
];

const VIEWS: [string, string, string][] = [
  ['Welche Aktie ist in einem Zeitraum am stärksten gestiegen?', '#/rendite', 'Rendite'],
  ['Welche Aktie ist stark und gleichmäßig gestiegen?', '#/ranking', 'Rendite → Gleichmäßig + Rendite'],
  ['Welche Aktien liegen in vielen Zeiträumen vorn?', '#/bericht', 'Rendite → Bericht 1–30'],
  ['Was sagen Kursverlauf und Analysten zusammen?', '#/potenzial', 'Potenzial'],
  ['Wie hätte sich ein Depot aus diesen Aktien entwickelt?', '#/depots', 'Rendite → Depots'],
  ['Wo steht eine bestimmte Aktie?', '#/aktien', 'Aktien (Suche) oder Watchlist'],
  ['Wie aktuell sind die Daten?', '#/status', '☰ → Datenstand & Betrieb'],
];

const FAQ: [string, ReactNode][] = [
  [
    'Warum fehlt eine Aktie in der Rangliste?',
    <>
      In die Rangliste mit Gleichmäßigkeit kommen nur Aktien, die im Zeitraum gestiegen sind und mindestens 15 Tageskurse haben. In der reinen Rendite-Rangliste fehlen
      nur Aktien ohne gültige Kurse. Unter „Aktien“ findest du jede Aktie mit dem Grund, zum Beispiel „Nicht steigend“ oder „Zu kurze Historie“.
    </>,
  ],
  [
    'Warum sind die Kurse von heute nicht dabei?',
    <>
      Die Ranglisten rechnen mit Schlusskursen. Schlusskurse gibt es erst nach Börsenschluss, in den USA gegen 22 Uhr. Der tägliche Lauf rechnet sie am nächsten Tag.
      Während des Börsentags kannst du mit ☰ → „Jetzt aktualisieren“ einen Zwischenstand mit vorläufigen Kursen rechnen lassen.
    </>,
  ],
  [
    'Wann kommen neue Daten?',
    <>
      Der tägliche Lauf ist für 7 Uhr geplant. GitHub startet geplante Läufe aber oft einige Stunden später; meist ist der neue Stand bis zum frühen Nachmittag da.
      Wann der letzte Lauf war, steht unter ☰ → „Datenstand & Betrieb“. Du kannst den Lauf jederzeit selbst starten: ☰ → „Jetzt aktualisieren“.
    </>,
  ],
  [
    'Was bedeutet „Schlusskurs 09.10.“ in einer Zeile?',
    <>
      Für diese Aktie gab es am Tag des Kursstands keinen Kurs, zum Beispiel wegen eines Feiertags an ihrer Börse. Sie zählt dann mit ihrem letzten Schlusskurs, wenn der
      höchstens eine Börsensitzung zurückliegt.
    </>,
  ],
  [
    'Sind die Ranglisten eine Kaufempfehlung?',
    <>
      Nein. Die App ordnet Aktien nach vergangenen Kursen und nach Angaben Dritter. Sie kennt deine persönliche Lage nicht und sagt nicht voraus, wie sich ein Kurs
      entwickelt. Starke Anstiege können sich schnell umkehren. Du entscheidest selbst.
    </>,
  ],
  [
    'Warum weicht ein Kurs von Trade Republic ab?',
    <>
      Die App nutzt die Schlusskurse einer Börse in deren Währung, bei US-Aktien zum Beispiel in US-Dollar. Trade Republic zeigt Euro-Kurse von seinem eigenen
      Handelsplatz. Kurs und Rendite können deshalb etwas abweichen.
    </>,
  ],
  [
    'Ich habe die Passphrase vergessen. Was nun?',
    <>
      Die Passphrase hat festgelegt, wer die App eingerichtet hat. Sie ist bei GitHub als Secret „DATA_PASSPHRASE“ hinterlegt; GitHub zeigt den Wert nicht wieder an.
      Ohne die richtige Passphrase lassen sich die Daten nicht öffnen. Die App selbst kann sie nicht wiederherstellen.
    </>,
  ],
  [
    'Funktioniert die App ohne Internet?',
    <>
      Ja, für Ansichten, die du schon einmal geöffnet hast. Die App speichert die letzten drei Datenstände auf dem Gerät. Neue Kurse und noch nicht geöffnete Details
      brauchen eine Verbindung.
    </>,
  ],
  [
    'Wie bekomme ich die neueste App-Version?',
    <>
      Erscheint oben „Neue App-Version verfügbar“, tippe auf „Aktualisieren“. Sonst schließe die App ganz und öffne sie neu. Deine Version steht unter ☰ →
      „Einstellungen“. Watchlist und Einstellungen bleiben bei einem Update erhalten.
    </>,
  ],
];

const PROBLEMS: [string, string][] = [
  ['„Diese Passphrase passt nicht“', 'Prüfe Groß- und Kleinschreibung. Tippe auf „Passphrase anzeigen“, um zu sehen, was du eingegeben hast. Dann erneut „Entsperren“.'],
  ['„Keine Internetverbindung“', 'Verbinde das Handy mit dem Internet (WLAN oder mobile Daten) und tippe auf „Erneut versuchen“.'],
  ['„Server antwortet nicht“', 'Das liegt nicht an deinem Gerät. Warte ein paar Minuten und tippe dann auf „Erneut versuchen“.'],
  ['„Daten nicht lesbar“', 'Tippe auf „Erneut versuchen“. Hilft das nicht: ☰ → Einstellungen → „Gespeicherte Datenstände löschen“ und die App neu öffnen.'],
  ['„Keine aktuelle Prüfung“', 'Der tägliche Lauf hat sich länger als 30 Stunden nicht gemeldet. Starte ihn über ☰ → „Jetzt aktualisieren“. Die App zeigt bis dahin den letzten Stand.'],
  ['„Teilstand“ oben rechts', 'Für einzelne Börsen fehlen noch Schlusskurse. Du musst nichts tun: Der nächste Lauf ergänzt sie von selbst.'],
  ['Eine Ansicht bleibt leer', 'Lies den Hinweis in der Ansicht: Er nennt den Grund, zum Beispiel einen zu kurzen Zeitraum. Wähle dann einen längeren Zeitraum oder eine andere Gewichtung.'],
];

export function HelpView({ route }: { route: Route }) {
  const wanted = route.params.get('begriff');
  const [query, setQuery] = useState('');
  const entries = searchGlossary(query);

  useEffect(() => {
    if (!wanted) return;
    // Ein Link auf einen Begriff zeigt ihn immer – auch wenn gerade ein Suchwort andere Begriffe ausblendet
    setQuery('');
    const timer = window.setTimeout(() => jump(`begriff-${wanted}`), 60);
    return () => window.clearTimeout(timer);
  }, [wanted]);

  return (
    <div className="view help-view">
      <header className="view-head">
        <h2 className="view-title">Hilfe und Begriffe</h2>
        <p className="lede">Hier steht, wofür die App gedacht ist, wie du sie bedienst und was die Zahlen bedeuten. Tippe auf ein Thema, um direkt dorthin zu springen.</p>
      </header>

      <nav className="help-toc" aria-label="Themen der Hilfe">
        {SECTIONS.map(([id, label]) => (
          <button key={id} type="button" className="chip" onClick={() => jump(id)}>
            {label}
          </button>
        ))}
      </nav>

      <section className="section" aria-labelledby="hilfe-zweck">
        <SectionTitle id="hilfe-zweck">Wofür ist die App?</SectionTitle>
        <p>
          Der TR-Aktienvergleich zeigt jeden Tag, welche Aktien aus der Aktienliste von Trade Republic in den letzten 1 bis 90 Tagen am stärksten gestiegen sind – und
          welche dabei am gleichmäßigsten.
        </p>
        <p>
          Die App rechnet nur mit vergangenen Schlusskursen. Sie sagt nicht voraus, wie es weitergeht, und gibt keine Kaufempfehlung. Sie ist kein Produkt von Trade
          Republic, braucht keine Zugangsdaten von Trade Republic und kann keine Aktien kaufen oder verkaufen.
        </p>
        <p>Gerechnet wird jeden Tag auf einem Server. Dein Handy muss dafür nicht eingeschaltet sein.</p>
      </section>

      <section className="section" aria-labelledby="hilfe-schritte">
        <SectionTitle id="hilfe-schritte">Erste Schritte</SectionTitle>
        <ol className="help-steps">
          <li>
            <strong>Passphrase eingeben.</strong> Das ist nur beim ersten Öffnen auf einem Gerät nötig. Danach öffnet sich gleich die Startseite.
          </li>
          <li>
            <strong>Startseite lesen.</strong> Oben stehen die Top 3 nach einer festen Punkteregel. Darunter steht der Kursstand: der Börsentag, dessen Schlusskurse
            verwendet werden.
          </li>
          <li>
            <strong>Unten auf „Rendite“ tippen.</strong> Wähle einen Zeitraum, zum Beispiel 30 Tage. Du siehst, welche Aktie in diesem Zeitraum am stärksten gestiegen ist.
          </li>
          <li>
            <strong>„Gleichmäßig + Rendite“ wählen,</strong> wenn eine Aktie stark <em>und</em> gleichmäßig gestiegen sein soll. Wähle die Gewichtung, zum Beispiel 60/40.
          </li>
          <li>
            <strong>Eine Aktie antippen.</strong> Du siehst den Kursverlauf, alle Kennzahlen und die Einschätzung der Analysten.
          </li>
          <li>
            <strong>Mit dem Stern ☆ merken.</strong> Gemerkte Aktien findest du unter „Aktien“ → „Watchlist“, jeweils mit ihrem aktuellen Platz.
          </li>
          <li>
            <strong>Neue Kurse</strong> kommen einmal am Tag von selbst. Mit ☰ → „Jetzt aktualisieren“ startest du die Berechnung sofort.
          </li>
        </ol>
      </section>

      <section className="section" aria-labelledby="hilfe-lesen">
        <SectionTitle id="hilfe-lesen">So liest du eine Rangliste</SectionTitle>
        <p>
          Beispiel mit drei Aktien und 30 Tagen. Zuerst bekommt jede Aktie für Kursrendite und Gleichmäßigkeit ein Perzentil von 0 (schlechteste) bis 100 (beste). Bei
          drei Aktien sind das 0, 50 und 100. Dann rechnet die Gewichtung 60/40 daraus den Rangscore.
        </p>
        <div className="table-wrap">
          <table className="help-table">
            <caption>Rechenbeispiel, Gewichtung 60/40 (60 % Gleichmäßigkeit, 40 % Kursrendite)</caption>
            <thead>
              <tr>
                <th scope="col">Aktie</th>
                <th scope="col">Kursrendite (Perzentil)</th>
                <th scope="col">Gleichmäßigkeit R² (Perzentil)</th>
                <th scope="col">Rangscore</th>
              </tr>
            </thead>
            <tbody>
              {EXAMPLE.map((row) => (
                <tr key={row.name}>
                  <th scope="row">{row.name}</th>
                  <td>
                    {row.r} ({row.pr})
                  </td>
                  <td>
                    {row.r2} ({row.pg})
                  </td>
                  <td>{row.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>
          Ergebnis bei 60/40: Platz 1 ist Aktie A, weil sie fast gerade gestiegen ist. Bei „Nur Kursrendite“ (0/100) wäre Aktie B auf Platz 1, weil sie am meisten
          gestiegen ist. Die Gewichtung ändert also die Reihenfolge – probiere beide aus.
        </p>
        <h3 className="help-subtitle">Was in einer Zeile steht</h3>
        <dl className="help-dl">
          <dt>Zahl links</dt>
          <dd>Der Platz in der Rangliste.</dd>
          <dt>Name und ISIN</dt>
          <dd>Die Aktie und ihre Kennnummer. Das Kopier-Symbol kopiert die ISIN, zum Beispiel für die Suche in der Trade-Republic-App.</dd>
          <dt>Prozentzahl rechts</dt>
          <dd>Die Kursrendite im gewählten Zeitraum.</dd>
          <dt>Rangscore</dt>
          <dd>Der Wert, nach dem sortiert ist: 0 bis 100, höher ist besser.</dd>
          <dt>R²</dt>
          <dd>Die Gleichmäßigkeit: 0 bis 1, je näher an 1, desto gerader ist der Kurs gestiegen. „R² –“ heißt: im Zeitraum zu wenige Tageskurse.</dd>
          <dt>Kennzeichen</dt>
          <dd>„Kaum Umsatz“, „Einzelsprung“ oder „Schlusskurs 09.10.“ unter dem Namen. Sie erklären, warum man bei dieser Zeile genauer hinsehen sollte.</dd>
          <dt>Details</dt>
          <dd>Klappt weitere Zahlen auf: Start- und Endkurs, größter Rückgang im Zeitraum und Umsatz.</dd>
        </dl>
      </section>

      <section className="section" aria-labelledby="hilfe-ansichten">
        <SectionTitle id="hilfe-ansichten">Welche Ansicht beantwortet welche Frage?</SectionTitle>
        <ul className="help-views">
          {VIEWS.map(([question, href, where]) => (
            <li key={href}>
              <span>{question}</span>
              <a href={href}>{where}</a>
            </li>
          ))}
        </ul>
      </section>

      <section className="section" aria-labelledby="hilfe-begriffe">
        <SectionTitle id="hilfe-begriffe">Begriffe von A bis Z</SectionTitle>
        <label className="field">
          <span className="field-label">Begriff suchen</span>
          <input
            className="input"
            type="search"
            inputMode="search"
            autoComplete="off"
            placeholder="zum Beispiel R² oder Kursziel"
            value={query}
            onInput={(e: Event) => setQuery((e.target as HTMLInputElement).value)}
          />
        </label>
        <p className="section-note" aria-live="polite">
          {query.trim()
            ? entries.length
              ? `${entries.length} von ${GLOSSARY.length} Begriffen passen.`
              : `Kein Begriff passt zu „${query.trim()}“. Versuche ein kürzeres Wort.`
            : `${GLOSSARY.length} Begriffe.`}
        </p>
        <dl className="glossary">
          {entries.map((entry) => (
            <div key={entry.id} id={`begriff-${entry.id}`} className={`glossary-entry${wanted === entry.id ? ' is-wanted' : ''}`}>
              <dt>{entry.term}</dt>
              <dd>
                <p>{entry.text}</p>
                {entry.example ? (
                  <p className="glossary-example">
                    <strong>Beispiel:</strong> {entry.example}
                  </p>
                ) : null}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="section" aria-labelledby="hilfe-fragen">
        <SectionTitle id="hilfe-fragen">Häufige Fragen</SectionTitle>
        <div className="help-faq">
          {FAQ.map(([question, answer]) => (
            <Disclosure key={question} summary={question}>
              <p>{answer}</p>
            </Disclosure>
          ))}
        </div>
      </section>

      <section className="section" aria-labelledby="hilfe-probleme">
        <SectionTitle id="hilfe-probleme">Wenn etwas nicht klappt</SectionTitle>
        <p>Jede Meldung der App nennt das Problem und den nächsten Schritt. Die häufigsten:</p>
        <dl className="help-dl">
          {PROBLEMS.map(([message, step]) => (
            <div key={message}>
              <dt>{message}</dt>
              <dd>{step}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
