# Research Config Schema

The `research-config.json` file is generated in `research/<topic-slug>/_config/` after each research run. It captures all parameters and selections made during the workflow.

## Schema

```json
{
  "topic": "string — the original research topic provided by the user",
  "topic_slug": "string — slugified version used for directory naming",
  "date": "string — ISO date of the research run (YYYY-MM-DD)",
  "context_groups_selected": [
    "string — names of the context groups the user chose to include"
  ],
  "subtopics_approved": [
    {
      "title": "string — subtopic title",
      "description": "string — subtopic description",
      "depth": "string — shallow|medium|deep"
    }
  ],
  "source_depth": "number — sources per subtopic the user selected (3, 5, 8, 12, or 20)",
  "subtopics_saved": [
    "string — titles of subtopics the user chose to save sources for"
  ],
  "total_sources_gathered": "number — actual total sources saved across all subtopics"
}
```

## Usage

This config allows:
- Reproducing or continuing a research run with the same parameters
- Understanding what choices were made during an interactive session
- Comparing parameters across different research runs on the same or different topics
