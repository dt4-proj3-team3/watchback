from __future__ import annotations

from copy import deepcopy

import pytest

from watchback_gold_sync.errors import ContractError
from watchback_gold_sync.models import build_payloads
from watchback_gold_sync.persistence import candidate_payload_hash


def rows() -> tuple[list[dict], list[dict], list[dict]]:
    batches = [
        {
            "batch_id": "batch-1",
            "ds_run_id": None,
            "status": "completed",
            "as_of": "2026-08-21T00:00:00Z",
            "generated_at": "2026-08-21T01:00:00Z",
            "policy_version": "ver.1",
            "schema_version": "1.0",
            "candidate_count": 2,
        }
    ]
    candidates = [
        {
            "batch_id": "batch-1",
            "candidate_id": "candidate-cve",
            "subject_type": "CVE",
            "subject_id": "CVE-2026-0001",
            "ghsa_id": "GHSA-aaaa-bbbb-0001",
            "cve_id": "CVE-2026-0001",
            "priority": "P0",
            "change_type": "KEV_NEW",
            "reason_summary": "KEV 등재",
            "selected_at": "2026-08-21T00:30:00Z",
        },
        {
            "batch_id": "batch-1",
            "candidate_id": "candidate-ghsa",
            "subject_type": "GHSA",
            "subject_id": "GHSA-aaaa-bbbb-0002",
            "ghsa_id": "GHSA-aaaa-bbbb-0002",
            "cve_id": None,
            "priority": "P3",
            "change_type": "PATCH_NEW",
            "reason_summary": "패치 등장",
            "selected_at": "2026-08-21T00:40:00Z",
        },
    ]
    evidence = [
        {
            "batch_id": "batch-1",
            "evidence_id": "evidence-1",
            "candidate_id": "candidate-cve",
            "signal": "kev",
            "value_type": "boolean",
            "previous_value": "false",
            "current_value": "true",
            "observed_at": "2026-08-21T00:20:00Z",
            "source": "cisa_kev",
            "evidence_summary": "CISA KEV에 새로 등재되었습니다.",
        },
        {
            "batch_id": "batch-1",
            "evidence_id": "evidence-2",
            "candidate_id": "candidate-ghsa",
            "signal": "patch",
            "value_type": "version",
            "previous_value": None,
            "current_value": None,
            "observed_at": "2026-08-21T00:25:00Z",
            "source": "github_advisory",
            "evidence_summary": "패치 정보가 변경되었습니다.",
        },
    ]
    return batches, candidates, evidence


def test_builds_cve_and_ghsa_payload_with_nullable_values() -> None:
    payloads, failures = build_payloads(*rows())
    assert failures == []
    assert len(payloads) == 1
    assert payloads[0].batch.ds_run_id is None
    assert payloads[0].candidates[1].cve_id is None
    assert payloads[0].evidence[1].current_value is None


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda b, c, e: b[0].update(candidate_count=1), "candidate_count"),
        (lambda b, c, e: c.append(deepcopy(c[0])), "중복 candidate_id"),
        (lambda b, c, e: e.append(deepcopy(e[0])), "중복 evidence_id"),
        (lambda b, c, e: e[0].update(candidate_id="missing"), "Candidate 없는"),
        (lambda b, c, e: c[0].update(priority="critical"), "priority"),
        (lambda b, c, e: c[1].update(subject_id="CVE-wrong"), "GHSA subject"),
    ],
)
def test_rejects_contract_violations(mutate, message: str) -> None:
    batches, candidates, evidence = rows()
    mutate(batches, candidates, evidence)
    payloads, failures = build_payloads(batches, candidates, evidence)
    assert payloads == []
    assert message in failures[0]["message"]


def test_rejects_duplicate_batch_grain() -> None:
    batches, candidates, evidence = rows()
    batches.append(deepcopy(batches[0]))
    with pytest.raises(ContractError, match="중복 batch_id"):
        build_payloads(batches, candidates, evidence)


def test_candidate_payload_hash_is_order_independent() -> None:
    payload = build_payloads(*rows())[0][0]
    candidate = payload.candidates[0]
    evidence = [item for item in payload.evidence if item.candidate_id == candidate.candidate_id]
    assert candidate_payload_hash(candidate, evidence) == candidate_payload_hash(
        candidate, list(reversed(evidence))
    )
