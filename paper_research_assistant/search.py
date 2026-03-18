from __future__ import annotations

import html
import time
from collections.abc import Callable
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import requests

from paper_research_assistant.config import Settings
from paper_research_assistant.errors import EmptySearchResultError, SearchProviderError
from paper_research_assistant.models import Paper, ProgressCallback, ResearchProgress


def _reconstruct_openalex_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    if not inverted_index:
        return ""
    max_position = max((max(positions) for positions in inverted_index.values() if positions), default=-1)
    if max_position < 0:
        return ""
    words = [""] * (max_position + 1)
    for token, positions in inverted_index.items():
        for position in positions:
            if 0 <= position <= max_position:
                words[position] = token
    return " ".join(word for word in words if word).strip()


def search_openalex(keyword: str, limit: int, settings: Settings) -> list[Paper]:
    params = {
        "search": keyword,
        "per-page": limit,
    }
    if settings.openalex_email:
        params["mailto"] = settings.openalex_email

    response = requests.get(
        "https://api.openalex.org/works",
        params=params,
        timeout=20,
    )
    response.raise_for_status()

    payload = response.json()
    papers: list[Paper] = []
    for item in payload.get("results", []):
        title = (item.get("display_name") or "").strip()
        abstract = _reconstruct_openalex_abstract(item.get("abstract_inverted_index"))
        if not title or not abstract:
            continue

        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}
        best_oa_location = item.get("best_oa_location") or {}
        pdf_url = best_oa_location.get("pdf_url") or primary_location.get("pdf_url")
        url = (
            best_oa_location.get("landing_page_url")
            or primary_location.get("landing_page_url")
            or item.get("doi")
            or item.get("id")
        )

        papers.append(
            Paper(
                title=title,
                abstract=abstract,
                year=item.get("publication_year"),
                venue=source.get("display_name"),
                authors=[
                    authorship.get("author", {}).get("display_name", "")
                    for authorship in item.get("authorships", [])
                    if authorship.get("author", {}).get("display_name")
                ],
                url=url,
                citation_count=item.get("cited_by_count"),
                source="openalex",
                keyword=keyword,
                pdf_url=pdf_url,
            )
        )
    return papers


def search_arxiv(keyword: str, limit: int) -> list[Paper]:
    time.sleep(5.0)
    query = urllib.parse.quote(f'all:"{keyword}"')
    url = (
        "http://export.arxiv.org/api/query"
        f"?search_query={query}&start=0&max_results={limit}&sortBy=relevance&sortOrder=descending"
    )
    with urllib.request.urlopen(url, timeout=20) as response:
        raw_xml = response.read()
    root = ET.fromstring(raw_xml)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    papers: list[Paper] = []
    for entry in root.findall("atom:entry", ns):
        title = html.unescape(" ".join((entry.findtext("atom:title", default="", namespaces=ns) or "").split()))
        abstract = html.unescape(" ".join((entry.findtext("atom:summary", default="", namespaces=ns) or "").split()))
        published = entry.findtext("atom:published", default="", namespaces=ns)
        year = int(published[:4]) if len(published) >= 4 and published[:4].isdigit() else None
        url = entry.findtext("atom:id", default="", namespaces=ns) or None
        pdf_url = None
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href")
                break
        if not pdf_url and url and "/abs/" in url:
            pdf_url = url.replace("/abs/", "/pdf/") + ".pdf"
        authors = [
            author.findtext("atom:name", default="", namespaces=ns)
            for author in entry.findall("atom:author", ns)
            if author.findtext("atom:name", default="", namespaces=ns)
        ]
        if not title or not abstract:
            continue
        papers.append(
            Paper(
                title=title,
                abstract=abstract,
                year=year,
                venue="arXiv",
                authors=authors,
                url=url,
                citation_count=None,
                source="arxiv",
                keyword=keyword,
                pdf_url=pdf_url,
            )
        )
    return papers


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


def _search_provider(
    provider: str,
    keyword: str,
    search_fn: Callable[[], list[Paper]],
    progress_callback: ProgressCallback | None,
    current: int,
    total: int,
) -> list[Paper]:
    _report(progress_callback, "search", f"正在通过 {provider} 检索：{keyword}", current=current, total=total)
    try:
        results = search_fn()
    except Exception as exc:
        raise SearchProviderError(provider, keyword, str(exc)) from exc
    _report(
        progress_callback,
        "search",
        f"{provider} 检索完成：关键词“{keyword}”获得 {len(results)} 篇结果",
        current=current,
        total=total,
    )
    return results


def search_papers(
    keywords: list[str],
    per_keyword: int,
    settings: Settings,
    progress_callback: ProgressCallback | None = None,
) -> list[Paper]:
    found: list[Paper] = []
    seen_titles: set[str] = set()
    total_keywords = len(keywords)

    for index, keyword in enumerate(keywords, start=1):
        per_source_results: list[Paper] = []
        _report(progress_callback, "search", f"正在处理检索关键词 {index}/{total_keywords}：{keyword}", current=index, total=total_keywords)
        # per_source_results.extend(
        #     _search_provider(
        #         "OpenAlex",
        #         keyword,
        #         lambda: search_openalex(keyword, per_keyword, settings),
        #         progress_callback,
        #         current=index,
        #         total=total_keywords,
        #     )
        # )
        per_source_results.extend(
            _search_provider(
                "arXiv",
                keyword,
                lambda: search_arxiv(keyword, max(3, per_keyword)),
                progress_callback,
                current=index,
                total=total_keywords,
            )
        )

        for paper in per_source_results:
            normalized_title = paper.title.strip().lower()
            if normalized_title in seen_titles:
                continue
            seen_titles.add(normalized_title)
            found.append(paper)

    if not found:
        raise EmptySearchResultError("未检索到任何论文，请调整研究任务或关键词后重试。")
    return found
