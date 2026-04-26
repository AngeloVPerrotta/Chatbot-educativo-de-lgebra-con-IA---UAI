import json
import re
from pathlib import Path

_chunks = None


def _load_chunks() -> list:
    global _chunks
    if _chunks is None:
        path = Path(__file__).parent.parent / "knowledge" / "algebra_chunks.json"
        with open(path, encoding="utf-8") as f:
            _chunks = json.load(f)
    return _chunks


def _tokenize(text: str) -> set:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = set(text.split())
    stopwords = {"el", "la", "los", "las", "de", "del", "en", "un", "una", "que",
                 "es", "son", "se", "con", "por", "para", "como", "qué", "cómo",
                 "a", "al", "y", "o", "si", "no", "me", "te", "le", "su", "sus"}
    return tokens - stopwords


def retrieve_context(query: str, top_k: int = 3) -> str:
    chunks = _load_chunks()
    query_tokens = _tokenize(query)

    if not query_tokens:
        return ""

    scores = []
    for chunk in chunks:
        topic_tokens = _tokenize(chunk["topic"].replace("_", " "))
        content_tokens = _tokenize(chunk["content"])
        candidate_tokens = topic_tokens | content_tokens

        score = len(query_tokens & candidate_tokens)
        # Bonus si la query hace match directo con el topic
        if query_tokens & topic_tokens:
            score += 3

        scores.append((score, chunk))

    scores.sort(key=lambda x: x[0], reverse=True)
    top_chunks = [chunk for score, chunk in scores[:top_k] if score > 0]

    if not top_chunks:
        return ""

    parts = []
    for chunk in top_chunks:
        parts.append(f"[{chunk['topic']}] {chunk['content']}")

    return "\n\n".join(parts)
