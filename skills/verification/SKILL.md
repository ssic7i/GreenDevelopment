---
name: verification
description: Use when implementing testable behavior, choosing or running tests, reviewing verification evidence, or preparing software integration and release.
license: Apache-2.0
---

# Verification

Read [verification policy](references/verification.md) for test selection, evidence validity and promotion checks. For testable behavior, demonstrate a failing requirement test, implement the minimum to pass, then refactor. Record a repeatable alternative and its limitations when automation is unavailable. Editorial changes use relevant validation.

Run focused checks during development. Complete the affected suite and required review/project gates before integration. Select versions by changed behavior and platform boundaries; available device capacity is not a mandatory matrix. Retain minimum/latest UI and persistence coverage, actual upgrade tests for migration changes, and relevant intermediate platform boundaries.

Reuse passed evidence only while the relevant code, tests, helpers, configuration, dependencies and environments remain applicable. Diagnose a bounded reproduction after failure, then rerun failed and directly affected cases. A changed helper can invalidate evidence without changing production code. Never weaken assertions or hide failed/unverified cases.

Run resource-producing commands through the resource-lifecycle runner, group dependent steps in one run, and retain final artifacts/reports before cleanup. Resource limits change scheduling, not required coverage. Verify the integrated result and planned staging checks. Report unmet gates instead of declaring success.
