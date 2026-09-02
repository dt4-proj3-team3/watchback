import os
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status
from sqlalchemy.orm import Session

from watchback_backend.api import service as review_service
from watchback_backend.api.routes import ContextHeaders, get_context_headers
from watchback_backend.db.session import get_session
from watchback_backend.remediation.schemas import (
    RemediationActionCreate,
    RemediationActionCreated,
    RemediationGroupListResponse,
    RemediationPullRequestBatchCreated,
    RemediationPullRequestCreate,
    RemediationPullRequestCloseResponse,
    RemediationPullRequestMergeRequest,
    RemediationPullRequestMergeResponse,
    RemediationReopened,
    RemediationReopenRequest,
)
from watchback_backend.remediation.service import (
    create_remediation_action,
    create_remediation_pull_requests,
    close_remediation_pull_requests,
    merge_remediation_pull_requests,
    list_remediation_groups,
    reopen_remediation_group,
)


router = APIRouter(prefix="/api/v1/remediation-groups", tags=["remediation-groups"])


@router.get(
    "",
    response_model=RemediationGroupListResponse,
    summary="패키지 단위 조치 후보 목록",
)
def get_remediation_groups(
    headers: Annotated[ContextHeaders, Depends(get_context_headers)],
    session: Annotated[Session, Depends(get_session)],
) -> RemediationGroupListResponse:
    context = review_service.require_context(
        session, headers.organization_id, headers.user_id
    )
    return list_remediation_groups(session, context)


@router.post(
    "/{group_id}/actions",
    response_model=RemediationActionCreated,
    status_code=status.HTTP_201_CREATED,
    summary="패키지 그룹 또는 선택한 저장소·manifest에 조치 기록",
)
def post_remediation_action(
    group_id: Annotated[
        str,
        Path(
            min_length=64,
            max_length=64,
            pattern=r"^[0-9a-f]{64}$",
            description="조직·ecosystem·패키지로 계산한 조치 그룹 키",
        ),
    ],
    payload: Annotated[RemediationActionCreate, Body()],
    headers: Annotated[ContextHeaders, Depends(get_context_headers)],
    session: Annotated[Session, Depends(get_session)],
) -> RemediationActionCreated:
    context = review_service.require_context(
        session, headers.organization_id, headers.user_id
    )
    return create_remediation_action(session, context, group_id, payload)


@router.post(
    "/{group_id}/pull-requests",
    response_model=RemediationPullRequestBatchCreated,
    status_code=status.HTTP_201_CREATED,
    summary="npm·pip 패키지 업데이트 PR 생성",
)
def post_remediation_pull_requests(
    group_id: Annotated[
        str,
        Path(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"),
    ],
    payload: Annotated[RemediationPullRequestCreate, Body()],
    headers: Annotated[ContextHeaders, Depends(get_context_headers)],
    session: Annotated[Session, Depends(get_session)],
) -> RemediationPullRequestBatchCreated:
    context = review_service.require_context(
        session, headers.organization_id, headers.user_id
    )
    token = os.environ.get("GITHUB_REMEDIATION_TOKEN")
    if not token:
        raise review_service.ServiceError(
            503,
            "github_remediation_not_configured",
            "GitHub 자동조치 토큰이 설정되지 않았습니다.",
        )
    return create_remediation_pull_requests(
        session,
        context,
        group_id,
        payload,
        github_token=token,
    )


@router.post(
    "/{group_id}/pull-requests/close",
    response_model=RemediationPullRequestCloseResponse,
    summary="저장된 패키지 업데이트 PR 일괄 닫기",
)
def post_remediation_pull_request_close(
    group_id: Annotated[str, Path(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")],
    payload: Annotated[RemediationPullRequestMergeRequest, Body()],
    headers: Annotated[ContextHeaders, Depends(get_context_headers)],
    session: Annotated[Session, Depends(get_session)],
) -> RemediationPullRequestCloseResponse:
    context = review_service.require_context(session, headers.organization_id, headers.user_id)
    token = os.environ.get("GITHUB_REMEDIATION_TOKEN")
    if not token:
        raise review_service.ServiceError(503, "github_remediation_not_configured", "GitHub 자동조치 토큰이 설정되지 않았습니다.")
    return close_remediation_pull_requests(session, context, group_id, payload, github_token=token)


@router.post(
    "/{group_id}/pull-requests/merge",
    response_model=RemediationPullRequestMergeResponse,
    summary="저장된 패키지 업데이트 PR 병합",
)
def post_remediation_pull_request_merge(
    group_id: Annotated[
        str,
        Path(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"),
    ],
    payload: Annotated[RemediationPullRequestMergeRequest, Body()],
    headers: Annotated[ContextHeaders, Depends(get_context_headers)],
    session: Annotated[Session, Depends(get_session)],
) -> RemediationPullRequestMergeResponse:
    context = review_service.require_context(
        session, headers.organization_id, headers.user_id
    )
    token = os.environ.get("GITHUB_REMEDIATION_TOKEN")
    if not token:
        raise review_service.ServiceError(
            503,
            "github_remediation_not_configured",
            "GitHub 자동조치 토큰이 설정되지 않았습니다.",
        )
    return merge_remediation_pull_requests(
        session,
        context,
        group_id,
        payload,
        github_token=token,
    )


@router.post(
    "/{group_id}/reopen",
    response_model=RemediationReopened,
    summary="패키지 그룹 또는 선택한 저장소·manifest의 재검토 열기",
)
def post_remediation_reopen(
    group_id: Annotated[
        str,
        Path(
            min_length=64,
            max_length=64,
            pattern=r"^[0-9a-f]{64}$",
        ),
    ],
    payload: Annotated[RemediationReopenRequest, Body()],
    headers: Annotated[ContextHeaders, Depends(get_context_headers)],
    session: Annotated[Session, Depends(get_session)],
) -> RemediationReopened:
    context = review_service.require_context(
        session, headers.organization_id, headers.user_id
    )
    return reopen_remediation_group(
        session,
        context,
        group_id,
        target_ids=payload.target_ids,
        note=payload.note,
    )
