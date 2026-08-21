from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from watchback_backend.api.schemas import (
    ACTIVITY_REQUEST_EXAMPLE,
    ACTIVITY_RESPONSE_EXAMPLE,
    DETAIL_EXAMPLE,
    EMPTY_LIST_EXAMPLE,
    LIST_EXAMPLE,
    ReviewActivityCreate,
    ReviewActivityCreated,
    ReviewActivityResponse,
    ReviewCaseDetail,
    ReviewCaseListResponse,
)
from watchback_backend.main import app


client = TestClient(app)
CASE_ID = "30000000-0000-0000-0000-000000000001"
CANDIDATE_ID = "40000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="module")
def openapi_document() -> dict[str, Any]:
    return client.get("/openapi.json").json()


def _parameter(operation: dict[str, Any], name: str) -> dict[str, Any]:
    return next(item for item in operation["parameters"] if item["name"] == name)


def _resolve_schema(document: dict[str, Any], ref: str) -> dict[str, Any]:
    prefix = "#/components/schemas/"
    assert ref.startswith(prefix)
    return document["components"]["schemas"][ref.removeprefix(prefix)]


def test_openapi_exposes_review_case_contract(openapi_document: dict[str, Any]) -> None:
    paths = openapi_document["paths"]
    assert "/api/v1/review-cases" in paths
    assert "/api/v1/review-cases/{case_id}" in paths
    assert "/api/v1/review-cases/{case_id}/activities" in paths

    for path, method in (
        ("/api/v1/review-cases", "get"),
        ("/api/v1/review-cases/{case_id}", "get"),
        ("/api/v1/review-cases/{case_id}/activities", "post"),
    ):
        operation = paths[path][method]
        assert all(item["in"] != "header" for item in operation.get("parameters", []))


def test_list_contract_defines_filters_sort_pagination_and_empty_example(
    openapi_document: dict[str, Any],
) -> None:
    operation = openapi_document["paths"]["/api/v1/review-cases"]["get"]

    assert _parameter(operation, "status")["schema"]["default"] == "open"
    assert _parameter(operation, "sort")["schema"]["default"] == "priority"
    assert _parameter(operation, "order")["schema"]["default"] == "desc"
    assert _parameter(operation, "page")["schema"]["minimum"] == 1
    page_size = _parameter(operation, "page_size")["schema"]
    assert page_size["default"] == 20
    assert page_size["minimum"] == 1
    assert page_size["maximum"] == 100

    examples = operation["responses"]["200"]["content"]["application/json"]["examples"]
    assert examples["with_items"]["value"]["total"] == 1
    assert examples["empty"]["value"] == {
        "items": [],
        "page": 1,
        "page_size": 20,
        "total": 0,
    }


