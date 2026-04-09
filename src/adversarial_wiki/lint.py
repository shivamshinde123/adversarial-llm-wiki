"""Lint command — health checks for compiled wikis.

Collects structural integrity issues across both sides and prints a concise
report. Intended for CLI/CI use; returns a boolean for exit code control.
"""

import json
import re
from pathlib import Path

import click
import logging

from adversarial_wiki.utils import slugify

logger = logging.getLogger(__name__)

# Fields required in every auto-mode article's frontmatter
_AUTO_REQUIRED_FIELDS = ("mode:", "compiled:")


def run_lint(topic: str, topic_dir) -> bool:
    """Run integrity checks on the compiled wikis for a topic.

    Checks both pro and con sides for:
      - wiki directory existence and non-emptiness
      - index.md presence
      - orphaned concept pages (not referenced in index.md)
      - broken [[wiki-links]] in any page
      - sources.json integrity (auto mode only)
      - frontmatter validity (auto mode only)

    Args:
        topic: Topic name.
        topic_dir: Path to the topic root directory.

    Returns:
        True if all checks pass, False if any issues found.
    """
    topic_dir = Path(topic_dir)
    all_passed = True

    for side in ("pro", "con"):
        wiki_dir = topic_dir / "wiki" / side
        issues = _lint_side(side, wiki_dir)
        _print_report(side, issues)
        logger.info("lint side=%s issues=%d", side, len(issues))
        if issues:
            all_passed = False

    return all_passed


# ---------------------------------------------------------------------------
# Per-side checks
# ---------------------------------------------------------------------------

def _lint_side(side: str, wiki_dir: Path) -> list[str]:
    """Run all checks for one wiki side. Returns a list of issue descriptions."""
    issues: list[str] = []

    # 1. Directory existence
    if not wiki_dir.exists():
        issues.append(f"wiki/{side}/ does not exist")
        return issues

    concept_pages = _get_concept_pages(wiki_dir)

    # 2. Non-empty
    if not concept_pages:
        issues.append(f"wiki/{side}/ has no concept pages")
        return issues

    valid_stems = {p.stem for p in concept_pages}

    # 3. index.md existence
    index_path = wiki_dir / "index.md"
    if not index_path.exists():
        issues.append("index.md is missing")
    else:
        index_content = index_path.read_text(encoding="utf-8")

        # 4. Orphaned pages (concept page not referenced in index.md)
        for page in concept_pages:
            if not _stem_referenced(page.stem, index_content):
                issues.append(f"Orphaned page: {page.name} (not referenced in index.md)")

        # 5. Broken links in index.md
        issues.extend(_check_broken_links(index_path, valid_stems))

    # 6. Broken links in concept pages
    for page in concept_pages:
        issues.extend(_check_broken_links(page, valid_stems))

    # 7. Auto-mode checks (sources.json present → auto mode)
    sources_json_path = wiki_dir / "sources.json"
    if sources_json_path.exists():
        issues.extend(_check_sources_json(sources_json_path, wiki_dir))
        issues.extend(_check_frontmatter(concept_pages))

    return issues


# ---------------------------------------------------------------------------
# Individual checkers
# ---------------------------------------------------------------------------

def _get_concept_pages(wiki_dir: Path) -> list[Path]:
    """Return all concept page paths in wiki_dir, excluding index.md and log.md."""
    return [
        p for p in sorted(wiki_dir.glob("*.md"))
        if p.name not in ("index.md", "log.md")
    ]


def _stem_referenced(stem: str, text: str) -> bool:
    """True if the page stem appears in text as a wiki-link or standalone reference.

    A "standalone" reference means the stem is not part of a longer word or
    hyphenated compound, e.g. ``cost`` in ``cost-benefit`` is NOT a reference.
    """
    return f"[[{stem}]]" in text or bool(
        re.search(r'\b' + re.escape(stem) + r'(?![-\w])', text)
    )


def _check_broken_links(page: Path, valid_stems: set[str]) -> list[str]:
    """Find [[wiki-links]] in page that don't resolve to any concept page."""
    issues: list[str] = []
    try:
        content = page.read_text(encoding="utf-8")
    except OSError:
        return [f"Could not read {page.name}"]

    for match in re.finditer(r'\[\[([^\]]+)\]\]', content):
        link = match.group(1)
        if link not in valid_stems and slugify(link) not in valid_stems:
            issues.append(f"Broken link in {page.name}: [[{link}]]")

    return issues


def _check_sources_json(sources_json_path: Path, wiki_dir: Path) -> list[str]:
    """Verify sources.json is valid and all used_in entries point to real files."""
    issues: list[str] = []
    try:
        data = json.loads(sources_json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ["sources.json is malformed or unreadable"]

    for record in data.get("sources", []):
        for filename in record.get("used_in", []):
            if not (wiki_dir / filename).exists():
                issues.append(
                    f"sources.json: used_in '{filename}' does not exist"
                )

    return issues


def _check_frontmatter(concept_pages: list[Path]) -> list[str]:
    """Verify each auto-mode article has required frontmatter fields."""
    issues: list[str] = []
    for page in concept_pages:
        try:
            content = page.read_text(encoding="utf-8")
        except OSError:
            continue
        if not content.startswith("---"):
            issues.append(f"{page.name}: missing frontmatter")
            continue
        # Scope the check to the frontmatter block only (between the two "---" fences)
        end = content.find("\n---", 3)
        frontmatter_block = content[: end + 4] if end != -1 else content
        for field in _AUTO_REQUIRED_FIELDS:
            if field not in frontmatter_block:
                issues.append(f"{page.name}: frontmatter missing '{field.rstrip(':')}'")
    return issues


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

def _print_report(side: str, issues: list[str]) -> None:
    """Print a pass/fail report for one wiki side to stdout.

    Args:
        side: 'pro' or 'con'.
        issues: List of issue description strings. Empty means all checks passed.
    """
    if not issues:
        click.echo(f"[{side}] PASSED — no issues found.")
    else:
        click.echo(f"[{side}] FAILED — {len(issues)} issue(s) found:")
        for issue in issues:
            click.echo(f"  - {issue}")
