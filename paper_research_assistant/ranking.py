from __future__ import annotations

import math
import re
from datetime import datetime

from paper_research_assistant.errors import LLMResponseError
from paper_research_assistant.llm import LLMClient
from paper_research_assistant.models import Paper


def _normalize_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9\-+/]{1,}", text.lower()))


def heuristic_rank(task: str, papers: list[Paper]) -> list[Paper]:
    now_year = datetime.now().year
    task_tokens = _normalize_tokens(task)

    for paper in papers:
        text_tokens = _normalize_tokens(f"{paper.title} {paper.abstract}")
        overlap = len(task_tokens & text_tokens) / max(len(task_tokens), 1)
        citations = math.log1p(paper.citation_count or 0) / 10
        recency = 0.0
        if paper.year:
            recency = max(0.0, 1 - min(now_year - paper.year, 10) / 10)
        paper.score = overlap * 0.65 + citations * 0.2 + recency * 0.15
        paper.reason = (
            f"task_overlap={overlap:.2f}, citations={paper.citation_count or 0}, "
            f"year={paper.year or 'unknown'}"
        )
    return sorted(papers, key=lambda item: item.score, reverse=True)


def rerank_with_llm(task: str, papers: list[Paper], llm: LLMClient, top_n: int) -> list[Paper]:
    candidate_payload = [
        {
            "id": index,
            "title": paper.title,
            "abstract": paper.abstract[:1200],
            "year": paper.year,
            "venue": paper.venue,
            "citation_count": paper.citation_count,
        }
        for index, paper in enumerate(papers)
    ]
    prompt = f"""
你是论文筛选助手。请根据研究任务，从候选论文中选出最值得保留的前 {top_n} 篇。
优先考虑：主题相关性、方法代表性、新文章、近年进展、可形成对比。
只返回 JSON 数组，每个元素格式为：
{{"id": 0, "score": 0.95, "reason": "一句话理由"}}

研究任务：
{task}

候选论文：
{candidate_payload}
""".strip()
    result = llm.json_response(prompt)
    if not isinstance(result, list):
        raise LLMResponseError("候选论文重排结果不是 JSON 数组。")

    rescored: list[Paper] = []
    for item in result:
        if not isinstance(item, dict):
            continue
        index = item.get("id")
        if not isinstance(index, int) or index < 0 or index >= len(papers):
            continue
        paper = papers[index]
        score = item.get("score")
        if isinstance(score, (int, float)):
            paper.score = float(score)
        reason = item.get("reason")
        if isinstance(reason, str) and reason.strip():
            paper.reason = reason.strip()
        rescored.append(paper)

    if not rescored:
        raise LLMResponseError("大模型未返回有效的重排结果。")

    unique: list[Paper] = []
    seen_titles: set[str] = set()
    for paper in sorted(rescored, key=lambda item: item.score, reverse=True):
        title_key = paper.title.lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        unique.append(paper)
    return unique[:top_n]
