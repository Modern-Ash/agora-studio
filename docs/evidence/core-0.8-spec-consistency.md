---
schema: "agora/consistency-report/v1"
swarm: "studio-core-0-8-migration"
work: "core-0-8-migration"
result: "success"
input-sha256: "781f86e568438eb0cb66d92178957958c0f318f3af8126b0d0e7fbcb295689af"
actor: "project:owner"
created-at: "2026-08-20T23:53:49Z"
---

# Core 0.8 migration specification consistency review

## Result

- Result: success
- Date: 2026-08-20
- Swarm: `studio-core-0-8-migration`
- Work item: `core-0-8-migration`
- Reviewed specification: `repo://docs/specs/core-0.8-studio-migration.md`
- Human clarification: `repo://docs/evidence/core-0.8-spec-clarification.md`
- Review scope: readiness of the specification for `drafting -> clarified`

This review establishes that each acceptance criterion has an explicit, internally consistent, and
testable contract in the specification. It is not implementation or release evidence. Product
behavior remains unimplemented and must be proven separately before completion.

## Criterion coverage

| Criterion | Specification coverage | Review result |
| --- | --- | --- |
| `scope` | Objective, Included, Excluded, Human clarification decisions | The target is Studio 0.5.0; budget controls are deferred; `/api/v1` remains without a Core 0.7 shim. |
| `compatibility` | Compatibility and service boundary | The supported range is exactly `agora-framework>=0.8,<0.9`; unsupported minors fail closed; Core, Studio, and durable protocol versions remain separate. |
| `read-contracts` | Core 0.8 reads | Every changed top-level schema is enumerated, new fields are named, unchanged nested schemas remain exact, and concurrent-read behavior is bounded. |
| `gate-flow` | Gate preparation and confirmation | Command v4 and prepared/decision v3 are explicit; all freshness, expiry, actor, evidence-digest, signing, durability, and no-retry constraints are stated. |
| `operational-errors` | Operational errors and recovery | Error v2 fields and the required behavior for expired, stale, concurrent-edit, evidence, signature, commit, rollback, and indeterminate codes are explicit. |
| `evidence-integrity` | Evidence integrity | URI and content identity are distinct; null digests are preserved; remote download, URI hashing, blocker suppression, and policy inference are prohibited. |
| `boundaries` | Scope; Compatibility and service boundary; HTTP and browser behavior | Reads and commands remain behind Core application services; CLI, subprocess, direct `.agora`, Git, parser, database, remote, auth, and multi-user fallbacks are excluded. |
| `verification` | Verification contract | Unit, real-Core integration, security, frontend, Chromium, boundary, build, wheel, version-range, failure-path, and evidence expectations are measurable. |
| `documentation` | Documentation requirements | README, architecture, compatibility, install, HTTP, recovery, and verification records must consistently describe Studio 0.5.0 and Core 0.8 without publication claims lacking evidence. |

## Source consistency

The specification agrees with the primary Core 0.8 migration guide and the public application DTO,
command, read-service, command-service, and operational-error contracts inspected in the sibling
Agora Core 0.8 checkout. It does not copy Core lifecycle calculations into Studio.

The current Studio baseline also supports the stated migration boundary: Studio 0.4.0 pins Core
`>=0.7,<0.8`, validates the Core 0.7 schemas, exposes the existing prepare/confirm gate mutation,
and exercises Core 0.7 in CI. No contradiction was found between that baseline and the proposed
Core 0.8 target.

## Residual obligations

- No production code or dependency has changed.
- No implementation-plan artifact exists yet.
- No technical acceptance criterion has implementation evidence yet.
- The completion gate must not rely on this specification-consistency evidence as proof of shipped
  behavior; verification evidence must be produced during the later `verifying` state.
- The 40 historical `session.context-invalid` validation findings remain a disclosed baseline and
  are outside this migration.

With the human clarification decisions recorded and the specification registered, the specification
is consistent and testable enough for the human spec owner to authorize `drafting -> clarified`.
