# Graph Report - .  (2026-05-01)

## Corpus Check
- Corpus is ~45,586 words - fits in a single context window. You may not need a graph.

## Summary
- 304 nodes · 519 edges · 14 communities detected
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 125 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Debate Flow|Debate Flow]]
- [[_COMMUNITY_Wiki Compilation|Wiki Compilation]]
- [[_COMMUNITY_Lint Checks|Lint Checks]]
- [[_COMMUNITY_Research Pipeline|Research Pipeline]]
- [[_COMMUNITY_Flexibility Benefits|Flexibility Benefits]]
- [[_COMMUNITY_CLI Commands|CLI Commands]]
- [[_COMMUNITY_Project Architecture|Project Architecture]]
- [[_COMMUNITY_Pro Remote Evidence|Pro Remote Evidence]]
- [[_COMMUNITY_Con Remote Evidence|Con Remote Evidence]]
- [[_COMMUNITY_LLM Client|LLM Client]]
- [[_COMMUNITY_Source Ingestion|Source Ingestion]]
- [[_COMMUNITY_Debate Evidence|Debate Evidence]]

## God Nodes (most connected - your core abstractions)
1. `compile_wiki()` - 19 edges
2. `_lint_side()` - 16 edges
3. `extract_json()` - 13 edges
4. `read_sources_from_dir()` - 12 edges
5. `run_debate()` - 11 edges
6. `_clarifying_loop()` - 11 edges
7. `_parse_slug_list()` - 10 edges
8. `slugify()` - 10 edges
9. `_make_wiki()` - 10 edges
10. `_check_broken_links()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `test_auto_mode_article_has_frontmatter()` --calls--> `compile_wiki()`  [INFERRED]
  tests\test_stage3.py → src\adversarial_wiki\compiler.py
- `test_auto_mode_article_cites_url_in_frontmatter_when_body_mentions_it()` --calls--> `compile_wiki()`  [INFERRED]
  tests\test_stage3.py → src\adversarial_wiki\compiler.py
- `test_manual_mode_article_has_no_sources_list()` --calls--> `compile_wiki()`  [INFERRED]
  tests\test_stage3.py → src\adversarial_wiki\compiler.py
- `test_extract_json_array()` --calls--> `extract_json()`  [INFERRED]
  tests\test_stage3.py → src\adversarial_wiki\utils.py
- `Adversarial Wiki Overview` --semantically_similar_to--> `Adversarial Wiki`  [INFERRED] [semantically similar]
  README.md → CLAUDE.md

## Hyperedges (group relationships)
- **Adversarial Wiki Runtime Pipeline** — cli_cli_interface, compiler_wiki_compilation_engine, research_auto_research_agent, debate_debate_engine, lint_wiki_lint_checks [EXTRACTED 0.95]
- **Remote Work Con Argument Bundle** — output_should_our_team_go_fully_remote, collaboration_and_creativity_loss_in_virtual_environments, communication_lag_and_information_loss_in_remote_teams, data_bias_in_remote_work_studies, hybrid_workplace_management_complexity [EXTRACTED 0.96]
- **Remote Work Concerns Cluster** — remote_work_productivity_measurement_challenges_productivity_measurement_challenges, pandemic_context_and_productivity_decline_pandemic_productivity_decline, remote_worker_multitasking_and_overemployment_multitasking_overemployment, work_life_boundary_erosion_in_remote_work_boundary_erosion, remote_work_and_employee_emotional_well_being_emotional_well_being [EXTRACTED 0.92]
- **Remote Work Benefits Cluster** — access_to_a_wider_talent_pool_talent_pool_access, cost_savings_for_employees_and_employers_cost_savings, elimination_of_the_commute_commute_elimination, employee_retention_and_job_satisfaction_retention_satisfaction, environmental_benefits_of_remote_work_environmental_benefits [EXTRACTED 0.93]
- **Hybrid Mitigation Pattern** — hybrid_work_arrangements_hybrid_work, remote_collaboration_and_communication_tools_collaboration_tools, challenges_and_disadvantages_of_remote_work_remote_work_challenges [INFERRED 0.79]
- **Remote Work Core Benefits Cluster** — remote_work_flexibility_and_scheduling_remote_work_flexibility, remote_work_productivity_gains_remote_work_productivity, remote_worker_health_and_wellness_remote_worker_health, work_life_balance_improvement_work_life_balance [INFERRED 0.94]
- **Shared Stanford Productivity Evidence** — remote_work_flexibility_and_scheduling_stanford_study, remote_work_productivity_gains_stanford_study, return_to_office_mandates_vs_remote_work_data_stanford_study [EXTRACTED 0.99]
- **RTO Conflict with Remote Benefits** — return_to_office_mandates_vs_remote_work_data_rto_mandates, remote_work_flexibility_and_scheduling_remote_work_flexibility, remote_work_productivity_gains_remote_work_productivity, work_life_balance_improvement_work_life_balance [INFERRED 0.89]

## Communities

### Community 0 - "Debate Flow"
Cohesion: 0.05
Nodes (60): _append_round(), _argue(), _clarifying_loop(), _format_articles(), _format_for_display(), _format_output_md(), _format_round(), _format_sources() (+52 more)

### Community 1 - "Wiki Compilation"
Cohesion: 0.06
Nodes (49): _combine_sources(), compile_wiki(), _extract_concepts(), _extract_summary(), _flag_contradictions(), Wiki compilation engine.  Transforms raw sources into a structured per‑side wiki, Write a single wiki article and return its summary., Write index.md with a 2-3 sentence summary entry per article. (+41 more)

### Community 2 - "Lint Checks"
Cohesion: 0.07
Nodes (47): _check_broken_links(), _check_frontmatter(), _check_sources_json(), _get_concept_pages(), _lint_side(), _print_report(), Lint command — health checks for compiled wikis.  Collects structural integrit, Return all concept page paths in wiki_dir, excluding index.md and log.md. (+39 more)

### Community 3 - "Research Pipeline"
Cohesion: 0.09
Nodes (30): _fetch_sources(), _find_articles_using_url(), _generate_queries(), Auto research agent.  Searches the web (DuckDuckGo via `ddgs`), fetches full t, Run each query against DuckDuckGo and return deduplicated results.      Uses a, Fetch full text for each search result via trafilatura.      Per-URL failures, Write sources.json to wiki/{side}/ with full source attribution.      Scans al, Scan article files to find which ones reference this URL. (+22 more)

### Community 4 - "Flexibility Benefits"
Cohesion: 0.09
Nodes (28): ConnectSolutions Remote Work Productivity Survey, Flexible Scheduling as an Equity Tool, Longer Hours Risk, Remote Work Flexibility and Scheduling, Stanford Remote Work Study, Structured Flexibility Best Practices, Autonomy as a Productivity Mechanism, Corporate Pushback Against Remote Work Data (+20 more)

### Community 5 - "CLI Commands"
Cohesion: 0.13
Nodes (18): cli(), compile(), debate(), lint(), CLI entry point for adversarial-wiki.  This module wires the Click commands and, Run health checks on the compiled wikis for a topic., Initialize process-wide logging for the CLI.      Args:         verbosity: Count, Adversarial Wiki — two opposing knowledge bases that debate each other. (+10 more)

### Community 6 - "Project Architecture"
Cohesion: 0.22
Nodes (15): Adversarial Wiki, CLI Interface, Wiki Compilation Engine, Debate Engine, Wiki Lint Checks, Anthropic Client Wrapper, Adversarial Wiki Overview, Auto Research Agent (+7 more)

### Community 7 - "Pro Remote Evidence"
Cohesion: 0.47
Nodes (14): Apollo Technical Remote Work Statistics, Access to a Wider Talent Pool, WalkerWP Benefits Article, Business News Daily Remote Work Article, Challenges and Disadvantages of Remote Work, Cost Savings for Employees and Employers, Elimination of the Commute, Employee Retention and Job Satisfaction (+6 more)

### Community 8 - "Con Remote Evidence"
Cohesion: 0.41
Nodes (13): Remote Work Con Wiki Index, Industry-Specific Limitations of Remote Work, Remote Work Con Compilation Log, Long-Term Project Performance in Remote Settings, Pandemic Context and Productivity Decline, Productivity Measurement Reframing for Digital Workplaces, Remote Work and Employee Emotional Well-Being, Remote Work Learning Curve and Infrastructure Gaps (+5 more)

### Community 9 - "LLM Client"
Cohesion: 0.4
Nodes (5): call(), get_client(), LLM client wrapper.  Centralizes interaction with Anthropic and exposes a minima, Return a singleton Anthropic client using `ANTHROPIC_API_KEY`.      Raises a Cli, Make a single LLM call and return the text response.      Args:         system:

### Community 10 - "Source Ingestion"
Cohesion: 0.4
Nodes (5): _fetch_urls(), Source reading — loads text content from files and URLs.  Supported formats:   ., Read a single source file and return its text content.      For .url files, each, Fetch and extract plain text from a list of URLs via trafilatura.      Lines sta, read_source()

### Community 11 - "Debate Evidence"
Cohesion: 0.7
Nodes (5): Collaboration and Creativity Loss in Virtual Environments, Communication Lag and Information Loss in Remote Teams, Data Bias in Remote Work Studies, Hybrid Workplace Management Complexity, Should Our Team Go Fully Remote Debate Output

## Ambiguous Edges - Review These
- `Remote Work Productivity Measurement Challenges` → `Remote Collaboration and Communication Tools`  [AMBIGUOUS]
  topics/remote-work/wiki/pro/remote-collaboration-and-communication-tools.md · relation: conceptually_related_to

## Knowledge Gaps
- **83 isolated node(s):** `CLI entry point for adversarial-wiki.  This module wires the Click commands and`, `Initialize process-wide logging for the CLI.      Args:         verbosity: Count`, `Adversarial Wiki — two opposing knowledge bases that debate each other.`, `Compile two opposing wikis for a topic.`, `Ask a question and get a structured debate with hidden assumption surfacing.` (+78 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Remote Work Productivity Measurement Challenges` and `Remote Collaboration and Communication Tools`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `slugify()` connect `Wiki Compilation` to `Debate Flow`, `Lint Checks`, `CLI Commands`?**
  _High betweenness centrality (0.214) - this node is a cross-community bridge._
- **Why does `_check_broken_links()` connect `Lint Checks` to `Wiki Compilation`?**
  _High betweenness centrality (0.152) - this node is a cross-community bridge._
- **Why does `compile_wiki()` connect `Wiki Compilation` to `Research Pipeline`, `CLI Commands`?**
  _High betweenness centrality (0.130) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `compile_wiki()` (e.g. with `compile()` and `slugify()`) actually correct?**
  _`compile_wiki()` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `_lint_side()` (e.g. with `test_lint_side_passes_clean_manual_wiki()` and `test_lint_side_stem_substring_not_treated_as_reference()`) actually correct?**
  _`_lint_side()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `extract_json()` (e.g. with `_extract_concepts()` and `_flag_contradictions()`) actually correct?**
  _`extract_json()` has 11 INFERRED edges - model-reasoned connections that need verification._
