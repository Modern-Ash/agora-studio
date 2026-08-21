# Agora method trace — Studio Core 0.8 migration

## Identity

- Date opened: 2026-08-20
- Core executable: Agora Core 0.8.0 from the reviewed sibling checkout
- Project: `agora-studio`
- Method Pack: `spec-driven` 1.0.0
- Swarm: `studio-core-0-8-migration`
- Work item: `core-0-8-migration`
- Current state: `clarified`
- Current spec owner: `project:owner`
- Developer: `project:agent`

## Lifecycle

| Step | Transition | Authorized role | Gate | Required outcome |
| --- | --- | --- | --- | --- |
| 1 | create in `drafting` | spec-owner | work creation rules | Work item and acceptance contract exist. |
| 2 | `drafting -> clarified` | spec-owner | `spec-clarified` | All criteria are explicitly satisfied and the required `spec` artifact is registered. No successful evidence or separate approval is required by the pack, although this project requires evidence before criterion satisfaction. |
| 3 | `clarified -> planned` | developer | none | Developer creates a plan against the clarified specification; project policy should register an `implementation-plan` artifact. |
| 4 | `planned -> implementing` | developer | none | Implementation begins only after the plan is reviewable. |
| 5 | `implementing -> verifying` | developer | none | The increment is submitted with verification artifacts and evidence. |
| 6a | `verifying -> implementing` | developer | none | Failed verification returns the work for rework. |
| 6b | `verifying -> completed` | spec-owner | `completion` | All criteria and required artifacts are satisfied, at least one successful evidence record exists, and the spec owner has approved. |

Agora does not permit a direct path that skips one of these transitions.

## Governed actions completed

1. Inspected Git branch, working tree, remote, `AGENTS.md`, existing `.agora`, project
   configuration, installed packs, actors, historical swarms, and current Studio architecture.
2. Ran the requested global `agora --version`; the global 0.3.2 CLI did not support that flag.
3. Selected the reviewed sibling Agora Core 0.8.0 executable without adding it to Studio runtime
   dependencies.
4. Reused the existing `.agora` project and ran Core 0.8 adoption preflight, status, upgrade preview,
   and validation. No reinitialization or protocol upgrade was applied.
5. Created swarm `studio-core-0-8-migration` with Method Pack `spec-driven` and no branch change.
6. Assigned `project:specification-agent` as initial spec owner and `project:agent` as developer.
7. Surveyed Studio 0.4/Core 0.7 boundaries, schemas, tests, CI, packaging, and the primary Core 0.8
   migration guide and public application contracts.
8. Created work item `core-0-8-migration` in `drafting` with nine acceptance criteria and required
   artifact kind `spec`.
9. Drafted and registered `repo://docs/specs/core-0.8-studio-migration.md`.
10. Handed the `spec-owner` role to human actor `project:owner` at the clarification boundary.
11. Recorded the human decisions for Studio 0.5.0, deferred budget controls, and `/api/v1` without a
    Core 0.7 shim in `repo://docs/evidence/core-0.8-spec-clarification.md`.
12. Registered that record as successful `human-clarification` evidence and satisfied only the
    `scope` criterion it directly proves.
13. Reviewed the complete specification against all nine criteria and registered
    `repo://docs/evidence/core-0.8-spec-consistency.md` as successful
    `specification-consistency` evidence. The report explicitly distinguishes specification
    readiness from implementation proof.
14. The human spec owner accepted all nine criteria as the clarified, testable contract.
15. Confirmed that `agora next` reported no `spec-clarified` blockers and transitioned the work from
    `drafting` to `clarified` as `project:owner`.

## Current state

The work is `clarified`. The required `spec` artifact exists, both `human-clarification` and
`specification-consistency` evidence are successful, and all nine criteria are accepted as the
clarified contract.

The `spec-clarified` gate passed with no blockers. Agora now assigns the next action to the
`developer` role and permits only the next transition:

- `clarified -> planned`

No implementation plan has been registered and no transition to `planned` has been requested.
Production code and dependencies remain unchanged.

## Validation baseline

Core 0.8 reads the newly created swarm, work, artifacts, evidence, criterion status, and handoff.
Full project validation remains false because 40 historical session records have the pre-existing
`session.context-invalid` issue. This cycle did not rewrite or waive them.

## Audit commands

Run these commands from the Studio repository with the Core 0.8 executable:

```bash
../agora/.venv/bin/agora status
../agora/.venv/bin/agora swarm show --swarm studio-core-0-8-migration
../agora/.venv/bin/agora swarm handoffs --swarm studio-core-0-8-migration
../agora/.venv/bin/agora work show --swarm studio-core-0-8-migration --work core-0-8-migration
../agora/.venv/bin/agora work traceability --swarm studio-core-0-8-migration --work core-0-8-migration
../agora/.venv/bin/agora work status-changes --swarm studio-core-0-8-migration --work core-0-8-migration
../agora/.venv/bin/agora next
../agora/.venv/bin/agora inbox
../agora/.venv/bin/agora validate
```

These are process tools for developers and operators. They are not Studio runtime dependencies and
must never be invoked by the web application.
