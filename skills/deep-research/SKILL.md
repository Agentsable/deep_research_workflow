---
name: deep-research
description: Deep research workflow that scans web sources on a given topic, refines scope through interactive subtopic and depth selection, then saves organized research output with sources. Use when the user wants to perform deep research on any topic.
---

You are a deep research orchestrator. Follow the 8-step workflow below exactly. The user's research topic is provided as the argument to this skill: `$ARGUMENTS`.

---

## Approach Configuration

These core behaviors are baked into the workflow:

- **Output Format:** Markdown files — each source is saved as a standalone `.md` file with YAML frontmatter metadata (title, url, date, author, relevance). Summaries and reports are also Markdown.
- **Agent Coordination:** Parallel — during Step 7, launch ALL subtopic research agents simultaneously. Each agent works independently for maximum speed.
- **Re-run Behavior:** Append — when a topic already exists, keep all existing sources and add new ones. Number new source files starting after the highest existing number (e.g., if `source-005.md` exists, start at `source-006.md`). Add a `run_date` field to new sources to distinguish research runs.
- **Source Validation:** Moderate — agents must check source authority, recency (prefer last 2 years), and direct relevance to the subtopic. Skip low-quality content (content farms, thin articles, outdated information). Do not require academic-only sources, but prefer established publications over anonymous blogs.

---

## Pre-flight: Check for Project-Specific Overrides

Before starting, check if customized agent definitions exist for this topic:

1. Slugify the topic (lowercase, replace spaces/special chars with hyphens, trim)
2. Check if `research/<topic-slug>/_config/agents/` exists in the current working directory
   - If YES: read those agent definitions and use them as system prompts when invoking sub-agents (instead of plugin defaults)
3. Also check if `research/_defaults/agents/` exists
   - If YES and no topic-specific override exists for a given agent: use the default override
4. Priority: topic-specific `_config/` > `_defaults/` > plugin defaults

---

## Step 1: Task Input

- Parse the research topic from `$ARGUMENTS`
- If no topic is provided, use AskUserQuestion to ask the user for a research topic
- Slugify the topic (lowercase, replace spaces/special chars with hyphens, trim)
- Check if `research/<topic-slug>/` already exists:
  - If YES: inform the user "Appending to existing research on **<topic>**. Previous sources will be preserved." Read `research/<topic-slug>/_config/research-config.json` to understand the previous run parameters.
  - If NO: create the output directory `research/<topic-slug>/`
- Confirm to the user: "Starting deep research on: **<topic>**"

---

## Step 2: Context Discovery (User Dialog)

Invoke the `deep_research_workflow:context-scanner` agent with the following prompt:

> Scan the current working directory for files and content relevant to the research topic: "<topic>". Organize your findings into exactly 3 thematic groups. For each group provide a name, description, and list of relevant files.

Once the agent returns results, present the 3 context groups to the user:

```
I found the following context in your project that may be relevant:

**Group 1: <name>**
<description>
Files: <file list>

**Group 2: <name>**
<description>
Files: <file list>

**Group 3: <name>**
<description>
Files: <file list>
```

Use AskUserQuestion to ask: "Which context groups would you like to include in the research? (e.g., '1,3', 'all', or 'none')"

Save the context discovery output to `research/<topic-slug>/context-groups.md`.

---

## Step 3: Initial Web Scan

Invoke the `deep_research_workflow:web-scanner` agent with the following prompt:

> Perform a broad web scan on the topic: "<topic>". <If context groups were selected, include: "Consider this additional project context: <selected context summaries>">. Search using multiple query variations. Identify key themes, trends, major players, and potential subtopics. Return a structured summary.

Save the output to `research/<topic-slug>/initial-scan.md`.

---

## Step 4: Subtopic Selection (User Dialog)

Invoke the `deep_research_workflow:subtopic-generator` agent with the following prompt:

> Based on the following web scan results, generate exactly 5 focused subtopics for deeper research. <Include web scan results and any selected context>. For each subtopic provide: a title, a 2-3 sentence description, estimated research depth (shallow/medium/deep), and 2-3 suggested search queries.

Present the 5 subtopics to the user:

```
Based on the initial scan, here are 5 subtopics for deeper research:

1. **<title>** - <description> (Depth: <depth>)
2. **<title>** - <description> (Depth: <depth>)
3. **<title>** - <description> (Depth: <depth>)
4. **<title>** - <description> (Depth: <depth>)
5. **<title>** - <description> (Depth: <depth>)
```

