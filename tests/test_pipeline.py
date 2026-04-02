import unittest
from types import SimpleNamespace
from unittest.mock import patch

from paper_research_assistant.agent import run_research
from paper_research_assistant.cards import build_card
from paper_research_assistant.config import Settings
from paper_research_assistant.errors import LLMConfigurationError, SearchProviderError
from paper_research_assistant.llm import LLMClient
from paper_research_assistant.models import Paper, PaperCard
from paper_research_assistant.pdf_utils import enrich_papers_with_pdf_text
from paper_research_assistant.ranking import heuristic_rank
from paper_research_assistant.report import build_comparison_table
from paper_research_assistant.search import search_papers


class DummyLLM:
    def __init__(self) -> None:
        self.last_prompt = ""

    def json_response(self, prompt):
        self.last_prompt = prompt
        return {
            "title": "Agentic Code Planning",
            "year": 2024,
            "venue": "arXiv",
            "url": "https://example.com",
            "pdf_url": None,
            "pdf_path": None,
            "relevance": "relevant",
            "problem": "We study agentic code planning.",
            "method": "Our method uses iterative decomposition.",
            "data_or_setting": "arXiv",
            "findings": "Experiments show improved success rate.",
            "limitations": "based on provided text only",
            "tags": ["agentic", "planning"],
            "evidence_scope": "title, abstract, and PDF full text excerpt",
        }


class FakeReActLLM:
    def __init__(self, actions):
        self.actions = list(actions)

    def json_response(self, prompt):
        if "ReAct-style paper research agent" not in prompt:
            raise AssertionError(f"Unexpected JSON prompt: {prompt}")
        if not self.actions:
            raise AssertionError("No more queued ReAct actions.")
        return self.actions.pop(0)

    def text_response(self, prompt):
        raise AssertionError(f"Unexpected text prompt: {prompt}")


