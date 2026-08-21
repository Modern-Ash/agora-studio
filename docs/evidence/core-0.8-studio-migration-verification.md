# Core 0.8 Studio Migration Verification

## Record

- Date: 2026-08-20
- Swarm: `studio-core-0-8-migration`
- Work item: `core-0-8-migration`
- Method state: `verifying`
- Developer: `project:agent`
- Specification: `repo://docs/specs/core-0.8-studio-migration.md`
- Implementation plan: `repo://docs/plans/core-0.8-studio-migration.md`

## Verification Scope

All nine acceptance criteria verified against Studio 0.5.0 / Core 0.8.0 integration:

| Criterion | Verification method | Result |
|---|---|---|
| `compatibility` | Unit test `test_rejects_incompatible_core_and_schema` + `test_version_and_core_dependency_are_explicit` | pass |
| `read-contracts` | Unit test `test_maps_public_dtos_and_exact_activity_filters` + `test_rejects_malformed_nested_control_contracts` + real Core integration | pass |
| `gate-flow` | Unit tests `test_prepares_and_validates_the_exact_core_contract`, `test_preserves_intent_text_and_accepts_core_canonical_values`, `test_validates_the_complete_gate_decision_projection`, `test_http_shape_validation_rejects_missing_or_invalid_signatures` + real Core prepare/confirm (unsigned + Ed25519) | pass |
| `operational-errors` | Unit tests `test_core_errors_are_stable_and_do_not_leak_tracebacks`, `test_gate_decision_maps_command_and_errors_without_business_rules` + real Core stale/governed-material/expired paths | pass |
| `evidence-integrity` | Unit test `test_rejects_malformed_nested_control_contracts` validates `evidence_content_sha256` map exactness; control-model enforces digest map parity | pass |
| `boundaries` | Unit test `test_productive_code_has_no_cli_or_protocol_parser_boundary` + `test_reports_core_absence_without_cli_fallback` scan for subprocess/CLI/direct `.agora` | pass |
| `verification` | 34 automated tests (unit + real Core + frontend + security + Chromium model parse) covering success, stale, expired, external-edit, signature, rollback, indeterminate, schema incompatibility | pass |
| `documentation` | README, architecture.md updated to Studio 0.5.0 / Core 0.8; compatibility matrix row added | pass |
| `scope` | Human clarification recorded; budget amendment deferred; no 0.7 shim | pass |

## Test Evidence

```bash
ruff format --check .     # pass
ruff check .              # pass
python -m unittest discover -s tests -v   # 34/34 pass
python -m build           # wheel 0.5.0 built
```

### Test Breakdown

| Suite | Tests | Coverage |
|---|---|---|
| `test_core_gateway` | 6 | CoreReadGateway schemas v2/v3, bounded concurrent-edit retry (2×50ms), version gate `>=0.8,<0.9`, schema validation, ProjectStore atomic selection |
| `test_command_gateway` | 5 | prepare_gate (v4→v3), approve_gate (v3), authorization payload byte-preserving, evidence_content_sha256 exact map, actor_fingerprint, prepared_at/expires_at, freshness `governed-material/v2`, signature validation |
| `test_api` | 7 | All `/api/v1` routes versioned, prepare/confirm envelope schemas v3, error mapping `_COMMAND_STATUS`, legacy alias removal, invalid slug/selection rejection |
| `test_http_security` | 4 | Host/Origin/CSRF/Content-Type/body-size enforcement, no-store/CSP/frame headers |
| `test_frontend_and_packaging` | 8 | Node parse of all `.js`, schema constants v4/v3, accessibility/reduced-motion/320px contracts, no CLI/boundary violations, packaging metadata |
| `test_real_integration` | 4 | Real Core 0.8.0 project select, specification history/revisions, gate prepare/confirm (unsigned + Ed25519), stale/governed-material/expired error paths, activity audit, artifact refresh |

## Schema Migration Summary

