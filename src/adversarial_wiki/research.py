"""Auto Research Agent — searches the web and feeds content to the compiler."""

import json
import re
from datetime import date
from pathlib import Path

import click

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
      2. Hit Tavily to get URLs + snippets
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
        click.echo(f"  [{side}] Searching: {', '.join(queries)}")

        search_results = _search(queries)
        if not search_results:
            click.echo(f"  [{side}] Warning: no search results found.", err=True)
            continue

        click.echo(f"  [{side}] Fetching {len(search_results)} sources...")
        sources, source_records = _fetch_sources(search_results)

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
    """Ask LLM to generate 3-5 search queries for this stance."""
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
            cleaned = [str(q).strip() for q in queries if str(q).strip()][:5]
            if cleaned:  # Fix 1: guard against empty list after parsing
                return cleaned
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: one generic query
    return [f"{topic} {stance_desc}"]


# ---------------------------------------------------------------------------
# Step 2 — Web search via Tavily
# ---------------------------------------------------------------------------

def _search(queries: list[str]) -> list[dict]:
    """Run each query against DuckDuckGo and return deduplicated results."""
    from duckduckgo_search import DDGS

    seen_urls: set[str] = set()
    results: list[dict] = []

    with DDGS() as ddgs:
        for query in queries:
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

    return results


# ---------------------------------------------------------------------------
# Step 3 — Fetch full content
# ---------------------------------------------------------------------------

def _fetch_sources(search_results: list[dict]) -> tuple[list[tuple[str, str]], list[dict]]:
    """Fetch full text for each search result via trafilatura.

    Returns:
        sources: list of (filename, content) tuples ready for the compiler
        source_records: enriched dicts for sources.json
    """
    import trafilatura

    sources: list[tuple[str, str]] = []
    source_records: list[dict] = []

    for result in search_results:
        url = result["url"]
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                click.echo(f"  Warning: could not fetch {url}", err=True)
                continue
            text = trafilatura.extract(downloaded)
            if not text or not text.strip():
                click.echo(f"  Warning: no content extracted from {url}", err=True)
                continue

            filename = _url_to_filename(url)
            content = f"[Source: {url}]\n[Title: {result['title']}]\n\n{text}"
            sources.append((filename, content))
            source_records.append({
                "url": url,
                "title": result["title"],
                "retrieved": str(date.today()),
                "used_in": [],
            })
        except Exception as e:
            click.echo(f"  Warning: error fetching {url}: {e}", err=True)

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
    """Write sources.json to wiki/{side}/ listing all sources used."""
    wiki_dir = topic_dir / "wiki" / side
    wiki_dir.mkdir(parents=True, exist_ok=True)

    for record in source_records:
        record["used_in"] = _find_articles_using_url(record["url"], wiki_dir)

    data = {
        "topic": topic,
        "side": side,
        "compiled": str(date.today()),
        "mode": "auto",
        "sources": source_records,
    }
    (wiki_dir / "sources.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


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
