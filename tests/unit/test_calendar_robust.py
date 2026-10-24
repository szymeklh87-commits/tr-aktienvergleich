"""Ab 1.17: Ein Börsenkalender, der sich mit den installierten Bibliotheken nicht laden lässt, bricht den Lauf nicht ab.

Gemessen am 24.10.2026 in GitHub Actions: pandas 3.1.0 mit exchange_calendars 4.13.2 → ASEX (NotImplementedError) und
XTAE (ValueError). Der Kalender gilt dann als nicht verfügbar, mit Grund; die übrigen bleiben nutzbar.
"""

from __future__ import annotations

import sys
import types
import unittest


class _FakeCalendar:
    def __init__(self, code: str) -> None:
        self.code = code


def _fake_xcals() -> types.ModuleType:
    module = types.ModuleType("exchange_calendars")
    module.__version__ = "test"
    module.get_calendar_names = lambda include_aliases=True: ["XETR", "ASEX", "XTAE"]

    def get_calendar(code):
        if code == "ASEX":
            raise NotImplementedError("offsets")
        if code == "XTAE":
            raise ValueError("weekmask")
        return _FakeCalendar(code)

    module.get_calendar = get_calendar
    return module


class CalendarRobustnessTests(unittest.TestCase):
    def setUp(self):
        self._saved = sys.modules.get("exchange_calendars")
        sys.modules["exchange_calendars"] = _fake_xcals()

    def tearDown(self):
        if self._saved is None:
            sys.modules.pop("exchange_calendars", None)
        else:
            sys.modules["exchange_calendars"] = self._saved

    def test_unloadable_calendars_are_unavailable_with_reason(self):
        from traktien.providers.calendars import ExchangeCalendarsProvider

        provider = ExchangeCalendarsProvider()
        self.assertTrue(provider.available("XETR"))
        self.assertFalse(provider.available("ASEX"))
        self.assertFalse(provider.available("XTAE"))
        self.assertFalse(provider.available("XXXX"))
        self.assertEqual(provider.broken, {"ASEX": "NotImplementedError", "XTAE": "ValueError"})
        # einmal festgestellt, wird nicht erneut geladen
        self.assertFalse(provider.available("ASEX"))


if __name__ == "__main__":
    unittest.main()
