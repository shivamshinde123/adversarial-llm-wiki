"""Tests for Stage 3 — Auto Research Agent (non-network parts)."""

import json
from pathlib import Path
from unittest.mock import patch

from adversarial_wiki.research import (
    _generate_queries,
    _url_to_filename,
    _write_sources_json,
    _find_articles_using_url,
)
from adversarial_wiki.utils import extract_json
from adversarial_wiki.compiler import compile_wiki


# ---------------------------------------------------------------------------
# _extract_first_json (shared bracket-matching logic)
# ---------------------------------------------------------------------------

def test_extract_json_array():
    text = 'Preamble ["query one", "query two"] done'
    result = json.loads(extract_json(text))
    assert result == ["query one", "query two"]

def test_extract_json_no_match():
    assert extract_json("nothing here") == "nothing here"


# ---------------------------------------------------------------------------
# _url_to_filename
# ---------------------------------------------------------------------------

def test_url_to_filename_strips_scheme():
    name = _url_to_filename("https://www.example.com/article/foo-bar")
    assert name.endswith(".txt")
    assert "https" not in name
    assert "www" not in name

def test_url_to_filename_truncates():
    long_url = "https://example.com/" + "a" * 200
    assert len(_url_to_filename(long_url)) <= 65  # 60 + ".txt"

def test_url_to_filename_safe_chars():
    name = _url_to_filename("https://example.com/path?q=hello world&x=1")
    assert " " not in name
    assert "?" not in name


# ---------------------------------------------------------------------------
# _generate_queries
# ---------------------------------------------------------------------------

@patch("adversarial_wiki.llm.call")
def test_generate_queries_returns_list(mock_llm):
    mock_llm.return_value = '["query one", "query two", "query three"]'
    queries = _generate_queries("remote work", "pro", "remote work boosts productivity")
    assert isinstance(queries, list)
    assert len(queries) == 3
    assert "query one" in queries

@patch("adversarial_wiki.llm.call")
def test_generate_queries_fallback_on_bad_json(mock_llm):
    mock_llm.return_value = "not json at all"
    queries = _generate_queries("remote work", "pro", "remote work boosts productivity")
    assert isinstance(queries, list)
    assert len(queries) == 1  # fallback single query

@patch("adversarial_wiki.llm.call")
def test_generate_queries_caps_at_five(mock_llm):
    mock_llm.return_value = '["q1","q2","q3","q4","q5","q6","q7"]'
    queries = _generate_queries("topic", "pro", "stance")
    assert len(queries) <= 5


# ---------------------------------------------------------------------------
# _write_sources_json
# ---------------------------------------------------------------------------

def test_write_sources_json_creates_file(tmp_path):
    wiki_dir = tmp_path / "wiki" / "pro"
    wiki_dir.mkdir(parents=True)

    records = [
        {"url": "https://example.com/a", "title": "Article A", "retrieved": "2026-04-07", "used_in": []},
        {"url": "https://example.com/b", "title": "Article B", "retrieved": "2026-04-07", "used_in": []},
    ]
    topic_dir = tmp_path
    _write_sources_json("remote-work", "pro", records, topic_dir)

    sources_path = wiki_dir / "sources.json"
    assert sources_path.exists()
    data = json.loads(sources_path.read_text())
    assert data["topic"] == "remote-work"
    assert data["side"] == "pro"
    assert data["mode"] == "auto"
    assert len(data["sources"]) == 2

def test_write_sources_json_populates_used_in(tmp_path):
    wiki_dir = tmp_path / "wiki" / "pro"
    wiki_dir.mkdir(parents=True)
    # Write an article that mentions the URL
    (wiki_dir / "productivity.md").write_text(
        "---\nsources:\n  - https://example.com/a\n---\n# Productivity\n\nContent here.",
        encoding="utf-8",
    )
    records = [
        {"url": "https://example.com/a", "title": "A", "retrieved": "2026-04-07", "used_in": []},
        {"url": "https://example.com/b", "title": "B", "retrieved": "2026-04-07", "used_in": []},
    ]
    _write_sources_json("remote-work", "pro", records, tmp_path)

    data = json.loads((wiki_dir / "sources.json").read_text())
    url_a = next(s for s in data["sources"] if s["url"] == "https://example.com/a")
    url_b = next(s for s in data["sources"] if s["url"] == "https://example.com/b")
    assert "productivity.md" in url_a["used_in"]
    assert url_b["used_in"] == []


# ---------------------------------------------------------------------------
# _find_articles_using_url
# ---------------------------------------------------------------------------

def test_find_articles_using_url(tmp_path):
    (tmp_path / "concept-a.md").write_text("mentions https://example.com/source", encoding="utf-8")
    (tmp_path / "concept-b.md").write_text("no mention here", encoding="utf-8")
    (tmp_path / "index.md").write_text("https://example.com/source in index", encoding="utf-8")  # should be skipped

    result = _find_articles_using_url("https://example.com/source", tmp_path)
    assert "concept-a.md" in result
    assert "concept-b.md" not in result
    assert "index.md" not in result


