"""Source reading — loads text content from files and URLs."""

import click
from pathlib import Path

SUPPORTED_SUFFIXES = {".md", ".txt", ".url"}


def read_source(path: Path) -> str:
    """Read a source file and return its text content.

    Supports .md, .txt plain text files and .url files (one URL per line
    that get fetched via trafilatura).
    """
    if path.suffix.lower() == ".url":
        return _fetch_urls(path.read_text(encoding="utf-8").strip().splitlines())

    return path.read_text(encoding="utf-8", errors="ignore")


def read_sources_from_dir(directory: Path) -> list[tuple[str, str]]:
    """Read all supported source files in a directory.

    Skips hidden files, unsupported extensions, and empty files.
    Returns a list of (filename, content) tuples.
    """
    if not directory.exists():
        return []

    results = []
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        content = read_source(path)
        if content.strip():
            results.append((path.name, content))
    return results


def _fetch_urls(urls: list[str]) -> str:
    """Fetch and extract text content from URLs using trafilatura.

    Skips blank lines and comments. Warns on fetch/parse failures but
    continues with remaining URLs.
    """
    import trafilatura

    parts = []
    for url in urls:
        url = url.strip()
        if not url or url.startswith("#"):
            continue
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                click.echo(f"  Warning: could not fetch {url}", err=True)
                continue
            text = trafilatura.extract(downloaded)
            if not text:
                click.echo(f"  Warning: no content extracted from {url}", err=True)
                continue
            parts.append(f"[Source: {url}]\n\n{text}")
        except Exception as e:
            click.echo(f"  Warning: error fetching {url}: {e}", err=True)
    return "\n\n---\n\n".join(parts)
