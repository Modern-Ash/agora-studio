"use strict";

(function exposeActivityModel(root) {
  const fields = ["timestamp", "type", "summary", "actor", "swarm_id", "work_id", "session_id", "tool_run_id", "source", "path"];

  function stableKey(event) {
    return JSON.stringify(fields.map((field) => event[field] ?? null));
  }

  function sortChronologically(events) {
    return events.map((event, index) => ({ event, index }))
      .sort((left, right) => left.event.timestamp.localeCompare(right.event.timestamp) || left.index - right.index)
      .map(({ event }) => event);
  }

  function filterEvents(events, filters) {
    return events.filter((event) => Object.entries(filters).every(([key, value]) => !value || event[key] === value));
  }

  function options(events, key) {
    return [...new Set(events.map((event) => event[key]).filter((value) => typeof value === "string" && value))]
      .sort((left, right) => left.localeCompare(right));
  }

  function relatedWork(events, selected) {
    if (!selected.swarm_id || !selected.work_id) return [];
    return events.filter((event) =>
      event.swarm_id === selected.swarm_id &&
      event.work_id === selected.work_id &&
      ["artifact.added", "evidence.added"].includes(event.type)
    );
  }

  function matchingSession(sessions, selected) {
    if (!selected.session_id) return null;
    return sessions.find((session) => session.id === selected.session_id) || null;
  }

  root.ActivityModel = { stableKey, sortChronologically, filterEvents, options, relatedWork, matchingSession };
}(globalThis));
