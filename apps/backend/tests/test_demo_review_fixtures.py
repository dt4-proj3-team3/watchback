from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from watchback_backend.api.schemas import ReviewCaseDetail, ReviewCaseListResponse


DEMO_ROOT = Path(__file__).resolve().parents[3] / "data" / "demo"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _review_case_data() -> dict[str, Any]:
    return _read_json(DEMO_ROOT / "review-cases.json")


def test_demo_list_and_empty_match_api_contract() -> None:
    payload = _review_case_data()
    review_cases = ReviewCaseListResponse.model_validate(payload["list"])
    empty = ReviewCaseListResponse.model_validate(payload["empty"])

    assert review_cases.total == len(review_cases.items) == 10
    assert empty.total == 0
    assert empty.items == []

    repositories = {item.repository.display_name for item in review_cases.items}
    priorities = {item.priority.value for item in review_cases.items}
    assert repositories == {"novalink/customer-fe", "novalink/ai-platform-api"}
    assert priorities == {"medium", "high", "critical"}


def test_every_demo_case_has_a_matching_detail() -> None:
    payload = _review_case_data()
    review_cases = ReviewCaseListResponse.model_validate(payload["list"])

    assert set(payload["details"]) == {str(item.id) for item in review_cases.items}

    summaries = {str(item.id): item for item in review_cases.items}
    for case_id, detail_payload in payload["details"].items():
        detail = ReviewCaseDetail.model_validate(detail_payload)
        summary = summaries[case_id]

        assert detail.status == summary.status
        assert detail.priority == summary.priority
        assert detail.repository == summary.repository
        assert detail.advisory == summary.advisory
        assert detail.alert.id == summary.alert.id
        assert detail.alert.github_alert_number == summary.alert.github_alert_number
        assert detail.latest_candidate == summary.latest_candidate
        assert detail.candidates[-1].id == detail.latest_candidate.id
        latest_kev_evidence = max(
            (
                evidence
                for candidate in detail.candidates
                for evidence in candidate.evidence
                if evidence.signal == "kev"
            ),
            key=lambda evidence: (evidence.observed_at, evidence.id),
            default=None,
        )
        expected_kev = (
            latest_kev_evidence is not None
            and latest_kev_evidence.current_value == "true"
        )
        assert detail.is_kev == summary.is_kev == expected_kev


def test_duplicate_manifest_alerts_share_candidate_but_not_case() -> None:
    review_cases = ReviewCaseListResponse.model_validate(_review_case_data()["list"])
    by_cve: dict[str, list[Any]] = defaultdict(list)
    for item in review_cases.items:
        assert item.advisory.cve_id is not None
        by_cve[item.advisory.cve_id].append(item)

    for cve_id in ("CVE-2026-39363",):
        duplicated = by_cve[cve_id]
        assert len(duplicated) == 2
        assert len({item.id for item in duplicated}) == 2
        assert len({item.alert.id for item in duplicated}) == 2
        assert len({item.latest_candidate.id for item in duplicated}) == 1


def test_demo_candidates_only_use_verified_s1_signals() -> None:
    source = _read_json(DEMO_ROOT / "vulnerabilities.json")
    assert source["expected_signal_evaluation"] == {
        "policy_version": "ver.1",
        "evaluation_start": "2025-03-21",
        "evaluation_end": "2026-08-20",
        "kev_catalog_version": "2026.08.20",
        "ghsa_patch_rules_evaluated": False,
    }
    vulnerabilities = source["vulnerabilities"]
    payload = _review_case_data()
    source_by_cve = {item["cve_id"]: item for item in vulnerabilities}

    expected_case_cves = {
        "CVE-2025-27520",
        "CVE-2025-29927",
        "CVE-2025-31125",
        "CVE-2025-55182",
        "CVE-2026-1207",
        "CVE-2026-35029",
        "CVE-2026-39363",
        "CVE-2026-42208",
        "CVE-2025-31486",
    }
    assert {item["advisory"]["cve_id"] for item in payload["list"]["items"]} == expected_case_cves

    checked_candidates: set[str] = set()
    for detail in payload["details"].values():
        for candidate in detail["candidates"]:
            if candidate["id"] in checked_candidates:
                continue
            checked_candidates.add(candidate["id"])

            cve_id = candidate["cve_id"]
            observed_on = candidate["selected_at"][:10]
            expected_signals = [
                signal
                for signal in source_by_cve[cve_id]["expected_signals"]
                if signal["included_in_s1"] and signal["observed_on"] == observed_on
            ]
            assert expected_signals
            assert len(candidate["evidence"]) == len(expected_signals)
            assert {item["observed_at"][:10] for item in candidate["evidence"]} == {
                observed_on
            }

            expected_evidence = set()
            for signal in expected_signals:
                if signal["rule_id"] == "R-KEV-NEW":
                    expected_evidence.add(("kev", "false", "true", "cisa_kev"))
                elif signal["rule_id"] == "R-EPSS-RISE-D30":
                    expected_evidence.add(
                        (
                            "epss_score_d30",
                            signal["previous_epss"],
                            signal["current_epss"],
                            "first_epss",
                        )
                    )
                else:
                    expected_evidence.add(
                        (
                            "epss_percentile_d30",
                            signal["previous_percentile"],
                            signal["current_percentile"],
                            "first_epss",
                        )
                    )
            assert {
                (
                    item["signal"],
                    item["previous_value"],
                    item["current_value"],
                    item["source"],
                )
                for item in candidate["evidence"]
            } == expected_evidence

    assert len(checked_candidates) == 16


