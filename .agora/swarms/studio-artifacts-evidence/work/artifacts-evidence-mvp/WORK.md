---
schema: "agora/work/v1"
id: "artifacts-evidence-mvp"
swarm: "studio-artifacts-evidence"
title: "Build the artifacts and evidence view"
state: "completed"
operational-status: "active"
status-reason: null
status-by: null
status-at: null
acceptance-criteria: {"listing":"A developer can browse a work item's artifacts and evidence records with kind, status and linked criterion","approvals":"Approval roles and their satisfaction state are visible for the selected work item","traceability":"A selected artifact or evidence record links back to its originating session or tool run when available","safety":"The backend uses only reviewed read-only Agora CLI operations and never exposes credentials, private keys or provider chain-of-thought","states":"Loading, empty, invalid-project and query-failure states are explicit and actionable","responsive-accessible":"The view remains usable on desktop and mobile with keyboard navigation, visible focus and reduced-motion support","tests":"Automated tests cover listing, approvals, traceability, safety boundaries and success, empty and failure responses"}
satisfied-criteria: ["listing","approvals","traceability","safety","states","responsive-accessible","tests"]
required-artifacts: ["spec"]
child-work-refs: []
budget-limits: null
---

# Build the artifacts and evidence view

## Description

Add a read-only view to Agora Studio that browses artifacts, evidence and approvals for a selected work item, without exposing provider reasoning or mutating the selected project.

## Acceptance criteria

- [x] **listing:** A developer can browse a work item's artifacts and evidence records with kind, status and linked criterion
- [x] **approvals:** Approval roles and their satisfaction state are visible for the selected work item
- [x] **traceability:** A selected artifact or evidence record links back to its originating session or tool run when available
- [x] **safety:** The backend uses only reviewed read-only Agora CLI operations and never exposes credentials, private keys or provider chain-of-thought
- [x] **states:** Loading, empty, invalid-project and query-failure states are explicit and actionable
- [x] **responsive-accessible:** The view remains usable on desktop and mobile with keyboard navigation, visible focus and reduced-motion support
- [x] **tests:** Automated tests cover listing, approvals, traceability, safety boundaries and success, empty and failure responses

## Required artifacts

- spec
