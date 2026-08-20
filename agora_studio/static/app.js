"use strict";

const API_ROOT = "/api/v1";
const workTabs = ["summary", "spec", "lifecycle", "artifacts", "evidence", "approvals", "activity"];
const viewNames = {
  overview: "Process overview",
  work: "Work control",
  swarms: "Swarms",
  actors: "Actors",
  activity: "Activity",
};

const state = {
  overview: null,
  activity: null,
  activityError: "",
  activityLoading: false,
  activityFilters: { type: "", actor: "", swarm_id: "" },
  details: {},
  detailRequests: new Map(),
  enrichmentLoading: false,
  generation: 0,
  gateAction: { key: null, decision: null, reason: "", submitting: false, error: "", result: "" },
  selectionPath: "",
  selectedWork: null,
  selectedTab: "summary",
  selectedRevision: null,
  revisionDetails: new Map(),
  view: "overview",
  loading: false,
};

const nodes = {
  content: document.querySelector("#content"),
  error: document.querySelector("#project-path-error"),
  form: document.querySelector("#project-form"),
  input: document.querySelector("#project-path"),
  live: document.querySelector("#live-status"),
  method: document.querySelector("#method-badge"),
  nav: [...document.querySelectorAll("[data-view]")],
  open: document.querySelector("#open-button"),
  refresh: document.querySelector("#refresh-button"),
  selection: document.querySelector("#selected-project"),
  selectionName: document.querySelector("#selected-project-name"),
  title: document.querySelector("#view-title"),
};

function element(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(options)) {
    if (value === undefined || value === null) continue;
    if (name === "text") node.textContent = String(value);
    else if (name === "className") node.className = value;
    else node.setAttribute(name, String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function replaceContent(...children) {
  nodes.content.replaceChildren(...children);
  nodes.content.setAttribute("aria-busy", "false");
}

function announce(message) {
  nodes.live.textContent = message;
}

function display(value, fallback = "Not recorded") {
  return value === undefined || value === null || value === "" ? fallback : String(value);
}

function titleCase(value) {
  return display(value, "Unknown").replaceAll("-", " ").replaceAll("_", " ");
}

function formatTime(timestamp) {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.valueOf())) return display(timestamp);
  return parsed.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function relativeTime(timestamp) {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.valueOf())) return display(timestamp);
  const seconds = Math.round((parsed.valueOf() - Date.now()) / 1000);
  const ranges = [
    [60, "second"],
    [60, "minute"],
    [24, "hour"],
    [7, "day"],
    [4.345, "week"],
    [12, "month"],
    [Infinity, "year"],
  ];
  let value = seconds;
  for (const [boundary, unit] of ranges) {
    if (Math.abs(value) < boundary) {
      return new Intl.RelativeTimeFormat([], { numeric: "auto" }).format(Math.round(value), unit);
    }
    value /= boundary;
  }
  return formatTime(timestamp);
}

async function requestJson(path, options) {
  if (!path.startsWith(`${API_ROOT}/`)) throw new Error("Studio rejected an unversioned API route.");
  const response = await fetch(path, options);
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error("Studio returned an unreadable response.");
  }
  if (!response.ok) {
    const error = new Error(payload.reason || "Studio could not complete the request.");
    error.code = payload.error || "request_failed";
    throw error;
  }
  return payload;
}

function statusPill(value) {
  const normalized = String(value || "unknown").toLowerCase();
  const tone = ["active", "running", "ready", "completed", "success"].includes(normalized)
    ? "good"
    : ["blocked", "failed", "error", "missing"].includes(normalized)
      ? "danger"
      : "neutral";
  return element("span", { className: `status-pill tone-${tone}`, text: titleCase(value) });
}

function tags(values, empty = "None") {
  const wrapper = element("div", { className: "tag-list" });
  const items = (values || []).filter(Boolean);
  if (!items.length) wrapper.append(element("span", { className: "muted", text: empty }));
  items.forEach((item) => wrapper.append(element("span", { className: "tag", text: item })));
  return wrapper;
}

function sectionHeading(kicker, title, description, action = null) {
  return element("header", { className: "section-heading" }, [
    element("div", {}, [
      element("p", { className: "section-kicker", text: kicker }),
      element("h2", { text: title }),
      description ? element("p", { className: "section-description", text: description }) : null,
    ]),
    action,
  ]);
}

function notice(kind, title, message) {
  return element("div", { className: `notice notice-${kind}`, role: kind === "error" ? "alert" : "status" }, [
    element("strong", { text: title }),
    element("span", { text: message }),
  ]);
}

function emptyState(code, title, message) {
  return element("div", { className: "empty-state" }, [
    element("span", { className: "empty-code", text: code }),
    element("h3", { text: title }),
    element("p", { text: message }),
  ]);
}

function loadingRows(label = "Loading durable records") {
  return element("div", { className: "loading-stack", "aria-label": label, "aria-busy": "true" }, [
    ...[0, 1, 2].map(() => element("div", { className: "skeleton-line" }, [element("span"), element("span")])),
  ]);
}

function setLoading(loading, message) {
  state.loading = loading;
  nodes.open.disabled = loading;
  nodes.refresh.disabled = loading || !state.overview;
  nodes.input.setAttribute("aria-busy", String(loading));
  nodes.refresh.classList.toggle("is-loading", loading);
  if (message) announce(message);
}

function resetProjectData() {
  state.generation += 1;
  state.activity = null;
  state.activityError = "";
  state.activityLoading = false;
  state.details = {};
  state.detailRequests = new Map();
  state.enrichmentLoading = false;
  state.gateAction = { key: null, decision: null, reason: "", submitting: false, error: "", result: "" };
  state.revisionDetails = new Map();
  state.selectedRevision = null;
  state.selectedWork = null;
  state.selectedTab = "summary";
}

function setSelection(selection) {
  if (state.selectionPath && state.selectionPath !== selection.path) resetProjectData();
  state.selectionPath = selection.path;
  nodes.selection.hidden = false;
  nodes.selectionName.textContent = selection.project;
  nodes.selectionName.title = selection.path;
  nodes.input.value = selection.path;
}

