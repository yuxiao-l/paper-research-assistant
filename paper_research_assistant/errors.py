from __future__ import annotations


class ResearchAssistantError(Exception):
    """Base exception for user-facing research assistant errors."""


class LLMConfigurationError(ResearchAssistantError):
    """Raised when the LLM client is not configured correctly."""


class LLMConnectionError(ResearchAssistantError):
    """Raised when the LLM service cannot be reached."""


class LLMResponseError(ResearchAssistantError):
    """Raised when the LLM returns an invalid response."""


class SearchProviderError(ResearchAssistantError):
    """Raised when a search provider fails."""

    def __init__(self, provider: str, keyword: str, detail: str) -> None:
        super().__init__(f"{provider} 检索失败（关键词：{keyword}）：{detail}")
        self.provider = provider
        self.keyword = keyword
        self.detail = detail


class EmptySearchResultError(ResearchAssistantError):
    """Raised when no papers are found for the task."""


class PDFProcessingError(ResearchAssistantError):
    """Raised when PDF parsing cannot be initialized."""


class AgentLoopError(ResearchAssistantError):
    """Raised when the ReAct agent cannot complete its loop safely."""
