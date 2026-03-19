from __future__ import annotations

from paper_research_assistant.cards import build_card
from paper_research_assistant.config import load_settings
from paper_research_assistant.errors import ResearchAssistantError
from paper_research_assistant.keywords import generate_keywords
from paper_research_assistant.llm import LLMClient
from paper_research_assistant.models import ProgressCallback, ResearchProgress, ResearchResult
from paper_research_assistant.pdf_utils import enrich_papers_with_pdf_text
from paper_research_assistant.ranking import heuristic_rank, rerank_with_llm
from paper_research_assistant.report import build_comparison_table, generate_overview, save_result
from paper_research_assistant.search import search_papers


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


def run_research(
    task: str,
    top_n: int = 5,
    per_keyword: int = 8,
    max_keywords: int = 6,
    overview_words: int = 300,
    parse_pdf_full_text: bool = True,
    save_output: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> tuple[ResearchResult, tuple[str, str] | None]:
    try:
        _report(progress_callback, "setup", "初始化研究助手")
        settings = load_settings()
        llm = LLMClient(settings)

        _report(progress_callback, "keywords", "生成检索关键词")
        keywords = generate_keywords(task, llm=llm, max_keywords=max_keywords)
        _report(progress_callback, "keywords", f"关键词：{', '.join(keywords)}")

        _report(progress_callback, "search", "检索论文标题与摘要")
        candidates = search_papers(
            keywords,
            per_keyword=per_keyword,
            settings=settings,
            progress_callback=progress_callback,
        )

        _report(progress_callback, "rank", f"开始筛选，共检索到 {len(candidates)} 篇候选论文")
        ranked = heuristic_rank(task, candidates)

        _report(progress_callback, "rank", "使用大模型重排候选论文")
        selected = rerank_with_llm(task, ranked[: max(top_n * 3, top_n)], llm=llm, top_n=top_n)
        _report(progress_callback, "rank", f"已选出前 {len(selected)} 篇论文")

        if parse_pdf_full_text:
            _report(progress_callback, "pdf", "开始下载并解析已入选论文的 PDF 全文")
            enrich_papers_with_pdf_text(selected, progress_callback=progress_callback)
        else:
            _report(progress_callback, "pdf", "已跳过 PDF 全文解析")

        cards = []
        for index, paper in enumerate(selected, start=1):
            _report(
                progress_callback,
                "card",
                f"生成标准信息卡 {index}/{len(selected)}：{paper.title}",
                current=index,
                total=len(selected),
            )
            cards.append(build_card(paper, task=task, llm=llm))

        _report(progress_callback, "overview", "生成综述与对比表")
        overview = generate_overview(task, cards=cards, papers=selected, llm=llm, target_words=overview_words)
        comparison_table = build_comparison_table(cards)

        for paper in selected:
            paper.full_text = None
            paper.full_text_excerpt = None

        result = ResearchResult(
            task=task,
            keywords=keywords,
            candidates=candidates,
            selected=selected,
            cards=cards,
            overview=overview,
            comparison_table=comparison_table,
        )
        paths = None
        if save_output:
            _report(progress_callback, "save", "保存研究结果")
            json_path, md_path = save_result(result)
            paths = (str(json_path), str(md_path))
        _report(progress_callback, "done", "调研完成")
        return result, paths
    except ResearchAssistantError as exc:
        _report(progress_callback, "error", f"调研失败：{exc}")
        raise
