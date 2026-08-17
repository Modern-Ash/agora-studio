---
schema: "agora/work/v1"
id: "activity-timeline-mvp"
swarm: "studio-activity-timeline"
title: "Build the governed activity timeline"
state: "completed"
operational-status: "active"
status-reason: null
status-by: null
status-at: null
acceptance-criteria: {"timeline":"The interface presents durable activity in chronological order with clear event type, time, actor and governed scope","filters":"A developer can filter activity by event type, actor, swarm, work, session and tool run without mutating the project","traceability":"A selected event links to its durable source and presents related artifact, evidence or session summaries when available","safety":"The backend uses only reviewed read-only Agora CLI operations and never exposes credentials, private keys or provider chain-of-thought","states":"Loading, empty, invalid-project and query-failure states are explicit and actionable","responsive-accessible":"The timeline remains usable on desktop and mobile with keyboard navigation, visible focus and reduced-motion support","tests":"Automated tests cover chronology, filters, traceability, safety boundaries and success, empty and failure responses"}
satisfied-criteria: ["timeline","filters","traceability","safety","states","responsive-accessible","tests"]
required-artifacts: ["spec"]
child-work-refs: []
budget-limits: null
---

# Build the governed activity timeline

## Description

Add a read-only visual timeline to Agora Studio that explains durable human, agent, swarm, session, and tool activity from Agora records without exposing provider reasoning or mutating the selected project.

## Acceptance criteria

- [x] **timeline:** The interface presents durable activity in chronological order with clear event type, time, actor and governed scope
- [x] **filters:** A developer can filter activity by event type, actor, swarm, work, session and tool run without mutating the project
- [x] **traceability:** A selected event links to its durable source and presents related artifact, evidence or session summaries when available
- [x] **safety:** The backend uses only reviewed read-only Agora CLI operations and never exposes credentials, private keys or provider chain-of-thought
- [x] **states:** Loading, empty, invalid-project and query-failure states are explicit and actionable
- [x] **responsive-accessible:** The timeline remains usable on desktop and mobile with keyboard navigation, visible focus and reduced-motion support
- [x] **tests:** Automated tests cover chronology, filters, traceability, safety boundaries and success, empty and failure responses

## Required artifacts

- spec
