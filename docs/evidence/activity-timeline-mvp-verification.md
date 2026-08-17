# Activity Timeline MVP verification

- Work: `studio-activity-timeline/activity-timeline-mvp`
- Actor: `project:agent` (`developer`)
- Result: automated verification succeeded
- Date: 2026-08-17

## Verified implementation

- `GET /api/activity` requires a selected project and validates the six supported filters plus a
  bounded `limit` before invoking the Agora CLI.
- The CLI boundary uses the exact `agora --project <path> activity list ...` argv form with
  `shell=False`, captured output, a timeout, JSON shape validation, and safe failure messages.
- The Activity view renders stable chronological ordering, six local AND filters, bounded-history
  disclosure, exact durable source links, exact work/session relationships, selection retention,
  explicit loading/empty/no-match/failure states, and stale-response protection.
- The UI includes keyboard-operable event controls, visible focus, live announcements, responsive
  detail placement, long-value wrapping, 44px controls, and reduced-motion handling.

## Automated evidence

`python -m unittest -v` completed successfully: 28 tests passed, including the Activity boundary,
API, ordering, filters, traceability, safety, non-mutation, state, asset, accessibility, and existing
foundation/visual-console regression suites.

`python -m compileall -q agora_studio tests` completed successfully.

`node --check agora_studio/static/activity-model.js` and
`node --check agora_studio/static/app.js` completed successfully.

`agora activity list --limit 3` returned the documented structured event shape for the active
project, including nullable actor and governed scope fields.

## Environment limitation

The managed execution sandbox denied opening a loopback listener with `EPERM`, including an
ephemeral port. Browser-based human verification was therefore not claimed here and remains part of
the Spec Owner's review gate. No deployment, mutation endpoint, Activity rebuild, or network
dependency was introduced.
