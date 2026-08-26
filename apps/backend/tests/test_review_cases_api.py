from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from watchback_backend.db.models import (
    AlertCandidateMatch,
    Base,
    CandidateEvidence,
    DependabotAlert,
    GoldBatch,
    GoldBatchCandidate,
    Organization,
    Repository,
    ReviewActivity,
    ReviewCase,
    RiskCandidate,
    SecurityAdvisory,
    User,
)
from watchback_backend.db.session import get_session
from watchback_backend.main import app


NOW = datetime(2026, 8, 20, 12, tzinfo=UTC)


@pytest.fixture()
def api_fixture(postgres_engine: Engine) -> Iterator[dict[str, UUID]]:
    ids = {
        name: uuid4()
        for name in (
            "org",
            "other_org",
            "user",
            "other_user",
            "repo",
            "other_repo",
            "advisory",
            "nullable_advisory",
            "alert",
            "alert_high",
            "other_alert",
            "candidate_old",
            "candidate_latest",
            "candidate_high",
            "unlinked_candidate",
            "case",
            "case_high",
            "other_case",
            "batch_old",
            "batch_new",
        )
    }
    with Session(postgres_engine) as session:
        session.add_all(
            [
                Organization(
                    id=ids["org"],
                    github_organization_id=1,
                    github_login="novalink",
                    display_name="노바링크",
                ),
                Organization(
                    id=ids["other_org"],
                    github_organization_id=2,
                    github_login="other",
                    display_name="다른 조직",
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                User(
                    id=ids["user"],
                    organization_id=ids["org"],
                    email="reviewer@novalink.example",
                    display_name="김서연",
                ),
                User(
                    id=ids["other_user"],
                    organization_id=ids["other_org"],
                    email="other@example.com",
                    display_name="이민준",
                ),
                Repository(
                    id=ids["repo"],
                    organization_id=ids["org"],
                    github_repository_id=11,
                    full_name="example/frontend",
                    display_name="novalink/customer-fe",
                    default_branch="main",
                    importance="critical",
                    last_synced_at=NOW,
                ),
                Repository(
                    id=ids["other_repo"],
                    organization_id=ids["other_org"],
                    github_repository_id=22,
                    full_name="other/backend",
                    display_name="other/backend",
                    default_branch="main",
                    importance="high",
                    last_synced_at=NOW,
                ),
                SecurityAdvisory(
                    id=ids["advisory"],
                    ghsa_id="GHSA-1111-2222-3333",
                    cve_id="CVE-2026-0001",
                    summary="대표 취약점",
                    severity="critical",
                    cvss_score=9.8,
                    github_updated_at=NOW,
                ),
                SecurityAdvisory(
                    id=ids["nullable_advisory"],
                    ghsa_id="GHSA-4444-5555-6666",
                    cve_id=None,
                    summary="CVE 없는 권고",
                    severity="high",
                    cvss_score=None,
                    github_updated_at=NOW,
                ),
            ]
        )
        session.flush()

        def alert(
            identifier: str, repo: str, advisory: str, number: int
        ) -> DependabotAlert:
            org = ids["org"] if repo == "repo" else ids["other_org"]
            return DependabotAlert(
                id=ids[identifier],
                organization_id=org,
                repository_id=ids[repo],
                advisory_id=ids[advisory],
                github_alert_number=number,
                state="open",
                package_name="example-package",
                ecosystem="npm",
                manifest_path="package-lock.json",
                dependency_scope="runtime",
                dependency_relationship="direct",
                vulnerable_version_range="<2",
                first_patched_version="2.0.0",
                html_url=f"https://github.com/example/repo/security/dependabot/{number}",
                github_created_at=NOW - timedelta(days=10),
                github_updated_at=NOW,
                last_synced_at=NOW,
            )

        session.add_all(
            [
                alert("alert", "repo", "advisory", 1),
                alert("alert_high", "repo", "nullable_advisory", 2),
                alert("other_alert", "other_repo", "advisory", 1),
            ]
        )
        candidates = [
            RiskCandidate(
                id=ids["candidate_old"],
                source_candidate_id="candidate-old",
                subject_type="CVE",
                subject_id="CVE-2026-0001",
                ghsa_id="GHSA-aaaa-bbbb-0001",
                cve_id="CVE-2026-0001",
                priority="P1",
                change_type="epss_rise",
                reason_summary="EPSS 상승",
                selected_at=NOW - timedelta(days=2),
            ),
            RiskCandidate(
                id=ids["candidate_latest"],
                source_candidate_id="candidate-latest",
                subject_type="CVE",
                subject_id="CVE-2026-0001",
                ghsa_id="GHSA-aaaa-bbbb-0001",
                cve_id="CVE-2026-0001",
                priority="P0",
                change_type="kev_added",
                reason_summary="KEV 등재",
                selected_at=NOW - timedelta(days=1),
            ),
            RiskCandidate(
                id=ids["candidate_high"],
                source_candidate_id="candidate-high",
                subject_type="GHSA",
                subject_id="GHSA-4444-5555-6666",
                ghsa_id="GHSA-4444-5555-6666",
                cve_id=None,
                priority="P1",
                change_type="epss_rise",
                reason_summary="EPSS 상승",
                selected_at=NOW,
            ),
            RiskCandidate(
                id=ids["unlinked_candidate"],
                source_candidate_id="candidate-unlinked",
                subject_type="CVE",
                subject_id="CVE-2026-9999",
                ghsa_id="GHSA-aaaa-bbbb-9999",
                cve_id="CVE-2026-9999",
                priority="P3",
                change_type="other",
                reason_summary="미연결",
                selected_at=NOW,
            ),
        ]
        session.add_all(candidates)
        session.flush()
        session.add_all(
            [
                AlertCandidateMatch(
                    organization_id=ids["org"],
                    alert_id=ids["alert"],
                    candidate_id=ids["candidate_old"],
                    matched_at=NOW,
                ),
                AlertCandidateMatch(
                    organization_id=ids["org"],
                    alert_id=ids["alert"],
                    candidate_id=ids["candidate_latest"],
                    matched_at=NOW,
                ),
                AlertCandidateMatch(
                    organization_id=ids["org"],
                    alert_id=ids["alert_high"],
                    candidate_id=ids["candidate_high"],
                    matched_at=NOW,
                ),
                AlertCandidateMatch(
                    organization_id=ids["other_org"],
                    alert_id=ids["other_alert"],
                    candidate_id=ids["candidate_old"],
                    matched_at=NOW,
                ),
                ReviewCase(
                    id=ids["case"],
                    organization_id=ids["org"],
                    alert_id=ids["alert"],
                    status="open",
                    priority="critical",
                    review_reason="다시 검토",
                    opened_at=NOW - timedelta(days=3),
                    reopened_count=0,
                    updated_at=NOW - timedelta(hours=1),
                ),
                ReviewCase(
                    id=ids["case_high"],
                    organization_id=ids["org"],
                    alert_id=ids["alert_high"],
                    status="resolved",
                    priority="high",
                    review_reason="해결된 검토",
                    opened_at=NOW - timedelta(days=2),
                    resolved_at=NOW - timedelta(hours=2),
                    reopened_count=0,
                    updated_at=NOW - timedelta(hours=2),
                ),
                ReviewCase(
                    id=ids["other_case"],
                    organization_id=ids["other_org"],
                    alert_id=ids["other_alert"],
                    status="open",
                    priority="medium",
                    review_reason="타 조직",
                    opened_at=NOW,
                    reopened_count=0,
                ),
                GoldBatch(
                    id=ids["batch_old"],
                    source_batch_id="batch-old",
                    as_of=NOW - timedelta(days=3),
                    source_generated_at=NOW - timedelta(days=3),
                    policy_version="v1",
                    schema_version="1",
                    candidate_count=1,
                    synced_at=NOW - timedelta(days=3),
                ),
                GoldBatch(
                    id=ids["batch_new"],
                    source_batch_id="batch-new",
                    as_of=NOW - timedelta(days=1),
                    source_generated_at=NOW - timedelta(days=1),
                    policy_version="v1",
                    schema_version="1",
                    candidate_count=1,
                    synced_at=NOW - timedelta(days=1),
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                GoldBatchCandidate(
                    batch_id=ids["batch_new"],
                    candidate_id=ids["candidate_latest"],
                    payload_hash="b" * 64,
                    received_at=NOW - timedelta(hours=20),
                ),
                GoldBatchCandidate(
                    batch_id=ids["batch_old"],
                    candidate_id=ids["candidate_latest"],
                    payload_hash="a" * 64,
                    received_at=NOW - timedelta(days=3),
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                CandidateEvidence(
                    source_evidence_id="evidence-new",
                    batch_id=ids["batch_new"],
                    candidate_id=ids["candidate_latest"],
                    signal="kev",
                    value_type="boolean",
                    previous_value="false",
                    current_value="true",
                    observed_at=NOW - timedelta(hours=10),
                    source="cisa",
                    evidence_summary="KEV 등재",
                ),
                CandidateEvidence(
                    source_evidence_id="evidence-old",
                    batch_id=ids["batch_old"],
                    candidate_id=ids["candidate_latest"],
                    signal="epss",
                    value_type="decimal",
                    previous_value="0.1",
                    current_value="0.5",
                    observed_at=NOW - timedelta(days=2),
                    source="first",
                    evidence_summary="EPSS 상승",
                ),
            ]
        )
        session.commit()

    def session_override() -> Iterator[Session]:
        with Session(postgres_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    yield ids
    app.dependency_overrides.clear()
    with postgres_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(delete(table))


@pytest.fixture()
def client(api_fixture: dict[str, UUID]) -> TestClient:
    del api_fixture
    return TestClient(app)


def headers(ids: dict[str, UUID], *, other_user: bool = False) -> dict[str, str]:
    return {
        "X-Organization-ID": str(ids["org"]),
        "X-User-ID": str(ids["other_user"] if other_user else ids["user"]),
    }


def test_list_filters_latest_candidate_and_paginates(
    client: TestClient, api_fixture: dict[str, UUID]
) -> None:
    base_headers = headers(api_fixture)
    response = client.get("/api/v1/review-cases", headers=base_headers)
    assert response.status_code == 200
    assert response.json()["items"][0]["latest_candidate"]["change_type"] == "kev_added"
    assert response.json()["total"] == 1

    all_cases = client.get(
        "/api/v1/review-cases?status=all&page_size=1", headers=base_headers
    ).json()
    assert all_cases["total"] == 2
    assert len(all_cases["items"]) == 1
    assert all_cases["items"][0]["priority"] == "critical"
    second_page = client.get(
        "/api/v1/review-cases?status=all&page=2&page_size=1", headers=base_headers
    ).json()
    repeated_first_page = client.get(
        "/api/v1/review-cases?status=all&page_size=1", headers=base_headers
    ).json()
    assert second_page["items"][0]["id"] != all_cases["items"][0]["id"]
    assert repeated_first_page["items"][0]["id"] == all_cases["items"][0]["id"]
    assert (
        client.get(
            "/api/v1/review-cases?status=all&change_type=epss_rise",
            headers=base_headers,
        ).json()["total"]
        == 1
    )
    assert client.get(
        "/api/v1/review-cases?priority=low", headers=base_headers
    ).json() == {"items": [], "page": 1, "page_size": 20, "total": 0}


@pytest.mark.parametrize("sort", ["priority", "opened_at", "updated_at"])
@pytest.mark.parametrize("order", ["asc", "desc"])
def test_list_all_sort_modes(
    client: TestClient, api_fixture: dict[str, UUID], sort: str, order: str
) -> None:
    response = client.get(
        f"/api/v1/review-cases?status=all&sort={sort}&order={order}",
        headers=headers(api_fixture),
    )
    assert response.status_code == 200
    assert len({item["id"] for item in response.json()["items"]}) == 2


def test_detail_returns_ordered_history_and_nullable_advisory(
    client: TestClient, api_fixture: dict[str, UUID]
) -> None:
    detail = client.get(
        f"/api/v1/review-cases/{api_fixture['case']}", headers=headers(api_fixture)
    ).json()
    assert [item["source_candidate_id"] for item in detail["candidates"]] == [
        "candidate-old",
        "candidate-latest",
    ]
    latest = detail["candidates"][1]
    assert [item["source_batch_id"] for item in latest["deliveries"]] == [
        "batch-old",
        "batch-new",
    ]
    assert [item["source_evidence_id"] for item in latest["evidence"]] == [
        "evidence-old",
        "evidence-new",
    ]
    assert detail["latest_candidate"]["id"] == str(api_fixture["candidate_latest"])

    nullable = client.get(
        f"/api/v1/review-cases/{api_fixture['case_high']}", headers=headers(api_fixture)
    ).json()
    assert nullable["advisory"]["cve_id"] is None
    assert nullable["latest_candidate"]["subject_type"] == "GHSA"
    assert nullable["latest_candidate"]["cve_id"] is None


def test_activity_creation_transition_link_and_detail_mapping(
    client: TestClient, api_fixture: dict[str, UUID]
) -> None:
    payload = {
        "activity_type": "risk_accepted",
        "candidate_id": str(api_fixture["candidate_latest"]),
        "note": "위험을 수용합니다.",
        "external_link": {
            "link_type": "issue",
            "url": "https://github.com/example/frontend/issues/31",
        },
    }
    response = client.post(
        f"/api/v1/review-cases/{api_fixture['case']}/activities",
        headers=headers(api_fixture),
        json=payload,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["case_status"] == "resolved"
    assert body["activity"]["actor"]["display_name"] == "김서연"
    assert body["activity"]["external_links"][0]["external_state"] is None

    detail = client.get(
        f"/api/v1/review-cases/{api_fixture['case']}", headers=headers(api_fixture)
    ).json()
    assert detail["status"] == "resolved"
    assert detail["activities"][0]["external_links"][0]["github_number"] == 31


def test_resolved_case_accepts_case_wide_activity(
    client: TestClient, api_fixture: dict[str, UUID]
) -> None:
    response = client.post(
        f"/api/v1/review-cases/{api_fixture['case_high']}/activities",
        headers=headers(api_fixture),
        json={"activity_type": "note_added", "note": "추가 메모"},
    )
    assert response.status_code == 201
    assert response.json()["case_status"] == "resolved"
    assert response.json()["activity"]["candidate_id"] is None


@pytest.mark.parametrize(
    "activity_type",
    ["review_deferred", "remediation_requested", "note_added", "external_link_added"],
)
def test_non_acceptance_activities_do_not_resolve_case(
    client: TestClient,
    api_fixture: dict[str, UUID],
    activity_type: str,
) -> None:
    payload: dict[str, object] = {"activity_type": activity_type}
    if activity_type in {"review_deferred", "remediation_requested"}:
        payload.update(candidate_id=str(api_fixture["candidate_old"]), note="검토 기록")
    elif activity_type == "note_added":
        payload["note"] = "Case 메모"
    else:
        payload["external_link"] = {
            "link_type": "pull_request",
            "url": f"https://github.com/example/frontend/pull/{50 + len(activity_type)}",
        }
    response = client.post(
        f"/api/v1/review-cases/{api_fixture['case']}/activities",
        headers=headers(api_fixture),
        json=payload,
    )
    assert response.status_code == 201
    assert response.json()["case_status"] == "open"


def test_duplicate_and_not_found_errors_are_stable(
    client: TestClient, api_fixture: dict[str, UUID]
) -> None:
    url = "https://github.com/example/frontend/issues/41"
    payload = {
        "activity_type": "remediation_requested",
        "candidate_id": str(api_fixture["candidate_latest"]),
        "note": "조치",
        "external_link": {"link_type": "issue", "url": url},
    }
    assert (
        client.post(
            f"/api/v1/review-cases/{api_fixture['case']}/activities",
            headers=headers(api_fixture),
            json=payload,
        ).status_code
        == 201
    )
    duplicate = client.post(
        f"/api/v1/review-cases/{api_fixture['case']}/activities",
        headers=headers(api_fixture),
        json=payload,
    )
    assert (duplicate.status_code, duplicate.json()["code"]) == (
        409,
        "duplicate_activity",
    )

    unlinked = client.post(
        f"/api/v1/review-cases/{api_fixture['case']}/activities",
        headers=headers(api_fixture),
        json={
            "activity_type": "review_deferred",
            "candidate_id": str(api_fixture["unlinked_candidate"]),
            "note": "보류",
        },
    )
    assert (unlinked.status_code, unlinked.json()["code"]) == (
        404,
        "candidate_not_found",
    )


def test_duplicate_external_url_rolls_back_activity(
    client: TestClient, api_fixture: dict[str, UUID], postgres_engine: Engine
) -> None:
    url = "https://github.com/example/frontend/issues/77"
    first = client.post(
        f"/api/v1/review-cases/{api_fixture['case']}/activities",
        headers=headers(api_fixture),
        json={
            "activity_type": "external_link_added",
            "external_link": {"link_type": "issue", "url": url},
        },
    )
    assert first.status_code == 201
    before = first.json()["activity"]["id"]
    duplicate = client.post(
        f"/api/v1/review-cases/{api_fixture['case_high']}/activities",
        headers=headers(api_fixture),
        json={
            "activity_type": "external_link_added",
            "external_link": {"link_type": "issue", "url": url},
        },
    )
    assert (duplicate.status_code, duplicate.json()["code"]) == (
        409,
        "duplicate_external_link",
    )
    with Session(postgres_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ReviewActivity)
                .where(ReviewActivity.activity_type == "external_link_added")
            )
            == 1
        )
        assert session.scalar(select(ReviewActivity.id)) == UUID(before)


def test_scope_and_missing_case_errors(
    client: TestClient, api_fixture: dict[str, UUID]
) -> None:
    wrong_user = client.get(
        "/api/v1/review-cases", headers=headers(api_fixture, other_user=True)
    )
    assert (wrong_user.status_code, wrong_user.json()["code"]) == (
        403,
        "organization_scope_violation",
    )
    cross_org = client.get(
        f"/api/v1/review-cases/{api_fixture['other_case']}",
        headers=headers(api_fixture),
    )
    assert (cross_org.status_code, cross_org.json()["code"]) == (
        403,
        "organization_scope_violation",
    )
    missing = client.get(
        f"/api/v1/review-cases/{uuid4()}", headers=headers(api_fixture)
    )
    assert (missing.status_code, missing.json()["code"]) == (
        404,
        "review_case_not_found",
    )


def test_invalid_context_uuid_returns_422(client: TestClient) -> None:
    response = client.get(
        "/api/v1/review-cases",
        headers={"X-Organization-ID": "invalid", "X-User-ID": "invalid"},
    )
    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


@pytest.mark.parametrize(
    "query",
    [
        "page=0",
        "page_size=101",
        "status=invalid",
        "priority=invalid",
        "sort=invalid",
        "order=invalid",
        "change_type=",
    ],
)
def test_invalid_list_query_returns_422_with_valid_context(
    client: TestClient, api_fixture: dict[str, UUID], query: str
) -> None:
    response = client.get(f"/api/v1/review-cases?{query}", headers=headers(api_fixture))
    assert (response.status_code, response.json()["code"]) == (
        422,
        "validation_error",
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"activity_type": "note_added", "note": "   "},
        {"activity_type": "external_link_added"},
        {
            "activity_type": "remediation_requested",
            "note": "Candidate가 없는 조치 요청",
        },
        {
            "activity_type": "external_link_added",
            "candidate_id": "not-a-uuid",
            "external_link": {
                "link_type": "issue",
                "url": "https://github.com/example/frontend/issues/21",
            },
        },
        {
            "activity_type": "external_link_added",
            "external_link": {
                "link_type": "pull_request",
                "url": "https://github.com/example/frontend/issues/21",
            },
        },
        {
            "activity_type": "external_link_added",
            "external_link": {
                "link_type": "issue",
                "url": "https://example.com/example/frontend/issues/21",
            },
        },
        {
            "activity_type": "unknown",
            "candidate_id": str(UUID("40000000-0000-0000-0000-000000000001")),
            "note": "알 수 없는 활동",
        },
    ],
)
def test_invalid_activity_payload_returns_422_with_valid_context(
    client: TestClient, api_fixture: dict[str, UUID], payload: dict[str, object]
) -> None:
    response = client.post(
        f"/api/v1/review-cases/{api_fixture['case']}/activities",
        headers=headers(api_fixture),
        json=payload,
    )
    assert (response.status_code, response.json()["code"]) == (
        422,
        "validation_error",
    )
