"""Aktualisieren auf Wunsch: Startlinks auf GitHub und nächster möglicher Kursstichtag."""

from __future__ import annotations

import datetime as dt
import os
import unittest
from unittest import mock

from traktien.jobs.cutoff import determine_cutoff, next_cutoff
from traktien.providers.demo import demo_calendars
from traktien.publish.site import update_links
from tests.helpers import day

UTC = dt.timezone.utc


class UpdateLinkTests(unittest.TestCase):
    def test_links_only_inside_github_actions(self) -> None:
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "simon/tr-aktienvergleich", "GITHUB_SERVER_URL": "https://github.com"}):
            links = update_links()
        self.assertEqual(links["starten_url"], "https://github.com/simon/tr-aktienvergleich/actions/workflows/taeglich.yml")
        self.assertEqual(links["laeufe_url"], "https://github.com/simon/tr-aktienvergleich/actions")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(update_links())

    def test_unsafe_values_are_ignored(self) -> None:
        for repository in ("simon/tr aktien", "<script>/x", "simon", "a/b/c"):
            with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": repository}, clear=True):
                self.assertIsNone(update_links(), repository)
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "simon/x", "GITHUB_SERVER_URL": "javascript:alert(1)"}, clear=True):
            self.assertIsNone(update_links())


class NextCutoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calendars = demo_calendars()
        self.codes = {"XNYS", "XETR", "XLON", "XTKS", "XHKG", "XASX"}

    def test_next_session_day_ready_one_hour_after_last_close(self) -> None:
        # Stichtag Montag 12.10.: nächster Tag Dienstag, New York schließt 16:00 EDT = 20:00 UTC
        result = next_cutoff(self.codes, self.calendars, day(2026, 10, 12), grace_minutes=60)
        self.assertEqual(result.day, day(2026, 10, 13))
        self.assertEqual(result.ready_utc, dt.datetime(2026, 10, 13, 21, 0, tzinfo=UTC))

    def test_weekend_is_skipped(self) -> None:
        result = next_cutoff(self.codes, self.calendars, day(2026, 10, 9), grace_minutes=60)
        self.assertEqual(result.day, day(2026, 10, 12))

    def test_same_rule_as_cutoff_determination(self) -> None:
        current = day(2026, 10, 12)
        nxt = next_cutoff(self.codes, self.calendars, current, grace_minutes=60)
        just_before = nxt.ready_utc - dt.timedelta(minutes=1)
        at_ready = nxt.ready_utc + dt.timedelta(seconds=1)
        self.assertEqual(determine_cutoff(self.codes, self.calendars, just_before, grace_minutes=60).cutoff_day, current)
        self.assertEqual(determine_cutoff(self.codes, self.calendars, at_ready, grace_minutes=60).cutoff_day, nxt.day)


if __name__ == "__main__":
    unittest.main()
