# Agora Studio visual console MVP verification

## Automated command

```text
python3 -m unittest discover -s tests -v
```

Result: 20 tests passed with no failures. The suite is offline and uses only the Python standard
library, including direct validation of the PNG signature and IHDR metadata.

Additional executable checks:

```text
node --check agora_studio/static/app.js
git diff --check
```

Both completed successfully.

## Live HTTP verification

The application was started on `127.0.0.1:7357` outside the restricted agent sandbox. `GET /`
returned `200` with `text/html`, `POST /api/projects/select` selected this repository, and
`GET /api/overview` returned the real project status plus actors, swarms, work, and sessions. A
before-and-after comparison of `git status --porcelain=v1` was identical after the overview read.

## Acceptance coverage

| Criterion | Reproducible evidence |
| --- | --- |
| `visual-shell` | Static route tests verify the root HTML and exact content types for the local CSS, JavaScript, and RGBA PNG mark. Source contracts assert one `h1`, semantic landmarks, and no remote assets. |
| `project-selection` | Existing selection tests cover valid, invalid, repeated, and rejected selections while preserving the last valid project. The frontend associates help and error messaging with the path input and disables duplicate submissions while loading. |
| `project-overview` | Fixture-driven API tests assert the project identity, branch, default method, integration, lifecycle counts, distributions, and attention payload returned by `/api/overview`. |
| `delivery-browser` | The overview fixture verifies actors, swarms, work, and sessions are aggregated. The interface renders each collection as a semantic table with mobile row labels. |
| `responsive-accessible` | Static contracts assert the skip link, landmarks, live region, associated form labeling, visible focus, 760px and 480px breakpoints, and reduced-motion media query. |
| `read-only-safety` | Tests assert the exact five argument vectors, reject an unlisted transition before process creation, reject asset traversal, and preserve selection after a failed overview read. A live read against this project returned all five collections successfully. |
| `verification` | The full 20-test suite covers assets, API success and failure, operation-specific JSON shapes, exact CLI boundaries, selection resilience, and responsive UI contracts. |

## Runtime read result

An actual `AgoraCliBoundary` snapshot against the repository completed successfully with project
`agora-studio`, 4 actors, 3 swarms, 3 work items, and 24 sessions. The snapshot contained exactly
`selection`, `status`, `actors`, `swarms`, `work`, and `sessions`.

## Environment limitation

The implementation agent's sandbox denied socket creation with `EPERM`; the parent session later
completed the live HTTP checks above. No in-app or external browser was connected, so screenshot-based
human visual verification was not available. The interface was checked through deterministic source,
asset, API, syntax, accessibility, responsive-contract, and live HTTP tests. Human visual acceptance
remains the Spec Owner's later approval boundary and is not claimed by this developer evidence.
