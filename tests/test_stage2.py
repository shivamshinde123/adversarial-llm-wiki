"""Tests for Stage 2 — Wiki Compilation Engine (non-LLM parts)."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from adversarial_wiki.compiler import (
    _slugify,
    _extract_json,
    _extract_summary,
    _combine_sources,
    compile_wiki,
)
from adversarial_wiki.sources import read_sources_from_dir
from adversarial_wiki.utils import init_topic_dirs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_slugify_basic():
    assert _slugify("Remote Work Productivity") == "remote-work-productivity"

def test_slugify_special_chars():
    assert _slugify("Work/Life Balance!") == "worklife-balance"

def test_slugify_truncates():
    long = "a" * 100
    assert len(_slugify(long)) <= 60

def test_extract_json_array():
    text = 'Some preamble ["Concept A", "Concept B"] trailing'
    assert json.loads(_extract_json(text)) == ["Concept A", "Concept B"]

def test_extract_json_no_match():
    # Falls back to returning the text stripped
    result = _extract_json("no json here")
    assert result == "no json here"

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

def test_read_sources_from_dir_empty(tmp_path):
    result = read_sources_from_dir(tmp_path / "nonexistent")
    assert result == []

def test_read_sources_from_dir_txt(tmp_path):
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
    # First call returns concepts JSON, subsequent calls return article body
    mock_llm.side_effect = [MOCK_CONCEPTS, MOCK_ARTICLE, MOCK_ARTICLE, "[]"]

    topic_dir = tmp_path / "topics" / "test-topic"
    (topic_dir / "wiki" / "pro").mkdir(parents=True)
    (topic_dir / "wiki" / "con").mkdir(parents=True)

    sources = [("source1.txt", "Remote work improves focus and output.")]
    compile_wiki("test-topic", "pro", sources, topic_dir)

    wiki_pro = topic_dir / "wiki" / "pro"
    assert (wiki_pro / "index.md").exists()
    assert (wiki_pro / "log.md").exists()
    assert (wiki_pro / "productivity.md").exists()
    assert (wiki_pro / "work-life-balance.md").exists()

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
def test_compile_wiki_log_records_sources(mock_llm, tmp_path):
    mock_llm.side_effect = [MOCK_CONCEPTS, MOCK_ARTICLE, MOCK_ARTICLE, "[]"]

    topic_dir = tmp_path / "topics" / "test-topic"
    (topic_dir / "wiki" / "pro").mkdir(parents=True)

    compile_wiki("test-topic", "pro", [("my-source.txt", "content")], topic_dir)

    log = (topic_dir / "wiki" / "pro" / "log.md").read_text()
    assert "my-source.txt" in log
