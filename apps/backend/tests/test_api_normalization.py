from watchback_backend.api.normalization import (
    normalize_change_type,
    normalize_evidence_signal,
    storage_change_type,
)


def test_normalizes_gold_change_types_to_public_contract() -> None:
    assert normalize_change_type("EPSS_RISE") == "epss_rise_d30"
    assert normalize_change_type("EPSS_TOP5_ENTRY") == "epss_top5_entry_d30"
    assert normalize_change_type("KEV_NEW") == "kev_new"


def test_normalizes_legacy_change_type_aliases() -> None:
    assert normalize_change_type("epss_rise") == "epss_rise_d30"
    assert normalize_change_type("epss_spike") == "epss_rise_d30"
    assert normalize_change_type("kev_added") == "kev_new"


def test_maps_public_filter_to_gold_storage_value() -> None:
    assert storage_change_type("epss_rise_d30") == "EPSS_RISE"
    assert storage_change_type("epss_top5_entry_d30") == "EPSS_TOP5_ENTRY"
    assert storage_change_type("kev_added") == "KEV_NEW"
    assert storage_change_type("kev_new") == "KEV_NEW"


def test_normalizes_gold_evidence_signals() -> None:
    assert normalize_evidence_signal("epss_score") == "epss_score_d30"
    assert normalize_evidence_signal("epss_percentile") == "epss_percentile_d30"
    assert normalize_evidence_signal("kev") == "kev"


def test_unknown_values_are_preserved() -> None:
    assert normalize_change_type("FUTURE_SIGNAL") == "FUTURE_SIGNAL"
    assert storage_change_type("future_signal") == "future_signal"
    assert normalize_evidence_signal("future_metric") == "future_metric"
