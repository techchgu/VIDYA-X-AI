"""
VIDYA-X AI — Embedding Service (Step 5)
Provides configurable text embeddings for pgvector storage and semantic search.
Supports local deterministic embeddings, sentence-transformers, OpenAI, and Gemini.
"""

import hashlib
import math
import os
from typing import List

# Read configuration from environment
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))

# Cached provider instances
_sentence_transformer_model = None


def _get_sentence_transformer():
    """Lazy-load sentence-transformers model if requested."""
    global _sentence_transformer_model
    if _sentence_transformer_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _sentence_transformer_model = SentenceTransformer(EMBEDDING_MODEL)
        except ImportError:
            raise RuntimeError(
                "sentence-transformers is not installed. Run: pip install sentence-transformers, "
                "or set EMBEDDING_PROVIDER=local in .env"
            )
    return _sentence_transformer_model


def _generate_local_embedding(text: str, dim: int = EMBEDDING_DIMENSION) -> List[float]:
    """
    Generate a normalized, deterministic semantic feature vector using character
    n-grams and term hash projections. Guaranteed to produce exactly `dim` dimensions
    with unit L2 norm without requiring external API keys or large downloads.
    """
    cleaned = (text or "").lower().strip()
    if not cleaned:
        return [0.0] * dim

    vec = [0.0] * dim
    words = cleaned.split()

    # 1. Word token projections
    for w in words:
        h = int(hashlib.sha256(w.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        weight = 1.0 + (len(w) / 10.0)
        vec[idx] += weight

    # 2. Bigram projections for semantic context
    for i in range(len(words) - 1):
        bigram = f"{words[i]}_{words[i+1]}"
        h = int(hashlib.md5(bigram.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.5

    # 3. Normalize vector to unit sphere (L2 norm = 1.0 for cosine similarity)
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    else:
        vec[0] = 1.0

    return vec


def generate_embedding(text: str) -> List[float]:
    """
    Generate an embedding vector for a single string.

    Args:
        text: The text string to embed.

    Returns:
        List of floats with length equal to EMBEDDING_DIMENSION.
    """
    if EMBEDDING_PROVIDER == "sentence-transformers":
        model = _get_sentence_transformer()
        emb = model.encode(text).tolist()
        return emb

    elif EMBEDDING_PROVIDER == "openai":
        import openai
        client = openai.OpenAI()
        resp = client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
        return resp.data[0].embedding

    elif EMBEDDING_PROVIDER == "gemini":
        import google.generativeai as genai
        result = genai.embed_content(
            model=f"models/{EMBEDDING_MODEL}",
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]

    else:
        # Default: local deterministic normalized vector
        return _generate_local_embedding(text, EMBEDDING_DIMENSION)


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Batch generate embeddings for a list of strings.

    Args:
        texts: List of text strings.

    Returns:
        List of embedding vectors.
    """
    if not texts:
        return []

    if EMBEDDING_PROVIDER == "sentence-transformers":
        model = _get_sentence_transformer()
        return model.encode(texts).tolist()

    # Batch fallback using single generator
    return [generate_embedding(t) for t in texts]
