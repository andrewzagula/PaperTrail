"""Generate embeddings for paper sections and store in ChromaDB."""

from openai import OpenAI

from app.config import settings
from app.services.vector_store import add_embeddings

EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 500  # target tokens per chunk (approx 4 chars per token)
CHUNK_CHAR_SIZE = CHUNK_SIZE * 4  # rough character estimate
CHUNK_OVERLAP = 200  # character overlap between chunks


def chunk_text(text: str, chunk_size: int = CHUNK_CHAR_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks.

    Tries to break on paragraph boundaries, falls back to sentence
    boundaries, then hard character splits.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:])
            break

        # Try to break at a paragraph boundary
        break_point = text.rfind("\n\n", start + chunk_size // 2, end)
        if break_point == -1:
            # Try sentence boundary
            break_point = text.rfind(". ", start + chunk_size // 2, end)
            if break_point != -1:
                break_point += 1  # include the period
        if break_point == -1:
            break_point = end

        chunks.append(text[start:break_point].strip())
        start = break_point - overlap

    return [c for c in chunks if c.strip()]


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts using OpenAI."""
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def embed_and_store_sections(
    paper_id: str,
    sections: list[dict],
) -> int:
    """Chunk sections, generate embeddings, and store in ChromaDB.

    Args:
        paper_id: UUID of the paper (as string).
        sections: List of dicts with "id", "title", "content".

    Returns:
        Number of chunks embedded.
    """
    all_ids: list[str] = []
    all_texts: list[str] = []
    all_metadatas: list[dict] = []

    for section in sections:
        chunks = chunk_text(section["content"])
        for i, chunk in enumerate(chunks):
            chunk_id = f"{section['id']}_chunk_{i}"
            all_ids.append(chunk_id)
            all_texts.append(chunk)
            all_metadatas.append({
                "paper_id": paper_id,
                "section_id": section["id"],
                "section_title": section["title"],
                "chunk_index": i,
            })

    if not all_texts:
        return 0

    # Generate embeddings in batches (OpenAI supports up to 2048 inputs)
    batch_size = 100
    all_embeddings: list[list[float]] = []
    for i in range(0, len(all_texts), batch_size):
        batch = all_texts[i : i + batch_size]
        embeddings = generate_embeddings(batch)
        all_embeddings.extend(embeddings)

    # Store in ChromaDB
    add_embeddings(
        ids=all_ids,
        embeddings=all_embeddings,
        documents=all_texts,
        metadatas=all_metadatas,
    )

    return len(all_ids)
