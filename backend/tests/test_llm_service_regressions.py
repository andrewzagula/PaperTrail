import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.config import settings
from app.services.arxiv_searcher import ArxivResult
from app.services.analyzer import analyze_paper
from app.services.chat_rag import generate_chat_response
from app.services.discovery import generate_search_queries, rank_results
from app.services.embedder import generate_query_embedding
from app.services.paper_compare import (
    extract_compare_profile_details,
    generate_comparison_synthesis,
)


class DiscoveryServiceRegressionTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.discovery.get_structured_client")
    async def test_generate_search_queries_unwraps_queries_payload(self, mock_get_structured_client):
        client = Mock()
        client.generate_structured.return_value = {
            "queries": ["transformer pruning", "model sparsity", "efficient inference"],
        }
        mock_get_structured_client.return_value = client

        queries = await generate_search_queries("How do I prune transformer models?", max_queries=2)

        self.assertEqual(queries, ["transformer pruning", "model sparsity"])
        self.assertEqual(
            client.generate_structured.call_args.kwargs["schema_name"],
            "discovery_queries",
        )
        self.assertEqual(
            client.generate_structured.call_args.kwargs["model"],
            settings.discovery_query_model,
        )

    @patch("app.services.discovery.get_structured_client")
    async def test_rank_results_unwraps_rankings_payload(self, mock_get_structured_client):
        client = Mock()
        client.generate_structured.return_value = {
            "rankings": [
                {"index": 1, "score": 0.91, "reason": "Most directly addresses the question."},
                {"index": 0, "score": 0.52, "reason": "Relevant baseline."},
            ],
        }
        mock_get_structured_client.return_value = client

        ranked = await rank_results(
            "How do I prune transformer models?",
            results=[
                ArxivResult(
                    arxiv_id="1234.5678",
                    title="Baseline Paper",
                    authors="Author A",
                    abstract="baseline abstract",
                    published="2024-01-01",
                ),
                ArxivResult(
                    arxiv_id="2345.6789",
                    title="Pruning Paper",
                    authors="Author B",
                    abstract="pruning abstract",
                    published="2024-02-01",
                ),
            ],
            max_return=1,
        )

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["title"], "Pruning Paper")
        self.assertEqual(
            client.generate_structured.call_args.kwargs["schema_name"],
            "discovery_rankings",
        )
        self.assertEqual(
            client.generate_structured.call_args.kwargs["model"],
            settings.discovery_rank_model,
        )

    @patch("app.services.discovery.get_structured_client")
    async def test_generate_search_queries_uses_configured_workflow_model(
        self,
        mock_get_structured_client,
    ):
        client = Mock()
        client.generate_structured.return_value = {"queries": ["q1", "q2"]}
        mock_get_structured_client.return_value = client

        with patch.object(settings, "discovery_query_model", "provider-query-model"):
            await generate_search_queries("How do I prune transformer models?")

        self.assertEqual(
            client.generate_structured.call_args.kwargs["model"],
            "provider-query-model",
        )

    @patch("app.services.discovery.get_structured_client")
    async def test_rank_results_uses_configured_workflow_model(self, mock_get_structured_client):
        client = Mock()
        client.generate_structured.return_value = {
            "rankings": [{"index": 0, "score": 0.75, "reason": "Relevant"}],
        }
        mock_get_structured_client.return_value = client

        with patch.object(settings, "discovery_rank_model", "provider-rank-model"):
            await rank_results(
                "How do I prune transformer models?",
                results=[
                    ArxivResult(
                        arxiv_id="1234.5678",
                        title="Pruning Paper",
                        authors="Author B",
                        abstract="pruning abstract",
                        published="2024-02-01",
                    ),
                ],
                max_return=1,
            )

        self.assertEqual(
            client.generate_structured.call_args.kwargs["model"],
            "provider-rank-model",
        )


