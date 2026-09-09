from __future__ import annotations

"""
RAG (Retrieval-Augmented Generation) context service.

For each flagged file in a PR, this module:
1. Fetches the full file content from the GitHub Contents API.
2. Splits the file into overlapping chunks (~40 lines each).
3. Embeds each chunk using the Gemini text-embedding model.
4. Embeds the flag's diff hunk (the "query").
5. Finds the top-2 most similar chunks via cosine similarity.
6. Returns a formatted context string that is injected into the LLM prompt,
   giving the model broader codebase understanding — not just the isolated diff.

This is the classic RAG pattern:
    query (diff hunk) → embedding → cosine similarity → top-k retrieval → LLM prompt enrichment

Falls back to an empty string (no context) if:
- GEMINI_API_KEY is not set
- The GitHub API returns an error for the file fetch
- The file is binary or too large
"""

import base64
import logging
import math
import os
from typing import Optional

import httpx

from app.services.heuristics import Flag

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
_CHUNK_LINES = 40       # lines per chunk
_OVERLAP_LINES = 8      # overlap between consecutive chunks
_TOP_K = 2              # number of top chunks to retrieve
_MAX_FILE_BYTES = 200_000  # skip files larger than 200 KB
_EMBEDDING_MODEL = "models/embedding-001"


# ── Embedding ─────────────────────────────────────────────────────────────────

def _get_embedding(text: str) -> list[float] | None:
    """
    Call the Gemini embedding API and return the embedding vector.
    Returns None on failure (triggers fallback — no context injected).
    """
    try:
        import google.generativeai as genai
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        result = genai.embed_content(
            model=_EMBEDDING_MODEL,
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
        )
        return result["embedding"]
    except Exception:
        logger.debug("Gemini embedding call failed", exc_info=True)
        return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure numpy-free cosine similarity using math module."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── File fetching ─────────────────────────────────────────────────────────────

def _fetch_file_content(
    owner: str,
    repo: str,
    path: str,
    token: Optional[str] = None,
) -> str | None:
    """
    Fetch the raw text content of a file from the GitHub Contents API.
    Returns None if the file is too large, binary, or the request fails.
    """
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        with httpx.Client(base_url=GITHUB_API_BASE, headers=headers, timeout=10.0) as client:
            response = client.get(f"/repos/{owner}/{repo}/contents/{path}")
        if response.status_code != 200:
            return None

        data = response.json()
        if isinstance(data, list):
            return None  # directory, not a file
        if data.get("encoding") != "base64":
            return None
        if data.get("size", 0) > _MAX_FILE_BYTES:
            logger.debug("Skipping RAG for large file: %s (%d bytes)", path, data["size"])
            return None

        raw = base64.b64decode(data["content"].replace("\n", "")).decode("utf-8", errors="replace")
        return raw
    except Exception:
        logger.debug("Failed to fetch file content for RAG: %s", path, exc_info=True)
        return None


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_file(content: str) -> list[str]:
    """Split file content into overlapping chunks of ~CHUNK_LINES lines."""
    lines = content.splitlines()
    chunks: list[str] = []
    step = _CHUNK_LINES - _OVERLAP_LINES
    for i in range(0, len(lines), step):
        chunk = "\n".join(lines[i : i + _CHUNK_LINES])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


# ── RAG main function ─────────────────────────────────────────────────────────

def get_context_for_flag(
    flag: Flag,
    owner: str,
    repo: str,
    token: Optional[str] = None,
) -> str:
    """
    Given a flag and repo coordinates, fetch the flagged file, embed its chunks,
    and return the top-K most relevant chunks as a formatted context string.

    Returns an empty string if RAG is unavailable (no API key, file fetch failure,
    embedding failure) — the LLM prompt is used as-is in that case.
    """
    file_path = flag.get("file", "")
    query_text = flag.get("hunk", "") or flag.get("matched_reason", "")

    if not file_path or not query_text:
        return ""

    # 1. Fetch full file content
    content = _fetch_file_content(owner, repo, file_path, token=token)
    if not content:
        return ""

    # 2. Chunk the file
    chunks = _chunk_file(content)
    if not chunks:
        return ""

    # 3. Embed the query (diff hunk)
    query_embedding = _get_embedding(query_text)
    if query_embedding is None:
        return ""

    # 4. Embed each chunk and compute cosine similarity
    scored_chunks: list[tuple[float, str]] = []
    for chunk in chunks:
        chunk_embedding = _get_embedding(chunk)
        if chunk_embedding is None:
            continue
        score = _cosine_similarity(query_embedding, chunk_embedding)
        scored_chunks.append((score, chunk))

    if not scored_chunks:
        return ""

    # 5. Select top-K chunks by similarity score
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    top_chunks = [chunk for _, chunk in scored_chunks[:_TOP_K]]

    # 6. Format as context block for the LLM prompt
    context_lines: list[str] = []
    for i, chunk in enumerate(top_chunks):

        context_lines.append(
            f"--- Broader codebase context (retrieved chunk {i + 1}/{len(top_chunks)}) ---"
        )
        context_lines.append(chunk)
        context_lines.append("")

    return "\n".join(context_lines).strip()

