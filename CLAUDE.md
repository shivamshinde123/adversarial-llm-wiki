# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Adversarial Wiki is a CLI tool that takes two opposing sets of sources on any topic, compiles two separate wikis (one per perspective), and runs a structured debate between them when the user asks a question. The key output is not just two arguments — it is the hidden assumption each side is making that the other side is not explicitly challenging. Inspired by Karpathy's LLM Wiki pattern, extended with adversarial debate and assumption surfacing.

## CLI Interface

```bash
adversarial-wiki compile --topic "topic-name" --manual
adversarial-wiki compile --topic "topic-name" --auto
adversarial-wiki compile --topic "topic-name" --auto --pro "stance A" --con "stance B"
adversarial-wiki debate --topic "topic-name" --question "your question"
adversarial-wiki lint --topic "topic-name"
```

## Folder Structure

All folders are created automatically. Users never create folders manually.

**Manual mode:**
```
topics/[topic-name]/
  raw/pro/          ← user drops source files here
  raw/con/
  wiki/pro/
    index.md
    concept pages...
  wiki/con/
    index.md
    concept pages...
  debates/[question-slug]/output.md
```

**Auto mode** (no `raw/` folder):
```
topics/[topic-name]/
  wiki/pro/
    sources.json
    index.md
    concept pages...
  wiki/con/
    sources.json
    index.md
    concept pages...
  debates/[question-slug]/output.md
```

## Architecture

### Two Modes

- **--manual**: User manually sorts sources into `raw/pro/` and `raw/con/`. System reads those and compiles two wikis.
- **--auto**: User gives a topic and optional stance descriptions. System autonomously searches the web, reads sources on the fly, and compiles wikis directly. No raw files are saved.

### Wiki Structure (each side)

- `index.md` — master index with 2-3 sentence summary per article. **Read this first** on every question to identify relevant articles before loading anything else.
- Individual concept pages (one per major idea), using `[[wiki-links]]` syntax for Obsidian compatibility
- `log.md` — tracks what was compiled and when
- Contradiction flags when sources within the same side disagree

In auto mode, every article has YAML frontmatter listing which URLs contributed to it. `sources.json` per side tracks all sources across the entire compilation with `used_in` fields.

### Debate Engine (Three Sequential LLM Calls)

1. **Pro argues**: reads `index.md` → identifies relevant `wiki/pro/` articles → reads only those → generates strongest pro argument with article citations
2. **Con argues**: same process from `wiki/con/`
3. **Hidden assumption surfacer**: takes both arguments → finds the underlying assumption each side makes that the other does not challenge → generates 3 clarifying questions. Never picks a winner.

### Clarifying Questions Loop

After the initial debate output, the system enters a loop:
- User answers one or more clarifying questions
- LLM appends answers to `output.md` under `## Your Answers`
- LLM generates 3 new questions grounded in wiki knowledge + user's answers so far
- Loop continues until user types `stop` or `exit`
- Every round is appended — nothing is ever overwritten

### Output Format (`debates/[question-slug]/output.md`)

```
# Question
## Wiki A Argues        ← with citations to specific wiki articles
## Wiki B Argues        ← with citations to specific wiki articles
## Hidden Assumptions
  ### Wiki A assumes:
  ### Wiki B assumes:
## Before You Decide, Answer These
  1. 2. 3.
---
## Round 2
  ### Your Answers
  ### New Questions Based On Your Answers
  1. 2. 3.
[continues until stop/exit]
---
## Sources
```

## Key Invariants

- The system never passes all wiki files to the LLM at once — always reads `index.md` first, then only the identified relevant articles.
- LLM writes and maintains all wiki content. Users never manually edit wiki files.
- `[[wiki-links]]` syntax is used throughout so the wiki folder opens in Obsidian as a navigable graph.
- The debate output always has three parts: pro argument, con argument, hidden assumption layer. Never fewer.
- `raw/` folder does not exist in auto mode. In manual mode, `raw/` is the source of truth and no `sources.json` is needed.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
