# Agora Core 0.8 migration

## Status

- Clarification status: human-approved; authoritative lifecycle state is the Agora work record
- Swarm: `studio-core-0-8-migration`
- Work item: `core-0-8-migration`
- Method: `spec-driven` 1.0.0
- Draft author: `project:specification-agent`
- Clarification owner: `project:owner`
- Target Studio release: 0.5.0
- Target Core contract: `agora-framework>=0.8,<0.9`

The material scope questions have been answered by the human spec owner. A registered consistency
review maps every criterion to an explicit, testable part of this specification. This is
specification evidence only: planning and implementation have not started, and shipped behavior
still requires separate verification evidence.

## Objective

Migrate Agora Studio from the Agora Core 0.7 application-service contracts to Core 0.8 while
preserving Studio as a local-first HTTP and browser adapter. Core remains the sole owner of durable
state, lifecycle policy, authority, canonical authorization material, evidence rules, transactions,
and recovery semantics.

## Baseline

The repository currently identifies Studio as version 0.4.0 and requires
`agora-framework>=0.7,<0.8`. `CoreReadGateway` and `CoreCommandGateway` validate the Core 0.7 schema
set, including work control v2, gate option v2, approve-gate command v3, prepared decision v2, and
gate decision projection v2. The bundled frontend exposes reads plus one governed mutation: prepare
and confirm a gate decision.

CI builds against Core tag `v0.7.0`, checks the published `>=0.7,<0.8` range, exercises real Core
integration, runs Chromium scenarios, builds both wheels, and smoke-tests the installed pair.

The existing Agora project is already adopted with durable protocol version 0.3.0 and the
`spec-driven` Method Pack. Core 0.8 reports no durable protocol upgrade for this project. Protocol,
Core package, and Studio package versions remain independent.

At cycle start the Git working tree was clean on `feat/studio-0.4-core-0.7-e2e`. Core 0.8 can read
the project, but `agora validate` reports pre-existing non-canonical context paths in 40 historical
sessions. This migration must not silently rewrite those historical records or claim that baseline
validation is clean.

## Users and outcome

The primary user is a developer operating Agora projects through the local Studio interface. After
the migration, the user can inspect Core 0.8 projects and complete the existing gate-review flow
with the additional freshness, expiry, actor-key, and evidence-content guarantees provided by Core
0.8. When Core reports an operational failure, the interface gives a safe, specific recovery path
without guessing from message text.

## Scope

### Included

- Select and read projects through `AgoraReadService` from one supported Core minor:
  `>=0.8,<0.9`.
- Consume and validate the exact Core 0.8 DTO schemas used by current Studio views.
- Migrate the existing gate preparation and confirmation flow to Core 0.8 contracts.
- Present content-addressed evidence state and Core-owned blockers without recreating policy.
- Handle Core application error v2 as structured operational state.
- Update the bundled frontend, tests, documentation, compatibility matrix, CI, build, and wheel
  verification required by the migrated contract.
- Record explicit verification evidence before any acceptance criterion is marked satisfied.

### Excluded

- Reimplementing any Agora Core rule, parser, persistence behavior, digest calculation, or recovery
  transaction in Studio.
- Invoking Agora CLI or another subprocess from production Studio code.
- Reading or editing `.agora/` records directly from Studio.
- Supporting Core 0.7 and 0.8 simultaneously through schema fallbacks or duck typing.
- Migrating a selected project's durable protocol merely because the installed Core package changes.
- Adding authentication, a database, telemetry, remote access, multi-user behavior, or a frontend
  framework.
- Resolving the pre-existing historical session validation errors as an incidental migration change.
- Any commit, push, pull request, release, or deployment in this work item unless separately
  authorized after implementation and verification.

The new Core 0.8 budget-amendment command does not receive Studio controls in this migration. A
separate spec-driven work item may define that product capability later.

## Contract requirements

### Compatibility and service boundary

1. Studio MUST require `agora-framework>=0.8,<0.9` and reject every other Core minor with an explicit
   compatibility response before exposing a mutation for the selected project.
2. All project reads MUST enter Core through `AgoraReadService`; all governed writes MUST enter Core
   through `AgoraCommandService`.
