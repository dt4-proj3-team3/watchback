from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from watchback_backend.api import service as review_service
from watchback_backend.api.schemas import (
    CaseSort,
    CaseStatusFilter,
    ReviewCaseDetail,
    ReviewCaseSummary,
    SortOrder,
)
from watchback_backend.api.service import RequestContext
from watchback_backend.ai_agent.service import GroundingSource
from watchback_backend.db.models import AIContextDocument, SecurityAdvisory


DEFAULT_OPEN_CASE_LIMIT = 3
MAX_GROUNDING_SOURCES = 48

CHANGE_LABELS = {
    "kev": "KEV 실제 악용 확인",
    "kev_new": "KEV 실제 악용 확인",
    "kev_added": "KEV 실제 악용 확인",
    "epss_score": "EPSS 악용 가능성 변화",
    "epss_score_d30": "EPSS 악용 가능성 상승",
    "epss_percentile": "EPSS 위험 구간 변화",
    "epss_percentile_d30": "EPSS 상위 위험 구간 진입",
    "epss_rise": "EPSS 악용 가능성 상승",
    "epss_rise_d30": "EPSS 악용 가능성 상승",
    "epss_top5_entry": "EPSS 상위 위험 구간 진입",
    "epss_top5_entry_d30": "EPSS 상위 위험 구간 진입",
    "patch_available": "수정 버전 확인",
    "patch_new": "수정 버전 확인",
}

SOURCE_LABELS = {
    "cisa_kev": "CISA KEV",
    "cisa-kev": "CISA KEV",
    "cisa kev": "CISA KEV",
    "first_epss": "FIRST EPSS",
    "first-epss": "FIRST EPSS",
    "first epss": "FIRST EPSS",
    "ghsa": "GitHub Security Advisory",
    "github_advisory": "GitHub Security Advisory",
}


def build_grounding_sources(
    session: Session,
    context: RequestContext,
    case_id: UUID | None,
    remediation_group_id: str | None = None,
) -> list[GroundingSource]:
    if remediation_group_id is not None:
        return _remediation_group_sources(session, context, remediation_group_id)
    if case_id is not None:
        detail = review_service.get_review_case(session, context, case_id)
        return _detail_sources(context.organization_id, detail)

    result = review_service.list_review_cases(
        session,
        context,
        case_status=CaseStatusFilter.OPEN,
        priority=None,
        change_type=None,
        sort=CaseSort.PRIORITY,
        order=SortOrder.DESC,
        page=1,
        page_size=DEFAULT_OPEN_CASE_LIMIT,
    )
    sources: list[GroundingSource] = []
    for summary in result.items:
        sources.extend(_summary_sources(context.organization_id, summary))
    return sources


