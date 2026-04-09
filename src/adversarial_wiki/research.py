"""Auto research agent.

Searches the web (DuckDuckGo via `ddgs`), fetches full text with
`trafilatura`, and passes sources to the compiler to build per‑side wikis.
"""

import json
import re
from datetime import date
from pathlib import Path

import click
import logging

from adversarial_wiki import llm
from adversarial_wiki.compiler import compile_wiki
from adversarial_wiki.utils import extract_json


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_research(
    topic: str,
    pro_stance: str | None,
    con_stance: str | None,
    topic_dir: Path,
) -> None:
    """Search the web for both stances and compile wikis directly.

    Three steps per side:
      1. Generate search queries via LLM
      2. Search DuckDuckGo to get URLs + snippets
      3. Fetch full content via trafilatura, feed to compiler

    Sources are tracked in YAML frontmatter per article (handled by compiler)
    and in a central sources.json per side.

    Args:
        topic: Topic name.
        pro_stance: Optional custom pro stance description.
        con_stance: Optional custom con stance description.
        topic_dir: Path to the topic root directory.
    """
    pro_desc = pro_stance or f"arguments in favour of {topic}"
    con_desc = con_stance or f"arguments against {topic}"

    for side, stance_desc in [("pro", pro_desc), ("con", con_desc)]:
        click.echo(f"  [{side}] Generating search queries...")
        queries = _generate_queries(topic, side, stance_desc)
        logger.info("[%s] generated %d queries", side, len(queries))
        click.echo(f"  [{side}] Searching: {', '.join(queries)}")

        search_results = _search(queries)
        logger.info("[%s] search returned %d results", side, len(search_results))
        if not search_results:
            click.echo(f"  [{side}] Warning: no search results found.", err=True)
            continue

        click.echo(f"  [{side}] Fetching {len(search_results)} sources...")
        sources, source_records = _fetch_sources(search_results)
        logger.info("[%s] fetched %d sources", side, len(sources))

        if not sources:
            click.echo(f"  [{side}] Warning: could not fetch any source content.", err=True)
            continue

        click.echo(f"  [{side}] Compiling wiki from {len(sources)} source(s)...")
        compile_wiki(topic, side, sources, topic_dir, mode="auto", source_records=source_records)

        _write_sources_json(topic, side, source_records, topic_dir)
        click.echo(f"  [{side}] Done.")


# ---------------------------------------------------------------------------
# Step 1 — Query generation
# ---------------------------------------------------------------------------

def _generate_queries(topic: str, side: str, stance_desc: str) -> list[str]:
    """Ask LLM to generate 3-5 diverse search queries for this stance.

    Falls back to a single generic query if the LLM returns invalid JSON or
    an empty list — ensuring we always have something to search with.

    Args:
        topic: Topic name.
        side: 'pro' or 'con' perspective label.
        stance_desc: Human-readable stance description (used in the prompt).

    Returns:
        List of 1-5 search query strings.
    """
    system = (
        "You generate web search queries to research a specific perspective on a topic. "
        "Return ONLY a JSON array of 3-5 search query strings. "
        "Queries should be varied — some factual, some citing studies, some recent. "
        "Return ONLY valid JSON, nothing else."
    )
    user = (
        f"Topic: {topic}\n"
        f"Perspective to research: {stance_desc}\n\n"
        'Return a JSON array of search queries. Example: ["query one", "query two", "query three"]'
    )
    response = llm.call(system, user, max_tokens=512)
    try:
        queries = json.loads(extract_json(response))
        if isinstance(queries, list):
            # Cap at 5 and strip whitespace; guard against empty list after filtering
            cleaned = [str(q).strip() for q in queries if str(q).strip()][:5]
            if cleaned:
                logger.debug("[%s] generated queries: %s", side, cleaned)
                return cleaned
    except (json.JSONDecodeError, ValueError):
        logger.warning("[%s] could not parse query list, using fallback", side)
    # Fallback: one generic query combining topic and stance
    return [f"{topic} {stance_desc}"]


# ---------------------------------------------------------------------------
# Step 2 — Web search via DuckDuckGo
# ---------------------------------------------------------------------------

