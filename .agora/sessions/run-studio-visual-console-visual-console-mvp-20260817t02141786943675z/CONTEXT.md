# Agora session context

## Project

- Name: agora-studio
- Root: `/home/faguero/dev-agora/agora-studio`

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

- Id: `studio-visual-console`
- Method: `spec-driven`
- Objective: Build the first operational visual console for Agora Studio, allowing developers to select a local Agora project and inspect its governed delivery state without mutating it.

## Active work

- Id: `visual-console-mvp`
- Title: Build the Agora Studio visual console
- State: `planned`
- Path: `.agora/swarms/studio-visual-console/work/visual-console-mvp`

## Required reading

- `.agora/project.md`
- `.agora/constitution.md`
- `.agora/PROTOCOL.md`
- `.agora/STANDARDS.md`
- `.agora/tools/TOOLS.md`
- `.agora/swarms/studio-visual-console/SWARM.md`
- `.agora/swarms/studio-visual-console/events.md`
- `.agora/methods/spec-driven/METHOD.md`
- `.agora/methods/spec-driven/PROTOCOL.md`
- `.agora/methods/spec-driven/TOOLS.md`
- `.agora/methods/spec-driven/roles/developer.md`
- `.agora/environments/README.md`
- `.agora/swarms/studio-visual-console/work/visual-console-mvp/WORK.md`
- `.agora/swarms/studio-visual-console/work/visual-console-mvp/artifacts.md`
- `.agora/swarms/studio-visual-console/work/visual-console-mvp/evidence.md`
- `.agora/swarms/studio-visual-console/work/visual-console-mvp/approvals.md`

## Operating rules

1. Read every available file listed above before acting.
2. Perform only actions allowed to the assigned role and active transition.
3. Use the Agora CLI to persist state, artifacts, evidence, and material outcomes.
4. Do not treat unrecorded conversation history as durable project state.
5. Stop when policy, permissions, or a gate cannot be satisfied.
