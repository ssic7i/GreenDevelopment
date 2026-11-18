# Verification

## Test-driven implementation

For testable behavior, demonstrate the intended failing test, write the least implementation needed to pass, then simplify while preserving passing behavior. Test observable requirements. When required behavior cannot be automated in the available environment, record a repeatable alternative and its limitations in the plan. Editorial and mechanical changes use relevant validation rather than artificial behavior tests.

## Coverage selected by risk

During development, run the smallest relevant check; before integration, complete the affected suite and required project gates. Record cases, platform versions, and reasons before expensive runs:

| Changed behavior | Required coverage |
| --- | --- |
| Pure logic | Relevant unit checks; native integration when behavior crosses that boundary. |
| UI | Affected flows and relevant layouts on minimum and latest supported versions. |
| Persistence | Minimum/latest coverage; an actual old-to-new upgrade retaining data when schemas or upgrade paths change. |
| Permissions, services, lifecycle, hardware, other platform APIs | The specific affected branches, including intermediate version boundaries. |

Available versions are capacity, not an automatic matrix. A full matrix requires identified cross-version risk or an explicit project gate. State the physical-device limitations of emulator/simulator evidence.

## Evidence and failures

Reuse passing results only while relevant production code, tests, helpers, configuration, dependencies, and environment identities remain applicable. A changed relevant helper invalidates its affected evidence even when production code is unchanged. Verify that integration preserves the tested result; integration alone does not invalidate every check.

After failure, stop the broad run, diagnose a bounded reproduction, fix the cause, and rerun failed and directly affected cases. Do not weaken assertions, hide failed or unverified cases, or repeatedly restart a full matrix without a reason. Resource limits change scheduling, not required coverage. If a required check cannot run, report it as unverified and block its associated gate.

## Build and promotion

Use identifiable source revisions and the authoritative build definition. For containers, use the same build contract locally, in staging, and in production. Supply environment configuration at runtime; keep secrets out of source and distributable artifacts. Tests use isolated data and services, never production data or services.

Verify the integrated result before release-ready promotion. Deployed services require planned staging smoke and integration checks. Required build or check failures block the associated deployment or promotion. Store distribution and infrastructure provisioning follow their own approved project procedures and task authorization.