function syncChrome() {
  nodes.nav.forEach((button) => {
    const active = button.dataset.view === state.view;
    button.disabled = !state.overview;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  nodes.refresh.disabled = state.loading || !state.overview;
  const method = state.overview?.status?.default_method;
  nodes.method.hidden = !method;
  nodes.method.textContent = method ? `Method / ${method}` : "";
  nodes.title.textContent = state.selectedWork
    ? state.overview?.work?.find((work) => DashboardModel.workKey(work) === state.selectedWork)?.title || "Work detail"
    : viewNames[state.view];
}

function detailSnapshot() {
  return state.details;
}

function metricCard(label, value, note, tone = "neutral", pending = false) {
  return element("article", { className: `metric-card metric-${tone}${pending ? " is-pending" : ""}` }, [
    element("span", { className: "metric-label", text: label }),
    element("strong", { text: pending ? "··" : value }),
    element("small", { text: note }),
  ]);
}

function renderRecentActivity(limit = 7) {
  if (state.activityLoading && !state.activity) return loadingRows("Loading recent activity");
  if (!state.activity) {
    return emptyState("ACT—00", "Activity unavailable", state.activityError || "No durable activity was returned.");
  }
  const events = DashboardModel.recentActivity(state.activity.events, limit);
  if (!events.length) return emptyState("ACT—00", "No activity yet", "No durable events match this project.");
  return element("ol", { className: "activity-list", "aria-label": "Recent activity" }, events.map((event) =>
    element("li", { className: "activity-row" }, [
      element("span", { className: `event-mark family-${String(event.type || "other").split(".")[0]}`, "aria-hidden": "true" }),
      element("div", { className: "activity-copy" }, [
        element("div", { className: "activity-head" }, [
          element("strong", { className: "mono", text: event.type }),
          element("time", { datetime: event.timestamp, text: relativeTime(event.timestamp), title: formatTime(event.timestamp) }),
        ]),
        element("p", { text: event.summary }),
        element("span", { className: "activity-scope", text: [event.actor, event.swarm_id, event.work_id].filter(Boolean).join(" / ") || "Project event" }),
      ]),
    ]),
  ));
}

function renderOverview() {
  const overview = state.overview;
  const status = overview.status || {};
  const metrics = DashboardModel.metrics(overview, detailSnapshot());
  const detailCount = Object.values(state.details).filter((detail) => !detail.loading).length;
  const partialCount = Object.values(state.details).filter((detail) => detail.errors?.length).length;
  const detailPending = state.enrichmentLoading && detailCount < (overview.work || []).length;
  const methodPack = status.default_method || "Not recorded";
  const activeWork = (overview.work || []).filter(DashboardModel.isWorkInProgress).slice(0, 4);

  const healthRail = element("section", { className: "health-rail", "aria-label": "Process health" }, [
    element("div", { className: "method-card" }, [
      element("span", { className: "metric-label", text: "Active Method Pack" }),
      element("strong", { text: methodPack }),
      element("small", { text: `${display(status.branch, "No branch")} · ${display(status.integration, "No integration")}` }),
    ]),
    metricCard("Active swarms", metrics.activeSwarms, `${(overview.swarms || []).length} total`, metrics.activeSwarms ? "accent" : "neutral"),
    metricCard("Work in progress", metrics.workInProgress, `${(overview.work || []).length} total`, metrics.workInProgress ? "accent" : "neutral"),
    metricCard("Blocked", metrics.blockedWork, "work items", metrics.blockedWork ? "danger" : "good"),
    metricCard("Pending approvals", metrics.pendingApprovals, "required roles", metrics.pendingApprovals ? "danger" : "good", detailPending),
    metricCard("Evidence missing", metrics.missingEvidence, "work items", metrics.missingEvidence ? "danger" : "good", detailPending),
    metricCard("Failed sessions", metrics.failedSessions, "durable runs", metrics.failedSessions ? "danger" : "good"),
  ]);

  const alerts = [];
  if (state.enrichmentLoading) alerts.push(notice("progress", "Checking gates and provenance", `${detailCount} of ${(overview.work || []).length} work items enriched.`));
  if (partialCount || state.activityError) alerts.push(notice("partial", "Partial data", `${partialCount + (state.activityError ? 1 : 0)} read ${partialCount + (state.activityError ? 1 : 0) === 1 ? "area is" : "areas are"} unavailable; verified data remains visible.`));

  const queue = element("section", { className: "control-panel", "aria-labelledby": "focus-title" }, [
    element("header", { className: "panel-heading" }, [
      element("div", {}, [element("p", { className: "section-kicker", text: "Immediate focus" }), element("h3", { id: "focus-title", text: "Work in progress" })]),
      element("span", { className: "panel-count", text: String(activeWork.length) }),
    ]),
    activeWork.length
      ? element("ol", { className: "focus-list" }, activeWork.map((work) => {
        const assignment = DashboardModel.assignmentFor(work, overview.swarms);
        const open = element("button", { className: "focus-row", type: "button", "aria-label": `Open ${work.title}` }, [
          element("span", { className: "state-stripe", "data-state": work.state, "aria-hidden": "true" }),
          element("span", { className: "focus-copy" }, [element("strong", { text: work.title || work.id }), element("small", { text: `${work.swarm_id}/${work.id}` })]),
          statusPill(work.state),
          element("span", { className: "focus-owner", text: assignment.actor || "Unassigned" }),
        ]);
        open.addEventListener("click", () => openWork(work));
        return element("li", {}, [open]);
      }))
      : emptyState("WIP—00", "No work in progress", "All durable work is terminal or no work has been registered."),
  ]);

  const activity = element("section", { className: "control-panel", "aria-labelledby": "recent-title" }, [
    element("header", { className: "panel-heading" }, [
      element("div", {}, [element("p", { className: "section-kicker", text: "Durable signal" }), element("h3", { id: "recent-title", text: "Recent activity" })]),
      element("button", { className: "text-button", type: "button", text: "View all →", "data-go": "activity" }),
    ]),
    renderRecentActivity(),
  ]);
  activity.querySelector("[data-go]").addEventListener("click", () => switchView("activity"));

  replaceContent(
    sectionHeading("01 / Control surface", "Process status", `A read-only operational view of ${overview.selection.project}.`),
    ...alerts,
    healthRail,
    element("div", { className: "overview-grid" }, [queue, activity]),
  );
}

function workCard(work) {
  const key = DashboardModel.workKey(work);
  const assignment = DashboardModel.assignmentFor(work, state.overview.swarms);
  const detail = state.details[key];
  const gates = DashboardModel.pendingGates(detail?.lifecycle);
  const blocked = DashboardModel.isBlocked(work);
  const button = element("button", { className: `work-card${blocked ? " is-blocked" : ""}`, type: "button", "aria-label": `Open work item ${work.title || work.id}` }, [
    element("span", { className: "work-card-topline" }, [
      element("span", { className: "mono card-key", text: key }),
      statusPill(work.state),
    ]),
    element("strong", { className: "work-title", text: work.title || work.id }),
    element("span", { className: "assignment-line" }, [
      element("span", { className: "avatar", text: (assignment.actor || "?").split(":").pop().slice(0, 2).toUpperCase(), "aria-hidden": "true" }),
      element("span", {}, [
        element("b", { text: assignment.actor || "Unassigned" }),
        element("small", { text: assignment.role ? `${assignment.role} · swarm scope` : "No role recorded" }),
      ]),
    ]),
    element("span", { className: `block-line${blocked ? " is-alert" : ""}` }, [
      element("span", { "aria-hidden": "true", text: blocked ? "!" : "✓" }),
      element("span", { text: blocked ? work.status_reason || "Blocked" : "No operational block" }),
    ]),
    element("span", { className: "card-footer" }, [
      element("span", { text: detail?.loading ? "Checking gates…" : gates.length ? `${gates.length} gate${gates.length === 1 ? "" : "s"} pending` : detail?.errors?.length ? "Gates unavailable" : "No pending gates" }),
      element("time", { datetime: work.status_at, text: relativeTime(work.status_at), title: formatTime(work.status_at) }),
    ]),
  ]);
  button.addEventListener("click", () => openWork(work));
  return button;
}

function renderBoard() {
  const columns = DashboardModel.boardColumns(state.overview.work, detailSnapshot());
  if (!columns.length) return emptyState("WRK—00", "No work registered", "The selected project has no durable work items.");
  return element("div", { className: "board", role: "region", "aria-label": "Work grouped by Method Pack state", tabindex: "0" }, columns.map((column, index) =>
    element("section", { className: "board-column", "aria-labelledby": `board-state-${index}` }, [
      element("header", { className: "column-heading" }, [
        element("span", { className: "column-index", text: String(index + 1).padStart(2, "0") }),
        element("h3", { id: `board-state-${index}`, text: titleCase(column.state) }),
        element("span", { className: "column-count", text: column.items.length }),
      ]),
      column.items.length
        ? element("div", { className: "card-stack" }, column.items.map(workCard))
        : element("p", { className: "column-empty", text: "No work in this state" }),
    ]),
  ));
}

function renderWork() {
  if (state.selectedWork) return renderWorkDetail();
  const method = state.overview.status?.default_method || "unavailable";
  const partial = Object.values(state.details).filter((detail) => detail.errors?.length).length;
  replaceContent(
    sectionHeading("02 / Governed delivery", "Work board", `Read-only board grouped by the ordered states available from Method Pack ${method}.`, statusPill("Read-only")),
    state.enrichmentLoading ? notice("progress", "Board enrichment in progress", "Gate, evidence, and approval state is loading without blocking the board.") : null,
    partial ? notice("partial", "Some cards are partial", `${partial} work item ${partial === 1 ? "read is" : "reads are"} incomplete.`) : null,
    renderBoard(),
  );
}

function selectedWorkRecord() {
  return state.overview.work.find((work) => DashboardModel.workKey(work) === state.selectedWork) || null;
}

function definitionList(entries) {
  return element("dl", { className: "definition-list" }, entries.map(([term, value]) =>
    element("div", {}, [element("dt", { text: term }), element("dd", { text: display(value) })]),
  ));
}

function renderSummaryTab(work, detail) {
  const assignment = DashboardModel.assignmentFor(work, state.overview.swarms);
  const gates = DashboardModel.pendingGates(detail?.lifecycle);
  const criteria = Object.entries(work.acceptance_criteria || {});
  return element("div", { className: "detail-grid" }, [
    element("section", { className: "detail-panel" }, [
      element("p", { className: "section-kicker", text: "Operating context" }),
      element("h3", { text: "Summary" }),
      element("p", { className: "detail-lead", text: work.description || "No durable description is recorded." }),
      definitionList([
        ["State", work.state],
        ["Operational", work.operational_status],
        ["Swarm actor", assignment.actor],
        ["Swarm role", assignment.role],
        ["Updated", formatTime(work.status_at)],
      ]),
    ]),
    element("section", { className: "detail-panel" }, [
      element("p", { className: "section-kicker", text: "Readiness" }),
      element("h3", { text: "Criteria and gates" }),
      criteria.length
        ? element("ul", { className: "check-list" }, criteria.map(([id, description]) =>
          element("li", { className: (work.satisfied_criteria || []).includes(id) ? "is-done" : "" }, [
            element("span", { "aria-hidden": "true", text: (work.satisfied_criteria || []).includes(id) ? "✓" : "○" }),
            element("span", {}, [element("strong", { text: id }), element("small", { text: description })]),
          ]),
        ))
        : emptyState("CRT—00", "No criteria recorded", "This work item has no durable acceptance criteria."),
      gates.length
        ? element("div", { className: "gate-alert" }, [
          element("strong", { text: `${gates.length} pending gate${gates.length === 1 ? "" : "s"}` }),
          ...gates.map((gate) => element("span", { text: `${gate.id} → ${gate.target}: ${gate.blockers.join("; ")}` })),
        ])
        : element("p", { className: "quiet-success", text: detail?.loading ? "Checking current gates…" : "No pending gate blockers detected." }),
    ]),
  ]);
}

function renderSpecTab(work, detail) {
  if (detail?.loading && !detail.lifecycle) return loadingRows("Loading specification history");
  if (!detail?.lifecycle) return emptyState("SPC—ERR", "Specification unavailable", detail?.errors?.join(" ") || "The lifecycle read did not return specification data.");
  const specification = detail.lifecycle.specification || {};
  if (!specification.available) return emptyState("SPC—00", "No verified specification", specification.reason || "No single registered specification is available.");
  const revisions = specification.revisions || [];
  const revisionKey = state.selectedRevision ? `${DashboardModel.workKey(work)}:${state.selectedRevision}` : null;
  const revisionDetail = revisionKey ? state.revisionDetails.get(revisionKey) : null;
  return element("div", { className: "detail-grid spec-grid" }, [
    element("section", { className: "detail-panel" }, [
      element("p", { className: "section-kicker", text: "Registered specification" }),
      element("h3", { className: "mono wrap", text: specification.uri }),
      revisions.length
        ? element("ol", { className: "revision-list" }, revisions.map((revision) => {
          const button = element("button", { className: `revision-button${state.selectedRevision === revision.id ? " is-selected" : ""}`, type: "button" }, [
            element("strong", { className: "mono", text: revision.short_sha || revision.id }),
            element("span", { text: revision.subject || "Working tree" }),
            element("small", { text: `${display(revision.work_state, "state unknown")} · ${formatTime(revision.timestamp)}` }),
          ]);
          button.addEventListener("click", () => loadRevision(work, revision.id));
          return element("li", {}, [button]);
        }))
        : emptyState("REV—00", "No revisions", "The specification has no available Git history."),
    ]),
    element("section", { className: "detail-panel revision-detail" }, [
      element("p", { className: "section-kicker", text: "Revision detail" }),
      !state.selectedRevision
        ? emptyState("REV—SELECT", "Select a revision", "Choose a verified revision to inspect its bounded diff.")
        : revisionDetail === "loading"
          ? loadingRows("Loading revision detail")
          : revisionDetail?.error
            ? emptyState("REV—ERR", "Revision unavailable", revisionDetail.error)
            : revisionDetail
              ? [element("h3", { className: "mono", text: revisionDetail.detail.revision }), tags(revisionDetail.detail.changed_headings, "No changed headings"), element("pre", { className: "revision-diff", text: revisionDetail.detail.text || "No textual diff." })]
              : loadingRows("Loading revision detail"),
    ]),
  ]);
}

function renderLifecycleTab(detail) {
  if (detail?.loading && !detail.lifecycle) return loadingRows("Loading lifecycle");
  if (!detail?.lifecycle?.method?.available) return emptyState("LFC—00", "Lifecycle unavailable", detail?.lifecycle?.diagnostics?.join(" ") || detail?.errors?.join(" ") || "Method topology is not available.");
  const lifecycle = detail.lifecycle;
  const states = lifecycle.method.states || [];
  const traversed = new Set((lifecycle.actual_path?.traversals || []).map((item) => `${item.from}/${item.to}`));
  return element("div", { className: "lifecycle-panel" }, [
    element("div", { className: "process-track", role: "list", "aria-label": `${lifecycle.method.name} lifecycle states` }, states.map((item, index) =>
      element("div", { className: `process-node${item.current ? " is-current" : ""}${item.terminal ? " is-terminal" : ""}`, role: "listitem" }, [
        element("span", { className: "node-number", text: String(index + 1).padStart(2, "0") }),
        element("strong", { text: titleCase(item.id) }),
        element("small", { text: item.current ? "Current" : item.terminal ? "Terminal" : "Method state" }),
      ]),
    )),
    element("section", { className: "detail-panel" }, [
      element("p", { className: "section-kicker", text: "Method transitions" }),
      element("h3", { text: lifecycle.method.name }),
      element("ul", { className: "transition-list" }, (lifecycle.method.transitions || []).map((transition) =>
        element("li", { className: `${traversed.has(`${transition.from}/${transition.to}`) ? "is-traversed" : ""}${transition.blockers?.length ? " is-blocked" : ""}` }, [
          element("span", { className: "transition-path mono", text: `${transition.from} → ${transition.to}` }),
          element("span", { text: transition.gate || "No gate" }),
          transition.blockers?.length ? element("small", { text: transition.blockers.join("; ") }) : element("small", { text: traversed.has(`${transition.from}/${transition.to}`) ? "Traversed" : "Available by method" }),
        ]),
      )),
    ]),
  ]);
}

function recordsTable(kind, records, columns, emptyMessage) {
  if (!records?.length) return emptyState(`${kind.slice(0, 3).toUpperCase()}—00`, `No ${kind.toLowerCase()}`, emptyMessage);
  const table = element("table", { className: "records-table" });
  table.append(element("thead", {}, [element("tr", {}, columns.map((column) => element("th", { scope: "col", text: column.label }))) ]));
  table.append(element("tbody", {}, records.map((record) => element("tr", {}, columns.map((column) => element("td", { "data-label": column.label }, [column.render(record)]))))));
  return element("div", { className: "table-frame" }, [table]);
}

function renderArtifactsTab(detail) {
  if (detail?.loading && !detail.artifacts) return loadingRows("Loading artifacts");
  if (!detail?.artifacts) return emptyState("ART—ERR", "Artifacts unavailable", detail?.errors?.join(" ") || "No artifact projection was returned.");
  return recordsTable("Artifacts", detail.artifacts.artifacts, [
    { label: "Kind", render: (record) => statusPill(record.kind) },
    { label: "URI", render: (record) => element("span", { className: "mono wrap", text: record.uri }) },
    { label: "Produced by", render: (record) => record.produced_by },
    { label: "Recorded", render: (record) => formatTime(record.timestamp) },
  ], "No artifacts are durably registered for this work item.");
}

function renderEvidenceTab(detail) {
  if (detail?.loading && !detail.artifacts) return loadingRows("Loading evidence");
  if (!detail?.artifacts) return emptyState("EVD—ERR", "Evidence unavailable", detail?.errors?.join(" ") || "No evidence projection was returned.");
  return recordsTable("Evidence", detail.artifacts.evidence, [
    { label: "Result", render: (record) => statusPill(record.result) },
    { label: "Type", render: (record) => record.type },
    { label: "Artifact refs", render: (record) => tags(record.artifact_references, "None") },
    { label: "Produced by", render: (record) => record.produced_by },
  ], "No evidence is durably registered for this work item.");
}

function gateErrorMessage(error) {
  const messages = {
    "command.actor-unauthorized": "This actor does not hold the role or authority required by the Method Pack.",
    "command.gate-already-resolved": "This gate decision was already recorded. Refresh before continuing.",
    "command.stale-precondition": "The work state changed after this view loaded. The projection has been refreshed.",
    "command.evidence-missing": "Required durable evidence is missing or no longer satisfies the gate.",
    "command.signature-required": "This actor requires a signed lifecycle action before the decision can be recorded.",
    "command.persistence-failed": "Core could not persist the complete decision; no partial result is shown.",
    "command.version-incompatible": "The installed Agora Core does not support this versioned command.",
  };
  return messages[error.code] || error.message;
}

function beginGateDecision(work, decision, reason) {
  if (!reason.trim()) {
    state.gateAction = { key: DashboardModel.workKey(work), decision: null, reason: "", submitting: false, error: "A reason is required for every gate decision.", result: "" };
  } else {
    state.gateAction = { key: DashboardModel.workKey(work), decision, reason: reason.trim(), submitting: false, error: "", result: "" };
  }
  renderWorkDetail();
  document.querySelector(
    state.gateAction.decision ? ".gate-confirmation button" : "#gate-reason",
  )?.focus();
}

async function refreshAfterGateDecision(work) {
  const key = DashboardModel.workKey(work);
  const [overview, activity] = await Promise.all([
    requestJson(`${API_ROOT}/overview`),
    requestJson(`${API_ROOT}/activity?limit=500`),
  ]);
  state.overview = overview;
  state.activity = activity;
  delete state.details[key];
  state.detailRequests.delete(key);
  const current = state.overview.work.find((item) => DashboardModel.workKey(item) === key);
  if (current) await ensureWorkDetail(current);
}

async function submitGateDecision(work, detail) {
  if (state.gateAction.submitting) return;
  const context = DashboardModel.gateDecisionContext(work, state.overview.swarms, detail);
  if (!context.ready || !state.gateAction.decision) return;
  state.gateAction.submitting = true;
  state.gateAction.error = "";
  renderWorkDetail();
  const evidenceReferences = [...new Set(context.evidence.flatMap((item) => item.artifact_references || []))];
  try {
    await requestJson(`${API_ROOT}/work-items/${encodeURIComponent(work.swarm_id)}/${encodeURIComponent(work.id)}/approvals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        schema: "agora/application/approve-gate-command/v1",
        gate_id: context.gate.id,
        actor_id: context.actor,
        decision: state.gateAction.decision,
        reason: state.gateAction.reason,
        expected_state: work.state,
        evidence_references: evidenceReferences,
      }),
    });
    const decision = state.gateAction.decision;
    await refreshAfterGateDecision(work);
    state.gateAction = {
      key: DashboardModel.workKey(work),
      decision: null,
      reason: "",
      submitting: false,
      error: "",
      result: decision === "approved"
        ? "Approval persisted. The gate projection and Activity log were refreshed."
        : "Rejection persisted. The gate remains closed and Activity now shows the decision.",
    };
    announce(state.gateAction.result);
  } catch (error) {
    state.gateAction.submitting = false;
    state.gateAction.error = gateErrorMessage(error);
    if (["command.stale-precondition", "command.gate-already-resolved"].includes(error.code)) {
      try {
        await refreshAfterGateDecision(work);
      } catch {
        state.gateAction.error += " Studio could not refresh the durable projection.";
      }
    }
    announce(`Gate decision failed. ${state.gateAction.error}`);
  }
  renderWorkDetail();
}

function renderGateControl(work, detail) {
  const context = DashboardModel.gateDecisionContext(work, state.overview.swarms, detail);
  if (!context.gate) return null;
  const action = state.gateAction.key === DashboardModel.workKey(work)
    ? state.gateAction
    : { decision: null, reason: "", submitting: false, error: "", result: "" };

  const evidence = context.evidence.length
    ? element("ul", { className: "gate-evidence" }, context.evidence.map((record) => element("li", {}, [
      statusPill(record.result),
      element("span", {}, [element("strong", { text: record.type }), tags(record.artifact_references, "No artifact references")]),
    ])))
    : emptyState("EVD—REQ", "Evidence required", "No successful durable evidence is associated with this gate.");

  let controls;
  if (action.decision) {
    const effect = action.decision === "approved"
      ? `Record ${context.role} approval by ${context.actor}; Core will then recompute gate ${context.gate.id}.`
      : `Record a durable rejection by ${context.actor}; the approval stays unsatisfied and the gate remains closed.`;
    const confirm = element("button", { className: `primary-button decision-${action.decision}`, type: "button", text: action.submitting ? "Persisting…" : `Confirm ${action.decision}`, disabled: action.submitting ? "disabled" : null });
    confirm.addEventListener("click", () => submitGateDecision(work, detail));
    const cancel = element("button", { className: "back-button", type: "button", text: "Cancel", disabled: action.submitting ? "disabled" : null });
    cancel.addEventListener("click", () => {
      state.gateAction = { key: DashboardModel.workKey(work), decision: null, reason: "", submitting: false, error: "", result: "" };
      renderWorkDetail();
    });
    controls = element("div", { className: "gate-confirmation", role: "alertdialog", "aria-labelledby": "gate-confirm-title", "aria-describedby": "gate-confirm-effect" }, [
      element("p", { className: "section-kicker", text: "Confirm governed mutation" }),
      element("h3", { id: "gate-confirm-title", text: `${titleCase(action.decision)} ${context.gate.id}` }),
      element("p", { id: "gate-confirm-effect", text: effect }),
      element("blockquote", { text: action.reason }),
      element("div", { className: "gate-actions" }, [confirm, cancel]),
    ]);
  } else if (action.result) {
    controls = element("p", { className: "quiet-success", text: "The durable response is visible above. Review Activity before making another decision." });
  } else {
    const form = element("form", { className: "gate-decision-form" }, [
      element("label", { for: "gate-reason" }, [element("span", { text: "Decision reason" }), element("textarea", { id: "gate-reason", name: "reason", rows: "4", required: "required", maxlength: "4000", text: action.reason, placeholder: "Explain the durable basis for this decision." })]),
      element("div", { className: "gate-actions" }, [
        element("button", { className: "primary-button decision-approved", type: "submit", value: "approved", text: "Approve gate", disabled: context.ready ? null : "disabled" }),
        element("button", { className: "back-button decision-rejected", type: "submit", value: "rejected", text: "Reject gate", disabled: context.ready ? null : "disabled" }),
      ]),
    ]);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const submitter = event.submitter?.value;
      if (!submitter) return;
      beginGateDecision(work, submitter, form.elements.reason.value);
    });
    controls = form;
  }

  return element("section", { className: "gate-control", "aria-labelledby": "gate-control-title" }, [
    element("div", { className: "gate-control-heading" }, [
      element("div", {}, [element("p", { className: "section-kicker", text: "Governed action" }), element("h3", { id: "gate-control-title", text: `Gate / ${context.gate.id}` })]),
      statusPill("pending"),
    ]),
    definitionList([["Expected state", work.state], ["Actor", context.actor], ["Role", context.role], ["Target state", context.gate.target]]),
    element("h4", { text: "Associated evidence" }),
    evidence,
    action.error ? notice("error", "Decision not persisted", action.error) : null,
    action.result ? notice("progress", "Durable response received", action.result) : null,
    controls,
  ]);
}

function renderApprovalsTab(work, detail) {
  if (detail?.loading && !detail.artifacts) return loadingRows("Loading approvals");
  if (!detail?.artifacts) return emptyState("APR—ERR", "Approvals unavailable", detail?.errors?.join(" ") || "No approval projection was returned.");
  const projection = detail.artifacts.approvals;
  if (!projection.satisfaction?.length) return emptyState("APR—00", "No approvals required", "This work item has no durable required approval roles.");
  const approvals = element("div", { className: "approval-grid" }, projection.satisfaction.map((item) => {
    const record = projection.records.find((candidate) => candidate.role === item.role);
    return element("article", { className: `approval-card${item.satisfied ? " is-satisfied" : " is-missing"}` }, [
      element("span", { className: "approval-mark", "aria-hidden": "true", text: item.satisfied ? "✓" : "!" }),
      element("div", {}, [
        element("span", { className: "metric-label", text: item.satisfied ? "Approved" : "Pending" }),
        element("h3", { text: item.role }),
        element("p", { text: record ? `${record.approved_by} · ${record.note}` : "No durable approval record yet." }),
        record ? element("time", { datetime: record.timestamp, text: formatTime(record.timestamp) }) : null,
      ]),
    ]);
  }));
  return element("div", { className: "approval-stack" }, [renderGateControl(work, detail), approvals]);
}

function renderWorkActivityTab(work) {
  if (state.activityLoading && !state.activity) return loadingRows("Loading work activity");
  if (!state.activity) return emptyState("ACT—ERR", "Activity unavailable", state.activityError || "No activity projection was returned.");
  const events = DashboardModel.recentActivity((state.activity.events || []).filter((event) => event.swarm_id === work.swarm_id && event.work_id === work.id), 100);
  if (!events.length) return emptyState("ACT—00", "No linked activity", "No durable activity references this exact work item.");
  return element("ol", { className: "activity-list detail-activity" }, events.map((event) => element("li", { className: "activity-row" }, [
    element("span", { className: "event-mark", "aria-hidden": "true" }),
    element("div", { className: "activity-copy" }, [
      element("div", { className: "activity-head" }, [element("strong", { className: "mono", text: event.type }), element("time", { datetime: event.timestamp, text: formatTime(event.timestamp) })]),
      element("p", { text: event.summary }),
      element("span", { className: "activity-scope", text: event.actor || "Actor not recorded" }),
    ]),
  ])));
}

function renderWorkTab(work, detail) {
  if (state.selectedTab === "summary") return renderSummaryTab(work, detail);
  if (state.selectedTab === "spec") return renderSpecTab(work, detail);
  if (state.selectedTab === "lifecycle") return renderLifecycleTab(detail);
  if (state.selectedTab === "artifacts") return renderArtifactsTab(detail);
  if (state.selectedTab === "evidence") return renderEvidenceTab(detail);
  if (state.selectedTab === "approvals") return renderApprovalsTab(work, detail);
  return renderWorkActivityTab(work);
}

function activateTab(tabName, focus = false) {
  state.selectedTab = tabName;
  renderWorkDetail();
  if (focus) document.querySelector(`[data-tab="${tabName}"]`)?.focus();
}

function renderWorkDetail() {
  const work = selectedWorkRecord();
  if (!work) {
    state.selectedWork = null;
    return renderWork();
  }
  const detail = state.details[state.selectedWork] || { loading: true, errors: [] };
  const assignment = DashboardModel.assignmentFor(work, state.overview.swarms);
  const back = element("button", { className: "back-button", type: "button", text: "← Back to board" });
  back.addEventListener("click", () => {
    state.selectedWork = null;
    state.selectedRevision = null;
    render();
  });
  const tabList = element("div", { className: "detail-tabs", role: "tablist", "aria-label": "Work item detail" }, workTabs.map((tab) => {
    const button = element("button", {
      className: `detail-tab${state.selectedTab === tab ? " is-active" : ""}`,
      type: "button",
      role: "tab",
      id: `tab-${tab}`,
      "data-tab": tab,
      "aria-controls": "work-tab-panel",
      "aria-selected": state.selectedTab === tab ? "true" : "false",
      tabindex: state.selectedTab === tab ? "0" : "-1",
      text: titleCase(tab),
    });
    button.addEventListener("click", () => activateTab(tab));
    button.addEventListener("keydown", (event) => {
      const index = workTabs.indexOf(tab);
      let next = null;
      if (event.key === "ArrowRight") next = workTabs[(index + 1) % workTabs.length];
      if (event.key === "ArrowLeft") next = workTabs[(index - 1 + workTabs.length) % workTabs.length];
      if (event.key === "Home") next = workTabs[0];
      if (event.key === "End") next = workTabs.at(-1);
      if (next) {
        event.preventDefault();
        activateTab(next, true);
      }
    });
    return button;
  }));
  replaceContent(
    back,
    element("header", { className: "work-detail-header" }, [
      element("div", {}, [
        element("p", { className: "mono detail-key", text: DashboardModel.workKey(work) }),
        element("h2", { text: work.title || work.id }),
        element("p", { text: work.description || "No durable description is recorded." }),
      ]),
      element("div", { className: "detail-status" }, [statusPill(work.state), element("span", { text: `${assignment.actor || "Unassigned"} / ${assignment.role || "No role"} · swarm assignment` })]),
    ]),
    detail.errors?.length ? notice("partial", "Partial work detail", detail.errors.join(" ")) : null,
    tabList,
    element("section", { id: "work-tab-panel", className: "tab-panel", role: "tabpanel", "aria-labelledby": `tab-${state.selectedTab}`, tabindex: "0" }, [renderWorkTab(work, detail)]),
  );
  syncChrome();
}

function renderDataTable(config) {
  const records = state.overview[config.key] || [];
  const content = records.length
    ? recordsTable(config.title, records, config.columns, config.empty)
    : emptyState(`${config.code}—00`, `No ${config.title.toLowerCase()}`, config.empty);
  replaceContent(sectionHeading(config.kicker, config.title, config.description), content);
}

function renderSwarms() {
  renderDataTable({
    key: "swarms",
    code: "SWR",
    kicker: "03 / Delivery topology",
    title: "Swarms",
    description: "Method ownership, branch, status, and durable role assignments.",
    empty: "No delivery swarms are registered.",
    columns: [
      { label: "Swarm", render: (record) => element("strong", { className: "mono", text: record.id }) },
      { label: "Method", render: (record) => record.method },
      { label: "Status", render: (record) => statusPill(record.status) },
      { label: "Objective", render: (record) => record.objective },
      { label: "Assignments", render: (record) => tags(Object.entries(record.assignments || {}).map(([role, actor]) => `${role}: ${actor}`)) },
    ],
  });
}

function renderActors() {
  renderDataTable({
    key: "actors",
    code: "ACTR",
    kicker: "04 / Participants",
    title: "Actors",
    description: "Identities and capabilities admitted to the selected process.",
    empty: "No actors are registered.",
    columns: [
      { label: "Actor", render: (record) => element("strong", { text: record.name }) },
      { label: "Reference", render: (record) => element("span", { className: "mono wrap", text: record.reference }) },
      { label: "Kind", render: (record) => statusPill(record.kind) },
      { label: "Capabilities", render: (record) => tags(record.capabilities) },
      { label: "Authentication", render: (record) => record.authentication_required ? "Required" : "Not required" },
    ],
  });
}

function activityFilter(label, field) {
  const select = element("select", { id: `filter-${field}`, "data-filter": field });
  select.append(element("option", { value: "", text: `All ${label.toLowerCase()}` }));
  ActivityModel.options(state.activity?.events || [], field).forEach((value) => select.append(element("option", { value, text: value })));
  select.value = state.activityFilters[field];
  select.addEventListener("change", () => {
    state.activityFilters[field] = select.value;
    renderActivity();
  });
  return element("label", { className: "filter-field" }, [element("span", { text: label }), select]);
}

function renderActivity() {
  if (state.activityLoading && !state.activity) {
    return replaceContent(sectionHeading("05 / Durable log", "Activity", "Loading bounded process events."), loadingRows("Loading activity"));
  }
  if (!state.activity) {
    return replaceContent(sectionHeading("05 / Durable log", "Activity", "A bounded timeline from Agora records."), notice("error", "Activity read failed", state.activityError || "No activity data is available."));
  }
  const events = DashboardModel.recentActivity(ActivityModel.filterEvents(state.activity.events || [], state.activityFilters), 500);
  replaceContent(
    sectionHeading("05 / Durable log", "Activity", "Filterable, bounded events with exact durable work and actor references."),
    element("section", { className: "activity-toolbar", "aria-label": "Activity filters" }, [
      activityFilter("Event type", "type"),
      activityFilter("Actor", "actor"),
      activityFilter("Swarm", "swarm_id"),
      element("div", { className: "filter-result" }, [element("strong", { text: events.length }), element("span", { text: "events" })]),
    ]),
    events.length
      ? element("section", { className: "activity-panel" }, [renderActivityRows(events)])
      : emptyState("ACT—00", "No matching activity", "Clear one or more filters to expand the result."),
  );
}

function renderActivityRows(events) {
  return element("ol", { className: "activity-list full-activity" }, events.map((event) => element("li", { className: "activity-row" }, [
    element("span", { className: `event-mark family-${String(event.type || "other").split(".")[0]}`, "aria-hidden": "true" }),
    element("div", { className: "activity-copy" }, [
      element("div", { className: "activity-head" }, [element("strong", { className: "mono", text: event.type }), element("time", { datetime: event.timestamp, text: formatTime(event.timestamp) })]),
      element("p", { text: event.summary }),
      element("span", { className: "activity-scope", text: [event.actor, event.swarm_id, event.work_id, event.session_id].filter(Boolean).join(" / ") || "Project event" }),
    ]),
  ])));
}

function render() {
  syncChrome();
  if (!state.overview) return;
  if (state.view === "overview") renderOverview();
  else if (state.view === "work") renderWork();
  else if (state.view === "swarms") renderSwarms();
  else if (state.view === "actors") renderActors();
  else renderActivity();
}

function renderFatal(message) {
  replaceContent(
    sectionHeading("Read interrupted", "The project stayed selected", "No local records were changed."),
    notice("error", "Studio could not build the control view", message),
  );
}

function switchView(view) {
  state.view = view;
  state.selectedWork = null;
  state.selectedRevision = null;
  render();
  document.querySelector("#main-content").focus({ preventScroll: true });
  announce(`${viewNames[view]} is visible.`);
  if (view === "activity" && !state.activity) loadActivity();
}

function openWork(work) {
  state.view = "work";
  state.selectedWork = DashboardModel.workKey(work);
  state.selectedTab = "summary";
  state.selectedRevision = null;
  render();
  ensureWorkDetail(work);
  if (!state.activity) loadActivity();
  document.querySelector("#main-content").focus({ preventScroll: true });
  announce(`${work.title || work.id} detail is visible.`);
}

async function loadActivity(message = "Loading durable activity") {
  if (state.activityLoading || !state.overview) return;
  const generation = state.generation;
  state.activityLoading = true;
  state.activityError = "";
  if (state.view === "activity" || state.view === "overview" || state.selectedTab === "activity") render();
  announce(message);
  try {
    const activity = await requestJson(`${API_ROOT}/activity?limit=500`);
    if (generation !== state.generation) return;
    state.activity = activity;
  } catch (error) {
    if (generation !== state.generation) return;
    state.activityError = error.message;
  } finally {
    if (generation !== state.generation) return;
    state.activityLoading = false;
    if (["overview", "activity"].includes(state.view) || state.selectedTab === "activity") render();
  }
}

async function ensureWorkDetail(work) {
  const key = DashboardModel.workKey(work);
  if (state.detailRequests.has(key)) return state.detailRequests.get(key);
  if (state.details[key] && !state.details[key].loading) return state.details[key];
  const generation = state.generation;
  const request = (async () => {
    state.details[key] = { loading: true, lifecycle: null, artifacts: null, errors: [] };
    if (state.view === "work" || state.view === "overview") render();
    const query = `swarm=${encodeURIComponent(work.swarm_id)}&work=${encodeURIComponent(work.id)}`;
    const [lifecycle, artifacts] = await Promise.allSettled([
      requestJson(`${API_ROOT}/lifecycle?${query}`),
      requestJson(`${API_ROOT}/artifacts?${query}`),
    ]);
    if (generation !== state.generation) return null;
    const errors = [];
    if (lifecycle.status === "rejected") errors.push(`Lifecycle: ${lifecycle.reason.message}`);
    if (artifacts.status === "rejected") errors.push(`Provenance: ${artifacts.reason.message}`);
    state.details[key] = {
      loading: false,
      lifecycle: lifecycle.status === "fulfilled" ? lifecycle.value : null,
      artifacts: artifacts.status === "fulfilled" ? artifacts.value : null,
      errors,
    };
    if (state.view === "work" || state.view === "overview") render();
    return state.details[key];
  })();
  state.detailRequests.set(key, request);
  return request;
}

async function enrichWork() {
  const work = state.overview.work || [];
  if (!work.length) return;
  const generation = state.generation;
  state.enrichmentLoading = true;
  render();
  let cursor = 0;
  const worker = async () => {
    while (cursor < work.length && generation === state.generation) {
      const item = work[cursor];
      cursor += 1;
      await ensureWorkDetail(item);
    }
  };
  await Promise.all(Array.from({ length: Math.min(4, work.length) }, worker));
  if (generation !== state.generation) return;
  state.enrichmentLoading = false;
  render();
  announce("Gate, evidence, and approval state loaded for the work board.");
}

async function loadRevision(work, revision) {
  const generation = state.generation;
  state.selectedRevision = revision;
  const key = `${DashboardModel.workKey(work)}:${revision}`;
  if (state.revisionDetails.has(key)) return renderWorkDetail();
  state.revisionDetails.set(key, "loading");
  renderWorkDetail();
  const query = `swarm=${encodeURIComponent(work.swarm_id)}&work=${encodeURIComponent(work.id)}&revision=${encodeURIComponent(revision)}`;
  try {
    const detail = await requestJson(`${API_ROOT}/lifecycle/revision?${query}`);
    if (generation !== state.generation) return;
    state.revisionDetails.set(key, detail);
  } catch (error) {
    if (generation !== state.generation) return;
    state.revisionDetails.set(key, { error: error.message });
  }
  if (generation !== state.generation) return;
  renderWorkDetail();
}

async function loadOverview(message = "Loading process status") {
  setLoading(true, message);
  nodes.content.setAttribute("aria-busy", "true");
  try {
    const overview = await requestJson(`${API_ROOT}/overview`);
    state.overview = overview;
    setSelection(overview.selection);
    render();
    nodes.error.textContent = "";
    nodes.input.removeAttribute("aria-invalid");
    announce(`${overview.selection.project} loaded. Process overview is visible.`);
    loadActivity();
    enrichWork();
  } catch (error) {
    renderFatal(error.message);
    announce(`Project data could not be loaded. ${error.message}`);
  } finally {
    setLoading(false);
    syncChrome();
  }
}

nodes.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.loading) return;
  nodes.error.textContent = "";
  nodes.input.removeAttribute("aria-invalid");
  setLoading(true, "Validating project path");
  try {
    const payload = await requestJson(`${API_ROOT}/projects/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: nodes.input.value }),
    });
    resetProjectData();
    setSelection(payload.project);
    state.view = "overview";
    await loadOverview("Project selected. Loading process status");
  } catch (error) {
    nodes.error.textContent = error.message;
    nodes.input.setAttribute("aria-invalid", "true");
    announce(`Project selection failed. ${error.message}`);
  } finally {
    setLoading(false);
  }
});

nodes.refresh.addEventListener("click", () => {
  resetProjectData();
  loadOverview("Refreshing verified process status");
});

nodes.nav.forEach((button) => button.addEventListener("click", () => {
  if (state.overview) switchView(button.dataset.view);
}));

(async function restoreSelection() {
  try {
    const payload = await requestJson(`${API_ROOT}/project`);
    if (payload.project) {
      setSelection(payload.project);
      await loadOverview("Restoring selected project");
    }
  } catch (error) {
    announce(`Studio could not restore the project selection. ${error.message}`);
  }
}());
