---
schema: "agora/work/v1"
id: "foundation"
swarm: "studio-foundation"
title: "Build the Agora Studio foundation"
state: "drafting"
operational-status: "active"
status-reason: null
status-by: null
status-at: null
acceptance-criteria: {"startup":"The application starts on 127.0.0.1","selection":"A valid Agora project can be selected","invalid-project":"Invalid projects produce a clear error","read-only":"Browsing does not mutate the repository","tests":"Success and failure paths have automated tests"}
satisfied-criteria: []
required-artifacts: ["spec"]
child-work-refs: []
budget-limits: null
---

# Build the Agora Studio foundation

## Description

Create the local server, project selection and read-only Agora CLI boundary.

## Acceptance criteria

- [ ] **startup:** The application starts on 127.0.0.1
- [ ] **selection:** A valid Agora project can be selected
- [ ] **invalid-project:** Invalid projects produce a clear error
- [ ] **read-only:** Browsing does not mutate the repository
- [ ] **tests:** Success and failure paths have automated tests

## Required artifacts

- spec
