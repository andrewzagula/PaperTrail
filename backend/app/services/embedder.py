from openai import OpenAI

from app.config import settings
from app.services.vector_store import add_embeddings

EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 500
CHUNK_CHAR_SIZE = CHUNK_SIZE * 4
CHUNK_OVERLAP = 200


def chunk_text(text: str, chunk_size: int = CHUNK_CHAR_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:])
            break

        break_point = text.rfind("\n\n", start + chunk_size // 2, end)
        if break_point == -1:
            break_point = text.rfind(". ", start + chunk_size // 2, end)
            if break_point != -1:
                break_point += 1
        if break_point == -1:
            break_point = end

        chunks.append(text[start:break_point].strip())
        start = break_point - overlap

    return [c for c in chunks if c.strip()]


def generate_embeddings(texts: list[str]) -> list[list[float]]:
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

    batch_size = 100
    all_embeddings: list[list[float]] = []
    for i in range(0, len(all_texts), batch_size):
        batch = all_texts[i : i + batch_size]
        embeddings = generate_embeddings(batch)
        all_embeddings.extend(embeddings)

    add_embeddings(
        ids=all_ids,
        embeddings=all_embeddings,
        documents=all_texts,
        metadatas=all_metadatas,
    )

    return len(all_ids)
