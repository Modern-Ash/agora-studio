# Agora Studio architecture

Agora Studio 0.5 is a local-first HTTP and browser adapter over Agora Core 0.8 application
services.

```text
Browser
  -> /api/v1
  -> Studio API
  -> CoreReadGateway / CoreCommandGateway
  -> AgoraReadService / AgoraCommandService
  -> Agora Core domain and persistence adapters
  -> Markdown and Git
```

## Ownership

Core owns durable project validation, Method Pack interpretation, lifecycle topology, transition
availability, gate blockers, authority, evidence requirements, approvals, traceability,
specification history, transactions, and Activity. Studio maps public DTO fields into versioned
HTTP envelopes and presentation models. It never invokes terminal commands or reads protocol
records.

`ProjectStore` retains one canonical project path in memory only after
`AgoraReadService.project_overview()` succeeds. `CoreReadGateway` requires the
`agora-framework>=0.8,<0.9` distribution and validates every consumed DTO's exact schema.
Compatibility failures are explicit and have no CLI or filesystem fallback.

Work detail uses `agora/application/work-item-detail/v2` inside Core's
`work-control-projection/v2`. That aggregate contains a snapshot token, lifecycle, artifacts,
evidence, approvals,
traceability, specification history, and exact gate decision options. Studio presents those facts
without recreating readiness, blocker, role, actor, or evidence rules.

## HTTP boundary

Only `/api/v1` is supported. Read endpoints expose overview, actors, swarms, work, sessions,
Activity, lifecycle, materials, traceability, and specification history. The gate-decision
endpoint constructs the versioned Core command, delegates the transaction, and returns Core's
durable projection.

The server binds to `127.0.0.1`. Every request validates `Host`. Mutations additionally require
an exact loopback `Origin`, a process-random CSRF token, JSON content type, and a bounded body.
CSP, no-sniff, frame denial, and no-referrer headers are applied to API and static responses.
There is no permissive CORS behavior.

Authenticated decisions have a separate preparation endpoint. Studio sends an intent with no
digest or signature. Core returns the canonical reason and evidence references, opaque
precondition digest, authorization payload and digest, actor, role, gate, decision, expected state,
target state, freshness marker, and public authentication metadata. The gateway validates the
complete prepared contract and verifies that the authorization SHA-256 matches the exact canonical
JSON. Confirmation is constructed only from those prepared fields, plus an optional detached
signature. Private keys never enter Studio. `GateDecisionProjection v2` is accepted only when its
complete identity, evidence references, precondition digest, nested lifecycle, and Activity
schemas match the submitted command.

## State and concurrency

Studio persists no projection. Browser refreshes reread Core after mutations. Successful mutation
responses are never applied optimistically: Studio waits for Core durability, rereads a complete
`WorkControlProjection v2`, and replaces the previous aggregate. The in-memory
selection is protected by a reentrant lock; threaded HTTP reads may run concurrently, while gate
submissions are serialized before entering Core. Core remains responsible for transaction
atomicity, stale preconditions, and double-submit rejection.

The Core work-control aggregate checks that work, lifecycle, traceability, and decision-option
states agree before Studio receives them and identifies the result with a validated snapshot token.
The browser associates reads with project generation, work identity, request revision, refresh, and
mutation revision; older responses are ignored or aborted. Core 0.8 binds the prepared action to a
complete governed-material precondition digest. Studio treats that digest as opaque, never computes
it, invalidates it on edit, and never retries a stale mutation automatically. `expires_at` is
currently null; time-based expiry remains a future Core contract decision.

Gate options carry both the eligible evidence-reference union and
`evidence_references_by_type`. Studio renders Core's required types, associated references, and
blockers without matching evidence in JavaScript.

## Verification

Unit tests use a fake gateway to characterize HTTP mapping without duplicating domain rules. The
integration suite uses real Core services and temporary durable projects, starts an actual
loopback server, exercises unsigned and detached-signature approval, rejection, specification
revision detail, and verifies persistence plus subsequent Activity and projection reads. CI also
scans production sources for forbidden CLI, subprocess, Git execution, parser, direct durable-file
boundaries, and recreated frontend readiness heuristics. A separate Playwright suite runs 22
scenarios in real Chromium against the same loopback boundary, including canonical preparation,
unsigned and Ed25519 confirmation, stale refresh, rapid specification-revision switching, response
ordering, keyboard focus, mobile layout, and safe durable-text rendering.
