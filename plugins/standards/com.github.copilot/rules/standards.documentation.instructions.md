---
description: "Use when creating, moving, or updating any markdown document, plan, implementation note, or review file in this repo. Covers where docs are allowed to live and which docs must never be generated."
applyTo: "**/*.md"
---

# Documentation Standards

Documentation is generated sparingly and stored in one place. Unrequested markdown scattered through the repo is noise that goes stale and misleads future agents.

## Placement

**All documentation goes in `docs/`.** Not the repo root, not `PR-Reviews/`, not alongside source
- Plans and implementation artifacts → `docs/plans/`
- Anything that genuinely needs planning → use the `software-factory` skill, which produces the artifact in the right place
- Explaining something to the user → use the `show-me` skill, do not write a file

*Note: `.github/` is exempt: agent, skill, instruction, and prompt files live there by necessity.*

## When Documentation Is Appropriate
- When asked by the user or instructed via harness documents like skills, instructions or hooks

## Rules

### Do
- ALWAYS Adhere to these standards

### Do not
- NEVER generate **Codebase structure or manifest documents.** like a file that maps the directory tree, lists components, or inventories the stack. Reasons: subagents already search the codebase on demand and return exactly the relevant parts; structure changes constantly and agents do not reliably keep such files updated; it is repo noise.
- NEVER explicitly reference files that do not require it. For example: Skills or instructions are designed in a way that the harness provides the agent the information it needs, WHEN it needs it without coupling things together.

### Conditionals
- IF adding a fact to a document THEN FIRST check whether it already lives in a source file. If it does, reference the path rather than restating the value. Every copied value is a future contradiction.

