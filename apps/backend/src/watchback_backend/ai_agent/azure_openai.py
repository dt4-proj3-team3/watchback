from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class AccessTokenProvider(Protocol):
    def __call__(self) -> str: ...


class JsonTransport(Protocol):
    def post(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]: ...


class UrllibJsonTransport:
    def post(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))


class AzureOpenAIRequestError(RuntimeError):
    """Azure OpenAI 인증·연결·응답 오류를 외부에 노출하지 않는 경계 오류."""


@dataclass(frozen=True)
class AzureOpenAISettings:
    endpoint: str
    deployment: str = "gpt-5.6-luna"
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Azure OpenAI endpoint는 HTTPS URL이어야 합니다.")
        if not self.deployment.strip():
            raise ValueError("Azure OpenAI deployment 이름이 필요합니다.")
        if self.timeout_seconds <= 0:
            raise ValueError("Azure OpenAI timeout은 0보다 커야 합니다.")


class AzureOpenAIResponsesClient:
    def __init__(
        self,
        settings: AzureOpenAISettings,
        access_token_provider: AccessTokenProvider,
        transport: JsonTransport | None = None,
    ) -> None:
        self._settings = settings
        self._access_token_provider = access_token_provider
        self._transport = transport or UrllibJsonTransport()

    @property
    def model(self) -> str:
        return self._settings.deployment

    def respond(self, *, instructions: str, input_text: str) -> str:
        try:
            token = self._access_token_provider()
            response = self._transport.post(
                url=f"{self._settings.endpoint.rstrip('/')}/openai/v1/responses",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                payload={
                    "model": self._settings.deployment,
                    "instructions": instructions,
                    "input": input_text,
                    "store": False,
                    "reasoning": {"effort": "low"},
                    "max_output_tokens": 1200,
                },
                timeout_seconds=self._settings.timeout_seconds,
            )
        except Exception as exc:
            raise AzureOpenAIRequestError(
                "Azure OpenAI 요청에 실패했습니다."
            ) from exc
        text = _response_text(response)
        if not text:
            raise AzureOpenAIRequestError(
                "Azure OpenAI 응답에 출력 텍스트가 없습니다."
            )
        return text


def _response_text(response: dict[str, Any]) -> str:
    texts: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict) or content.get("type") != "output_text":
                continue
            text = content.get("text")
            if isinstance(text, str):
                texts.append(text)
    return "\n".join(texts).strip()
