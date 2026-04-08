"""Tests for Stage 2 — Wiki Compilation Engine (non-LLM parts)."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from adversarial_wiki.compiler import (
    _extract_summary,
    _combine_sources,
    compile_wiki,
)
from adversarial_wiki.utils import slugify, extract_json as _extract_json
from adversarial_wiki.sources import read_sources_from_dir


# ---------------------------------------------------------------------------
# slugify (now in utils)
# ---------------------------------------------------------------------------

def test_slugify_basic():
    assert slugify("Remote Work Productivity") == "remote-work-productivity"

def test_slugify_special_chars():
    assert slugify("Work/Life Balance!") == "worklife-balance"

def test_slugify_truncates():
    long = "a" * 100
    assert len(slugify(long)) <= 60

def test_slugify_empty_punctuation():
    assert slugify("!!!") == ""


# ---------------------------------------------------------------------------
# _extract_json (bracket-matching)
# ---------------------------------------------------------------------------

def test_extract_json_array():
    text = 'Some preamble ["Concept A", "Concept B"] trailing'
    assert json.loads(_extract_json(text)) == ["Concept A", "Concept B"]

def test_extract_json_no_match():
    result = _extract_json("no json here")
    assert result == "no json here"

def test_extract_json_nested():
    text = 'prefix [["a", "b"], ["c"]] suffix'
    result = json.loads(_extract_json(text))
    assert result == [["a", "b"], ["c"]]

def test_extract_json_does_not_over_capture():
    # Two separate arrays — should only return the first complete one
    text = '["first"] and then ["second"]'
    result = json.loads(_extract_json(text))
    assert result == ["first"]

def test_extract_json_object():
    text = 'here is {"key": "value"} done'
    result = json.loads(_extract_json(text))
    assert result == {"key": "value"}


# ---------------------------------------------------------------------------
# _extract_summary
# ---------------------------------------------------------------------------

def test_extract_summary_from_section():
    body = "## Overview\nSome intro.\n\n## Summary\nThis is sentence one. This is sentence two. This is sentence three. Fourth sentence.\n"
    summary = _extract_summary(body, "Test Concept")
    assert "sentence one" in summary
    assert "Fourth" not in summary  # truncated to 3

def test_extract_summary_fallback():
    body = "## Overview\nFirst paragraph content here. More info."
    summary = _extract_summary(body, "Test Concept")
    assert "First paragraph" in summary

def test_combine_sources():
    sources = [("file1.txt", "content one"), ("file2.md", "content two")]
    combined = _combine_sources(sources)
    assert "=== Source: file1.txt ===" in combined
    assert "content one" in combined
    assert "=== Source: file2.md ===" in combined


# ---------------------------------------------------------------------------
# Source reader
# ---------------------------------------------------------------------------

def test_read_sources_from_dir_missing(tmp_path):
    result = read_sources_from_dir(tmp_path / "nonexistent")
    assert result == []

def test_read_sources_from_dir_txt_and_md(tmp_path):
    (tmp_path / "a.txt").write_text("hello world", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Title\ncontent", encoding="utf-8")
    result = read_sources_from_dir(tmp_path)
    assert len(result) == 2
    names = [r[0] for r in result]
    assert "a.txt" in names
    assert "b.md" in names

def test_read_sources_skips_empty(tmp_path):
    (tmp_path / "empty.txt").write_text("   \n  ", encoding="utf-8")
    (tmp_path / "real.txt").write_text("actual content", encoding="utf-8")
    result = read_sources_from_dir(tmp_path)
    assert len(result) == 1
    assert result[0][0] == "real.txt"

def test_read_sources_skips_unsupported_extensions(tmp_path):
    (tmp_path / "data.pdf").write_bytes(b"%PDF binary content")
    (tmp_path / ".DS_Store").write_bytes(b"hidden")
    (tmp_path / "notes.txt").write_text("valid content", encoding="utf-8")
    result = read_sources_from_dir(tmp_path)
    assert len(result) == 1
    assert result[0][0] == "notes.txt"

def test_read_sources_skips_hidden_files(tmp_path):
    (tmp_path / ".hidden.txt").write_text("hidden content", encoding="utf-8")
    (tmp_path / "visible.txt").write_text("visible content", encoding="utf-8")
    result = read_sources_from_dir(tmp_path)
    assert len(result) == 1
    assert result[0][0] == "visible.txt"

@patch("trafilatura.fetch_url")
@patch("trafilatura.extract")
def test_read_sources_url_file(mock_extract, mock_fetch, tmp_path):
    mock_fetch.return_value = "<html>content</html>"
    mock_extract.return_value = "Extracted article text"
    url_file = tmp_path / "sources.url"
    url_file.write_text("https://example.com/article\n# comment line\n\nhttps://example.com/other\n", encoding="utf-8")
    result = read_sources_from_dir(tmp_path)
    assert len(result) == 1
    assert result[0][0] == "sources.url"
    assert "Extracted article text" in result[0][1]
    assert mock_fetch.call_count == 2  # two valid URLs, comment skipped

@patch("trafilatura.fetch_url")
@patch("trafilatura.extract")
def test_fetch_urls_handles_failure_gracefully(mock_extract, mock_fetch, tmp_path):
    mock_fetch.side_effect = [Exception("network error"), "<html>ok</html>"]
    mock_extract.return_value = "Good content"
    url_file = tmp_path / "sources.url"
    url_file.write_text("https://bad.example.com\nhttps://good.example.com\n", encoding="utf-8")
    # Should not raise; second URL should still be fetched
    result = read_sources_from_dir(tmp_path)
    assert "Good content" in result[0][1]

@patch("trafilatura.fetch_url")
@patch("trafilatura.extract")
def test_fetch_urls_skips_unfetchable(mock_extract, mock_fetch, tmp_path):
    mock_fetch.return_value = None  # fetch returns None = unreachable
    url_file = tmp_path / "sources.url"
    url_file.write_text("https://unreachable.example.com\n", encoding="utf-8")
    result = read_sources_from_dir(tmp_path)
    # Empty content → skipped by read_sources_from_dir
    assert result == []


# ---------------------------------------------------------------------------
# compile_wiki (LLM mocked)
# ---------------------------------------------------------------------------

MOCK_CONCEPTS = '["Productivity", "Work Life Balance"]'

MOCK_ARTICLE = (
    "## Overview\nThis concept is important.\n\n"
    "See also [[Work Life Balance]].\n\n"
    "## Summary\nProductivity increases with remote work. Studies confirm this."
)

@patch("adversarial_wiki.llm.call")
def test_compile_wiki_creates_files(mock_llm, tmp_path):
    mock_llm.side_effect = [MOCK_CONCEPTS, MOCK_ARTICLE, MOCK_ARTICLE, "[]"]
    topic_dir = tmp_path / "topics" / "test-topic"
    (topic_dir / "wiki" / "pro").mkdir(parents=True)

    sources = [("source1.txt", "Remote work improves focus and output.")]
    compile_wiki("test-topic", "pro", sources, topic_dir)

    wiki_pro = topic_dir / "wiki" / "pro"
    assert (wiki_pro / "index.md").exists()
    assert (wiki_pro / "log.md").exists()
    assert (wiki_pro / "productivity.md").exists()
    assert (wiki_pro / "work-life-balance.md").exists()

@patch("adversarial_wiki.llm.call")
def test_compile_wiki_articles_have_frontmatter_aliases(mock_llm, tmp_path):
    mock_llm.side_effect = [MOCK_CONCEPTS, MOCK_ARTICLE, MOCK_ARTICLE, "[]"]
    topic_dir = tmp_path / "topics" / "test-topic"
    (topic_dir / "wiki" / "pro").mkdir(parents=True)

    compile_wiki("test-topic", "pro", [("s.txt", "content")], topic_dir)

    article = (topic_dir / "wiki" / "pro" / "productivity.md").read_text()
    assert "aliases:" in article
    assert '"Productivity"' in article

@patch("adversarial_wiki.llm.call")
def test_compile_wiki_index_has_entries(mock_llm, tmp_path):
    mock_llm.side_effect = [MOCK_CONCEPTS, MOCK_ARTICLE, MOCK_ARTICLE, "[]"]
    topic_dir = tmp_path / "topics" / "test-topic"
    (topic_dir / "wiki" / "pro").mkdir(parents=True)

    compile_wiki("test-topic", "pro", [("s.txt", "content")], topic_dir)

    index = (topic_dir / "wiki" / "pro" / "index.md").read_text()
    assert "[[productivity]]" in index
    assert "[[work-life-balance]]" in index

@patch("adversarial_wiki.llm.call")
def test_compile_wiki_log_records_sources_and_filenames(mock_llm, tmp_path):
    mock_llm.side_effect = [MOCK_CONCEPTS, MOCK_ARTICLE, MOCK_ARTICLE, "[]"]
    topic_dir = tmp_path / "topics" / "test-topic"
    (topic_dir / "wiki" / "pro").mkdir(parents=True)

    compile_wiki("test-topic", "pro", [("my-source.txt", "content")], topic_dir)

    log = (topic_dir / "wiki" / "pro" / "log.md").read_text()
    assert "my-source.txt" in log
    assert "productivity.md" in log  # Fix 9: slug filename in log

@patch("adversarial_wiki.llm.call")
def test_compile_wiki_deduplicates_slugs(mock_llm, tmp_path):
    # Two concepts that produce the same slug should only write one file
    mock_llm.side_effect = ['["Remote Work", "Remote  Work"]', MOCK_ARTICLE, "[]"]
    topic_dir = tmp_path / "topics" / "test-topic"
    (topic_dir / "wiki" / "pro").mkdir(parents=True)

    compile_wiki("test-topic", "pro", [("s.txt", "content")], topic_dir)

    wiki_pro = topic_dir / "wiki" / "pro"
    md_files = [f for f in wiki_pro.iterdir() if f.suffix == ".md" and f.name not in ("index.md", "log.md")]
    assert len(md_files) == 1