3. Studio MUST NOT import private Core internals as a substitute for the public application package.
4. Studio MUST validate every consumed top-level and nested schema exactly. An unknown schema or
   missing required field MUST fail closed as a compatibility error.
5. Studio MUST keep Core version, Studio version, and selected-project protocol version separate in
   code, UI, tests, and documentation.

### Core 0.8 reads

The migrated gateway MUST accept the following changed schemas and preserve their new fields:

| Projection | Required Core 0.8 schema | New material used by Studio |
| --- | --- | --- |
| Project overview | `agora/application/project-overview/v2` | `gate_decision_ttl_seconds` |
| Method summary | `agora/application/method-summary/v2` | gate decision TTL |
| Gate summary | `agora/application/gate-summary/v2` | content-addressed evidence requirement |
| Work detail | `agora/application/work-item-detail/v3` | nested artifact/evidence v3 |
| Artifact summary | `agora/application/artifact-summary/v3` | `content_sha256` |
| Evidence summary | `agora/application/evidence-summary/v3` | `artifact_content_sha256` |
| Lifecycle | `agora/application/lifecycle-projection/v3` | gate summary v2 |
| Traceability | `agora/application/traceability-summary/v2` | artifact/evidence v3 |
| Gate option | `agora/application/gate-decision-option-summary/v3` | digest map and content-addressed flag |
| Gate options | `agora/application/gate-decision-options-projection/v3` | gate option v3 |
| Work control | `agora/application/work-control-projection/v3` | complete Core 0.8 aggregate |

Unchanged nested contracts remain exact rather than being accepted generically. The work control
snapshot token is an opaque projection identity, not an authorization token or database version.

If Core returns `durable-state.concurrent-edit` with `retryable: true`, Studio MAY perform a short,
bounded read retry. It MUST never loop indefinitely, broaden that behavior to mutations, or hide a
final failure. The concrete retry count and delay must be fixed in the implementation plan and
covered with deterministic tests.

### Gate preparation and confirmation

1. Preparation MUST send an unsigned, digest-free
   `agora/application/approve-gate-command/v4` to
   `AgoraCommandService.prepare_gate_decision()`.
2. Studio MUST validate and present
   `agora/application/prepared-gate-decision/v3`, including Core's canonical reason, exact selected
   evidence references, exact `evidence_content_sha256` map, actor fingerprint, preparation time,
   expiry, authorization payload, and authorization digest.
3. Confirmation MUST reuse, unchanged, the returned reason, evidence references, digest map, actor
   fingerprint, precondition digest, `prepared_at`, and `expires_at`. Only the externally produced
   detached signature may be added when authentication is required.
4. Studio MUST NOT calculate or reinterpret the authorization payload, precondition digest, evidence
   content digest, actor fingerprint, freshness, or expiration.
5. The exact expiration instant counts as expired. Expired material requires a new preparation.
6. The evidence digest map MUST contain exactly the selected references. A selected reference with
   unknown content identity remains present with a null value; unselected eligible references MUST
   NOT be added.
7. Success requires the durable
   `agora/application/gate-decision-projection/v3`. The UI MUST NOT update optimistically and MUST
   reread the complete work control projection after durability.
8. Studio MUST never retry a gate mutation automatically after a stale, expired, signature, commit,
   rollback, or indeterminate result.

### Evidence integrity

1. The UI MUST distinguish an artifact URI from its optional content SHA-256 and render both as
   untrusted text.
2. Evidence MUST retain the Core-provided URI-to-content-digest map, including null values.
3. A Core option requiring content-addressed evidence MUST remain disabled while Core reports
   `gate.evidence-content-digest-missing` or any other blocker.
4. Studio MUST NOT download remote evidence, hash a URI as a content substitute, suppress a blocker,
   or infer that evidence is sufficient.

### Operational errors and recovery

Studio MUST consume `agora/application/error/v2` by stable `code`, `category`, `retryable`,
`recovery_hint`, and safe `details`. Messages and details are untrusted display text, never control
flow or HTML.

