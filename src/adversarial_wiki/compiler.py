"""Wiki Compilation Engine — builds structured wiki from source content."""

import json
import re
from datetime import date
from pathlib import Path

from adversarial_wiki import llm


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compile_wiki(topic: str, side: str, sources: list[tuple[str, str]], topic_dir: Path) -> None:
    """Compile source content into a structured wiki for one side.

    Args:
        topic: Topic name.
        side: 'pro' or 'con'.
        sources: List of (filename, content) tuples from source documents.
        topic_dir: Path to the topic root directory.
    """
    wiki_dir = topic_dir / "wiki" / side
    wiki_dir.mkdir(parents=True, exist_ok=True)

    combined = _combine_sources(sources)

    # Step 1: extract concept names
    concepts = _extract_concepts(topic, side, combined)

    # Step 2: write one article per concept
    written: list[tuple[str, str]] = []  # (slug, summary)
    for concept in concepts:
        slug, summary = _write_article(topic, side, concept, combined, wiki_dir)
        written.append((slug, summary))

    # Step 3: write index.md
    _write_index(topic, side, written, wiki_dir)

    # Step 4: write log.md
    _write_log(topic, side, sources, concepts, wiki_dir)

    # Step 5: flag contradictions within this side
    _flag_contradictions(topic, side, combined, written, wiki_dir)


# ---------------------------------------------------------------------------
# Step 1 — Concept extraction
# ---------------------------------------------------------------------------

