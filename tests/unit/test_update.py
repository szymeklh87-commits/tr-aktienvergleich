"""Aktualisieren auf Wunsch: Startlinks auf GitHub und nächster möglicher Kursstichtag."""

from __future__ import annotations

import datetime as dt
import os
import unittest
from unittest import mock

from traktien.config import load_pipeline_config
from traktien.jobs.cutoff import determine_cutoff, next_cutoff
from traktien.providers.demo import demo_calendars
from traktien.publish.site import SITE_SNAPSHOTS_DEFAULT, retained_snapshots, update_links
from tests.helpers import day

UTC = dt.timezone.utc


def stand(snapshot_id: str, completeness: str, *, intraday: bool = False) -> dict:
    entry = {"snapshot_id": snapshot_id, "completeness": completeness}
    if intraday:
        entry["art"] = "zwischenstand"
    return entry


class SiteRetentionTests(unittest.TestCase):
    """Ab 14.10.2026 hält die Website drei Stände (ein Zwischenstand zählt mit) und immer zusätzlich den neuesten
    vollständigen; ältere Stände bleiben als Archiv im Release."""

    def test_three_stands_in_configuration_and_as_fallback_in_code(self) -> None:
        self.assertEqual(int(load_pipeline_config().get("aufbewahrung.site_snapshots")), 3)
        self.assertEqual(SITE_SNAPSHOTS_DEFAULT, 3)

    def test_newest_three_including_the_intraday_stand(self) -> None:
        index = {
            "snapshots": [
                stand("2026-10-14_z1", "teilstand", intraday=True),
                stand("2026-10-13_a", "vollstaendig"),
                stand("2026-10-12_c", "vollstaendig"),
                stand("2026-10-12_b", "vollstaendig"),
                stand("2026-10-12_a", "teilstand"),
            ]
        }
        kept = [s["snapshot_id"] for s in retained_snapshots(index, SITE_SNAPSHOTS_DEFAULT)]
        self.assertEqual(kept, ["2026-10-14_z1", "2026-10-13_a", "2026-10-12_c"])

    def test_newest_complete_stand_is_kept_in_addition(self) -> None:
        index = {
            "snapshots": [
                stand("2026-10-14_z1", "teilstand", intraday=True),
                stand("2026-10-13_b", "teilstand"),
                stand("2026-10-12_b", "teilstand"),
                stand("2026-10-11_a", "vollstaendig"),
                stand("2026-10-10_a", "vollstaendig"),
            ]
        }
        kept = [s["snapshot_id"] for s in retained_snapshots(index, SITE_SNAPSHOTS_DEFAULT)]
        self.assertEqual(kept, ["2026-10-14_z1", "2026-10-13_b", "2026-10-12_b", "2026-10-11_a"])

    def test_one_stand_per_day_and_kind(self) -> None:
        """Ab 1.17.1: Ein zweites Mal gerechneter Kurstag verdrängt keinen älteren Tag mehr (24.10.2026: der 23.10. stand
        zweimal in „Frühere Stände“, der 21.10. fehlte); ein Zwischenstand desselben Tages bleibt eigene Art."""
        index = {
            "snapshots": [
                {"snapshot_id": "2026-10-23_68f9fbe5", "cutoff_session_date": "2026-10-23", "completeness": "vollstaendig"},
                {"snapshot_id": "2026-10-23_bce9bf2d", "cutoff_session_date": "2026-10-23", "completeness": "vollstaendig"},
                {"snapshot_id": "2026-10-22_bf62cacb", "cutoff_session_date": "2026-10-22", "completeness": "vollstaendig"},
                {"snapshot_id": "2026-10-22_cd0f7368", "cutoff_session_date": "2026-10-22", "completeness": "vollstaendig"},
                {"snapshot_id": "2026-10-21_aaaa0000", "cutoff_session_date": "2026-10-21", "completeness": "vollstaendig"},
            ]
        }
        kept = [s["snapshot_id"] for s in retained_snapshots(index, SITE_SNAPSHOTS_DEFAULT)]
        self.assertEqual(kept, ["2026-10-23_68f9fbe5", "2026-10-22_bf62cacb", "2026-10-21_aaaa0000"])
        with_intraday = {"snapshots": [stand("2026-10-23_z1", "teilstand", intraday=True) | {"cutoff_session_date": "2026-10-23"}] + index["snapshots"]}
        kept = [s["snapshot_id"] for s in retained_snapshots(with_intraday, SITE_SNAPSHOTS_DEFAULT)]
        self.assertEqual(kept, ["2026-10-23_z1", "2026-10-23_68f9fbe5", "2026-10-22_bf62cacb"])

    def test_stand_of_an_older_method_stays_next_to_the_recomputed_day(self) -> None:
        """Ab 1.18.0: Rechnet eine neue Methode (tr-methode-1.10.0) einen Kurstag noch einmal, bleibt der Stand nach der
        alten Methode desselben Tages erhalten – historische Stände bleiben unverändert lesbar."""
        new, old = {"method": "tr-methode-1.10.0"}, {"method": "tr-methode-1.9.0"}
        index = {
            "snapshots": [
                {"snapshot_id": "2026-10-23_n1", "cutoff_session_date": "2026-10-23", "completeness": "vollstaendig", "versions": new},
                {"snapshot_id": "2026-10-23_o2", "cutoff_session_date": "2026-10-23", "completeness": "vollstaendig", "versions": old},
                {"snapshot_id": "2026-10-23_o1", "cutoff_session_date": "2026-10-23", "completeness": "vollstaendig", "versions": old},
                {"snapshot_id": "2026-10-22_o1", "cutoff_session_date": "2026-10-22", "completeness": "vollstaendig", "versions": old},
            ]
        }
        kept = [s["snapshot_id"] for s in retained_snapshots(index, SITE_SNAPSHOTS_DEFAULT)]
        self.assertEqual(kept, ["2026-10-23_n1", "2026-10-23_o2", "2026-10-22_o1"])


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
