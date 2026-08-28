from datetime import UTC, datetime, timedelta, timezone

import pytest

from watchback_backend.api.source_annotations import (
    SOURCE_ANNOTATION_CATALOG,
    SourceAnnotationType,
    annotations_for_observed_at,
)


def test_catalog_contains_the_three_reviewed_external_source_dates() -> None:
    assert [
        (
            item.snapshot_date.isoformat(),
            item.annotation_type,
            item.label,
            item.description,
            item.source_url,
        )
        for item in SOURCE_ANNOTATION_CATALOG
    ] == [
        (
            "2025-11-18",
            SourceAnnotationType.EPSS_SOURCE_SCORE_SHIFT,
            "EPSS 소스 점수 대규모 변동일",
            "EPSS 점수가 10%p 이상 증가한 CVE가 2,677개로 확인되어, "
            "후보가 평소보다 많이 발생했을 가능성이 있는 날짜입니다.",
            "https://expel.com/blog/patch-tuesday-december-2025-expels-version/",
        ),
        (
            "2026-06-15",
            SourceAnnotationType.EPSS_MODEL_TRANSITION,
            "EPSS 모델 v5 전환일",
            "FIRST가 공지한 EPSS v5 모델 전환일로, 모델 변경 영향에 따라 "
            "후보가 급증했을 가능성이 있는 날짜입니다.",
            "https://www.first.org/epss/data",
        ),
        (
            "2026-06-16",
            SourceAnnotationType.EPSS_MODEL_TRANSITION_AFTEREFFECT,
            "EPSS 모델 전환 직후 영향일",
            "FIRST가 공지한 EPSS v5 모델 전환일 직후 날짜로, 모델 변경 영향이 "
            "일부 이어져 후보가 증가했을 가능성이 있습니다.",
            "https://www.first.org/epss/data",
        ),
    ]


def test_lookup_normalizes_observed_at_to_utc_date() -> None:
    korea_time = datetime(
        2026,
        6,
        16,
        8,
        30,
        tzinfo=timezone(timedelta(hours=9)),
    )

    annotations = annotations_for_observed_at(korea_time)

    assert len(annotations) == 1
    assert annotations[0].snapshot_date.isoformat() == "2026-06-15"
    assert annotations[0].annotation_type is SourceAnnotationType.EPSS_MODEL_TRANSITION


@pytest.mark.parametrize(
    "observed_at",
    [
        datetime(2025, 11, 17, tzinfo=UTC),
        datetime(2025, 11, 19, tzinfo=UTC),
        datetime(2025, 4, 20, tzinfo=UTC),
        datetime(2025, 12, 18, tzinfo=UTC),
        None,
    ],
)
def test_lookup_returns_no_user_annotation_for_other_dates(
    observed_at: datetime | None,
) -> None:
    assert annotations_for_observed_at(observed_at) == ()
