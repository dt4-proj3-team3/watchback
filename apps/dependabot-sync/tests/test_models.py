from __future__ import annotations

from decimal import Decimal

from pydantic import ValidationError
import pytest

from watchback_dependabot_sync.models import AlertPayload
from watchback_dependabot_sync.service import (
    collect_advisories,
    repository_digest,
    repository_summary,
)


def test_representative_source_values_and_nullable_fields(raw_alerts):
    alerts = [AlertPayload.model_validate(item) for item in raw_alerts]
    assert {item.state for item in alerts} == {"open", "fixed", "dismissed", "auto_dismissed"}
    assert {item.dependency.relationship for item in alerts} >= {"direct", "transitive", "unknown"}
    assert alerts[1].security_advisory.cve_id is None
    assert alerts[1].security_vulnerability.first_patched_version is None
    assert len(collect_advisories({"repo": alerts})) == 4
    summary = repository_summary(alerts, 2)
    assert summary["source_count"] == 5
    assert summary["missing_cve_count"] == 1
    assert summary["excluded_count"] == 0
    assert summary["excluded_reasons"] == {}
    assert len(summary["sha256"]) == 64
    assert repository_digest(list(reversed(alerts))) == summary["sha256"]


def test_state_timestamp_contract_is_strict(raw_alerts):
    raw_alerts[0]["fixed_at"] = "2026-08-10T00:00:00Z"
    with pytest.raises(ValidationError):
        AlertPayload.model_validate(raw_alerts[0])


def test_equal_timestamp_conflicting_advisory_is_rejected(raw_alerts):
    alerts = [AlertPayload.model_validate(item) for item in raw_alerts]
    conflicting = alerts[4].model_copy(deep=True)
    conflicting.security_advisory.summary = "서로 다른 내용"
    with pytest.raises(Exception, match="동일 시각"):
        collect_advisories({"repo": [alerts[0], conflicting]})


def test_prefers_cvss_v4_and_treats_empty_legacy_score_as_missing(raw_alerts):
    source = raw_alerts[0]
    source["security_advisory"]["cvss"] = {
        "vector_string": None,
        "score": 0.0,
    }
    source["security_advisory"]["cvss_severities"] = {
        "cvss_v3": {"vector_string": None, "score": 0.0},
        "cvss_v4": {
            "vector_string": "CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:H",
            "score": 8.2,
        },
    }

    advisory = AlertPayload.model_validate(source).security_advisory
    assert advisory.effective_cvss_score == Decimal("8.2")

    advisory.cvss_severities = None
    assert advisory.effective_cvss_score is None
