"""Tests for Stage 4 — Debate Engine."""

import json
from pathlib import Path
from unittest.mock import patch, call

from adversarial_wiki.debate import (
    _retrieve_articles,
    _parse_slug_list,
    _format_articles,
    _format_output_md,
    _save_output,
    run_debate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_parse_slug_list_basic():
    result = _parse_slug_list('["productivity", "work-life-balance"]')
    assert result == ["productivity", "work-life-balance"]

def test_parse_slug_list_strips_md_extension():
    result = _parse_slug_list('["productivity.md", "burnout.md"]')
    assert result == ["productivity", "burnout"]

def test_parse_slug_list_bad_json_returns_empty():
    assert _parse_slug_list("not json") == []

def test_parse_slug_list_empty_array():
    assert _parse_slug_list("[]") == []

def test_format_articles():
    articles = [("productivity", "Content A"), ("burnout", "Content B")]
    result = _format_articles(articles)
    assert "=== Article: productivity ===" in result
    assert "Content A" in result
    assert "=== Article: burnout ===" in result

def test_format_output_md_structure():
    md = _format_output_md("My question?", "Pro arg", "Con arg", "Assumptions text")
    assert "# Question" in md
    assert "My question?" in md
    assert "## Wiki A Argues" in md
    assert "Pro arg" in md
    assert "## Wiki B Argues" in md
    assert "Con arg" in md
    assert "## Hidden Assumptions" in md
    assert "Assumptions text" in md


# ---------------------------------------------------------------------------
# _retrieve_articles
# ---------------------------------------------------------------------------

@patch("adversarial_wiki.llm.call")
def test_retrieve_articles_loads_identified_articles(mock_llm, tmp_path):
    wiki_dir = tmp_path / "wiki" / "pro"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "index.md").write_text("## [[productivity]]\nAbout productivity.", encoding="utf-8")
    (wiki_dir / "productivity.md").write_text("# Productivity\nContent here.", encoding="utf-8")
    (wiki_dir / "burnout.md").write_text("# Burnout\nNot relevant.", encoding="utf-8")

    mock_llm.return_value = '["productivity"]'
    articles = _retrieve_articles("Does remote work help?", wiki_dir, "pro")

    assert len(articles) == 1
    assert articles[0][0] == "productivity"
    assert "Content here." in articles[0][1]

@patch("adversarial_wiki.llm.call")
def test_retrieve_articles_fallback_loads_all_on_empty_response(mock_llm, tmp_path):
    wiki_dir = tmp_path / "wiki" / "pro"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "index.md").write_text("Index content", encoding="utf-8")
    (wiki_dir / "concept-a.md").write_text("# Concept A", encoding="utf-8")
    (wiki_dir / "concept-b.md").write_text("# Concept B", encoding="utf-8")
    (wiki_dir / "log.md").write_text("Log content", encoding="utf-8")

    mock_llm.return_value = "[]"  # LLM returns no relevant articles
    articles = _retrieve_articles("question", wiki_dir, "pro")

    slugs = [a[0] for a in articles]
    assert "concept-a" in slugs
    assert "concept-b" in slugs
    assert "log" not in slugs  # log.md excluded

def test_retrieve_articles_missing_wiki_returns_empty(tmp_path):
    result = _retrieve_articles("question", tmp_path / "nonexistent", "pro")
    assert result == []

@patch("adversarial_wiki.llm.call")
def test_retrieve_articles_skips_missing_slugs(mock_llm, tmp_path):
    wiki_dir = tmp_path / "wiki" / "pro"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "index.md").write_text("Index", encoding="utf-8")
    (wiki_dir / "real.md").write_text("# Real", encoding="utf-8")

    mock_llm.return_value = '["real", "ghost"]'  # "ghost" does not exist
    articles = _retrieve_articles("question", wiki_dir, "pro")

    assert len(articles) == 1
    assert articles[0][0] == "real"


# ---------------------------------------------------------------------------
# _save_output
# ---------------------------------------------------------------------------

