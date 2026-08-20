# Contributing to Agora Studio

Thanks for helping improve Agora Studio. The project is experimental, but changes should preserve
its deliberately small and auditable local-first boundary.

## Development setup

Use Python 3.11 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ../agora -e ".[dev]"
```

Run the application with `python -m agora_studio` or `agora-studio`. Development may use the
sibling Core checkout, but production and wheel tests use `agora-framework>=0.7,<0.8`.

## Before opening a pull request

Run the same checks as CI:

```bash
ruff format --check .
ruff check .
python -m unittest discover -s tests -v
python -m pip install -e ".[e2e]"
python -m playwright install chromium
python -m unittest discover -s e2e -v
python -m build
```

Install the generated wheel into a clean virtual environment and verify
`agora-studio --version`. Add focused tests for behavior changes and update user-facing
documentation when a contract or safety boundary changes.

## Architectural guardrails

- Keep Studio local-first and bound to loopback during the `0.x` series. Reads remain read-only;
  any governed mutation must cross a versioned Agora Core application-service boundary.
- Treat Markdown and Git as the source of truth. Do not introduce a database, authentication,
  remote mode, or multi-user behavior without an accepted architectural decision.
- Never edit a selected project's `.agora/` files from Studio.
- Keep browser rendering separate from Agora domain and application rules.
- Consume only public, versioned `agora.application` DTOs and services. Do not execute Agora CLI,
  spawn processes, parse durable files, or add a local lifecycle fallback.
- Preserve Core's path containment, symlink defenses, bounded reads, and schema validation.
- Do not add frontend frameworks or remote assets as incidental changes.

Changes to Core DTO expectations must include consumer-contract tests and must not silently invent
durable relationships.

## Change scope

Keep pull requests focused and explain user-visible behavior, validation performed, and known
risks. Do not commit generated `build/`, `dist/`, virtual environments, caches, or local Agora
session records unrelated to the change.

By contributing, you agree that your contribution is licensed under Apache License 2.0.
