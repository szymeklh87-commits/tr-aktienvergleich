import { useApp } from '../state/AppState';

function ratio(value: unknown, fallback: string): string {
  if (value && typeof value === 'object' && 'num' in value && 'den' in value) {
    const r = value as { num: number; den: number };
    return `${((100 * r.num) / r.den).toLocaleString('de-DE', { maximumFractionDigits: 1 })} %`;
  }
  return fallback;
}

export function MethodView() {
  const { manifest } = useApp();
  const method = (manifest?.method ?? {}) as Record<string, unknown>;
  const minTrend = Number(method.min_obs_trend ?? 15);
  const anchor = Number(method.anchor_max_gap_days ?? 7);
  const jump = Number(method.jump_factor ?? 3);
  const sessions = ratio(method.min_session_coverage, '98 %');
  const volume = ratio(method.min_volume_coverage, '80 %');

  return (
    <article className="prose">
      <p className="lede">
        Die App beschreibt, was in der Vergangenheit passiert ist. Sie gibt keine Kauf- oder Verkaufsempfehlung und keine Prognose. Methodenversion: {manifest?.versions.method ?? 'tr-methode-1.2.0'}.
      </p>

      <h2>Zeitraum: 1 bis 90 Kalendertage</h2>
      <p>
        Alle Zeiträume enden am selben Kursstichtag D: dem jüngsten Handelstag, dessen Schlusskurse an allen an diesem Tag geöffneten Börsen bereits feststehen. „30 Tage“ heißt 30 Kalendertage zurück. Als Startkurs gilt der Schlusskurs der letzten Börsensitzung am oder vor diesem Ziel-Startdatum, höchstens {anchor} Kalendertage
        früher. Fehlt an dieser Sitzung ein Kurs, wird nicht auf einen älteren Kurs ausgewichen; der Zeitraum ist dann für diese Aktie nicht berechenbar.
      </p>
      <p>Wochenenden und Feiertage führen dazu, dass benachbarte Kalenderzeiträume manchmal dieselben tatsächlichen Start- und Endkurse haben. Jede Zeile nennt deshalb den tatsächlichen Beginn und das Ende.</p>

      <h2>Kursrendite</h2>
      <p className="formula">r = Schlusskurs am Ende ÷ Schlusskurs am Start − 1</p>
      <p>
        Gerechnet wird in der Notierungswährung der Referenzbörse, splitbereinigt, ohne Dividenden, Gebühren, Steuern und ohne Wechselkurseffekt. Ein Kurs in Pence (GBp) bleibt in Pence; die Rendite ist davon unabhängig. Für die reine Rendite reichen zwei echte Schlusskurse.
      </p>

      <h2>Gleichmäßigkeit (R²)</h2>
      <p>
        Durch die Tagesschlusskurse des Zeitraums wird die beste gerade Linie gelegt (kleinste Quadrate, Zeitachse in Handelsbeobachtungen 0, 1, 2 …). R² ist der Anteil der Kursschwankung, den diese Gerade erklärt:
      </p>
      <p className="formula">R² = 1 − Summe der quadrierten Abstände zur Geraden ÷ Summe der quadrierten Abstände zum Mittelwert</p>
      <p>
        Beispiel: R² = 0,9326 heißt, 93,26 % der Kursbewegung liegen auf einer Geraden – der Kurs ist sehr gleichmäßig gelaufen. R² sagt nichts über die Richtung; auch ein gleichmäßig fallender Kurs hat ein hohes R². Deshalb zählen für die Gleichmäßigkeit nur Aktien mit positiver Rendite und positiver
        Steigung. Ein stetig, aber gekrümmt steigender Kurs (zum Beispiel immer schneller) kann ein niedrigeres R² haben, obwohl er nie gefallen ist.
      </p>
      <h3>Ergänzende Kennzahlen</h3>
      <ul>
        <li>Relative Steigung: Steigung der Geraden je Handelstag in Prozent des Durchschnittskurses.</li>
        <li>Residualrauschen: typische Abweichung der Kurse von der Geraden in Prozent des Durchschnittskurses.</li>
        <li>Größter Rückgang: stärkster Fall von einem Zwischenhoch innerhalb des Zeitraums.</li>
        <li>Volumenabdeckung: Anteil der Tage mit belegtem Handelsumsatz.</li>
      </ul>

      <h2>Wer wird verglichen?</h2>
      <p>Pro Zeitraum gibt es zwei Vergleichsfelder:</p>
      <ul>
        <li>
          <strong>V – Aktien mit veröffentlichter Kursrendite:</strong> eindeutig identifiziert, Schlusskurs am Stichtag, mindestens 2 echte Kurse, mindestens {sessions} der erwarteten Börsensitzungen mit Kurs, mindestens {volume} der Tage mit belegtem Umsatz, kein ungeklärter Kurssprung um mehr als das {jump}-Fache und keine offene Kapitalmaßnahme.
        </li>
        <li>
          <strong>U – gleichmäßig gestiegene Aktien:</strong> zusätzlich mindestens {minTrend} echte Tageskurse, positive Rendite, positive Steigung und ein berechenbares R². U ist immer ein Teil von V.
        </li>
      </ul>
      <p>In sehr kurzen Zeiträumen (etwa unter drei Wochen) gibt es weniger als {minTrend} Tageskurse. Dort bleibt die Gleichmäßigkeit leer; die reine Renditeliste funktioniert trotzdem.</p>

      <h2>Elf Gewichtungen</h2>
      <p>Die erste Zahl ist immer der Anteil Gleichmäßigkeit, die zweite der Anteil Kursrendite: 0/100, 10/90, 20/80 … 100/0. Innerhalb des Vergleichsfelds bekommt jede Aktie zwei Perzentile von 0 bis 100:</p>
      <p className="formula">P = 100 × (Durchschnittsrang − 1) ÷ (M − 1)</p>
      <p>
        M ist die Zahl der verglichenen Aktien; der Rang wird aufsteigend vergeben, exakt gleiche Werte erhalten denselben Durchschnittsrang. G ist das Perzentil von R², R das Perzentil der Kursrendite. Der Score lautet:
      </p>
      <p className="formula">Score = w/100 × G + (1 − w/100) × R</p>
      <p>Beispiel 60/40 mit G = 80 und R = 60: 0,6 × 80 + 0,4 × 60 = 72. Bei 0/100 zählt nur die Rendite, bei 100/0 nur die Gleichmäßigkeit.</p>
      <p>Gibt es nur eine einzige qualifizierte Aktie, erhält sie Score 100 mit dem Hinweis „Einziger qualifizierter Titel – keine relative Konkurrenzbewertung“.</p>

      <h3>Nativ oder gleiches Vergleichsfeld</h3>
      <ul>
        <li>
          <strong>Nativ (Standard):</strong> 0/100 vergleicht alle Aktien aus V und lässt auch negative Renditen zu. Alle anderen Gewichtungen vergleichen nur U.
        </li>
        <li>
          <strong>Gleiches Vergleichsfeld:</strong> alle elf Gewichtungen vergleichen dieselben Aktien aus U. Nur so zeigt ein Vergleich zweier Gewichtungen allein die Wirkung der Gewichtung.
        </li>
      </ul>

      <h3>Reihenfolge und Gleichstände</h3>
      <ul>
        <li>0/100: höhere Kursrendite zuerst, bei exakt gleicher Rendite nach ISIN.</li>
        <li>10/90 bis 90/10: höherer Score, dann höhere Rendite, dann höheres R², dann ISIN.</li>
        <li>100/0: höheres R², dann höhere Steigung, dann geringeres Rauschen, dann ISIN.</li>
      </ul>
      <p>Exakt gleiche Werte werden als Gleichstand gekennzeichnet; die ISIN legt nur die Anzeigereihenfolge fest.</p>

      <h2>Höchste Rendite 1–90 Tage</h2>
      <p>
        Für jeden der 90 Zeiträume steht die Aktie mit der höchsten Kursrendite aus V. Sind alle Renditen negativ, steht dort der geringste Verlust mit Vorzeichen. Das Gesamtmaximum ist der höchste Wert über alle geprüften Aktie-Zeitraum-Paare – ein rückblickend ausgewählter Bestwert,
        keine erwartete Rendite. Renditen verschiedener Zeiträume werden nie addiert oder auf ein Jahr hochgerechnet.
      </p>

      <h2>Häufigste Aktien</h2>
      <p>
        Eine Zelle ist eine Kombination aus Zeitraum und Gewichtung eines Datenstands (höchstens 90 × 11 = 990). Ein Treffer ist ein Platz unter den ersten K (1, 3 oder 10) einer veröffentlichten Rangliste; jede Aktie zählt je Zelle höchstens einmal. Leere Zellen ohne Rangliste zählen nicht
        mit.
      </p>
      <ul>
        <li>N1, N3, N10: Zahl der Zellen mit Platz 1, Platz 1–3, Platz 1–10.</li>
        <li>E: Zahl der gültigen Ranglisten in der Auswahl. A: Zahl der Zellen, in denen die Aktie überhaupt bewertet wurde.</li>
        <li>Verschiedene Zeiträume: in wie vielen unterschiedlichen Zeiträumen die Aktie unter den ersten K war.</li>
      </ul>
      <p>
        Benachbarte Zeiträume und ähnliche Gewichtungen beruhen auf fast denselben Kursen. Viele Treffer sind deshalb keine unabhängigen Bestätigungen, und Anteile wie N10 ÷ E sind keine Wahrscheinlichkeit für künftige Gewinne. Native und gleiche Vergleichsfelder werden nie zusammengezählt.
      </p>

      <h2>Daten und Grenzen</h2>
      <ul>
        <li>Das Aktienuniversum stammt aus der öffentlichen Instrumentenliste von Trade Republic (nur Aktienabschnitt). Eine Listung bedeutet nicht, dass eine Aktie im eigenen Konto jederzeit handelbar ist.</li>
        <li>Kurse: {manifest?.provider.prices ?? 'siehe Datenstand'}. {manifest?.provider.license_note ?? ''}</li>
        <li>Es werden ausschließlich Tagesschlusskurse verwendet. Live- oder Intradaykurse sind nicht eingerichtet; eine 1-Tages-Ansicht zeigt nur die zwei belegten Schlusskurse.</li>
        <li>Fehlende Börsensitzungen bleiben im Chart als Lücke sichtbar. Es werden keine Kurse erfunden oder aufgefüllt.</li>
        <li>Diese App ist kein Angebot von Trade Republic und steht in keiner Verbindung zu Trade Republic.</li>
      </ul>
    </article>
  );
}
