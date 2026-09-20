"use strict";

(function exposeAiSdlcModel(root) {
  const CONTENT_SECTIONS = ["lifecycle", "clarifications", "separation", "provenance", "metrics"];
  const CONTEXT_SECTIONS = ["flavor", "profiles"];
  const MAX_LABEL = 80;

  function isPlainObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  // Presentation is a non-authoritative hint: only known section names are reordered, in the hinted
  // order, and any omitted section is still shown afterwards.
  function orderedSections(projection) {
    const hint = Array.isArray(projection?.presentation?.section_order) ? projection.presentation.section_order : [];
    const seen = new Set();
    const ordered = [];
    hint.forEach((name) => {
      if (CONTENT_SECTIONS.includes(name) && !seen.has(name)) {
        seen.add(name);
        ordered.push(name);
      }
    });
    CONTENT_SECTIONS.forEach((name) => {
      if (!seen.has(name)) ordered.push(name);
    });
    return ordered;
  }

  function label(projection, id) {
    const hint = projection?.presentation?.labels?.[id];
    if (typeof hint === "string" && hint.trim() && hint.length <= MAX_LABEL) return hint;
    return String(id);
  }

  function section(projection, name) {
    const envelope = projection?.[name];
    if (!isPlainObject(envelope)) return { status: "unavailable", reason: { code: "projection.invalid", message: "Section is not readable." } };
    return envelope;
  }

  function isAvailable(envelope) {
    return envelope?.status === "available" && envelope.value !== undefined && envelope.value !== null;
  }

  // Lifecycle ids are open strings. The treatment depends only on structural flags, never on an id.
  function stateFlags(lifecycle, state) {
    return {
      current: state.id === lifecycle.current_state,
      initial: state.initial === true,
      terminal: state.terminal === true || state.id === lifecycle.terminal_state,
    };
  }

  function transitionsFrom(lifecycle, id) {
    return (Array.isArray(lifecycle.transitions) ? lifecycle.transitions : []).filter((item) => item.source === id);
  }

  // Blocked decisions are shown as blocked; nothing is ever softened into a positive treatment.
  function decisionTone(decision) {
    return String(decision).toLowerCase() === "blocked" ? "danger" : "neutral";
  }

  function provenanceField(field) {
    if (!isPlainObject(field)) return { source: "unavailable", value: null };
    const source = typeof field.source === "string" && field.source ? field.source : "unavailable";
    const value = field.value === undefined ? null : field.value;
    return { source, value };
  }

  function metricDisplay(item) {
    const unit = typeof item.unit === "string" ? item.unit : "";
    const value = item.value === null || item.value === undefined ? "Not recorded" : String(item.value);
    return unit && value !== "Not recorded" ? `${value} ${unit}` : value;
  }

  function shortSnapshot(projection) {
    const snapshot = projection?.project?.snapshot;
    return typeof snapshot === "string" ? snapshot.slice(0, 12) : "";
  }

  function unavailableSections(projection) {
    return [...CONTEXT_SECTIONS, ...CONTENT_SECTIONS].filter((name) => !isAvailable(section(projection, name)));
  }

  root.AiSdlcModel = {
    CONTENT_SECTIONS,
    CONTEXT_SECTIONS,
    decisionTone,
    isAvailable,
    label,
    metricDisplay,
    orderedSections,
    provenanceField,
    section,
    shortSnapshot,
    stateFlags,
    transitionsFrom,
    unavailableSections,
  };
}(globalThis));
