# Core 0.7 / Studio 0.4 verification

## Scope

This record covers Agora Studio's migration to the strengthened public contracts in Agora Core
0.7. It verifies only the Studio adapter, HTTP boundary, packaged browser, and their use of Core's
application services. It does not claim remote, multi-user, database, or general write support.

## Contract pair

- Studio: `0.4.0`
- Core requirement: `agora-framework>=0.7,<0.8`
- Work snapshot: `agora/application/work-control-projection/v2`
- Gate options: `gate-decision-options-projection/v2` and
  `gate-decision-option-summary/v2`
- Intent/confirmation command: `approve-gate-command/v3`
- Prepared action: `prepared-gate-decision/v2` with authorization v3
- Durable result: `gate-decision-projection/v2`

Studio rejects unknown schema versions. It validates the work snapshot token, nested DTO schemas
and identities, evidence references grouped by type, prepared authorization payload SHA-256,
precondition digest, freshness marker, authentication metadata, and the complete durable result.

## Governed browser flow

The browser chooses only an option returned by Core and sends an unsigned, digest-free intent.
Core canonicalizes the reason and evidence references and returns the exact command material. The
browser displays and can copy that material. Confirmation reuses the prepared values and opaque
precondition digest; editing returns to the intent phase. Studio does not calculate either digest,
does not read private keys, does not optimistically update lifecycle state, and does not retry stale
mutations.

After a durable response, the browser rereads and replaces a complete `WorkControlProjection v2`.
Project generation, work identity, request revision, refresh revision, and mutation revision prevent
older responses from replacing a newer selection. A stale response refreshes the projection and
requires explicit re-preparation.

## Automated evidence

The standard suite covers DTO/schema failures, HTTP translation and security, frontend models,
boundary scans, and real Core persistence. The separate Playwright suite exercises 22 scenarios in
real Chromium:

1. local project selection;
2. work detail navigation;
3. multiple Core options;
4. disabled blocked options;
5. approval preparation;
6. unsigned confirmation;
7. canonical payload display and copy;
8. opaque precondition digest display;
9. evidence references grouped by type;
10. approval persistence and Activity refresh;
11. durable rejection;
12. stale governed material and forced re-preparation;
13. rapid specification-revision switching with only the latest response applied;
14. latest project selection winning;
15. old work response cancellation on project change;
16. keyboard tab navigation;
17. focus after validation error;
18. no browser console or page errors;
19. durable text rendered without HTML interpretation;
20. Core authentication metadata for an Ed25519 actor;
21. detached-signature persistence without optimistic state;
22. operable mobile layout.

Commands used for final verification are recorded in the task handoff. CI reproduces the Chromium
suite with separately installed Core and Studio wheels, installs the Playwright-managed Chromium
binary, and uploads screenshots plus traces only when the E2E job fails.

## Final local verification

- `ruff format --check .`: 427 files formatted.
- `ruff check .`: passed.
- `python scripts/check_boundaries.py`: passed.
- `python -m unittest discover -s tests -v`: 34 tests passed.
- `python -m unittest discover -s e2e -v`: 22 Chromium tests passed.
- `python -m build`: built the Studio 0.4.0 wheel and source distribution.
- Clean Python 3.13 install: resolved `agora-studio==0.4.0` with the published
  `agora-framework==0.7.0`; CLI version and packaged browser assets passed smoke verification.
- Installed-wheel Chromium run: the same 22 scenarios passed using only the clean Studio and Core
  installations.
- Documentation link check: all local links across 16 Markdown files resolved.

No E2E scenario failed, so no screenshots, traces, or failure logs were retained.

## Deliberate limits

- Core 0.7 remains the sole lifecycle, authority, evidence, canonicalization, digest, transaction,
  and persistence authority.
- The `expires_at` field is currently null; Studio validates it but invents no clock policy.
- Loopback plus CSRF is an exposure boundary, not multi-user authentication.
- Markdown and Git remain the durable source of truth through Core adapters.
- Studio has no CLI fallback, direct `.agora/` access, database, remote mode, or automatic mutation
  retry.
- Core `v0.7.0` was published from merge
  `15bf97521da5a2f7bb0239561a6db107487a1411` on GitHub and PyPI before final Studio verification.
  CI builds its source wheel from that immutable tag and separately installs the minimum and latest
  compatible published wheels. Studio 0.4 can now be released without a provisional Core source pin.
