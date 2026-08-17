# Lifecycle and Specification Evolution Graph Implementation Plan

## Governed scope

- Work: `studio-lifecycle-graph/lifecycle-spec-evolution-graph`
- Role: `developer` (`project:agent`)
- Clarified specification: `repo://docs/specs/lifecycle-spec-evolution-graph.md`
- Baseline: the current uncommitted Agora Studio tree, including the selected-project overview and
  Activity timeline work already present in `agora_studio/` and `tests/`
- Delivery boundary: read-only local inspection only; no project, Agora, Git, network, or external
  system mutation

This plan implements the clarified specification without changing it. The implementation will add a
work-scoped lifecycle projection, a bounded native Git history/diff boundary, and a Lifecycle view
that coexists with the Activity view.

## Architecture and data flow

1. The browser selects an existing work record from the already loaded overview and requests a
   lifecycle projection using validated `swarm` and `work` slugs.
2. `ProjectStore` resolves the selected work and swarm from exact Agora CLI list results, then reads
   only the active Method Pack's canonical `METHOD.md`, `transitions/*.md`, and `gates/*.md` files.
3. A lifecycle projector validates bounded front matter and returns declared states, transitions,
   roles, gates, current state, and safe partial-data diagnostics. Filenames and prose never create
   topology.
4. The existing bounded Activity query supplies exact work events. Ordered `work.transitioned`
   records produce traversals and the state-at-time timeline; handoffs and failed or retried
   sessions become annotations. Actor, session, approval, artifact, evidence, and commit links are
   emitted only when durable identifiers match exactly.
5. The registered `spec` artifact is resolved from the selected work record. A separate Git reader
   verifies its canonical repository-relative path and uses fixed, direct `git` argv to project
   committed revisions, rename history, working-tree status, and an on-demand bounded textual diff.
6. The server returns normalized JSON only. The browser renders an SVG/DOM lifecycle graph plus an
   equivalent semantic table and one shared detail panel. It ignores stale responses by project and
   work request identity.

## Implementation sequence

### 1. Add validated lifecycle request and projection models

Files: `agora_studio/core.py`, new `agora_studio/lifecycle.py`

- Add a request model that accepts exactly one `swarm` and one `work` value, enforces the established
  scalar/control-character/length rules, and restricts identifiers to safe Agora slugs before any
  filesystem or subprocess access.
- Resolve the work, owning swarm, and method by exact identifiers from the structured Agora overview;
  reject mismatches and missing records without guessing.
- Add a bounded front-matter reader for the fields used by Agora Method, transition, and gate schemas.
  Require regular files below the canonical selected project, reject traversal and symbolic-link
  escapes, cap file count and bytes, and represent malformed or missing optional records as explicit
  partial-data diagnostics.
- Build stable projection types for method metadata, state nodes, transition edges, gate requirements,
  current state, traversals, annotations, source references, and availability flags. Preserve cycles,
  branches, repeated traversals, and source order.
- Derive the actual path only from exact `work.transitioned` Activity records for the requested scope.
  State-at-time is calculated from that ordered path; provenance relationships are never created from
  timestamp proximity.

### 2. Add a dedicated bounded Git read boundary

Files: new `agora_studio/git_history.py`, `agora_studio/core.py`

- Resolve the canonical specification exclusively from registered `spec` artifacts on the exact work
  item. Accept only a single safe `repo://` regular-file target inside the selected repository and
  return an unavailable/ambiguous state when zero or conflicting canonical targets exist.
- Introduce a Git runner with fixed read-only operations, `shell=False`, captured output, a short
  timeout, an explicit output-byte ceiling, and a minimal environment. Disable external diff and
  prompts. Every command uses `git -C <repo> ... -- <canonical-relative-spec-path>`.
- Read rename-aware commit history and bounded commit metadata, then obtain only the section/line
  summary needed for revision nodes. Detect the working-tree revision separately and label it
  uncommitted and unapproved.
- Add a second, on-demand revision-detail operation restricted to a revision identifier returned by
  the projection. Return escaped plain text, capped lines/bytes, truncation metadata, and changed
  headings; never return arbitrary blobs, HTML, unrestricted stderr, or commands.
- Treat unavailable Git, absent history, deleted files, malformed output, timeout, and output-limit
  exhaustion as typed partial failures that leave verified Method and Activity data usable.

### 3. Expose normalized read-only API routes

Files: `agora_studio/core.py`, `agora_studio/server.py`, `README.md`

- Add `GET /api/lifecycle?swarm=<slug>&work=<slug>` for the combined Method, Activity, traceability,
  and spec-revision projection.
- Add `GET /api/lifecycle/revision?...&revision=<opaque-id>` only if keeping revision details separate
  materially reduces the initial response; validate the opaque identifier against the server-created
  revision set before invoking Git.
- Preserve the selected-project requirement and return stable 400, 404, 409, and 502 error shapes for
  invalid requests, missing work, no project, and bounded read failures. Safe partial results remain
  HTTP 200 with per-layer availability and diagnostics.
- Keep POST handling limited to the existing project-selection endpoint. Add new static assets to the
  exact allowlist only; do not broaden path routing.
- Document the new read-only routes, query bounds, and offline test command.

### 4. Build a framework-free lifecycle model and layout

Files: new `agora_studio/static/lifecycle-model.js`, `agora_studio/static/index.html`,
`agora_studio/static/app.js`

- Add a Lifecycle navigation entry and work-selection control populated from the loaded work records.
  Opening Lifecycle without a work selection presents a clear selection action.
