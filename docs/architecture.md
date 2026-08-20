# Agora Studio architecture

Agora Studio 0.2 is a local-first HTTP and browser adapter over Agora Core 0.5 application
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
`agora-framework>=0.5,<0.6` distribution and validates every consumed DTO's exact schema.
Compatibility failures are explicit and have no CLI or filesystem fallback.

## HTTP boundary

Only `/api/v1` is supported. Read endpoints expose overview, actors, swarms, work, sessions,
Activity, lifecycle, materials, traceability, and specification history. The gate-decision
endpoint constructs the versioned Core command, delegates the transaction, and returns Core's
durable projection.

The server binds to `127.0.0.1`. Every request validates `Host`. Mutations additionally require
an exact loopback `Origin`, a process-random CSRF token, JSON content type, and a bounded body.
CSP, no-sniff, frame denial, and no-referrer headers are applied to API and static responses.
There is no permissive CORS behavior.

## State and concurrency

Studio persists no projection. Browser refreshes reread Core after mutations. The in-memory
selection is protected by a reentrant lock; threaded HTTP reads may run concurrently, while gate
submissions are serialized before entering Core. Core remains responsible for transaction
atomicity, stale preconditions, and double-submit rejection.

## Verification

Unit tests use a fake gateway to characterize HTTP mapping without duplicating domain rules. The
integration suite uses real Core services and temporary durable projects, starts an actual
loopback server, exercises approval and rejection, and verifies persistence plus subsequent
Activity and projection reads. CI also scans production sources for forbidden CLI, subprocess,
parser, and direct durable-file boundaries.
