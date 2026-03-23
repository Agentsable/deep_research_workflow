---
name: deep-research
description: Deep research workflow that scans web sources on a given topic, refines scope through interactive subtopic and depth selection, then saves organized research output with sources. Use when the user wants to perform deep research on any topic.
---

You are a deep research orchestrator. Follow the workflow below exactly. The user's research topic is provided as the argument to this skill: `$ARGUMENTS`.

**CRITICAL: Never stop between steps.** After each user dialog answer, immediately continue to the next step. The entire flow should run as one continuous sequence — only pausing when AskUserQuestion is waiting for user input. Do not summarize, recap, or ask for confirmation between steps.

All user dialogs use AskUserQuestion. For multi-selection steps, use `multiSelect: true` so the user sees a checkable list. AskUserQuestion automatically provides an "Other" option for custom input.

---

## Approach Configuration

- **Output Format:** Markdown files with YAML frontmatter metadata.
- **Agent Coordination:** Parallel — launch context-scanner and web-scanner simultaneously, then launch ALL subtopic research agents simultaneously.
- **Re-run Behavior:** Append — when a topic already exists, keep existing sources and add new ones. Number new source files starting after the highest existing number. Add `run_date` to new sources.
- **Source Validation:** Moderate — check authority, recency (prefer last 2 years), and relevance. Skip content farms, thin articles, outdated info.

---

## Pre-flight: Check for Project-Specific Overrides

1. Slugify the topic (lowercase, replace spaces/special chars with hyphens, trim)
2. Check if `research/<topic-slug>/_config/agents/` exists — if YES, use those agent definitions instead of plugin defaults
3. Check if `research/_defaults/agents/` exists — if YES and no topic-specific override, use default overrides
4. Priority: topic-specific `_config/` > `_defaults/` > plugin defaults

---

## Step 1: Topic & Context Selection

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

Then immediately ask about project context using AskUserQuestion: "Include current project context in the research?" with two options:
- `label`: "Yes", `description`: "Scan this project for relevant files and use them to enrich the research"
- `label`: "No", `description`: "Research from web sources only"

**Immediately proceed to Step 2 after the user answers.**

---

## Step 2: Parallel Scanning

Launch agents in parallel based on the user's context choice:

**If the user selected "Yes" to context**: Launch BOTH agents in parallel (single message with multiple Agent tool calls):

1. `deep_research_workflow:context-scanner` agent:
   > Scan the current working directory for files and content relevant to the research topic: "<topic>". Organize your findings into exactly 3 thematic groups. For each group provide a name, description, and list of relevant files.

2. `deep_research_workflow:web-scanner` agent:
   > Perform a broad web scan on the topic: "<topic>". Search using multiple query variations. Identify key themes, trends, major players, and potential subtopics. Then generate exactly 5 focused subtopics for deeper research. For each subtopic provide: a title, a 2-3 sentence description, estimated depth (shallow/medium/deep), and 2-3 suggested search queries. Return the scan overview and subtopics in a single structured output.

**If the user selected "No" to context**: Launch only the web-scanner agent (same prompt as above, without context).

After both agents complete:
- Save context output (if any) to `research/<topic-slug>/context-groups.md`
- Save web scan + subtopics to `research/<topic-slug>/initial-scan.md`

**Immediately proceed to Step 3.**

---

## Step 3: Subtopic & Depth Selection (User Dialog)

Present the 5 subtopics from the web-scanner using AskUserQuestion with `multiSelect: true`. Each subtopic is an option:
- `label`: the subtopic title
- `description`: subtopic description and estimated depth

In the question text, include: "Select subtopics to research. Default depth is **Thorough** (~8 sources per subtopic). Select 'Other' to specify a different depth (Quick ~3, or Deep Dive ~15)."

Save selections to `research/<topic-slug>/subtopics.md`.

Parse the depth from the user's response. If no depth override, default to **Thorough** (~8 sources per subtopic).

**Immediately proceed to Step 4.**

---

## Step 4: Research Execution

All research output is always saved to disk — the full report, subtopic summaries, and individual source files.

### Execution

For each selected subtopic, invoke the `deep_research_workflow:deep-researcher` agent. **Launch ALL agents in parallel** (single message with multiple Agent tool calls). Each agent receives:

> Perform deep research on the subtopic: "<subtopic title>". Description: "<subtopic description>". Use these search queries as starting points: <suggested queries>. <Include any relevant project context from context-groups if available>.
>
> **Work in two phases**: Phase 1 — run all searches (3-5 WebSearch calls) and collect a ranked list of candidate URLs. Phase 2 — batch fetch the best candidates using WebFetch, then extract and save.
>
> **Source validation (Moderate):** Check each source for authority (prefer established publications, official docs, recognized experts), recency (prefer last 2 years unless historical context is needed), and direct relevance. Skip content farms, thin/low-effort articles, and outdated information.
>
> **Append mode:** Check if `research/<topic-slug>/<subtopic-slug>/sources/` already exists. If yes, start numbering after the highest existing source file. Add `run_date: "<today>"` to frontmatter of all new sources.
>
> Gather exactly <N> quality sources.
>
> **Output instructions:**
> - **Always save all files to disk.** Do not just return findings in your output — you MUST write them to files using the Write tool.
> - Write `research/<topic-slug>/<subtopic-slug>/summary.md` synthesizing all sources for this subtopic.
> - Create `research/<topic-slug>/<subtopic-slug>/sources/source-NNN.md` for each source with this format:
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

1. Write `research/<topic-slug>/research-report.md`:
   - Summarizes the overall research topic
   - Provides key findings per subtopic
   - Lists all sources with links
   - Notes patterns or connections across subtopics

2. Save/update `research/<topic-slug>/_config/research-config.json`:
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
         "sources_gathered": "<count>"
       }
     ],
     "total_sources_gathered": "<cumulative count>"
   }
   ```

3. Tell the user:
   - Research is complete
   - Where to find the output (`research/<topic-slug>/`)
   - That they can customize future runs by editing `_config/`
   - Summary stats (subtopics researched, total sources)
   - Note: run `/deep-research config <topic>` to copy agent definitions for customization
