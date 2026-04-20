from __future__ import annotations

from langchain_core.embeddings import Embeddings

from app.llm.providers.common import load_provider_dependency, raise_provider_request_error


def _load_huggingface_embeddings_class():
    module = load_provider_dependency(
        "langchain_huggingface",
        "langchain-huggingface",
    )
    return module.HuggingFaceEmbeddings


class SentenceTransformerEmbeddingClient:
    def __init__(self, *, default_model: str, device: str = ""):
        self.default_model = default_model
        self.device = device.strip()

    def _build_model(self) -> Embeddings:
        huggingface_embeddings = _load_huggingface_embeddings_class()
        kwargs = {"model_name": self.default_model}
        if self.device:
            kwargs["model_kwargs"] = {"device": self.device}
        return huggingface_embeddings(**kwargs)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            return self._build_model().embed_documents(texts)
        except Exception as error:
            raise_provider_request_error(
                "sentence-transformers",
                "embedding generation",
                error,
            )

    def embed_query(self, text: str) -> list[float]:
        try:
            return self._build_model().embed_query(text)
        except Exception as error:
            raise_provider_request_error(
                "sentence-transformers",
                "query embedding generation",
                error,
            )