def _extract_concepts(topic: str, side: str, combined: str) -> list[str]:
    """Ask the LLM to identify the major concepts/entities in the sources."""
    system = (
        "You are a knowledge base architect. Your job is to identify the major "
        "concepts, claims, entities, and arguments present in a set of sources "
        "about a topic. You will return ONLY a JSON array of concept names — "
        "short, noun-phrase titles suitable for wiki article headings. "
        "Each concept should be distinct and worth its own article. "
        "Aim for 5-15 concepts depending on source depth. "
        "Return ONLY valid JSON, nothing else."
    )
    user = (
        f"Topic: {topic}\n"
        f"Perspective: {side}\n\n"
        f"Sources:\n{combined[:12000]}\n\n"
        "Return a JSON array of concept names. Example:\n"
        '["Productivity Gains", "Work-Life Balance", "Remote Collaboration Tools"]'
    )
    response = llm.call(system, user, max_tokens=1024)
    try:
        concepts = json.loads(_extract_json(response))
        if isinstance(concepts, list):
            return [str(c).strip() for c in concepts if str(c).strip()]
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: parse line by line
    return [line.strip('- "\'').strip() for line in response.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Step 2 — Article writing
# ---------------------------------------------------------------------------

def _write_article(
    topic: str,
    side: str,
    concept: str,
    combined: str,
    wiki_dir: Path,
) -> tuple[str, str]:
    """Write a single wiki article and return (slug, two-sentence summary)."""
    system = (
        "You are writing a wiki article for one side of a structured debate knowledge base. "
        "Write a thorough, well-structured article about the given concept as it relates "
        "to the perspective of your side. "
        "Requirements:\n"
        "- Use markdown with ## subheadings\n"
        "- Cross-reference related concepts using [[Concept Name]] wiki-link syntax\n"
        "- Ground every claim in the provided sources\n"
        "- If sources within this side contradict each other on this concept, "
        "  add a > **Contradiction:** note inline\n"
        "- Do NOT include a top-level # heading (the filename is the title)\n"
        "- End with a ## Summary section: exactly 2-3 sentences summarising the article"
    )
    user = (
        f"Topic: {topic}\n"
        f"Perspective: {side}\n"
        f"Concept to write about: {concept}\n\n"
        f"Sources:\n{combined[:12000]}"
    )
    article_body = llm.call(system, user)

    slug = _slugify(concept)
    path = wiki_dir / f"{slug}.md"
    path.write_text(f"# {concept}\n\n{article_body}\n", encoding="utf-8")

    summary = _extract_summary(article_body, concept)
    return slug, summary


# ---------------------------------------------------------------------------
# Step 3 — Index
# ---------------------------------------------------------------------------

def _write_index(
    topic: str,
    side: str,
    written: list[tuple[str, str]],
    wiki_dir: Path,
) -> None:
    """Write index.md with a 2-3 sentence summary entry per article."""
    lines = [
        f"# {topic} — {side.capitalize()} Wiki Index\n",
        f"*Compiled: {date.today()}*\n",
        "",
    ]
    for slug, summary in written:
        lines.append(f"## [[{slug}]]\n")
        lines.append(f"{summary}\n")

    (wiki_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Step 4 — Log
# ---------------------------------------------------------------------------

def _write_log(
    topic: str,
    side: str,
    sources: list[tuple[str, str]],
    concepts: list[str],
    wiki_dir: Path,
) -> None:
    """Write log.md recording what was compiled and when."""
    lines = [
        f"# Compilation Log — {topic} ({side})\n",
        f"**Date:** {date.today()}",
        f"**Sources processed:** {len(sources)}",
        f"**Articles compiled:** {len(concepts)}",
        "",
        "## Sources",
    ]
    for name, _ in sources:
        lines.append(f"- {name}")
    lines += [
        "",
        "## Articles",
    ]
    for concept in concepts:
        lines.append(f"- {concept}")

    (wiki_dir / "log.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Step 5 — Contradiction flagging
# ---------------------------------------------------------------------------

def _flag_contradictions(
    topic: str,
    side: str,
    combined: str,
    written: list[tuple[str, str]],
    wiki_dir: Path,
) -> None:
    """Ask LLM to identify contradictions within this side's sources and annotate articles."""
    system = (
        "You are reviewing a set of sources that all support the same perspective. "
        "Identify any factual contradictions — cases where two sources within this "
        "same perspective make incompatible claims. "
        "Return ONLY a JSON array of objects with keys: "
        '"concept" (which article it belongs to), "note" (one sentence describing the contradiction). '
        "If there are no contradictions, return an empty array []."
    )
    user = (
        f"Topic: {topic}\nPerspective: {side}\n\n"
        f"Sources:\n{combined[:10000]}"
    )
    response = llm.call(system, user, max_tokens=1024)

    try:
        flags = json.loads(_extract_json(response))
    except (json.JSONDecodeError, ValueError):
        return

    if not isinstance(flags, list):
        return

    for flag in flags:
        concept = flag.get("concept", "")
        note = flag.get("note", "")
        if not concept or not note:
            continue
        slug = _slugify(concept)
        article_path = wiki_dir / f"{slug}.md"
        if article_path.exists():
            content = article_path.read_text(encoding="utf-8")
            contradiction_block = f"\n> **Contradiction:** {note}\n"
            # Append before the Summary section if present, else at end
            if "## Summary" in content:
                content = content.replace("## Summary", f"{contradiction_block}\n## Summary", 1)
            else:
                content += contradiction_block
            article_path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _combine_sources(sources: list[tuple[str, str]]) -> str:
    parts = []
    for name, content in sources:
        parts.append(f"=== Source: {name} ===\n\n{content}")
    return "\n\n---\n\n".join(parts)


def _extract_json(text: str) -> str:
    """Pull the first JSON array or object out of an LLM response."""
    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1)
    return text.strip()


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")


def _extract_summary(article_body: str, concept: str) -> str:
    """Extract the ## Summary section from an article, or generate a fallback."""
    match = re.search(r"## Summary\s*\n+(.*?)(?:\n##|\Z)", article_body, re.DOTALL | re.IGNORECASE)
    if match:
        summary = match.group(1).strip()
        # Trim to 2-3 sentences max
        sentences = re.split(r"(?<=[.!?])\s+", summary)
        return " ".join(sentences[:3])
    # Fallback: first non-empty paragraph
    for para in article_body.split("\n\n"):
        para = para.strip().lstrip("#").strip()
        if para and not para.startswith(">"):
            sentences = re.split(r"(?<=[.!?])\s+", para)
            return " ".join(sentences[:2])
    return f"Article about {concept}."
