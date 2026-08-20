"use strict";

(function exposeControlModel(root) {
  const tabs = ["summary", "spec", "lifecycle", "artifacts", "evidence", "approvals", "activity"];

  function command(option, reason, authentication = null) {
    return {
      schema: "agora/application/approve-gate-command/v2",
      gate_id: option.gate_id,
      actor_id: option.actor_id,
      decision: option.decision,
      reason: reason.trim(),
      expected_state: option.expected_state,
      transition_target: option.transition_target,
      role_id: option.role_id,
      evidence_references: [...(option.evidence_references || [])],
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

  function preparationIssue(prepared, option, reason) {
    if (!prepared || !option) return "The prepared action is unavailable.";
    const expected = {
      gate_id: option.gate_id,
      actor_id: option.actor_id,
      decision: option.decision,
      expected_state: option.expected_state,
      transition_target: option.transition_target,
      role_id: option.role_id,
      reason: reason.trim(),
    };
    for (const [field, value] of Object.entries(expected)) {
      if (prepared[field] !== value) return "The action changed after preparation. Regenerate it.";
    }
    if (
      JSON.stringify(prepared.evidence_references || [])
      !== JSON.stringify(option.evidence_references || [])
    ) {
      return "The evidence references changed after preparation. Regenerate the action.";
    }
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
    revisionToken,
    tabs,
  };
}(globalThis));