def test_save_output_creates_file(tmp_path):
    topic_dir = tmp_path
    (topic_dir / "debates").mkdir()

    path = _save_output(
        "test-topic", "Should I go remote?",
        "Pro argument here.", "Con argument here.",
        "Assumptions here.", topic_dir,
    )

    assert path.exists()
    assert path.name == "output.md"
    content = path.read_text()
    assert "Should I go remote?" in content
    assert "Pro argument here." in content
    assert "Con argument here." in content

def test_save_output_slug_used_as_dir(tmp_path):
    topic_dir = tmp_path
    (topic_dir / "debates").mkdir()

    path = _save_output(
        "test", "Is remote work productive?",
        "pro", "con", "assumptions", topic_dir,
    )

    assert path.parent.name == "is-remote-work-productive"


# ---------------------------------------------------------------------------
# run_debate (full pipeline mocked)
# ---------------------------------------------------------------------------

MOCK_INDEX = "## [[productivity]]\nAbout productivity gains.\n## [[burnout]]\nAbout burnout risks."
MOCK_ARTICLE = "# Productivity\n\nRemote work boosts productivity."

@patch("adversarial_wiki.llm.call")
def test_run_debate_makes_three_llm_calls(mock_llm, tmp_path):
    topic_dir = tmp_path
    wiki_pro = topic_dir / "wiki" / "pro"
    wiki_con = topic_dir / "wiki" / "con"
    wiki_pro.mkdir(parents=True)
    wiki_con.mkdir(parents=True)
    (topic_dir / "debates").mkdir()

    (wiki_pro / "index.md").write_text(MOCK_INDEX, encoding="utf-8")
    (wiki_con / "index.md").write_text(MOCK_INDEX, encoding="utf-8")
    (wiki_pro / "productivity.md").write_text(MOCK_ARTICLE, encoding="utf-8")
    (wiki_con / "productivity.md").write_text(MOCK_ARTICLE, encoding="utf-8")

    mock_llm.side_effect = [
        '["productivity"]',   # retrieval: pro
        '["productivity"]',   # retrieval: con
        "Strong pro argument with [[productivity]] citation.",  # call 1: pro argues
        "Strong con argument with [[productivity]] citation.",  # call 2: con argues
        "### Wiki A assumes:\nX\n\n### Wiki B assumes:\nY\n\n## Before You Decide, Answer These\n1. Q1\n2. Q2\n3. Q3",  # call 3
    ]

    run_debate("test-topic", "Should I go remote?", topic_dir)

    assert mock_llm.call_count == 5  # 2 retrieval + 3 debate calls

@patch("adversarial_wiki.llm.call")
def test_run_debate_output_file_has_all_sections(mock_llm, tmp_path):
    topic_dir = tmp_path
    wiki_pro = topic_dir / "wiki" / "pro"
    wiki_con = topic_dir / "wiki" / "con"
    wiki_pro.mkdir(parents=True)
    wiki_con.mkdir(parents=True)
    (topic_dir / "debates").mkdir()

    (wiki_pro / "index.md").write_text(MOCK_INDEX, encoding="utf-8")
    (wiki_con / "index.md").write_text(MOCK_INDEX, encoding="utf-8")
    (wiki_pro / "productivity.md").write_text(MOCK_ARTICLE, encoding="utf-8")
    (wiki_con / "productivity.md").write_text(MOCK_ARTICLE, encoding="utf-8")

    assumptions = "### Wiki A assumes:\nX\n\n### Wiki B assumes:\nY\n\n## Before You Decide, Answer These\n1. Q1\n2. Q2\n3. Q3"
    mock_llm.side_effect = [
        '["productivity"]', '["productivity"]',
        "Pro argument.", "Con argument.", assumptions,
    ]

    run_debate("test-topic", "Should I go remote?", topic_dir)

    output = next((topic_dir / "debates").rglob("output.md"))
    content = output.read_text()

    assert "# Question" in content
    assert "Should I go remote?" in content
    assert "## Wiki A Argues" in content
    assert "Pro argument." in content
    assert "## Wiki B Argues" in content
    assert "Con argument." in content
    assert "## Hidden Assumptions" in content
    assert "Wiki A assumes:" in content
    assert "Wiki B assumes:" in content
