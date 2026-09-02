from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.dialects import postgresql

from watchback_backend.api.service import RequestContext
from watchback_backend.db.models import DependencyVersionSnapshot
from watchback_backend.remediation.service import (
    RemediationSourceRow,
    _load_source_rows,
    build_remediation_groups,
)


NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)
ORG_ID = UUID("10000000-0000-0000-0000-000000000001")


def source_row(
    number: int,
    *,
    repository_number: int = 1,
    case_number: int | None = None,
    candidate_number: int | None = None,
    package_name: str = "vite",
    ecosystem: str = "npm",
    manifest_path: str = "package-lock.json",
    cve_id: str | None = None,
    priority: str = "P1",
    case_status: str = "open",
    alert_state: str = "open",
    fixed_version: str | None = "6.4.2",
) -> RemediationSourceRow:
    case_number = case_number or number
    candidate_number = candidate_number or case_number
    cve_id = cve_id or f"CVE-2026-{case_number:04d}"
    return RemediationSourceRow(
        organization_id=ORG_ID,
        case_id=UUID(f"20000000-0000-0000-0000-{case_number:012d}"),
        case_status=case_status,
        case_opened_at=NOW - timedelta(days=case_number),
        repository_id=UUID(
            f"30000000-0000-0000-0000-{repository_number:012d}"
        ),
        repository_full_name=f"example/repo-{repository_number}",
        repository_display_name=f"novalink/repo-{repository_number}",
        repository_importance="high",
        alert_id=UUID(f"40000000-0000-0000-0000-{number:012d}"),
        github_alert_number=number,
        alert_state=alert_state,
        package_name=package_name,
        ecosystem=ecosystem,
        manifest_path=manifest_path,
        vulnerable_version_range="< 6.4.2",
        first_patched_version=fixed_version,
        alert_html_url=f"https://github.com/example/repo-{repository_number}/security/dependabot/{number}",
        alert_github_updated_at=NOW + timedelta(minutes=number),
        ghsa_id=f"GHSA-aaaa-bbbb-{case_number:04d}",
        cve_id=cve_id,
        advisory_summary=f"Advisory {cve_id}",
        advisory_severity="high",
        candidate_id=UUID(
            f"50000000-0000-0000-0000-{candidate_number:012d}"
        ),
        candidate_priority=priority,
        candidate_change_type="KEV_NEW" if priority == "P0" else "EPSS_RISE",
        candidate_selected_at=NOW - timedelta(days=case_number),
    )


def test_groups_same_package_across_repositories_and_preserves_targets() -> None:
    response = build_remediation_groups(
        [
            source_row(1, repository_number=1, priority="P2"),
            source_row(2, repository_number=2, priority="P0"),
        ]
    )

    assert response.total == 1
    group = response.items[0]
    assert group.package_name == "vite"
    assert group.priority == "P0"
    assert group.repository_count == 2
    assert group.cve_count == 2
    assert group.registered_at == NOW - timedelta(days=2)
    assert len(group.targets) == 2
    assert {target.repository.full_name for target in group.targets} == {
        "example/repo-1",
        "example/repo-2",
    }


def test_manifest_targets_remain_separate_without_duplicating_group_alerts() -> None:
    rows = [
        source_row(1, case_number=1, manifest_path="package-lock.json"),
        source_row(2, case_number=1, manifest_path="fixtures/package-lock.json"),
    ]
    response = build_remediation_groups(rows + [rows[0]])

    group = response.items[0]
    assert len(group.targets) == 2
    assert group.github_alert_counts.open == 2
    assert group.cve_count == 1
    assert len(group.vulnerabilities) == 1
    assert set(group.vulnerabilities[0].alert_ids) == {
        rows[0].alert_id,
        rows[1].alert_id,
    }


def test_removed_manifest_without_open_alert_is_hidden_from_action_targets() -> None:
    active = source_row(1, manifest_path="package-lock.json")
    removed = source_row(
        2,
        case_number=2,
        manifest_path="transitive-override/package-lock.json",
        case_status="resolved",
        alert_state="fixed",
    )
    removed_snapshot = DependencyVersionSnapshot(
        id=UUID("70000000-0000-0000-0000-000000000001"),
        organization_id=ORG_ID,
        repository_id=removed.repository_id,
        manifest_path=removed.manifest_path,
        commit_sha="a" * 40,
        ecosystem="npm",
        package_name="vite",
        resolved_versions=[],
        status="unavailable",
        reason="lockfile_not_found",
        source_path=None,
        source_blob_sha=None,
        observed_at=NOW,
    )

    group = build_remediation_groups(
        [active, removed],
        versions_by_target={
            (
                removed.repository_id,
                removed.manifest_path,
                removed.ecosystem,
                removed.package_name,
            ): removed_snapshot
        },
    ).items[0]

    assert [target.project_root for target in group.targets] == [""]
    assert group.github_alert_counts.open == 1
    assert group.github_alert_counts.fixed == 1


