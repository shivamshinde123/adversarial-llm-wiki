"""Shared utilities — topic directory management and path helpers."""

from pathlib import Path


TOPICS_DIR = Path("topics")


def _validate_topic_name(topic: str) -> str:
    """Validate that topic is a single safe directory name."""
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must not be empty")
    if topic in {".", ".."}:
        raise ValueError("topic must not be '.' or '..'")
    if "/" in topic or "\\" in topic:
        raise ValueError("topic must not contain path separators")
    topic_path = Path(topic)
    if topic_path.anchor or topic_path.name != topic:
        raise ValueError("topic must be a single relative directory name")
    return topic


def get_topic_dir(topic: str) -> Path:
    """Return the root path for a topic (does not create it)."""
    return TOPICS_DIR / _validate_topic_name(topic)


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
    if mode not in {"manual", "auto"}:
        raise ValueError(f"mode must be 'manual' or 'auto', got {mode!r}")

    topic_dir = get_topic_dir(topic)

    (topic_dir / "wiki" / "pro").mkdir(parents=True, exist_ok=True)
    (topic_dir / "wiki" / "con").mkdir(parents=True, exist_ok=True)
    (topic_dir / "debates").mkdir(parents=True, exist_ok=True)

    if mode == "manual":
        (topic_dir / "raw" / "pro").mkdir(parents=True, exist_ok=True)
        (topic_dir / "raw" / "con").mkdir(parents=True, exist_ok=True)

    return topic_dir


def slugify(text: str) -> str:
    """Convert a title or question into a filesystem-safe slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")


def extract_json(text: str) -> str:
    """Extract the first complete JSON array or object from *text*.

    Uses bracket-matching (respecting strings and escape sequences) to avoid
    greedy over-capture.  Returns *text* stripped if no bracket is found.
    """
    start: int | None = None
    opening = closing = ""

    for i, ch in enumerate(text):
        if ch == "[":
            start, opening, closing = i, "[", "]"
            break
        if ch == "{":
            start, opening, closing = i, "{", "}"
            break

    if start is None:
        return text.strip()

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return text.strip()
