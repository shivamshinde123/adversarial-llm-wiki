# Adversarial Wiki

Two opposing knowledge bases that debate each other — and surface the hidden assumptions neither side is explicitly challenging.

Inspired by Karpathy's LLM Wiki pattern, extended with adversarial debate and assumption surfacing.

---

## What it does

Given any topic, Adversarial Wiki:

1. **Compiles two wikis** — one for each perspective — from your sources (manual mode) or by researching the web autonomously (auto mode).
2. **Debates them** — when you ask a question, the pro wiki argues its strongest case, the con wiki argues its strongest case, and a third LLM call surfaces the hidden assumption each side is making that the other side never challenges.
3. **Deepens your thinking** — after the initial debate, an interactive loop generates progressively targeted clarifying questions based on your answers and the wiki knowledge, appending every round to the output file.

The output is never a winner declaration. It is a structured map of the disagreement, designed to help you make a better decision.

---

## Installation

**Requirements:** Python 3.11+

```bash
git clone https://github.com/shivamshinde123/adversarial-llm-wiki.git
cd adversarial-llm-wiki
pip install -e .
```

**API keys** — copy `.env.example` to `.env` and fill in:

```env
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...   # only needed for --auto mode
```

---

## Quick start

### Manual mode

Drop your source files (`.md`, `.txt`, or `.url`) into the topic's raw folders, then compile:

```bash
# 1. Compile wikis from your own sources
adversarial-wiki compile --topic "remote-work" --manual
#   → put pro sources in:  topics/remote-work/raw/pro/
#   → put con sources in:  topics/remote-work/raw/con/

# 2. Ask a question
adversarial-wiki debate --topic "remote-work" --question "Should our team go fully remote?"

# 3. Check wiki health
adversarial-wiki lint --topic "remote-work"
```

### Auto mode

Let the tool research the web itself:

```bash
# Basic — tool picks its own stance descriptions
adversarial-wiki compile --topic "remote-work" --auto

# Custom stances
adversarial-wiki compile --topic "remote-work" --auto \
  --pro "remote work boosts individual productivity and well-being" \
  --con "remote work weakens team cohesion and company culture"
```

---

## Commands

### `compile`

Builds two wikis — `wiki/pro/` and `wiki/con/` — for a topic.

| Flag | Description |
|---|---|
| `--topic` | Topic name, used as the folder name (required) |
| `--manual` | Read sources from `raw/pro/` and `raw/con/` |
| `--auto` | Autonomously search the web and compile |
| `--pro` | Custom pro stance description (auto mode only) |
| `--con` | Custom con stance description (auto mode only) |

In **manual mode**, supported source formats are `.md`, `.txt`, and `.url` (one URL per line — fetched via trafilatura).

In **auto mode**, the tool generates search queries via LLM, searches via Tavily, fetches full page content via trafilatura, and compiles directly. No raw files are saved.

### `debate`

Asks a question against the compiled wikis and runs the full debate pipeline.

```bash
adversarial-wiki debate --topic "remote-work" --question "Is remote work better for deep focus?"
```

The pipeline makes **5 LLM calls** per debate:

| Call | What it does |
|---|---|
| 1 | Reads pro `index.md`, identifies relevant articles |
| 2 | Reads con `index.md`, identifies relevant articles |
| 3 | Pro side argues its strongest case, citing wiki articles |
| 4 | Con side argues its strongest case, citing wiki articles |
| 5 | Surfaces the hidden assumption each side makes; generates 3 clarifying questions |

After the debate is printed, an **interactive loop** begins. You answer the clarifying questions; the LLM generates 3 new, deeper questions grounded in your answers and the wiki. Type `stop` or press Enter to exit. Every round is appended to `output.md` — nothing is overwritten.

Output is saved to `topics/[topic]/debates/[question-slug]/output.md`.

### `lint`

Runs integrity checks on the compiled wikis and exits with code `1` if any issues are found (useful in CI).

```bash
adversarial-wiki lint --topic "remote-work"
```

Checks per side:

| Check | Modes |
|---|---|
| `wiki/pro/` and `wiki/con/` exist and are non-empty | both |
| `index.md` present | both |
| Every concept page referenced in `index.md` (no orphans) | both |
| All `[[wiki-links]]` resolve to existing pages | both |
| `sources.json` valid; all `used_in` entries point to real files | auto only |
| All article frontmatter has `mode` and `compiled` fields | auto only |

---

## Output format

`debates/[question-slug]/output.md`:

```markdown
# Question

Should our team go fully remote?

*Generated: 2026-04-08*

---

## Wiki A Argues

[Strongest pro argument with [[article-name]] citations]

---

## Wiki B Argues

[Strongest con argument with [[article-name]] citations]

---

## Hidden Assumptions

### Wiki A assumes:
[Core assumption the pro side makes that con never challenges]

### Wiki B assumes:
[Core assumption the con side makes that pro never challenges]

## Before You Decide, Answer These
1. [Clarifying question]
2. [Clarifying question]
3. [Clarifying question]

---

## Round 2

### Your Answers

[Your typed answers]

### New Questions Based On Your Answers
1. [Deeper question]
2. [Deeper question]
3. [Deeper question]

---

## Sources

### Wiki A (Pro)
- [[article-name]]

### Wiki B (Con)
- [[article-name]]
```

---

## Folder structure

All folders are created automatically — you never create them manually.

**Manual mode:**
```
topics/[topic-name]/
  raw/
    pro/          ← drop your source files here
    con/          ← drop your source files here
  wiki/
    pro/
      index.md
      [concept].md
      log.md
    con/
      index.md
      [concept].md
      log.md
  debates/
    [question-slug]/
      output.md
```

**Auto mode** (no `raw/` folder):
```
topics/[topic-name]/
  wiki/
    pro/
      sources.json
      index.md
      [concept].md
      log.md
    con/
      sources.json
      index.md
      [concept].md
      log.md
  debates/
    [question-slug]/
      output.md
```

Each wiki folder opens as a navigable graph in [Obsidian](https://obsidian.md) — all concept pages use `[[wiki-links]]` syntax with YAML frontmatter aliases.

---

## How the wiki compiler works

The compiler runs a multi-step LLM pipeline over your source content:

1. **Concept extraction** — identifies the major ideas across all sources
2. **Article writing** — writes one Markdown article per concept, citing sources with `[[wiki-links]]`
3. **Index generation** — writes `index.md` with a 2-3 sentence summary per article
4. **Log entry** — records what was compiled and when in `log.md`
5. **Contradiction flagging** — notes where sources within the same side disagree

In auto mode, each article's YAML frontmatter lists the URLs that contributed to it. A central `sources.json` per side tracks all sources with `used_in` cross-references.

The debate engine never loads all wiki files at once — it always reads `index.md` first, asks the LLM to identify relevant articles, then loads only those.

---

## Running tests

```bash
pytest
```

To run a single stage:

```bash
pytest tests/test_stage2.py
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `anthropic` | LLM calls (model: `claude-opus-4-6`) |
| `click` | CLI framework |
| `python-dotenv` | `.env` file loading |
| `trafilatura` | URL-to-text extraction |
| `tavily-python` | Web search (auto mode) |
| `rank-bm25` | Future: BM25 retrieval for large wikis |
