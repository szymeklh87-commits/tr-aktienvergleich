import { useApp } from '../state/AppState';

function ratio(value: unknown, fallback: string): string {
  if (value && typeof value === 'object' && 'num' in value && 'den' in value) {
    const r = value as { num: number; den: number };
    return `${((100 * r.num) / r.den).toLocaleString('de-DE', { maximumFractionDigits: 1 })} %`;
  }
  return fallback;
}

function money(value: number): string {
  return `${(value / 1e6).toLocaleString('de-DE', { maximumFractionDigits: 1 })} Mio. USD`;
}

export function MethodView() {
  const { manifest } = useApp();
  const turnover = manifest?.turnover;
  const venue = manifest?.venue_check ?? null;
  const method = (manifest?.method ?? {}) as Record<string, unknown>;
  const minTrend = Number(method.min_obs_trend ?? 15);
  const anchor = Number(method.anchor_max_gap_days ?? 7);
  const jump = Number(method.jump_factor ?? 3);
  const sessions = ratio(method.min_session_coverage, '98 %');
  const volume = ratio(method.min_volume_coverage, '80 %');
  const rule = (method.rotation ?? {}) as Record<string, number | number[] | string>;
  const num = (key: string, fallback: number): number => (typeof rule[key] === 'number' ? (rule[key] as number) : fallback);
  const pctText = (value: number, digits = 0) => `${(value * 100).toLocaleString('de-DE', { maximumFractionDigits: digits })} %`;

  return (
    <article className="prose">
      <p className="lede">
        Die App beschreibt, was in der Vergangenheit passiert ist. Sie gibt keine Anlageberatung und keine Prognose; die Umschichtungs-Regel zeigt nur, was eine feste Rechenregel täte. Methodenversion:{' '}
        {manifest?.versions.method ?? 'tr-methode-1.6.0'}.
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

      <h2>Zwei Rendite-Ranglisten</h2>
      <p>
        <strong>Höchste Kursrendite:</strong> alle Aktien mit veröffentlichter Kursrendite (Feld V), sortiert nur nach Kursrendite – das ist die Gewichtung 0 % Gleichmäßigkeit / 100 % Kursrendite. Es gibt keine
        Mindestgrenze für Aktienpreis, Börsenwert oder Umsatz; die Datenqualitätsprüfungen gelten trotzdem. Aktien mit einem Ø Tagesumsatz unter {money(turnover?.sehr_niedrig_usd ?? 1_000_000)} sind als
        „sehr niedriger Umsatz“ gekennzeichnet.
      </p>
      <p>
        <strong>Höchste Kursrendite – Ø Tagesumsatz mindestens {money(turnover?.schwelle_usd ?? 10_000_000)}:</strong> dieselben Kurse, Zeiträume, derselbe Kursstichtag und dieselbe Renditeformel. Aufgenommen
        werden nur Aktien, deren Ø Tagesumsatz bestimmt ist und die Schwelle erreicht. Der Umsatz ist ein Aufnahmefilter, kein Sortierkriterium und kein zweiter Renditewert – die Reihenfolge ist exakt die der
        ersten Liste ohne die übrigen Aktien.
      </p>
      <p className="formula">Ø Tagesumsatz = Mittelwert über die letzten {turnover?.sitzungen ?? 20} abgeschlossenen Sitzungen von (Schlusskurs × gemeldetes Volumen)</p>
      <ul>
        <li>Kurs und Volumen stammen von derselben Notierung an der Referenzbörse, beide splitbereinigt. Liegt ein Split oder eine Zusammenlegung innerhalb der Sitzungen, gilt der Umsatz als nicht bestimmbar.</li>
        <li>Mindestens {turnover?.min_sitzungen_mit_umsatz ?? 16} der {turnover?.sitzungen ?? 20} Sitzungen brauchen ein positives Volumen. Fehlende Tage zählen nicht als null, sie werden ausgelassen.</li>
        <li>
          Andere Währungen werden nur für diesen Filter indikativ in US-Dollar umgerechnet, je Sitzung mit dem Referenzkurs dieses Tages oder dem letzten davor ({turnover?.wechselkurse.quelle ?? 'EZB-Referenzkurse'}). Kurse
          in Untereinheiten (Pence, Agorot, Cent) werden vorher in die Hauptwährung umgerechnet.
        </li>
        <li>Fehlen Volumen oder Wechselkurs, kommt die Aktie nicht in die zweite Liste; in der ersten kann sie trotzdem stehen.</li>
      </ul>
      <p>
        Hinweise in beiden Listen: ein einzelner Tag erklärt mehr als die Hälfte der Bewegung (Impulstag), Kurssprung ab 15 % mit anschließend kaum Bewegung (Übernahmemuster), Split im Zeitraum, geprüfter
        Kurssprung und auffällige Kursabweichung zwischen Börsenplätzen.
      </p>

      <h2>Abgleich mit einem zweiten Börsenplatz</h2>
      <p>
        Für jede Aktie, die in mindestens einem Zeitraum unter den ersten {venue?.plaetze ?? 10} Plätzen einer der beiden Rendite-Ranglisten steht, misst der Server die Kursrendite zusätzlich an einem zweiten
        Handelsplatz derselben ISIN – bevorzugt Xetra, dann Frankfurt, sonst eine andere unterstützte Börse (keine OTC-Märkte) – und zwar für alle ihre Zeiträume. Verwendet werden die Schlusskurse dieses
        Handelsplatzes zum letzten Handelstag am oder vor dem Start- und dem Enddatum (höchstens {venue?.max_abstand_tage ?? 4} Tage früher), umgerechnet in die Währung der Referenzbörse mit den
        EZB-Referenzkursen.
      </p>
      <p className="formula">Abweichung = (1 + Rendite am zweiten Platz) ÷ (1 + Rendite an der Referenzbörse) − 1</p>
      <p>
        Auffällig ist ein Zeitraum, wenn diese Abweichung oder die Abweichung des Endkurses mehr als {Math.round((venue?.schwelle_wertentwicklung ?? 0.1) * 100)} % beträgt. Das deutet auf einen Datenfehler,
        eine nicht bereinigte Kapitalmaßnahme oder eine Handelsaussetzung hin. Es ist nur ein Hinweis: Rendite und Rang bleiben die der Referenzbörse. Fehlende Vergleichskurse werden nicht ersetzt; dann steht dort
        „Vergleichskurse fehlen“. Aktien auf späteren Plätzen werden nicht abgeglichen.
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

      <h2>Gruppenvergleich A/B</h2>
      <p>
        Zwei Aktiengruppen mit demselben Kursstichtag, denselben Zeitregeln und derselben Renditeformel ({manifest?.versions.groups ?? 'gruppen-v1'}):
      </p>
      <ul>
        <li>
          <strong>Gruppe A – ohne Mindestumsatz:</strong> alle Aktien der TR-Liste mit ausreichender Datenqualität (Vergleichsfelder V und U wie oben).
        </li>
        <li>
          <strong>Gruppe B – höherer Handelsumsatz:</strong> dieselben Aktien, zusätzlich Ø Tagesumsatz mindestens {money(turnover?.schwelle_usd ?? 10_000_000)} über {turnover?.sitzungen ?? 20} abgeschlossene
          Sitzungen (Vergleichsfelder V ∩ L und U ∩ L).
        </li>
      </ul>
      <p>
        Beide Gruppen haben alle elf Gewichtungen, also bis zu 2 × 90 × 11 Ranglisten je Kursstichtag; die Matrix zeigt 1–30 Tage (2 × 30 × 11 = 660). Rendite und R² werden je Gruppe in Perzentile von 0 bis 100
        umgerechnet – <strong>innerhalb der Gruppe</strong>. Ein Score der Gruppe B ist deshalb nicht mit einem Score der Gruppe A vergleichbar. Für 0/100 und 100/0 ergibt das dieselbe Reihenfolge wie Gruppe A
        ohne die übrigen Aktien; gemischte Gewichtungen können abweichen. Gleichstände wie oben, zuletzt nach ISIN.
      </p>
      <p>
        <strong>Matrix:</strong> je Zeitraum (Zeile) und Gewichtung (Spalte) die erstplatzierte Aktie mit Name, ISIN, Score und Kursrendite. Fehlen für die Gleichmäßigkeit die nötigen {minTrend} Tageskurse, steht
        dort „nicht berechenbar“ – die reine Renditeliste erscheint trotzdem. Wiederkehrende Aktien tragen in beiden Gruppen und allen Ansichten dieselbe Farbe und die Zahl ihrer Platz-1-Vorkommen (Identität
        über die ISIN; Aktiengattungen und ADRs haben eigene ISINs). „≡“ kennzeichnet Zellen, deren Spitzenaktie denselben tatsächlichen Start- und Endkurs hat wie in den genannten Zeiträumen.
      </p>
      <p>
        <strong>Häufigkeitsranking je Gruppe:</strong> sortiert nach der Zahl der Ranglisten mit Platz 1, dann Top 3, Top 10, ISIN. Je Rangliste zählt eine Aktie höchstens einmal; Platz 1 zählt zugleich zu
        Top 3 und Top 10, die Spalten werden nie addiert. „Auswertbar“ ist die Zahl der Ranglisten der Auswahl, in denen die Aktie einen Rang hat. Wahlweise je einzelner Gewichtung, über alle elf oder A und B
        getrennt nebeneinander. „Identische Kursfenster nur einmal zählen“ fasst Kombinationen aus Gruppe, Gewichtung und tatsächlichem Start- und Enddatum zusammen; verschiedene Gewichtungen bleiben verschieden.
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

      <h2>Umschichtungs-Regel</h2>
      <p>
        Eine feste, mechanische Regel zum Ausprobieren ({manifest?.rotation?.version ?? 'rotation-v1'}). Sie hält gedanklich N Aktien zu gleichen Teilen und tauscht sie zu festen Terminen aus. Gerechnet wird mit
        Wochenwerten: je Aktie und Woche der letzte Schlusskurs, die Umsatzsumme und der Schlusskurs der ersten Sitzung.
      </p>
      <ul>
        <li>
          <strong>Auswahl am Prüftag:</strong> Ø Tagesumsatz der letzten {num('turnover_weeks', 4)} Wochen mindestens {money(num('min_turnover_usd', 10_000_000))} (Summe Schlusskurs × Volumen ÷ Sitzungen mit
          Volumen, in US-Dollar mit dem EZB-Referenzkurs), an mindestens {pctText(num('min_positive_share', 0.8))} der Sitzungen Umsatz, Kurse an mindestens {pctText(num('min_coverage', 0.9))} der Sitzungen im
          Trendzeitraum, kein Tagessprung über das {num('max_jump_factor', 3)}-Fache.
        </li>
        <li>
          <strong>Trend:</strong> Kursrendite über 13 Wochen (91 Tage) oder 4 Wochen (28 Tage) in Notierungswährung; höherer Trend zuerst, bei Gleichstand nach ISIN.
        </li>
      </ul>
      <p className="formula">Trend = Schlusskurs am Prüftag ÷ letzter Schlusskurs der Woche vor 13 (bzw. 4) Wochen − 1</p>
      <ul>
        <li>
          <strong>Termine:</strong> Entscheidung nach Börsenschluss am ersten Freitag im Monat (Variante: jeden Freitag), Ausführung zum Schlusskurs der ersten Sitzung danach – so, wie man frühestens handeln kann.
        </li>
        <li>
          <strong>Halten und Tauschen:</strong> Eine gehaltene Aktie bleibt, solange sie unter den ersten {num('keep_rank_factor', 2)} × N Plätzen liegt. Freie Plätze bekommen die bestplatzierten nicht gehaltenen
          Aktien mit je 1/N des Depotwerts. Gehaltene Aktien werden nur angeglichen, wenn ihr Anteil mehr als {Math.round(num('band', 0.05) * 100)} Prozentpunkte von 1/N abweicht. Reicht das Geld nicht für alle
          Käufe, werden sie gleichmäßig gekürzt; übriges Geld bleibt als Bargeld im Regeldepot.
        </li>
        <li>
          <strong>Kosten und Steuern:</strong> je Order {num('fee_eur', 1).toLocaleString('de-DE', { minimumFractionDigits: 2 })} € und {pctText(num('spread', 0.001), 1)} Kursabschlag. Abgeltungsteuer mit
          Solidaritätszuschlag ({pctText(num('tax_rate', 0.26375), 3)}) auf realisierte Gewinne nach Verlustverrechnung und Sparerpauschbetrag ({num('allowance_eur', 1000).toLocaleString('de-DE')} € je
          Kalenderjahr); Verluste werden im selben Jahr erstattet, sonst in den Verlusttopf vorgetragen. Keine Kirchensteuer, keine Quellensteuer, keine Dividenden.
        </li>
        <li>
          <strong>Bewertung:</strong> in Euro zu den Freitagsschlusskursen mit den EZB-Referenzkursen. Vergleichslinie: alle Kandidaten zu gleichen Teilen, an jedem Termin neu aufgeteilt, ohne Kosten.
        </li>
        <li>
          <strong>Rückblick:</strong> bis {num('history_years', 3)} Jahre, mit den Aktien, die heute in der TR-Liste stehen und heute mindestens {money(num('pool_min_turnover_usd', 2_000_000))} am Tag
          umsetzen. Aktien, die es nicht mehr gibt, fehlen – das Ergebnis ist dadurch eher zu gut.
        </li>
        <li>
          <strong>Tagesvorschlag:</strong> dieselbe Regel auf den neuesten Kursstand angewendet (Wochen rückwärts ab dem Kursstichtag), ausgehend vom Regeldepot nach der letzten Umschichtung im Rückblick.
        </li>
      </ul>

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