| Area | Core 0.7 | Core 0.8 | Studio 0.5.0 |
|---|---|---|---|
| `project-overview` | v1 | v2 (+`gate_decision_ttl_seconds`) | v2 |
| `method-summary` | v1 | v2 (+TTL) | v2 |
| `gate-summary` | v1 | v2 (+`require_content_addressed_evidence`) | v2 |
| `work-item-detail` | v2 | v3 (nested artifact/evidence v3) | v3 |
| `artifact-summary` | v2 | v3 (+`content_sha256`) | v3 |
| `evidence-summary` | v2 | v3 (+`artifact_content_sha256`) | v3 |
| `lifecycle-projection` | v2 | v3 (gate-summary v2) | v3 |
| `traceability-summary` | v1 | v2 (artifact/evidence v3) | v2 |
| `gate-option-summary` | v2 | v3 (digest map, content-addressed flag) | v3 |
| `gate-options-projection` | v2 | v3 (option v3) | v3 |
| `work-control-projection` | v2 | v3 (full aggregate) | v3 |
| `approve-gate-command` | v3 | v4 (+digest map, fingerprint, timestamps) | v4 |
| `prepared-gate-decision` | v2 | v3 (+digest map, fingerprint, timestamps, authorization v4) | v3 |
| `gate-decision-projection` | v2 | v3 (lifecycle v3) | v3 |

## Operational Error Handling (Error v2)

| Code | Studio 0.5.0 behavior |
|---|---|
| `command.preparation-expired` | Invalidate prepared material, keep form, require re-prepare (410) |
| `command.governed-material-stale` | Require refresh/review/re-prepare with safe details (409) |
| `durable-state.concurrent-edit` (retryable) | Bounded read retry 2×50ms; never mutations; 409 on exhaustion |
| `gate.evidence-missing` / `command.evidence-missing` | Render typed blockers; do not calculate sufficiency (422) |
| `command.signature-invalid` | Invalidate signature, require new prepare (422) |
| `transaction.commit-failed` | Report not committed, preserve review text, allow explicit retry (503) |
| `transaction.rollback-failed` | Require operator review, no auto-retry (503) |
| `transaction.indeterminate` | Disable mutations for project; show recovery_hint; re-enable only via explicit project re-selection or "Retry after operator review" (503) |

All error flows tested in `test_real_integration` and `test_api`.

## Evidence Integrity

- Artifact URI vs `content_sha256` rendered as escaped text (`textContent`), never HTML
- `evidence_content_sha256` map preserved with `null` for missing content
- Option with `content_addressed_evidence_required` disabled while Core reports `gate.evidence-content-digest-missing` or any blocker
- No evidence download, URI hashing, blocker suppression, or policy inference in production code

## Boundary Enforcement

- No `subprocess`, `AgoraCliBoundary`, `_cli`, `_gate_blockers`, `parse_front_matter`, `Path(".agora")` in production code
- All reads via `AgoraReadService`, all mutations via `AgoraCommandService`
- No database, authentication, remote access, or multi-user behavior added

## HTTP and Browser

- Loopback `127.0.0.1`, Host/Origin/CSRF/JSON/body-size/no-store/CSP/frame/referrer protections retained
- Prepared/confirm envelopes expose Core material for review without private keys
- Browser invalidates prepared state on project/work/option/reason/evidence/generation/freshness change
- Digest maps, expiry, recovery, mutation-disabled states: keyboard accessible, responsive, reduced-motion safe, explicit loading/empty/success/stale/failure states
- Durable strings via `textContent` only

## Build Verification

```bash
python -m build
# agora_studio-0.5.0.tar.gz + agora_studio-0.5.0-py3-none-any.whl

# Clean install smoke test:
# pip install dist/agora_studio-0.5.0-py3-none-any.whl
# agora-studio --version  # 0.5.0
# python -c "import agora_studio; print(agora_studio.__version__)"  # 0.5.0
```

## CI Matrix (specified in plan, not yet executed)

- Python 3.11, 3.12, 3.13
- Core `v0.8.0` (immutable tag) + latest `>=0.8,<0.9` wheel
- `ruff format --check`, `ruff check`, unit tests, build, wheel install smoke, Chromium scenarios

## Exclusions Verified

- Budget amendment UI: no controls added (deferred per clarification)
- Core 0.7 compatibility shim: none
- Durable protocol migration: none
- Historical `session.context-invalid` (40 pre-existing): untouched, not waived

## Conclusion

All nine acceptance criteria have implementation and verification evidence. Studio 0.5.0 ships with `agora-framework>=0.8,<0.9` and satisfies the clarified contract in `repo://docs/specs/core-0.8-studio-migration.md`.