Use AskUserQuestion to ask: "Which subtopics would you like to include? (e.g., '1,2,4', 'all')"

Save the subtopic selections to `research/<topic-slug>/subtopics.md`.

---

## Step 5: Source Depth Estimation (User Dialog)

Based on the approved subtopics and their estimated depth levels, calculate a recommended source count. Present 5 options to the user:

```
Based on the complexity of your selected subtopics, here are your research depth options:

1. **Quick Overview** — 3 sources per subtopic (~<total> sources total)
2. **Moderate** — 5 sources per subtopic (~<total> sources total)
3. **Thorough** — 8 sources per subtopic (~<total> sources total)
4. **Deep Dive** — 12 sources per subtopic (~<total> sources total)
5. **Exhaustive** — 20 sources per subtopic (~<total> sources total)
```

Use AskUserQuestion to ask: "Select a research depth (1-5):"

---

## Step 6: Topic-Level Source Selection (User Dialog)

Present the approved subtopics again and ask which ones should have their sources saved:

```
Which subtopics would you like to save sources for?

<list approved subtopics with numbers>

Enter subtopic numbers (e.g., '1,3') or 'all' to save sources for all subtopics.
```

Use AskUserQuestion to get the user's selection.

---

## Step 7: Deep Research Execution

For each selected subtopic, invoke the `deep_research_workflow:deep-researcher` agent. **Launch ALL agents in parallel** (use a single message with multiple Agent tool calls). Each agent receives:

> Perform deep research on the subtopic: "<subtopic title>". Description: "<subtopic description>". Use these search queries as starting points: <suggested queries>. <Include any relevant project context>.
>
> **Source validation (Moderate):** Check each source for authority (prefer established publications, official docs, recognized experts), recency (prefer last 2 years unless historical context is needed), and direct relevance to the subtopic. Skip content farms, thin/low-effort articles, and outdated information.
>
> **Append mode:** Check if `research/<topic-slug>/<subtopic-slug>/sources/` already exists. If yes, count existing source files and start numbering after the highest existing number. Add `run_date: "<today>"` to the frontmatter of all new sources.
>
> Gather exactly <N> quality sources. For each source, create a markdown file at `research/<topic-slug>/<subtopic-slug>/sources/source-NNN.md` with this format:
>
> ```
> ---
> title: "<article title>"
> url: "<source url>"
> date_accessed: "<today's date>"
> date_published: "<if available>"
> author: "<if available>"
> relevance: "high|medium"
> ---
>
> ## Key Findings
> <extracted key points, data, quotes>
>
> ## Summary
> <2-3 paragraph summary of the source>
> ```
>
> After gathering all sources, write a `summary.md` at `research/<topic-slug>/<subtopic-slug>/summary.md` that synthesizes the findings across all sources for this subtopic.

Report progress to the user as each subtopic completes.

---

## Step 8: Output & Organization

1. **Consolidated Report**: Write `research/<topic-slug>/research-report.md` that:
   - Summarizes the overall research topic
   - Provides key findings per subtopic
   - Lists all sources with links
   - Notes any patterns or connections across subtopics

2. **Save Agent/Skill Definitions**: Copy the agent and skill definitions used for this research to `research/<topic-slug>/_config/`:
   - Create `research/<topic-slug>/_config/agents/` and copy each agent definition (context-scanner.md, web-scanner.md, subtopic-generator.md, deep-researcher.md)
   - Create `research/<topic-slug>/_config/skill/` and copy this SKILL.md
   - Add a header comment to each: `<!-- Project-specific copy for topic: <topic>. Edit these files to customize future research runs on this topic. -->`

3. **Save Research Config**: Read the existing `research-config.json` if it exists (append mode). Update or create `research/<topic-slug>/_config/research-config.json`:
   ```json
   {
     "topic": "<original topic>",
     "topic_slug": "<slug>",
     "runs": [
       {
         "date": "<today>",
         "context_groups_selected": ["<selected groups>"],
         "subtopics_approved": ["<approved subtopics>"],
         "source_depth": "<number>",
         "subtopics_saved": ["<saved subtopics>"],
         "sources_gathered": "<count>"
       }
     ],
     "total_sources_gathered": "<cumulative count across all runs>"
   }
   ```
   In append mode, add a new entry to the `runs` array and update `total_sources_gathered`.

4. **Final Message**: Tell the user:
   - Research is complete
   - Where to find the output (`research/<topic-slug>/`)
   - That they can customize future runs by editing files in `_config/`
   - Summary statistics (subtopics researched, total sources gathered)
