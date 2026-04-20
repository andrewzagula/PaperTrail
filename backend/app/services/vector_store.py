import chromadb
import hashlib
import re

from app.config import settings

_client: chromadb.ClientAPI | None = None
LEGACY_COLLECTION_NAME = "paper_sections"
COLLECTION_PREFIX = "paper_sections__"


def get_chroma_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return _client


def _normalize_collection_component(value: str, *, fallback: str, max_length: int) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    if not normalized:
        normalized = fallback
    return normalized[:max_length]


def get_active_collection_name() -> str:
    provider = _normalize_collection_component(
        settings.embedding_provider,
        fallback="unknown",
        max_length=12,
    )
    model = _normalize_collection_component(
        settings.embedding_model,
        fallback="default",
        max_length=16,
    )
    signature = hashlib.sha1(
        f"{settings.embedding_provider}::{settings.embedding_model}".encode("utf-8")
    ).hexdigest()[:8]
    return f"{COLLECTION_PREFIX}{provider}__{model}__{signature}"


def get_collection(name: str | None = None) -> chromadb.Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name or get_active_collection_name(),
        metadata={"hnsw:space": "cosine"},
    )


def add_embeddings(
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    collection = get_collection()
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )


def query_embeddings(
    query_embedding: list[float],
    paper_id: str | None = None,
    n_results: int = 5,
) -> dict:
    collection = get_collection()
    where_filter = {"paper_id": paper_id} if paper_id else None
    return collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )


def delete_by_paper(paper_id: str) -> None:
    client = get_chroma_client()
    collection_names = [str(name) for name in client.list_collections()]

    if LEGACY_COLLECTION_NAME not in collection_names:
        collection_names.append(LEGACY_COLLECTION_NAME)

    for collection_name in collection_names:
        if collection_name != LEGACY_COLLECTION_NAME and not collection_name.startswith(
            COLLECTION_PREFIX
        ):
            continue

        try:
            client.get_collection(collection_name).delete(where={"paper_id": paper_id})
        except Exception:
            continue


def delete_by_paper_from_collection(paper_id: str, collection_name: str) -> None:
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        return

    try:
        collection.delete(where={"paper_id": paper_id})
    except Exception:
        return


def delete_by_paper_from_active_collection(paper_id: str) -> None:
    delete_by_paper_from_collection(paper_id, get_active_collection_name())
