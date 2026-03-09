# app/prompts/

Prompt templates used by Claude agents and workflows.

## Principles
- Prompts are stored here, never embedded in business logic.
- Each prompt file is named for its purpose: `summarize_scenario.txt`, `draft_investor_summary.txt`, etc.
- Prompts reference named placeholders — they do not contain hardcoded deal data.
- Versioned: breaking prompt changes get a new filename or version suffix.

## Planned prompt files (Phase 2+)
- `summarize_scenario_outputs.txt`
- `explain_scenario_diff.txt`
- `draft_investor_summary.txt`
- `draft_committee_memo.txt`
- `classify_user_intent.txt`
