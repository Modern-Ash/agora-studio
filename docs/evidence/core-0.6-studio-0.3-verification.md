# Core 0.6 / Studio 0.3 verification

Date: 2026-08-20

## Scope

This verification covers Agora Studio 0.3.0 against the published
`agora-framework>=0.6,<0.7` application-service boundary. Production Studio code uses no CLI
bridge, subprocess, direct Git invocation, Markdown/front-matter parser, or direct `.agora/`
access.

The exercised contracts include WorkItemDetail v2, WorkControlProjection v1, gate decision
options v1, ApproveGateCommand v2, PreparedGateDecision v1, GateDecisionProjection v1, and
SpecificationRevisionDetail v1.

## Automated results

The following checks passed from the Studio repository:

```text
ruff format --check .                    422 files already formatted
ruff check .                             All checks passed
python scripts/check_boundaries.py       Application-service boundary check passed
python -m unittest discover -s tests -v  32 tests passed
```

The suite includes behavioral JavaScript execution with Node, HTTP security, schema rejection,
and real Core–Studio integration on ephemeral loopback servers. The real integration exercised:

- six Core-calculated gate options across multiple transitions, gates, roles, actors, approve,
  and reject decisions;
- disabled blockers without frontend readiness inference;
- unsigned preparation and durable approval;
- detached Ed25519 preparation, signing, verification, and durable approval;
- stale preconditions and duplicate submission rejection;
- durable rejection and Activity refresh;
- committed and working-tree specification revisions;
- bounded content and diff truncation;
- an unavailable revision response.

## Distribution result

An isolated PEP 517 build produced:

```text
agora_studio-0.3.0-py3-none-any.whl
agora_studio-0.3.0.tar.gz
```

The wheel was installed in a clean Python 3.14 virtual environment. Dependency resolution
downloaded the published `agora-framework-0.6.0` wheel from PyPI. The installed commands and
metadata reported:

```text
agora-studio 0.3.0
clean wheel pair: 0.3.0 0.6.0
```

The installed package contains `index.html`, `control-model.js`, and the remaining local static
assets.

## Server smoke

The source checkout served `/` and `/api/v1/project` successfully on `127.0.0.1:7358`. Responses
included the expected no-store behavior, same-origin CSP, no-sniff, frame denial, and no-referrer
headers. No permissive CORS header was emitted.

Visual browser inspection and screenshots were not produced because no browser instance was
available in the execution environment. Semantic markup, focus styling, tab keyboard behavior,
ARIA live status, reduced motion, absence of `innerHTML`, and absence of remote resources remain
covered by source and executable JavaScript model tests.

## Deliberate limits

- Core 0.6 provides a guarded logical work-control projection, not a filesystem-wide transactional
  snapshot.
- Signed command freshness is bound to expected durable state; `expires_at` is currently null.
  Studio invalidates prepared payloads when action inputs change, while time-based expiry remains a
  future Core contract decision.
- Studio remains loopback-only, single-process, local-first, and experimental. It has no database,
  remote mode, multi-user mode, or private-key custody.
