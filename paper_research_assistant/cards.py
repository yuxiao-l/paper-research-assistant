from __future__ import annotations

from paper_research_assistant.errors import LLMResponseError
from paper_research_assistant.llm import LLMClient
from paper_research_assistant.models import Paper, PaperCard


def build_card(paper: Paper, task: str, llm: LLMClient) -> PaperCard:
    evidence_scope = "title and abstract"
    full_text_section = "Not available."
    if paper.full_text_excerpt:
        evidence_scope = "title, abstract, and PDF full text excerpt"
        full_text_section = paper.full_text_excerpt

    prompt = f"""
You are preparing a structured literature review card for a single paper.
Return valid JSON only with these keys:
title, year, venue, url, relevance, problem, method, data_or_setting, findings, limitations, tags, evidence_scope

Rules:
- Use only the evidence provided below.
- If a field is missing, write "not stated".
- `tags` must be a JSON array of short strings.
- `evidence_scope` must describe whether the card is based on title/abstract only or also PDF full text excerpt.

Research task:
{task}

Paper metadata:
title={paper.title}
year={paper.year}
venue={paper.venue}
url={paper.url}
pdf_url={paper.pdf_url}

Abstract:
{paper.abstract}

PDF full text excerpt:
{full_text_section}

Evidence scope:
{evidence_scope}
""".strip()
    result = llm.json_response(prompt)
    if not isinstance(result, dict):
        raise LLMResponseError("信息卡生成结果不是合法的 JSON 对象。")

    tags = result.get("tags")
    if not isinstance(tags, list):
        raise LLMResponseError("信息卡生成结果中的 tags 不是 JSON 数组。")

    return PaperCard(
        title=str(result.get("title") or paper.title),
        year=result.get("year") if isinstance(result.get("year"), int) or result.get("year") is None else paper.year,
        venue=str(result.get("venue") or paper.venue or ""),
        url=result.get("url") if isinstance(result.get("url"), str) else paper.url,
        pdf_url=paper.pdf_url,
        pdf_path=paper.pdf_path,
        relevance=str(result.get("relevance") or ""),
        problem=str(result.get("problem") or ""),
        method=str(result.get("method") or ""),
        data_or_setting=str(result.get("data_or_setting") or ""),
        findings=str(result.get("findings") or ""),
        limitations=str(result.get("limitations") or ""),
        tags=[str(tag) for tag in tags if isinstance(tag, str)],
        evidence_scope=str(result.get("evidence_scope") or evidence_scope),
    )
