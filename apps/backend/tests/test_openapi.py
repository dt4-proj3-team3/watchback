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
from watchback_backend.db.session import get_session
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


def test_openapi_exposes_paths_and_required_context_headers(
    openapi_document: dict[str, Any],
) -> None:
    paths = openapi_document["paths"]
    for path, method in (
        ("/api/v1/review-cases", "get"),
        ("/api/v1/review-cases/dashboard-summary", "get"),
        ("/api/v1/review-cases/{case_id}", "get"),
        ("/api/v1/review-cases/{case_id}/activities", "post"),
    ):
        operation = paths[path][method]
        headers = {
            item["name"]: item
            for item in operation["parameters"]
            if item["in"] == "header"
        }
        assert set(headers) == {"X-Organization-ID", "X-User-ID"}
        assert all(item["required"] for item in headers.values())
        assert "501" not in operation["responses"]


def test_list_contract_defines_filters_sort_pagination_and_empty_example(
    openapi_document: dict[str, Any],
) -> None:
    operation = openapi_document["paths"]["/api/v1/review-cases"]["get"]
    assert _parameter(operation, "status")["schema"]["default"] == "open"
    priority = _parameter(operation, "priority")["schema"]
    priority_schema = _resolve_schema(openapi_document, priority["anyOf"][0]["$ref"])
    assert priority_schema["enum"] == ["P0", "P1", "P2", "P3"]
    assert _parameter(operation, "sort")["schema"]["default"] == "priority"
    assert _parameter(operation, "order")["schema"]["default"] == "desc"
    assert _parameter(operation, "page")["schema"]["minimum"] == 1
    page_size = _parameter(operation, "page_size")["schema"]
    assert (page_size["default"], page_size["minimum"], page_size["maximum"]) == (
        20,
        1,
        100,
    )
    examples = operation["responses"]["200"]["content"]["application/json"]["examples"]
    assert examples["empty"]["value"] == EMPTY_LIST_EXAMPLE


def test_detail_contract_contains_candidate_batch_evidence_and_activity_history(
    openapi_document: dict[str, Any],
) -> None:
    operation = openapi_document["paths"]["/api/v1/review-cases/{case_id}"]["get"]
    detail = _resolve_schema(
        openapi_document,
        operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"],
    )
    assert {"candidates", "activities"}.issubset(detail["required"])
    candidate = _resolve_schema(
        openapi_document, detail["properties"]["candidates"]["items"]["$ref"]
    )
    assert {"deliveries", "evidence"}.issubset(candidate["required"])
    assert {item.get("type") for item in candidate["properties"]["ghsa_id"]["anyOf"]} == {
        "string",
        "null",
    }
    assert "cve_id" in candidate["required"]
    summary = _resolve_schema(
        openapi_document,
        openapi_document["paths"]["/api/v1/review-cases"]["get"]["responses"][
            "200"
        ]["content"]["application/json"]["schema"]["$ref"],
    )
    list_item = _resolve_schema(
        openapi_document, summary["properties"]["items"]["items"]["$ref"]
    )
    assert "source_annotations" in list_item["properties"]
    delivery = _resolve_schema(
        openapi_document, candidate["properties"]["deliveries"]["items"]["$ref"]
    )
    assert "source_annotations" in delivery["properties"]
    assert DETAIL_EXAMPLE["candidates"][0]["deliveries"][0][
        "source_annotations"
    ][0]["annotation_type"] == "EPSS_MODEL_TRANSITION"
    assert LIST_EXAMPLE["items"][0]["latest_candidate"]["change_type"] == "kev_new"


def test_activity_contract_and_examples(openapi_document: dict[str, Any]) -> None:
    operation = openapi_document["paths"]["/api/v1/review-cases/{case_id}/activities"][
        "post"
    ]
    assert {"403", "404", "409", "422"}.issubset(operation["responses"])
    conflicts = operation["responses"]["409"]["content"]["application/json"]["examples"]
    assert set(conflicts) == {"duplicate_activity", "duplicate_external_link"}
    assert ACTIVITY_RESPONSE_EXAMPLE["case_status"] == "resolved"
    assert ACTIVITY_RESPONSE_EXAMPLE["activity"]["activity_type"] == "risk_accepted"
    assert (
        ACTIVITY_RESPONSE_EXAMPLE["activity"]["external_links"][0]["external_state"]
        is None
    )


def test_representative_examples_conform_to_models() -> None:
    ReviewCaseListResponse.model_validate(LIST_EXAMPLE)
    ReviewCaseListResponse.model_validate(EMPTY_LIST_EXAMPLE)
    ReviewCaseDetail.model_validate(DETAIL_EXAMPLE)
    TypeAdapter(ReviewActivityCreate).validate_python(ACTIVITY_REQUEST_EXAMPLE)
    ReviewActivityCreated.model_validate(ACTIVITY_RESPONSE_EXAMPLE)
    ReviewActivityResponse.model_validate(
        {
            **ACTIVITY_RESPONSE_EXAMPLE["activity"],
            "candidate_id": None,
            "activity_type": "case_opened",
            "note": None,
            "actor": None,
        }
    )


def _unused_session() -> Any:
    yield None


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/v1/review-cases", None),
        ("get", f"/api/v1/review-cases/{CASE_ID}", None),
        ("get", "/api/v1/review-cases?page_size=101", None),
        ("get", "/api/v1/review-cases?status=invalid", None),
        ("get", "/api/v1/review-cases/not-a-uuid", None),
        (
            "post",
            f"/api/v1/review-cases/{CASE_ID}/activities",
            {"activity_type": "note_added", "note": "   "},
        ),
    ],
)
def test_invalid_or_missing_context_returns_uniform_validation_error(
    method: str, path: str, payload: dict[str, Any] | None
) -> None:
    app.dependency_overrides[get_session] = _unused_session
    try:
        response = client.request(method, path, json=payload)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
