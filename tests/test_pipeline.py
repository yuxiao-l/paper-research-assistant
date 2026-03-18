import unittest
from types import SimpleNamespace
from unittest.mock import patch

from paper_research_assistant.cards import build_card
from paper_research_assistant.config import Settings
from paper_research_assistant.errors import LLMConfigurationError, SearchProviderError
from paper_research_assistant.llm import LLMClient
from paper_research_assistant.models import Paper
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
            search_papers(["agent"], per_keyword=2, settings=settings)

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


if __name__ == "__main__":
    unittest.main()