# ---------------------------------------------------------------------------
# compile_wiki with mode="auto" frontmatter
# ---------------------------------------------------------------------------

MOCK_CONCEPTS = '["Productivity"]'
MOCK_ARTICLE = "## Overview\nContent.\n\n## Summary\nThis is the summary."
# Article body that explicitly cites a URL (simulates LLM mentioning its source)
MOCK_ARTICLE_WITH_URL = "## Overview\nSee https://example.com/a for details.\n\n## Summary\nThis is the summary."

@patch("adversarial_wiki.llm.call")
def test_auto_mode_article_has_frontmatter(mock_llm, tmp_path):
    mock_llm.side_effect = [MOCK_CONCEPTS, MOCK_ARTICLE, "[]"]
    topic_dir = tmp_path / "topics" / "test"
    (topic_dir / "wiki" / "pro").mkdir(parents=True)

    source_records = [
        {"url": "https://example.com/a", "title": "A", "retrieved": "2026-04-07", "used_in": []}
    ]
    compile_wiki(
        "test", "pro",
        [("a.txt", "content")],
        topic_dir,
        mode="auto",
        source_records=source_records,
    )

    article = (topic_dir / "wiki" / "pro" / "productivity.md").read_text()
    assert "mode: auto" in article
    assert "compiled:" in article
    # URL not cited in body — should not appear in frontmatter (Fix 4)
    assert "https://example.com/a" not in article

@patch("adversarial_wiki.llm.call")
def test_auto_mode_article_cites_url_in_frontmatter_when_body_mentions_it(mock_llm, tmp_path):
    mock_llm.side_effect = [MOCK_CONCEPTS, MOCK_ARTICLE_WITH_URL, "[]"]
    topic_dir = tmp_path / "topics" / "test"
    (topic_dir / "wiki" / "pro").mkdir(parents=True)

    source_records = [
        {"url": "https://example.com/a", "title": "A", "retrieved": "2026-04-07", "used_in": []}
    ]
    compile_wiki(
        "test", "pro",
        [("a.txt", "content")],
        topic_dir,
        mode="auto",
        source_records=source_records,
    )

    article = (topic_dir / "wiki" / "pro" / "productivity.md").read_text()
    # URL cited in body — should appear in frontmatter sources list
    assert "sources:" in article
    assert "https://example.com/a" in article

@patch("adversarial_wiki.llm.call")
def test_manual_mode_article_has_no_sources_list(mock_llm, tmp_path):
    mock_llm.side_effect = [MOCK_CONCEPTS, MOCK_ARTICLE, "[]"]
    topic_dir = tmp_path / "topics" / "test"
    (topic_dir / "wiki" / "pro").mkdir(parents=True)

    compile_wiki("test", "pro", [("a.txt", "content")], topic_dir, mode="manual")

    article = (topic_dir / "wiki" / "pro" / "productivity.md").read_text()
    assert "mode: manual" in article
    assert "sources:" not in article


# ---------------------------------------------------------------------------
# run_research (full pipeline mocked)
# ---------------------------------------------------------------------------

@patch("adversarial_wiki.research._fetch_sources")
@patch("adversarial_wiki.research._search")
@patch("adversarial_wiki.llm.call")
def test_run_research_creates_wiki_and_sources_json(mock_llm, mock_search, mock_fetch, tmp_path):
    from adversarial_wiki.research import run_research

    mock_llm.side_effect = [
        # pro queries, con queries
        '["pro query"]', '["con query"]',
        # pro: concepts, article, contradictions
        '["Productivity"]', MOCK_ARTICLE, "[]",
        # con: concepts, article, contradictions
        '["Burnout"]', MOCK_ARTICLE, "[]",
    ]
    mock_search.return_value = [
        {"url": "https://example.com/a", "title": "A", "snippet": "snippet", "query": "q"}
    ]
    mock_fetch.return_value = (
        [("a.txt", "content")],
        [{"url": "https://example.com/a", "title": "A", "retrieved": "2026-04-07", "used_in": []}],
    )

    topic_dir = tmp_path / "topics" / "test"
    (topic_dir / "wiki" / "pro").mkdir(parents=True)
    (topic_dir / "wiki" / "con").mkdir(parents=True)

    run_research("test", None, None, topic_dir)

    assert (topic_dir / "wiki" / "pro" / "sources.json").exists()
    assert (topic_dir / "wiki" / "con" / "sources.json").exists()
    assert (topic_dir / "wiki" / "pro" / "index.md").exists()
    assert (topic_dir / "wiki" / "con" / "index.md").exists()
