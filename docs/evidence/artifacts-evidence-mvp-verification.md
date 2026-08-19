# Verification report: Artifacts and Evidence view

## Automated verification

Full offline suite: `python3 -m unittest discover -s tests -v`

```
Ran 54 tests in 0.158s

OK
```

All pre-existing foundation, visual-console, activity, and lifecycle
regression tests pass unchanged. 18 new tests in
`tests/test_artifacts_evidence.py` cover:

- listing (artifacts, evidence, kind/status/linked references)
- approvals, including the zero-required-roles case
- traceability, both present (exact durable session/tool-run id) and absent
  (no fabricated links for mismatched or missing event types)
- safety: path-traversal rejection, symbolic-link-escape rejection,
  non-`repo://` URIs treated as display-only, argv-only subprocess calls with
  no `shell=True`
- API states: `project_required` (409), invalid query (400), not-found (404),
  success (200), and upstream CLI failure (502)
- static accessibility/responsive contract checks (keyboard reachability,
  non-color indicators, 320px/44px/reduced-motion rules present)

## Human verification checklist (per spec)

1. Compared rendered artifacts/evidence against `agora work show` and the
   durable `artifacts.md` / `evidence.md` tables for `studio-lifecycle-graph`
   / `lifecycle-spec-evolution-graph` (populated fixture) and
   `studio-artifacts-evidence` / `artifacts-evidence-mvp` (near-empty
   fixture) — matched.
2. Compared rendered approval state against `approval_roles` and
   `approvals.md` — matched, including the zero-required-role case.
3. Confirmed traceability links only render when a durable session or
   tool-run id is present; this project's real Activity fixtures currently
   carry no such ids on artifact/evidence/approval events, so no live link is
   shown anywhere today — expected and correct per the spec's exact-identifier
   requirement.
4. Inspected empty, invalid-project, and query-failure fixtures via the new
   automated tests.
5. Confirmed the view never mutates Git or any Agora durable record (read-only
   `_regular_file` boundary, no new CLI operations beyond existing allowlisted
   reads).

## Result

success
