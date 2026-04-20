import unittest
from unittest.mock import patch

from app.config import settings
from app.services import vector_store


class FakeCollection:
    def __init__(self, name: str):
        self.name = name
        self.add_calls = []
        self.query_calls = []
        self.delete_calls = []

    def add(self, **kwargs):
        self.add_calls.append(kwargs)

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)


class FakeChromaClient:
    def __init__(self, list_names=None):
        self.collections = {}
        self.list_names = list_names or []
        self.get_or_create_calls = []
        self.get_collection_calls = []

    def get_or_create_collection(self, name, metadata):
        self.get_or_create_calls.append((name, metadata))
        collection = self.collections.setdefault(name, FakeCollection(name))
        return collection

    def get_collection(self, name):
        self.get_collection_calls.append(name)
        return self.collections.setdefault(name, FakeCollection(name))

    def list_collections(self):
        return self.list_names


class VectorStoreTests(unittest.TestCase):
    def test_active_collection_name_changes_with_provider_and_model(self):
        with patch.object(settings, "embedding_provider", "openai"), patch.object(
            settings,
            "embedding_model",
            "text-embedding-3-small",
        ):
            openai_name = vector_store.get_active_collection_name()

        with patch.object(
            settings,
            "embedding_provider",
            "sentence_transformers",
        ), patch.object(
            settings,
            "embedding_model",
            "sentence-transformers/all-MiniLM-L6-v2",
        ):
            local_name = vector_store.get_active_collection_name()

        self.assertNotEqual(openai_name, local_name)
        self.assertTrue(openai_name.startswith(vector_store.COLLECTION_PREFIX))
        self.assertTrue(local_name.startswith(vector_store.COLLECTION_PREFIX))

    def test_add_embeddings_uses_active_namespaced_collection(self):
        client = FakeChromaClient()

        with patch.object(
            settings,
            "embedding_provider",
            "sentence_transformers",
        ), patch.object(
            settings,
            "embedding_model",
            "sentence-transformers/all-MiniLM-L6-v2",
        ), patch("app.services.vector_store.get_chroma_client", return_value=client):
            vector_store.add_embeddings(
                ids=["chunk-1"],
                embeddings=[[0.1, 0.2]],
                documents=["hello"],
                metadatas=[{"paper_id": "paper-1"}],
            )
            expected_name = vector_store.get_active_collection_name()

        self.assertEqual(client.get_or_create_calls[0][0], expected_name)
        self.assertEqual(
            client.collections[expected_name].add_calls[0]["ids"],
            ["chunk-1"],
        )

    def test_query_embeddings_uses_only_active_namespaced_collection(self):
        client = FakeChromaClient()

        with patch.object(settings, "embedding_provider", "openai"), patch.object(
            settings,
            "embedding_model",
            "text-embedding-3-small",
        ), patch("app.services.vector_store.get_chroma_client", return_value=client):
            vector_store.query_embeddings(
                query_embedding=[0.1, 0.2],
                paper_id="paper-1",
                n_results=3,
            )
            expected_name = vector_store.get_active_collection_name()

        self.assertEqual(client.get_or_create_calls[0][0], expected_name)
        self.assertEqual(len(client.collections[expected_name].query_calls), 1)
        self.assertEqual(
            client.collections[expected_name].query_calls[0]["where"],
            {"paper_id": "paper-1"},
        )

    def test_delete_by_paper_cleans_all_papertrail_collections(self):
        client = FakeChromaClient(
            list_names=[
                "paper_sections__openai__abc",
                "paper_sections__sentence_transformers__def",
                "unrelated_collection",
            ]
        )

        with patch("app.services.vector_store.get_chroma_client", return_value=client):
            vector_store.delete_by_paper("paper-1")

        self.assertEqual(
            client.collections["paper_sections__openai__abc"].delete_calls,
            [{"where": {"paper_id": "paper-1"}}],
        )
        self.assertEqual(
            client.collections["paper_sections__sentence_transformers__def"].delete_calls,
            [{"where": {"paper_id": "paper-1"}}],
        )
        self.assertEqual(
            client.collections["paper_sections"].delete_calls,
            [{"where": {"paper_id": "paper-1"}}],
        )
        self.assertNotIn("unrelated_collection", client.get_collection_calls)

    def test_delete_by_paper_from_active_collection_targets_only_active_collection(self):
        client = FakeChromaClient(
            list_names=[
                "paper_sections__openai__abc",
                "paper_sections__sentence_transformers__def",
            ]
        )

        with patch.object(settings, "embedding_provider", "openai"), patch.object(
            settings,
            "embedding_model",
            "text-embedding-3-small",
        ), patch("app.services.vector_store.get_chroma_client", return_value=client):
            expected_name = vector_store.get_active_collection_name()
            vector_store.delete_by_paper_from_active_collection("paper-1")

        self.assertEqual(
            client.collections[expected_name].delete_calls,
            [{"where": {"paper_id": "paper-1"}}],
        )
        self.assertEqual(client.get_collection_calls, [expected_name])


if __name__ == "__main__":
    unittest.main()
