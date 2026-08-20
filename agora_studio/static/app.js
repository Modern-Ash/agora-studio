"use strict";

const API_ROOT = "/api/v1";
const workTabs = ControlModel.tabs;
const viewNames = {
  overview: "Process overview",
  work: "Work control",
  swarms: "Swarms",
  actors: "Actors",
  activity: "Activity",
};

function newGateAction(key = null) {
  return {
    key,
    optionKey: null,
    reason: "",
    phase: "edit",
    prepared: null,
    preparing: false,
    submitting: false,
    authentication: { algorithm: "", fingerprint: "", signature: "" },
    error: "",
    result: "",
    refreshWarning: "",
  };
}

const state = {
  overview: null,
  activity: null,
  activityError: "",
  activityLoading: false,
  activityFilters: {
    type: "",
    actor: "",
    swarm_id: "",
    work_id: "",
    session_id: "",
    tool_run_id: "",
  },
  details: {},
  detailRequests: new Map(),
  controlRevision: 0,
  mutationRevision: 0,
  enrichmentLoading: false,
  generation: 0,
  gateAction: newGateAction(),
  selectionPath: "",
  selectedWork: null,
  selectedTab: "summary",
  selectedRevision: null,
  revisionDetails: new Map(),
  revisionRequest: null,
  view: "overview",
  loading: false,
  csrfToken: "",
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
  const request = { ...(options || {}) };
  if (request.method && request.method !== "GET") {
    request.headers = { ...(request.headers || {}), "X-Agora-Studio-CSRF": state.csrfToken };
  }
  const response = await fetch(path, request);
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

function blockerText(blocker) {
  return typeof blocker === "string" ? blocker : blocker?.message || blocker?.code || "Blocked";
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
  state.revisionRequest?.abort();
  state.detailRequests.forEach((request) => request.controller?.abort());
  state.generation += 1;
  state.activity = null;
  state.activityError = "";
  state.activityLoading = false;
  state.details = {};
  state.detailRequests = new Map();
  state.enrichmentLoading = false;
  state.gateAction = newGateAction();
  state.revisionDetails = new Map();
  state.selectedRevision = null;
  state.revisionRequest = null;
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
  const activeWork = (overview.work || []).filter(
    (work) => DashboardModel.isWorkInProgress(work, overview),
  ).slice(0, 4);

  const healthRail = element("section", { className: "health-rail", "aria-label": "Process health" }, [
    element("div", { className: "method-card" }, [
      element("span", { className: "metric-label", text: "Active Method Pack" }),
      element("strong", { text: methodPack }),
      element("small", { text: `${display(status.branch, "No branch")} · ${display(status.integration, "No integration")}` }),
    ]),
    metricCard("Active swarms", metrics.activeSwarms, `${(overview.swarms || []).length} total`, metrics.activeSwarms ? "accent" : "neutral"),
    metricCard("Work in progress", metrics.workInProgress, `${(overview.work || []).length} total`, metrics.workInProgress ? "accent" : "neutral"),
    metricCard("Blocked", metrics.blockedWork, "work items", metrics.blockedWork ? "danger" : "good"),
    metricCard("Pending approvals", metrics.pendingApprovals, "Core options ready", metrics.pendingApprovals ? "danger" : "good", detailPending),
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
        const assignments = DashboardModel.swarmAssignments(work, overview.swarms);
        const open = element("button", { className: "focus-row", type: "button", "aria-label": `Open ${work.title}` }, [
          element("span", { className: "state-stripe", "data-state": work.state, "aria-hidden": "true" }),
          element("span", { className: "focus-copy" }, [element("strong", { text: work.title || work.id }), element("small", { text: `${work.swarm_id}/${work.id}` })]),
          statusPill(work.state),
          element("span", { className: "focus-owner", text: assignments.length ? `${assignments.length} governed role${assignments.length === 1 ? "" : "s"}` : "No swarm roles" }),
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
  const assignments = DashboardModel.swarmAssignments(work, state.overview.swarms);
  const detail = state.details[key];
  const gateCount = DashboardModel.gateCount(detail);
  const blocked = DashboardModel.isBlocked(work, state.overview);
  const button = element("button", { className: `work-card${blocked ? " is-blocked" : ""}`, type: "button", "aria-label": `Open work item ${work.title || work.id}` }, [
    element("span", { className: "work-card-topline" }, [
      element("span", { className: "mono card-key", text: key }),
      statusPill(work.state),
    ]),
    element("strong", { className: "work-title", text: work.title || work.id }),
    element("span", { className: "assignment-line" }, [
      element("span", { className: "avatar", text: String(assignments.length).padStart(2, "0"), "aria-hidden": "true" }),
      element("span", {}, [
        element("b", { text: assignments.length ? `${assignments.length} swarm assignment${assignments.length === 1 ? "" : "s"}` : "No assignments" }),
        element("small", { text: assignments.map((item) => `${item.role}: ${item.actor}`).join(" · ") || "No role recorded" }),
      ]),
    ]),
    element("span", { className: `block-line${blocked ? " is-alert" : ""}` }, [
      element("span", { "aria-hidden": "true", text: blocked ? "!" : "✓" }),
      element("span", { text: blocked ? work.status_reason || "Blocked" : "No operational block" }),
    ]),
    element("span", { className: "card-footer" }, [
      element("span", { text: detail?.loading ? "Loading Core options…" : gateCount ? `${gateCount} governed gate${gateCount === 1 ? "" : "s"}` : detail?.errors?.length ? "Options unavailable" : "No gate options" }),
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
  const assignments = DashboardModel.swarmAssignments(work, state.overview.swarms);
  const options = DashboardModel.decisionOptions(detail);
  const blockers = options.flatMap((option) => option.blockers || []);
  const criteria = Object.entries(work.acceptance_criteria || {});
  return element("div", { className: "detail-grid" }, [
    element("section", { className: "detail-panel" }, [
      element("p", { className: "section-kicker", text: "Operating context" }),
      element("h3", { text: "Summary" }),
      element("p", { className: "detail-lead", text: work.description || "No durable description is recorded." }),
      definitionList([
        ["State", work.state],
        ["Operational", work.operational_status],
        ["Swarm assignments", assignments.map((item) => `${item.role}: ${item.actor}`).join(", ")],
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
      options.length
        ? element("div", { className: "gate-alert" }, [
          element("strong", { text: `${options.length} Core decision option${options.length === 1 ? "" : "s"}` }),
          element("span", { text: blockers.length ? blockers.map(blockerText).join("; ") : "At least one governed option is executable." }),
        ])
        : element("p", { className: "quiet-success", text: detail?.loading ? "Loading Core decision options…" : detail?.control?.gate_decision_options?.reason || "No governed gate decisions are available." }),
    ]),
  ]);
}

function revisionKey(work, revisionId) {
  return ControlModel.revisionToken(
    state.selectionPath,
    DashboardModel.workKey(work),
    revisionId,
  );
}

async function loadSpecificationRevision(work, revision) {
  state.revisionRequest?.abort();
  const controller = new AbortController();
  const generation = state.generation;
  const selectedWork = state.selectedWork;
  const key = revisionKey(work, revision.id);
  state.revisionRequest = controller;
  state.selectedRevision = revision.id;
  state.revisionDetails.set(key, { loading: true, error: "", data: null });
  renderWorkDetail();
  try {
    const query = `swarm=${encodeURIComponent(work.swarm_id)}&work=${encodeURIComponent(work.id)}`;
    const payload = await requestJson(
      `${API_ROOT}/specification-revisions/${encodeURIComponent(revision.id)}?${query}`,
      { signal: controller.signal },
    );
    if (
      generation !== state.generation
      || selectedWork !== state.selectedWork
      || state.selectedRevision !== revision.id
      || state.revisionRequest !== controller
    ) return;
    state.revisionDetails.set(key, { loading: false, error: "", data: payload.revision });
    announce(`${revision.subject || revision.id} revision detail loaded.`);
  } catch (error) {
    if (error.name === "AbortError") return;
    if (
      generation !== state.generation
      || selectedWork !== state.selectedWork
      || state.selectedRevision !== revision.id
      || state.revisionRequest !== controller
    ) return;
    state.revisionDetails.set(key, { loading: false, error: error.message, data: null });
    announce(`Specification revision could not be loaded. ${error.message}`);
  } finally {
    if (state.revisionRequest === controller) state.revisionRequest = null;
    if (
      generation === state.generation
      && selectedWork === state.selectedWork
      && state.selectedRevision === revision.id
    ) renderWorkDetail();
  }
}

function renderRevisionDetail(work) {
  if (!state.selectedRevision) {
    return element("section", { className: "detail-panel revision-detail" }, [
      element("p", { className: "section-kicker", text: "Revision detail" }),
      element("h3", { text: "Select a version" }),
      element("p", { text: "Content and bounded diff are loaded on demand from Agora Core." }),
    ]);
  }
  const record = state.revisionDetails.get(revisionKey(work, state.selectedRevision));
  if (!record || record.loading) return loadingRows("Loading specification revision detail");
  if (record.error) return notice("error", "Revision detail unavailable", record.error);
  const revision = record.data;
  if (!revision?.available) {
    return emptyState("REV—NA", "Revision unavailable", revision?.reason || "Core could not return this revision.");
  }
  const back = element("button", { className: "back-button", type: "button", text: "← Back to revision list" });
  back.addEventListener("click", () => {
    state.selectedRevision = null;
    renderWorkDetail();
    document.querySelector(".revision-list button")?.focus();
  });
  return element("section", { className: "detail-panel revision-detail", "aria-labelledby": "revision-detail-title" }, [
    back,
    element("p", { className: "section-kicker", text: revision.kind === "working-tree" ? "Working tree / not committed" : "Committed specification" }),
    element("h3", { id: "revision-detail-title", text: revision.subject || revision.revision_id }),
    definitionList([
      ["Revision", revision.revision_id],
      ["Commit", revision.sha],
      ["Previous", revision.previous_revision_id],
      ["Author", revision.author],
      ["Recorded", formatTime(revision.timestamp)],
      ["Size", `${revision.size_bytes} bytes`],
      ["Encoding", revision.encoding],
    ]),
    revision.content_truncated ? notice("partial", "Content truncated", "Core returned a bounded content extract.") : null,
    revision.content === null
      ? emptyState("TXT—NA", revision.binary ? "Binary specification" : "Content unavailable", revision.reason || "No text content is available.")
      : element("pre", { className: "revision-diff revision-content", text: revision.content }),
    revision.diff_truncated ? notice("partial", "Diff truncated", "Core returned a bounded diff extract.") : null,
    revision.diff === null
      ? null
      : element("div", {}, [
        element("h4", { text: "Diff" }),
        element("pre", { className: "revision-diff", text: revision.diff }),
      ]),
  ]);
}

function renderSpecTab(work, detail) {
  if (detail?.loading && !detail.control) return loadingRows("Loading specification history");
  if (!detail?.control) return emptyState("SPC—ERR", "Specification unavailable", detail?.errors?.join(" ") || "Core did not return work control data.");
  const specification = detail.control.specification_history || {};
  if (!specification.available) return emptyState("SPC—00", "No verified specification", specification.reason || "No single registered specification is available.");
  const revisions = specification.revisions || [];
  return element("div", { className: "detail-grid spec-grid" }, [
    element("section", { className: "detail-panel" }, [
      element("p", { className: "section-kicker", text: "Registered specification" }),
      element("h3", { className: "mono wrap", text: specification.uri }),
      revisions.length
        ? element("ol", { className: "revision-list" }, revisions.map((revision) => {
          const button = element("button", {
            className: `revision-button${state.selectedRevision === revision.id ? " is-selected" : ""}`,
            type: "button",
            "aria-current": state.selectedRevision === revision.id ? "true" : null,
          }, [
            element("strong", { className: "mono", text: revision.short_sha || revision.id }),
            element("span", { text: revision.subject || "Working tree" }),
            element("small", { text: `${revision.uncommitted ? "Working tree" : display(revision.author, "author unknown")} · ${formatTime(revision.timestamp)}` }),
          ]);
          button.addEventListener("click", () => loadSpecificationRevision(work, revision));
          return element("li", {}, [button]);
        }))
        : emptyState("REV—00", "No revisions", "The specification has no available Git history."),
    ]),
    renderRevisionDetail(work),
  ]);
}

function renderLifecycleTab(detail) {
  if (detail?.loading && !detail.control) return loadingRows("Loading lifecycle");
  if (!detail?.control?.lifecycle) return emptyState("LFC—00", "Lifecycle unavailable", detail?.errors?.join(" ") || "Core did not return lifecycle data.");
  const lifecycle = detail.control.lifecycle;
  const states = lifecycle.states || [];
  return element("div", { className: "lifecycle-panel" }, [
    element("div", { className: "process-track", role: "list", "aria-label": `${lifecycle.method} lifecycle states` }, states.map((item, index) =>
      element("div", { className: `process-node${item.id === lifecycle.current_state ? " is-current" : ""}${item.terminal ? " is-terminal" : ""}`, role: "listitem" }, [
        element("span", { className: "node-number", text: String(index + 1).padStart(2, "0") }),
        element("strong", { text: titleCase(item.id) }),
        element("small", { text: item.id === lifecycle.current_state ? "Current" : item.terminal ? "Terminal" : "Method state" }),
      ]),
    )),
    element("section", { className: "detail-panel" }, [
      element("p", { className: "section-kicker", text: "Method transitions" }),
      element("h3", { text: lifecycle.method }),
      element("ul", { className: "transition-list" }, (lifecycle.transitions || []).map((transition) =>
        element("li", { className: `${transition.source === lifecycle.current_state ? "is-traversed" : ""}${transition.blockers?.length ? " is-blocked" : ""}` }, [
          element("span", { className: "transition-path mono", text: `${transition.source} → ${transition.target}` }),
          element("span", { text: transition.gate_id || "No gate" }),
          transition.blockers?.length ? element("small", { text: transition.blockers.map(blockerText).join("; ") }) : element("small", { text: transition.available ? "Available now" : "Declared by method" }),
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
  if (detail?.loading && !detail.control) return loadingRows("Loading artifacts");
  if (!detail?.control) return emptyState("ART—ERR", "Artifacts unavailable", detail?.errors?.join(" ") || "No work control projection was returned.");
  return recordsTable("Artifacts", detail.control.artifacts, [
    { label: "Kind", render: (record) => statusPill(record.kind) },
    { label: "URI", render: (record) => element("span", { className: "mono wrap", text: record.uri }) },
    { label: "Produced by", render: (record) => record.produced_by },
    { label: "Recorded", render: (record) => formatTime(record.timestamp) },
  ], "No artifacts are durably registered for this work item.");
}

function renderEvidenceTab(detail) {
  if (detail?.loading && !detail.control) return loadingRows("Loading evidence");
  if (!detail?.control) return emptyState("EVD—ERR", "Evidence unavailable", detail?.errors?.join(" ") || "No work control projection was returned.");
  return recordsTable("Evidence", detail.control.evidence, [
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
    "core.schema-incompatible": "Core returned a projection Studio cannot safely trust.",
  };
  return messages[error.code] || error.message;
}

function gateCommand(option, reason, authentication = null) {
  return ControlModel.command(option, reason, authentication);
}

async function prepareGateDecision(work, detail) {
  const action = state.gateAction;
  const option = DashboardModel.findOption(detail, action.optionKey);
  if (!option || option.allowed !== true || !option.actor_id) {
    action.error = "Select an enabled action supplied by Agora Core.";
    renderWorkDetail();
    return;
  }
  if (!action.reason.trim()) {
    action.error = "A reason is required for every gate decision.";
    renderWorkDetail();
    document.querySelector("#gate-reason")?.focus();
    return;
  }
  action.reason = action.reason.trim();
  action.preparing = true;
  action.error = "";
  const generation = state.generation;
  renderWorkDetail();
  try {
    const payload = await requestJson(
      `${API_ROOT}/work-items/${encodeURIComponent(work.swarm_id)}/${encodeURIComponent(work.id)}/approvals/prepare`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(gateCommand(option, action.reason)),
      },
    );
    if (generation !== state.generation || state.gateAction !== action) return;
    action.prepared = payload.preparation;
    action.authentication = {
      algorithm: payload.preparation.authentication_algorithm || "ed25519",
      fingerprint: payload.preparation.authentication_fingerprint || "",
      signature: "",
    };
    action.phase = payload.preparation.authentication_required ? "sign" : "confirm";
    announce(
      payload.preparation.authentication_required
        ? "Canonical payload prepared. A detached signature is required."
        : "Gate decision prepared and ready for confirmation.",
    );
  } catch (error) {
    if (generation !== state.generation || state.gateAction !== action) return;
    action.error = gateErrorMessage(error);
    if (["command.stale-precondition", "command.gate-already-resolved"].includes(error.code)) {
      try {
        await refreshAfterGateDecision(work);
      } catch {
        action.error += " Studio could not refresh the durable projection.";
      }
    }
  } finally {
    if (generation !== state.generation || state.gateAction !== action) return;
    action.preparing = false;
    renderWorkDetail();
    document.querySelector(action.phase === "sign" ? "#detached-signature" : ".gate-confirmation button")?.focus();
  }
}

async function refreshAfterGateDecision(work) {
  const key = DashboardModel.workKey(work);
  const generation = state.generation;
  const selectionPath = state.selectionPath;
  const revision = ++state.mutationRevision;
  state.detailRequests.get(key)?.controller?.abort();
  state.detailRequests.delete(key);
  const [overview, activity, detail] = await Promise.all([
    requestJson(`${API_ROOT}/overview`),
    requestJson(`${API_ROOT}/activity?limit=500`),
    requestJson(
      `${API_ROOT}/work-items/${encodeURIComponent(work.swarm_id)}/${encodeURIComponent(work.id)}`,
    ),
  ]);
  if (
    revision !== state.mutationRevision
    || generation !== state.generation
    || selectionPath !== state.selectionPath
    || state.selectedWork !== key
  ) return false;
  state.overview = overview;
  state.activity = activity;
  state.details[key] = { loading: false, control: detail.control, errors: [] };
  return true;
}

async function submitGateDecision(work, detail) {
  if (state.gateAction.submitting) return;
  const action = state.gateAction;
  const option = DashboardModel.findOption(detail, action.optionKey);
  if (!option || option.allowed !== true || !action.prepared) return;
  const preparationIssue = ControlModel.preparationIssue(action.prepared, option);
  if (preparationIssue) {
    resetGatePreparation(action);
    action.error = preparationIssue;
    renderWorkDetail();
    document.querySelector("#gate-reason")?.focus();
    return;
  }
  let authentication = null;
  if (action.prepared.authentication_required) {
    authentication = {
      algorithm: action.authentication.algorithm.trim(),
      fingerprint: action.authentication.fingerprint.trim(),
      signature: action.authentication.signature.trim(),
    };
    const issue = ControlModel.authenticationIssue(action.prepared, authentication);
    if (issue) {
      action.error = issue;
      renderWorkDetail();
      document.querySelector("#detached-signature")?.focus();
      return;
    }
  }
  state.gateAction.submitting = true;
  state.gateAction.error = "";
  renderWorkDetail();
  let response;
  try {
    response = await requestJson(`${API_ROOT}/work-items/${encodeURIComponent(work.swarm_id)}/${encodeURIComponent(work.id)}/approvals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ControlModel.preparedCommand(action.prepared, authentication)),
    });
  } catch (error) {
    action.submitting = false;
    action.error = gateErrorMessage(error);
    if (["command.stale-precondition", "command.gate-already-resolved"].includes(error.code)) {
      const preservedError = action.error;
      resetGatePreparation(action);
      action.error = preservedError;
      try {
        await refreshAfterGateDecision(work);
      } catch {
        action.error += " Studio could not refresh the durable projection.";
      }
    }
    announce(`Gate decision failed. ${action.error}`);
    renderWorkDetail();
    return;
  }

  action.submitting = false;
  action.phase = "done";
  action.result = option.decision === "approved"
    ? "Approval was durably persisted by Agora Core."
    : "Rejection was durably persisted by Agora Core.";
  announce(action.result);
  try {
    await refreshAfterGateDecision(work);
  } catch {
    action.refreshWarning = "The decision is durable, but the follow-up refresh failed. Refresh before another action.";
    announce(`${action.result} ${action.refreshWarning}`);
  }
  renderWorkDetail();
}

function resetGatePreparation(action) {
  action.phase = "edit";
  action.prepared = null;
  action.authentication = { algorithm: "", fingerprint: "", signature: "" };
  action.error = "";
}

function renderPreparedDecision(work, detail, action, option) {
  const prepared = action.prepared;
  const confirm = element("button", {
    className: `primary-button decision-${option.decision}`,
    type: "button",
    text: action.submitting ? "Persisting…" : `Confirm ${option.decision}`,
    disabled: action.submitting ? "disabled" : null,
  });
  confirm.addEventListener("click", () => submitGateDecision(work, detail));
  const regenerate = element("button", { className: "back-button", type: "button", text: "Edit and regenerate", disabled: action.submitting ? "disabled" : null });
  regenerate.addEventListener("click", () => {
    resetGatePreparation(action);
    renderWorkDetail();
    document.querySelector("#gate-reason")?.focus();
  });
  const children = [
    element("p", { className: "section-kicker", text: prepared.authentication_required ? "Detached signature required" : "Confirm governed mutation" }),
    element("h3", { id: "gate-confirm-title", text: `${titleCase(option.decision)} / ${option.gate_id}` }),
    definitionList([
      ["Actor", prepared.actor_id],
      ["Role", prepared.role_id],
      ["Gate", prepared.gate_id],
      ["Decision", prepared.decision],
      ["Expected state", prepared.expected_state],
      ["Target state", prepared.transition_target],
      ["Fingerprint", prepared.authentication_fingerprint],
      ["Authorization digest", prepared.authorization_digest],
      ["Precondition digest", prepared.precondition_digest],
      ["Freshness", prepared.freshness],
    ]),
    element("div", { className: "canonical-command" }, [
      element("strong", { text: "Canonical reason" }),
      element("blockquote", { text: prepared.reason }),
      element("strong", { text: "Canonical evidence references" }),
      tags(prepared.evidence_references, "None"),
    ]),
  ];
  const payload = element("textarea", { id: "canonical-payload", rows: "8", readonly: "readonly", text: prepared.authorization_payload, "aria-label": "Canonical command payload" });
  const copy = element("button", { className: "back-button", type: "button", text: "Copy canonical payload" });
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(prepared.authorization_payload);
      announce("Canonical payload copied.");
    } catch {
      payload.focus();
      payload.select();
      announce("Clipboard access is unavailable. The canonical payload is selected for copying.");
    }
  });
  children.push(element("div", { className: "signature-payload" }, [payload, copy]));
  if (prepared.authentication_required) {
    const algorithm = element("input", { id: "signature-algorithm", value: action.authentication.algorithm, maxlength: "32", required: "required", autocomplete: "off" });
    const fingerprint = element("input", { id: "signature-fingerprint", value: action.authentication.fingerprint, pattern: "[0-9a-f]{64}", maxlength: "64", required: "required", autocomplete: "off" });
    const signature = element("textarea", { id: "detached-signature", rows: "5", maxlength: "8192", required: "required", autocomplete: "off", placeholder: "Paste the detached signature", text: action.authentication.signature });
    algorithm.addEventListener("input", () => { action.authentication.algorithm = algorithm.value; });
    fingerprint.addEventListener("input", () => { action.authentication.fingerprint = fingerprint.value; });
    signature.addEventListener("input", () => { action.authentication.signature = signature.value; });
    children.push(
      element("div", { className: "signature-fields" }, [
        element("label", { for: "signature-algorithm" }, [element("span", { text: "Algorithm" }), algorithm]),
        element("label", { for: "signature-fingerprint" }, [element("span", { text: "Fingerprint" }), fingerprint]),
        element("label", { for: "detached-signature" }, [element("span", { text: "Detached signature" }), signature]),
      ]),
    );
  }
  children.push(element("div", { className: "gate-actions" }, [confirm, regenerate]));
  return element("div", { className: "gate-confirmation", role: "alertdialog", "aria-labelledby": "gate-confirm-title" }, children);
}

function renderGateControl(work, detail) {
  const projection = DashboardModel.decisionProjection(detail);
  const options = DashboardModel.decisionOptions(detail);
  if (!projection) return detail?.loading ? loadingRows("Loading governed actions") : null;
  const key = DashboardModel.workKey(work);
  const action = state.gateAction.key === key ? state.gateAction : newGateAction(key);
  const selected = DashboardModel.findOption(detail, action.optionKey);
  let controls;
  if (action.phase === "done") {
    controls = element("div", {}, [
      notice("progress", "Durable response received", action.result),
      action.refreshWarning ? notice("partial", "Refresh required", action.refreshWarning) : null,
    ]);
  } else if (action.prepared && selected) {
    controls = renderPreparedDecision(work, detail, action, selected);
  } else {
    const optionsList = options.length
      ? element("fieldset", { className: "gate-option-list" }, [
        element("legend", { text: "Action calculated by Agora Core" }),
        ...options.map((option, index) => {
          const id = `gate-option-${index}`;
          const evidenceTypes = [...new Set([
            ...(option.required_evidence_types || []),
            ...Object.keys(option.evidence_references_by_type || {}),
          ])];
          const input = element("input", {
            id,
            type: "radio",
            name: "gate-option",
            value: DashboardModel.optionKey(option),
            checked: action.optionKey === DashboardModel.optionKey(option) ? "checked" : null,
            disabled: option.allowed === true ? null : "disabled",
          });
          input.addEventListener("change", () => {
            state.gateAction = newGateAction(key);
            state.gateAction.optionKey = input.value;
            state.gateAction.reason = action.reason;
            renderWorkDetail();
            document.querySelector("#gate-reason")?.focus();
          });
          return element("label", { className: `gate-option${option.allowed === true ? "" : " is-disabled"}`, for: id }, [
            input,
            element("span", {}, [
              element("strong", { text: `${titleCase(option.decision)} ${option.gate_id}` }),
              element("small", { text: `${option.transition_source} → ${option.transition_target} · ${option.role_id} · ${display(option.actor_id, "No authorized actor")}` }),
              evidenceTypes.length
                ? element("span", { className: "typed-evidence" }, evidenceTypes.map((kind) =>
                  element("small", {}, [
                    element("b", { text: `${kind}: ` }),
                    element("span", { text: (option.evidence_references_by_type?.[kind] || []).join(", ") || "missing" }),
                  ]),
                ))
                : null,
              option.blockers?.length ? element("small", { className: "option-blockers", text: option.blockers.map(blockerText).join("; ") }) : null,
            ]),
          ]);
        }),
      ])
      : emptyState("GATE—00", "No gate decisions available", projection.reason || "Core returned no governed options for this state.");
    const reason = element("textarea", { id: "gate-reason", name: "reason", rows: "4", required: "required", maxlength: "4000", text: action.reason, placeholder: "Explain the durable basis for this exact action." });
    reason.addEventListener("input", () => { action.reason = reason.value; });
    const form = element("form", { className: "gate-decision-form", novalidate: "novalidate" }, [
      optionsList,
      element("label", { for: "gate-reason" }, [element("span", { text: "Decision reason" }), reason]),
      element("div", { className: "gate-actions" }, [
        element("button", { className: "primary-button", type: "submit", text: action.preparing ? "Preparing…" : "Prepare exact action", disabled: selected && selected.allowed === true && !action.preparing ? null : "disabled" }),
      ]),
    ]);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      prepareGateDecision(work, detail);
    });
    controls = form;
  }
  return element("section", { className: "gate-control", "aria-labelledby": "gate-control-title" }, [
    element("div", { className: "gate-control-heading" }, [
      element("div", {}, [element("p", { className: "section-kicker", text: "Governed action" }), element("h3", { id: "gate-control-title", text: "Core decision options" })]),
      statusPill(projection.terminal ? "terminal" : projection.operational_status),
    ]),
    action.error ? notice("error", "Decision not persisted", action.error) : null,
    controls,
  ]);
}

function renderApprovalsTab(work, detail) {
  if (detail?.loading && !detail.control) return loadingRows("Loading approvals");
  if (!detail?.control) return emptyState("APR—ERR", "Approvals unavailable", detail?.errors?.join(" ") || "No work control projection was returned.");
  const records = detail.control.approvals || [];
  const approvals = records.length
    ? element("div", { className: "approval-grid" }, records.map((record) =>
      element("article", { className: `approval-card${record.decision === "approved" ? " is-satisfied" : " is-missing"}` }, [
      element("span", { className: "approval-mark", "aria-hidden": "true", text: record.decision === "approved" ? "✓" : "!" }),
      element("div", {}, [
        element("span", { className: "metric-label", text: titleCase(record.decision) }),
        element("h3", { text: record.role }),
        element("p", { text: `${record.actor} · ${record.note}` }),
        element("time", { datetime: record.timestamp, text: formatTime(record.timestamp) }),
      ]),
    ])))
    : emptyState("APR—00", "No durable gate decisions", "Agora Core has not recorded an approval or rejection for this work item.");
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
  const assignments = DashboardModel.swarmAssignments(work, state.overview.swarms);
  const back = element("button", { className: "back-button", type: "button", text: "← Back to board" });
  back.addEventListener("click", () => {
    state.revisionRequest?.abort();
    state.revisionRequest = null;
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
      const next = ControlModel.nextTab(tab, event.key);
      if (next !== tab) {
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
      element("div", { className: "detail-status" }, [statusPill(work.state), element("span", { text: assignments.map((item) => `${item.role}: ${item.actor}`).join(" · ") || "No swarm assignments recorded" })]),
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
    element("section", { className: "activity-toolbar activity-toolbar-six", "aria-label": "Activity filters" }, [
      activityFilter("Event type", "type"),
      activityFilter("Actor", "actor"),
      activityFilter("Swarm", "swarm_id"),
      activityFilter("Work", "work_id"),
      activityFilter("Session", "session_id"),
      activityFilter("Tool run", "tool_run_id"),
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
  state.revisionRequest?.abort();
  state.revisionRequest = null;
  state.view = view;
  state.selectedWork = null;
  state.selectedRevision = null;
  render();
  document.querySelector("#main-content").focus({ preventScroll: true });
  announce(`${viewNames[view]} is visible.`);
  if (view === "activity" && !state.activity) loadActivity();
}

function openWork(work) {
  state.revisionRequest?.abort();
  state.revisionRequest = null;
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
  if (state.detailRequests.has(key)) return state.detailRequests.get(key).promise;
  if (state.details[key] && !state.details[key].loading) return state.details[key];
  const generation = state.generation;
  const selectionPath = state.selectionPath;
  const revision = ++state.controlRevision;
  const controller = new AbortController();
  const request = (async () => {
    state.details[key] = { loading: true, control: null, errors: [] };
    if (state.view === "work" || state.view === "overview") render();
    let payload;
    let error = null;
    try {
      payload = await requestJson(
        `${API_ROOT}/work-items/${encodeURIComponent(work.swarm_id)}/${encodeURIComponent(work.id)}`,
        { signal: controller.signal },
      );
    } catch (caught) {
      if (caught.name === "AbortError") return null;
      error = caught;
    }
    const active = state.detailRequests.get(key);
    if (
      generation !== state.generation
      || selectionPath !== state.selectionPath
      || active?.revision !== revision
    ) return null;
    state.details[key] = {
      loading: false,
      control: payload?.control || null,
      errors: error ? [`Control projection: ${error.message}`] : [],
    };
    if (state.view === "work" || state.view === "overview") render();
    return state.details[key];
  })();
  state.detailRequests.set(key, { promise: request, controller, revision });
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
  state.revisionRequest?.abort();
  state.revisionRequest = null;
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
    state.csrfToken = payload.csrf_token || "";
    if (payload.project) {
      setSelection(payload.project);
      await loadOverview("Restoring selected project");
    }
  } catch (error) {
    announce(`Studio could not restore the project selection. ${error.message}`);
  }
}());