class StructuredWorkflowModelRegressionTests(unittest.TestCase):
    @patch("app.services.analyzer.get_structured_client")
    def test_analyze_paper_uses_configured_workflow_model(self, mock_get_structured_client):
        client = Mock()
        client.generate_structured.return_value = {
            "problem": "p",
            "method": "m",
            "key_contributions": "k",
            "results": "r",
            "limitations": "l",
            "future_work": "f",
        }
        mock_get_structured_client.return_value = client

        with patch.object(settings, "analysis_model", "provider-analysis-model"):
            analyze_paper(
                title="Test Paper",
                abstract="Test abstract",
                sections=[{"title": "Method", "content": "Test content"}],
            )

        self.assertEqual(
            client.generate_structured.call_args.kwargs["model"],
            "provider-analysis-model",
        )

    @patch("app.services.analyzer.get_structured_client")
    def test_analyze_paper_includes_section_content_in_prompt(self, mock_get_structured_client):
        client = Mock()
        client.generate_structured.return_value = {
            "problem": "p",
            "method": "m",
            "key_contributions": "k",
            "results": "r",
            "limitations": "l",
            "future_work": "f",
        }
        mock_get_structured_client.return_value = client

        analyze_paper(
            title="Test Paper",
            abstract="Test abstract",
            sections=[{"title": "Method", "content": "Unique section evidence"}],
        )

        user_message = client.generate_structured.call_args.kwargs["messages"][1]["content"]
        self.assertIn("## Method", user_message)
        self.assertIn("Unique section evidence", user_message)

    @patch("app.services.chat_rag.get_structured_client")
    @patch("app.services.chat_rag.query_embeddings")
    @patch("app.services.chat_rag.generate_query_embedding")
    def test_generate_chat_response_uses_configured_workflow_model(
        self,
        mock_generate_query_embedding,
        mock_query_embeddings,
        mock_get_structured_client,
    ):
        mock_generate_query_embedding.return_value = [0.1, 0.2]
        mock_query_embeddings.return_value = {
            "documents": [["Quoted section text"]],
            "metadatas": [[{"section_id": "sec-1", "section_title": "Method"}]],
            "distances": [[0.01]],
        }
        client = Mock()
        client.generate_structured.return_value = {
            "answer": "Answer",
            "citations": [{"section_title": "Method", "excerpt": "Quoted section text"}],
        }
        mock_get_structured_client.return_value = client

        with patch.object(settings, "chat_model", "provider-chat-model"):
            response = generate_chat_response(
                paper_id="paper-1",
                paper_title="Test Paper",
                query="What is the method?",
                history=[],
            )

        self.assertEqual(response["answer"], "Answer")
        self.assertEqual(
            client.generate_structured.call_args.kwargs["model"],
            "provider-chat-model",
        )

    @patch("app.services.chat_rag.query_embeddings")
    @patch("app.services.chat_rag.generate_query_embedding")
    def test_generate_chat_response_mentions_reembedding_when_status_is_stale(
        self,
        mock_generate_query_embedding,
        mock_query_embeddings,
    ):
        mock_generate_query_embedding.return_value = [0.1, 0.2]
        mock_query_embeddings.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

        response = generate_chat_response(
            paper_id="paper-1",
            paper_title="Test Paper",
            query="What is the method?",
            history=[],
            embedding_status="stale",
        )

        self.assertIn("re-embedded", response["answer"])
        self.assertEqual(response["citations"], [])

    @patch("app.services.chat_rag.query_embeddings")
    @patch("app.services.chat_rag.generate_query_embedding")
    def test_generate_chat_response_mentions_missing_embeddings_when_status_is_missing(
        self,
        mock_generate_query_embedding,
        mock_query_embeddings,
    ):
        mock_generate_query_embedding.return_value = [0.1, 0.2]
        mock_query_embeddings.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

        response = generate_chat_response(
            paper_id="paper-1",
            paper_title="Test Paper",
            query="What is the method?",
            history=[],
            embedding_status="missing",
        )

        self.assertIn("does not have embeddings", response["answer"])
        self.assertEqual(response["citations"], [])

    @patch("app.services.paper_compare.get_structured_client")
    def test_extract_compare_profile_details_uses_configured_workflow_model(
        self,
        mock_get_structured_client,
    ):
        client = Mock()
        client.generate_structured.return_value = {
            "problem": "p",
            "method": "m",
            "dataset_or_eval_setup": "d",
            "key_results": "r",
            "strengths": "s",
            "weaknesses": "w",
            "evidence_notes": {
                "problem": [],
                "method": [],
                "dataset_or_eval_setup": [],
                "key_results": [],
                "strengths": [],
                "weaknesses": [],
            },
            "warnings": [],
        }
        mock_get_structured_client.return_value = client

        with patch.object(settings, "compare_profile_model", "provider-compare-profile"):
            extract_compare_profile_details(
                title="Test Paper",
                abstract="Test abstract",
                breakdown={"problem": "p"},
                sections=[
                    SimpleNamespace(
                        section_title="Method",
                        section_order=0,
                        content="Method content",
                    )
                ],
            )

        self.assertEqual(
            client.generate_structured.call_args.kwargs["model"],
            "provider-compare-profile",
        )

    @patch("app.services.paper_compare.get_structured_client")
    def test_generate_comparison_synthesis_uses_configured_workflow_model(
        self,
        mock_get_structured_client,
    ):
        client = Mock()
        client.generate_structured.return_value = {
            "problem_landscape": "p",
            "method_divergence": "m",
            "evaluation_differences": "e",
            "researcher_tradeoffs": "t",
            "warnings": [],
        }
        mock_get_structured_client.return_value = client

        with patch.object(settings, "compare_synthesis_model", "provider-compare-synthesis"):
            generate_comparison_synthesis(
                [{"title": "Paper One", "problem": "p", "warnings": [], "evidence_notes": {}}]
            )

        self.assertEqual(
            client.generate_structured.call_args.kwargs["model"],
            "provider-compare-synthesis",
        )


class EmbedderServiceRegressionTests(unittest.TestCase):
    @patch("app.services.embedder.get_embedding_client")
    def test_generate_query_embedding_uses_embed_query(self, mock_get_embedding_client):
        client = Mock()
        client.embed_query.return_value = [0.1, 0.2, 0.3]
        mock_get_embedding_client.return_value = client

        embedding = generate_query_embedding("what is retrieval augmentation?")

        self.assertEqual(embedding, [0.1, 0.2, 0.3])
        client.embed_query.assert_called_once_with("what is retrieval augmentation?")
        client.embed_texts.assert_not_called()


if __name__ == "__main__":
    unittest.main()
