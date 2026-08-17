# Agora Studio Governed Activity Timeline MVP

## Status and ownership

- Swarm: `studio-activity-timeline`
- Work item: `activity-timeline-mvp`
- Method: `spec-driven`
- Specification owner: `project:specification-agent`
- Status: clarified for developer planning

## Objective

Add a read-only Activity view to Agora Studio that turns Agora's durable Activity Ledger into a
chronological, inspectable account of what humans, agents, swarms, sessions, and governed tools did.
The view must preserve the durable record's attribution and source references, make recorded context
and outcomes understandable without exposing provider reasoning, and never mutate the selected
project.

## User outcome

A developer selects a local Agora project, opens Activity, and can:

1. scan durable events from oldest to newest;
2. identify each event's type, timestamp, actor, swarm, work, session, and tool-run scope;
3. narrow the list by any of those governed dimensions;
4. select an event to inspect its recorded summary, durable source, and related artifact, evidence,
   or session summaries when the loaded records provide them; and
5. recover from loading, empty, invalid-project, and query-failure states without losing the ability
   to select or refresh a project.

## Durable data contract

The Activity Ledger and the structured output of `agora activity list` are authoritative. Studio
must not parse provider transcripts or derive hidden reasoning from session output. Every event is
represented using the fields returned by that reviewed read operation:

| Field | Meaning |
| --- | --- |
| `timestamp` | ISO 8601 event time used for ordering and display |
| `type` | Durable event type, such as `work.transitioned` |
| `summary` | Recorded event facts shown verbatim as plain text |
| `actor` | Actor reference when the durable event attributes one |
| `swarm_id` | Related swarm identifier when present |
| `work_id` | Related work identifier when present |
| `session_id` | Related session identifier when present |
| `tool_run_id` | Related governed Tool Run identifier when present |
| `source` | Durable `repo://` source reference |
| `path` | CLI-reported ledger path; diagnostic only and never an instruction to read a path |

Absent optional fields remain visibly `Unattributed` or `Not recorded` where their absence matters;
the client must not invent actor identity, intent, or causal explanation.

## Information architecture and interaction

### Navigation and layout

- Add `Activity` to the existing project navigation without changing the current default Overview
  view.
- The Activity view uses the established compact, neutral Studio visual language, typography,
  spacing, coral/teal accents, and local-only assets.
- A filter toolbar precedes a single vertical timeline. On wide screens, selecting an event opens a
  persistent detail region beside the timeline. On narrow screens, details follow the selected row
  in document order without horizontal viewport overflow.
- The result count and active-filter count remain visible. When the CLI limit is reached, disclose
  that the view is a bounded recent slice rather than implying that it is the complete history.

### Timeline behavior

- Render events in ascending timestamp order (oldest to newest). For equal timestamps, preserve the
  CLI order so rerenders are stable.
- Each event row is one keyboard-operable button or link-like control with visible focus. It shows
  local-formatted time with the exact ISO timestamp available in accessible text or a tooltip, event
  type, recorded summary, actor, and only the governed scope identifiers that are present.
- Event-type treatment may vary by stable family (`project`, `actor`, `swarm`, `work`, `session`,
  `tool`, `artifact`, `evidence`, `approval`, or other), but color is never the only distinction.
- Selecting an event marks it with `aria-current` and updates a labeled detail region without
  moving focus unexpectedly. Refresh preserves the selected event only if the same stable field set
  is still present; otherwise it clears the detail region and announces the change.

### Filters

- Provide six independently usable filters: event type, actor, swarm, work, session, and tool run.
- A missing or `All` value means no restriction for that dimension. Multiple active dimensions use
  AND semantics.
- Options come from the loaded structured records, are sorted predictably, and expose full values
  even when their visual labels truncate.
- `Clear filters` resets all six dimensions and restores the chronological loaded result set.
- Changing a filter updates the result count and live status. A zero-result filter state retains the
  controls and offers `Clear filters`; it is distinct from an empty Activity Ledger.

### Event detail and traceability

- The detail region repeats the exact timestamp, type, actor, summary, and every recorded governed
  scope identifier.
- Present `source` as the durable source reference in a real link whose `href` is the returned
  `repo://` URI. Do not dereference arbitrary paths in Studio, construct `file://` URLs, or expose
  source-file contents through a new endpoint.
- Related summaries are derived only from already loaded structured data:
  - for a work-scoped event, show loaded `artifact.added` and `evidence.added` events with the same
    swarm and work identifiers;
  - for a session-scoped event, show the matching structured session summary from the already
    loaded overview snapshot when available;
  - when no related summary is available, say so without treating it as an error.
- Relationships are exact identifier matches. Studio must not infer causality, ownership, or
  reasoning from temporal proximity.

## Backend and API contract

Keep the current Python standard-library server and `AgoraCliBoundary` pattern.

### Read-only CLI boundary

Add one explicit boundary operation for `activity list`. It must execute an argv sequence with
captured output, `shell=False` behavior, the existing bounded timeout, and JSON validation. The only
permitted arguments are the reviewed CLI flags below:

| API input | Agora argv |
| --- | --- |
| `type` | `--type <value>` |
| `actor` | `--actor <value>` |
| `swarm` | `--swarm <value>` |
| `work` | `--work <value>` |
| `session` | `--session <value>` |
| `tool_run` | `--tool-run <value>` |
| `limit` | `--limit <integer>` |

