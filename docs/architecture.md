# Agora Studio architecture

Agora Studio 0.3 is a local-first HTTP and browser adapter over Agora Core 0.6 application
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
`agora-framework>=0.6,<0.7` distribution and validates every consumed DTO's exact schema.
Compatibility failures are explicit and have no CLI or filesystem fallback.

Work detail uses `agora/application/work-item-detail/v2` inside Core's
`work-control-projection/v1`. That aggregate contains lifecycle, artifacts, evidence, approvals,
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

Authenticated decisions have a separate preparation endpoint. Core returns the canonical
authorization payload, digest, actor, role, gate, decision, expected state, target state, and
public fingerprint. Studio validates only the HTTP shape, accepts a detached signature, and sends
the exact command to Core. Private keys never enter Studio. `GateDecisionProjection v1` is accepted
only when its complete identity plus nested lifecycle and Activity schemas match the submitted
command.

## State and concurrency

Studio persists no projection. Browser refreshes reread Core after mutations. The in-memory
selection is protected by a reentrant lock; threaded HTTP reads may run concurrently, while gate
submissions are serialized before entering Core. Core remains responsible for transaction
atomicity, stale preconditions, and double-submit rejection.

The Core work-control aggregate checks that work, lifecycle, traceability, and decision-option
states agree before Studio receives them. This is a guarded logical snapshot, not a database
transaction or filesystem-wide snapshot. Signed payload freshness in Core 0.6 is bound to the
expected durable state; `expires_at` is currently null. Studio invalidates and regenerates prepared
payloads whenever the selected action or reason changes. Time-based expiry remains a future Core
contract decision.

## Verification

Unit tests use a fake gateway to characterize HTTP mapping without duplicating domain rules. The
integration suite uses real Core services and temporary durable projects, starts an actual
loopback server, exercises unsigned and detached-signature approval, rejection, specification
revision detail, and verifies persistence plus subsequent Activity and projection reads. CI also
scans production sources for forbidden CLI, subprocess, Git execution, parser, direct durable-file
boundaries, and recreated frontend readiness heuristics.
