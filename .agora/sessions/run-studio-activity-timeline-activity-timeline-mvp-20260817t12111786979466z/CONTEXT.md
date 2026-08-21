# Agora session context

## Project

- Name: agora-studio
- Root: `/home/faguero/dev-agora/agora-studio`

## Runtime

- Integration: `codex`
- Provider: `openai`
- Model: `configured-by-codex`

## Actor

- Identity: `project:specification-agent`
- Kind: `ai-agent`
- Roles: `spec-owner`
- Capabilities: `acceptance`, `specification`
- Represented swarm: `none`

## Swarm

- Id: `studio-activity-timeline`
- Method: `spec-driven`
- Objective: Build a read-only governed activity timeline for Agora Studio so developers can understand what humans, agents, swarms, sessions, and tools did and why.

## Active work

- Id: `activity-timeline-mvp`
- Title: Build the governed activity timeline
- State: `drafting`
- Path: `.agora/swarms/studio-activity-timeline/work/activity-timeline-mvp`

## Required reading

- `.agora/project.md`
- `.agora/activity.md`
- `.agora/constitution.md`
- `.agora/PROTOCOL.md`
- `.agora/STANDARDS.md`
- `.agora/tools/TOOLS.md`
- `.agora/swarms/studio-activity-timeline/SWARM.md`
- `.agora/swarms/studio-activity-timeline/events.md`
- `.agora/methods/spec-driven/METHOD.md`
- `.agora/methods/spec-driven/PROTOCOL.md`
- `.agora/methods/spec-driven/TOOLS.md`
- `.agora/methods/spec-driven/roles/spec-owner.md`
- `.agora/environments/README.md`
- `.agora/swarms/studio-activity-timeline/handoffs/activity-spec-to-ai/HANDOFF.md`
- `.agora/swarms/studio-activity-timeline/work/activity-timeline-mvp/WORK.md`
- `.agora/swarms/studio-activity-timeline/work/activity-timeline-mvp/artifacts.md`
- `.agora/swarms/studio-activity-timeline/work/activity-timeline-mvp/evidence.md`
- `.agora/swarms/studio-activity-timeline/work/activity-timeline-mvp/approvals.md`

## Operating rules

1. Read every available file listed above before acting.
2. Perform only actions allowed to the assigned role and active transition.
3. Use the Agora CLI to persist state, artifacts, evidence, and material outcomes.
4. Do not treat unrecorded conversation history as durable project state.
5. Stop when policy, permissions, or a gate cannot be satisfied.
