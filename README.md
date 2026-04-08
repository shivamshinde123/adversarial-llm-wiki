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

## Example walkthrough

**Topic:** Should our team work remotely or onsite?

### Step 1 — Compile

```bash
adversarial-wiki compile --topic "remote-work" --auto \
  --pro "remote work boosts productivity and employee well-being" \
  --con "onsite work strengthens collaboration and company culture"
```

```
[pro] Generating search queries...
[pro] Searching: remote work productivity research, remote work employee wellbeing studies...
[pro] Fetching 8 sources...
[pro] Compiling wiki from 8 source(s)...
[con] Generating search queries...
[con] Searching: onsite work collaboration benefits, office culture productivity...
[con] Fetching 7 sources...
[con] Compiling wiki from 7 source(s)...
Done.
```

This creates two wikis under `topics/remote-work/wiki/` — one arguing for remote, one arguing for onsite — each as a set of linked concept pages.

### Step 2 — Debate

```bash
adversarial-wiki debate --topic "remote-work" \
  --question "Should our engineering team go fully remote?"
```

```
  Identifying relevant articles...
  Loaded 4 pro article(s), 3 con article(s).
  [Call 1/3] Pro side arguing...
  [Call 2/3] Con side arguing...
  [Call 3/3] Surfacing hidden assumptions...

============================================================
QUESTION: Should our engineering team go fully remote?

------------------------------------------------------------
WIKI A ARGUES
------------------------------------------------------------
Remote work consistently delivers higher individual output for deep-focus
engineering tasks. According to [[async-communication]], engineers working
remotely report 40% fewer interruptions and longer unbroken focus blocks.
[[productivity-research]] documents that remote engineers ship more features
per sprint when given autonomy over their environment...

------------------------------------------------------------
WIKI B ARGUES
------------------------------------------------------------
The strongest engineering work happens through informal, unplanned
collaboration — the hallway conversation, the whiteboard session, the
overheard problem. [[knowledge-transfer]] shows that onboarding time for
new engineers doubles in fully remote teams because tacit knowledge stops
flowing. [[team-cohesion]] links in-person time to psychological safety...

------------------------------------------------------------
HIDDEN ASSUMPTIONS & CLARIFYING QUESTIONS
------------------------------------------------------------
### Wiki A assumes:
The bottleneck for your team is individual focus and autonomy. It treats
engineering as primarily a solo activity interrupted by meetings, and
assumes your team already has strong communication habits that translate
to async channels.

### Wiki B assumes:
Your team's value comes primarily from emergent collaboration rather than
individual output. It assumes your engineers are early in their careers
or that your product is in a phase requiring high coordination, where
tacit knowledge transfer outweighs focus time.

## Before You Decide, Answer These
1. What is the current tenure mix on your team — mostly senior engineers
   who know the codebase, or a mix with several people still onboarding?
2. Is your product in a mature maintenance phase (where individual output
   dominates) or active feature exploration (where daily coordination matters)?
3. Have you measured whether your team's current bottleneck is interruptions
   and focus time, or alignment and shared understanding?
```

### Step 3 — Answer the clarifying questions

```
Answer the clarifying questions above, or type 'stop' to finish.

Your answers (press Enter or type 'stop' to finish)
> Mostly senior engineers, 3+ years on the codebase. We're in maintenance
  mode shipping incremental features. Our main complaint is too many meetings.

  [Round 2] Generating follow-up questions...

### New Questions Based On Your Answers
1. Do your senior engineers already have strong relationships with each
   other built from prior in-person time, or are some of them relatively
   new to the team despite being senior?
2. When you say "too many meetings" — are those meetings generating useful
   output, or are they coordination overhead that could be replaced by
   async documentation?
3. Is your leadership team also remote-capable, or would engineers go remote
   while managers remain onsite — and if so, how would that affect visibility
   and promotion dynamics?
```

The full history is saved to `topics/remote-work/debates/should-our-engineering-team-go-fully-remote/output.md`.

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

In **auto mode**, the tool generates search queries via LLM, searches via DuckDuckGo (no API key needed), fetches full page content via trafilatura, and compiles directly. No raw files are saved.

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

## Contributing

1. Open an issue describing what you want to change and why.
2. Fork the repository and create a branch from `master`.
3. Make your changes and ensure `pytest` passes.
4. Open a pull request against `master`, referencing the issue with `Ref #N`.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Dependencies

| Package | Purpose |
|---|---|
| `anthropic` | LLM calls (model: `claude-opus-4-6`) |
| `click` | CLI framework |
| `python-dotenv` | `.env` file loading |
| `trafilatura` | URL-to-text extraction |
| `duckduckgo-search` | Web search (auto mode, no API key needed) |
| `rank-bm25` | Future: BM25 retrieval for large wikis |
