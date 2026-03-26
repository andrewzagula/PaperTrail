import chromadb

from app.config import settings

_client: chromadb.ClientAPI | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return _client


def get_collection(name: str = "paper_sections") -> chromadb.Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name,
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
    collection = get_collection()
    collection.delete(where={"paper_id": paper_id})