| Core code | Required behavior |
| --- | --- |
| `command.preparation-expired` | Keep the reviewed form, invalidate prepared material, and require preparation again. |
| `command.governed-material-stale` | Require refresh, review, and preparation again; show safe stale-reason details when present. |
| `durable-state.concurrent-edit` | Offer a bounded read retry only when Core marks it retryable. |
| `gate.evidence-missing` | Render Core's typed blockers; do not calculate evidence sufficiency. |
| `command.signature-invalid` | Invalidate the signature and require signing a newly prepared payload. |
| `transaction.commit-failed` | Report that no decision committed, preserve user-entered review text, and allow only an explicit reviewed retry. |
| `transaction.rollback-failed` | Require operator review before another mutation; do not auto-retry. |
| `transaction.indeterminate` | Disable mutation controls for the selected project and display Core's recovery hint to reconcile Git and run `agora validate`. |

The implementation plan MUST define the explicit user action that re-enables mutations after an
indeterminate result; successful validation MUST NOT be inferred by Studio invoking the CLI.

## HTTP and browser behavior

- Existing loopback, Host, Origin, CSRF, JSON-content-type, body-size, no-store, CSP, frame, and
  referrer protections remain mandatory.
- Prepared and confirmed HTTP envelopes MUST expose enough Core material for exact review and
  confirmation without exposing private keys or persisting request-scoped signatures.
- The browser MUST invalidate prepared state whenever the selected project, work, option, reason,
  selected evidence, project generation, or Core freshness material changes.
- Digest maps, expiry, structured error recovery, and mutation-disabled state MUST be keyboard
  accessible, responsive, safe under reduced motion, and represented in loading, empty, success,
  stale, and failure states.
- Durable strings and error details MUST be inserted as text, never interpreted as HTML.

The existing `/api/v1` route set remains. Affected response envelopes advance to their migrated
schemas together with the bundled frontend, without a Core 0.7 compatibility shim.

## Verification contract

No criterion is satisfied merely because code exists or a test command exits successfully. Evidence
must identify the contract exercised and the result.

Required verification includes:

- strict unit tests for every changed schema and required field, plus rejection of 0.7 and unknown
  schemas;
- command gateway tests proving byte-preserving use of Core's prepared authorization material,
  exact selected digest maps, null digest retention, timestamps, expiry, and actor fingerprint;
- real Core 0.8 prepare/confirm integration for unsigned and Ed25519 actors using the portable Core
  0.8 golden fixture or an equivalent real flow;
- deterministic stale-state, governed-material, expired-preparation, external-edit, missing-digest,
  invalid-signature, commit-failure, rollback-failure, and indeterminate-transaction paths;
- HTTP security and concurrency regression tests proving there is no optimistic mutation or
  automatic mutation retry;
- frontend model and Chromium coverage for review, expiration, recovery, keyboard, focus, mobile,
  reduced-motion, response ordering, and safe durable-text rendering;
- a boundary scan proving production code has no CLI, subprocess, direct durable-record, Git, parser,
  or lifecycle-rule fallback;
- formatting, lint, the full unit/integration suite, package build, clean-wheel installation,
  `agora-studio --version`, and package-resource smoke tests;
- CI against immutable minimum Core `v0.8.0` and the latest published `>=0.8,<0.9` wheel on the
  supported Python matrix.

The final verification record must distinguish local source integration, built-wheel integration,
published-range coverage, and any scenario that could not be run.

## Documentation requirements

README, architecture, compatibility matrix, install instructions, HTTP contract documentation, and
the new verification record MUST consistently describe Studio 0.5.0, the Core 0.8 range,
changed schemas, operational recovery behavior, and deliberate exclusions. Documentation MUST NOT
claim a published Studio or Core artifact without evidence that it exists.

## Human clarification decisions

On 2026-08-20, the human spec owner resolved the three material scope questions:

1. Ship the migration as Studio 0.5.0.
2. Defer budget-amendment UI to a separate work item.
3. Retain `/api/v1`, advance affected envelopes and the bundled frontend atomically, and provide no
   Core 0.7 compatibility shim.

The durable clarification evidence is
`repo://docs/evidence/core-0.8-spec-clarification.md`.

## Clarification exit conditions

The human spec owner has answered every open question and the registered consistency review covers
every criterion. Agora records criterion satisfaction here as acceptance of the clarified contract,
not as proof of implementation. The `drafting -> clarified` transition still requires an explicit
human request. After clarification, planning may begin; production-code and dependency changes stay
prohibited until the later `planned -> implementing` transition.
