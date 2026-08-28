from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum


class SourceAnnotationType(StrEnum):
    EPSS_MODEL_TRANSITION = "EPSS_MODEL_TRANSITION"
    EPSS_MODEL_TRANSITION_AFTEREFFECT = "EPSS_MODEL_TRANSITION_AFTEREFFECT"
    EPSS_SOURCE_SCORE_SHIFT = "EPSS_SOURCE_SCORE_SHIFT"


@dataclass(frozen=True)
class SourceAnnotationDefinition:
    snapshot_date: date
    annotation_type: SourceAnnotationType
    label: str
    description: str
    source_url: str


SOURCE_ANNOTATION_CATALOG: tuple[SourceAnnotationDefinition, ...] = (
    SourceAnnotationDefinition(
        snapshot_date=date(2025, 11, 18),
        annotation_type=SourceAnnotationType.EPSS_SOURCE_SCORE_SHIFT,
        label="EPSS 소스 점수 대규모 변동일",
        description=(
            "EPSS 점수가 10%p 이상 증가한 CVE가 2,677개로 확인되어, "
            "후보가 평소보다 많이 발생했을 가능성이 있는 날짜입니다."
        ),
        source_url=(
            "https://expel.com/blog/patch-tuesday-december-2025-expels-version/"
        ),
    ),
    SourceAnnotationDefinition(
        snapshot_date=date(2026, 6, 15),
        annotation_type=SourceAnnotationType.EPSS_MODEL_TRANSITION,
        label="EPSS 모델 v5 전환일",
        description=(
            "FIRST가 공지한 EPSS v5 모델 전환일로, 모델 변경 영향에 따라 "
            "후보가 급증했을 가능성이 있는 날짜입니다."
        ),
        source_url="https://www.first.org/epss/data",
    ),
    SourceAnnotationDefinition(
        snapshot_date=date(2026, 6, 16),
        annotation_type=SourceAnnotationType.EPSS_MODEL_TRANSITION_AFTEREFFECT,
        label="EPSS 모델 전환 직후 영향일",
        description=(
            "FIRST가 공지한 EPSS v5 모델 전환일 직후 날짜로, 모델 변경 영향이 "
            "일부 이어져 후보가 증가했을 가능성이 있습니다."
        ),
        source_url="https://www.first.org/epss/data",
    ),
)

_ANNOTATIONS_BY_DATE = {
    annotation.snapshot_date: tuple(
        item
        for item in SOURCE_ANNOTATION_CATALOG
        if item.snapshot_date == annotation.snapshot_date
    )
    for annotation in SOURCE_ANNOTATION_CATALOG
}


def annotations_for_as_of(
    as_of: datetime | None,
) -> tuple[SourceAnnotationDefinition, ...]:
    if as_of is None:
        return ()
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    snapshot_date = as_of.astimezone(UTC).date()
    return _ANNOTATIONS_BY_DATE.get(snapshot_date, ())
