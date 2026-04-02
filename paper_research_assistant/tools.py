from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from paper_research_assistant.cards import build_card
from paper_research_assistant.config import Settings
from paper_research_assistant.llm import LLMClient
from paper_research_assistant.models import Paper, ProgressCallback, ResearchProgress, ResearchState
from paper_research_assistant.pdf_utils import enrich_papers_with_pdf_text
from paper_research_assistant.ranking import heuristic_rank, rerank_with_llm
from paper_research_assistant.report import build_comparison_table, generate_overview
from paper_research_assistant.search import search_arxiv, search_openalex


def _report(
    progress_callback: ProgressCallback | None,
    step: str,
    message: str,
    current: int | None = None,
    total: int | None = None,
) -> None:
    if progress_callback is None:
        return
    progress_callback(ResearchProgress(step=step, message=message, current=current, total=total))


@dataclass
class ToolContext:
    settings: Settings
    llm: LLMClient
    progress_callback: ProgressCallback | None = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, str]
    handler: Callable[[ResearchState, dict[str, Any], ToolContext], str]


def _paper_brief(paper: Paper) -> str:
    return (
        f"{paper.paper_id}: {paper.title} "
        f"(year={paper.year or 'N/A'}, source={paper.source}, score={paper.score:.3f}, "
        f"pdf={'yes' if paper.full_text_excerpt else 'no'})"
    )


def _assign_new_papers(state: ResearchState, papers: list[Paper]) -> list[Paper]:
    added: list[Paper] = []
    for paper in papers:
        normalized_title = paper.title.strip().lower()
        if not paper.title or normalized_title in state.seen_titles:
            continue
        paper.paper_id = f"P{state.next_paper_index}"
        state.next_paper_index += 1
        state.seen_titles.add(normalized_title)
        state.candidates.append(paper)
        added.append(paper)
    return added


def _lookup_papers(state: ResearchState, paper_ids: list[str] | None, selected_only: bool = False) -> list[Paper]:
    source = state.selected if selected_only else state.candidates
    if not paper_ids:
        return list(source)
    wanted = {paper_id.strip() for paper_id in paper_ids if isinstance(paper_id, str) and paper_id.strip()}
    return [paper for paper in source if paper.paper_id in wanted]


def tool_generate_keywords(state: ResearchState, action_input: dict[str, Any], ctx: ToolContext) -> str:
    focus = str(action_input.get("focus") or "").strip()
    max_keywords = int(action_input.get("max_keywords") or state.max_keywords)
    task = state.task if not focus else f"{state.task}\nFocus: {focus}"
    from paper_research_assistant.keywords import generate_keywords

    state.keywords = generate_keywords(task, llm=ctx.llm, max_keywords=max_keywords)
    _report(ctx.progress_callback, "react", f"生成检索关键词：{', '.join(state.keywords)}")
    return f"Generated {len(state.keywords)} keywords: {', '.join(state.keywords)}"


def _search_with_provider(
    state: ResearchState,
    provider: str,
    query: str,
    limit: int,
    ctx: ToolContext,
) -> str:
    _report(ctx.progress_callback, "react", f"使用 {provider} 检索：{query}")
    if provider == "arxiv":
        papers = search_arxiv(query, limit)
    else:
        papers = search_openalex(query, limit, ctx.settings)
    added = _assign_new_papers(state, papers)
    state.search_history.append(f"{provider}:{query}")
    if not added:
        return f"{provider} returned 0 new papers for query '{query}'."
    preview = "; ".join(_paper_brief(paper) for paper in added[:5])
    return f"{provider} returned {len(added)} new papers for query '{query}'. New papers: {preview}"


def tool_search_arxiv(state: ResearchState, action_input: dict[str, Any], ctx: ToolContext) -> str:
    query = str(action_input.get("query") or "").strip()
    if not query:
        query = state.keywords[0] if state.keywords else state.task
    limit = int(action_input.get("limit") or max(3, state.per_keyword))
    return _search_with_provider(state, "arxiv", query, limit, ctx)


