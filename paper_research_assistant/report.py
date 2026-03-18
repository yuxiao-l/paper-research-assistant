from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from paper_research_assistant.llm import LLMClient
from paper_research_assistant.models import PaperCard, ResearchResult


def generate_overview(task: str, cards: list[PaperCard], llm: LLMClient, target_words: int = 300) -> str:
    lower_bound = max(80, int(target_words * 0.8))
    upper_bound = max(lower_bound, int(target_words * 1.2))
    prompt = f"""
You are writing a concise literature review overview.
Based on the paper cards below, write an overview for the following research task.

Requirements:
- Target length: about {target_words} Chinese characters, ideally within {lower_bound}-{upper_bound}.
- Summarize the main research threads and key differences across papers.
- Point out promising directions for deeper reading.
- Respect the evidence scope in each paper card. Some cards are based on title/abstract only, while others also use PDF full text excerpts.
- Start directly with the overview content.

Research task:
{task}

Paper cards:
{json.dumps([card.to_dict() for card in cards], ensure_ascii=False)}
""".strip()
    return llm.text_response(prompt)


def build_comparison_table(cards: list[PaperCard]) -> str:
    headers = ["Title", "Year", "Venue", "Problem", "Method", "Findings", "Limitations"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for card in cards:
        row = [
            card.title.replace("|", "/"),
            str(card.year or ""),
            (card.venue or "").replace("|", "/"),
            card.problem[:80].replace("|", "/"),
            card.method[:80].replace("|", "/"),
            card.findings[:80].replace("|", "/"),
            card.limitations[:80].replace("|", "/"),
        ]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def save_result(result: ResearchResult, output_dir: str = "outputs") -> tuple[Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(output_dir) / timestamp
    output_path.mkdir(parents=True, exist_ok=True)

    json_path = output_path / "result.json"
    md_path = output_path / "report.md"

    json_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# Paper Research Report",
        "",
        "## Task",
        result.task,
        "",
        "## Keywords",
        ", ".join(result.keywords),
        "",
        "## Overview",
        result.overview,
        "",
        "## Selected Papers",
    ]
    for index, paper in enumerate(result.selected, start=1):
        report.extend(
            [
                f"### {index}. {paper.title}",
                f"- Year: {paper.year or 'N/A'}",
                f"- Venue: {paper.venue or 'N/A'}",
                f"- Source: {paper.source}",
                f"- Score: {paper.score:.3f}",
                f"- Reason: {paper.reason}",
                f"- URL: {paper.url or 'N/A'}",
                f"- PDF URL: {paper.pdf_url or 'N/A'}",
                f"- Full Text Extracted: {'Yes' if paper.full_text_excerpt else 'No'}",
                "",
            ]
        )
    report.extend(["## Comparison Table", result.comparison_table, "", "## Information Cards"])
    for card in result.cards:
        report.extend(
            [
                f"### {card.title}",
                f"- Relevance: {card.relevance}",
                f"- Evidence Scope: {card.evidence_scope}",
                f"- Problem: {card.problem}",
                f"- Method: {card.method}",
                f"- Data/Setting: {card.data_or_setting}",
                f"- Findings: {card.findings}",
                f"- Limitations: {card.limitations}",
                f"- Tags: {', '.join(card.tags)}",
                "",
            ]
        )
    md_path.write_text("\n".join(report), encoding="utf-8")
    return json_path, md_path
