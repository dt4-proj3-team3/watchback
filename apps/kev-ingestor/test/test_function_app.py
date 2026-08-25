import copy
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import requests

os.environ.setdefault("STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import function_app  # noqa: E402


NOW = datetime(2026, 8, 16, 12, 0, 0, tzinfo=timezone.utc)

ITEM_A = {
    "cveID": "CVE-2024-0001",
    "vendorProject": "ExampleCorp",
    "product": "ExampleProduct",
    "vulnerabilityName": "Example Vulnerability A",
    "dateAdded": "2024-01-01",
    "shortDescription": "desc a",
    "requiredAction": "Apply updates",
    "dueDate": "2024-01-22",
    "knownRansomwareCampaignUse": "Unknown",
    "notes": "",
    "cwes": ["CWE-79", "CWE-89"],
}

ITEM_B = {
    "cveID": "CVE-2024-0002",
    "vendorProject": "OtherCorp",
    "product": "OtherProduct",
    "vulnerabilityName": "Example Vulnerability B",
    "dateAdded": "2024-02-01",
    "shortDescription": "desc b",
    "requiredAction": "Apply updates",
    "dueDate": "2024-02-22",
    "knownRansomwareCampaignUse": "Unknown",
    "notes": "",
    "cwes": ["CWE-20"],
}


def make_snapshot(items, catalog_version="2026.08.16", date_released="2026-08-16T00:00:00Z"):
    return {
        "catalogVersion": catalog_version,
        "dateReleased": date_released,
        "vulnerabilities": [copy.deepcopy(i) for i in items],
    }


def make_state(items_by_id, last_processed_commit_sha="sha1", pending_removed=None):
    return {
        "last_processed_commit_sha": last_processed_commit_sha,
        "last_processed_at": NOW.isoformat(),
        "last_catalog_version": "2026.08.16",
        "items": {
            cve_id: {"hash": function_app.compute_hash(item), "item": copy.deepcopy(item)}
            for cve_id, item in items_by_id.items()
        },
        "pending_removed": pending_removed or {},
    }


class ComputeHashTests(unittest.TestCase):
    def test_array_reorder_does_not_change_hash(self):
        reordered = copy.deepcopy(ITEM_A)
        reordered["cwes"] = list(reversed(reordered["cwes"]))
        self.assertEqual(function_app.compute_hash(ITEM_A), function_app.compute_hash(reordered))


class KevPollCaseTests(unittest.TestCase):
    def setUp(self):
        patcher_load = patch.object(function_app, "load_state")
        patcher_save = patch.object(function_app, "save_state")
        patcher_sha = patch.object(function_app, "get_latest_commit_sha")
        patcher_fetch = patch.object(function_app, "fetch_kev_catalog")
        patcher_bronze = patch.object(function_app, "write_to_bronze")
        patcher_heartbeat = patch.object(function_app, "write_heartbeat")

        self.mock_load_state = patcher_load.start()
        self.mock_save_state = patcher_save.start()
        self.mock_get_sha = patcher_sha.start()
        self.mock_fetch = patcher_fetch.start()
        self.mock_write_to_bronze = patcher_bronze.start()
        self.mock_write_heartbeat = patcher_heartbeat.start()

        for p in (patcher_load, patcher_save, patcher_sha, patcher_fetch, patcher_bronze, patcher_heartbeat):
            self.addCleanup(p.stop)

    # 1. 변경 없는 스냅샷을 두 번 연속 처리해도 Bronze 이벤트가 발생하지 않는다.
    def test_case_1_no_change_twice(self):
        state = make_state({"CVE-2024-0001": ITEM_A})
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha1"  # 커밋 변화 없음

        function_app.run_poll_cycle(NOW)
        function_app.run_poll_cycle(NOW + timedelta(minutes=10))

        self.mock_fetch.assert_not_called()
        self.mock_write_to_bronze.assert_not_called()

    # 2. catalogVersion/dateReleased만 바뀐 스냅샷 처리 시 per-item hash가 전부 동일해 이벤트가 발생하지 않는다.
    def test_case_2_catalog_metadata_only_change(self):
        snapshot_v1 = make_snapshot([ITEM_A, ITEM_B], catalog_version="2026.08.16")
        snapshot_v2 = make_snapshot([ITEM_A, ITEM_B], catalog_version="2026.08.17")

        hashes_v1 = {v["cveID"]: function_app.compute_hash(v) for v in snapshot_v1["vulnerabilities"]}
        hashes_v2 = {v["cveID"]: function_app.compute_hash(v) for v in snapshot_v2["vulnerabilities"]}
        self.assertEqual(hashes_v1, hashes_v2)

        previous_items = {cve_id: {"hash": h} for cve_id, h in hashes_v1.items()}
        added, removed_candidates, updated = function_app.diff_items(hashes_v2, previous_items)
        self.assertEqual(added, set())
        self.assertEqual(removed_candidates, set())
        self.assertEqual(updated, set())

    # 3. 신규 cveID가 추가되면 kev_added 이벤트가 발행되고 state.items에 반영된다.
    def test_case_3_new_cve_added(self):
        state = make_state({"CVE-2024-0001": ITEM_A})
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha2"
        self.mock_fetch.return_value = make_snapshot([ITEM_A, ITEM_B])

        function_app.run_poll_cycle(NOW)

        events = self.mock_write_to_bronze.call_args[0][0]
        added_events = [e for e in events if e["event_type"] == "kev_added"]
        self.assertEqual({e["cve_id"] for e in added_events}, {"CVE-2024-0002"})

        saved_state = self.mock_save_state.call_args[0][0]
        self.assertIn("CVE-2024-0002", saved_state["items"])
        self.assertEqual(saved_state["last_processed_commit_sha"], "sha2")

    # 4. 기존 cveID의 아무 필드(예: notes)가 바뀌면 kev_updated 이벤트가 발행된다.
    def test_case_4_existing_field_changed(self):
        state = make_state({"CVE-2024-0001": ITEM_A})
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha2"

        changed_item = copy.deepcopy(ITEM_A)
        changed_item["notes"] = "updated note"
        self.mock_fetch.return_value = make_snapshot([changed_item])

        function_app.run_poll_cycle(NOW)

        events = self.mock_write_to_bronze.call_args[0][0]
        updated_events = [e for e in events if e["event_type"] == "kev_updated"]
        self.assertEqual({e["cve_id"] for e in updated_events}, {"CVE-2024-0001"})

        saved_state = self.mock_save_state.call_args[0][0]
        self.assertEqual(
            saved_state["items"]["CVE-2024-0001"]["hash"],
            function_app.compute_hash(changed_item),
        )

    # 5. cveID가 사라지면 즉시 kev_removed_confirmed가 발행되지 않고 pending_removed에 들어간다.
    def test_case_5_removed_goes_to_pending(self):
        state = make_state({"CVE-2024-0001": ITEM_A, "CVE-2024-0002": ITEM_B})
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha2"
        self.mock_fetch.return_value = make_snapshot([ITEM_A])  # ITEM_B 사라짐

        function_app.run_poll_cycle(NOW)

        events = self.mock_write_to_bronze.call_args[0][0] if self.mock_write_to_bronze.called else []
        self.assertFalse(any(e["event_type"] == "kev_removed_confirmed" for e in events))

        saved_state = self.mock_save_state.call_args[0][0]
        self.assertIn("CVE-2024-0002", saved_state["pending_removed"])
        pending_entry = saved_state["pending_removed"]["CVE-2024-0002"]
        self.assertEqual(pending_entry["removed_detected_at"], NOW.isoformat())
        self.assertEqual(pending_entry["last_known_item"], ITEM_B)

    # 6. pending_removed에 있던 cveID가 24시간 이내 재등재되면 kev_removed_confirmed 미발행,
    #    pending_removed에서 제거된다 (CVE-2026-1281류 픽스처).
    def test_case_6_pending_reappears_within_debounce(self):
        reappeared_item = copy.deepcopy(ITEM_B)
        reappeared_item["notes"] = "reappeared with a tweak"

        state = make_state(
            {"CVE-2024-0001": ITEM_A, "CVE-2024-0002": ITEM_B},
            pending_removed={
                "CVE-2024-0002": {
                    "removed_detected_at": (NOW - timedelta(hours=1, minutes=30)).isoformat(),
                    "last_known_item": ITEM_B,
                }
            },
        )
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha2"
        self.mock_fetch.return_value = make_snapshot([ITEM_A, reappeared_item])

        function_app.run_poll_cycle(NOW)

        events = self.mock_write_to_bronze.call_args[0][0]
        self.assertFalse(any(e["event_type"] == "kev_removed_confirmed" for e in events))
        self.assertTrue(any(e["event_type"] == "kev_updated" and e["cve_id"] == "CVE-2024-0002" for e in events))

        saved_state = self.mock_save_state.call_args[0][0]
        self.assertNotIn("CVE-2024-0002", saved_state["pending_removed"])

    # 7. pending_removed가 24시간 넘게 재등재되지 않으면, 새 커밋 없는 실행에서도 kev_removed_confirmed가 발행된다.
    def test_case_7_pending_expires_without_new_commit(self):
        state = make_state(
            {"CVE-2024-0001": ITEM_A, "CVE-2024-0002": ITEM_B},
            pending_removed={
                "CVE-2024-0002": {
                    "removed_detected_at": (NOW - timedelta(hours=25)).isoformat(),
                    "last_known_item": ITEM_B,
                }
            },
        )
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha1"  # 이전과 동일 -> has_new_commit = False

        function_app.run_poll_cycle(NOW)

        self.mock_fetch.assert_not_called()
        events = self.mock_write_to_bronze.call_args[0][0]
        confirmed = [e for e in events if e["event_type"] == "kev_removed_confirmed"]
        self.assertEqual({e["cve_id"] for e in confirmed}, {"CVE-2024-0002"})
        self.assertEqual(confirmed[0]["data"], ITEM_B)

        saved_state = self.mock_save_state.call_args[0][0]
        self.assertNotIn("CVE-2024-0002", saved_state["pending_removed"])
        self.assertNotIn("CVE-2024-0002", saved_state["items"])

    # 8. GitHub 미러 API가 실패하면 이번 실행은 조용히 스킵하고 state를 갱신하지 않는다.
    def test_case_8_github_failure_skips_run(self):
        self.mock_load_state.return_value = make_state({"CVE-2024-0001": ITEM_A})
        self.mock_get_sha.side_effect = requests.exceptions.RequestException("boom")

        function_app.run_poll_cycle(NOW)

        self.mock_fetch.assert_not_called()
        self.mock_write_to_bronze.assert_not_called()
        self.mock_save_state.assert_not_called()

    # 9. Bronze 적재가 실패하면 last_processed_commit_sha가 갱신되지 않는다.
    def test_case_9_bronze_failure_keeps_checkpoint(self):
        self.mock_load_state.return_value = make_state({"CVE-2024-0001": ITEM_A}, last_processed_commit_sha="sha1")
        self.mock_get_sha.return_value = "sha2"
        self.mock_fetch.return_value = make_snapshot([ITEM_A, ITEM_B])
        self.mock_write_to_bronze.side_effect = RuntimeError("bronze write failed")

        function_app.run_poll_cycle(NOW)

        self.mock_save_state.assert_not_called()

    # 보강 1. fetch_kev_catalog 실패 시에도 조용히 스킵되고 state가 갱신되지 않는다.
    def test_extra_1_fetch_catalog_failure_skips_run(self):
        self.mock_load_state.return_value = make_state({"CVE-2024-0001": ITEM_A}, last_processed_commit_sha="sha1")
        self.mock_get_sha.return_value = "sha2"
        self.mock_fetch.side_effect = requests.exceptions.RequestException("boom")

        function_app.run_poll_cycle(NOW)

        self.mock_write_to_bronze.assert_not_called()
        self.mock_save_state.assert_not_called()

    # 보강 2. write_to_bronze에 넘어가는 commit_sha/run_at 값이 이번 실행의 값과 일치한다.
    def test_extra_2_write_to_bronze_receives_commit_sha_and_run_at(self):
        state = make_state({"CVE-2024-0001": ITEM_A})
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha2"
        self.mock_fetch.return_value = make_snapshot([ITEM_A, ITEM_B])

        function_app.run_poll_cycle(NOW)

        _, kwargs = self.mock_write_to_bronze.call_args
        self.assertEqual(kwargs["commit_sha"], "sha2")
        self.assertEqual(kwargs["run_at"], NOW.isoformat())

    # 보강 3. 새 커밋은 있지만 실제 항목 변화가 없으면 Bronze는 건너뛰되 checkpoint는 갱신된다.
    def test_extra_3_new_commit_without_item_changes_skips_bronze_but_updates_checkpoint(self):
        state = make_state({"CVE-2024-0001": ITEM_A, "CVE-2024-0002": ITEM_B}, last_processed_commit_sha="sha1")
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha2"
        self.mock_fetch.return_value = make_snapshot([ITEM_A, ITEM_B], catalog_version="2026.08.17")

        function_app.run_poll_cycle(NOW)

        self.mock_write_to_bronze.assert_not_called()
        self.mock_save_state.assert_called_once()
        saved_state = self.mock_save_state.call_args[0][0]
        self.assertEqual(saved_state["last_processed_commit_sha"], "sha2")

    # 보강 4. removed_candidate는 pending 중엔 state.items에서 빠지지 않고 남아있는다.
    def test_extra_4_removed_candidate_stays_in_items_while_pending(self):
        state = make_state({"CVE-2024-0001": ITEM_A, "CVE-2024-0002": ITEM_B})
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha2"
        self.mock_fetch.return_value = make_snapshot([ITEM_A])  # ITEM_B 사라짐

        function_app.run_poll_cycle(NOW)

        saved_state = self.mock_save_state.call_args[0][0]
        self.assertIn("CVE-2024-0002", saved_state["items"])
        self.assertIn("CVE-2024-0002", saved_state["pending_removed"])

    # 보강 5. 아무 필드도 안 바뀐 채 그대로 재등재되면 REMOVED도 UPDATED도 발생하지 않는다.
    def test_extra_5_reappear_with_no_changes_emits_nothing(self):
        state = make_state(
            {"CVE-2024-0001": ITEM_A, "CVE-2024-0002": ITEM_B},
            pending_removed={
                "CVE-2024-0002": {
                    "removed_detected_at": (NOW - timedelta(hours=1, minutes=30)).isoformat(),
                    "last_known_item": ITEM_B,
                }
            },
        )
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha2"
        self.mock_fetch.return_value = make_snapshot([ITEM_A, ITEM_B])  # ITEM_B 무변경 그대로 재등재

        function_app.run_poll_cycle(NOW)

        events = self.mock_write_to_bronze.call_args[0][0] if self.mock_write_to_bronze.called else []
        self.assertFalse(any(e["cve_id"] == "CVE-2024-0002" for e in events))

        saved_state = self.mock_save_state.call_args[0][0]
        self.assertNotIn("CVE-2024-0002", saved_state["pending_removed"])

    # 보강 6. 새 커밋을 정상 처리하면 heartbeat가 had_new_commit=True, status="ok"로 기록된다.
    def test_extra_6_heartbeat_on_success_with_new_commit(self):
        state = make_state({"CVE-2024-0001": ITEM_A})
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha2"
        self.mock_fetch.return_value = make_snapshot([ITEM_A, ITEM_B])

        function_app.run_poll_cycle(NOW)

        self.mock_write_heartbeat.assert_called_once_with(NOW, had_new_commit=True, status="ok")

    # 보강 7. 새 커밋이 없는 실행에서는 heartbeat가 had_new_commit=False, status="ok"로 기록된다.
    def test_extra_7_heartbeat_on_no_new_commit(self):
        state = make_state({"CVE-2024-0001": ITEM_A})
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha1"  # 커밋 변화 없음

        function_app.run_poll_cycle(NOW)

        self.mock_write_heartbeat.assert_called_once_with(NOW, had_new_commit=False, status="ok")

    # 보강 8. GitHub API 실패 시 write_to_bronze는 호출되지 않고, heartbeat는 status="error"로 기록된다.
    def test_extra_8_heartbeat_on_github_failure(self):
        self.mock_load_state.return_value = make_state({"CVE-2024-0001": ITEM_A})
        self.mock_get_sha.side_effect = requests.exceptions.RequestException("boom")

        function_app.run_poll_cycle(NOW)

        self.mock_write_to_bronze.assert_not_called()
        self.mock_write_heartbeat.assert_called_once_with(NOW, had_new_commit=False, status="error")

    # 보강 9. write_to_bronze 실패 시 heartbeat가 had_new_commit=True, status="error"로 기록된다.
    def test_extra_9_heartbeat_on_bronze_failure(self):
        self.mock_load_state.return_value = make_state({"CVE-2024-0001": ITEM_A}, last_processed_commit_sha="sha1")
        self.mock_get_sha.return_value = "sha2"
        self.mock_fetch.return_value = make_snapshot([ITEM_A, ITEM_B])
        self.mock_write_to_bronze.side_effect = RuntimeError("bronze write failed")

        function_app.run_poll_cycle(NOW)

        self.mock_write_heartbeat.assert_called_once_with(NOW, had_new_commit=True, status="error")

    # 보강 10. 새 커밋은 없지만 만료된 REMOVED의 Bronze 적재가 실패하면
    #          heartbeat가 had_new_commit=False, status="error"로 기록된다 (명시되지 않았던 경로).
    def test_extra_10_heartbeat_on_expired_removed_bronze_failure_without_new_commit(self):
        state = make_state(
            {"CVE-2024-0001": ITEM_A, "CVE-2024-0002": ITEM_B},
            pending_removed={
                "CVE-2024-0002": {
                    "removed_detected_at": (NOW - timedelta(hours=25)).isoformat(),
                    "last_known_item": ITEM_B,
                }
            },
        )
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha1"  # 커밋 변화 없음
        self.mock_write_to_bronze.side_effect = RuntimeError("bronze write failed")

        function_app.run_poll_cycle(NOW)

        self.mock_save_state.assert_not_called()
        self.mock_write_heartbeat.assert_called_once_with(NOW, had_new_commit=False, status="error")

    # 보강 11. load_state/save_state 등 명시되지 않은 곳에서 예기치 못한 예외가 나도
    #          heartbeat는 남고, 예외 자체는 Azure Function 실패 처리를 위해 다시 던져진다.
    def test_extra_11_heartbeat_on_unexpected_exception_then_reraises(self):
        state = make_state({"CVE-2024-0001": ITEM_A})
        self.mock_load_state.return_value = state
        self.mock_get_sha.return_value = "sha2"
        self.mock_fetch.return_value = make_snapshot([ITEM_A, ITEM_B])
        self.mock_save_state.side_effect = RuntimeError("blob storage unavailable")

        with self.assertRaises(RuntimeError):
            function_app.run_poll_cycle(NOW)

        self.mock_write_heartbeat.assert_called_once_with(NOW, had_new_commit=True, status="error")


if __name__ == "__main__":
    unittest.main()
