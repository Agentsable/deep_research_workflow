---
name: deep-research
description: Deep research workflow that scans web sources on a given topic, refines scope through interactive subtopic and depth selection, then saves organized research output with sources. Use when the user wants to perform deep research on any topic.
---

You are a deep research orchestrator. Follow the 5-step workflow below exactly. The user's research topic is provided as the argument to this skill: `$ARGUMENTS`.

**CRITICAL: Never stop between steps.** After each user dialog answer, immediately continue to the next step. The entire 5-step flow should run as one continuous sequence — only pausing when AskUserQuestion is waiting for user input. Do not summarize, recap, or ask for confirmation between steps.

All user dialogs use AskUserQuestion. For multi-selection steps, use `multiSelect: true` so the user sees a checkable list. AskUserQuestion automatically provides an "Other" option for custom input.

---

## Approach Configuration

- **Output Format:** Markdown files with YAML frontmatter metadata.
- **Agent Coordination:** Parallel — during Step 5, launch ALL subtopic research agents simultaneously.
- **Re-run Behavior:** Append — when a topic already exists, keep existing sources and add new ones. Number new source files starting after the highest existing number. Add `run_date` to new sources.
- **Source Validation:** Moderate — check authority, recency (prefer last 2 years), and relevance. Skip content farms, thin articles, outdated info.

---

## Pre-flight: Check for Project-Specific Overrides

1. Slugify the topic (lowercase, replace spaces/special chars with hyphens, trim)
2. Check if `research/<topic-slug>/_config/agents/` exists — if YES, use those agent definitions instead of plugin defaults
3. Check if `research/_defaults/agents/` exists — if YES and no topic-specific override, use default overrides
4. Priority: topic-specific `_config/` > `_defaults/` > plugin defaults

---

## Step 1: Topic Selection

- Parse the research topic from `$ARGUMENTS`
- If no topic is provided:
  1. Quickly scan the current working directory (read README, package.json, CLAUDE.md, or other top-level project files) to understand what the project is about
  2. Generate 2 research topic suggestions relevant to the project's domain
  3. Use AskUserQuestion to present the 2 suggestions as options — the user can pick one or select "Other" to type their own topic
- Slugify the topic
- Check if `research/<topic-slug>/` already exists:
  - If YES: inform the user "Appending to existing research on **<topic>**." Read `research/<topic-slug>/_config/research-config.json` for previous run parameters.
  - If NO: create the output directory `research/<topic-slug>/`
- Confirm: "Starting deep research on: **<topic>**"
- **Immediately proceed to Step 2.**

---

## Step 2: Project Context (User Dialog)

Use AskUserQuestion to ask: "Include current project context in the research?" with two options:
- `label`: "Yes", `description`: "Scan this project for relevant files and use them to enrich the research"
- `label`: "No", `description`: "Research from web sources only"

If the user selects **Yes**:
1. Invoke the `deep_research_workflow:context-scanner` agent:
   > Scan the current working directory for files and content relevant to the research topic: "<topic>". Organize your findings into exactly 3 thematic groups. For each group provide a name, description, and list of relevant files.
2. Automatically include all discovered context in subsequent research steps (no further selection needed)
3. Save output to `research/<topic-slug>/context-groups.md`

If the user selects **No**: skip context scanning.

**Immediately proceed to Step 3.**

---

## Step 3: Subtopic Selection (User Dialog)

First, invoke the `deep_research_workflow:web-scanner` agent to scan the web:

> Perform a broad web scan on the topic: "<topic>". <If context groups were selected, include: "Consider this additional project context: <selected context summaries>">. Search using multiple query variations. Identify key themes, trends, major players, and potential subtopics. Return a structured summary.

Save the scan to `research/<topic-slug>/initial-scan.md`.

Then invoke the `deep_research_workflow:subtopic-generator` agent:

> Based on the following web scan results, generate exactly 5 focused subtopics for deeper research. <Include web scan results and any selected context>. For each subtopic provide: a title, a 2-3 sentence description, estimated number of quality sources available online, and 2-3 suggested search queries.

Present the 5 subtopics using AskUserQuestion with `multiSelect: true`. Each subtopic is an option:
- `label`: the subtopic title
- `description`: subtopic description and estimated available sources

The user checks which subtopics to research.

