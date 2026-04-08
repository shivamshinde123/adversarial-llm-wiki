"""Debate Engine — three-call debate pipeline with smart retrieval."""

from datetime import date
from pathlib import Path

import click

from adversarial_wiki import llm
from adversarial_wiki.utils import slugify


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_debate(topic: str, question: str, topic_dir: Path) -> None:
    """Run the full debate pipeline for a question against a compiled topic.

    Steps:
      1. Smart retrieval: read index.md from both sides, identify relevant articles
      2. Call 1 — Pro argues: strongest pro argument, grounded in wiki/pro articles
      3. Call 2 — Con argues: strongest con argument, grounded in wiki/con articles
      4. Call 3 — Hidden assumption surfacer: finds underlying assumptions, generates
         3 clarifying questions
      5. Save structured output to debates/[question-slug]/output.md

    Args:
        topic: Topic name.
        question: The user's question.
        topic_dir: Path to the topic root directory.
    """
    wiki_pro = topic_dir / "wiki" / "pro"
    wiki_con = topic_dir / "wiki" / "con"

    # Step 1: smart retrieval
    click.echo("  Identifying relevant articles...")
    pro_articles = _retrieve_articles(question, wiki_pro, "pro")
    con_articles = _retrieve_articles(question, wiki_con, "con")

    click.echo(f"  Loaded {len(pro_articles)} pro article(s), {len(con_articles)} con article(s).")

    # Step 2: pro argues
    click.echo("  [Call 1/3] Pro side arguing...")
    pro_argument = _argue(topic, question, "pro", pro_articles)

    # Step 3: con argues
    click.echo("  [Call 2/3] Con side arguing...")
    con_argument = _argue(topic, question, "con", con_articles)

    # Step 4: hidden assumption surfacer
    click.echo("  [Call 3/3] Surfacing hidden assumptions...")
    assumptions = _surface_assumptions(topic, question, pro_argument, con_argument)

    # Step 5: save output
    output_path = _save_output(question, pro_argument, con_argument, assumptions, topic_dir, pro_articles, con_articles)
    click.echo(f"\nDebate saved to: {output_path}")
    click.echo("\n" + "=" * 60)
    click.echo(_format_for_display(question, pro_argument, con_argument, assumptions))


# ---------------------------------------------------------------------------
# Step 1 — Smart retrieval
# ---------------------------------------------------------------------------

def _retrieve_articles(question: str, wiki_dir: Path, side: str) -> list[tuple[str, str]]:
    """Two-step retrieval: read index.md first, then only relevant articles.

    Never loads all wiki files at once.
    """
    index_path = wiki_dir / "index.md"
    if not index_path.exists():
        return []

    index_content = index_path.read_text(encoding="utf-8")

    # Ask LLM which articles are relevant based on index summaries
    system = (
        "You are a retrieval assistant for a wiki knowledge base. "
        "Given a user question and a wiki index (which contains article titles and summaries), "
        "identify which articles are relevant to answering the question. "
        "Return ONLY a JSON array of article filenames (without the .md extension). "
        "Be selective — only include articles that are genuinely relevant. "
        "Return ONLY valid JSON, nothing else."
    )
    user = (
        f"Question: {question}\n\n"
        f"Wiki index ({side} side):\n{index_content}\n\n"
        "Return a JSON array of relevant article slugs. "
        'Example: ["productivity", "work-life-balance"]'
    )
    response = llm.call(system, user, max_tokens=512)

    slugs = _parse_slug_list(response)

    # Load only the identified articles
    articles: list[tuple[str, str]] = []
    for slug in slugs:
        article_path = wiki_dir / f"{slug}.md"
        if article_path.exists():
            content = article_path.read_text(encoding="utf-8")
            articles.append((slug, content))

    # Fallback: if retrieval returned nothing, load all non-index articles
    if not articles:
        for md_file in sorted(wiki_dir.glob("*.md")):
            if md_file.name not in ("index.md", "log.md"):
                articles.append((md_file.stem, md_file.read_text(encoding="utf-8")))

    return articles


# ---------------------------------------------------------------------------
# Step 2 & 3 — Argue
# ---------------------------------------------------------------------------

def _argue(
    topic: str,
    question: str,
    side: str,
    articles: list[tuple[str, str]],
) -> str:
    """Generate the strongest argument for one side grounded in its wiki articles."""
    articles_text = _format_articles(articles)

    system = (
        f"You are arguing the {side} perspective in a structured debate. "
        "Your argument must be grounded strictly in the provided wiki articles — "
        "do not introduce outside information. "
        "Make the strongest possible case for your side. "
        "Cite specific wiki articles by name using [[article-name]] syntax. "
        "Structure your argument with clear paragraphs. "
        "Be direct and substantive — no preamble."
    )
    user = (
        f"Topic: {topic}\n"
        f"Question: {question}\n\n"
        f"Your wiki articles ({side} perspective):\n{articles_text}"
    )
    return llm.call(system, user)


