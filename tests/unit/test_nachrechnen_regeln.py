"""Regeln der unabhängigen Nachrechnung je Methodenversion (ab 1.18.1, ``tests/live/nachrechnen.py``)."""

from __future__ import annotations

import unittest

from tests.live import nachrechnen


class ToleratedSessions(unittest.TestCase):
    def test_rule_exists_only_since_it_is_in_the_manifest(self):
        """tr-methode-1.7.0 (Software bis 1.5.0) hatte keine Ausnahme für einen fehlenden Börsentag – ohne Eintrag 0;
        ab 1.5.1 steht der Wert im Manifest (tr-methode-1.8.0 bis 1.10.0: 1)."""
        self.assertEqual(nachrechnen.tolerated_sessions({}), 0)
        self.assertEqual(nachrechnen.tolerated_sessions({"min_session_coverage": {"num": 49, "den": 50}}), 0)
        self.assertEqual(nachrechnen.tolerated_sessions({"tolerated_missing_sessions": 1}), 1)
        self.assertEqual(nachrechnen.tolerated_sessions({"tolerated_missing_sessions": 0}), 0)


class StandIds(unittest.TestCase):
    def test_only_release_stand_ids(self):
        self.assertEqual(nachrechnen.stand_id("2026-10-12_5092bae0"), "2026-10-12_5092bae0")
        with self.assertRaises(Exception):
            nachrechnen.stand_id("2026-10-12_5092bae0 --x")


if __name__ == "__main__":
    unittest.main()
