# Delivery Policy

## Context and agreement

Discover ownership boundaries, authoritative documentation, stack, verification commands, branch roles, supported platforms, deployment targets, and resource tooling from the project. Ask only about consequential gaps inspection cannot resolve. Follow explicitly adopted conventions; use the defaults here where they are silent. Do not migrate a project to fit this policy. A parent containing independent repositories does not require Git initialization or submodules.

A specification defines behavior, constraints, and acceptance criteria. Its implementation plan links it and identifies affected components, tasks, tests, dependencies, and delivery checks. Keep both proportionate; reuse applicable approved material. A detailed approved task brief can serve as the specification. Record approval in the conversation or existing project mechanism.

An initial feature request does not approve an unseen specification or plan. Obtain missing approvals in that order before dependent implementation. Existing approval covers its agreed scope; material changes require updating the affected agreement. An unavailable required specification blocks dependent work, not unrelated progress. Purely editorial and mechanical changes use clear task scope and relevant validation as defined in the entrypoint.

## Ownership and identifiers

Keep shared requirements, architecture, contracts, and plans in the authoritative documentation location; implementation-only details belong with the component. Link shared documents instead of copying them. Cross-repository plans identify every affected repository, use a consistent feature identifier, and keep commits in each file's owning repository.

Absent an established naming convention, document IDs are descriptive lowercase hyphenated filename stems, unique across related repositories, without sequence numbers, UUIDs, timestamps, or date prefixes. Search before creating one; do not rename existing documents merely to enforce this default.

## Isolation and integration

Use a dedicated feature worktree for active implementation; detect and reuse an already isolated workspace, preferring native worktree support. Create it from the designated integration base with project branch conventions. Before editing, run available relevant baseline checks. Resolve baseline failures within scope, or obtain explicit approval to proceed with them recorded; do not silently expand the task to fix unrelated failures.

Follow the declared branch flow. If none exists, agree concrete names for a feature → integration → release-ready flow. Integration and release roles may share a branch in established trunk-based development. Do not commit feature implementation directly to shared integration or release branches. Required tests and review must pass before integration.

When delegation is justified under the entrypoint, preserve the approved plan's ownership boundaries. Shared-contract changes and dependent work remain sequential. Review each delegated result and its evidence, then verify the combined change. When delegation is unavailable, perform these responsibilities sequentially; if specifically required independent review is unavailable, report that gate as blocked.

## Minimal implementation and dependencies

Use established stack and patterns; prefer standard libraries, native APIs, and existing project code. Avoid speculative abstractions, extension points, scaffolding, and unrelated improvements.

Add a library, tool, or bundled asset only when it materially reduces code or implementation risk. Before adoption, verify the exact version's license and intended-use terms; record sources, obligations, and required notices in the plan. Unless the owner or project explicitly approves different terms, require compatibility with closed-source commercial use: no mandatory payment, royalty, usage fee, restriction on commercial use, or obligation to disclose proprietary source or project-specific modifications. Unknown or ambiguous terms block adoption.

Exceptions identify exact scope and obligations; a data exception does not cover application code or tooling automatically. Preserve required attribution. Hosted infrastructure costs belong to the infrastructure plan and spending authorization. Dependency selection does not authorize changing project licensing or repository visibility.