def tool_search_openalex(state: ResearchState, action_input: dict[str, Any], ctx: ToolContext) -> str:
    query = str(action_input.get("query") or "").strip()
    if not query:
        query = state.keywords[0] if state.keywords else state.task
    limit = int(action_input.get("limit") or state.per_keyword)
    return _search_with_provider(state, "openalex", query, limit, ctx)


def tool_rank_candidates(state: ResearchState, action_input: dict[str, Any], ctx: ToolContext) -> str:
    del action_input, ctx
    state.candidates = heuristic_rank(state.task, state.candidates)
    preview = "; ".join(_paper_brief(paper) for paper in state.candidates[:5])
    return f"Ranked {len(state.candidates)} candidates. Top papers: {preview}"


def tool_select_papers(state: ResearchState, action_input: dict[str, Any], ctx: ToolContext) -> str:
    top_n = int(action_input.get("top_n") or state.top_n)
    candidate_limit = int(action_input.get("candidate_limit") or max(top_n * 3, top_n))
    paper_ids = action_input.get("paper_ids")
    selected_pool = _lookup_papers(state, paper_ids if isinstance(paper_ids, list) else None)
    if not selected_pool:
        selected_pool = list(state.candidates)
    if not selected_pool:
        return "No candidate papers are available for selection."
    selected_pool = selected_pool[:candidate_limit]
    state.selected = rerank_with_llm(state.task, selected_pool, llm=ctx.llm, top_n=top_n)
    preview = "; ".join(_paper_brief(paper) for paper in state.selected)
    _report(ctx.progress_callback, "react", f"选出 {len(state.selected)} 篇重点论文")
    return f"Selected {len(state.selected)} papers: {preview}"


def tool_read_papers(state: ResearchState, action_input: dict[str, Any], ctx: ToolContext) -> str:
    if not state.parse_pdf_full_text:
        return "PDF reading is disabled by configuration."

    paper_ids = action_input.get("paper_ids")
    selected_only = bool(action_input.get("selected_only", True))
    papers = _lookup_papers(state, paper_ids if isinstance(paper_ids, list) else None, selected_only=selected_only)
    if not papers:
        papers = list(state.selected if state.selected else state.candidates[: state.top_n])
    enrich_papers_with_pdf_text(papers, progress_callback=ctx.progress_callback)
    extracted = [paper.paper_id for paper in papers if paper.full_text_excerpt]
    if not extracted:
        return f"Attempted PDF extraction for {len(papers)} papers, but no usable full text was extracted."
    return f"Extracted PDF full text for {len(extracted)} papers: {', '.join(extracted)}"


def tool_build_cards(state: ResearchState, action_input: dict[str, Any], ctx: ToolContext) -> str:
    paper_ids = action_input.get("paper_ids")
    papers = _lookup_papers(state, paper_ids if isinstance(paper_ids, list) else None, selected_only=True)
    if not papers:
        papers = list(state.selected)
    if not papers:
        return "No selected papers are available for card extraction."

    existing_by_title = {card.title: card for card in state.cards}
    for paper in papers:
        _report(ctx.progress_callback, "react", f"生成论文信息卡：{paper.title}")
        card = build_card(paper, task=state.task, llm=ctx.llm)
        existing_by_title[card.title] = card
    state.cards = list(existing_by_title.values())
    return f"Built {len(papers)} paper cards. Total cards available: {len(state.cards)}"


def tool_generate_report(state: ResearchState, action_input: dict[str, Any], ctx: ToolContext) -> str:
    target_words = int(action_input.get("target_words") or state.overview_words)
    if not state.selected:
        return "No selected papers are available for report generation."
    if not state.cards:
        return "No paper cards are available for report generation."
    state.overview = generate_overview(
        state.task,
        cards=state.cards,
        papers=state.selected,
        llm=ctx.llm,
        target_words=target_words,
    )
    state.comparison_table = build_comparison_table(state.cards)
    _report(ctx.progress_callback, "react", "已生成综述与对比表")
    return (
        f"Generated overview ({len(state.overview)} chars) and comparison table "
        f"for {len(state.cards)} papers."
    )


