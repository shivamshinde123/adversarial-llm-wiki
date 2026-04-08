"""Debate Engine — runs three-call debate pipeline and clarifying questions loop."""


def run_debate(topic: str, question: str, topic_dir) -> None:
    """Run the full debate pipeline for a question against a compiled topic.

    Retrieves relevant wiki articles for both sides, runs three sequential
    LLM calls (pro argues, con argues, hidden assumption surfacer), saves
    output to debates/[question-slug]/output.md, then enters the clarifying
    questions loop.

    Args:
        topic: Topic name.
        question: The user's question.
        topic_dir: Path to the topic root directory.
    """
    raise NotImplementedError("Debate Engine not yet implemented (Stage 4).")
