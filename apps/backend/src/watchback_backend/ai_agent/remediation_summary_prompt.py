from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


PROMPT_VERSION = "remediation-summary-v7"

REMEDIATION_SUMMARY_PROMPT = """패키지 조치 상세 상단에 표시할 AI 요약을 작성하세요.

반드시 아래 세 줄만 출력하세요.
핵심 위험: <한두 문장>
권장 조치: <한 문장>
해석 주의: <한 문장 또는 없음>

작성 규칙:
- 보안 담당자가 바로 이해할 수 있는 사용자 용어만 사용합니다.
- DS, P0, P1, P2, P3, Candidate, 후보 선정, 내부 점수 같은 내부 용어를 쓰지 않습니다.
- CVE 식별자는 바로 아래 표에 있으므로 본문에서 반복하지 않습니다.
- 패키지명은 화면 상단에 있으므로 핵심 위험과 권장 조치 본문에서 반복하지 않습니다.
- `요약 대상 데이터`에 지정된 가장 중요한 취약점 하나만 설명하고 다른 취약점 내용을 나열하지 않습니다.
- 핵심 위험에는 Advisory 설명에서 확인되는 취약점 유형 또는 영향, Watchback이 포착한 핵심 변화와 관찰 날짜를 포함합니다. 취약점 유형부터 문장을 시작합니다.
- Advisory 근거로 취약점 유형을 특정할 수 없으면 '보안 취약점'이라고 쓰고 추측하지 않습니다.
- KEV 변화는 'M월 D일 CISA가 실제 악용이 확인된 취약점으로 KEV에 새로 등재했다'고 CISA를 판단 주체로 명확히 설명합니다.
- 핵심 위험 본문에 'Watchback 근거만으로 실제 악용 여부를 확정할 수 없다'는 일반 안내를 덧붙이지 않습니다. 해당 안내는 화면의 공통 안내에서 제공합니다.
- EPSS 점수는 '향후 30일 악용 가능성이 이전 N%에서 현재 N%로 상승했다'고 실제 수치를 포함합니다.
- EPSS percentile은 점수와 혼동하지 말고 '전체 CVE 중 상위 N%'라고 설명합니다. N은 (1-current percentile)×100입니다.
- 같은 관찰일의 EPSS 점수와 percentile은 한 문장에 함께 설명할 수 있습니다. 날짜나 사건이 다르면 문장을 분리합니다.
- 날짜는 Evidence의 관찰 시각을 사용하며 Batch 기준일이나 후보 선정 시각으로 대체하지 않습니다.
- 날짜는 연도를 제외하고 'M월 D일' 형식으로 씁니다.
- EPSS 백분율은 소수점 둘째 자리까지 반올림해 표시합니다.
- 아래 `요약 대상 데이터`에 적힌 날짜와 표시값만 사용합니다. 다른 근거에 보이는 시각이나 원시 소수로 날짜·백분율을 새로 계산하지 않습니다.
- 권장 조치는 정확히 '{권장 수정 버전} 이상으로 업데이트한 뒤 애플리케이션 테스트를 수행하세요.' 형식으로 씁니다. 패키지명과 '대표', '후보'라는 표현은 넣지 않습니다.
- 실제 해결, 패치 안전성, 위험 수용 필요성을 확정하지 않습니다.
- `EPSS 모델·소스 변동 주석`이 있으면 해석 주의에 'M월 D일 EPSS 모델·소스 변동과 겹쳐 해당 변화에 소스 변동 영향이 함께 반영됐을 수 있습니다.'라고 씁니다.
- `EPSS 모델·소스 변동 주석`이 없으면 해석 주의에 근거번호 없이 정확히 '없음'이라고 씁니다.
- 각 문장 끝에는 근거 [S번호]를 붙입니다.
"""


