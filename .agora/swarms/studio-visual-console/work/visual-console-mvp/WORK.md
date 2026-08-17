---
schema: "agora/work/v1"
id: "visual-console-mvp"
swarm: "studio-visual-console"
title: "Build the Agora Studio visual console"
state: "implementing"
operational-status: "active"
status-reason: "An external repository writer reviewed the implementation, staged the intended files, and can launch the governed commit."
status-by: "project:agent"
status-at: "2026-08-17T02:32:42.234208Z"
acceptance-criteria: {"visual-shell":"The root route serves an English, branded Agora Studio interface with the Agora logo and a quiet operations-console layout","project-selection":"A developer can enter and select a local Agora project path and receives clear loading, success and failure feedback","project-overview":"The selected project view presents its name, branch, active method, lifecycle counts and attention items from real Agora data","delivery-browser":"The interface exposes scannable views for actors, swarms, work and sessions using read-only Agora CLI results","responsive-accessible":"The interface remains usable on desktop and mobile with keyboard navigation, visible focus, semantic landmarks and reduced-motion support","read-only-safety":"Every backend query uses an explicit structured read-only allowlist and project browsing does not mutate the selected repository","verification":"Automated tests cover assets, API success and failure states, CLI argument boundaries and responsive UI contracts"}
satisfied-criteria: ["visual-shell","project-selection","project-overview","delivery-browser","responsive-accessible","read-only-safety","verification"]
required-artifacts: ["spec"]
child-work-refs: []
budget-limits: null
---

# Build the Agora Studio visual console

## Description

Serve a polished local operations console from the Python application so developers can select an Agora project and inspect its delivery state through governed, read-only CLI queries.

## Acceptance criteria

- [x] **visual-shell:** The root route serves an English, branded Agora Studio interface with the Agora logo and a quiet operations-console layout
- [x] **project-selection:** A developer can enter and select a local Agora project path and receives clear loading, success and failure feedback
- [x] **project-overview:** The selected project view presents its name, branch, active method, lifecycle counts and attention items from real Agora data
- [x] **delivery-browser:** The interface exposes scannable views for actors, swarms, work and sessions using read-only Agora CLI results
- [x] **responsive-accessible:** The interface remains usable on desktop and mobile with keyboard navigation, visible focus, semantic landmarks and reduced-motion support
- [x] **read-only-safety:** Every backend query uses an explicit structured read-only allowlist and project browsing does not mutate the selected repository
- [x] **verification:** Automated tests cover assets, API success and failure states, CLI argument boundaries and responsive UI contracts

## Required artifacts

- spec
