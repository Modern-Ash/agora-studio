# Implementation plan: Artifacts and Evidence view

## Approach

Extend the existing read-only server and static frontend with one new bounded
projection, mirroring the `lifecycle.py` precedent rather than introducing new
architecture.

## Backend

- `agora_studio/artifacts.py`: reads the selected work's durable
  `artifacts.md`, `evidence.md`, and `approvals.md` tables via the existing
  bounded `_regular_file` / `parse_front_matter` helpers imported from
  `lifecycle.py`. Required approval roles come from the work item's
  `approval_roles` field. Traceability to a session or tool run is derived
  only from exact durable `artifact.added` / `evidence.added` / `approval.added`
  Activity events matched by kind/type/role in durable order — never from
  timestamp proximity.
- `agora_studio/server.py`: new `GET /api/artifacts?swarm=&work=` route with
  the same error shape as `/api/lifecycle` (`project_required` 409, domain
  error 400/404, `SelectionError` 502).

## Frontend

- `static/artifacts-model.js`: pure selection helpers.
- `static/app.js`, `static/index.html`, `static/styles.css`: new `Artifacts`
  nav entry, work picker, three panels (artifacts/evidence/approvals), one
  shared detail region, reusing existing `.data-table`, `.event-button`,
  320px/44px/reduced-motion rules.

## Testing

- `tests/test_artifacts_evidence.py`: 18 tests covering listing, approvals
  (including zero-required), traceability (present/absent), path-traversal
  and symlink-escape rejection, argv-only/no-shell safety, and API states.

## Risks / follow-ups

- Real Activity fixtures in this project never carry session/tool-run ids on
  artifact/evidence/approval events, so traceability is exercised with
  synthetic fixtures in tests rather than live data.
