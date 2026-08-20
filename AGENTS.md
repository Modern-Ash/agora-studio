# AGENTS.md

These instructions apply to the entire Agora Studio repository.

## Product boundary

Agora Studio is an experimental, local-first web control plane. Preserve the current functional
architecture unless a task explicitly changes it:

- bind only to `127.0.0.1`;
- keep projections read-only and route any explicitly governed mutation through Agora Core
  application services;
- treat Markdown and Git as the source of truth;
- do not edit `.agora/` records;
- do not add authentication, a database, remote or multi-user behavior;
- do not migrate the dependency-free frontend incidentally.

Studio must not become the owner of Agora lifecycle or domain rules. The current Agora CLI bridge
is temporary and limited to reviewed read operations. Keep invocations as explicit argument
arrays with `shell=False`, bounded timeouts, validated JSON, and no user-selected command names.
Preserve project path containment, symlink protections, and Git object-name validation.

## Working practices

- Inspect `git status` before editing and preserve unrelated work.
- Read the relevant spec, plan, evidence, and durable `.agora/` records before changing behavior.
- Prefer Python standard-library solutions unless a dependency is justified by the task.
- Keep the package version in `agora_studio.__version__`; packaging and `--version` read it from
  there.
- Add or update tests for contract, security, and rendering changes.
- Do not commit or push unless the user explicitly asks.

## Verification

Run these checks before handing off a change:

```bash
ruff format --check .
ruff check .
python -m unittest discover -s tests -v
python -m build
```

For packaging changes, install the wheel into a clean environment and run
`agora-studio --version` plus a package-resource smoke test.