def _remediation_group_sources(
    session: Session,
    context: RequestContext,
    group_id: str,
) -> list[GroundingSource]:
    from watchback_backend.remediation.service import list_remediation_groups

    group = next(
        (item for item in list_remediation_groups(session, context).items if item.id == group_id),
        None,
    )
    if group is None:
        return []
    is_litellm = (
        group.ecosystem.lower() == "pip"
        and group.package_name.lower().replace("_", "-") == "litellm"
    )
    advisory_severities = [
        str(vulnerability.advisory_severity).split(".")[-1].lower()
        for vulnerability in group.vulnerabilities
    ]
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    display_severity = min(
        advisory_severities,
        key=lambda value: severity_rank.get(value, 99),
        default="확인 불가",
    )
    sources = [
        GroundingSource(
            organization_id=context.organization_id,
            source_type="review_case",
            source_id=f"remediation_group:{group.id}",
            title=f"{group.package_name} 패키지 조치 후보",
            content=(
                f"ecosystem={group.ecosystem}; 표시 위험도={display_severity.title()}; "
                f"CVE={group.cve_count}건; 저장소={group.repository_count}곳; "
                f"Open Alert={group.github_alert_counts.open}건; "
                f"권장 수정 버전 후보={', '.join(group.recommended_fix_versions) or '없음'}"
            ),
            observed_at=group.updated_at,
        )
    ]
    if is_litellm:
        sources.extend(
            _litellm_advisory_sources(
                session,
                context.organization_id,
                {(item.cve_id, item.ghsa_id) for item in group.vulnerabilities},
            )
        )
        sources.extend(
            _litellm_analysis_sources(
                session,
                context.organization_id,
                group.id,
            )
        )
    for target in group.targets:
        versions = ", ".join(target.current_versions) or "확인 불가"
        for alert in target.alerts:
            sources.append(
                GroundingSource(
                    organization_id=context.organization_id,
                    source_type="dependabot_alert",
                    source_id=f"dependabot_alert:{alert.id}",
                    title=f"{target.repository.display_name} · Alert #{alert.github_alert_number}",
                    content=(
                        f"상태={alert.state}; manifest={target.manifest_path or '확인 불가'}; "
                        f"현재 버전={versions}; 영향 버전={alert.vulnerable_version_range}; "
                        f"최초 패치 버전={alert.first_patched_version or '확인 불가'}; "
                        f"CVE={alert.cve_id}"
                    ),
                    observed_at=alert.github_updated_at,
                    source_url=str(alert.html_url),
                )
            )
    for vulnerability in group.vulnerabilities:
        for candidate in vulnerability.candidates:
            sources.append(
                _candidate_source(
                    context.organization_id,
                    candidate,
                    advisory_summary=vulnerability.advisory_summary,
                    advisory_severity=vulnerability.advisory_severity,
                )
            )
            for evidence in candidate.evidence:
                sources.append(
                    GroundingSource(
                        organization_id=context.organization_id,
                        source_type="evidence",
                        source_id=f"evidence:{evidence.id}",
                        title=(
                            f"{vulnerability.cve_id} · "
                            f"{_change_label(evidence.signal)}"
                        ),
                        content=(
                            f"이전 값={evidence.previous_value or '없음'}; "
                            f"현재 값={evidence.current_value or '없음'}; "
                            f"출처={_source_label(evidence.source)}; "
                            f"설명={evidence.evidence_summary}"
                        ),
                        observed_at=evidence.observed_at,
                    )
                )
            for delivery in candidate.deliveries:
                for annotation in delivery.source_annotations:
                    sources.append(
                        GroundingSource(
                            organization_id=context.organization_id,
                            source_type="source_annotation",
                            source_id=(
                                f"source_annotation:{annotation.snapshot_date}:"
                                f"{annotation.annotation_type}"
                            ),
                            title=annotation.label,
                            content=annotation.description,
                            observed_at=_date_at_utc(annotation.snapshot_date),
                            source_url=str(annotation.source_url),
                        )
                    )
    return _unique_sources(sources)[:MAX_GROUNDING_SOURCES]


def _summary_sources(
    organization_id: UUID, summary: ReviewCaseSummary
) -> list[GroundingSource]:
    case_source = GroundingSource(
        organization_id=organization_id,
        source_type="review_case",
        source_id=f"review_case:{summary.id}",
        title=f"{summary.advisory.cve_id or summary.advisory.ghsa_id} 재검토 Case",
        content=(
            f"상태={summary.status}; 표시 위험도={summary.advisory.severity}; "
            f"저장소={summary.repository.display_name}; 중요도={summary.repository.importance}; "
            f"패키지={summary.alert.package_name} ({summary.alert.ecosystem}); "
            f"Advisory severity={summary.advisory.severity}; "
            f"검토 사유={summary.review_reason}"
        ),
        observed_at=summary.updated_at,
    )
    return [case_source, _candidate_source(organization_id, summary.latest_candidate)]


