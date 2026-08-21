from __future__ import annotations

import email.utils
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import ValidationError

from .config import GITHUB_API_VERSION
from .errors import ContractError, GitHubRequestError
from .models import AlertPayload, RepositoryPayload


RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
MAX_PAGES = 100
MAX_WAIT_SECONDS = 300.0


class GitHubClient:
    def __init__(
        self,
        token: str,
        *,
        api_url: str,
        transport: httpx.BaseTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._sleeper = sleeper
        self._now = now
        self._client = httpx.Client(
            base_url=api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
                "User-Agent": "watchback-dependabot-sync",
            },
            timeout=httpx.Timeout(30.0, connect=10.0, write=10.0, pool=10.0),
            transport=transport,
            follow_redirects=False,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _retry_delay(self, response: httpx.Response | None, attempt: int) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return max(0.0, float(retry_after))
                except ValueError:
                    parsed = email.utils.parsedate_to_datetime(retry_after)
                    return max(0.0, parsed.timestamp() - self._now())
            reset = response.headers.get("X-RateLimit-Reset")
            if reset:
                return max(0.0, float(reset) - self._now())
        return float(2 ** (attempt - 1))

    @staticmethod
    def _is_rate_limit(response: httpx.Response) -> bool:
        return response.status_code == 403 and (
            response.headers.get("X-RateLimit-Remaining") == "0"
            or "X-RateLimit-Reset" in response.headers
            or "Retry-After" in response.headers
        )

    def _get(self, url: str, *, context: dict[str, Any]) -> httpx.Response:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            response: httpx.Response | None = None
            try:
                response = self._client.get(url)
                if response.is_success:
                    return response
                retryable = (
                    response.status_code in RETRYABLE_STATUSES
                    or self._is_rate_limit(response)
                )
                if not retryable:
                    raise GitHubRequestError(
                        "github_http_error",
                        "GitHub API 요청이 거부되었습니다.",
                        context={**context, "http_status": response.status_code},
                    )
            except httpx.TransportError as exc:
                if attempt == MAX_ATTEMPTS:
                    raise GitHubRequestError(
                        "github_transport_error",
                        "GitHub API 연결에 실패했습니다.",
                        context=context,
                    ) from exc

            if attempt == MAX_ATTEMPTS:
                raise GitHubRequestError(
                    "github_retry_exhausted",
                    "GitHub API 재시도 횟수를 초과했습니다.",
                    context={
                        **context,
                        **(
                            {"http_status": response.status_code}
                            if response is not None
                            else {}
                        ),
                    },
                )
            delay = self._retry_delay(response, attempt)
            if delay > MAX_WAIT_SECONDS:
                retry_at = datetime.fromtimestamp(self._now() + delay, tz=UTC).isoformat()
                raise GitHubRequestError(
                    "github_retry_wait_exceeded",
                    "GitHub API 재시도 대기시간이 제한을 초과했습니다.",
                    context={
                        **context,
                        "retry_at": retry_at,
                        **(
                            {"http_status": response.status_code}
                            if response is not None
                            else {}
                        ),
                    },
                )
            self._sleeper(delay)
        raise AssertionError("unreachable")

    def get_repository(self, full_name: str) -> RepositoryPayload:
        response = self._get(f"/repos/{full_name}", context={"repository": full_name})
        try:
            value = response.json()
            if not isinstance(value, dict):
                raise TypeError("repository response is not an object")
            return RepositoryPayload.model_validate(value)
        except (ValueError, TypeError, ValidationError) as exc:
            raise ContractError(
                "invalid_repository_payload",
                "GitHub 저장소 응답이 계약과 다릅니다.",
                context={"repository": full_name},
            ) from exc

    def get_alerts(self, full_name: str) -> tuple[list[AlertPayload], int]:
        url: str | None = f"/repos/{full_name}/dependabot/alerts?per_page=100"
        visited: set[str] = set()
        alerts: list[AlertPayload] = []
        numbers: set[int] = set()
        page = 0

        while url is not None:
            page += 1
            if page > MAX_PAGES:
                raise ContractError(
                    "page_limit_exceeded",
                    "Dependabot Alert 페이지 제한을 초과했습니다.",
                    context={"repository": full_name, "page": page},
                )
            resolved_url = self._client.base_url.join(url)
            if (
                resolved_url.scheme != self._client.base_url.scheme
                or resolved_url.host != self._client.base_url.host
                or resolved_url.port != self._client.base_url.port
            ):
                raise ContractError(
                    "invalid_next_link_origin",
                    "Dependabot Alert next Link의 출처가 GitHub API와 다릅니다.",
                    context={"repository": full_name, "page": page},
                )
            absolute_url = str(resolved_url)
            if absolute_url in visited:
                raise ContractError(
                    "repeated_next_link",
                    "Dependabot Alert next Link가 반복되었습니다.",
                    context={"repository": full_name, "page": page},
                )
            visited.add(absolute_url)
            response = self._get(
                url,
                context={"repository": full_name, "page": page},
            )
            try:
                raw_items = response.json()
                if not isinstance(raw_items, list):
                    raise TypeError("alerts response is not an array")
                page_items = [AlertPayload.model_validate(item) for item in raw_items]
            except (ValueError, TypeError, ValidationError) as exc:
                raise ContractError(
                    "invalid_alert_payload",
                    "Dependabot Alert 응답이 계약과 다릅니다.",
                    context={"repository": full_name, "page": page},
                ) from exc
            for alert in page_items:
                if alert.number in numbers:
                    raise ContractError(
                        "duplicate_alert_number",
                        "페이지 간 Alert 번호가 중복되었습니다.",
                        context={
                            "repository": full_name,
                            "page": page,
                            "alert_number": alert.number,
                        },
                    )
                numbers.add(alert.number)
                alerts.append(alert)
            next_link = response.links.get("next")
            url = next_link.get("url") if next_link else None

        return alerts, page
