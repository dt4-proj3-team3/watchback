"""Gold 저장값과 공개 API enum 사이의 정규화 규칙."""

from __future__ import annotations


_CHANGE_TYPE_TO_API = {
    "EPSS_RISE": "epss_rise_d30",
    "EPSS_TOP5_ENTRY": "epss_top5_entry_d30",
    "KEV_NEW": "kev_new",
}

_CHANGE_TYPE_ALIASES = {
    "epss_rise": "epss_rise_d30",
    "epss_spike": "epss_rise_d30",
    "epss_rise_d30": "epss_rise_d30",
    "epss_top5_entry": "epss_top5_entry_d30",
    "epss_top5_entry_d30": "epss_top5_entry_d30",
    "kev_added": "kev_new",
    "kev_new": "kev_new",
}

_CHANGE_TYPE_TO_STORAGE = {
    "epss_rise_d30": "EPSS_RISE",
    "epss_top5_entry_d30": "EPSS_TOP5_ENTRY",
    "kev_new": "KEV_NEW",
}

_SIGNAL_TO_API = {
    "epss_score": "epss_score_d30",
    "epss_percentile": "epss_percentile_d30",
    "kev": "kev",
}


def normalize_change_type(value: str) -> str:
    """알려진 Gold/legacy 값을 공개 API canonical 값으로 변환한다."""

    stripped = value.strip()
    storage_value = _CHANGE_TYPE_TO_API.get(stripped.upper())
    if storage_value is not None:
        return storage_value
    return _CHANGE_TYPE_ALIASES.get(stripped.lower(), stripped)


def storage_change_type(value: str) -> str:
    """공개 API 필터 값을 Gold 저장값으로 변환한다."""

    canonical = normalize_change_type(value)
    return _CHANGE_TYPE_TO_STORAGE.get(canonical, value.strip())


def normalize_evidence_signal(value: str) -> str:
    """알려진 Gold Evidence 신호를 공개 API canonical 값으로 변환한다."""

    stripped = value.strip()
    return _SIGNAL_TO_API.get(stripped.lower(), stripped)
