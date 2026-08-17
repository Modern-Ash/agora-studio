# Agora Studio Visual Console MVP

## Status

Clarified for implementation.

## Objective

Provide a polished, local, read-only operations console for developers working with Agora. The
console must make the durable state of an existing Agora project understandable without requiring
the user to inspect Markdown files or invoke several CLI commands manually.

## Audience and design direction

The primary user is a developer running Agora Studio beside an IDE and terminal. The interface is
an operational tool, not a marketing page. It should feel calm, precise, and information-dense,
using neutral surfaces, strong typography, restrained coral and teal accents, and the Agora logo as
the primary brand signal. Panels use compact radii of 8px or less. Decorative gradients, floating
orbs, oversized hero text, and nested cards are out of scope.

## User flow

1. The user starts Studio with `python3 -m agora_studio --port 7357`.
2. The root URL opens the visual console.
3. With no project selected, the main view asks for an absolute local path and explains validation
   errors next to the form.
4. After selection, Studio loads a project overview using only allowlisted Agora CLI reads.
5. The user moves among Overview, Actors, Swarms, Work, and Sessions without a page reload.
6. Refresh reloads the selected project's durable state. Studio never offers lifecycle mutations.

## Information architecture

### Application shell

- A compact sidebar contains the Agora logo, product name, navigation, and selected-project label.
- A top bar contains the current view title, read-only status, and a refresh icon button.
- The main region contains one active view and an accessible live status region.
- On narrow screens the sidebar becomes a compact top navigation and all tables become readable
  stacked rows without horizontal viewport overflow.

### Empty selection

- Show a concise project-path form as the primary task.
- Preserve the entered value after a failed selection.
- Disable duplicate submissions while validation is running.
- Show actionable error text from the structured API response without exposing a traceback.

### Overview

- Show project name, Git branch, default method, and integration.
- Show lifecycle counts for actors, swarms, work, sessions, and tool runs.
- Show swarm and work state distributions.
- Show attention queues for active, blocked, unfinished, and failed items.
- Empty attention queues must read as healthy states rather than blank panels.

### Actors, swarms, work, and sessions

- Actors: name, reference, kind, capabilities, and authentication state.
- Swarms: identifier, method, status, branch, objective, and role assignments.
- Work: swarm/work reference, title, lifecycle state, operational status, criteria progress, and
  required artifact/evidence readiness.
- Sessions: identifier, actor, swarm/work context, status, and timestamps when present.
- Use semantic tables on wide screens and labeled stacked rows on mobile.
- Long identifiers wrap or truncate with an accessible full-value title; they never resize the
  surrounding layout.

## Backend and API contract

Keep the server in Python and use only the standard library. Static assets live under
`agora_studio/static/`.

- `GET /` returns the HTML application shell with `text/html; charset=utf-8`.
- `GET /assets/<allowlisted-file>` serves only known local assets with correct content types and
  traversal protection.
- `POST /api/projects/select` retains the existing selection contract.
- `GET /api/project` retains the existing selection contract.
- `GET /api/overview` returns `409` with a structured `project_required` error when no project is
  selected. Once selected, it returns `selection`, `status`, `actors`, `swarms`, `work`, and
  `sessions`.

Extend `AgoraCliBoundary` with explicit structured operations only:

| Operation | Exact Agora arguments |
| --- | --- |
| `status` | `status` |
| `actors` | `actor list` |
| `swarms` | `swarm list` |
| `work` | `work list` |
| `sessions` | `session list` |

Every invocation remains an argv sequence with `shell=False` behavior, a bounded timeout, captured
output, and JSON validation. No endpoint may execute a user-provided command or lifecycle mutation.
If one overview query fails, return a structured error and keep the last valid project selection.

## Frontend implementation

- Use semantic HTML, authored CSS, and a small dependency-free JavaScript module.
- Keep all display text in English.
- Use CSS custom properties for palette, spacing, borders, typography, and motion.
- Use familiar symbols or compact inline icons for navigation and refresh controls; all icon-only
  controls require accessible names and tooltips.
- Animate only meaningful state changes and short view transitions. Respect
  `prefers-reduced-motion: reduce`.
- Use no CDN, remote font, telemetry, external image, or build-time dependency.
- Include the existing Agora logo as a local optimized bitmap asset.
- JavaScript must render API values as text, never inject provider output as HTML.

## Accessibility and resilience

- Provide one `h1`, logical headings, landmarks, a skip link, visible focus, and keyboard-operable
  navigation.
- Meet WCAG AA contrast for text and controls.
- Associate the project path label, help, and error text with the input.
- Loading and error updates use an `aria-live` region without stealing focus.
- The interface remains legible at 320px width and at 200% browser zoom.
- A backend failure must leave navigation and project re-selection available.

## Acceptance mapping

| Criterion | Verification |
| --- | --- |
| `visual-shell` | Root and asset handler tests plus inspection of branded shell semantics |
| `project-selection` | UI contract tests and selection API success/failure tests |
| `project-overview` | Aggregation tests using deterministic CLI fixtures |
| `delivery-browser` | Fixture-driven rendering contracts for all four collections |
| `responsive-accessible` | Static assertions for landmarks, labels, focus, breakpoints, and reduced motion |
| `read-only-safety` | Exact argv tests, operation rejection tests, and repository snapshot comparison |
| `verification` | Full offline unit suite covering success and failure paths |

## Human verification

1. Start Studio and open it at desktop and mobile viewport sizes.
2. Exercise invalid and valid project selection.
3. Compare the visual counts and records with `agora status`, `agora actor list`, `agora swarm list`,
   `agora work list`, and `agora session list` for the same project.
4. Confirm keyboard navigation, visible focus, refresh feedback, and reduced motion.
5. Confirm `git status --porcelain` for the selected project does not change after browsing.

## Non-goals

- Editing Agora files or executing governed transitions.
- Authentication, remote access, multi-user state, or persistence of recent project paths.
- Charts, analytics history, live filesystem watching, WebSockets, or background polling.
- A frontend framework, package manager, or asset build pipeline.
