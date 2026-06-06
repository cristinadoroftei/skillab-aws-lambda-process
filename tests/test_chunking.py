"""Local unit tests (no AWS calls needed)."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from app import chunk_text, lambda_handler  # noqa: E402


# ---------- chunking logic ----------

def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_short_text_is_single_chunk():
    chunks = chunk_text("hello world", size=500, overlap=50)
    assert len(chunks) == 1
    assert chunks[0]["text"] == "hello world"
    assert chunks[0]["index"] == 0


def test_long_text_is_split_with_overlap():
    text = "abcdefghij " * 200
    chunks = chunk_text(text, size=500, overlap=50)
    assert len(chunks) > 1
    assert all(chunks[i]["index"] == i for i in range(len(chunks)))
    total = sum(c["char_count"] for c in chunks)
    assert total >= len(text.strip())


def test_chunks_respect_size_limit():
    text = "word " * 1000
    size = 200
    chunks = chunk_text(text, size=size, overlap=20)
    assert all(c["char_count"] <= size + 50 for c in chunks)


def test_invalid_parameters_raise():
    import pytest
    with pytest.raises(ValueError):
        chunk_text("hi", size=0, overlap=0)
    with pytest.raises(ValueError):
        chunk_text("hi", size=100, overlap=100)


# ---------- handler routing ----------

def test_handler_detects_s3_event():
    """A typical S3 event should be routed to the S3 handler."""
    event = {
        "Records": [{
            "s3": {
                "bucket": {"name": "demo"},
                "object": {"key": "input/a.txt"}
            }
        }]
    }
    with patch("app.s3") as mock_s3:
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"hello world from S3")
        }
        result = lambda_handler(event, None)
    assert result["mode"] == "s3_event"
    assert result["processed"] == 1


def test_handler_manual_inline_text():
    """Manual invoke with inline text should not touch S3."""
    event = {"text": "Just some text. Another sentence. And one more."}
    result = lambda_handler(event, None)
    assert result["mode"] == "manual"
    assert result["processed"] == 1
    assert result["results"][0]["source"] == "inline"
    assert result["results"][0]["chunk_count"] >= 1


def test_handler_manual_with_explicit_keys():
    """Manual invoke with explicit list of S3 keys."""
    event = {"bucket": "demo-bucket", "keys": ["input/a.txt", "input/b.txt"]}
    with patch("app.s3") as mock_s3:
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"content")
        }
        result = lambda_handler(event, None)
    assert result["mode"] == "manual"
    assert result["processed"] == 2


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