def build_remediation_summary_prompt(group) -> str:
    lines = [
        f"- 패키지명: {group.package_name}",
        f"- 권장 수정 버전: {group.representative_patched_version or '확인 불가'}",
    ]
    primary_vulnerabilities = _primary_vulnerabilities(group.vulnerabilities)
    for vulnerability in primary_vulnerabilities:
        lines.append(
            f"- Advisory: {vulnerability.advisory_summary}"
        )
        candidate = _primary_candidate(vulnerability.candidates)
        evidence_items = _primary_evidence(candidate.evidence if candidate else [])
        for evidence in evidence_items:
            fact = _evidence_fact(evidence)
            if fact:
                lines.append(
                    f"- Evidence 관찰일 {_month_day(evidence.observed_at)}: {fact}"
                )
        evidence_dates = {evidence.observed_at.date() for evidence in evidence_items}
        if candidate is not None:
            for delivery in getattr(candidate, "deliveries", []):
                for annotation in getattr(delivery, "source_annotations", []):
                    if annotation.snapshot_date not in evidence_dates:
                        continue
                    lines.append(
                        "- EPSS 모델·소스 변동 주석 "
                        f"{_month_day(annotation.snapshot_date)}: "
                        f"{annotation.label} - {annotation.description}"
                    )
    return f"{REMEDIATION_SUMMARY_PROMPT}\n\n요약 대상 데이터:\n" + "\n".join(lines)


def _primary_vulnerabilities(vulnerabilities) -> list:
    if not vulnerabilities:
        return []
    priority_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    change_rank = {
        "kev_new": 0,
        "kev_added": 0,
        "epss_top5_entry_d30": 1,
        "epss_rise_d30": 2,
    }

    def rank(item) -> tuple[int, int, str]:
        candidate_changes = [
            candidate.change_type for candidate in item.candidates
        ] or [item.change_type]
        return (
            priority_rank.get(str(item.priority), 99),
            min((change_rank.get(change, 99) for change in candidate_changes), default=99),
            item.cve_id,
        )

    return [min(vulnerabilities, key=rank)]


def _primary_candidate(candidates):
    if not candidates:
        return None
    priority_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    change_rank = {
        "kev_new": 0,
        "kev_added": 0,
        "epss_top5_entry_d30": 1,
        "epss_rise_d30": 2,
    }
    return min(
        candidates,
        key=lambda item: (
            priority_rank.get(str(getattr(item, "priority", "")), 99),
            change_rank.get(getattr(item, "change_type", ""), 99),
            -getattr(item, "selected_at", datetime.min.replace(tzinfo=UTC)).timestamp(),
            str(getattr(item, "id", "")),
        ),
    )


def _primary_evidence(evidence_items) -> list:
    if not evidence_items:
        return []
    latest_date = max(item.observed_at.date() for item in evidence_items)
    return sorted(
        (item for item in evidence_items if item.observed_at.date() == latest_date),
        key=lambda item: (item.observed_at, str(item.id)),
    )


def _evidence_fact(evidence) -> str | None:
    if evidence.signal == "kev" and evidence.current_value == "true":
        return "CISA KEV 신규 등재"
    if evidence.signal == "epss_score_d30":
        previous = _percent(evidence.previous_value)
        current = _percent(evidence.current_value)
        if previous is not None and current is not None:
            return f"향후 30일 악용 가능성 {previous}% → {current}%"
    if evidence.signal == "epss_percentile_d30":
        previous = _top_percent(evidence.previous_value)
        current = _top_percent(evidence.current_value)
        if current is not None:
            before = f"상위 {previous}% → " if previous is not None else ""
            return f"전체 CVE 내 EPSS 순위 {before}상위 {current}%"
    return None


def _percent(value: str | None) -> str | None:
    try:
        return _decimal_text(Decimal(str(value)) * 100)
    except (InvalidOperation, TypeError):
        return None


def _top_percent(value: str | None) -> str | None:
    try:
        return _decimal_text((Decimal("1") - Decimal(str(value))) * 100)
    except (InvalidOperation, TypeError):
        return None


