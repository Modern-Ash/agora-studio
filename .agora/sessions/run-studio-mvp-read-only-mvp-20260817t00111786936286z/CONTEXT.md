# Agora session context

## Project

- Name: agora-studio
- Root: `/home/faguero/dev/agora-studio`

## Runtime

- Integration: `codex`
- Provider: `openai`
- Model: `configured-by-codex`

## Actor

- Identity: `project:agent`
- Kind: `ai-agent`
- Roles: `developer`
- Capabilities: `implementation`
- Represented swarm: `none`

## Swarm

- Id: `studio-mvp`
- Method: `spec-driven`
- Objective: Build a local-first GUI for visualizing and operating Agora projects while keeping Markdown and Git as the source of truth

## Active work

- Id: `read-only-mvp`
- Title: Define read-only Agora Studio MVP
- State: `implementing`
- Path: `.agora/swarms/studio-mvp/work/read-only-mvp`

## Required reading

- `.agora/project.md`
- `.agora/constitution.md`
- `.agora/PROTOCOL.md`
- `.agora/STANDARDS.md`
- `.agora/tools/TOOLS.md`
- `.agora/swarms/studio-mvp/SWARM.md`
- `.agora/swarms/studio-mvp/events.md`
- `.agora/methods/spec-driven/METHOD.md`
- `.agora/methods/spec-driven/PROTOCOL.md`
- `.agora/methods/spec-driven/TOOLS.md`
- `.agora/methods/spec-driven/roles/developer.md`
- `.agora/environments/README.md`
- `.agora/swarms/studio-mvp/work/read-only-mvp/WORK.md`
- `.agora/swarms/studio-mvp/work/read-only-mvp/artifacts.md`
- `.agora/swarms/studio-mvp/work/read-only-mvp/evidence.md`
- `.agora/swarms/studio-mvp/work/read-only-mvp/approvals.md`

## Operating rules

1. Read every available file listed above before acting.
2. Perform only actions allowed to the assigned role and active transition.
3. Use the Agora CLI to persist state, artifacts, evidence, and material outcomes.
4. Do not treat unrecorded conversation history as durable project state.
5. Stop when policy, permissions, or a gate cannot be satisfied.
