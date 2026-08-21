"use strict";

(function exposeControlModel(root) {
  const tabs = ["summary", "spec", "lifecycle", "artifacts", "evidence", "approvals", "activity"];

  function command(option, reason, authentication = null) {
    return {
      schema: "agora/application/approve-gate-command/v4",
      gate_id: option.gate_id,
      actor_id: option.actor_id,
      decision: option.decision,
      reason,
      expected_state: option.expected_state,
      transition_target: option.transition_target,
      role_id: option.role_id,
      evidence_references: [...(option.evidence_references || [])],
      precondition_digest: null,
      authentication,
    };
  }

  function preparedCommand(prepared, authentication = null) {
    return {
      schema: prepared.command_schema,
      gate_id: prepared.gate_id,
      actor_id: prepared.actor_id,
      decision: prepared.decision,
      reason: prepared.reason,
      expected_state: prepared.expected_state,
      transition_target: prepared.transition_target,
      role_id: prepared.role_id,
      evidence_references: [...prepared.evidence_references],
      evidence_content_sha256: prepared.evidence_content_sha256 ? { ...prepared.evidence_content_sha256 } : {},
      actor_fingerprint: prepared.actor_fingerprint || null,
      precondition_digest: prepared.precondition_digest,
      prepared_at: prepared.prepared_at,
      expires_at: prepared.expires_at || null,
      authentication,
    };
  }

  function authenticationIssue(prepared, authentication) {
    if (!prepared?.authentication_required) return "";
    if (!authentication?.algorithm?.trim()) return "Algorithm is required.";
    if (!/^[0-9a-f]{64}$/.test(authentication?.fingerprint?.trim() || "")) {
      return "Fingerprint must be a lowercase SHA-256 value.";
    }
    const signature = authentication?.signature?.trim() || "";
    if (!signature) return "Detached signature is required.";
    if (signature.length > 8192 || [...signature].some((character) => character.charCodeAt(0) < 32)) {
      return "Detached signature has an invalid shape.";
    }
    return "";
  }

  function preparationIssue(prepared, option) {
    if (!prepared || !option) return "The prepared action is unavailable.";
    const expected = {
      gate_id: option.gate_id,
      actor_id: option.actor_id,
      decision: option.decision,
      expected_state: option.expected_state,
      transition_target: option.transition_target,
      role_id: option.role_id,
    };
    for (const [field, value] of Object.entries(expected)) {
      if (prepared[field] !== value) return "The action changed after preparation. Regenerate it.";
    }
    if (!/^[0-9a-f]{64}$/.test(prepared.precondition_digest || "")) {
      return "The prepared precondition digest is invalid. Regenerate the action.";
    }
    if (!prepared.prepared_at) return "Missing prepared_at. Regenerate the action.";
    if (prepared.expires_at) {
      const exp = Date.parse(prepared.expires_at);
      if (!Number.isNaN(exp) && Date.now() >= exp) return "The prepared material has expired. Prepare again.";
    }
    const refs = prepared.evidence_references || [];
    const m = prepared.evidence_content_sha256 || {};
    if (Object.keys(m).length !== refs.length || !refs.every((r) => r in m)) return "Evidence digest map does not match selection.";
    return "";
  }

  function nextTab(current, key) {
    const index = tabs.indexOf(current);
    if (index < 0) return tabs[0];
    if (key === "ArrowRight") return tabs[(index + 1) % tabs.length];
    if (key === "ArrowLeft") return tabs[(index - 1 + tabs.length) % tabs.length];
    if (key === "Home") return tabs[0];
    if (key === "End") return tabs.at(-1);
    return current;
  }

  function revisionToken(project, work, revision) {
    return JSON.stringify([project, work, revision]);
  }

  root.ControlModel = {
    authenticationIssue,
    command,
    nextTab,
    preparationIssue,
    preparedCommand,
    revisionToken,
    tabs,
  };
}(globalThis));
