from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Paper:
    title: str
    abstract: str
    paper_id: str | None = None
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
        payload = asdict(self)
        payload.pop("full_text", None)
        payload.pop("full_text_excerpt", None)
        return payload


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
    reasoning_trace: list["AgentTraceStep"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "keywords": self.keywords,
            "candidates": [paper.to_dict() for paper in self.candidates],
            "selected": [paper.to_dict() for paper in self.selected],
            "cards": [card.to_dict() for card in self.cards],
            "overview": self.overview,
            "comparison_table": self.comparison_table,
            "reasoning_trace": [step.to_dict() for step in self.reasoning_trace],
        }


@dataclass
class ResearchProgress:
    step: str
    message: str
    current: int | None = None
    total: int | None = None


ProgressCallback = Callable[[ResearchProgress], None]


@dataclass
class AgentTraceStep:
    iteration: int
    thought: str
    action: str
    action_input: dict[str, Any]
    observation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchState:
    task: str
    top_n: int
    per_keyword: int
    max_keywords: int
    overview_words: int
    parse_pdf_full_text: bool
    keywords: list[str] = field(default_factory=list)
    candidates: list[Paper] = field(default_factory=list)
    selected: list[Paper] = field(default_factory=list)
    cards: list[PaperCard] = field(default_factory=list)
    overview: str = ""
    comparison_table: str = ""
    search_history: list[str] = field(default_factory=list)
    reasoning_trace: list[AgentTraceStep] = field(default_factory=list)
    done: bool = False
    next_paper_index: int = 1
    seen_titles: set[str] = field(default_factory=set, repr=False)

    def to_result(self) -> ResearchResult:
        return ResearchResult(
            task=self.task,
            keywords=list(self.keywords),
            candidates=list(self.candidates),
            selected=list(self.selected),
            cards=list(self.cards),
            overview=self.overview,
            comparison_table=self.comparison_table,
            reasoning_trace=list(self.reasoning_trace),
        )
