# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Django app that collects user input through configurable measures, instruments and conditions. Axis uses it
for checklists, so changes here can change what users answer and see.

## Team-wide rules

- When instructions don't match the current state (e.g. "update the PR" but no PR exists, "fix the test"
  but it passes), STOP and ask. Don't create or change things that weren't asked for.
- **Never create git tags or GitHub releases by hand.** CI (`release.yml`) tags and releases on merge to master.
- Never push to master. All changes go through a draft PR, CI, a review by Steven or Artem, and the merge queue.
- **End every PR description with an Assistant guide line** (the `pivotal-common:assistant-guide` skill). Axis
  users see this package's changes when axis bumps its pin, and the guides are updated in that bump PR, so here
  the line says what users will see or do differently, or "no user-facing change".

## GitHub Restrictions

**CRITICAL:** Only interact with repositories owned by `pivotal-energy-solutions`.
- When using `gh` CLI commands (issue, pr, etc.), ALWAYS explicitly specify `--repo pivotal-energy-solutions/<repo-name>`
- NEVER create issues or PRs in upstream repos (NREL, NatLabRockies, etc.)
- If a repo is a fork, the `gh` CLI may default to upstream - always use explicit `--repo` flag

```bash
# CORRECT - explicit repo
gh pr create --repo pivotal-energy-solutions/django-input-collection --draft --title "..."

# WRONG - may go to upstream
gh pr create --title "..."
```
