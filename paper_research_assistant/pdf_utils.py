from __future__ import annotations

from io import BytesIO
import re

import requests

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

from paper_research_assistant.errors import PDFProcessingError
from paper_research_assistant.models import Paper, ProgressCallback, ResearchProgress


DEFAULT_MAX_PAGES = 8
DEFAULT_MAX_CHARS = 20000


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


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_pdf_text(pdf_bytes: bytes, max_pages: int = DEFAULT_MAX_PAGES) -> str:
    if PdfReader is None:
        raise PDFProcessingError("缺少 `pypdf` 依赖，无法解析 PDF，请先执行 `pip install -r requirements.txt`。")

    reader = PdfReader(BytesIO(pdf_bytes))
    snippets: list[str] = []
    for page in reader.pages[:max_pages]:
        page_text = page.extract_text() or ""
        page_text = _normalize_text(page_text)
        if page_text:
            snippets.append(page_text)
    return "\n\n".join(snippets)


def enrich_papers_with_pdf_text(
    papers: list[Paper],
    progress_callback: ProgressCallback | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[Paper]:
    total = len(papers)
    if total == 0:
        return papers

    for index, paper in enumerate(papers, start=1):
        if not paper.pdf_url:
            _report(
                progress_callback,
                "pdf",
                f"跳过 PDF 解析 {index}/{total}：{paper.title}（未找到 PDF 链接）",
                current=index,
                total=total,
            )
            continue

        _report(
            progress_callback,
            "pdf",
            f"下载 PDF {index}/{total}：{paper.title}",
            current=index,
            total=total,
        )
        try:
            response = requests.get(
                paper.pdf_url,
                timeout=30,
                headers={"User-Agent": "paper-research-assistant/1.0"},
            )
            response.raise_for_status()

            _report(
                progress_callback,
                "pdf",
                f"解析全文 {index}/{total}：{paper.title}",
                current=index,
                total=total,
            )
            full_text = extract_pdf_text(response.content, max_pages=max_pages)
        except Exception as exc:
            paper.full_text = None
            paper.full_text_excerpt = None
            _report(
                progress_callback,
                "pdf",
                f"PDF 解析失败 {index}/{total}：{paper.title}（{exc}）",
                current=index,
                total=total,
            )
            continue

        if not full_text:
            paper.full_text = None
            paper.full_text_excerpt = None
            _report(
                progress_callback,
                "pdf",
                f"未提取到可用全文 {index}/{total}：{paper.title}",
                current=index,
                total=total,
            )
            continue

        paper.full_text = full_text
        paper.full_text_excerpt = full_text[:max_chars]
        _report(
            progress_callback,
            "pdf",
            f"全文解析完成 {index}/{total}：{paper.title}",
            current=index,
            total=total,
        )

    return papers
