from __future__ import annotations

from typing import Any

import pytest

from watchback_backend.ai_agent.azure_openai import (
    AzureOpenAIRequestError,
    AzureOpenAIResponsesClient,
    AzureOpenAISettings,
)


class FakeTransport:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.request: dict[str, Any] | None = None

    def post(self, **request: Any) -> dict[str, Any]:
        self.request = request
        return self.response


def test_responses_client_uses_v1_endpoint_entra_token_and_disables_storage() -> None:
    transport = FakeTransport(
        {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "근거 답변 [S1]"}],
                }
            ]
        }
    )
    client = AzureOpenAIResponsesClient(
        AzureOpenAISettings(
            endpoint="https://oai-watchback-dev.example.azure.com/",
            timeout_seconds=12,
        ),
        access_token_provider=lambda: "entra-token",
        transport=transport,
    )

    result = client.respond(instructions="근거만 사용", input_text="질문")

    assert result == "근거 답변 [S1]"
    assert transport.request == {
        "url": "https://oai-watchback-dev.example.azure.com/openai/v1/responses",
        "headers": {
            "Authorization": "Bearer entra-token",
            "Content-Type": "application/json",
        },
        "payload": {
            "model": "gpt-5.6-luna",
            "instructions": "근거만 사용",
            "input": "질문",
            "store": False,
            "reasoning": {"effort": "low"},
            "max_output_tokens": 1200,
        },
        "timeout_seconds": 12,
    }


def test_responses_client_rejects_missing_output_text() -> None:
    client = AzureOpenAIResponsesClient(
        AzureOpenAISettings(endpoint="https://oai-watchback-dev.example.azure.com"),
        access_token_provider=lambda: "entra-token",
        transport=FakeTransport({"output": []}),
    )

    with pytest.raises(AzureOpenAIRequestError, match="출력 텍스트"):
        client.respond(instructions="근거만 사용", input_text="질문")


@pytest.mark.parametrize(
    "endpoint",
    ["http://insecure.example.com", "not-a-url", ""],
)
def test_responses_client_requires_https_endpoint(endpoint: str) -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        AzureOpenAISettings(endpoint=endpoint)
