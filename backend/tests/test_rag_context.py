import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from app.services.rag_context import (
    _chunk_file,
    _cosine_similarity,
    _get_embedding,
    get_context_for_flag,
)


def test_cosine_similarity_identical_vectors():
    vec = [1.0, 2.0, 3.0]
    score = _cosine_similarity(vec, vec)
    assert pytest.approx(score, rel=1e-5) == 1.0


def test_cosine_similarity_orthogonal_vectors():
    vec_a = [1.0, 0.0]
    vec_b = [0.0, 1.0]
    assert _cosine_similarity(vec_a, vec_b) == 0.0


def test_cosine_similarity_zero_vector():
    vec_a = [0.0, 0.0]
    vec_b = [1.0, 2.0]
    assert _cosine_similarity(vec_a, vec_b) == 0.0


def test_chunk_file_creates_overlapping_chunks():
    # 100 lines of code
    lines = [f"line {i}" for i in range(100)]
    content = "\n".join(lines)
    chunks = _chunk_file(content)

    assert len(chunks) > 1
    # Check that chunks contain lines
    assert "line 0" in chunks[0]
    assert "line 39" in chunks[0]
    # Check overlap (step is 32 lines, so second chunk starts at line 32)
    assert "line 32" in chunks[1]


def test_chunk_file_empty_content():
    assert _chunk_file("") == []


def test_get_context_for_flag_no_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    flag = {
        "file": "app/auth.py",
        "hunk": "+def login(): pass",
        "tag": "auth_change",
        "matched_reason": "auth match",
    }
    context = get_context_for_flag(flag, owner="owner", repo="repo")
    assert context == ""


@patch("app.services.rag_context._fetch_file_content")
@patch("app.services.rag_context._get_embedding")
def test_get_context_for_flag_successful_retrieval(mock_embed, mock_fetch):
    # Mock file content
    file_content = "\n".join([f"def func_{i}():\n    return {i}" for i in range(50)])
    mock_fetch.return_value = file_content

    # Query embedding and chunk embeddings
    def fake_embed(text):
        if "login" in text or "auth" in text:
            return [1.0, 0.0, 0.0]
        return [0.0, 1.0, 0.0]

    mock_embed.side_effect = fake_embed

    flag = {
        "file": "app/auth.py",
        "hunk": "+def login_handler(): pass",
        "tag": "auth_change",
        "matched_reason": "auth match",
    }

    context = get_context_for_flag(flag, owner="myorg", repo="myrepo")
    assert "Broader codebase context" in context
    assert len(context) > 0