def test_vite_source_shift_is_kept_and_annotated_in_one_demo_case() -> None:
    payload = _review_case_data()
    summary = next(
        item
        for item in payload["list"]["items"]
        if item["advisory"]["cve_id"] == "CVE-2025-31486"
    )
    detail = payload["details"][summary["id"]]

    assert summary["alert"]["github_alert_number"] == 4
    assert [
        candidate["selected_at"][:10] for candidate in detail["candidates"]
    ] == ["2025-11-18", "2026-06-15"]
    assert [
        annotation["annotation_type"]
        for candidate in detail["candidates"]
        for delivery in candidate["deliveries"]
        for annotation in delivery["source_annotations"]
    ] == ["EPSS_SOURCE_SCORE_SHIFT", "EPSS_MODEL_TRANSITION"]
    assert all(
        candidate["selected_at"][:10] != "2026-06-16"
        for candidate in detail["candidates"]
    )


def test_review_cases_match_vulnerability_snapshot() -> None:
    vulnerabilities = _read_json(DEMO_ROOT / "vulnerabilities.json")["vulnerabilities"]
    payload = _review_case_data()
    source_by_alert = {
        (alert["repository"], alert["alert_number"]): (vulnerability, alert)
        for vulnerability in vulnerabilities
        for alert in vulnerability["alerts"]
    }

    for item in payload["list"]["items"]:
        key = (item["repository"]["full_name"], item["alert"]["github_alert_number"])
        vulnerability, alert = source_by_alert[key]

        assert item["advisory"]["cve_id"] == vulnerability["cve_id"]
        assert item["advisory"]["ghsa_id"] == vulnerability["ghsa_id"]
        assert item["advisory"]["summary"] == vulnerability["summary"]
        assert item["advisory"]["severity"] == vulnerability["severity"]
        assert item["advisory"]["cvss_score"] == vulnerability["cvss_score"]
        assert item["alert"]["package_name"] == vulnerability["package"]
        assert item["alert"]["ecosystem"] == vulnerability["ecosystem"]
        assert item["alert"]["state"] == alert["state"]
        assert item["alert"]["first_patched_version"] == alert["first_patched_version"]
        assert item["alert"]["html_url"] == alert["html_url"]

        detail = payload["details"][item["id"]]
        assert detail["alert"]["manifest_path"] == alert["manifest_path"]
        assert detail["alert"]["dependency_relationship"] == alert["relationship"]
        assert detail["alert"]["dependency_scope"] == alert["scope"]
        assert detail["alert"]["vulnerable_version_range"] == alert["vulnerable_version_range"]
        assert detail["alert"]["github_created_at"] == alert["alert_created_at"]
        assert detail["alert"]["github_updated_at"] == alert["alert_updated_at"]


def test_demo_repository_and_alert_ids_match_operational_id_rules() -> None:
    source = _read_json(DEMO_ROOT / "vulnerabilities.json")
    repository_github_ids = {
        item["full_name"]: item["id"] for item in source["repositories"]
    }

    for item in _review_case_data()["list"]["items"]:
        full_name = item["repository"]["full_name"]
        github_repository_id = repository_github_ids[full_name]
        alert_number = item["alert"]["github_alert_number"]

        assert item["repository"]["id"] == str(
            uuid5(
                NAMESPACE_URL,
                f"watchback:demo:repository:github:{github_repository_id}",
            )
        )
        assert item["alert"]["id"] == str(
            uuid5(
                NAMESPACE_URL,
                f"watchback:dependabot-alert:{github_repository_id}:{alert_number}",
            )
        )
