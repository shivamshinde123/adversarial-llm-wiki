"""Shared utilities — topic directory management and path helpers."""

from pathlib import Path


TOPICS_DIR = Path("topics")


def get_topic_dir(topic: str) -> Path:
    """Return the root path for a topic (does not create it)."""
    return TOPICS_DIR / topic


def init_topic_dirs(topic: str, mode: str) -> Path:
    """Create the required directory tree for a topic.

    Manual mode creates:  raw/pro, raw/con, wiki/pro, wiki/con, debates/
    Auto mode creates:    wiki/pro, wiki/con, debates/

    Args:
        topic: Topic name (used as folder name).
        mode: 'manual' or 'auto'.

    Returns:
        Path to the topic root directory.
    """
    topic_dir = get_topic_dir(topic)

    (topic_dir / "wiki" / "pro").mkdir(parents=True, exist_ok=True)
    (topic_dir / "wiki" / "con").mkdir(parents=True, exist_ok=True)
    (topic_dir / "debates").mkdir(parents=True, exist_ok=True)

    if mode == "manual":
        (topic_dir / "raw" / "pro").mkdir(parents=True, exist_ok=True)
        (topic_dir / "raw" / "con").mkdir(parents=True, exist_ok=True)

    return topic_dir


def slugify(text: str) -> str:
    """Convert a question or title into a filesystem-safe slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80].strip("-")
