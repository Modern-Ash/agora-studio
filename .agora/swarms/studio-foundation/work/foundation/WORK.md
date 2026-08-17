---
schema: "agora/work/v1"
id: "foundation"
swarm: "studio-foundation"
title: "Build the Agora Studio foundation"
state: "completed"
operational-status: "active"
status-reason: null
status-by: null
status-at: null
acceptance-criteria: {"startup":"The application starts on 127.0.0.1","selection":"A valid Agora project can be selected","invalid-project":"Invalid projects produce a clear error","read-only":"Browsing does not mutate the repository","tests":"Success and failure paths have automated tests"}
satisfied-criteria: ["startup","selection","invalid-project","read-only","tests"]
required-artifacts: ["spec"]
child-work-refs: []
budget-limits: null
---

# Build the Agora Studio foundation

## Description

Create the local server, project selection and read-only Agora CLI boundary.

## Acceptance criteria

- [x] **startup:** The application starts on 127.0.0.1
- [x] **selection:** A valid Agora project can be selected
- [x] **invalid-project:** Invalid projects produce a clear error
- [x] **read-only:** Browsing does not mutate the repository
- [x] **tests:** Success and failure paths have automated tests

## Required artifacts

- spec
