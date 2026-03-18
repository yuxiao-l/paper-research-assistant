from __future__ import annotations

from paper_research_assistant.errors import LLMResponseError
from paper_research_assistant.llm import LLMClient


def generate_keywords(task: str, llm: LLMClient, max_keywords: int = 6) -> list[str]:
    prompt = f"""
你是论文检索助手。请根据下面的研究任务，生成最多 {max_keywords} 条适合学术检索的关键词或短语。
要求：
1. 同时覆盖任务主题、方法、应用场景。
2. 使用英文学术检索表达。
3. 返回 JSON 数组，不要附加解释。

研究任务：
{task}
""".strip()
    result = llm.json_response(prompt)
    if not isinstance(result, list):
        raise LLMResponseError("关键词生成结果不是 JSON 数组。")

    keywords: list[str] = []
    for item in result:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned and cleaned not in keywords:
                keywords.append(cleaned)

    if not keywords:
        raise LLMResponseError("大模型未生成有效关键词。")
    return keywords[:max_keywords]
