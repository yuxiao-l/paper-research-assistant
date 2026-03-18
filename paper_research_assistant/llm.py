from __future__ import annotations

import json
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None

from paper_research_assistant.config import Settings
from paper_research_assistant.errors import LLMConfigurationError, LLMConnectionError, LLMResponseError


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.openai_api_key
        self.model = settings.openai_model
        self._client = None
        if self._api_key and OpenAI is not None:
            kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
            if settings.openai_base_url:
                kwargs["base_url"] = settings.openai_base_url
            self._client = OpenAI(**kwargs)

    def _require_client(self) -> OpenAI:
        if OpenAI is None:
            raise LLMConfigurationError("未安装 openai 依赖，请先执行 `pip install -r requirements.txt`。")
        if not self._api_key:
            raise LLMConfigurationError("未配置 `OPENAI_API_KEY`，请在 `.env` 中填写后重试。")
        if self._client is None:
            raise LLMConfigurationError("大模型客户端初始化失败，请检查 `.env` 配置。")
        return self._client

    def _chat_text(self, prompt: str) -> str:
        client = self._require_client()

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful research assistant."},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
            )
        except Exception as exc:
            raise LLMConnectionError("无法连接到大模型，请检查 API Key、Base URL 或网络连接。") from exc

        choices = getattr(response, "choices", None)
        if not choices:
            raise LLMResponseError("大模型未返回任何内容。")

        message = getattr(choices[0], "message", None)
        text = getattr(message, "content", None) if message is not None else None
        if not isinstance(text, str) or not text.strip():
            raise LLMResponseError("大模型未返回可用文本。")
        return text.strip()

    def json_response(self, prompt: str) -> Any:
        text = self._chat_text(prompt)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            raise LLMResponseError("大模型返回内容不是合法 JSON，请重试。")

    def text_response(self, prompt: str) -> str:
        return self._chat_text(prompt)