def _decimal_text(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(rounded, "f").rstrip("0").rstrip(".")


def _month_day(value) -> str:
    return f"{value.month}월 {value.day}일"


def normalize_summary_display_text(text: str) -> str:
    without_year = re.sub(r"\b\d{4}년\s*(\d{1,2}월\s*\d{1,2}일)", r"\1", text)
    attributed_kev_wording = without_year.replace(
        "CISA KEV에 새로 등재되어 실제 악용 사례가 확인되었다는 의미지만 "
        "Watchback 근거만으로 실제 악용 여부를 확정할 수 없습니다.",
        "CISA가 실제 악용이 확인된 취약점으로 KEV에 새로 등재했습니다.",
    )
    direct_wording = attributed_kev_wording.replace(
        "확인되었다는 의미입니다.",
        "확인되었습니다.",
    )

    def round_percent(match: re.Match[str]) -> str:
        value = Decimal(match.group(1))
        return f"{_decimal_text(value)}%"

    return re.sub(r"(?<![\d.])(\d+\.\d{3,})%", round_percent, direct_wording)


def remove_leading_package_reference(text: str, package_name: str) -> str:
    escaped_package = re.escape(package_name)
    optional_version = r"(?:\s+v?\d+(?:\.\d+)*(?:[\w.+-]*))?"
    particle = r"(?:(?:패키지)?(?:에서|에는|은|는|의)|패키지(?:를|을)|을|를)"
    pattern = rf"^\s*`?{escaped_package}`?{optional_version}\s*{particle}\s*"
    without_leading_reference = re.sub(
        pattern, "", text, count=1, flags=re.IGNORECASE
    ).strip()
    repeated_disclaimer = (
        rf"\s*`?{escaped_package}`?에\s+확인되었다는 의미지만\s+"
        r"Watchback 근거만으로 실제 악용 여부를 확정할 수 없습니다\."
    )
    return re.sub(
        repeated_disclaimer,
        "",
        without_leading_reference,
        flags=re.IGNORECASE,
    ).strip()


@dataclass(frozen=True)
class ParsedRemediationSummary:
    risk_summary: str
    action_summary: str
    interpretation_note: str | None


def parse_remediation_summary(value: str) -> ParsedRemediationSummary:
    normalized = value.replace("**", "").strip()
    match = re.search(
        r"핵심 위험\s*[:：]\s*([\s\S]*?)\s*권장 조치\s*[:：]\s*([\s\S]+)",
        normalized,
    )
    if match is None:
        raise ValueError("AI 요약이 핵심 위험/권장 조치 형식을 따르지 않았습니다.")

    def clean(text: str) -> str:
        without_citations = re.sub(r"\[S[1-9][0-9]*\]", "", text)
        normalized_spacing = re.sub(r"\s+", " ", without_citations).strip()
        cleaned = re.sub(r"\s+([.!?,])", r"\1", normalized_spacing)
        return cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."

    risk_summary = clean(match.group(1))
    action_text = match.group(2)
    interpretation_match = re.search(
        r"\s*해석 주의\s*[:：]\s*([\s\S]+)$",
        action_text,
    )
    interpretation_note = None
    if interpretation_match is not None:
        action_text = action_text[:interpretation_match.start()]
        note_text = interpretation_match.group(1).strip()
        note_without_citations = re.sub(r"\[S[1-9][0-9]*\]", "", note_text).strip()
        if note_without_citations.rstrip(".") != "없음":
            interpretation_note = clean(note_text)
    action_summary = clean(action_text)
    if not risk_summary or not action_summary:
        raise ValueError("AI 요약의 핵심 위험 또는 권장 조치가 비어 있습니다.")
    if re.search(r"\b(?:DS|P[0-3]|Candidate)\b|후보 선정|내부 점수|대표 (?:권장 )?수정 버전", normalized, re.IGNORECASE):
        raise ValueError("AI 요약에 사용자에게 노출하면 안 되는 내부 용어가 포함되었습니다.")
    return ParsedRemediationSummary(risk_summary, action_summary, interpretation_note)
