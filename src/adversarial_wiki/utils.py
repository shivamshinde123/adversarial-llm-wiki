"""Shared utilities — topic directory management and text helpers.

Everything here is intentionally side-effect-free (except `init_topic_dirs`
which creates directories). Modules import from here; nothing here imports
from other adversarial_wiki modules to keep the dependency graph acyclic.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TOPICS_DIR = Path("topics")


def _validate_topic_name(topic: str) -> str:
    """Validate and return a safe single-component topic name.

    Rejects empty strings, '.', '..', and any name containing path separators
    or absolute path anchors — preventing path traversal via user-supplied topic names.

    Args:
        topic: Raw topic name from user input.

    Returns:
        Stripped, validated topic name.

    Raises:
        ValueError: If the name is unsafe or malformed.
    """
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must not be empty")
    if topic in {".", ".."}:
        raise ValueError("topic must not be '.' or '..'")
    if "/" in topic or "\\" in topic:
        raise ValueError("topic must not contain path separators")
    topic_path = Path(topic)
    # anchor is non-empty for absolute paths (e.g. "/foo" or "C:\\foo")
    # name != topic when topic contains separators that Path normalised away
    if topic_path.anchor or topic_path.name != topic:
        raise ValueError("topic must be a single relative directory name")
    return topic


def get_topic_dir(topic: str) -> Path:
    """Return the root path for a topic without creating it.

    Args:
        topic: Topic name (validated via `_validate_topic_name`).

    Returns:
        Path object pointing to topics/<topic>.
    """
    return TOPICS_DIR / _validate_topic_name(topic)


def init_topic_dirs(topic: str, mode: str) -> Path:
    """Create the required directory tree for a topic and return its root path.

    Manual mode creates:  raw/pro, raw/con, wiki/pro, wiki/con, debates/
    Auto mode creates:    wiki/pro, wiki/con, debates/

    The raw/ folder is intentionally absent in auto mode — sources are
    fetched on-the-fly and never persisted as raw files.

    Args:
        topic: Topic name (used as folder name).
        mode: 'manual' or 'auto'.

    Returns:
        Path to the topic root directory.

    Raises:
        ValueError: If mode is not 'manual' or 'auto', or topic is unsafe.
    """
    if mode not in {"manual", "auto"}:
        raise ValueError(f"mode must be 'manual' or 'auto', got {mode!r}")

    topic_dir = get_topic_dir(topic)

    # Always create wiki and debates dirs
    (topic_dir / "wiki" / "pro").mkdir(parents=True, exist_ok=True)
    (topic_dir / "wiki" / "con").mkdir(parents=True, exist_ok=True)
    (topic_dir / "debates").mkdir(parents=True, exist_ok=True)

    if mode == "manual":
        # raw/ is only used in manual mode — user drops source files here
        (topic_dir / "raw" / "pro").mkdir(parents=True, exist_ok=True)
        (topic_dir / "raw" / "con").mkdir(parents=True, exist_ok=True)

    logger.debug("Initialised topic dirs for '%s' (mode=%s) at %s", topic, mode, topic_dir)
    return topic_dir


def slugify(text: str) -> str:
    """Convert a title or question into a filesystem-safe, URL-friendly slug.

    Steps: lowercase → strip punctuation → collapse whitespace/underscores
    to hyphens → collapse repeated hyphens → truncate to 60 chars.

    Args:
        text: Any human-readable string (concept name, question, etc.).

    Returns:
        A slug safe to use as a filename or URL path segment (≤60 chars).
    """
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)        # remove punctuation except hyphens
    text = re.sub(r"[\s_]+", "-", text)          # spaces/underscores → hyphens
    text = re.sub(r"-+", "-", text)              # collapse repeated hyphens
    return text[:60].strip("-")


def extract_json(text: str) -> str:
    """Extract the first complete JSON array or object from free-form LLM output.

    LLM responses often wrap JSON in prose (e.g. "Here are the queries: [...]").
    This function finds the first `[` or `{` that starts valid JSON and returns
    only that JSON span, discarding surrounding text.

    Uses `json.JSONDecoder.raw_decode` which is O(n) and handles nested
    structures correctly — no manual bracket counting required.

    Args:
        text: Raw LLM response text that may contain embedded JSON.

    Returns:
        The extracted JSON string, or the original stripped text if no valid
        JSON array or object is found.
    """
    import json
    decoder = json.JSONDecoder()
    for start, ch in enumerate(text):
        if ch not in "[{":
            continue
        try:
            value, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, (list, dict)):
            return text[start: start + end]
    # No JSON found — return stripped original so callers get something to parse
    return text.strip()
