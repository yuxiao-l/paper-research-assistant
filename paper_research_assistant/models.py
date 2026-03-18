from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Paper:
    title: str
    abstract: str
    year: int | None = None
    venue: str | None = None
    authors: list[str] = field(default_factory=list)
    url: str | None = None
    citation_count: int | None = None
    source: str = "unknown"
    keyword: str = ""
    score: float = 0.0
    reason: str = ""
    pdf_url: str | None = None
    pdf_path: str | None = None
    full_text: str | None = None
    full_text_excerpt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PaperCard:
    title: str
    year: int | None
    venue: str | None
    url: str | None
    pdf_url: str | None
    pdf_path: str | None
    relevance: str
    problem: str
    method: str
    data_or_setting: str
    findings: str
    limitations: str
    tags: list[str]
    evidence_scope: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchResult:
    task: str
    keywords: list[str]
    candidates: list[Paper]
    selected: list[Paper]
    cards: list[PaperCard]
    overview: str
    comparison_table: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "keywords": self.keywords,
            "candidates": [paper.to_dict() for paper in self.candidates],
            "selected": [paper.to_dict() for paper in self.selected],
            "cards": [card.to_dict() for card in self.cards],
            "overview": self.overview,
            "comparison_table": self.comparison_table,
        }


@dataclass
class ResearchProgress:
    step: str
    message: str
    current: int | None = None
    total: int | None = None


ProgressCallback = Callable[[ResearchProgress], None]
