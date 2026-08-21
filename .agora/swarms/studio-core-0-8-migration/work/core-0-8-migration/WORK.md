---
schema: "agora/work/v1"
id: "core-0-8-migration"
swarm: "studio-core-0-8-migration"
title: "Migrate Agora Studio to Agora Core 0.8"
state: "completed"
operational-status: "active"
status-reason: null
status-by: null
status-at: null
acceptance-criteria: {"scope":"The human-reviewed specification resolves the Studio release identity and whether Core 0.8 budget amendment controls are included or explicitly deferred.","compatibility":"Studio requires agora-framework>=0.8,<0.9, rejects unsupported Core minors before mutation, and keeps Core independent from the selected project protocol version.","read-contracts":"Every consumed Core 0.8 read DTO and nested schema is validated exactly, including new TTL and content-digest fields and bounded handling of retryable concurrent durable reads.","gate-flow":"Gate preparation and confirmation use the exact Core 0.8 v4/v3 contracts, preserve prepared timestamps, expiry, actor fingerprint, and the selected evidence digest map, and never calculate authorization material in Studio.","operational-errors":"Application error v2 codes and safe structured details drive distinct retry, re-prepare, review, and mutation-stop behavior without parsing English messages.","evidence-integrity":"Studio presents Core-owned content-addressed evidence requirements and blockers without downloading evidence, hashing URIs, widening the selected evidence set, or recreating gate rules.","boundaries":"Production code uses only AgoraReadService and AgoraCommandService, never invokes Agora CLI or subprocesses, never reads or edits durable .agora records directly, and adds no database, authentication, remote, or multi-user behavior.","verification":"Automated unit, integration, security, frontend, Chromium, build, wheel, minimum-0.8 and latest-compatible-0.8 checks cover success, stale, expired, external-edit, signature, rollback, indeterminate, and schema incompatibility paths.","documentation":"Versioned compatibility, architecture, API behavior, recovery guidance, and verification evidence describe the shipped Core 0.8 contract without claiming unevidenced support."}
satisfied-criteria: ["scope","compatibility","read-contracts","gate-flow","operational-errors","evidence-integrity","boundaries","verification","documentation"]
criterion-statuses: {"scope":["satisfied"],"compatibility":["satisfied"],"read-contracts":["satisfied"],"gate-flow":["satisfied"],"operational-errors":["satisfied"],"evidence-integrity":["satisfied"],"boundaries":["satisfied"],"verification":["satisfied"],"documentation":["satisfied"]}
required-artifacts: ["spec"]
child-work-refs: []
budget-limits: null
---

# Migrate Agora Studio to Agora Core 0.8

## Description

Migrate Studio from the Core 0.7 application contracts to the supported Core 0.8 minor while preserving the local-first application-service boundary. Planning and implementation remain gated until human clarification.

## Acceptance criteria

- [x] **scope:** The human-reviewed specification resolves the Studio release identity and whether Core 0.8 budget amendment controls are included or explicitly deferred.; stages: satisfied
- [x] **compatibility:** Studio requires agora-framework>=0.8,<0.9, rejects unsupported Core minors before mutation, and keeps Core independent from the selected project protocol version.; stages: satisfied
- [x] **read-contracts:** Every consumed Core 0.8 read DTO and nested schema is validated exactly, including new TTL and content-digest fields and bounded handling of retryable concurrent durable reads.; stages: satisfied
- [x] **gate-flow:** Gate preparation and confirmation use the exact Core 0.8 v4/v3 contracts, preserve prepared timestamps, expiry, actor fingerprint, and the selected evidence digest map, and never calculate authorization material in Studio.; stages: satisfied
- [x] **operational-errors:** Application error v2 codes and safe structured details drive distinct retry, re-prepare, review, and mutation-stop behavior without parsing English messages.; stages: satisfied
- [x] **evidence-integrity:** Studio presents Core-owned content-addressed evidence requirements and blockers without downloading evidence, hashing URIs, widening the selected evidence set, or recreating gate rules.; stages: satisfied
- [x] **boundaries:** Production code uses only AgoraReadService and AgoraCommandService, never invokes Agora CLI or subprocesses, never reads or edits durable .agora records directly, and adds no database, authentication, remote, or multi-user behavior.; stages: satisfied
- [x] **verification:** Automated unit, integration, security, frontend, Chromium, build, wheel, minimum-0.8 and latest-compatible-0.8 checks cover success, stale, expired, external-edit, signature, rollback, indeterminate, and schema incompatibility paths.; stages: satisfied
- [x] **documentation:** Versioned compatibility, architecture, API behavior, recovery guidance, and verification evidence describe the shipped Core 0.8 contract without claiming unevidenced support.; stages: satisfied

## Required artifacts

- spec
