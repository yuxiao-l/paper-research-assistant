from __future__ import annotations

import argparse
import sys

from paper_research_assistant.agent import run_research
from paper_research_assistant.errors import ResearchAssistantError
from paper_research_assistant.models import ResearchProgress


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Single-agent paper research assistant")
    parser.add_argument("--task", required=True, help="Research task description")
    parser.add_argument("--top-n", type=int, default=5, help="Number of selected papers")
    parser.add_argument("--per-keyword", type=int, default=8, help="Search results per keyword")
    parser.add_argument("--max-keywords", type=int, default=6, help="Maximum number of generated search keywords")
    parser.add_argument("--overview-words", type=int, default=300, help="Target word count for the generated overview")
    parser.add_argument("--no-pdf-full-text", action="store_true", help="Skip PDF download and full-text extraction")
    parser.add_argument("--no-save", action="store_true", help="Do not save outputs to disk")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    def on_progress(progress: ResearchProgress) -> None:
        print(f"[{progress.step}] {progress.message}", file=sys.stderr)

    try:
        result, paths = run_research(
            task=args.task,
            top_n=args.top_n,
            per_keyword=args.per_keyword,
            max_keywords=args.max_keywords,
            overview_words=args.overview_words,
            parse_pdf_full_text=not args.no_pdf_full_text,
            save_output=not args.no_save,
            progress_callback=on_progress,
        )
    except ResearchAssistantError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("=" * 80)
    print("Research Task:")
    print(result.task)
    print()
    print("Keywords:")
    print(", ".join(result.keywords))
    print()
    print("Overview:")
    print(result.overview)
    print()
    print("Selected Papers:")
    for index, paper in enumerate(result.selected, start=1):
        print(f"{index}. {paper.title} ({paper.year or 'N/A'}) [{paper.source}] score={paper.score:.3f}")
        print(f"   reason: {paper.reason}")
        if paper.url:
            print(f"   url: {paper.url}")
        if paper.pdf_url:
            print(f"   pdf: {paper.pdf_url}")
        if paper.full_text_excerpt:
            print(f"   full text excerpt: {paper.full_text_excerpt[:300]}...")
    print()
    print("Comparison Table:")
    print(result.comparison_table)
    if paths:
        print()
        print(f"Saved JSON: {paths[0]}")
        print(f"Saved Markdown: {paths[1]}")


if __name__ == "__main__":
    sys.exit(main())
