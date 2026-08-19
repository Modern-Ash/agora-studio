# Agora Studio Artifacts and Evidence View

## Status and ownership

- Active swarm: `studio-artifacts-evidence`
- Active work item: `artifacts-evidence-mvp`
- Method: `spec-driven`
- Specification owner: `project:owner`
- Developer: `project:agent`
- Status: drafting; registered as the work item's canonical `spec` artifact

## Clarification record

- The registered specification URI is `repo://docs/specs/artifacts-evidence-mvp.md`.
- The feature is a read-only extension of the existing selected-project and selected-work
  experience, following the same boundary pattern as `activity-timeline-mvp` and
  `lifecycle-spec-evolution-graph`.
- Agora's durable `artifacts.md`, `evidence.md`, and `approvals.md` records for a work item are the
  authority for what is shown; nothing is inferred from files, sessions, or temporal proximity.
- Delivery planning and verification evidence belong to later lifecycle phases and do not alter the
  clarified product, safety, accessibility, or verification requirements below.

## Objective

Add a read-only view to Agora Studio that lets a developer browse the artifacts, evidence, and
approvals durably recorded against a selected work item, so they can see what was produced, whether
it passed verification, and whether required approvals were granted, without exposing provider
reasoning or mutating the selected project.

## User outcome

A developer selects a project and work item, opens its Artifacts view, and can:

1. see every registered artifact with its kind, URI, producing actor, and timestamp;
2. see every evidence record with its result, the criterion or artifact it relates to, and its
   source;
3. see each required approval role and whether it has been satisfied;
4. select an artifact or evidence record to see linked traceability (originating session or tool
   run) when Agora records establish that relationship; and
5. do all of this without triggering any mutation of the selected project.

## Data model

- Resolve the selected work's swarm and work slug using reviewed Agora data, exactly as the
  Activity and Lifecycle views already do.
- Read only the work item's durable `artifacts.md`, `evidence.md`, and `approvals.md` records
  through the existing bounded Agora CLI read boundary (or the library equivalent already used by
  the server), never by scanning the filesystem directly.
- Do not follow artifact `repo://` URIs to read file contents; display the URI as a reference only.
- Do not infer a relationship between an artifact, evidence record, session, or tool run unless a
  durable identifier makes that relationship explicit.

## Interaction and layout

- Add an `Artifacts` view or an equally clear entry point from a selected work; do not replace
  Activity or Lifecycle.
- Present artifacts, evidence, and approvals as three related, clearly labeled sections or panels
  reachable from one view.
- Selecting an artifact or evidence record opens one consistent detail region showing its full
  identifiers and, when present, its linked session or tool run reference.
- Preserve selection while related data remains available; clear it explicitly when project or work
  changes.
- Long URIs, identifiers, and summaries wrap without resizing controls or obscuring adjacent
  content.

## API and read-only boundaries

Extend the existing Python standard-library server and explicit boundary pattern.

- Add one bounded API projection for a selected work's artifacts, evidence, and approvals, or one
  combined projection if that keeps validation clearer.
- Accept only a selected canonical project plus validated swarm and work slugs.
- Use only reviewed, already-allowlisted Agora CLI read operations; add no new subprocess surface
  beyond the existing bounded pattern.
- Return normalized JSON projections. Never return raw commands, unrestricted stderr, environment
  values, private keys, credentials, provider reasoning, complete session transcripts, or arbitrary
  filesystem content.
- Do not add mutation endpoints, background watchers, WebSockets, polling, deployment behavior,
  databases, remote assets, or network dependencies.

## States and resilience

- **Loading:** retain navigation and identify that artifacts/evidence data is loading.
- **No work selected:** present a clear work-selection action.
- **Empty:** distinguish "no artifacts registered" from "no evidence recorded" from "no approval
  roles required" explicitly; do not conflate them into one generic empty state.
- **Query failure:** retain the last successful data, show a safe reason, and offer retry.
- **Stale response:** ignore results belonging to a previous project or work selection.

## Accessibility and responsive behavior

- Make every artifact, evidence, and approval row reachable by keyboard in a predictable order.
- Provide visible focus, descriptive accessible names, and announcements for selection changes.
- Never use color as the only indicator of evidence result or approval satisfaction.
- Support 320px width, 200% zoom, 44px controls, long-value wrapping, and logical detail placement.
- Disable non-essential motion under `prefers-reduced-motion: reduce`.

## Acceptance criteria and verification

| Criterion | Required verification |
| --- | --- |
| `listing` | Tests prove artifacts and evidence render with kind, status/result, and linked criterion from durable records. |
| `approvals` | Tests prove required approval roles and their satisfaction state render accurately, including when no approvals are required. |
| `traceability` | Tests prove a selected artifact or evidence record links to its originating session or tool run only when a durable identifier establishes that relationship. |
| `safety` | Boundary tests assert only reviewed read-only Agora CLI operations are used and that no credentials, private keys, or provider chain-of-thought are exposed. |
| `states` | Tests cover loading, empty, invalid-project, and query-failure states. |
| `responsive-accessible` | Tests cover keyboard navigation, visible focus, accessible names, non-color indicators, reduced motion, zoom, and narrow layout. |
| `tests` | The full offline suite passes without network access and includes existing foundation, visual console, Activity, and Lifecycle regression suites. |

## Required artifacts

- `spec`
- `verification-report`

## Human verification

1. Compare rendered artifacts and evidence with `agora artifact list` / durable `artifacts.md` and
   `evidence.md` records for the selected work.
2. Compare rendered approval state with the work item's `approval_roles` and `approvals.md`.
3. Confirm traceability links only appear where a durable session or tool-run identifier exists.
4. Inspect empty, invalid-project, and query-failure fixtures.
5. Navigate the complete experience by keyboard.
6. Repeat at desktop, mobile width, 200% zoom, and reduced motion.
7. Confirm browsing leaves every Agora durable record unchanged.

## Non-goals

- Registering, editing, or approving artifacts, evidence, or approvals from the view.
- Reading or rendering the contents of artifact files referenced by `repo://` URIs.
- Mutating work, actors, swarms, sessions, tools, Method Packs, Git history, commits, or branches.
- Inferring authorship, causality, or relationships when durable identifiers do not establish them.
- Rendering raw provider output, chain-of-thought, credentials, private keys, environment variables,
  or arbitrary local files.
- Cross-project aggregation, live collaboration, notifications, analytics, deployment, remote fonts,
  or new frontend package and network dependencies.