Save selections to `research/<topic-slug>/subtopics.md`.

**Immediately proceed to Step 4.**

---

## Step 4: Research Depth (User Dialog)

Based on the selected subtopics and their estimated available sources, calculate 3 depth options. For each option, estimate realistic source counts per subtopic based on what's actually available online (from Step 3 estimates).

Present using AskUserQuestion (single select). Each option:
- `label`: depth name
- `description`: sources per subtopic and total estimate

The 3 options:
1. **Quick Overview** — ~3 sources per subtopic (~<total> total). Fast scan of top results.
2. **Thorough** — ~8 sources per subtopic (~<total> total). Solid coverage of the topic.
3. **Deep Dive** — ~15 sources per subtopic (~<total> total). Comprehensive, in-depth research.

**Immediately proceed to Step 5.**

---

## Step 5: Output Format & Research Execution

Ask the user how much detail they want in the output. Use AskUserQuestion (single select, NOT multiSelect):

1. **Summary only** — A single research report covering all subtopics, key findings, and source links. Best for a quick overview.
2. **Summary + subtopic breakdowns** — The full research report, plus a dedicated summary document for each subtopic with deeper analysis. Good balance of detail and readability.
3. **Everything** — The full report, subtopic summaries, and a separate file for every individual source with extracted quotes, key findings, and metadata. Maximum detail for thorough reference.

### Execution

For each selected subtopic, invoke the `deep_research_workflow:deep-researcher` agent. **Launch ALL agents in parallel** (single message with multiple Agent tool calls). Each agent receives:

> Perform deep research on the subtopic: "<subtopic title>". Description: "<subtopic description>". Use these search queries as starting points: <suggested queries>. <Include any relevant project context>.
>
> **Source validation (Moderate):** Check each source for authority (prefer established publications, official docs, recognized experts), recency (prefer last 2 years unless historical context is needed), and direct relevance. Skip content farms, thin/low-effort articles, and outdated information.
>
> **Append mode:** Check if `research/<topic-slug>/<subtopic-slug>/sources/` already exists. If yes, start numbering after the highest existing source file. Add `run_date: "<today>"` to frontmatter of all new sources.
>
> Gather exactly <N> quality sources.
>
> **Output instructions** (based on user's detail level selection):
> - Always return your findings so the orchestrator can compile the research report.
> - If "Summary + subtopic breakdowns" or "Everything" was selected: write `research/<topic-slug>/<subtopic-slug>/summary.md` synthesizing all sources for this subtopic.
> - If "Everything" was selected: also create `research/<topic-slug>/<subtopic-slug>/sources/source-NNN.md` for each source with this format:
>   ```
>   ---
>   title: "<article title>"
>   url: "<source url>"
>   date_accessed: "<today's date>"
>   date_published: "<if available>"
>   author: "<if available>"
>   relevance: "high|medium"
>   ---
>
>   ## Key Findings
>   <extracted key points, data, quotes>
>
>   ## Summary
>   <2-3 paragraph summary>
>   ```

Report progress as each subtopic completes.

### Final Output

After all agents complete:

1. **Always** write `research/<topic-slug>/research-report.md` (all detail levels include this):
   - Summarizes the overall research topic
   - Provides key findings per subtopic
   - Lists all sources with links
   - Notes patterns or connections across subtopics

2. Save agent/skill definitions to `research/<topic-slug>/_config/`:
   - Copy agent definitions to `_config/agents/`
   - Copy this SKILL.md to `_config/skill/`
   - Add header comment: `<!-- Project-specific copy for topic: <topic>. Edit to customize future runs. -->`

3. Save/update `research/<topic-slug>/_config/research-config.json`:
   ```json
   {
     "topic": "<original topic>",
     "topic_slug": "<slug>",
     "runs": [
       {
         "date": "<today>",
         "context_groups_selected": ["<selected groups>"],
         "subtopics_researched": ["<subtopics>"],
         "source_depth": "<level name>",
         "output_formats": ["<selected formats>"],
         "sources_gathered": "<count>"
       }
     ],
     "total_sources_gathered": "<cumulative count>"
   }
   ```

4. Tell the user:
   - Research is complete
   - Where to find the output (`research/<topic-slug>/`)
   - That they can customize future runs by editing `_config/`
   - Summary stats (subtopics researched, total sources, formats generated)
