"""Source reading — loads text content from files and URLs.

Supported formats:
  .md / .txt  Plain text, read as-is.
  .url        One URL per line; each URL is fetched and extracted via trafilatura.
"""

import logging
from pathlib import Path

import click

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".md", ".txt", ".url"}


def read_source(path: Path) -> str:
    """Read a single source file and return its text content.

    For .url files, each non-blank, non-comment line is treated as a URL
    and fetched via trafilatura. All fetched texts are joined with separators.

    Args:
        path: Path to the source file.

    Returns:
        Full text content of the source (may be empty if fetching fails).
    """
    if path.suffix.lower() == ".url":
        logger.debug("Reading URL list from %s", path.name)
        return _fetch_urls(path.read_text(encoding="utf-8").strip().splitlines())

    logger.debug("Reading text file %s (%d bytes)", path.name, path.stat().st_size)
    return path.read_text(encoding="utf-8", errors="ignore")


def read_sources_from_dir(directory: Path) -> list[tuple[str, str]]:
    """Read all supported source files in a directory.

    Skips:
      - Directories and symlinks
      - Hidden files (names starting with '.')
      - Files with unsupported extensions
      - Files whose content is empty after stripping whitespace

    Args:
        directory: Path to the directory to scan.

    Returns:
        List of (filename, content) tuples, sorted by filename.
        Returns an empty list if the directory does not exist.
    """
    if not directory.exists():
        logger.debug("Source directory %s does not exist, returning empty", directory)
        return []

    results = []
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            logger.debug("Skipping hidden file: %s", path.name)
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            logger.debug("Skipping unsupported file type: %s", path.name)
            continue
        content = read_source(path)
        if content.strip():
            results.append((path.name, content))
        else:
            logger.debug("Skipping empty file: %s", path.name)

    logger.debug("Loaded %d source file(s) from %s", len(results), directory)
    return results


def _fetch_urls(urls: list[str]) -> str:
    """Fetch and extract plain text from a list of URLs via trafilatura.

    Lines starting with '#' are treated as comments and skipped.
    Per-URL failures are logged as warnings but do not abort the batch.

    Args:
        urls: List of URL strings (may include blank lines and comments).

    Returns:
        Extracted text from all successfully fetched URLs, separated by
        horizontal rules. Returns an empty string if all URLs fail.
    """
    import trafilatura

    parts = []
    for url in urls:
        url = url.strip()
        if not url or url.startswith("#"):
            continue  # skip blank lines and comments
        logger.debug("Fetching URL: %s", url)
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                click.echo(f"  Warning: could not fetch {url}", err=True)
                logger.warning("Could not fetch %s", url)
                continue
            text = trafilatura.extract(downloaded)
            if not text:
                click.echo(f"  Warning: no content extracted from {url}", err=True)
                logger.warning("No content extracted from %s", url)
                continue
            logger.debug("Fetched %d chars from %s", len(text), url)
            parts.append(f"[Source: {url}]\n\n{text}")
        except Exception as e:
            click.echo(f"  Warning: error fetching {url}: {e}", err=True)
            logger.warning("Error fetching %s: %s", url, e)

    return "\n\n---\n\n".join(parts)