def _search(queries: list[str]) -> list[dict]:
    """Run each query against DuckDuckGo and return deduplicated results.

    Uses a single DDGS session for all queries (more efficient than
    opening a new connection per query). URLs are deduplicated globally
    across all queries so the same page isn't fetched twice.

    Args:
        queries: List of search query strings.

    Returns:
        List of result dicts with keys: url, title, snippet, query.
    """
    from ddgs import DDGS

    seen_urls: set[str] = set()
    results: list[dict] = []

    with DDGS() as ddgs:
        for query in queries:
            logger.debug("Searching: %r", query)
            try:
                for r in ddgs.text(query, max_results=5) or []:
                    url = r.get("href", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        results.append({
                            "url": url,
                            "title": r.get("title", ""),
                            "snippet": r.get("body", ""),
                            "query": query,
                        })
            except Exception as e:
                click.echo(f"  Warning: search failed for '{query}': {e}", err=True)
                logger.warning("Search failed for %r: %s", query, e)

    logger.debug("Search complete: %d unique URLs across %d queries", len(results), len(queries))
    return results


# ---------------------------------------------------------------------------
# Step 3 — Fetch full content
# ---------------------------------------------------------------------------

def _fetch_sources(search_results: list[dict]) -> tuple[list[tuple[str, str]], list[dict]]:
    """Fetch full text for each search result via trafilatura.

    Per-URL failures are warned and skipped — a partial result set is
    better than aborting the entire compilation.

    Args:
        search_results: List of result dicts from `_search`.

    Returns:
        sources: List of (filename, content) tuples ready for the compiler.
        source_records: Enriched dicts for sources.json with url/title/retrieved.
    """
    import trafilatura

    sources: list[tuple[str, str]] = []
    source_records: list[dict] = []

    for result in search_results:
        url = result["url"]
        logger.debug("Fetching %s", url)
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                click.echo(f"  Warning: could not fetch {url}", err=True)
                logger.warning("Could not fetch %s", url)
                continue
            text = trafilatura.extract(downloaded)
            if not text or not text.strip():
                click.echo(f"  Warning: no content extracted from {url}", err=True)
                logger.warning("No content extracted from %s", url)
                continue

            filename = _url_to_filename(url)
            # Prepend source metadata so the LLM can cite the URL in articles
            content = f"[Source: {url}]\n[Title: {result['title']}]\n\n{text}"
            sources.append((filename, content))
            source_records.append({
                "url": url,
                "title": result["title"],
                "retrieved": str(date.today()),
                "used_in": [],  # populated later by _write_sources_json
            })
            logger.debug("Fetched %d chars from %s", len(text), url)
        except Exception as e:
            click.echo(f"  Warning: error fetching {url}: {e}", err=True)
            logger.warning("Error fetching %s: %s", url, e)

    return sources, source_records


# ---------------------------------------------------------------------------
# sources.json
# ---------------------------------------------------------------------------

def _write_sources_json(
    topic: str,
    side: str,
    source_records: list[dict],
    topic_dir: Path,
) -> None:
    """Write sources.json to wiki/{side}/ with full source attribution.

    Scans all article files to populate the `used_in` field for each source
    record (i.e. which articles cite that URL). This must be called *after*
    `compile_wiki` so the article files already exist.

    Args:
        topic: Topic name.
        side: 'pro' or 'con'.
        source_records: List of source dicts (url, title, retrieved, used_in).
        topic_dir: Topic root directory.
    """
    wiki_dir = topic_dir / "wiki" / side
    wiki_dir.mkdir(parents=True, exist_ok=True)

    # Populate used_in by scanning articles for each URL
    for record in source_records:
        record["used_in"] = _find_articles_using_url(record["url"], wiki_dir)

    data = {
        "topic": topic,
        "side": side,
        "compiled": str(date.today()),
        "mode": "auto",
        "sources": source_records,
    }
    path = wiki_dir / "sources.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.debug("Wrote sources.json with %d records to %s", len(source_records), path)


def _find_articles_using_url(url: str, wiki_dir: Path) -> list[str]:
    """Scan article files to find which ones reference this URL."""
    used_in = []
    for md_file in wiki_dir.glob("*.md"):
        if md_file.name in ("index.md", "log.md"):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            if url in content:
                used_in.append(md_file.name)
        except Exception:
            pass
    return used_in


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _url_to_filename(url: str) -> str:
    """Convert a URL to a short readable filename."""
    name = re.sub(r"^https?://(www\.)?", "", url)
    name = re.sub(r"[^\w.-]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return f"{name[:60]}.txt"
logger = logging.getLogger(__name__)
