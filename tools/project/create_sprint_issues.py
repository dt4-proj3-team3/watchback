#!/usr/bin/env python3
"""검토된 YAML에서 GitHub Parent/Sub-issue를 계획하거나 생성한다."""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
TEAMS_PATH = ROOT / ".github" / "teams.yml"


def run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"명령 실패: {' '.join(command)}\n{result.stderr.strip()}")
    return result.stdout.strip()


def repository() -> str:
    repo = os.environ.get("GH_REPO")
    if repo:
        return repo
    url = run(["git", "config", "--get", "remote.origin.url"])
    if url.startswith("git@github.com:"):
        return url.removeprefix("git@github.com:").removesuffix(".git")
    if "github.com/" in url:
        return url.split("github.com/", 1)[1].removesuffix(".git")
    raise RuntimeError("GitHub origin을 찾지 못했습니다. GH_REPO=owner/repo를 지정하세요.")


def ensure_label(repo: str, label: str) -> None:
    names = {item["name"] for item in json.loads(run(["gh", "label", "list", "--repo", repo, "--json", "name"]))}
    if label not in names:
        run(["gh", "label", "create", label, "--repo", repo, "--color", "0075ca"])


def create_issue(repo: str, title: str, body: str, labels: list[str], assignee: str | None) -> int:
    command = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
    for label in labels:
        command.extend(["--label", label])
    if assignee:
        command.extend(["--assignee", assignee])
    return int(run(command).rstrip("/").split("/")[-1])


def node_id(repo: str, number: int) -> str:
    owner, name = repo.split("/", 1)
    query = f'query={{repository(owner:"{owner}",name:"{name}"){{issue(number:{number}){{id}}}}}}'
    data = json.loads(run(["gh", "api", "graphql", "-f", f"query={query}"]))
    return data["data"]["repository"]["issue"]["id"]


def link_sub_issue(parent_id: str, child_id: str) -> None:
    mutation = f'mutation={{addSubIssue(input:{{issueId:"{parent_id}",subIssueId:"{child_id}"}}){{issue{{number}}}}}}'
    run(["gh", "api", "graphql", "-f", f"query={mutation}"])


def required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}은 비어 있지 않은 문자열이어야 합니다.")
    return value.strip()


def validate_issue(issue: Any, teams: dict[str, Any], field: str, default_priority: str | None = None) -> dict[str, Any]:
    if not isinstance(issue, dict):
        raise ValueError(f"{field}은 객체여야 합니다.")

    priority = required_text(issue.get("priority", default_priority), f"{field}.priority").lower()
    priorities = {"p0", "p1", "p2"}
    if priority not in priorities:
        raise ValueError(f"지원하지 않는 {field}.priority: {priority}")

    team = required_text(issue.get("team"), f"{field}.team").upper()
    if team not in teams:
        raise ValueError(f"지원하지 않는 {field}.team: {team}")

    assignee = issue.get("assignee")
    if assignee is not None:
        assignee = required_text(assignee, f"{field}.assignee")

    return {
        "title": required_text(issue.get("title"), f"{field}.title"),
        "team": team,
        "priority": priority,
        "body": required_text(issue.get("body"), f"{field}.body"),
        "assignee": assignee,
    }


def load_plan(path: str) -> dict[str, Any]:
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Sprint YAML 최상위 값은 객체여야 합니다.")

    teams_config = yaml.safe_load(TEAMS_PATH.read_text(encoding="utf-8"))
    if not isinstance(teams_config, dict) or not isinstance(teams_config.get("teams"), dict):
        raise ValueError(f"팀 설정이 올바르지 않습니다: {TEAMS_PATH}")
    teams = teams_config["teams"]

    sprint = config.get("sprint")
    if not isinstance(sprint, dict):
        raise ValueError("sprint는 객체여야 합니다.")
    sprint_name = required_text(sprint.get("name"), "sprint.name")
    sprint_label = required_text(sprint.get("label"), "sprint.label")

    issues = config.get("issues")
    if not isinstance(issues, list) or not issues:
        raise ValueError("issues는 한 개 이상의 이슈를 포함한 목록이어야 합니다.")

    planned_issues = []
    titles = set()
    for index, issue in enumerate(issues):
        field = f"issues[{index}]"
        parent = validate_issue(issue, teams, field)
        sub_issues = issue.get("sub_issues", [])
        if not isinstance(sub_issues, list):
            raise ValueError(f"{field}.sub_issues는 목록이어야 합니다.")
        parent["sub_issues"] = [
            validate_issue(sub_issue, teams, f"{field}.sub_issues[{sub_index}]", parent["priority"])
            for sub_index, sub_issue in enumerate(sub_issues)
        ]
        for item in [parent, *parent["sub_issues"]]:
            normalized_title = item["title"].casefold()
            if normalized_title in titles:
                raise ValueError(f"YAML 안에 중복된 이슈 제목이 있습니다: {item['title']}")
            titles.add(normalized_title)
        planned_issues.append(parent)

    return {"sprint": {"name": sprint_name, "label": sprint_label}, "issues": planned_issues}


def issue_title(issue: dict[str, Any]) -> str:
    return f"[{issue['team']}][{issue['priority'].upper()}] {issue['title']}"


def issue_labels(issue: dict[str, Any], sprint_label: str) -> list[str]:
    return ["task", sprint_label, f"team:{issue['team'].lower()}", f"priority:{issue['priority']}"]


def print_plan(plan: dict[str, Any]) -> None:
    sprint = plan["sprint"]
    print(f"Sprint: {sprint['name']} ({sprint['label']})")
    for parent in plan["issues"]:
        print(f"[Parent] {issue_title(parent)}")
        print(f"  labels: {', '.join(issue_labels(parent, sprint['label']))}")
        if parent["assignee"]:
            print(f"  assignee: {parent['assignee']}")
        for child in parent["sub_issues"]:
            print(f"  [Sub] {issue_title(child)}")
            print(f"    labels: {', '.join(issue_labels(child, sprint['label']))}")
            if child["assignee"]:
                print(f"    assignee: {child['assignee']}")


def create_plan(plan: dict[str, Any]) -> None:
    repo = repository()
    sprint_label = plan["sprint"]["label"]

    for issue in plan["issues"]:
        labels = issue_labels(issue, sprint_label)
        for label in labels:
            ensure_label(repo, label)
        parent = create_issue(repo, issue_title(issue), issue["body"], labels, issue["assignee"])
        parent_id = node_id(repo, parent)
        print(f"Parent #{parent}")

        for child in issue["sub_issues"]:
            child_labels = issue_labels(child, sprint_label)
            for label in child_labels:
                ensure_label(repo, label)
            number = create_issue(repo, issue_title(child), child["body"], child_labels, child["assignee"])
            link_sub_issue(parent_id, node_id(repo, number))
            print(f"  Sub #{number}")
            time.sleep(0.5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="Sprint 이슈 YAML 경로")
    parser.add_argument("--dry-run", action="store_true", help="GitHub를 변경하지 않고 생성 계획만 출력")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sprint_plan = load_plan(args.config)
    if args.dry_run:
        print_plan(sprint_plan)
    else:
        create_plan(sprint_plan)