# ---------------------------------------------------------------------------
# Step 4 — Hidden assumption surfacer
# ---------------------------------------------------------------------------

def _surface_assumptions(
    topic: str,
    question: str,
    pro_argument: str,
    con_argument: str,
) -> str:
    """Find hidden assumptions in both arguments and generate clarifying questions."""
    system = (
        "You are an epistemics analyst examining a structured debate. "
        "Your job is NOT to pick a winner. "
        "Your job is to find the underlying assumption each side is making "
        "that the other side is not explicitly challenging. "
        "Then generate 3 clarifying questions the user should answer before making a decision. "
        "The questions should be progressively more targeted to the user's specific situation. "
        "Structure your output EXACTLY as:\n\n"
        "### Wiki A assumes:\n[one paragraph describing the core assumption]\n\n"
        "### Wiki B assumes:\n[one paragraph describing the core assumption]\n\n"
        "## Before You Decide, Answer These\n"
        "1. [question]\n"
        "2. [question]\n"
        "3. [question]"
    )
    user = (
        f"Topic: {topic}\n"
        f"Question: {question}\n\n"
        f"## Wiki A (Pro) Argues:\n{pro_argument}\n\n"
        f"## Wiki B (Con) Argues:\n{con_argument}"
    )
    return llm.call(system, user)


# ---------------------------------------------------------------------------
# Step 5 — Output formatting and saving
# ---------------------------------------------------------------------------

def _save_output(
    question: str,
    pro_argument: str,
    con_argument: str,
    assumptions: str,
    topic_dir: Path,
    pro_articles: list[tuple[str, str]] | None = None,
    con_articles: list[tuple[str, str]] | None = None,
) -> Path:
    """Format and save the debate output to debates/[question-slug]/output.md."""
    slug = slugify(question)
    debate_dir = topic_dir / "debates" / slug
    debate_dir.mkdir(parents=True, exist_ok=True)
    output_path = debate_dir / "output.md"

    content = _format_output_md(question, pro_argument, con_argument, assumptions, pro_articles, con_articles)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _format_output_md(
    question: str,
    pro_argument: str,
    con_argument: str,
    assumptions: str,
    pro_articles: list[tuple[str, str]] | None = None,
    con_articles: list[tuple[str, str]] | None = None,
) -> str:
    sources_section = _format_sources(pro_articles or [], con_articles or [])
    return (
        f"# Question\n\n{question}\n\n"
        f"*Generated: {date.today()}*\n\n"
        "---\n\n"
        f"## Wiki A Argues\n\n{pro_argument}\n\n"
        "---\n\n"
        f"## Wiki B Argues\n\n{con_argument}\n\n"
        "---\n\n"
        f"## Hidden Assumptions\n\n{assumptions}\n\n"
        "---\n\n"
        f"## Sources\n\n{sources_section}"
    )


def _format_for_display(
    question: str,
    pro_argument: str,
    con_argument: str,
    assumptions: str,
) -> str:
    """Compact terminal display of the debate result."""
    sep = "-" * 60
    return (
        f"QUESTION: {question}\n\n"
        f"{sep}\nWIKI A ARGUES\n{sep}\n{pro_argument}\n\n"
        f"{sep}\nWIKI B ARGUES\n{sep}\n{con_argument}\n\n"
        f"{sep}\nHIDDEN ASSUMPTIONS & CLARIFYING QUESTIONS\n{sep}\n{assumptions}\n"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_slug_list(response: str) -> list[str]:
    """Parse a JSON array of slugs from an LLM response.

    Strips the .md extension if present and discards any slug that contains
    path separators or '..' to prevent path traversal via LLM-returned values.
    """
    import json
    import re
    from adversarial_wiki.utils import extract_json
    try:
        parsed = json.loads(extract_json(response))
        if isinstance(parsed, list):
            slugs = []
            for s in parsed:
                slug = str(s).strip().removesuffix(".md")
                # Reject slugs with path separators or parent-directory components
                if slug and not re.search(r'[/\\]|\.\.', slug):
                    slugs.append(slug)
            return slugs
    except (json.JSONDecodeError, ValueError):
        pass
    return []


def _format_sources(
    pro_articles: list[tuple[str, str]],
    con_articles: list[tuple[str, str]],
) -> str:
    """Format a sources section listing the wiki articles consulted on each side."""
    def _bullet_list(articles: list[tuple[str, str]]) -> str:
        return "\n".join(f"- [[{slug}]]" for slug, _ in articles) or "*none*"

    return (
        f"### Wiki A (Pro)\n{_bullet_list(pro_articles)}\n\n"
        f"### Wiki B (Con)\n{_bullet_list(con_articles)}\n"
    )


def _format_articles(articles: list[tuple[str, str]]) -> str:
    parts = []
    for slug, content in articles:
        parts.append(f"=== Article: {slug} ===\n\n{content}")
    return "\n\n---\n\n".join(parts)
