from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, Path, Query, status
from sqlalchemy.orm import Session

from watchback_backend.api import service
from watchback_backend.api.schemas import (
    ACTIVITY_REQUEST_EXAMPLE,
    ACTIVITY_RESPONSE_EXAMPLE,
    DETAIL_EXAMPLE,
    EMPTY_LIST_EXAMPLE,
    LIST_EXAMPLE,
    CandidatePriority,
    CaseSort,
    CaseStatusFilter,
    ErrorResponse,
    ReviewDashboardSummary,
    ReviewActivityCreate,
    ReviewActivityCreated,
    ReviewCaseDetail,
    ReviewCaseListResponse,
    SortOrder,
)
from watchback_backend.db.session import get_session


router = APIRouter(prefix="/api/v1/review-cases", tags=["review-cases"])


@dataclass(frozen=True)
class ContextHeaders:
    organization_id: UUID
    user_id: UUID


def get_context_headers(
    organization_id: Annotated[
        UUID, Header(alias="X-Organization-ID", description="요청 조직 UUID")
    ],
    user_id: Annotated[UUID, Header(alias="X-User-ID", description="작업자 UUID")],
) -> ContextHeaders:
    return ContextHeaders(organization_id, user_id)


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
NOT_FOUND = {
    "model": ErrorResponse,
    "description": "재검토 Case 또는 연결된 Candidate를 찾을 수 없음",
    "content": {
        "application/json": {
            "examples": {
                "review_case_not_found": {
                    "value": {
                        "code": "review_case_not_found",
                        "message": "재검토 Case를 찾을 수 없습니다.",
                        "details": None,
                    }
                },
                "candidate_not_found": {
                    "value": {
                        "code": "candidate_not_found",
                        "message": "이 Case에 연결된 위험 후보를 찾을 수 없습니다.",
                        "details": None,
                    }
                },
            }
        }
    },
}
CONFLICT = {
    "model": ErrorResponse,
    "description": "동일 활동 또는 외부 링크와 충돌",
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
            }
        }
    },
}
VALIDATION_ERROR = _error_response(
    "요청 경로·헤더·쿼리·본문 검증 실패",
    "validation_error",
    "요청 값이 API 계약에 맞지 않습니다.",
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
    },
)
def list_review_cases(
    headers: Annotated[ContextHeaders, Depends(get_context_headers)],
    session: Annotated[Session, Depends(get_session)],
    case_status: Annotated[
        CaseStatusFilter,
        Query(alias="status", description="기본값은 열린 Case만 조회합니다."),
    ] = CaseStatusFilter.OPEN,
    priority: Annotated[
        CandidatePriority | None,
        Query(description="대표 Candidate의 DS 재검토 우선순위(P0~P3)"),
    ] = None,
    change_type: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    sort: Annotated[
        CaseSort,
        Query(
            description="priority는 P0→P1→P2→P3 순이며 동률이면 updated_at 내림차순입니다."
        ),
    ] = CaseSort.PRIORITY,
    order: Annotated[SortOrder, Query()] = SortOrder.DESC,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReviewCaseListResponse:
    context = service.require_context(session, headers.organization_id, headers.user_id)
    return service.list_review_cases(
        session,
        context,
        case_status=case_status,
        priority=priority,
        change_type=change_type,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/dashboard-summary",
    response_model=ReviewDashboardSummary,
    summary="재검토 대시보드 주간 비교",
    responses={403: FORBIDDEN, 422: VALIDATION_ERROR},
)
def get_review_dashboard_summary(
    headers: Annotated[ContextHeaders, Depends(get_context_headers)],
    session: Annotated[Session, Depends(get_session)],
) -> ReviewDashboardSummary:
    context = service.require_context(session, headers.organization_id, headers.user_id)
    return service.get_review_dashboard_summary(session, context)


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
    },
)
def get_review_case(
    case_id: Annotated[UUID, Path(description="재검토 Case 식별자")],
    headers: Annotated[ContextHeaders, Depends(get_context_headers)],
    session: Annotated[Session, Depends(get_session)],
) -> ReviewCaseDetail:
    context = service.require_context(session, headers.organization_id, headers.user_id)
    return service.get_review_case(session, context, case_id)


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
    },
)
def create_review_activity(
    case_id: Annotated[UUID, Path(description="재검토 Case 식별자")],
    headers: Annotated[ContextHeaders, Depends(get_context_headers)],
    session: Annotated[Session, Depends(get_session)],
    payload: Annotated[
        ReviewActivityCreate,
        Body(
            discriminator="activity_type",
            openapi_examples={
                "with_external_link": {"value": ACTIVITY_REQUEST_EXAMPLE}
            },
        ),
    ],
) -> ReviewActivityCreated:
    context = service.require_context(session, headers.organization_id, headers.user_id)
    return service.create_review_activity(session, context, case_id, payload)
