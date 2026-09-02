from __future__ import annotations

import os
from functools import lru_cache

from watchback_backend.ai_agent.azure_openai import (
    AzureOpenAIResponsesClient,
    AzureOpenAISettings,
)
from watchback_backend.ai_agent.service import AgentService
from watchback_backend.api.service import ServiceError


AZURE_OPENAI_SCOPE = "https://cognitiveservices.azure.com/.default"


class EntraAccessTokenProvider:
    def __init__(self, credential) -> None:
        self._credential = credential

    def __call__(self) -> str:
        return self._credential.get_token(AZURE_OPENAI_SCOPE).token


@lru_cache(maxsize=1)
def get_agent_service() -> AgentService:
    from azure.identity import DefaultAzureCredential

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT 환경변수가 필요합니다.")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.6-luna")
    timeout_seconds = float(os.getenv("AZURE_OPENAI_TIMEOUT_SECONDS", "90"))
    credential = DefaultAzureCredential()
    client = AzureOpenAIResponsesClient(
        AzureOpenAISettings(
            endpoint=endpoint,
            deployment=deployment,
            timeout_seconds=timeout_seconds,
        ),
        access_token_provider=EntraAccessTokenProvider(credential),
    )
    return AgentService(client)


def require_agent_service() -> AgentService:
    try:
        return get_agent_service()
    except (ImportError, RuntimeError, ValueError) as exc:
        raise ServiceError(
            503,
            "ai_not_configured",
            "AI 검토 도우미가 아직 구성되지 않았습니다.",
        ) from exc