class PipelineTests(unittest.TestCase):
    def test_heuristic_rank_prefers_relevant_paper(self):
        papers = [
            Paper(
                title="Multi-Agent Collaboration for Code Generation",
                abstract="This paper studies multi-agent collaboration and code generation with planning.",
                year=2025,
                citation_count=20,
            ),
            Paper(
                title="Image Classification with CNNs",
                abstract="This paper studies convolutional neural networks for image tasks.",
                year=2024,
                citation_count=200,
            ),
        ]
        ranked = heuristic_rank("multi-agent collaboration for code generation", papers)
        self.assertEqual(ranked[0].title, "Multi-Agent Collaboration for Code Generation")

    def test_build_card_and_table(self):
        llm = DummyLLM()
        paper = Paper(
            title="Agentic Code Planning",
            abstract="We study agentic code planning. Our method uses iterative decomposition. "
            "Experiments show improved success rate.",
            year=2024,
            venue="arXiv",
            url="https://example.com",
            pdf_url="https://example.com/paper.pdf",
            full_text_excerpt="The full paper describes an iterative decomposition pipeline in detail.",
        )
        card = build_card(paper, task="agentic coding", llm=llm)
        table = build_comparison_table([card])
        self.assertIn("Agentic Code Planning", table)
        self.assertIn("iterative decomposition", card.method)
        self.assertIn("The full paper describes", llm.last_prompt)

    def test_paper_to_dict_excludes_full_text_fields(self):
        paper = Paper(
            title="PDF Paper",
            abstract="abstract",
            full_text="full text body",
            full_text_excerpt="excerpt",
        )
        payload = paper.to_dict()
        self.assertNotIn("full_text", payload)
        self.assertNotIn("full_text_excerpt", payload)

    def test_llm_without_api_key_raises(self):
        llm = LLMClient(
            Settings(
                openai_api_key=None,
                openai_base_url=None,
                openai_model="gpt-4o-mini",
                openalex_email=None,
            )
        )
        with self.assertRaises(LLMConfigurationError):
            llm.text_response("hello")

    @patch("paper_research_assistant.llm.OpenAI", new=SimpleNamespace)
    def test_llm_json_response_uses_chat_completions_shape(self):
        llm = LLMClient(
            Settings(
                openai_api_key=None,
                openai_base_url="https://api.deepseek.com",
                openai_model="deepseek-chat",
                openalex_email=None,
            )
        )
        llm._api_key = "test-key"
        llm._client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
                    )
                )
            )
        )
        result = llm.json_response("hello")
        self.assertEqual(result, {"ok": True})

    @patch("paper_research_assistant.search.search_openalex", side_effect=RuntimeError("network down"))
    def test_search_papers_surfaces_provider_error(self, _mock_search):
        settings = Settings(
            openai_api_key=None,
            openai_base_url=None,
            openai_model="gpt-4o-mini",
            openalex_email=None,
        )
        with self.assertRaises(SearchProviderError):
            search_papers(["agent"], per_keyword=2, settings=settings, providers=("openalex",))

    @patch("paper_research_assistant.pdf_utils.PdfReader")
    @patch("paper_research_assistant.pdf_utils.requests.get")
    def test_enrich_papers_with_pdf_text_populates_excerpt(self, mock_get, mock_pdf_reader):
        mock_get.return_value = SimpleNamespace(content=b"%PDF-1.4", raise_for_status=lambda: None)
        mock_pdf_reader.return_value = SimpleNamespace(
            pages=[
                SimpleNamespace(extract_text=lambda: "First page text."),
                SimpleNamespace(extract_text=lambda: "Second page text."),
            ]
        )
        paper = Paper(
            title="PDF Paper",
            abstract="abstract",
            pdf_url="https://example.com/paper.pdf",
        )

        enrich_papers_with_pdf_text([paper])

        self.assertIn("First page text.", paper.full_text or "")
        self.assertIn("Second page text.", paper.full_text_excerpt or "")

    @patch("paper_research_assistant.agent.load_settings")
    @patch("paper_research_assistant.agent.LLMClient")
    @patch("paper_research_assistant.tools.search_arxiv")
    @patch("paper_research_assistant.tools.enrich_papers_with_pdf_text")
    @patch("paper_research_assistant.tools.build_card")
    @patch("paper_research_assistant.tools.generate_overview")
    @patch("paper_research_assistant.tools.rerank_with_llm")
    def test_run_research_uses_react_loop(
        self,
        mock_rerank,
        mock_overview,
        mock_build_card,
        mock_enrich,
        mock_search_arxiv,
        mock_llm_cls,
        mock_load_settings,
    ):
        actions = [
            {"thought": "Need search terms first.", "action": "generate_keywords", "action_input": {}},
            {
                "thought": "Search arXiv with the refined query.",
                "action": "search_arxiv",
                "action_input": {"query": "agentic code generation", "limit": 5},
            },
            {"thought": "Rank the candidate pool.", "action": "rank_candidates", "action_input": {}},
            {"thought": "Pick the best paper.", "action": "select_papers", "action_input": {"top_n": 1}},
            {"thought": "Read the PDF for richer evidence.", "action": "read_papers", "action_input": {}},
            {"thought": "Extract a structured card.", "action": "build_cards", "action_input": {}},
            {"thought": "Write the overview.", "action": "generate_report", "action_input": {}},
            {"thought": "The answer is ready.", "action": "finish", "action_input": {}},
        ]

        fake_llm = FakeReActLLM(actions)
        mock_llm_cls.return_value = fake_llm
        mock_load_settings.return_value = Settings(
            openai_api_key="test-key",
            openai_base_url=None,
            openai_model="gpt-4o-mini",
            openalex_email=None,
        )

        search_results = [
            Paper(
                title="Agentic Planning for Code Generation",
                abstract="We study planning-based agentic code generation.",
                year=2025,
                venue="arXiv",
                source="arxiv",
                pdf_url="https://example.com/paper.pdf",
            )
        ]
        mock_search_arxiv.return_value = search_results
        mock_rerank.side_effect = lambda task, papers, llm, top_n: papers[:top_n]

        def enrich_side_effect(papers, progress_callback=None, max_chars=20000):
            del progress_callback, max_chars
            for paper in papers:
                paper.full_text = "Full text"
                paper.full_text_excerpt = "Full text excerpt"
            return papers

        mock_enrich.side_effect = enrich_side_effect
        mock_build_card.return_value = PaperCard(
            title="Agentic Planning for Code Generation",
            year=2025,
            venue="arXiv",
            url="https://example.com",
            pdf_url="https://example.com/paper.pdf",
            pdf_path=None,
            relevance="high",
            problem="Code generation with agents",
            method="Planning",
            data_or_setting="Benchmarks",
            findings="Improved success rate",
            limitations="Single benchmark",
            tags=["agentic", "planning"],
            evidence_scope="title, abstract, and PDF full text excerpt",
        )
        mock_overview.return_value = "overview"

        with patch("paper_research_assistant.keywords.generate_keywords", return_value=["agentic code generation"]):
            result, paths = run_research(
                task="Survey agentic code generation",
                top_n=1,
                per_keyword=5,
                max_keywords=4,
                overview_words=200,
                parse_pdf_full_text=True,
                save_output=False,
            )

        self.assertIsNone(paths)
        self.assertEqual(result.keywords, ["agentic code generation"])
        self.assertEqual(len(result.selected), 1)
        self.assertEqual(result.selected[0].paper_id, "P1")
        self.assertEqual(result.overview, "overview")
        self.assertTrue(result.comparison_table)
        self.assertEqual(len(result.reasoning_trace), 8)
        self.assertEqual(result.reasoning_trace[0].action, "generate_keywords")
        self.assertEqual(result.reasoning_trace[-1].action, "finish")


if __name__ == "__main__":
    unittest.main()