def tool_finish(state: ResearchState, action_input: dict[str, Any], ctx: ToolContext) -> str:
    del action_input
    if not state.candidates and not state.selected:
        return "Cannot finish yet because no usable papers have been found."
    if not state.selected:
        state.candidates = heuristic_rank(state.task, state.candidates)
        state.selected = state.candidates[: state.top_n]
    if not state.selected:
        return "Cannot finish yet because no papers could be selected."
    if state.parse_pdf_full_text and state.selected and not any(paper.full_text_excerpt for paper in state.selected):
        enrich_papers_with_pdf_text(state.selected[: state.top_n], progress_callback=ctx.progress_callback)
    if len(state.cards) < len(state.selected):
        existing_titles = {card.title for card in state.cards}
        for paper in state.selected:
            if paper.title in existing_titles:
                continue
            state.cards.append(build_card(paper, task=state.task, llm=ctx.llm))
    if state.selected and state.cards and not state.overview:
        state.overview = generate_overview(
            state.task,
            cards=state.cards,
            papers=state.selected,
            llm=ctx.llm,
            target_words=state.overview_words,
        )
        state.comparison_table = build_comparison_table(state.cards)
    state.done = True
    return (
        f"Research finished with {len(state.selected)} selected papers, "
        f"{len(state.cards)} cards, and overview={'yes' if state.overview else 'no'}."
    )


def build_tool_registry() -> dict[str, ToolDefinition]:
    return {
        "generate_keywords": ToolDefinition(
            name="generate_keywords",
            description="Generate or refine academic search keywords for the research task.",
            input_schema={"focus": "optional string", "max_keywords": "optional integer"},
            handler=tool_generate_keywords,
        ),
        "search_arxiv": ToolDefinition(
            name="search_arxiv",
            description="Search arXiv and add new papers into the candidate pool.",
            input_schema={"query": "string", "limit": "optional integer"},
            handler=tool_search_arxiv,
        ),
        "search_openalex": ToolDefinition(
            name="search_openalex",
            description="Search OpenAlex and add new papers into the candidate pool.",
            input_schema={"query": "string", "limit": "optional integer"},
            handler=tool_search_openalex,
        ),
        "rank_candidates": ToolDefinition(
            name="rank_candidates",
            description="Apply heuristic ranking to the current candidate pool.",
            input_schema={},
            handler=tool_rank_candidates,
        ),
        "select_papers": ToolDefinition(
            name="select_papers",
            description="Use the LLM to rerank papers and select the most valuable ones.",
            input_schema={
                "top_n": "optional integer",
                "candidate_limit": "optional integer",
                "paper_ids": "optional string array",
            },
            handler=tool_select_papers,
        ),
        "read_papers": ToolDefinition(
            name="read_papers",
            description="Download PDFs and extract full-text excerpts for selected papers.",
            input_schema={
                "paper_ids": "optional string array",
                "selected_only": "optional boolean, default true",
            },
            handler=tool_read_papers,
        ),
        "build_cards": ToolDefinition(
            name="build_cards",
            description="Create structured literature-review cards for selected papers.",
            input_schema={"paper_ids": "optional string array"},
            handler=tool_build_cards,
        ),
        "generate_report": ToolDefinition(
            name="generate_report",
            description="Generate the final overview and comparison table from cards and papers.",
            input_schema={"target_words": "optional integer"},
            handler=tool_generate_report,
        ),
        "finish": ToolDefinition(
            name="finish",
            description="Finalize the research result when evidence is sufficient.",
            input_schema={},
            handler=tool_finish,
        ),
    }
