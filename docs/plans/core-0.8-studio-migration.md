# Core 0.8 Studio Migration Implementation Plan

## Governed scope

- Work: `studio-core-0-8-migration/core-0-8-migration`
- Role: `developer` (`project:agent`)
- Clarified specification: `repo://docs/specs/core-0.8-studio-migration.md`
- Baseline: Studio 0.4.0 on Core `>=0.7,<0.8`, single prepare/confirm gate flow at `/api/v1`, current `agora_studio/core.py` and `commands.py` validating v2/v1 schemas
- Target: Studio 0.5.0 on `agora-framework>=0.8,<0.9`, no 0.7 shim, no durable protocol migration

This plan implements the clarified contract without altering it. No production code changes before `planned -> implementing`.

## Architecture

Studio remains a local-first adapter. All reads through `AgoraReadService`, all mutations through `AgoraCommandService`. No CLI, subprocess, direct `.agora` reads, or lifecycle recalculation. View changes are presentation of Core-owned material only.

```
Browser -> Studio HTTP (127.0.0.1, CSRF, loopback) -> ProjectStore/CoreReadGateway -> AgoraReadService
Browser -> Studio HTTP POST prepare/confirm -> CoreCommandGateway -> AgoraCommandService.{prepare_gate_decision,approve_gate}
Core DTOs validated exactly; unknown schema or missing field fails closed as 426.
```

## Implementation sequence

### 1. Compatibility and packaging

Files: `agora_studio/__init__.py`, `pyproject.toml`, `README.md`, `docs/architecture.md`

- Bump `__version__` 0.4.0 -> 0.5.0, `dependencies` to `agora-framework>=0.8,<0.9`.
- Update `MINIMUM_CORE_VERSION=(0,8,0)` `MAXIMUM_CORE_VERSION=(0,9,0)` and all compatibility messages to mention `>=0.8,<0.9`.
- Reject unsupported minors before mutation with `core.version-incompatible` (426) via existing `_ensure_compatible` path; keep Core/Studio/protocol versions separate in UI and docs.
- Verify no private Core internals imported.

### 2. Read contracts

Files: `agora_studio/core.py`, `agora_studio/lifecycle.py`, `agora_studio/artifacts.py`

Update `SCHEMAS` to exact Core 0.8 values:

| key | 0.7 | 0.8 |
|---|---|---|
| overview | v1 | v2 (adds `gate_decision_ttl_seconds`) |
| method | v1 | v2 (adds TTL) |
| gate | v1 | v2 (`require_content_addressed_evidence`) |
| work_detail | v2 | v3 (nested artifact/evidence v3) |
| artifact | v2 | v3 (`content_sha256`) |
| evidence | v2 | v3 (`artifact_content_sha256`) |
| lifecycle | v2 | v3 (gate-summary v2) |
| traceability | v1 | v2 (artifact/evidence v3) |
| gate_option | v2 | v3 (digest map, content-addressed flag) |
| gate_options | v2 | v3 (option v3) |
| work_control | v2 | v3 (full aggregate) |

- Validate every top-level and nested schema exactly; `_payload`/`_nested`/`_nested_many` stay strict, unknown schema fails as `core.schema-incompatible`.
- Preserve new fields: `gate_decision_ttl_seconds`, `content_sha256`, `artifact_content_sha256`, `evidence_content_sha256`, `content_addressed_evidence_required`.
- Work-control: snapshot token stays opaque projection identity; re-validate cross-projection consistency (states, operational_status, artifacts/evidence/traceability alignment, gate options identity).
- Bounded concurrent-edit retry: on `durable-state.concurrent-edit` with `retryable:true`, allow at most 2 read retries with 50ms delay (config constant), reads only, never mutations, never unbounded loop; deterministic tests cover exhaustion. Concrete values fixed here per spec requirement.
- No fallback to 0.7 schemas.

### 3. Gate preparation and confirmation

Files: `agora_studio/commands.py`, `agora_studio/server.py`

Command/DTO constants:

- `APPROVE_GATE_SCHEMA` v3 -> v4, `AUTHORIZATION_SCHEMA` v3 -> v4 (approve-gate-authorization/v4), `PREPARED_GATE_SCHEMA` v2 -> v3, `GATE_PROJECTION_SCHEMA` v2 -> v3.
- ApproveGateCommand now carries `evidence_content_sha256: Mapping[str,str|None]`, `actor_fingerprint`, `prepared_at`, `expires_at`; preparation sends unsigned, digest-free command (`authentication=None`, `precondition_digest=None`, `evidence_content_sha256={}`, `prepared_at=None`, `expires_at=None`).
- Preparation validates returned `PreparedGateDecision/v3`: command_schema, authorization_schema (v4), precondition_digest (SHA-256), authorization_digest matches ASCII canonical payload ending with `\n`, payload equals canonical command plus authorization_schema, plus new fields `evidence_content_sha256` (exactly selected refs, null for missing content), `actor_fingerprint`, `prepared_at`, `expires_at`, `freshness=governed-material/v1`, `authentication_*` metadata.
- Confirmation reuses unchanged `reason`, `evidence_references`, `evidence_content_sha256`, `actor_fingerprint`, `precondition_digest`, `prepared_at`, `expires_at`; only detached `authentication.signature` may be added. Validate confirmation rejects missing precondition_digest, rejects modified digests. Expiry is inclusive: `now >= expires_at` treated expired by Core, Studio requires re-preparation.
- Success must be `GateDecisionProjection/v3`; server must not update optimistically and must require reread of full work-control projection after durability (existing work-detail route already does; keep behavior).
- Never auto-retry gate mutations on stale/expired/signature/commit/rollback/indeterminate; surface typed error.
- Keep HTTP envelopes at `/api/v1` with bumped inner schemas: `prepared-gate-decision/v3` and `gate-decision/v3`.