def _detail_sources(
    organization_id: UUID, detail: ReviewCaseDetail
) -> list[GroundingSource]:
    sources = _summary_sources(organization_id, detail)
    alerts = detail.alerts or [detail.alert]
    for alert in alerts:
        sources.append(
            GroundingSource(
                organization_id=organization_id,
                source_type="dependabot_alert",
                source_id=f"dependabot_alert:{alert.id}",
                title=f"Dependabot Alert #{alert.github_alert_number}",
                content=(
                    f"상태={alert.state}; 패키지={alert.package_name} ({alert.ecosystem}); "
                    f"manifest={alert.manifest_path or '확인 불가'}; "
                    f"영향 버전={alert.vulnerable_version_range}; "
                    f"최초 패치 버전={alert.first_patched_version or '확인 불가'}"
                ),
                observed_at=alert.github_updated_at,
                source_url=str(alert.html_url),
            )
        )

    for candidate in detail.candidates:
        candidate_id = f"candidate:{candidate.id}"
        if all(source.source_id != candidate_id for source in sources):
            sources.append(_candidate_source(organization_id, candidate))
        for evidence in candidate.evidence:
            sources.append(
                GroundingSource(
                    organization_id=organization_id,
                source_type="evidence",
                source_id=f"evidence:{evidence.id}",
                title=f"{candidate.cve_id} · {_change_label(evidence.signal)}",
                content=(
                    f"이전 값={evidence.previous_value or '없음'}; "
                    f"현재 값={evidence.current_value or '없음'}; "
                    f"출처={_source_label(evidence.source)}; "
                    f"설명={evidence.evidence_summary}"
                    ),
                    observed_at=evidence.observed_at,
                )
            )
        for delivery in candidate.deliveries:
            for annotation in delivery.source_annotations:
                sources.append(
                    GroundingSource(
                        organization_id=organization_id,
                        source_type="source_annotation",
                        source_id=(
                            "source_annotation:"
                            f"{annotation.snapshot_date}:{annotation.annotation_type}"
                        ),
                        title=annotation.label,
                        content=annotation.description,
                        observed_at=_date_at_utc(annotation.snapshot_date),
                        source_url=str(annotation.source_url),
                    )
                )
    return _unique_sources(sources)[:MAX_GROUNDING_SOURCES]


def _candidate_source(
    organization_id: UUID,
    candidate,
    *,
    advisory_summary: str | None = None,
    advisory_severity=None,
) -> GroundingSource:
    advisory_context = (
        f"; Advisory 위험도={advisory_severity}; "
        f"Advisory 제목={advisory_summary}"
        if advisory_summary
        else ""
    )
    return GroundingSource(
        organization_id=organization_id,
        source_type="candidate",
        source_id=f"candidate:{candidate.id}",
        title=f"{candidate.cve_id} · {_change_label(candidate.change_type)}",
        content=(
            f"변화={_change_label(candidate.change_type)}; "
            f"선정 사유={candidate.reason_summary}{advisory_context}"
        ),
        observed_at=candidate.selected_at,
    )


def _litellm_advisory_sources(
    session: Session,
    organization_id: UUID,
    identifiers: set[tuple[str, str]],
) -> list[GroundingSource]:
    cve_ids = {cve_id for cve_id, _ in identifiers}
    ghsa_ids = {ghsa_id for _, ghsa_id in identifiers}
    advisories = session.scalars(
        select(SecurityAdvisory)
        .where(
            SecurityAdvisory.cve_id.in_(cve_ids),
            SecurityAdvisory.ghsa_id.in_(ghsa_ids),
        )
        .order_by(SecurityAdvisory.cve_id.asc(), SecurityAdvisory.ghsa_id.asc())
    ).all()
    return [
        GroundingSource(
            organization_id=organization_id,
            source_type="advisory",
            source_id=f"advisory:{advisory.ghsa_id}",
            title=f"{advisory.cve_id or advisory.ghsa_id} 취약점 원문",
            content=(
                f"위험도={advisory.severity.title()}; 제목={advisory.summary}; "
                f"공식 설명={advisory.description or '상세 설명 없음'}"
            ),
            observed_at=advisory.github_updated_at,
            source_url=f"https://github.com/advisories/{advisory.ghsa_id}",
        )
        for advisory in advisories
    ]


def _litellm_analysis_sources(
    session: Session,
    organization_id: UUID,
    group_key: str,
) -> list[GroundingSource]:
    from watchback_backend.ai_agent.litellm_context import document_grounding_source

    documents = session.scalars(
        select(AIContextDocument)
        .where(
            AIContextDocument.organization_id == organization_id,
            AIContextDocument.group_key == group_key,
        )
        .order_by(AIContextDocument.document_type.asc())
    ).all()
    return [
        document_grounding_source(document, organization_id)
        for document in documents
    ]


def _change_label(value: object) -> str:
    normalized = str(value).split(".")[-1].strip().lower()
    return CHANGE_LABELS.get(normalized, "위험 정보 변경")


def _source_label(value: object) -> str:
    normalized = str(value).strip().lower()
    return SOURCE_LABELS.get(normalized, "외부 위험 정보")


def _date_at_utc(value) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def _unique_sources(sources: list[GroundingSource]) -> list[GroundingSource]:
    seen: set[str] = set()
    result: list[GroundingSource] = []
    for source in sources:
        if source.source_id in seen:
            continue
        seen.add(source.source_id)
        result.append(source)
    return result