def test_manifest_and_lockfile_in_same_project_are_one_action_target() -> None:
    rows = [
        source_row(
            1,
            case_number=1,
            ecosystem="pip",
            package_name="Django",
            manifest_path="pyproject.toml",
        ),
        source_row(
            2,
            case_number=1,
            ecosystem="pip",
            package_name="django",
            manifest_path="uv.lock",
        ),
    ]

    target = build_remediation_groups(rows).items[0].targets[0]

    assert target.project_root == ""
    assert target.manifest_paths == ["pyproject.toml", "uv.lock"]
    assert target.github_alert_counts.open == 2
    assert {alert.id for alert in target.alerts} == {
        rows[0].alert_id,
        rows[1].alert_id,
    }


def test_watchback_review_status_uses_open_accepted_and_resolved_precedence() -> None:
    accepted = source_row(1, case_status="resolved", alert_state="open")
    response = build_remediation_groups(
        [
            accepted,
            source_row(
                2,
                case_number=2,
                case_status="open",
                alert_state="fixed",
            ),
        ],
        accepted_target_keys={(accepted.alert_id, accepted.candidate_id)},
    )

    group = response.items[0]
    assert group.watchback_status == "accepted"
    assert group.github_alert_counts.open == 1
    assert group.github_alert_counts.fixed == 1
    assert {
        vulnerability.watchback_status
        for vulnerability in group.vulnerabilities
    } == {"accepted", "resolved"}


def test_review_case_resolution_does_not_hide_an_open_github_alert() -> None:
    group = build_remediation_groups(
        [source_row(1, case_status="resolved", alert_state="open")]
    ).items[0]

    assert group.watchback_status == "needs_review"
    assert group.github_alert_counts.open == 1
    assert group.github_alert_counts.fixed == 0


def test_new_candidate_reopens_an_accepted_alert() -> None:
    current = source_row(1, candidate_number=2)

    group = build_remediation_groups(
        [current],
        accepted_target_keys={
            (
                current.alert_id,
                UUID("50000000-0000-0000-0000-000000000001"),
            )
        },
    ).items[0]

    assert group.watchback_status == "needs_review"


def test_group_priority_uses_open_alert_scope_before_fixed_history() -> None:
    group = build_remediation_groups(
        [
            source_row(1, priority="P0", alert_state="fixed"),
            source_row(2, case_number=2, priority="P2", alert_state="open"),
        ]
    ).items[0]

    assert group.priority == "P2"


def test_groups_are_split_by_ecosystem_and_package() -> None:
    response = build_remediation_groups(
        [
            source_row(1, package_name="vite", ecosystem="npm"),
            source_row(2, package_name="litellm", ecosystem="pip"),
            source_row(3, package_name="vite", ecosystem="pip"),
        ]
    )

    assert response.total == 3
    assert {(item.ecosystem, item.package_name) for item in response.items} == {
        ("npm", "vite"),
        ("pip", "litellm"),
        ("pip", "vite"),
    }


def test_pip_package_names_use_pep_503_normalization_for_grouping() -> None:
    response = build_remediation_groups(
        [
            source_row(1, package_name="Django", ecosystem="pip"),
            source_row(
                2,
                case_number=2,
                package_name="django",
                ecosystem="pip",
            ),
        ]
    )

    assert response.total == 1
    assert response.items[0].package_name == "django"
    assert response.items[0].github_alert_counts.open == 2


def test_same_cve_across_repositories_is_one_vulnerability_with_all_cases() -> None:
    rows = [
        source_row(1, repository_number=1, case_number=1, cve_id="CVE-2026-0042"),
        source_row(2, repository_number=2, case_number=2, cve_id="CVE-2026-0042"),
    ]

    group = build_remediation_groups(rows).items[0]

    assert group.cve_count == 1
    assert len(group.vulnerabilities) == 1
    assert set(group.vulnerabilities[0].case_ids) == {
        rows[0].case_id,
        rows[1].case_id,
    }
    assert set(group.vulnerabilities[0].alert_ids) == {
        rows[0].alert_id,
        rows[1].alert_id,
    }


def test_fix_versions_are_preserved_without_unsafe_cross_ecosystem_ordering() -> None:
    group = build_remediation_groups(
        [
            source_row(1, fixed_version="6.4.2"),
            source_row(2, case_number=2, fixed_version="15.2.3"),
            source_row(3, case_number=3, fixed_version=None),
        ]
    ).items[0]

    assert group.recommended_fix_versions == ["15.2.3", "6.4.2"]


def test_target_uses_highest_comparable_fix_version() -> None:
    group = build_remediation_groups(
        [
            source_row(1, package_name="litellm", ecosystem="pip", fixed_version="1.83.0"),
            source_row(2, case_number=2, package_name="litellm", ecosystem="pip", fixed_version="1.83.7"),
        ]
    ).items[0]

    assert len(group.targets) == 1
    assert group.targets[0].recommended_fix_versions == ["1.83.0", "1.83.7"]
    assert group.targets[0].representative_patched_version == "1.83.7"


def test_source_query_compiles_for_postgresql() -> None:
    class EmptyResult:
        def mappings(self) -> list[dict[str, object]]:
            return []

    class CompileOnlySession:
        def execute(self, statement: object) -> EmptyResult:
            statement.compile(dialect=postgresql.dialect())
            return EmptyResult()

    result = _load_source_rows(
        CompileOnlySession(),  # type: ignore[arg-type]
        RequestContext(
            organization_id=ORG_ID,
            user_id=UUID("60000000-0000-0000-0000-000000000001"),
            display_name="Reviewer",
        ),
    )

    assert result == []
