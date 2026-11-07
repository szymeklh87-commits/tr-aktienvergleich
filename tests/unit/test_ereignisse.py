"""Ereignisse aus Schlagzeilen (ab 1.25.0, ``ereignisse-1``): Arten, bestätigt/Bericht/Gerücht, Kaufwarnung nur bei belegten
kritischen Ereignissen. Beispiele nach dem Muster bekannter früherer Fälle (Insolvenzantrag, verweigertes Testat,
Handelsaussetzung, Gewinnwarnung) mit erfundenen Firmennamen – und typische Fehlalarme, die nicht anschlagen dürfen."""

from __future__ import annotations

import unittest

from traktien.analytics import ereignisse as ev

NOW = 1_794_000_000  # Sekunden seit 1970
DAY = 86_400


def news(title: str, *, days_ago: float = 1.0, source: str | None = "Reuters", related: bool = True) -> dict:
    return {"titel": title, "quelle": source, "zeit": int(NOW - days_ago * DAY), "link": "https://example.org/x", "bezug": related}


class EventTests(unittest.TestCase):
    def test_known_critical_patterns(self):
        cases = {
            "Beispiel Bank parent files for Chapter 11 bankruptcy protection": ("insolvenz", "bestaetigt"),
            "Beispiel AG stellt Insolvenzantrag": ("insolvenz", "bericht"),
            "Wirtschaftsprüfer verweigert Testat – 1,9 Milliarden Euro fehlen bei der Beispiel AG": ("bilanz", "bericht"),
            "Beispiel Corp to restate three years of financial statements": ("bilanz", "bericht"),
            "SEC investigation into Beispiel Holdings widens": ("ermittlung", "bericht"),
            "Staatsanwaltschaft durchsucht Büros der Beispiel SE": ("ermittlung", "bericht"),
            "Trading in Beispiel shares halted after plunge": ("handelsaussetzung", "bericht"),
            "Beispiel warns of going concern doubt": ("liquiditaet", "bericht"),
            "Beispiel cuts full-year guidance as demand slows": ("gewinnwarnung", "bericht"),
            "Beispiel senkt Jahresprognose": ("gewinnwarnung", "bericht"),
        }
        for title, expected in cases.items():
            self.assertEqual(ev.classify(title, "Reuters"), expected, title)

    def test_positive_and_other_events(self):
        self.assertEqual(ev.classify("Beispiel beats estimates on record revenue"), ("zahlen_stark", "bericht"))
        self.assertEqual(ev.classify("Beispiel raises full-year guidance", "Business Wire"), ("prognose_hoch", "bestaetigt"))
        self.assertEqual(ev.classify("Beispiel wins $2 billion contract"), ("auftrag", "bericht"))
        self.assertEqual(ev.classify("Bank upgrades Beispiel to Buy"), ("analyst_hoch", "bericht"))
        self.assertEqual(ev.classify("Beispiel downgraded to Sell"), ("analyst_runter", "bericht"))
        self.assertEqual(ev.classify("Beispiel announces $50 million public offering"), ("verwaesserung", "bestaetigt"))

    def test_rumors_are_marked(self):
        self.assertEqual(ev.classify("Beispiel reportedly considering bankruptcy filing"), ("insolvenz", "geruecht"))
        self.assertEqual(ev.classify("Laut Kreisen erwägt die Beispiel AG eine Kapitalerhöhung"), ("verwaesserung", "geruecht"))

    def test_false_alarms_do_not_fire(self):
        for title in (
            "Production halted at Beispiel plant after storm",
            "Beispiel reports diluted EPS of $1.20",
            "Beispiel launches software upgrade for its devices",
            "Beispiel opens new headquarters",
            "Insider buys Beispiel shares",
        ):
            self.assertIsNone(ev.classify(title), title)

    def test_warning_only_for_recent_confirmed_critical_events(self):
        items = [news("Beispiel files for Chapter 11 bankruptcy", days_ago=2)]
        events = ev.events_of(items)
        self.assertEqual(ev.warning(events, NOW).art, "insolvenz")
        self.assertEqual(ev.light(events, NOW), "rot")
        old = ev.events_of([news("Beispiel files for Chapter 11 bankruptcy", days_ago=45)])
        self.assertIsNone(ev.warning(old, NOW), "älter als 30 Tage")
        rumor = ev.events_of([news("Beispiel reportedly weighs bankruptcy filing", days_ago=1)])
        self.assertIsNone(ev.warning(rumor, NOW), "Gerücht ist keine Kaufwarnung")
        self.assertEqual(ev.light(rumor, NOW), "grau")
        unrelated = ev.events_of([news("Beispiel files for Chapter 11 bankruptcy", related=False)])
        self.assertEqual(unrelated, [], "Meldung ohne Bezug zur Aktie zählt nicht")

    def test_light_and_duplicates(self):
        events = ev.events_of([
            news("Beispiel beats estimates", days_ago=1),
            news("Beispiel beats expectations again", days_ago=1.2),  # gleiche Art am selben Tag: einmal
            news("Beispiel wins contract", days_ago=3),
            news("Beispiel downgraded to Hold", days_ago=4),
        ])
        self.assertEqual([e.art for e in events], ["zahlen_stark", "auftrag", "analyst_runter"])
        self.assertEqual(ev.light(events, NOW), "gruen")
        self.assertEqual(ev.light([], NOW), "grau")
        d = events[0].as_dict()
        self.assertEqual(set(d), {"art", "bezeichnung", "ton", "kritisch", "stand", "titel", "quelle", "zeit", "link"})


if __name__ == "__main__":
    unittest.main()
