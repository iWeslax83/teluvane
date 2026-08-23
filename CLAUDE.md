# CLAUDE.md

Guidance for Claude Code when working in this repo (`teluvane`).

## Multi-agent coordination

This project is worked on by multiple Claude Code agents in parallel (separate sessions/terminals on
the same clone or on separate clones of the same repo). Before starting any task, every agent MUST:

1. **Check git state first** — run `git log --oneline -20`, `git status`, and `git diff` to see what
   has already been committed or is in progress (including changes from another agent's session).
2. **Check planned work** — read `docs/superpowers/specs/` and `docs/superpowers/plans/` for existing
   specs and plans. Plan files use `- [ ]` / `- [x]` checkbox syntax to track task status; read the
   relevant plan fully before touching files it covers, to see what's already done, in progress, or
   still open.
3. **Check for unfinished work** — look for uncommitted changes (`git status`, `git diff`), open
   branches (`git branch -a`), and any half-finished tasks in the plans above, before starting new
   work or assuming a clean slate.
4. **Don't duplicate or collide** — if a plan task or file is already marked done or is mid-edit by
   another agent (uncommitted local changes, or a very recent commit), coordinate instead of
   re-doing or overwriting it: pick a different task, or ask the user.

Only after this check should an agent start implementing, and it should update the relevant plan's
checkboxes (or leave a clear note) as it finishes tasks, so the next agent's check-in stays accurate.
