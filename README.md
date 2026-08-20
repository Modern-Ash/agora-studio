<p align="center">
  <img src="./agora-logo.png" alt="Agora" width="560">
</p>

# Agora Studio

Agora Studio is the experimental, local-first web control plane for Agora projects. Studio 0.3
renders operational state through Agora Core 0.6 application services and offers one governed
mutation: approving or rejecting an exact gate option calculated by Core.

> [!WARNING]
> Studio is experimental software. Keep it on loopback and review sensitive projects before
> opening them.

## Architecture

```text
Browser -> /api/v1 -> Studio API -> AgoraReadService / AgoraCommandService -> Agora Core 0.6
```

The browser consumes only `/api/v1`. Studio does not execute Agora CLI, spawn subprocesses, read
durable protocol files, parse Markdown/front matter, or calculate lifecycle rules. Core owns
project validation, Method Pack topology, transition availability, gates, blockers, artifacts,
evidence, approvals, traceability, specification history, persistence, and Activity.

Markdown and Git remain the source of truth through Core's persistence adapters. Studio keeps only
the selected canonical project path and a random CSRF token in process memory. There is no
database, remote service, multi-user mode, telemetry, or frontend framework.

## Views

- **Overview** — active Method Pack, active swarms, work in progress, blocked work, approvals,
  evidence, failed sessions, and recent Activity.
- **Work** — a read-only board grouped by Core-reported Method state, with Summary, Spec,
  Lifecycle, Artifacts, Evidence, Approvals, and Activity tabs.
- **Swarms** — status, Method Pack, objective, assignments, and work states.
- **Actors** — configured actors, capabilities, durable references, and runtime metadata.
- **Activity** — a bounded, filterable timeline of durable Core events.

Gate approval and rejection use Core's versioned decision options and `ApproveGateCommand v2`.
Studio never chooses a first gate, role, actor, transition, or readiness state. Disabled options
retain the blockers returned by Core. For authenticated actors, Studio requests the canonical
payload, shows its digest and public fingerprint, accepts an externally produced detached
signature, and sends it back to Core. Studio never reads or stores a private key. There is no
optimistic mutation.

## Install and run

Python 3.11, 3.12, and 3.13 are supported.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install "agora-studio==0.3.0"
agora-studio --version
agora-studio --port 7357
```

Installing the Studio wheel installs a compatible Agora Core wheel automatically. No `agora`
executable or sibling checkout is required. Open <http://127.0.0.1:7357> and select a local Agora
project.

For development with the sibling Core checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ../agora -e ".[dev]"
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m build
```

## Core compatibility

| Studio | Agora Core package | Application contracts | Durable protocol |
| --- | --- | --- | --- |
| 0.1.x | Transitional/implicit | CLI reads plus gate command v1 | Project-defined |
| 0.2.x | `agora-framework>=0.5,<0.6` | Core 0.5 read DTOs and gate command v1 | Project-defined and independently versioned |
| 0.3.x | `agora-framework>=0.6,<0.7` | Work detail v2, work control v1, gate command v2, prepared decision v1, revision detail v1 | Project-defined and independently versioned |

Three versions must not be conflated:

- **Studio version** describes this web package and API adapter.
- **Core version** describes the installed `agora-framework` Python distribution.
- **Protocol version** belongs to the selected durable Agora project.

Studio validates the Core package range and every DTO schema it consumes. Missing Core, an
unsupported Core minor, or an unexpected schema returns an explicit compatibility error; Studio
never falls back to the CLI or a local parser.

## HTTP API

All current endpoints are under `/api/v1`:

- `GET /project`, `/overview`, `/actors`, `/swarms`, `/work-items`, `/sessions`, `/activity`;
- `GET /work-items/{swarm}/{work}`;
- `GET /specification-revisions/{revision_id}?swarm=...&work=...`;
- `GET /lifecycle`, `/artifacts`, `/evidence`, `/approvals`, `/traceability`,
  `/specification-history`;
- `POST /projects/select`;
- `POST /work-items/{swarm}/{work}/approvals/prepare`;
- `POST /work-items/{swarm}/{work}/approvals`.

Every successful projection and error has a schema identifier. Missing durable information is
returned as an explicit unavailable projection where Core supports it; compatibility and read
failures remain distinct HTTP errors. Legacy unversioned API aliases are removed.

## Security boundaries

- The server binds only to IPv4 loopback.
- Every request validates `Host`.
- Mutating requests require an exact same-loopback `Origin` and the process-random
  `X-Agora-Studio-CSRF` token obtained from `GET /api/v1/project`.
- The token is held only in memory, is not logged, and is never persisted in the selected project.
- JSON mutations require `application/json` and a body no larger than 64 KiB.
- Approval requests accept only versioned identifiers and bounded text; browser-provided paths are
  not part of either gate endpoint.
- Canonical payloads and detached signatures remain request-scoped. Studio does not persist or log
  them and never handles private key material.
- Responses set CSP, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, no-referrer, and
  no-store headers where appropriate. Studio emits no permissive CORS header.
- Durable text is rendered through text nodes, not interpreted as HTML.
- Concurrent gate requests are serialized at the HTTP adapter and remain governed by Core's
  transaction and stale-precondition checks.

Loopback is an exposure boundary, not user authentication. Anyone with access to the same local
session may be able to view the selected project's durable data.

## Verification

The suite includes behavioral JavaScript model tests, strict schema-failure tests, HTTP security
tests, and non-mocked Core–Studio integrations. Those integrations create temporary Agora projects,
start the loopback server, read the dashboard, prepare and persist unsigned and signed decisions,
verify Activity, and retrieve committed and working-tree specification revisions exclusively
through Core.

CI builds the Core wheel, installs it, builds and installs the Studio wheel, runs Python
3.11–3.13, and checks that production code contains no CLI bridge, subprocess access, protocol
parser, or direct durable-file read.

See the [Core 0.6 / Studio 0.3 verification record](docs/evidence/core-0.6-studio-0.3-verification.md)
for the exercised contracts, distribution smoke, and deliberate limits.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md). Agora Studio is licensed under the
[Apache License 2.0](LICENSE).
