<p align="center">
  <img src="./agora-logo.png" alt="Agora" width="560">
</p>

# Agora Studio

Agora Studio is the experimental web control plane for Agora projects. The current `0.x`
implementation is local-first: its operational views are read-only, and its first governed action
can approve or reject a pending gate through Agora Core.

> [!WARNING]
> Agora Studio is experimental. Its UI and compatibility surface may change between `0.x`
> releases. Do not expose the server to untrusted networks.

## What is available today

Studio provides these views:

- **Overview** — active Method Pack, operational metrics, immediate work focus, and recent
  activity.
- **Work** — a read-only board grouped by Method Pack state. Work detail includes Summary, Spec,
  Lifecycle, Artifacts, Evidence, Approvals, and Activity tabs. The Approvals tab can submit a
  reasoned gate approval or rejection when a durable actor, role, and evidence are available.
- **Swarms** — swarm status, method, objective, and assignments.
- **Actors** — configured actors, capabilities, and durable references.
- **Activity** — a bounded, filterable timeline derived from durable records.

Artifacts, evidence, and approvals are visualized only when durable relationships exist. Studio
does not infer or manufacture missing links. Failed reads are shown as partial-data states while
the last verified data remains visible.

## Architecture

Agora Studio is local-first during the `0.x` series:

```text
Browser on 127.0.0.1
        |
Agora Studio frontend -> /api/v1 -> loopback HTTP server
                                  |              |
                    read-only projections       AgoraCommandService
                                  |              |
                     bounded CLI/Markdown/Git    governed transaction
                                  \              /
                           selected Agora project
```

Markdown and Git remain the source of truth. Studio keeps only the active project selection in
memory: it has no database, authentication system, remote service, or multi-user mode. The
frontend is bundled with the Python package and makes no CDN or third-party network requests.

The gate-decision endpoint consumes Agora Core's versioned `ApproveGateCommand` through
`AgoraCommandService`; Studio does not reproduce authority, evidence, lifecycle, or transaction
rules. Existing read projections still predate that boundary and invoke a small allowlist of
read-only Agora CLI commands. That bridge is an implementation constraint, not a conceptual
dependency on terminal workflows.

## Requirements

- Python 3.11, 3.12, or 3.13
- An `agora` executable on `PATH`
- An editable Agora Core environment exposing `AgoraCommandService` for governed actions
- A local Agora project containing `.agora/project.md`

## Install and run

From a checkout:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ../agora
python -m pip install .
agora-studio --version
agora-studio --port 7357
```

Open <http://127.0.0.1:7357>, select a local Agora project directory, and load its views. The
same server can be run from source with `python -m agora_studio`.

For development:

```bash
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
python -m unittest discover -s tests -v
python -m build
```

## Security boundaries

- The server binds only to `127.0.0.1`; non-loopback hosts are not configurable.
- Project selection requires a real, readable directory with `.agora/project.md` and successful
  Agora project identification.
- CLI calls use exact argument arrays, `shell=False`, timeouts, and an explicit read-only
  allowlist. Browser input cannot choose arbitrary Agora subcommands.
- Activity filters are length- and type-checked before a process starts.
- Lifecycle and artifact paths are resolved inside the selected project and reject traversal,
  absolute paths, symlink escapes, and unsafe Git object names.
- Studio never edits `.agora/` or Git directly. Gate decisions are sent as versioned commands to
  Agora Core, which revalidates authority and evidence and owns the durable transaction.
- The gate endpoint accepts JSON only, caps request bodies at 64 KiB, validates slugs and fields,
  derives project identity server-side, and never accepts a project path from the browser.
- Durable text is rendered with DOM text nodes rather than injected as HTML.

Loopback binding is a safety boundary, not authentication. Anyone able to access the local user
session or loopback port may see the selected project's durable records. Review sensitive
projects before opening them and do not proxy Studio onto a network.

## Agora Core compatibility

There is not yet a versioned, negotiated compatibility contract between Agora Studio and Agora
Core for the legacy read bridge. Current read compatibility is limited to the JSON emitted by
these operations:

```text
agora status
agora actor list
agora swarm list
agora work list
agora session list
agora activity list
```

Studio validates the top-level result types, the fields required to render an overview, and the
complete Activity event shape. Compatibility tests exercise that minimum shape and fail closed
when required durable data is absent or mistyped. This is narrower than a stable Core API; a
future release should replace the CLI bridge with versioned, serializable Agora application
service contracts.

The governed gate action has a narrower explicit contract:
`agora/application/approve-gate-command/v1`. If that command or `AgoraCommandService` is absent,
Studio fails closed with `command.version-incompatible`; it does not fall back to a CLI mutation.

The Studio package version and the `.agora/project.md` protocol version are independent. This
release is Agora Studio `0.1.0`; it does not claim compatibility with every Agora Core `0.x`
release.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, validation, and architectural guardrails.
Security-sensitive findings should not be published in a public issue before maintainers have a
chance to assess them.

## License

Licensed under the [Apache License 2.0](LICENSE).