def test_detail_contract_contains_candidate_batch_evidence_and_activity_history(
    openapi_document: dict[str, Any],
) -> None:
    operation = openapi_document["paths"]["/api/v1/review-cases/{case_id}"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    detail = _resolve_schema(openapi_document, response_schema["$ref"])

    assert {"candidates", "activities"}.issubset(detail["required"])
    repository_ref = detail["properties"]["repository"]["$ref"]
    repository = _resolve_schema(openapi_document, repository_ref)
    assert {"full_name", "display_name"}.issubset(repository["required"])
    candidate_ref = detail["properties"]["candidates"]["items"]["$ref"]
    candidate = _resolve_schema(openapi_document, candidate_ref)
    assert {"deliveries", "evidence"}.issubset(candidate["required"])

    delivery_ref = candidate["properties"]["deliveries"]["items"]["$ref"]
    delivery = _resolve_schema(openapi_document, delivery_ref)
    assert {"as_of", "policy_version", "source_batch_id"}.issubset(delivery["required"])

    evidence_ref = candidate["properties"]["evidence"]["items"]["$ref"]
    evidence = _resolve_schema(openapi_document, evidence_ref)
    assert {
        "previous_value",
        "current_value",
        "value_type",
        "observed_at",
        "source",
    }.issubset(evidence["required"])


def test_activity_contract_defines_examples_and_error_responses(
    openapi_document: dict[str, Any],
) -> None:
    operation = openapi_document["paths"][
        "/api/v1/review-cases/{case_id}/activities"
    ]["post"]

    body_examples = operation["requestBody"]["content"]["application/json"]["examples"]
    assert body_examples["with_external_link"]["value"]["candidate_id"] == CANDIDATE_ID
    assert operation["responses"]["201"]["content"]["application/json"]["example"][
        "activity"
    ]["actor"]["display_name"] == "Watchback Reviewer"
    assert {"403", "404", "409", "422", "501"}.issubset(operation["responses"])

    conflict_examples = operation["responses"]["409"]["content"]["application/json"][
        "examples"
    ]
    assert {"duplicate_activity", "duplicate_external_link"}.issubset(conflict_examples)

    body_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert len(body_schema["oneOf"]) == 3
    assert body_schema["discriminator"]["propertyName"] == "activity_type"


def test_representative_examples_conform_to_response_models() -> None:
    ReviewCaseListResponse.model_validate(LIST_EXAMPLE)
    ReviewCaseListResponse.model_validate(EMPTY_LIST_EXAMPLE)
    ReviewCaseDetail.model_validate(DETAIL_EXAMPLE)
    TypeAdapter(ReviewActivityCreate).validate_python(ACTIVITY_REQUEST_EXAMPLE)
    ReviewActivityCreated.model_validate(ACTIVITY_RESPONSE_EXAMPLE)

    system_activity = {
        **ACTIVITY_RESPONSE_EXAMPLE["activity"],
        "candidate_id": None,
        "activity_type": "case_opened",
        "note": None,
        "actor": None,
    }
    ReviewActivityResponse.model_validate(system_activity)


@pytest.mark.parametrize(
    ("path", "expected_status"),
    [
        ("/api/v1/review-cases", 501),
        (f"/api/v1/review-cases/{CASE_ID}", 501),
        ("/api/v1/review-cases?page_size=101", 422),
        ("/api/v1/review-cases?status=invalid", 422),
        ("/api/v1/review-cases/not-a-uuid", 422),
    ],
)
def test_get_contract_validation(path: str, expected_status: int) -> None:
    response = client.get(path)
    assert response.status_code == expected_status
    assert response.json()["code"] in {"not_implemented", "validation_error"}


@pytest.mark.parametrize(
    "payload",
    [
        {
            "activity_type": "note_added",
            "candidate_id": CANDIDATE_ID,
            "note": "   ",
        },
        {
            "activity_type": "external_link_added",
            "candidate_id": CANDIDATE_ID,
        },
        {
            "activity_type": "unknown",
            "candidate_id": CANDIDATE_ID,
            "note": "메모",
        },
        {
            "activity_type": "external_link_added",
            "candidate_id": "not-a-uuid",
            "external_link": {
                "link_type": "issue",
                "url": "https://github.com/watchback/demo-frontend/issues/21",
            },
        },
        {
            "activity_type": "remediation_requested",
            "note": "Candidate가 없는 결정 요청",
        },
        {
            "activity_type": "external_link_added",
            "candidate_id": CANDIDATE_ID,
            "external_link": {
                "link_type": "pull_request",
                "url": "https://github.com/watchback/demo-frontend/issues/21",
            },
        },
    ],
)
def test_invalid_activity_requests_return_uniform_validation_error(
    payload: dict[str, Any],
) -> None:
    response = client.post(
        f"/api/v1/review-cases/{CASE_ID}/activities",
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_valid_activity_request_is_contract_only() -> None:
    response = client.post(
        f"/api/v1/review-cases/{CASE_ID}/activities",
        json={
            "activity_type": "remediation_requested",
            "candidate_id": CANDIDATE_ID,
            "note": "패치 작업을 요청합니다.",
            "external_link": {
                "link_type": "pull_request",
                "url": "https://github.com/watchback/demo-frontend/pull/22",
            },
        },
    )
    assert response.status_code == 501
    assert response.json()["code"] == "not_implemented"


@pytest.mark.parametrize(
    "payload",
    [
        {"activity_type": "note_added", "note": "Case 전체에 남기는 메모입니다."},
        {
            "activity_type": "external_link_added",
            "external_link": {
                "link_type": "issue",
                "url": "https://github.com/watchback/demo-frontend/issues/23",
            },
        },
    ],
)
def test_case_wide_activity_does_not_require_candidate(payload: dict[str, Any]) -> None:
    response = client.post(
        f"/api/v1/review-cases/{CASE_ID}/activities",
        json=payload,
    )
    assert response.status_code == 501
