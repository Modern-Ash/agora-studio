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

- Id: `studio-artifacts-evidence`
- Method: `spec-driven`
- Objective: Visualize artifacts, evidence and approvals for Agora work items

## Active work

- Id: `artifacts-evidence-mvp`
- Title: Build the artifacts and evidence view
- State: `clarified`
- Path: `.agora/swarms/studio-artifacts-evidence/work/artifacts-evidence-mvp`

## Required reading

- `.agora/project.md`
- `.agora/activity.md`
- `.agora/constitution.md`
- `.agora/PROTOCOL.md`
- `.agora/STANDARDS.md`
- `.agora/tools/TOOLS.md`
- `.agora/swarms/studio-artifacts-evidence/SWARM.md`
- `.agora/swarms/studio-artifacts-evidence/events.md`
- `.agora/methods/spec-driven/METHOD.md`
- `.agora/methods/spec-driven/PROTOCOL.md`
- `.agora/methods/spec-driven/TOOLS.md`
- `.agora/methods/spec-driven/roles/developer.md`
- `.agora/environments/README.md`
- `.agora/swarms/studio-artifacts-evidence/work/artifacts-evidence-mvp/WORK.md`
- `.agora/swarms/studio-artifacts-evidence/work/artifacts-evidence-mvp/artifacts.md`
- `.agora/swarms/studio-artifacts-evidence/work/artifacts-evidence-mvp/evidence.md`
- `.agora/swarms/studio-artifacts-evidence/work/artifacts-evidence-mvp/approvals.md`

## Operating rules

1. Read every available file listed above before acting.
2. Perform only actions allowed to the assigned role and active transition.
3. Use the Agora CLI to persist state, artifacts, evidence, and material outcomes.
4. Do not treat unrecorded conversation history as durable project state.
5. Stop when policy, permissions, or a gate cannot be satisfied.