### 4. Evidence integrity and UI

Files: `agora_studio/static/*`, `agora_studio/server.py`

- Distinguish artifact URI vs `content_sha256`; render both as escaped text, never as HTML.
- Preserve `evidence_content_sha256` map with nulls; do not synthesize digests or download evidence.
- When option `content_addressed_evidence_required` and Core reports `gate.evidence-content-digest-missing` (or any blocker), keep option disabled.
- Blockers rendered from `gate_blocker-summary/v1` verbatim.

### 5. Operational errors

Files: `agora_studio/core.py`, `agora_studio/commands.py`, `agora_studio/server.py`, `agora_studio/static/*`

Consume `agora/application/error/v2` via `AgoraApplicationError.to_dict()` already mapped; enforce structured fields `code, category, retryable, recovery_hint, details` as source of control flow. Never branch on `message`. Details/messages are untrusted text.

| code | behavior |
|---|---|
| `command.preparation-expired` | invalidate prepared material, keep form, require re-prepare |
| `command.governed-material-stale` | require refresh/review/re-prepare; show details safely |
| `durable-state.concurrent-edit` retryable | bounded read retry (step 2) |
| `gate.evidence-missing` | render typed blockers |
| `command.signature-invalid` | invalidate signature, require new prepare |
| `transaction.commit-failed` | report not committed, preserve review text, allow explicit retry |
| `transaction.rollback-failed` | require operator review, no auto-retry |
| `transaction.indeterminate` | disable mutations for selected project, show recovery_hint (`reconcile Git, agora validate`); re-enable only via explicit user action: selecting a different project then re-selecting, or explicit "Retry after operator review" button; successful validation must not be inferred by Studio calling CLI |

Map to HTTP: keep existing `_COMMAND_STATUS` plus add `durable-state.concurrent-edit` 409, `command.preparation-expired` 410, `transaction.*` 503/409 as per Core category.

### 6. HTTP and browser

Files: `agora_studio/server.py`, `agora_studio/static/*`

- Retain loopback, Host/Origin, CSRF, JSON content-type, body-size, no-store, CSP, frame/referrer protections.
- Prepared/confirmed envelopes expose Core material for review without exposing private keys or persisting signatures.
- Browser invalidates prepared state on change of project/work/option/reason/evidence selection/generation/freshness.
- Digest maps, expiry, recovery, mutation-disabled states are keyboard accessible, responsive, reduced-motion safe, with explicit loading/empty/success/stale/failure states. Durable strings inserted via `textContent`.

### 7. CI, build, verification contract

Files: `.github/workflows/*`, `tests/*`, `e2e/*`, `docs/evidence/*`

- CI matrix: minimum `v0.8.0` tag and latest `>=0.8,<0.9` wheel, Python 3.11-3.13, runs `ruff format --check`, `ruff check`, `python -m unittest discover -s tests -v`, `python -m build`, clean-wheel install + `agora-studio --version` + package-resource smoke, Chromium scenarios.
- Tests required (deterministic, no network):
  - strict schema unit for every changed schema and required field plus rejection of 0.7/unknown
  - gateway tests for byte-preserving prepared material, exact digest maps with null retention, timestamps, expiry inclusive, actor fingerprint
  - real Core 0.8 prepare/confirm integration unsigned + Ed25519 via sibling checkout golden fixture or equivalent real flow (requires `../agora/.venv`)
  - failure paths: stale, expired, external-edit, missing-digest, invalid-signature, commit/rollback/indeterminate
  - HTTP security/concurrency regressions: no optimistic mutation, no auto-retry
  - frontend model + Chromium for review/expiry/recovery/keyboard/focus/mobile/reduced-motion/ordering/safe rendering
  - boundary scan: no `subprocess`, no `agora` CLI, no `.agora` read, no Git/parser fallback in production code
  - build/wheel/version-range coverage

### 8. Documentation

Files: `README.md`, `docs/architecture.md`, `docs/specs/core-0.8-studio-migration.md` refs, HTTP contract docs, compatibility matrix

- Consistently describe Studio 0.5.0, Core 0.8 range, changed schemas, recovery, exclusions; no unevidenced publication claims.

## Acceptance traceability

| Criterion | Steps | Verification |
|---|---|---|
| compatibility | 1,2,5 | version range unit, 426 rejection, no private import scan |
| read-contracts | 2,7 | strict DTO tests, work-control cross-checks, bounded retry |
| gate-flow | 3,7 | gateway byte-preserving + real Core integration + expiry/null-map |
| operational-errors | 5,7 | typed error mapping, indeterminate disable, no message parsing |
| evidence-integrity | 4,7 | URI vs digest distinction, null retention, no download |
| boundaries | 1-3,7 | boundary scan, service-boundary import checks |
| verification | 7 | full matrix above |
| documentation | 8,7 | docs consistency check |

## Risks and controls

- Digest reuse treated as authorization material: Studio never calculates SHA-256 over authorization payload or evidence; Core-owned.
- Evidence downgrade: null digests preserved, unselected refs not added, blocked options stay disabled.
- Concurrent edit: bounded short retry reads only; no mutation retry.
- Indeterminate transaction: mutation disable is project-scoped and requires explicit user action, not CLI polling.
- 40 historical `session.context-invalid` records remain untouched.

## Delivery checkpoints

1. Packaging/compat bump passes validation.
2. Read + command gateway unit passes including 0.7 rejection.
3. Real Core integration passes on 0.8 fixture.
4. HTTP/frontend/Chromium/boundary suite passes.
5. `docs/evidence/core-0.8-studio-migration-verification.md` registered before `verifying -> completed`.
