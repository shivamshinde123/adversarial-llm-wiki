"""Debate engine — three-call pipeline with smart retrieval.

Coordinates retrieval of relevant wiki articles from both sides, runs the
three LLM calls (pro argues, con argues, assumption surfacer), writes the
structured output, and optionally runs an interactive clarifying-questions
loop.
"""

from datetime import date
from pathlib import Path

import click
import logging

from adversarial_wiki import llm
from adversarial_wiki.utils import slugify

_MAX_ROUNDS = 10  # safety cap on clarifying questions loop


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
      6. Clarifying questions loop: user answers questions, LLM generates 3 deeper
         follow-ups each round; appended to output.md until user types stop/exit

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
    logger.info("retrieved pro=%d con=%d", len(pro_articles), len(con_articles))

    # Step 2: pro argues
    click.echo("  [Call 1/3] Pro side arguing...")
    pro_argument = _argue(topic, question, "pro", pro_articles)
    logger.debug("pro argument chars=%d", len(pro_argument))

    # Step 3: con argues
    click.echo("  [Call 2/3] Con side arguing...")
    con_argument = _argue(topic, question, "con", con_articles)
    logger.debug("con argument chars=%d", len(con_argument))

    # Step 4: hidden assumption surfacer
    click.echo("  [Call 3/3] Surfacing hidden assumptions...")
    assumptions = _surface_assumptions(topic, question, pro_argument, con_argument)
    logger.debug("assumptions chars=%d", len(assumptions))

    # Step 5: save output
    output_path = _save_output(question, pro_argument, con_argument, assumptions, topic_dir, pro_articles, con_articles)
    click.echo(f"\nDebate saved to: {output_path}")
    logger.info("output saved: %s", output_path)
    click.echo("\n" + "=" * 60)
    click.echo(_format_for_display(question, pro_argument, con_argument, assumptions))

    # Step 6: clarifying questions loop
    _clarifying_loop(topic, question, pro_argument, con_argument, pro_articles, con_articles, output_path)


# ---------------------------------------------------------------------------
# Step 1 — Smart retrieval
# ---------------------------------------------------------------------------

_FALLBACK_ARTICLE_LIMIT = 10


def _retrieve_articles(question: str, wiki_dir: Path, side: str) -> list[tuple[str, str]]:
    """Two-step retrieval: read index.md first, then only relevant articles.

    Loads only LLM-identified articles; falls back to at most
    _FALLBACK_ARTICLE_LIMIT articles when retrieval returns nothing.
    """
    index_path = wiki_dir / "index.md"
    if not index_path.exists():
        return []

    index_content = index_path.read_text(encoding="utf-8")

    # Pre-compute valid stems to guard against path traversal in LLM output
    valid_stems = {
        p.stem for p in wiki_dir.glob("*.md")
        if p.name not in ("index.md", "log.md")
    }

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

    # Load only identified articles that exist in the wiki (defense-in-depth)
    articles: list[tuple[str, str]] = []
    for slug in slugs:
        if slug not in valid_stems:
            continue
        article_path = wiki_dir / f"{slug}.md"
        content = article_path.read_text(encoding="utf-8")
        articles.append((slug, content))

    # Fallback: if retrieval returned nothing, load up to the cap
    if not articles:
        for md_file in sorted(wiki_dir.glob("*.md"))[:_FALLBACK_ARTICLE_LIMIT]:
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
# Step 6 — Clarifying questions loop
# ---------------------------------------------------------------------------

def _clarifying_loop(
    topic: str,
    question: str,
    pro_argument: str,
    con_argument: str,
    pro_articles: list[tuple[str, str]],
    con_articles: list[tuple[str, str]],
    output_path: Path,
) -> None:
    """Interactive loop: user answers questions, LLM generates deeper follow-ups.

    Each round is appended to output_path. Nothing is ever overwritten.
    Type 'stop' or 'exit' to quit.
    """
    all_answers: list[str] = []

    click.echo("\nAnswer the clarifying questions above, or type 'stop' to finish.")

    for round_num in range(2, _MAX_ROUNDS + 2):  # rounds 2..11 → 10 iterations max
        user_input = click.prompt(
            "\nYour answers (press Enter or type 'stop' to finish)",
            default="stop",
            prompt_suffix="\n> ",
        )
        if user_input.strip().lower() in ("stop", "exit"):
            break

        all_answers.append(user_input)

        click.echo(f"\n  [Round {round_num}] Generating follow-up questions...")
        new_questions = _generate_followup_questions(
            topic, question, pro_argument, con_argument,
            pro_articles, con_articles, all_answers,
        )

        round_text = _format_round(round_num, user_input, new_questions)
        _append_round(output_path, round_text)

        click.echo(f"\n{'=' * 60}")
        click.echo(new_questions)
        round_num += 1


def _generate_followup_questions(
    topic: str,
    question: str,
    pro_argument: str,
    con_argument: str,
    pro_articles: list[tuple[str, str]],
    con_articles: list[tuple[str, str]],
    all_answers: list[str],
) -> str:
    """Generate 3 follow-up questions grounded in wiki knowledge and user answers so far.

    Note: passes full wiki articles + all prior answers every round. Context grows
    linearly with round count and article count — acceptable for typical wikis but
    could approach token limits for very large topics in late rounds.
    """
    articles_text = (
        "### Wiki A (Pro) Articles\n" + _format_articles(pro_articles) +
        "\n\n### Wiki B (Con) Articles\n" + _format_articles(con_articles)
    )
    answers_text = "\n\n".join(
        f"Round {i + 1} answers:\n{ans}" for i, ans in enumerate(all_answers)
    )
    system = (
        "You are an epistemics analyst deepening a structured debate. "
        "The user has answered some clarifying questions. "
        "Generate exactly 3 new follow-up questions grounded in the wiki knowledge "
        "and informed by the user's answers so far. "
        "Questions must be progressively more targeted to the user's specific situation. "
        "Do not repeat questions the user has already answered. "
        "Structure your output EXACTLY as:\n\n"
        "### New Questions Based On Your Answers\n"
        "1. [question]\n"
        "2. [question]\n"
        "3. [question]"
    )
    user = (
        f"Topic: {topic}\n"
        f"Original question: {question}\n\n"
        f"## Debate Summary\n"
        f"### Pro argues:\n{pro_argument}\n\n"
        f"### Con argues:\n{con_argument}\n\n"
        f"## Wiki Articles\n{articles_text}\n\n"
        f"## User Answers So Far\n{answers_text}"
    )
    return llm.call(system, user)


def _format_round(round_num: int, user_answers: str, new_questions: str) -> str:
    """Format one round as a markdown section to append to output.md."""
    return (
        f"\n---\n\n"
        f"## Round {round_num}\n\n"
        f"### Your Answers\n\n{user_answers}\n\n"
        f"{new_questions}\n"
    )


def _append_round(output_path: Path, round_text: str) -> None:
    """Append a formatted round to the output file."""
    with output_path.open("a", encoding="utf-8") as f:
        f.write(round_text)


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
logger = logging.getLogger(__name__)
