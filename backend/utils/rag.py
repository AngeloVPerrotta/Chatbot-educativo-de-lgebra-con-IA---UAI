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


def retrieve_context(query: str, top_k: int = 3) -> tuple:
    """Returns (context_text, max_score). context_text is empty string if no results."""
    chunks = _load_chunks()
    query_tokens = _tokenize(query)

    if not query_tokens:
        return "", 0.0

    scores = []
    for chunk in chunks:
        tema_tokens    = _tokenize(chunk["tema"])
        clase_tokens   = _tokenize(chunk["clase"])
        content_tokens = _tokenize(chunk["contenido"])
        keyword_tokens = set(chunk.get("keywords", []))
        candidate_tokens = tema_tokens | content_tokens

        score = len(query_tokens & candidate_tokens)
        # Bonus por match directo en tema o clase
        if query_tokens & tema_tokens:
            score += 3
        if query_tokens & clase_tokens:
            score += 1
        # Bonus por match en keywords explícitas
        if query_tokens & keyword_tokens:
            score += 2

        scores.append((score, chunk))

    scores.sort(key=lambda x: x[0], reverse=True)
    top_chunks = [chunk for score, chunk in scores[:top_k] if score > 0]

    if not top_chunks:
        return "", 0.0

    max_score = float(scores[0][0])
    parts = []
    for chunk in top_chunks:
        parts.append(f"[{chunk['clase']} | {chunk['tema']}]\n{chunk['contenido']}")

    return "\n\n".join(parts), max_score