- Keep graph transformation and layout in a small pure JavaScript module. Compute deterministic ranks
  from the declared directed graph while preserving back edges/cycles and branching; do not key any
  behavior to `spec-driven` or to a fixed list of states.
- Render topology and overlays with DOM-created SVG/HTML only: declared nodes/edges, traversed edges,
  repeated traversal counts, current/initial/terminal/available/blocked distinctions, annotations,
  and spec-revision nodes. Use labels, shapes, icons, and line styles in addition to color.
- Implement layer toggles, fit, reset, keyboard traversal, work switching, and one consistent detail
  region. Preserve a selected item only while its stable identifier remains in the refreshed response.
- Provide a synchronized semantic table/list with the same states, transitions, revisions, and exact
  relationships. Announce selection and loading changes through the existing live region.
- Extend request serial tracking so stale lifecycle and revision responses cannot replace data for a
  newer project or work selection. On refresh failure retain the last successful graph and offer retry.

### 5. Apply responsive visual treatment and resilient states

Files: `agora_studio/static/styles.css`, `agora_studio/static/app.js`

- Give the graph the primary unframed work surface, with a restrained toolbar and a detail region that
  moves below it at narrow widths. Long identifiers wrap without changing control geometry.
- Add visible focus, 44px controls, non-color state cues, horizontal/vertical overflow containment,
  320px support, and 200% zoom behavior.
- Disable graph/detail motion under `prefers-reduced-motion: reduce` and retain the existing offline,
  local-asset-only policy.
- Implement explicit loading, empty, no-transitions, no-spec, no-history, partial-data, Git-unavailable,
  stale-response, and retry states, preserving whichever verified layers remain available.

### 6. Verify every clarified criterion and regressions

Files: new `tests/test_lifecycle_graph.py`, focused additions to existing tests as required

- Create temporary-project fixtures for linear, cyclic, and branching Method Packs. Prove topology is
  read from transition front matter, repeated actual traversals remain visible, and current state and
  gate blocking are accurate.
- Create local Git fixtures covering multiple spec commits, rename following, modified working tree,
  no history, deleted/missing spec, and unavailable Git. Assert exact argv, `shell=False`, timeout,
  minimal environment, output caps, and safe truncation.
- Exercise traversal, absolute/out-of-repository, symlink, non-regular, ambiguous artifact, invalid
  slug, unknown revision, malformed Method/Activity/Git, and arbitrary-file rejection before reads.
- Verify exact traceability joins and negative cases: close timestamps must not link unrelated actors,
  sessions, commits, approvals, artifacts, or evidence.
- Test API success, partial, empty, stale, retry, and safe failure shapes while snapshotting the selected
  project and Git status to prove all browsing is non-mutating.
- Test the pure browser model with Node fixtures, and assert keyboard controls, semantic equivalence,
  accessible names, non-color indicators, 320px/200% layout contracts, reduced motion, escaped text,
  and absence of `innerHTML`.
- Run `python3 -m unittest discover -s tests -v` offline. Record the exact commands and results in
  `docs/evidence/lifecycle-spec-evolution-graph-verification.md`, register it as `verification-report`,
  and add successful evidence only after every assertion passes.

## Acceptance traceability

| Criterion | Planned delivery | Verification focus |
| --- | --- | --- |
| `method-graph` | Steps 1 and 4 | Linear, cyclic, branching, malformed, and partial Method fixtures |
| `actual-path` | Steps 1 and 4 | Ordered durable transitions, retries, annotations, current state |
| `spec-versions` | Steps 2 and 4 | Commits, renames, working tree, no history, unavailable Git |
| `traceability` | Steps 1, 2, and 4 | Exact identifiers and explicit negative temporal-proximity cases |
| `interaction` | Steps 3 and 4 | Selection, layers, fit/reset, retained context, bounded detail |
| `safety` | Steps 1 through 3 | Canonical paths, strict argv, subprocess/output bounds, non-mutation |
| `states` | Steps 2 through 5 | Loading, empty, partial, unavailable, stale, failure, retry |
| `accessibility` | Steps 4 and 5 | Keyboard, table parity, focus, names, zoom, width, reduced motion |
| `tests` | Step 6 | Complete existing and new offline regression suite |

## Delivery checkpoints

1. Backend projection and Git-boundary tests pass before UI integration.
2. API contracts pass with success, partial, rejection, and non-mutation fixtures.
3. Browser model and accessibility contracts pass before visual polish.
4. The complete offline suite passes and the verification report is registered before transitioning
   from `implementing` to `verifying`.
5. Final acceptance remains with the assigned `spec-owner`; the developer will stop at that approval
   boundary after verification.

## Risks and controls

- **Custom Method diversity:** parse only declared schema fields and preserve unknown-but-valid graph
  shapes; never substitute a built-in lifecycle.
- **Provenance overclaiming:** separate chronological state derivation from exact identity joins and
  label unavailable relationships rather than infer them.
- **Git output growth:** cap commit count, subprocess bytes, diff lines, and returned summaries; expose
  truncation explicitly.
- **Symlink and traversal escape:** canonicalize repository and target, require containment and regular
  files, and revalidate before every Git read.
- **Dirty baseline overlap:** do not rewrite or discard existing Activity/console changes; make focused
  edits and review the governed repository status before any later commit operation.
- **Graph accessibility:** ship the semantic table as a first-class equivalent representation, not as
  a fallback generated after the visual graph.
