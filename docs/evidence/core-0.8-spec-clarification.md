# Core 0.8 migration specification clarification

## Record

- Date: 2026-08-20
- Swarm: `studio-core-0-8-migration`
- Work item: `core-0-8-migration`
- Method state: `drafting`
- Human spec owner: `project:owner`
- Specification: `repo://docs/specs/core-0.8-studio-migration.md`

## Human decisions

The human spec owner reviewed the three open questions and selected the proposed option for each:

1. The migration targets Agora Studio 0.5.0.
2. Core 0.8 budget-amendment controls are deferred to a separate spec-driven work item.
3. Studio retains `/api/v1`, advances affected response envelopes with the bundled frontend, and
   does not provide a Core 0.7 compatibility shim.

## Evidence boundary

This record is evidence only for resolution of the `scope` acceptance criterion. It does not prove
that Core 0.8 compatibility, DTO handling, gate behavior, operational recovery, evidence integrity,
security boundaries, automated verification, or release documentation have been implemented.

No production code or dependency was changed, and no transition to `clarified` was requested while
recording these decisions.
