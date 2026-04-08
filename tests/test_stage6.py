"""Tests for Stage 6 — Lint Command."""

import json
from pathlib import Path

from adversarial_wiki.lint import (
    run_lint,
    _lint_side,
    _check_broken_links,
    _check_sources_json,
    _check_frontmatter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wiki(tmp_path, side="pro", concept_pages=None, index_content=None, sources_json=None):
    """Build a minimal wiki directory for testing."""
    wiki_dir = tmp_path / "wiki" / side
    wiki_dir.mkdir(parents=True)

    pages = concept_pages or {"productivity": "# Productivity\n\nContent.\n"}
    for stem, content in pages.items():
        (wiki_dir / f"{stem}.md").write_text(content, encoding="utf-8")

    if index_content is None:
        # Default: every stem is referenced
        links = "\n".join(f"## [[{stem}]]\nSummary." for stem in pages)
        index_content = links
    (wiki_dir / "index.md").write_text(index_content, encoding="utf-8")

    if sources_json is not None:
        (wiki_dir / "sources.json").write_text(
            json.dumps(sources_json, indent=2), encoding="utf-8"
        )

    return wiki_dir


# ---------------------------------------------------------------------------
# _check_broken_links
# ---------------------------------------------------------------------------

def test_check_broken_links_passes_on_valid_link(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("See [[productivity]] for details.", encoding="utf-8")
    issues = _check_broken_links(page, {"productivity"})
    assert issues == []


def test_check_broken_links_flags_missing_link(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("See [[missing-concept]] for details.", encoding="utf-8")
    issues = _check_broken_links(page, {"productivity"})
    assert len(issues) == 1
    assert "missing-concept" in issues[0]


def test_check_broken_links_resolves_capitalised_link(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("See [[Productivity]] for details.", encoding="utf-8")
    issues = _check_broken_links(page, {"productivity"})
    assert issues == []


def test_check_broken_links_multiple_links(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("[[good]] and [[bad-one]] and [[also-bad]].", encoding="utf-8")
    issues = _check_broken_links(page, {"good"})
    assert len(issues) == 2


def test_check_broken_links_no_links(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("Plain text, no links here.", encoding="utf-8")
    issues = _check_broken_links(page, {"productivity"})
    assert issues == []


# ---------------------------------------------------------------------------
# _check_sources_json
# ---------------------------------------------------------------------------

def test_check_sources_json_passes_valid(tmp_path):
    wiki_dir = tmp_path / "wiki" / "pro"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "productivity.md").write_text("# Productivity", encoding="utf-8")

    sources_json = wiki_dir / "sources.json"
    sources_json.write_text(json.dumps({
        "sources": [{"url": "https://example.com", "used_in": ["productivity.md"]}]
    }), encoding="utf-8")

    issues = _check_sources_json(sources_json, wiki_dir)
    assert issues == []


def test_check_sources_json_flags_missing_used_in_file(tmp_path):
    wiki_dir = tmp_path / "wiki" / "pro"
    wiki_dir.mkdir(parents=True)

    sources_json = wiki_dir / "sources.json"
    sources_json.write_text(json.dumps({
        "sources": [{"url": "https://example.com", "used_in": ["ghost.md"]}]
    }), encoding="utf-8")

    issues = _check_sources_json(sources_json, wiki_dir)
    assert len(issues) == 1
    assert "ghost.md" in issues[0]


def test_check_sources_json_malformed(tmp_path):
    wiki_dir = tmp_path / "wiki" / "pro"
    wiki_dir.mkdir(parents=True)

    sources_json = wiki_dir / "sources.json"
    sources_json.write_text("not valid json", encoding="utf-8")

    issues = _check_sources_json(sources_json, wiki_dir)
    assert len(issues) == 1
    assert "malformed" in issues[0]


def test_check_sources_json_empty_used_in(tmp_path):
    wiki_dir = tmp_path / "wiki" / "pro"
    wiki_dir.mkdir(parents=True)

    sources_json = wiki_dir / "sources.json"
    sources_json.write_text(json.dumps({
        "sources": [{"url": "https://example.com", "used_in": []}]
    }), encoding="utf-8")

    issues = _check_sources_json(sources_json, wiki_dir)
    assert issues == []


# ---------------------------------------------------------------------------
# _check_frontmatter
# ---------------------------------------------------------------------------

def test_check_frontmatter_passes_valid_auto_article(tmp_path):
    page = tmp_path / "productivity.md"
    page.write_text(
        "---\naliases:\n  - Productivity\nmode: auto\ncompiled: 2026-04-07\n---\n# Productivity\n",
        encoding="utf-8",
    )
    issues = _check_frontmatter([page])
    assert issues == []


def test_check_frontmatter_flags_missing_mode(tmp_path):
    page = tmp_path / "productivity.md"
    page.write_text(
        "---\naliases:\n  - Productivity\ncompiled: 2026-04-07\n---\n# Productivity\n",
        encoding="utf-8",
    )
    issues = _check_frontmatter([page])
    assert any("mode" in i for i in issues)


def test_check_frontmatter_flags_missing_compiled(tmp_path):
    page = tmp_path / "productivity.md"
    page.write_text(
        "---\naliases:\n  - Productivity\nmode: auto\n---\n# Productivity\n",
        encoding="utf-8",
    )
    issues = _check_frontmatter([page])
    assert any("compiled" in i for i in issues)


def test_check_frontmatter_flags_missing_frontmatter_block(tmp_path):
    page = tmp_path / "productivity.md"
    page.write_text("# Productivity\n\nNo frontmatter here.", encoding="utf-8")
    issues = _check_frontmatter([page])
    assert any("missing frontmatter" in i for i in issues)


def test_check_frontmatter_does_not_match_field_in_body(tmp_path):
    """Fields that appear only in the body (not the YAML block) must not satisfy the check."""
    page = tmp_path / "productivity.md"
    # mode: and compiled: appear only in the body paragraph, not in frontmatter
    page.write_text(
        "---\naliases:\n  - Productivity\n---\n"
        "# Productivity\n\nThe mode: of operation and compiled: output are discussed here.\n",
        encoding="utf-8",
    )
    issues = _check_frontmatter([page])
    assert any("mode" in i for i in issues)
    assert any("compiled" in i for i in issues)


# ---------------------------------------------------------------------------
# _lint_side
# ---------------------------------------------------------------------------

def test_lint_side_passes_clean_manual_wiki(tmp_path):
    _make_wiki(tmp_path)
    issues = _lint_side("pro", tmp_path / "wiki" / "pro")
    assert issues == []


def test_lint_side_stem_substring_not_treated_as_reference(tmp_path):
    """A stem that appears only as part of a longer word must still be treated as orphaned."""
    wiki_dir = _make_wiki(
        tmp_path,
        concept_pages={"cost": "# Cost", "productivity": "# Productivity"},
        # "cost" appears only inside "cost-benefit", not as a standalone word or [[cost]]
        index_content="## [[productivity]]\nSee the cost-benefit section.\n",
    )
    issues = _lint_side("pro", tmp_path / "wiki" / "pro")
    assert any("cost" in i and "Orphaned" in i for i in issues)


def test_lint_side_missing_wiki_dir(tmp_path):
    issues = _lint_side("pro", tmp_path / "wiki" / "pro")
    assert any("does not exist" in i for i in issues)


def test_lint_side_missing_index(tmp_path):
    wiki_dir = tmp_path / "wiki" / "pro"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "productivity.md").write_text("# Productivity", encoding="utf-8")
    # No index.md written

    issues = _lint_side("pro", wiki_dir)
    assert any("index.md" in i for i in issues)


def test_lint_side_detects_orphaned_page(tmp_path):
    wiki_dir = _make_wiki(
        tmp_path,
        concept_pages={"productivity": "# Productivity", "burnout": "# Burnout"},
        index_content="## [[productivity]]\nSummary.",  # burnout missing
    )
    issues = _lint_side("pro", tmp_path / "wiki" / "pro")
    assert any("burnout" in i and "Orphaned" in i for i in issues)


def test_lint_side_detects_broken_link_in_concept_page(tmp_path):
    wiki_dir = _make_wiki(
        tmp_path,
        concept_pages={"productivity": "# Productivity\n\nSee [[ghost]] for details."},
        index_content="## [[productivity]]\nSummary.",
    )
    issues = _lint_side("pro", tmp_path / "wiki" / "pro")
    assert any("ghost" in i and "Broken link" in i for i in issues)


def test_lint_side_no_concept_pages(tmp_path):
    wiki_dir = tmp_path / "wiki" / "pro"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "index.md").write_text("# Index", encoding="utf-8")

    issues = _lint_side("pro", wiki_dir)
    assert any("no concept pages" in i for i in issues)


def test_lint_side_auto_mode_checks_sources_json(tmp_path):
    _make_wiki(
        tmp_path,
        concept_pages={"productivity": "---\nmode: auto\ncompiled: 2026-04-07\n---\n# Prod"},
        sources_json={
            "sources": [{"url": "https://example.com", "used_in": ["ghost.md"]}]
        },
    )
    issues = _lint_side("pro", tmp_path / "wiki" / "pro")
    assert any("ghost.md" in i for i in issues)


# ---------------------------------------------------------------------------
# run_lint (full)
# ---------------------------------------------------------------------------

def test_run_lint_returns_true_on_clean_wiki(tmp_path):
    _make_wiki(tmp_path, side="pro")
    _make_wiki(tmp_path, side="con")
    assert run_lint("test", tmp_path) is True


def test_run_lint_returns_false_when_pro_has_issues(tmp_path):
    # pro: missing wiki dir entirely
    _make_wiki(tmp_path, side="con")
    assert run_lint("test", tmp_path) is False


def test_run_lint_returns_false_when_con_has_issues(tmp_path):
    _make_wiki(tmp_path, side="pro")
    # con: missing wiki dir entirely
    assert run_lint("test", tmp_path) is False
