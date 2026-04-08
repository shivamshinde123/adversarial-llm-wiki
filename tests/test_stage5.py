"""Tests for Stage 5 — Clarifying Questions Loop."""

from pathlib import Path
from unittest.mock import patch, call

from adversarial_wiki.debate import (
    _format_round,
    _append_round,
    _generate_followup_questions,
    _clarifying_loop,
    _MAX_ROUNDS,
)


# ---------------------------------------------------------------------------
# _format_round
# ---------------------------------------------------------------------------

def test_format_round_contains_round_header():
    text = _format_round(2, "My answer here.", "### New Questions\n1. Q1\n2. Q2\n3. Q3")
    assert "## Round 2" in text


def test_format_round_contains_your_answers():
    text = _format_round(3, "User typed this.", "### New Questions\n1. Q1\n2. Q2\n3. Q3")
    assert "### Your Answers" in text
    assert "User typed this." in text


def test_format_round_contains_new_questions():
    text = _format_round(2, "My answer.", "### New Questions Based On Your Answers\n1. Q1\n2. Q2\n3. Q3")
    assert "New Questions Based On Your Answers" in text
    assert "Q1" in text


def test_format_round_has_separator():
    text = _format_round(2, "answer", "questions")
    assert "---" in text


# ---------------------------------------------------------------------------
# _append_round
# ---------------------------------------------------------------------------

def test_append_round_adds_content(tmp_path):
    output = tmp_path / "output.md"
    output.write_text("# Question\n\nOriginal content.", encoding="utf-8")

    _append_round(output, "\n---\n\n## Round 2\n\n### Your Answers\n\nHello.\n")

    content = output.read_text()
    assert "Original content." in content
    assert "## Round 2" in content
    assert "Hello." in content


def test_append_round_does_not_overwrite(tmp_path):
    output = tmp_path / "output.md"
    output.write_text("# Existing\n", encoding="utf-8")

    _append_round(output, "\nRound 2 text.")
    _append_round(output, "\nRound 3 text.")

    content = output.read_text()
    assert "# Existing" in content
    assert "Round 2 text." in content
    assert "Round 3 text." in content


# ---------------------------------------------------------------------------
# _generate_followup_questions
# ---------------------------------------------------------------------------

@patch("adversarial_wiki.llm.call")
def test_generate_followup_questions_calls_llm(mock_llm):
    mock_llm.return_value = "### New Questions Based On Your Answers\n1. Q1\n2. Q2\n3. Q3"

    result = _generate_followup_questions(
        "remote work", "Should I go remote?",
        "Pro argument.", "Con argument.",
        [("productivity", "Content A")],
        [("burnout", "Content B")],
        ["I work best in isolation."],
    )

    assert mock_llm.call_count == 1
    assert "New Questions" in result


@patch("adversarial_wiki.llm.call")
def test_generate_followup_questions_includes_prior_answers(mock_llm):
    mock_llm.return_value = "### New Questions\n1. Q1\n2. Q2\n3. Q3"

    _generate_followup_questions(
        "topic", "question",
        "pro", "con",
        [], [],
        ["Answer round 1.", "Answer round 2."],
    )

    user_prompt = mock_llm.call_args[0][1]
    assert "Answer round 1." in user_prompt
    assert "Answer round 2." in user_prompt


# ---------------------------------------------------------------------------
# _clarifying_loop
# ---------------------------------------------------------------------------

@patch("adversarial_wiki.llm.call")
@patch("click.prompt")
def test_clarifying_loop_stop_immediately(mock_prompt, mock_llm, tmp_path):
    output = tmp_path / "output.md"
    output.write_text("# Initial content\n", encoding="utf-8")

    mock_prompt.return_value = "stop"

    _clarifying_loop(
        "topic", "question", "pro arg", "con arg",
        [("a", "content")], [("b", "content")], output,
    )

    mock_llm.assert_not_called()
    assert output.read_text() == "# Initial content\n"


@patch("adversarial_wiki.llm.call")
@patch("click.prompt")
def test_clarifying_loop_exit_keyword(mock_prompt, mock_llm, tmp_path):
    output = tmp_path / "output.md"
    output.write_text("# Initial\n", encoding="utf-8")

    mock_prompt.return_value = "exit"

    _clarifying_loop(
        "topic", "question", "pro", "con", [], [], output,
    )

    mock_llm.assert_not_called()


@patch("adversarial_wiki.llm.call")
@patch("click.prompt")
def test_clarifying_loop_one_round_appends_to_file(mock_prompt, mock_llm, tmp_path):
    output = tmp_path / "output.md"
    output.write_text("# Initial content\n", encoding="utf-8")

    mock_prompt.side_effect = ["I prefer solo work.", "stop"]
    mock_llm.return_value = "### New Questions Based On Your Answers\n1. Q1\n2. Q2\n3. Q3"

    _clarifying_loop(
        "remote work", "Should I go remote?",
        "Pro arg.", "Con arg.",
        [("productivity", "Prod content")],
        [("burnout", "Burn content")],
        output,
    )

    content = output.read_text()
    assert "# Initial content" in content
    assert "## Round 2" in content
    assert "I prefer solo work." in content
    assert "New Questions Based On Your Answers" in content
    assert mock_llm.call_count == 1


@patch("adversarial_wiki.llm.call")
@patch("click.prompt")
def test_clarifying_loop_two_rounds_accumulate_answers(mock_prompt, mock_llm, tmp_path):
    output = tmp_path / "output.md"
    output.write_text("# Initial\n", encoding="utf-8")

    mock_prompt.side_effect = ["Answer one.", "Answer two.", "stop"]
    mock_llm.side_effect = [
        "### New Questions Based On Your Answers\n1. Q1\n2. Q2\n3. Q3",
        "### New Questions Based On Your Answers\n1. Q4\n2. Q5\n3. Q6",
    ]

    _clarifying_loop(
        "topic", "question", "pro", "con", [], [], output,
    )

    content = output.read_text()
    assert "## Round 2" in content
    assert "## Round 3" in content
    assert "Answer one." in content
    assert "Answer two." in content
    # Second LLM call should have both answers in the user prompt
    second_call_user = mock_llm.call_args_list[1][0][1]
    assert "Answer one." in second_call_user
    assert "Answer two." in second_call_user


@patch("adversarial_wiki.llm.call")
@patch("click.prompt")
def test_clarifying_loop_respects_max_rounds(mock_prompt, mock_llm, tmp_path):
    output = tmp_path / "output.md"
    output.write_text("# Initial\n", encoding="utf-8")

    # Never type stop — loop should self-terminate at _MAX_ROUNDS
    mock_prompt.return_value = "My answer."
    mock_llm.return_value = "### New Questions\n1. Q\n2. Q\n3. Q"

    _clarifying_loop(
        "topic", "question", "pro", "con", [], [], output,
    )

    assert mock_llm.call_count == _MAX_ROUNDS
