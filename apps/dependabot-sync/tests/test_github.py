from __future__ import annotations

import base64
import json

import httpx
import pytest

from watchback_dependabot_sync.errors import ContractError, GitHubRequestError
from watchback_dependabot_sync.github import GitHubClient


def client(handler, *, sleeps=None, now=lambda: 1000.0):
    return GitHubClient(
        "secret-token",
        api_url="https://api.github.test",
        transport=httpx.MockTransport(handler),
        sleeper=(sleeps.append if sleeps is not None else lambda _: None),
        now=now,
    )


def test_follows_link_header_until_last_page(raw_alerts):
    def handler(request):
        assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"
        if "page=2" in str(request.url):
            return httpx.Response(200, json=raw_alerts[1:])
        return httpx.Response(
            200,
            json=raw_alerts[:1],
            headers={"Link": '<https://api.github.test/alerts?page=2>; rel="next"'},
        )

    with client(handler) as github:
        alerts, pages = github.get_alerts("example/repo")
    assert pages == 2
    assert [item.number for item in alerts] == [1, 2, 3, 4, 5]


def test_repeated_link_is_rejected(raw_alerts):
    next_url = "https://api.github.test/alerts?page=2"

    def handler(request):
        return httpx.Response(200, json=[], headers={"Link": f'<{next_url}>; rel="next"'})

    with client(handler) as github, pytest.raises(ContractError, match="반복"):
        github.get_alerts("example/repo")


def test_external_next_link_is_rejected_before_sending_token(raw_alerts):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json=[],
            headers={"Link": '<https://attacker.example/alerts?page=2>; rel="next"'},
        )

    with client(handler) as github, pytest.raises(ContractError, match="출처"):
        github.get_alerts("example/repo")
    assert calls == 1


def test_non_array_and_duplicate_alert_are_rejected(raw_alerts):
    with client(lambda _: httpx.Response(200, json={"message": "not an array"})) as github:
        with pytest.raises(ContractError):
            github.get_alerts("example/repo")

    with client(lambda _: httpx.Response(200, json=[raw_alerts[0], raw_alerts[0]])) as github:
        with pytest.raises(ContractError, match="중복"):
            github.get_alerts("example/repo")


def test_retry_after_and_transport_errors_are_retried(raw_alerts):
    calls = 0
    sleeps = []

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("token must never be shown", request=request)
        if calls == 2:
            return httpx.Response(503, headers={"Retry-After": "2"})
        return httpx.Response(200, json=[])

    with client(handler, sleeps=sleeps) as github:
        alerts, _ = github.get_alerts("example/repo")
    assert alerts == []
    assert calls == 3
    assert sleeps == [1.0, 2.0]


def test_rate_limit_reset_and_non_retryable_errors(raw_alerts):
    calls = 0
    sleeps = []

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                403,
                headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1005"},
            )
        return httpx.Response(200, json=[])

    with client(handler, sleeps=sleeps) as github:
        github.get_alerts("example/repo")
    assert sleeps == [5.0]

    with client(lambda _: httpx.Response(401, json={"token": "secret-token"})) as github:
        with pytest.raises(GitHubRequestError) as caught:
            github.get_alerts("example/repo")
    rendered = json.dumps(caught.value.context) + str(caught.value)
    assert "secret-token" not in rendered
    assert "token" not in rendered

    calls = 0

    def general_forbidden(request):
        nonlocal calls
        calls += 1
        return httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "10", "X-RateLimit-Reset": "1005"},
        )

    with client(general_forbidden) as github:
        with pytest.raises(GitHubRequestError):
            github.get_alerts("example/repo")
    assert calls == 1


def test_reads_repository_file_at_an_immutable_commit():
    content = base64.b64encode(b'{"lockfileVersion": 3}').decode()

    def handler(request):
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "commit-sha"})
        assert request.url.path.endswith("/contents/apps/web/package-lock.json")
        assert request.url.params["ref"] == "commit-sha"
        return httpx.Response(
            200,
            json={
                "type": "file",
                "sha": "blob-sha",
                "encoding": "base64",
                "content": content,
            },
        )

    with client(handler) as github:
        commit_sha = github.get_commit_sha("example/repo", "main")
        source = github.get_repository_file(
            "example/repo", "apps/web/package-lock.json", ref=commit_sha
        )

    assert commit_sha == "commit-sha"
    assert source is not None
    assert source.blob_sha == "blob-sha"
    assert source.content == '{"lockfileVersion": 3}'


def test_missing_repository_file_returns_none_and_large_file_uses_blob_api():
    calls = []
    blob_content = base64.b64encode(b"large lockfile").decode()

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/contents/missing.lock"):
            return httpx.Response(404)
        if request.url.path.endswith("/contents/large.lock"):
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "sha": "large-blob-sha",
                    "encoding": "none",
                    "content": "",
                },
            )
        if request.url.path.endswith("/git/blobs/large-blob-sha"):
            return httpx.Response(
                200, json={"encoding": "base64", "content": blob_content}
            )
        raise AssertionError(request.url)

    with client(handler) as github:
        assert github.get_repository_file(
            "example/repo", "missing.lock", ref="commit-sha"
        ) is None
        source = github.get_repository_file(
            "example/repo", "large.lock", ref="commit-sha"
        )

    assert source is not None
    assert source.content == "large lockfile"
    assert calls[-1].endswith("/git/blobs/large-blob-sha")