The server must reject unknown query keys, repeated scalar values, control characters, and values
longer than 200 characters. It must parse `limit` as an integer from 1 through 500; the default is
500. Filter values are passed as individual argv elements and never interpolated into a shell
command. The result must be a JSON array whose items contain string or null values for the documented
event fields. Invalid JSON or an invalid result shape is a bounded query failure.

No Activity endpoint may invoke `activity rebuild`, any lifecycle mutation, arbitrary executable,
or a user-supplied Agora subcommand. The endpoint must not read `path`, `source`, session transcripts,
credentials, authentication records, private keys, or provider chain-of-thought from the filesystem.

### HTTP response

Add `GET /api/activity`:

- Without a selected project, return `409` and the existing structured `project_required` shape.
- On success, return `200` with `selection`, normalized `filters`, `events`, and `meta` containing
  `count`, `limit`, and `limit_reached`.
- Preserve the selected project when the Activity query fails. Return `400` with
  `invalid_activity_query` for rejected query input, and `502` with `activity_query_failed`, safe
  `operation`, and safe `reason` fields for CLI failures.
- Never include a Python traceback, CLI command line, environment value, raw stderr that may contain
  secrets, or filesystem contents in the response. Diagnostics remain concise and actionable.

The browser may apply the six filters locally to the bounded response for instant interaction. If
it requests server-side filters, the query must follow the same contract and AND semantics.

## States and resilience

- **Loading:** show timeline skeleton rows or a compact progress state, mark the Activity region
  busy, and prevent duplicate refreshes while leaving navigation usable.
- **Empty ledger:** explain that no durable activity has been recorded for the selected project and
  keep Refresh and project selection available.
- **No filter matches:** state that the loaded activity has no matching events and offer Clear
  filters.
- **Invalid project / no selection:** retain the existing project selection call to action and do
  not issue an Activity request before selection.
- **Query failure:** show the safe API reason, retain the last successfully rendered timeline when
  one exists, and offer Retry. A failed request must not clear the valid project selection.
- **Stale response:** ignore an older response that completes after a newer project selection or
  Activity request.

## Accessibility and responsive requirements

- Preserve the existing skip link, landmarks, single page `h1`, visible focus, and live status
  region.
- Every filter has a visible label; the result count and errors are announced without stealing
  focus. Event controls have an accessible name containing type, exact time, and actor state.
- The detail region has a programmatic heading and logical reading order. Long IDs and source URIs
  wrap safely and expose their full value.
- All actions are reachable and operable by keyboard at 320px width and 200% zoom. Touch targets
  remain at least 44 by 44 CSS pixels.
- Motion is limited to short state transitions and disabled under
  `prefers-reduced-motion: reduce`.

## Acceptance and automated verification mapping

| Criterion | Required verification |
| --- | --- |
| `timeline` | Fixture-driven tests prove ascending timestamp order, stable tie order, visible type/time/actor/scope, and bounded-history disclosure |
| `filters` | Tests cover all six filters independently, AND semantics, clear behavior, zero matches, and absence of lifecycle mutations |
| `traceability` | Tests cover source-link rendering, exact work/session matching, artifact/evidence/session summaries, and explicit missing-related state |
| `safety` | Boundary tests assert exact argv, `shell=False` behavior, timeout, limit bounds, rejected keys/values, JSON shape validation, and no `rebuild` or mutation path |
| `states` | API and rendering tests cover loading, empty, no selection, invalid query, CLI failure, retry, retained last success, and stale responses |
| `responsive-accessible` | Static and behavior tests cover landmarks, labels, `aria-current`, live status, keyboard operation, wrapping, 320px layout, visible focus, and reduced motion |
| `tests` | The full offline suite passes and includes success, empty, filtered, invalid-project, invalid-query, CLI-failure, and non-mutation cases |

For non-mutation verification, snapshot the selected fixture project's tracked and untracked state
before and after Activity API and UI flows. No test may rely on network access, remote assets, or a
locally installed frontend package.

## Human verification

1. Start Studio and select a project with human, AI-agent, swarm, work, session, artifact, evidence,
   approval, and Tool Run activity.
2. Compare the rendered chronology and each filter with `agora activity list` using the same limit
   and filters.
3. Select representative events and confirm the displayed facts and `repo://` source match the CLI
   output; confirm related summaries use exact identifiers.
4. Exercise loading, no matches, empty fixture, no-selection, invalid-query, and simulated CLI
   failure states at desktop and mobile sizes.
5. Navigate and filter using only the keyboard, verify visible focus and announcements, then repeat
   with reduced motion enabled.
6. Confirm the selected project's Git and Agora durable state are unchanged after browsing.

## Non-goals

- Rebuilding the Activity Ledger, writing events, editing project records, approving, transitioning,
  launching, retrying, or cancelling governed work.
- Displaying raw session process output, prompts, model chain-of-thought, authentication material,
  environment variables, private keys, or arbitrary local files.
- Full-text search, saved filters, export, pagination beyond the CLI's bounded list operation, live
  filesystem watching, WebSockets, polling, notifications, analytics, or cross-project aggregation.
- Installing a frontend framework, package manager, database, remote font, telemetry client, or
  network dependency.
