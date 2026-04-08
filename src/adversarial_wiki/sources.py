"""Source reading — loads text content from files and URLs."""

from pathlib import Path


def read_source(path: Path) -> str:
    """Read a source file and return its text content.

    Supports .md, .txt plain text files and .url files (one URL per line
    that get fetched via trafilatura).
    """
    suffix = path.suffix.lower()

    if suffix == ".url":
        return _fetch_urls(path.read_text(encoding="utf-8").strip().splitlines())

    return path.read_text(encoding="utf-8", errors="ignore")


def read_sources_from_dir(directory: Path) -> list[tuple[str, str]]:
    """Read all source files in a directory.

    Returns a list of (filename, content) tuples, skipping empty files.
    """
    if not directory.exists():
        return []

    results = []
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        content = read_source(path)
        if content.strip():
            results.append((path.name, content))
    return results


def _fetch_urls(urls: list[str]) -> str:
    """Fetch and extract text content from URLs using trafilatura."""
    import trafilatura

    parts = []
    for url in urls:
        url = url.strip()
        if not url or url.startswith("#"):
            continue
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            if text:
                parts.append(f"[Source: {url}]\n\n{text}")
    return "\n\n---\n\n".join(parts)
