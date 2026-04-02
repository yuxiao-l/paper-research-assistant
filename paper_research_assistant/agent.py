from __future__ import annotations

from paper_research_assistant.config import load_settings
from paper_research_assistant.errors import ResearchAssistantError
from paper_research_assistant.llm import LLMClient
from paper_research_assistant.models import ProgressCallback, ResearchProgress, ResearchResult, ResearchState
from paper_research_assistant.react_agent import ReActResearchAgent
from paper_research_assistant.report import save_result
from paper_research_assistant.tools import ToolContext


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
        _report(progress_callback, "setup", "初始化 ReAct 论文调研 Agent")
        settings = load_settings()
        llm = LLMClient(settings)
        ctx = ToolContext(settings=settings, llm=llm, progress_callback=progress_callback)
        agent = ReActResearchAgent(ctx=ctx, max_iterations=10)
        state = ResearchState(
            task=task,
            top_n=top_n,
            per_keyword=per_keyword,
            max_keywords=max_keywords,
            overview_words=overview_words,
            parse_pdf_full_text=parse_pdf_full_text,
        )

        _report(progress_callback, "react", "开始 ReAct 循环决策")
        state = agent.run(state)

        for paper in state.selected:
            paper.full_text = None
            paper.full_text_excerpt = None

        result = state.to_result()
        paths = None
        if save_output:
            _report(progress_callback, "save", "保存调研结果")
            json_path, md_path = save_result(result)
            paths = (str(json_path), str(md_path))

        _report(progress_callback, "done", "调研完成")
        return result, paths
    except ResearchAssistantError as exc:
        _report(progress_callback, "error", f"调研失败：{exc}")
        raise
