from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Path, Query, status
from fastapi.responses import JSONResponse

from watchback_backend.api.schemas import (
    ACTIVITY_REQUEST_EXAMPLE,
    ACTIVITY_RESPONSE_EXAMPLE,
    DETAIL_EXAMPLE,
    EMPTY_LIST_EXAMPLE,
    LIST_EXAMPLE,
    CaseSort,
    CaseStatusFilter,
    ErrorResponse,
    Priority,
    ReviewActivityCreate,
    ReviewActivityCreated,
    ReviewCaseDetail,
    ReviewCaseListResponse,
    SortOrder,
)


router = APIRouter(prefix="/api/v1/review-cases", tags=["review-cases"])

def _error_response(description: str, code: str, message: str) -> dict[str, Any]:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "example": {"code": code, "message": message, "details": None}
            }
        },
    }


FORBIDDEN = _error_response(
    "사용자가 요청 조직에 속하지 않음",
    "organization_scope_violation",
    "요청한 조직 범위에 접근할 수 없습니다.",
)
NOT_FOUND = _error_response(
    "요청 조직에서 재검토 Case를 찾을 수 없음",
    "review_case_not_found",
    "재검토 Case를 찾을 수 없습니다.",
)
CONFLICT = {
    "model": ErrorResponse,
    "description": "동일 활동·외부 링크 또는 현재 Case 상태와 충돌",
    "content": {
        "application/json": {
            "examples": {
                "duplicate_activity": {
                    "value": {
                        "code": "duplicate_activity",
                        "message": "동일 Candidate에 같은 활동이 이미 기록되었습니다.",
                        "details": None,
                    }
                },
                "duplicate_external_link": {
                    "value": {
                        "code": "duplicate_external_link",
                        "message": "조직에 같은 외부 링크가 이미 등록되어 있습니다.",
                        "details": None,
                    }
                },
                "case_state_conflict": {
                    "value": {
                        "code": "case_state_conflict",
                        "message": "현재 Case 상태에서는 요청한 활동을 기록할 수 없습니다.",
                        "details": None,
                    }
                },
            }
        }
    },
}
VALIDATION_ERROR = _error_response(
    "요청 경로·헤더·쿼리·본문 검증 실패",
    "validation_error",
    "요청 값이 API 계약에 맞지 않습니다.",
)
NOT_IMPLEMENTED = _error_response(
    "이슈 #86에서는 계약만 제공하며 실제 처리는 WEB-04에서 구현",
    "not_implemented",
    "API 계약만 정의되어 있으며 아직 실행 기능은 구현되지 않았습니다.",
)


def _not_implemented() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "code": "not_implemented",
            "message": "API 계약만 정의되어 있으며 아직 실행 기능은 구현되지 않았습니다.",
            "details": None,
        },
    )


@router.get(
    "",
    response_model=ReviewCaseListResponse,
    summary="재검토 Case 목록",
    responses={
        200: {
            "description": "필터와 페이지 조건에 맞는 재검토 Case 목록",
            "content": {
                "application/json": {
                    "examples": {
                        "with_items": {"value": LIST_EXAMPLE},
                        "empty": {"value": EMPTY_LIST_EXAMPLE},
                    }
                }
            },
        },
        403: FORBIDDEN,
        422: VALIDATION_ERROR,
        501: NOT_IMPLEMENTED,
    },
)
def list_review_cases(
    case_status: Annotated[
        CaseStatusFilter,
        Query(alias="status", description="기본값은 열린 Case만 조회합니다."),
    ] = CaseStatusFilter.OPEN,
    priority: Annotated[Priority | None, Query()] = None,
    change_type: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    sort: Annotated[
        CaseSort,
        Query(
            description="priority는 critical→high→medium→low 순이며 동률이면 updated_at 내림차순입니다."
        ),
    ] = CaseSort.PRIORITY,
    order: Annotated[SortOrder, Query()] = SortOrder.DESC,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Any:
    del case_status, priority, change_type, sort, order, page, page_size
    return _not_implemented()


@router.get(
    "/{case_id}",
    response_model=ReviewCaseDetail,
    summary="재검토 Case 상세",
    responses={
        200: {
            "description": "Alert와 전체 Candidate·Evidence·활동 이력",
            "content": {"application/json": {"example": DETAIL_EXAMPLE}},
        },
        403: FORBIDDEN,
        404: NOT_FOUND,
        422: VALIDATION_ERROR,
        501: NOT_IMPLEMENTED,
    },
)
def get_review_case(
    case_id: Annotated[UUID, Path(description="재검토 Case 식별자")],
) -> Any:
    del case_id
    return _not_implemented()


@router.post(
    "/{case_id}/activities",
    response_model=ReviewActivityCreated,
    status_code=status.HTTP_201_CREATED,
    summary="재검토 활동과 외부 링크 기록",
    responses={
        201: {
            "description": "기록된 활동, 작업자·시각과 외부 링크",
            "content": {"application/json": {"example": ACTIVITY_RESPONSE_EXAMPLE}},
        },
        403: FORBIDDEN,
        404: NOT_FOUND,
        409: CONFLICT,
        422: VALIDATION_ERROR,
        501: NOT_IMPLEMENTED,
    },
)
def create_review_activity(
    case_id: Annotated[UUID, Path(description="재검토 Case 식별자")],
    payload: Annotated[
        ReviewActivityCreate,
        Body(
            discriminator="activity_type",
            openapi_examples={"with_external_link": {"value": ACTIVITY_REQUEST_EXAMPLE}},
        ),
    ],
) -> Any:
    del case_id, payload
    return _not_implemented()
