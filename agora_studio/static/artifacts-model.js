"use strict";

(function exposeArtifactsModel(root) {
  function itemKey(kind, item) {
    return `${kind}:${item.id}`;
  }

  function selectionExists(projection, key) {
    if (!key || !projection) return false;
    const candidates = [
      ...(projection.artifacts || []).map((item) => itemKey("artifact", item)),
      ...(projection.evidence || []).map((item) => itemKey("evidence", item)),
      ...((projection.approvals && projection.approvals.records) || []).map((item) => itemKey("approval", item)),
    ];
    return candidates.includes(key);
  }

  function findSelected(projection, selected) {
    if (!selected) return null;
    const [kind, id] = selected.split(/:(.*)/s);
    const collections = {
      artifact: projection.artifacts || [],
      evidence: projection.evidence || [],
      approval: (projection.approvals && projection.approvals.records) || [],
    };
    const item = (collections[kind] || []).find((record) => record.id === id);
    return item ? { kind, item } : null;
  }

  function hasTraceability(item) {
    return Boolean(item && item.traceability && (item.traceability.session_id || item.traceability.tool_run_id));
  }

  root.ArtifactsModel = { itemKey, selectionExists, findSelected, hasTraceability };
}(globalThis));
