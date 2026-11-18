---
name: development-workflow
description: Use when planning, implementing, fixing, refactoring, integrating software, or editing development documentation in the owner's projects. Excludes read-only explanations and unrelated writing.
license: Apache-2.0
---

# Development Workflow

Explicit user instructions and existing authorization take precedence. Discover the project's stack, ownership, branch flow, documentation and commands. Do not impose a new layout or migrate its conventions. This plugin does not authorize publication, purchases, pushing, merging or deployment beyond the task.

Read [delivery policy](references/delivery-policy.md) before implementation setup, dependency adoption or integration. Reuse an approved specification and its approved plan; obtain only missing approvals before dependent implementation. Editorial/mechanical changes with no requirement or runtime behavior change need no new specification or plan. Keep shared documents authoritative and linked.

Use isolated feature workspaces, relevant baseline checks and the smallest sufficient implementation. Prefer standard libraries, native APIs and existing code. Follow the verification skill for TDD, affected suites and required review. Failed required gates remain blockers.

## Economy and delegation

Default to one agent. Delegate separable work or material-risk review when the benefit exceeds coordination cost; required independent review remains required. Parallel writers need separate worktrees and clear ownership. Shared contracts and dependent work stay sequential. The coordinator verifies each result and the integrated change.

Search before reading; inspect affected sections and connected dependencies. Reuse unchanged context and approvals. Load only relevant references. Give delegates the goal, acceptance criteria, relevant files, constraints and settled decisions; request results, evidence and unresolved issues. Keep checkpoints short.

Summarize successful commands; show relevant failure diagnostics with exit status and access to complete required logs. Repeat work only for changed inputs, missing evidence or a concrete uncertainty. Bound retries. Budget pressure never permits weaker tests, hidden failures or unsupported success claims.

Before running builds/tests, invoke resource-lifecycle and use its runner. Cleanup is part of completing the task, without reminders. Before completion inspect changes, checks, delivery state and cleanup receipts; report artifact locations and blockers. Distinguish implemented, integrated and deployed states.
