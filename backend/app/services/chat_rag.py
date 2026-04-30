from app.config import settings
from app.llm import get_structured_client
from app.services.embedder import generate_query_embedding
from app.services.vector_store import query_embeddings

MAX_HISTORY_MESSAGES = 20
MAX_CONTEXT_CHUNKS = 5
COULD_NOT_ANSWER_FROM_RETRIEVED_CONTEXT = "Could not answer from retrieved context."
CHAT_RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "section_title": {"type": "string"},
                    "excerpt": {"type": "string"},
                },
                "required": ["section_title", "excerpt"],
            },
        },
    },
    "required": ["answer", "citations"],
}

SYSTEM_PROMPT = (
    "You are a research paper assistant. Answer questions about the paper based "
    "ONLY on the provided context sections. Be specific and cite which sections "
    "your answer comes from.\n\n"
    "Rules:\n"
    "- Only use information from the provided context\n"
    "- If the context doesn't contain enough information to answer, start the answer with "
    f"'{COULD_NOT_ANSWER_FROM_RETRIEVED_CONTEXT}' and say what is missing\n"
    "- Reference sections by their title when citing (e.g., 'According to the Methods section...')\n"
    "- Be concise but thorough\n\n"
    "You MUST respond with a JSON object containing:\n"
    '- "answer": your response text (string)\n'
    '- "citations": list of objects with "section_title" and "excerpt" (a short '
    "verbatim quote from that section supporting your claim)\n\n"
    "If you cannot answer from the context, return an empty citations list."
)


def _build_context(chunks: dict) -> tuple[str, list[dict]]:
    if not chunks or not chunks.get("documents") or not chunks["documents"][0]:
        return "", []

    documents = chunks["documents"][0]
    metadatas = chunks["metadatas"][0]
    distances = chunks["distances"][0]

    context_parts = []
    sources = []

    for doc, meta, dist in zip(documents, metadatas, distances):
        section_title = meta.get("section_title", "Unknown")
        context_parts.append(f"[Section: {section_title}]\n{doc}")
        sources.append({
            "section_id": meta.get("section_id", ""),
            "section_title": section_title,
            "distance": dist,
        })

    return "\n\n---\n\n".join(context_parts), sources


def _format_history(history: list[dict]) -> list[dict]:
    messages = []
    for msg in history[-MAX_HISTORY_MESSAGES:]:
        role = msg["role"]
        if role == "assistant":
            content = msg.get("content", "")
        else:
            content = msg.get("content", "")
        messages.append({"role": role, "content": content})
    return messages


def _build_empty_context_response(embedding_status: str | None) -> dict:
    if embedding_status == "stale":
        answer = (
            f"{COULD_NOT_ANSWER_FROM_RETRIEVED_CONTEXT} "
            "I couldn't retrieve sections for this paper with the currently configured "
            "embedding backend. The paper has embeddings from a different backend or model, "
            "so it should be re-embedded before relying on retrieval."
        )
    elif embedding_status == "missing":
        answer = (
            f"{COULD_NOT_ANSWER_FROM_RETRIEVED_CONTEXT} "
            "I couldn't retrieve sections for this paper because it does not have embeddings "
            "for the currently configured embedding backend yet. Re-embed the paper and try again."
        )
    elif embedding_status == "failed":
        answer = (
            f"{COULD_NOT_ANSWER_FROM_RETRIEVED_CONTEXT} "
            "I couldn't retrieve sections for this paper because the last embedding attempt "
            "for the current backend failed. Fix the provider issue and re-embed the paper."
        )
    else:
        answer = (
            f"{COULD_NOT_ANSWER_FROM_RETRIEVED_CONTEXT} "
            "I couldn't find relevant sections in this paper to answer your question. "
            "The question may be outside the paper's scope, or retrieval may not have found "
            "relevant passages for it."
        )

    return {
        "answer": answer,
        "citations": [],
    }


def _build_uncited_context_response() -> dict:
    return {
        "answer": (
            f"{COULD_NOT_ANSWER_FROM_RETRIEVED_CONTEXT} "
            "The retrieved sections did not produce citation-backed support for this "
            "answer, so I am not presenting unsupported claims."
        ),
        "citations": [],
    }


def generate_chat_response(
    paper_id: str,
    paper_title: str,
    query: str,
    history: list[dict],
    embedding_status: str | None = None,
) -> dict:
    query_embedding = generate_query_embedding(query)

    chunks = query_embeddings(
        query_embedding=query_embedding,
        paper_id=paper_id,
        n_results=MAX_CONTEXT_CHUNKS,
    )

    context_text, sources = _build_context(chunks)

    if not context_text:
        return _build_empty_context_response(embedding_status)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append({
        "role": "system",
        "content": f"Paper: {paper_title}\n\nRelevant sections:\n\n{context_text}",
    })

    messages.extend(_format_history(history))

    messages.append({"role": "user", "content": query})

    result = get_structured_client().generate_structured(
        model=settings.chat_model,
        temperature=0.3,
        schema_name="paper_chat_response",
        schema=CHAT_RESPONSE_JSON_SCHEMA,
        messages=messages,
    )

    answer = result.get("answer", "")
    citations = result.get("citations", [])
    if not citations:
        return _build_uncited_context_response()

    for citation in citations:
        title = citation.get("section_title", "")
        for source in sources:
            if source["section_title"] == title:
                citation["section_id"] = source["section_id"]
                break

    return {"answer": answer, "citations": citations}
