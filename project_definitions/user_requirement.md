# Deep Research Workflow - User Requirements

## Overview

A Claude Code plugin that performs deep research on a given topic by scanning the web, refining scope through user interaction, and saving organized research outputs.

## Workflow Steps

### 1. Task Input
- The plugin is triggered via a skill/command called `deep_research`
- The user provides a research topic or task as input

### 2. Context Discovery (User Dialog)
- The agent scans the current working directory for existing files, documents, and code that may be relevant to the research topic
- It organizes the discovered context into **3 groups** based on thematic relevance
- The user is prompted via dialog to select which context groups to include in the research
- Included context will inform and enrich the subsequent web research

### 3. Initial Web Scan
- The agent scans the web for relevant information related to the given topic
- It identifies key themes, trends, and subtopics from the initial scan

### 4. Subtopic Selection (User Dialog)
- The agent generates a list of **5 subtopics** based on the initial scan
- The user is prompted to select which subtopics are relevant via an interactive dialog
- The user can approve or reject each subtopic

### 5. Source Depth Estimation
- Based on the selected subtopics, the agent estimates the depth level of the content
- It presents the user with **5 different options** for the number of sources to gather
- Each option reflects a different depth of research (e.g., light overview to exhaustive deep dive)
- The user selects their preferred source count

### 6. Topic-Level Source Selection
- The agent asks the user to select which approved subtopics they want to save sources for
- The user can either:
  - Select individual subtopics
  - Mark all subtopics for source saving

### 7. Deep Research Execution
- The agent performs deep research for each selected subtopic
- It gathers the estimated number of articles/sources the user requested per subtopic

### 8. Output & Organization
- All research is saved in a `research/` folder
- Sources are organized into subdirectories by subtopic/research topic
- Each source is saved with its content and metadata

## Agents & Skills Structure

The plugin uses a modular architecture with 1 skill and 4 specialized agents:

### Skill
- **`deep-research`** — Main entry point that orchestrates the full 8-step workflow, handles all user dialogs, and delegates to agents

### Agents
- **`context-scanner`** — Scans the project directory, organizes files into 3 thematic groups
- **`web-scanner`** — Performs initial broad web scan, identifies themes and trends
- **`subtopic-generator`** — Generates 5 focused subtopics from scan results
- **`deep-researcher`** — Deep research on a single subtopic, gathers and saves sources

### Per-Project Customization
- Agent and skill definitions are copied to `research/<topic>/_config/` after each run
- Users can edit these files to customize future research on the same topic
- Cross-topic defaults can be set in `research/_defaults/agents/`
- Priority order: topic-specific `_config/` > `_defaults/` > plugin defaults

## Approach Decisions

| Decision | Choice | Details |
|----------|--------|---------|
| Output Format | Markdown files | Each source as standalone `.md` with YAML frontmatter metadata |
| Agent Coordination | Parallel | All subtopic agents launch simultaneously for max speed |
| Re-run Behavior | Append | Keep existing sources, add new ones with incremental numbering and `run_date` tracking |
| Source Validation | Moderate | Check authority, recency (2yr), relevance; skip content farms and thin articles |
