"use strict";

const activityFilters = {
  type: "Event type",
  actor: "Actor",
  swarm_id: "Swarm",
  work_id: "Work",
  session_id: "Session",
  tool_run_id: "Tool run",
};
const state = {
  overview: null,
  view: "overview",
  loading: false,
  activityLoading: false,
  activity: null,
  activityError: "",
  activityFilters: Object.fromEntries(Object.keys(activityFilters).map((key) => [key, ""])),
  selectedEvent: null,
  lifecycleLoading: false,
  lifecycle: null,
  lifecycleError: "",
  lifecycleWork: null,
  selectedLifecycleItem: null,
  revisionDetails: new Map(),
  lifecycleLayers: { topology: true, path: true, revisions: true },
  lifecycleScale: 1,
  artifactsLoading: false,
  artifacts: null,
  artifactsError: "",
  artifactsWork: null,
  selectedArtifactsItem: null,
  requestSerial: 0,
  selectionPath: "",
};
const viewNames = { overview: "Project overview", actors: "Actors", swarms: "Swarms", work: "Work", sessions: "Sessions", activity: "Activity", lifecycle: "Lifecycle", artifacts: "Artifacts" };

const nodes = {
  form: document.querySelector("#project-form"),
  input: document.querySelector("#project-path"),
  error: document.querySelector("#project-path-error"),
  open: document.querySelector("#open-button"),
  refresh: document.querySelector("#refresh-button"),
  title: document.querySelector("#view-title"),
  content: document.querySelector("#content"),
  live: document.querySelector("#live-status"),
  selection: document.querySelector("#selected-project"),
  selectionName: document.querySelector("#selected-project-name"),
  nav: [...document.querySelectorAll("[data-view]")],
};

function element(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(options)) {
    if (value === undefined || value === null) continue;
    if (name === "text") node.textContent = String(value);
    else if (name === "className") node.className = value;
    else node.setAttribute(name, String(value));
  }
  for (const child of children.flat()) {
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function svgElement(tag, options = {}, children = []) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [name, value] of Object.entries(options)) {
    if (value === undefined || value === null) continue;
    if (name === "text") node.textContent = String(value);
    else if (name === "className") node.setAttribute("class", value);
    else node.setAttribute(name, String(value));
  }
  for (const child of children.flat()) node.append(child);
  return node;
}

function replaceContent(...children) {
  nodes.content.replaceChildren(...children);
  nodes.content.style.animation = "none";
  requestAnimationFrame(() => { nodes.content.style.animation = ""; });
}

function announce(message) { nodes.live.textContent = message; }

async function requestJson(path, options) {
  const response = await fetch(path, options);
  let payload;
  try { payload = await response.json(); }
  catch { throw new Error("Studio returned an unreadable response."); }
  if (!response.ok) throw new Error(payload.reason || "Studio could not complete the request.");
  return payload;
}

function setLoading(loading, message) {
  state.loading = loading;
  nodes.open.disabled = loading;
  nodes.refresh.disabled = loading || state.activityLoading || state.lifecycleLoading || state.artifactsLoading || !state.overview;
  nodes.input.setAttribute("aria-busy", String(loading));
  nodes.refresh.classList.toggle("is-loading", loading);
  if (message) announce(message);
}

function setSelection(selection) {
  if (state.selectionPath && state.selectionPath !== selection.path) {
    state.requestSerial += 1;
    state.activityLoading = false;
    state.activity = null;
    state.activityError = "";
    state.selectedEvent = null;
    state.lifecycleLoading = false;
    state.lifecycle = null;
    state.lifecycleError = "";
    state.lifecycleWork = null;
    state.selectedLifecycleItem = null;
    state.revisionDetails = new Map();
    state.activityFilters = Object.fromEntries(Object.keys(activityFilters).map((key) => [key, ""]));
    state.artifactsLoading = false;
    state.artifacts = null;
    state.artifactsError = "";
    state.artifactsWork = null;
    state.selectedArtifactsItem = null;
  }
  state.selectionPath = selection.path;
  nodes.selection.hidden = false;
  nodes.selectionName.textContent = selection.project;
  nodes.selectionName.title = selection.path;
  nodes.input.value = selection.path;
}

function syncNavigation() {
  nodes.nav.forEach((button) => {
    button.disabled = !state.overview;
    const active = button.dataset.view === state.view;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  nodes.refresh.disabled = state.loading || state.activityLoading || state.lifecycleLoading || !state.overview;
}

function display(value, fallback = "—") {
  if (value === undefined || value === null || value === "") return fallback;
  return String(value);
}

function tags(values) {
  const wrapper = element("div", { className: "tag-list" });
  const items = Array.isArray(values) ? values : [];
  if (!items.length) wrapper.append(element("span", { className: "muted", text: "None" }));
  else items.forEach((value) => wrapper.append(element("span", { className: "tag", text: value })));
  return wrapper;
}

function statusPill(value) {
  const healthy = ["active", "running", "ready", "completed", "success"].includes(String(value).toLowerCase());
  return element("span", { className: `status-pill ${healthy ? "is-good" : "is-alert"}`, text: display(value) });
}

function viewHeading(kicker, title, description) {
  return element("div", { className: "view-heading" }, [
    element("div", {}, [element("p", { className: "section-kicker", text: kicker }), element("h2", { text: title })]),
    element("p", { text: description }),
  ]);
}

function renderOverview() {
  const data = state.overview;
  const status = data.status || {};
  const counts = status.counts || {};
  const identity = [
    ["Project", status.project || data.selection.project],
    ["Branch", status.branch],
    ["Method", status.default_method],
    ["Integration", status.integration],
  ];
  const countItems = ["actors", "swarms", "work", "sessions", "tool-runs"];

  const identityStrip = element("div", { className: "identity-strip" }, identity.map(([label, value]) =>
    element("article", { className: "identity-item" }, [
      element("span", { className: "panel-label", text: label }),
      element("strong", { text: display(value) }),
    ])
  ));

  const metricGrid = element("div", { className: "metric-grid" }, countItems.map((key) =>
    element("article", { className: "metric" }, [
      element("span", { className: "panel-label", text: key }),
      element("strong", { text: display(counts[key], "0") }),
    ])
  ));

  const distributions = element("div", { className: "distribution" });
  const groups = [["Swarm status", status.swarm_statuses], ["Work state", status.work_states]];
  groups.forEach(([label, values]) => {
    const entries = Object.entries(values || {});
    const total = Math.max(1, entries.reduce((sum, [, amount]) => sum + Number(amount || 0), 0));
    distributions.append(element("div", { className: "distribution-row" }, [
      element("span", { className: "panel-label", text: label }),
      ...entries.map(([name, amount]) => element("div", {}, [
        element("div", { className: "distribution-head" }, [element("span", { text: name }), element("strong", { text: amount })]),
        element("div", { className: "distribution-track" }, [element("div", { className: "distribution-fill", style: `width:${Math.max(3, Number(amount) / total * 100)}%` })]),
      ])),
      ...(!entries.length ? [element("span", { className: "healthy", text: "No lifecycle records" })] : []),
    ]));
  });

  const attentionList = element("ul", { className: "attention-list" });
  const attentionEntries = Object.entries(status.attention || {});
  const populated = attentionEntries.filter(([, values]) => Array.isArray(values) && values.length);
  if (!populated.length) attentionList.append(element("li", {}, [element("span", { className: "healthy", text: "No items need attention" })]));
  populated.forEach(([name, values]) => attentionList.append(element("li", {}, [
    element("strong", { text: name.replaceAll("-", " ") }),
    element("span", { text: values.join(" · "), title: values.join(" · ") }),
  ])));

  replaceContent(
    viewHeading("01 / Snapshot", "Delivery at a glance", "A current read from Agora's durable project records."),
    identityStrip,
    metricGrid,
    element("div", { className: "dashboard-grid" }, [
      element("section", { className: "panel", "aria-labelledby": "lifecycle-title" }, [element("h3", { id: "lifecycle-title", text: "Lifecycle distribution" }), distributions]),
      element("section", { className: "panel", "aria-labelledby": "attention-title" }, [element("h3", { id: "attention-title", text: "Attention queue" }), attentionList]),
    ])
  );
}

function renderTable(config) {
  const rows = Array.isArray(state.overview[config.key]) ? state.overview[config.key] : [];
  const table = element("table", { className: "data-table" });
  const headRow = element("tr");
  config.columns.forEach((column) => headRow.append(element("th", { scope: "col", text: column.label })));
  table.append(element("thead", {}, [headRow]));
  const body = element("tbody");
  rows.forEach((record) => {
    const row = element("tr");
    config.columns.forEach((column) => {
      const rendered = column.render(record);
      const cell = element("td", { "data-label": column.label });
      cell.append(rendered instanceof Node ? rendered : document.createTextNode(display(rendered)));
      row.append(cell);
    });
    body.append(row);
  });
  table.append(body);
  const frameChildren = rows.length ? [table] : [element("p", { className: "empty-table", text: `No ${config.title.toLowerCase()} are registered.` })];
  replaceContent(
    viewHeading(config.kicker, config.title, config.description),
    element("div", { className: "data-frame" }, frameChildren)
  );
}

const tableViews = {
  actors: {
    key: "actors", kicker: "02 / Participants", title: "Actors", description: "Identities and capabilities admitted to this project.",
    columns: [
      { label: "Actor", render: (r) => element("strong", { text: r.name }) },
      { label: "Reference", render: (r) => element("span", { className: "mono", text: r.reference, title: r.reference }) },
      { label: "Kind", render: (r) => statusPill(r.kind) },
      { label: "Capabilities", render: (r) => tags(r.capabilities) },
      { label: "Authentication", render: (r) => r.authentication_required ? "Required" : "Not required" },
    ],
  },
  swarms: {
    key: "swarms", kicker: "03 / Delivery", title: "Swarms", description: "Active delivery structures, methods, and role ownership.",
    columns: [
      { label: "Swarm", render: (r) => element("strong", { className: "mono", text: r.id, title: r.id }) },
      { label: "Method", render: (r) => r.method },
      { label: "Status", render: (r) => statusPill(r.status) },
      { label: "Branch", render: (r) => element("span", { className: "mono", text: r.branch, title: r.branch }) },
      { label: "Objective", render: (r) => r.objective },
      { label: "Assignments", render: (r) => tags(Object.entries(r.assignments || {}).map(([role, actor]) => `${role}: ${actor}`)) },
    ],
  },
  work: {
    key: "work", kicker: "04 / Lifecycle", title: "Work", description: "Governed increments and their artifact, evidence, and criteria readiness.",
    columns: [
      { label: "Work", render: (r) => element("strong", { className: "mono", text: `${r.swarm_id}/${r.id}`, title: `${r.swarm_id}/${r.id}` }) },
      { label: "Title", render: (r) => r.title },
      { label: "State", render: (r) => statusPill(r.state) },
      { label: "Operational", render: (r) => statusPill(r.operational_status) },
      { label: "Criteria", render: (r) => `${(r.satisfied_criteria || []).length} / ${Object.keys(r.acceptance_criteria || {}).length}` },
      { label: "Readiness", render: (r) => tags([`${(r.artifact_kinds || []).length} artifacts`, `${(r.evidence_results || []).filter((v) => v === "success").length} successful evidence`]) },
    ],
  },
  sessions: {
    key: "sessions", kicker: "05 / Runtime", title: "Sessions", description: "Bounded agent and human executions recorded by Agora.",
    columns: [
      { label: "Session", render: (r) => element("span", { className: "mono", text: r.id, title: r.id }) },
      { label: "Actor", render: (r) => r.actor },
      { label: "Context", render: (r) => `${display(r.swarm_id)} / ${display(r.work_id)}` },
      { label: "Status", render: (r) => statusPill(r.status) },
      { label: "Created", render: (r) => element("time", { datetime: r.created_at, text: display(r.created_at) }) },
    ],
  },
};

function activityKey(event) {
  return ActivityModel.stableKey(event);
}

function activityFamily(type) {
  const family = String(type || "").split(".")[0];
  return ["project", "actor", "swarm", "work", "session", "tool", "artifact", "evidence", "approval"].includes(family) ? family : "other";
}

function localTime(timestamp) {
  const parsed = new Date(timestamp);
  return Number.isNaN(parsed.valueOf()) ? display(timestamp) : parsed.toLocaleString([], { dateStyle: "medium", timeStyle: "medium" });
}

function definitionList(entries, className = "detail-facts") {
  const list = element("dl", { className });
  entries.forEach(([label, value]) => {
    list.append(element("div", {}, [
      element("dt", { text: label }),
      element("dd", { className: "mono wrap-anywhere", text: display(value, "Not recorded"), title: display(value, "Not recorded") }),
    ]));
  });
  return list;
}

function relatedActivity(event) {
  const related = [];
  if (event.swarm_id && event.work_id) {
    const matches = ActivityModel.relatedWork(state.activity.events, event);
    if (matches.length) {
      const list = element("ul", { className: "related-list" });
      matches.forEach((match) => list.append(element("li", {}, [
        element("strong", { text: match.type }),
        element("span", { text: match.summary }),
        match.source
          ? element("a", { href: match.source, className: "source-link mono", text: "Durable source" })
          : element("span", { className: "muted", text: "Durable source not recorded" }),
      ])));
      related.push(element("section", { "aria-labelledby": "related-work-title" }, [
        element("h4", { id: "related-work-title", text: "Loaded work records" }), list,
      ]));
    }
  }
  if (event.session_id) {
    const session = ActivityModel.matchingSession(state.overview.sessions || [], event);
    if (session) {
      related.push(element("section", { "aria-labelledby": "related-session-title" }, [
        element("h4", { id: "related-session-title", text: "Loaded session summary" }),
        definitionList([
          ["Status", session.status],
          ["Actor", session.actor],
          ["Created", session.created_at],
        ], "session-facts"),
      ]));
    }
  }
  return related.length ? related : [element("p", { className: "muted", text: "No related artifact, evidence, or session summary is available in the loaded records." })];
}

function eventDetail(event) {
  const titleId = `event-detail-${Math.abs(activityKey(event).split("").reduce((value, character) => ((value * 31) + character.charCodeAt(0)) | 0, 0))}`;
  return element("article", { className: "event-detail", "aria-labelledby": titleId }, [
    element("div", { className: "detail-heading" }, [
      element("p", { className: "section-kicker", text: "Selected durable event" }),
      element("h3", { id: titleId, text: event.type }),
      element("p", { className: "detail-summary", text: event.summary }),
    ]),
    definitionList([
      ["Exact time", event.timestamp],
      ["Actor", event.actor || "Unattributed"],
      ["Swarm", event.swarm_id],
      ["Work", event.work_id],
      ["Session", event.session_id],
      ["Tool run", event.tool_run_id],
    ]),
    element("div", { className: "source-block" }, [
      element("span", { className: "panel-label", text: "Durable source" }),
      event.source
        ? element("a", { href: event.source, className: "source-link mono wrap-anywhere", text: event.source })
        : element("span", { className: "mono muted", text: "Not recorded" }),
    ]),
    element("div", { className: "related-block" }, [
      element("h3", { text: "Related loaded records" }),
      ...relatedActivity(event),
    ]),
  ]);
}

function activityFilterOptions(events, key) {
  return ActivityModel.options(events, key);
}

function filteredActivity(events) {
  return ActivityModel.filterEvents(events, state.activityFilters);
}

function renderActivitySkeleton() {
  replaceContent(
    viewHeading("06 / Chronicle", "Durable activity", "Loading the governed Activity Ledger."),
    element("section", { className: "activity-loading", "aria-busy": "true", "aria-label": "Loading activity" }, [
      ...[0, 1, 2, 3].map(() => element("div", { className: "skeleton-row" }, [element("span"), element("span"), element("span")])),
    ])
  );
}

function renderActivity() {
  if (state.activityLoading && !state.activity) {
    renderActivitySkeleton();
    return;
  }
  if (!state.activity && state.activityError) {
    const retry = element("button", { className: "primary-button", type: "button", text: "Retry" });
    retry.addEventListener("click", () => loadActivity());
    replaceContent(
      viewHeading("06 / Chronicle", "Durable activity", "A chronological account of governed project actions."),
      element("div", { className: "error-panel", role: "alert" }, [
        element("p", { className: "section-kicker", text: "Activity read interrupted" }),
        element("h2", { text: "The project stayed selected." }),
        element("p", { text: state.activityError }),
        retry,
      ])
    );
    return;
  }
  if (!state.activity) {
    replaceContent(
      viewHeading("06 / Chronicle", "Durable activity", "A chronological account of governed project actions."),
      element("div", { className: "empty-state compact-empty" }, [
        element("span", { className: "empty-index", text: "06 / WAITING" }),
        element("h2", { text: "Activity is ready to load." }),
        element("button", { className: "primary-button", type: "button", id: "activity-load", text: "Load activity" }),
      ])
    );
    document.querySelector("#activity-load").addEventListener("click", () => loadActivity());
    return;
  }

  const events = state.activity.events;
  const visible = filteredActivity(events);
  const activeCount = Object.values(state.activityFilters).filter(Boolean).length;
  const controls = element("div", { className: "filter-grid" });
  Object.entries(activityFilters).forEach(([key, label]) => {
    const select = element("select", { id: `activity-filter-${key}`, "data-activity-filter": key });
    select.append(element("option", { value: "", text: "All" }));
    activityFilterOptions(events, key).forEach((value) => select.append(element("option", { value, text: value, title: value })));
    select.value = state.activityFilters[key];
    select.addEventListener("change", () => {
      state.activityFilters[key] = select.value;
      renderActivity();
      announce(`${filteredActivity(events).length} activity events match the current filters.`);
    });
    controls.append(element("label", { className: "filter-field", for: select.id }, [
      element("span", { text: label }), select,
    ]));
  });
  const clear = element("button", { className: "secondary-button", type: "button", text: "Clear filters" });
  clear.disabled = activeCount === 0;
  clear.addEventListener("click", () => {
    state.activityFilters = Object.fromEntries(Object.keys(activityFilters).map((key) => [key, ""]));
    renderActivity();
    announce(`${events.length} activity events visible. Filters cleared.`);
  });

  const toolbar = element("section", { className: "activity-toolbar", "aria-labelledby": "activity-filter-title" }, [
    element("div", { className: "toolbar-heading" }, [
      element("div", {}, [element("h3", { id: "activity-filter-title", text: "Filter the ledger" }), element("p", { text: "Dimensions combine with AND semantics." })]),
      element("div", { className: "result-summary", "aria-live": "polite" }, [
        element("strong", { text: `${visible.length} / ${events.length}` }),
        element("span", { text: `events · ${activeCount} active ${activeCount === 1 ? "filter" : "filters"}` }),
      ]),
    ]),
    controls,
    element("div", { className: "toolbar-actions" }, [clear]),
  ]);

  const heading = viewHeading("06 / Chronicle", "Durable activity", "Oldest to newest, attributed to Agora's recorded actors and governed scope.");
  const children = [heading];
  if (state.activityError) {
    const retry = element("button", { className: "secondary-button", type: "button", text: "Retry" });
    retry.addEventListener("click", () => loadActivity());
    children.push(element("div", { className: "inline-error", role: "alert" }, [
      element("span", { text: state.activityError }), retry,
    ]));
  }
  children.push(toolbar);
  if (state.activity.meta.limit_reached) {
    children.push(element("p", { className: "bounded-notice", text: `Showing a bounded recent slice of ${state.activity.meta.limit} events; earlier durable activity may exist.` }));
  }
  if (!events.length) {
    children.push(element("div", { className: "empty-state compact-empty" }, [
      element("span", { className: "empty-index", text: "06 / EMPTY" }),
      element("h2", { text: "No durable activity yet." }),
      element("p", { text: "Agora has not recorded Activity Ledger events for this selected project." }),
    ]));
  } else if (!visible.length) {
    const noMatchClear = element("button", { className: "primary-button", type: "button", text: "Clear filters" });
    noMatchClear.addEventListener("click", () => {
      state.activityFilters = Object.fromEntries(Object.keys(activityFilters).map((key) => [key, ""]));
      renderActivity();
      announce(`${events.length} activity events visible. Filters cleared.`);
    });
    children.push(element("div", { className: "no-matches" }, [
      element("h3", { text: "No loaded events match." }),
      element("p", { text: "The Activity Ledger is available, but this filter combination has no results." }), noMatchClear,
    ]));
  } else {
    const selected = visible.find((event) => activityKey(event) === state.selectedEvent) || null;
    if (!selected && state.selectedEvent) state.selectedEvent = null;
    const timeline = element("ol", { className: "timeline-list", "aria-label": "Durable activity, oldest to newest" });
    visible.forEach((event, index) => {
      const key = activityKey(event);
      const active = key === state.selectedEvent;
      const button = element("button", {
        className: `event-button family-${activityFamily(event.type)}${active ? " is-selected" : ""}`,
        type: "button",
        "aria-current": active ? "true" : "false",
        "aria-label": `${event.type}, ${event.timestamp}, ${event.actor || "Unattributed"}`,
      }, [
        element("span", { className: "event-index", text: String(index + 1).padStart(2, "0") }),
        element("span", { className: "event-copy" }, [
          element("span", { className: "event-head" }, [
            element("strong", { text: event.type }),
            element("time", { datetime: event.timestamp, title: event.timestamp, text: localTime(event.timestamp) }),
          ]),
          element("span", { className: "event-summary", text: event.summary }),
          element("span", { className: "event-meta" }, [
            element("span", { text: event.actor || "Unattributed" }),
            ...[["swarm", event.swarm_id], ["work", event.work_id], ["session", event.session_id], ["tool", event.tool_run_id]]
              .filter(([, value]) => value)
              .map(([label, value]) => element("span", { className: "scope-chip", text: `${label}: ${value}`, title: value })),
          ]),
        ]),
      ]);
      button.addEventListener("click", () => {
        state.selectedEvent = key;
        renderActivity();
        announce(`${event.type} selected. Event details updated.`);
      });
      timeline.append(element("li", { className: "timeline-item" }, [button, ...(active ? [eventDetail(event)] : [])]));
    });
    children.push(timeline);
  }
  replaceContent(...children);
}

async function loadActivity(message = "Loading durable activity") {
  if (!state.overview || state.activityLoading) return;
  const request = ++state.requestSerial;
  const projectPath = state.selectionPath;
  const previousSelection = state.selectedEvent;
  state.activityLoading = true;
  state.activityError = "";
  nodes.refresh.disabled = true;
  if (!state.activity) renderActivitySkeleton();
  announce(message);
  try {
    const payload = await requestJson("/api/activity?limit=500");
    if (request !== state.requestSerial || projectPath !== state.selectionPath) return;
    const ordered = ActivityModel.sortChronologically(payload.events);
    state.activity = { ...payload, events: ordered };
    state.selectedEvent = previousSelection && ordered.some((event) => activityKey(event) === previousSelection) ? previousSelection : null;
    state.activityLoading = false;
    renderActivity();
    announce(`${ordered.length} durable activity events loaded in chronological order.${state.selectedEvent ? " The selected event was preserved." : previousSelection ? " The previous selection is no longer available." : ""}`);
  } catch (error) {
    if (request !== state.requestSerial || projectPath !== state.selectionPath) return;
    state.activityError = error.message;
    state.activityLoading = false;
    renderActivity();
    announce(`Activity could not be loaded. ${error.message}`);
  } finally {
    if (request === state.requestSerial) {
      state.activityLoading = false;
      syncNavigation();
    }
  }
}

function lifecycleWorkPicker() {
  const select = element("select", { id: "lifecycle-work-select", "aria-label": "Work item" });
  select.append(element("option", { value: "", text: "Select work…" }));
  (state.overview.work || []).forEach((work) => {
    const value = `${work.swarm_id}/${work.id}`;
    select.append(element("option", { value, text: `${work.title || work.id} · ${work.state}`, title: value }));
  });
  select.value = state.lifecycleWork ? `${state.lifecycleWork.swarm_id}/${state.lifecycleWork.id}` : "";
  select.addEventListener("change", () => {
    const [swarmId, ...workParts] = select.value.split("/");
    const workId = workParts.join("/");
    state.lifecycleWork = (state.overview.work || []).find((item) => item.swarm_id === swarmId && item.id === workId) || null;
    state.selectedLifecycleItem = null;
    state.revisionDetails = new Map();
    if (state.lifecycleWork) loadLifecycle("Loading lifecycle for selected work");
    else {
      state.lifecycle = null;
      renderLifecycle();
    }
  });
  return select;
}

function renderLifecycleSkeleton() {
  replaceContent(
    viewHeading("07 / System map", "Lifecycle", "Loading Method topology, durable path, and specification history."),
    element("section", { className: "lifecycle-loading", "aria-busy": "true", "aria-label": "Loading lifecycle" }, [
      element("div", { className: "graph-skeleton" }, [...[0, 1, 2, 3].map(() => element("span"))]),
    ])
  );
}

function lifecycleSelect(kind, item) {
  state.selectedLifecycleItem = LifecycleModel.itemKey(kind, item);
  renderLifecycle();
  announce(`${kind} ${item.id} selected. Lifecycle details updated.`);
  if (kind === "revision" && !state.revisionDetails.has(item.id)) loadRevisionDetail(item.id);
}

function keyboardSelect(node, callback) {
  node.addEventListener("click", callback);
  node.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      callback();
    }
  });
}

function lifecycleDetail(projection) {
  const selected = state.selectedLifecycleItem;
  if (!selected) {
    return element("aside", { className: "lifecycle-detail", "aria-label": "Lifecycle detail" }, [
      element("p", { className: "section-kicker", text: "Inspect the map" }),
      element("h3", { text: "Select a governed record" }),
      element("p", { className: "muted", text: "Choose a state, transition, annotation, or specification revision. Exact durable relationships appear here without inferred attribution." }),
    ]);
  }
  const [kind, id] = selected.split(/:(.*)/s);
  const collections = {
    state: projection.method.states || [], transition: projection.method.transitions || [],
    annotation: projection.actual_path.annotations || [], revision: projection.specification.revisions || [],
  };
  const item = (collections[kind] || []).find((record) => record.id === id);
  if (!item) {
    state.selectedLifecycleItem = null;
    return lifecycleDetail(projection);
  }
  let facts;
  if (kind === "state") facts = [["State", item.id], ["Current", item.current ? "Yes" : "No"], ["Initial", item.initial ? "Yes" : "No"], ["Terminal", item.terminal ? "Yes" : "No"]];
  else if (kind === "transition") facts = [["From", item.from], ["To", item.to], ["Roles", (item.roles || []).join(", ")], ["Gate", item.gate], ["Availability", item.available ? "Available now" : "Not currently available"]];
  else if (kind === "annotation") facts = [["Type", item.type], ["Time", item.timestamp], ["Actor", item.actor], ["Session", item.session_id]];
  else facts = [["Revision", item.short_sha], ["Kind", item.kind], ["Time", item.timestamp], ["Author", item.author], ["Work state", item.work_state], ["Approval", item.approved === false ? "Not approved" : "Not recorded"]];
  const children = [
    element("p", { className: "section-kicker", text: `Selected ${kind}` }),
    element("h3", { className: "wrap-anywhere", text: item.subject || item.summary || item.id }),
    definitionList(facts, "detail-facts"),
  ];
  if (kind === "transition") {
    const selectedTransition = item;
    const occurrences = (projection.actual_path.traversals || []).filter((occurrence) => occurrence.from === selectedTransition.from && occurrence.to === selectedTransition.to);
    if (occurrences.length) children.push(element("section", { className: "related-block", "aria-labelledby": "traversal-detail-title" }, [
      element("h4", { id: "traversal-detail-title", text: `Durable traversals · ${occurrences.length}` }),
      element("ul", { className: "related-list" }, occurrences.map((occurrence) => element("li", {}, [
        element("strong", { text: occurrence.timestamp }),
        element("span", { text: `${occurrence.actor || "Unattributed"}${occurrence.session_id ? ` · ${occurrence.session_id}` : " · session not recorded"}` }),
        occurrence.source ? element("a", { href: occurrence.source, className: "source-link mono", text: "Durable source" }) : element("span", { className: "muted", text: "Source not recorded" }),
      ]))),
    ]));
  }
  if (item.blockers?.length) children.push(element("div", { className: "gate-blockers" }, [element("strong", { text: "Recorded blockers" }), ...item.blockers.map((value) => element("span", { text: value }))]));
  if (item.source) children.push(element("a", { href: item.source, className: "source-link mono wrap-anywhere", text: item.source }));
  if (kind === "revision") {
    const detail = state.revisionDetails.get(item.id);
    if (detail === "loading") children.push(element("p", { className: "muted", text: "Loading bounded revision detail…" }));
    else if (detail?.error) children.push(element("p", { className: "inline-error", role: "alert", text: detail.error }));
    else if (detail?.detail) {
      children.push(element("div", { className: "revision-summary" }, [
        element("span", { className: "panel-label", text: `${detail.detail.line_count} diff lines${detail.detail.truncated ? " · truncated" : ""}` }),
        tags(detail.detail.changed_headings),
        element("pre", { className: "revision-diff", text: detail.detail.text || "No textual changes are available for this revision." }),
      ]));
    }
  }
  return element("aside", { className: "lifecycle-detail", "aria-label": "Lifecycle detail" }, children);
}

function lifecycleGraph(projection) {
  const layout = LifecycleModel.layout(projection.method, 920);
  const revisions = projection.specification.revisions || [];
  const revisionY = layout.height + 58;
  const graphHeight = layout.height + (state.lifecycleLayers.revisions && revisions.length ? 150 : 20);
  const width = Math.max(layout.width, state.lifecycleLayers.revisions ? (revisions.length * 120) + 80 : 0);
  const graph = svgElement("svg", {
    className: "lifecycle-svg", viewBox: `0 0 ${width} ${graphHeight}`,
    width: Math.round(width * state.lifecycleScale), height: Math.round(graphHeight * state.lifecycleScale),
    role: "group", "aria-label": "Method lifecycle and specification evolution graph",
  });
  graph.append(svgElement("defs", {}, [svgElement("marker", {
    id: "graph-arrow", viewBox: "0 0 10 10", refX: "8", refY: "5", markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse",
  }, [svgElement("path", { d: "M 0 0 L 10 5 L 0 10 z", className: "graph-arrow" })])]));
  const counts = LifecycleModel.traversalCounts(projection.actual_path.traversals);
  layout.edges.forEach((edge) => {
    const used = counts.get(`${edge.from}\u0000${edge.to}`) || 0;
    if ((!state.lifecycleLayers.topology && !used) || (!state.lifecycleLayers.path && used && !state.lifecycleLayers.topology)) return;
    const source = layout.positions[edge.from];
    const target = layout.positions[edge.to];
    if (!source || !target) return;
    const x1 = source.x + 58;
    const x2 = target.x - 58;
    const pathData = edge.backEdge
      ? `M ${x1} ${source.y} C ${x1 + 55} ${source.y + 76}, ${x2 - 55} ${target.y + 76}, ${x2} ${target.y}`
      : `M ${x1} ${source.y} C ${(x1 + x2) / 2} ${source.y}, ${(x1 + x2) / 2} ${target.y}, ${x2} ${target.y}`;
    const path = svgElement("path", {
      d: pathData,
      className: `graph-edge${used && state.lifecycleLayers.path ? " is-traversed" : ""}${edge.available ? " is-available" : ""}${edge.blockers?.length ? " is-blocked" : ""}`,
      "marker-end": "url(#graph-arrow)",
      tabindex: "0", role: "button",
      "aria-label": `${edge.from} to ${edge.to}; ${used ? `traversed ${used} times` : "not traversed"}${edge.blockers?.length ? "; blocked" : ""}`,
    });
    keyboardSelect(path, () => lifecycleSelect("transition", edge));
    graph.append(path);
    if (used && state.lifecycleLayers.path) graph.append(svgElement("text", { x: (x1 + x2) / 2, y: (source.y + target.y) / 2 - 8, className: "edge-count", text: `×${used}` }));
  });
  if (state.lifecycleLayers.topology || state.lifecycleLayers.path) {
    (projection.method.states || []).forEach((item) => {
      const position = layout.positions[item.id];
      const group = svgElement("g", {
        className: `graph-node${item.current ? " is-current" : ""}${item.initial ? " is-initial" : ""}${item.terminal ? " is-terminal" : ""}`,
        transform: `translate(${position.x} ${position.y})`, tabindex: "0", role: "button",
        "aria-label": `${item.id} state${item.current ? ", current" : ""}${item.initial ? ", initial" : ""}${item.terminal ? ", terminal" : ""}`,
      }, [
        svgElement("rect", { x: -58, y: -29, width: 116, height: 58, rx: 6 }),
        svgElement("text", { x: 0, y: 4, "text-anchor": "middle", text: item.id }),
        ...(item.current ? [svgElement("text", { x: 0, y: 45, "text-anchor": "middle", className: "node-note", text: "CURRENT" })] : []),
      ]);
      keyboardSelect(group, () => lifecycleSelect("state", item));
      graph.append(group);
    });
  }
  if (state.lifecycleLayers.revisions && revisions.length) {
    graph.append(svgElement("line", { x1: 30, y1: revisionY, x2: width - 30, y2: revisionY, className: "revision-rail" }));
    revisions.forEach((item, index) => {
      const x = 65 + index * Math.max(110, (width - 130) / Math.max(1, revisions.length - 1));
      const group = svgElement("g", {
        className: `revision-node${item.uncommitted ? " is-working" : ""}`,
        transform: `translate(${Math.min(x, width - 65)} ${revisionY})`, tabindex: "0", role: "button",
        "aria-label": `${item.subject}; ${item.uncommitted ? "uncommitted and unapproved" : item.short_sha}`,
      }, [
        svgElement(item.uncommitted ? "rect" : "circle", item.uncommitted ? { x: -9, y: -9, width: 18, height: 18 } : { cx: 0, cy: 0, r: 9 }),
        svgElement("text", { x: 0, y: 28, "text-anchor": "middle", text: item.short_sha }),
        svgElement("text", { x: 0, y: 47, "text-anchor": "middle", className: "node-note", text: item.work_state || "STATE UNKNOWN" }),
      ]);
      keyboardSelect(group, () => lifecycleSelect("revision", item));
      graph.append(group);
    });
  }
  return element("div", { className: "graph-scroll", tabindex: "0", "aria-label": "Scrollable lifecycle graph" }, [graph]);
}

function lifecycleTextView(projection) {
  const section = element("section", { className: "lifecycle-text", "aria-labelledby": "lifecycle-text-title" }, [
    element("h3", { id: "lifecycle-text-title", text: "Text equivalent" }),
    element("p", { className: "muted", text: "The same governed states, transitions, and specification revisions in reading order." }),
  ]);
  const traversed = LifecycleModel.traversalCounts(projection.actual_path.traversals);
  const tables = [
    ["States", ["State", "Markers"], (projection.method.states || []).map((item) => [item.id, [item.initial && "Initial", item.current && "Current", item.terminal && "Terminal"].filter(Boolean).join(", ") || "Declared"])],
    ["Transitions", ["Transition", "Roles / gate", "Traversal", "Status"], (projection.method.transitions || []).map((item) => [
      `${item.from} → ${item.to}`, `${(item.roles || []).join(", ") || "Not recorded"}${item.gate ? ` · gate ${item.gate}` : ""}`,
      `${traversed.get(`${item.from}\u0000${item.to}`) || 0} durable`, item.blockers?.length ? `Blocked: ${item.blockers.join("; ")}` : item.available ? "Available now" : "Allowed",
    ])],
    ["Specification revisions", ["Revision", "Author / time", "Work state"], (projection.specification.revisions || []).map((item) => [
      item.subject || item.short_sha, `${item.author || "Uncommitted"}${item.timestamp ? ` · ${item.timestamp}` : ""}`, item.work_state || "Not recorded",
    ])],
  ];
  tables.forEach(([title, headings, rows]) => {
    const table = element("table", { className: "compact-table" }, [
      element("caption", { text: title }),
      element("thead", {}, [element("tr", {}, headings.map((heading) => element("th", { scope: "col", text: heading })))]),
      element("tbody", {}, rows.length ? rows.map((row) => element("tr", {}, row.map((value) => element("td", { text: value })))) : [element("tr", {}, [element("td", { colspan: String(headings.length), text: "Unavailable" })])]),
    ]);
    section.append(table);
  });
  return section;
}

function lifecycleToolbar(projection) {
  const toolbar = element("section", { className: "lifecycle-toolbar", "aria-label": "Lifecycle controls" });
  toolbar.append(element("label", { className: "work-picker" }, [element("span", { text: "Work item" }), lifecycleWorkPicker()]));
  const layerControls = element("fieldset", { className: "layer-controls" }, [element("legend", { text: "Layers" })]);
  [["topology", "Method"], ["path", "Actual path"], ["revisions", "Spec revisions"]].forEach(([key, label]) => {
    const input = element("input", { type: "checkbox", id: `layer-${key}` });
    input.checked = state.lifecycleLayers[key];
    input.addEventListener("change", () => { state.lifecycleLayers[key] = input.checked; renderLifecycle(); });
    layerControls.append(element("label", { for: input.id }, [input, element("span", { text: label })]));
  });
  toolbar.append(layerControls);
  const fit = element("button", { className: "secondary-button", type: "button", text: "Fit graph" });
  fit.addEventListener("click", () => { state.lifecycleScale = .82; renderLifecycle(); announce("Lifecycle graph fitted to the work surface."); });
  const reset = element("button", { className: "secondary-button", type: "button", text: "Reset view" });
  reset.addEventListener("click", () => { state.lifecycleScale = 1; renderLifecycle(); announce("Lifecycle graph view reset."); });
  toolbar.append(element("div", { className: "graph-actions" }, [fit, reset]));
  return toolbar;
}

function renderLifecycle() {
  if (state.lifecycleLoading && !state.lifecycle) return renderLifecycleSkeleton();
  const heading = viewHeading("07 / System map", "Lifecycle", "Allowed topology, traversed history, and Git-backed specification evolution for one work item.");
  if (!state.lifecycleWork) {
    replaceContent(heading, element("div", { className: "empty-state compact-empty" }, [
      element("span", { className: "empty-index", text: "07 / SELECT" }),
      element("h2", { text: "Choose work to map." }),
      element("p", { text: "Lifecycle reads stay bounded to one exact swarm and work item." }),
      element("label", { className: "standalone-work-picker" }, [element("span", { className: "panel-label", text: "Work item" }), lifecycleWorkPicker()]),
    ]));
    return;
  }
  if (!state.lifecycle && state.lifecycleError) {
    const retry = element("button", { className: "primary-button", type: "button", text: "Retry" });
    retry.addEventListener("click", () => loadLifecycle());
    replaceContent(heading, element("div", { className: "error-panel", role: "alert" }, [element("h2", { text: "The last project read stayed intact." }), element("p", { text: state.lifecycleError }), retry]));
    return;
  }
  if (!state.lifecycle) return renderLifecycleSkeleton();
  const projection = state.lifecycle;
  if (!LifecycleModel.selectionExists(projection, state.selectedLifecycleItem)) state.selectedLifecycleItem = null;
  const children = [heading];
  if (state.lifecycleError) {
    const retry = element("button", { className: "secondary-button", type: "button", text: "Retry" });
    retry.addEventListener("click", () => loadLifecycle());
    children.push(element("div", { className: "inline-error", role: "alert" }, [element("span", { text: state.lifecycleError }), retry]));
  }
  children.push(lifecycleToolbar(projection));
  if (projection.diagnostics?.length) children.push(element("div", { className: "partial-notice", role: "status" }, [element("strong", { text: "Verified partial view" }), ...projection.diagnostics.map((item) => element("span", { text: item }))]));
  if (!projection.method.available) {
    children.push(element("div", { className: "no-matches" }, [element("h3", { text: "Method topology is unavailable." }), element("p", { text: "The durable work state remains visible in the text summary without a guessed graph." })]));
  }
  children.push(element("div", { className: "lifecycle-workspace" }, [
    element("section", { className: "graph-surface", "aria-label": "Lifecycle map" }, [lifecycleGraph(projection)]),
    lifecycleDetail(projection),
  ]));
  if (projection.actual_path.annotations?.length) children.push(element("section", { className: "annotation-strip", "aria-labelledby": "annotations-title" }, [
    element("h3", { id: "annotations-title", text: "Path annotations" }),
    ...projection.actual_path.annotations.map((item) => {
      const button = element("button", { type: "button", className: "annotation-button", text: `${item.type} · ${item.summary}` });
      button.addEventListener("click", () => lifecycleSelect("annotation", item));
      return button;
    }),
  ]));
  children.push(lifecycleTextView(projection));
  replaceContent(...children);
}

async function loadLifecycle(message = "Loading lifecycle") {
  if (!state.lifecycleWork || state.lifecycleLoading) return;
  const request = ++state.requestSerial;
  const projectPath = state.selectionPath;
  const scope = `${state.lifecycleWork.swarm_id}/${state.lifecycleWork.id}`;
  state.lifecycleLoading = true;
  state.lifecycleError = "";
  nodes.refresh.disabled = true;
  if (!state.lifecycle) renderLifecycleSkeleton();
  announce(message);
  try {
    const query = `swarm=${encodeURIComponent(state.lifecycleWork.swarm_id)}&work=${encodeURIComponent(state.lifecycleWork.id)}`;
    const payload = await requestJson(`/api/lifecycle?${query}`);
    if (request !== state.requestSerial || projectPath !== state.selectionPath || scope !== `${state.lifecycleWork?.swarm_id}/${state.lifecycleWork?.id}`) return;
    state.lifecycle = payload;
    state.lifecycleLoading = false;
    renderLifecycle();
    announce(`Lifecycle loaded for ${scope}.${payload.availability.partial ? " Some layers are explicitly unavailable." : ""}`);
  } catch (error) {
    if (request !== state.requestSerial || projectPath !== state.selectionPath) return;
    state.lifecycleError = error.message;
    state.lifecycleLoading = false;
    renderLifecycle();
    announce(`Lifecycle could not be loaded. ${error.message}`);
  } finally {
    if (request === state.requestSerial) {
      state.lifecycleLoading = false;
      syncNavigation();
    }
  }
}

async function loadRevisionDetail(revision) {
  if (!state.lifecycleWork || state.revisionDetails.has(revision)) return;
  const request = state.requestSerial;
  const projectPath = state.selectionPath;
  state.revisionDetails.set(revision, "loading");
  renderLifecycle();
  try {
    const query = `swarm=${encodeURIComponent(state.lifecycleWork.swarm_id)}&work=${encodeURIComponent(state.lifecycleWork.id)}&revision=${encodeURIComponent(revision)}`;
    const payload = await requestJson(`/api/lifecycle/revision?${query}`);
    if (request !== state.requestSerial || projectPath !== state.selectionPath) return;
    state.revisionDetails.set(revision, payload);
  } catch (error) {
    if (request !== state.requestSerial || projectPath !== state.selectionPath) return;
    state.revisionDetails.set(revision, { error: error.message });
  }
  renderLifecycle();
}

function artifactsWorkPicker() {
  const select = element("select", { id: "artifacts-work-select", "aria-label": "Work item" });
  select.append(element("option", { value: "", text: "Select work…" }));
  (state.overview.work || []).forEach((work) => {
    const value = `${work.swarm_id}/${work.id}`;
    select.append(element("option", { value, text: `${work.title || work.id} · ${work.state}`, title: value }));
  });
  select.value = state.artifactsWork ? `${state.artifactsWork.swarm_id}/${state.artifactsWork.id}` : "";
  select.addEventListener("change", () => {
    const [swarmId, ...workParts] = select.value.split("/");
    const workId = workParts.join("/");
    state.artifactsWork = (state.overview.work || []).find((item) => item.swarm_id === swarmId && item.id === workId) || null;
    state.selectedArtifactsItem = null;
    if (state.artifactsWork) loadArtifacts("Loading artifacts for selected work");
    else {
      state.artifacts = null;
      renderArtifacts();
    }
  });
  return select;
}

function renderArtifactsSkeleton() {
  replaceContent(
    viewHeading("08 / Provenance", "Artifacts", "Loading durable artifacts, evidence, and approvals."),
    element("section", { className: "activity-loading", "aria-busy": "true", "aria-label": "Loading artifacts" }, [
      ...[0, 1, 2].map(() => element("div", { className: "skeleton-row" }, [element("span"), element("span"), element("span")])),
    ])
  );
}

function traceabilityNote(item) {
  if (!ArtifactsModel.hasTraceability(item)) {
    return element("span", { className: "muted", text: "No linked session or tool run is recorded." });
  }
  const trace = item.traceability;
  return element("div", { className: "trace-note" }, [
    trace.session_id ? element("span", { text: `Session: ${trace.session_id}` }) : null,
    trace.tool_run_id ? element("span", { text: `Tool run: ${trace.tool_run_id}` }) : null,
  ].filter(Boolean));
}

function artifactsDetail(projection) {
  const found = ArtifactsModel.findSelected(projection, state.selectedArtifactsItem);
  if (!found) {
    return element("aside", { className: "lifecycle-detail", "aria-label": "Artifacts detail" }, [
      element("p", { className: "section-kicker", text: "Inspect a record" }),
      element("h3", { text: "Select an artifact, evidence, or approval record" }),
      element("p", { className: "muted", text: "Full identifiers and, when a durable Agora record establishes it, the originating session or tool run appear here." }),
    ]);
  }
  const { kind, item } = found;
  let facts;
  if (kind === "artifact") facts = [["Kind", item.kind], ["URI", item.uri], ["Produced by", item.produced_by], ["Timestamp", item.timestamp]];
  else if (kind === "evidence") facts = [["Type", item.type], ["Result", item.result], ["Produced by", item.produced_by], ["Timestamp", item.timestamp]];
  else facts = [["Role", item.role], ["Approved by", item.approved_by], ["Note", item.note], ["Timestamp", item.timestamp]];
  const children = [
    element("p", { className: "section-kicker", text: `Selected ${kind}` }),
    element("h3", { className: "wrap-anywhere", text: item.kind || item.type || item.role }),
    definitionList(facts, "detail-facts"),
  ];
  if (kind === "evidence" && item.artifact_references?.length) {
    children.push(element("div", { className: "related-block" }, [
      element("h4", { text: "Artifact references" }),
      tags(item.artifact_references),
    ]));
  }
  children.push(element("div", { className: "related-block" }, [
    element("h4", { text: "Traceability" }),
    traceabilityNote(item),
  ]));
  return element("aside", { className: "lifecycle-detail", "aria-label": "Artifacts detail" }, children);
}

function artifactsSelect(kind, item) {
  state.selectedArtifactsItem = ArtifactsModel.itemKey(kind, item);
  renderArtifacts();
  announce(`${kind} ${item.id} selected. Details updated.`);
}

function recordButton(kind, item, label, meta, index = 0) {
  const active = state.selectedArtifactsItem === ArtifactsModel.itemKey(kind, item);
  const button = element("button", {
    className: `event-button family-${kind}${active ? " is-selected" : ""}`,
    type: "button",
    "aria-current": active ? "true" : "false",
    "aria-label": `${label}. ${meta}`,
  }, [
    element("span", { className: "event-index", text: String(index + 1).padStart(2, "0") }),
    element("span", { className: "event-copy" }, [
      element("span", { className: "event-head" }, [element("strong", { text: label })]),
      element("span", { className: "event-meta", text: meta }),
    ]),
  ]);
  keyboardSelect(button, () => artifactsSelect(kind, item));
  return button;
}

function renderArtifactsSection(title, description, emptyMessage, items, rowBuilder) {
  const body = items.length
    ? element("ol", { className: "timeline-list", "aria-label": title }, items.map((item, index) => element("li", { className: "timeline-item" }, [rowBuilder(item, index)])))
    : element("p", { className: "empty-table", text: emptyMessage });
  return element("section", { className: "panel", "aria-label": title }, [
    element("h3", { text: title }),
    element("p", { className: "muted", text: description }),
    body,
  ]);
}

function renderApprovalsSection(projection) {
  const satisfaction = projection.approvals.satisfaction;
  const records = projection.approvals.records;
  if (!satisfaction.length) {
    return element("section", { className: "panel", "aria-label": "Approvals" }, [
      element("h3", { text: "Approvals" }),
      element("p", { className: "empty-table", text: "No approval roles are required for this work item." }),
    ]);
  }
  const list = element("ol", { className: "timeline-list", "aria-label": "Required approval roles" });
  satisfaction.forEach(({ role, satisfied }, index) => {
    const record = records.find((item) => item.role === role);
    const label = `${satisfied ? "✓ Satisfied" : "○ Missing"} · ${role}`;
    if (record) {
      list.append(element("li", { className: "timeline-item" }, [
        recordButton("approval", record, label, `${record.approved_by} · ${record.timestamp}`, index),
      ]));
    } else {
      list.append(element("li", { className: "timeline-item" }, [
        element("div", { className: "event-button family-approval is-unsatisfied", role: "text", "aria-label": label }, [
          element("span", { className: "event-index", text: String(index + 1).padStart(2, "0") }),
          element("span", { className: "event-copy" }, [element("span", { className: "event-head" }, [element("strong", { text: label })]), element("span", { className: "event-meta", text: "No approval record yet" })]),
        ]),
      ]));
    }
  });
  return element("section", { className: "panel", "aria-label": "Approvals" }, [
    element("h3", { text: "Approvals" }),
    element("p", { className: "muted", text: "Required roles and their durable satisfaction state." }),
    list,
  ]);
}

function renderArtifacts() {
  if (state.artifactsLoading && !state.artifacts) return renderArtifactsSkeleton();
  const heading = viewHeading("08 / Provenance", "Artifacts", "Registered artifacts, evidence, and required approvals for one selected work item.");
  if (!state.artifactsWork) {
    replaceContent(heading, element("div", { className: "empty-state compact-empty" }, [
      element("span", { className: "empty-index", text: "08 / SELECT" }),
      element("h2", { text: "Choose work to inspect." }),
      element("p", { text: "Artifacts, evidence, and approvals stay bounded to one exact swarm and work item." }),
      element("label", { className: "standalone-work-picker" }, [element("span", { className: "panel-label", text: "Work item" }), artifactsWorkPicker()]),
    ]));
    return;
  }
  if (!state.artifacts && state.artifactsError) {
    const retry = element("button", { className: "primary-button", type: "button", text: "Retry" });
    retry.addEventListener("click", () => loadArtifacts());
    replaceContent(heading, element("div", { className: "error-panel", role: "alert" }, [element("h2", { text: "The last project read stayed intact." }), element("p", { text: state.artifactsError }), retry]));
    return;
  }
  if (!state.artifacts) return renderArtifactsSkeleton();
  const projection = state.artifacts;
  if (!ArtifactsModel.selectionExists(projection, state.selectedArtifactsItem)) state.selectedArtifactsItem = null;
  const children = [heading];
  if (state.artifactsError) {
    const retry = element("button", { className: "secondary-button", type: "button", text: "Retry" });
    retry.addEventListener("click", () => loadArtifacts());
    children.push(element("div", { className: "inline-error", role: "alert" }, [element("span", { text: state.artifactsError }), retry]));
  }
  children.push(element("section", { className: "lifecycle-toolbar", "aria-label": "Artifacts controls" }, [
    element("label", { className: "work-picker" }, [element("span", { text: "Work item" }), artifactsWorkPicker()]),
  ]));
  if (projection.diagnostics?.length) children.push(element("div", { className: "partial-notice", role: "status" }, [element("strong", { text: "Verified partial view" }), ...projection.diagnostics.map((item) => element("span", { text: item }))]));

  const artifactsSection = renderArtifactsSection(
    "Artifacts", "Every artifact registered durably for this work item.", "No artifacts are registered for this work item.",
    projection.artifacts, (item, index) => recordButton("artifact", item, item.kind, `${item.uri} · ${item.produced_by}`, index)
  );
  const evidenceSection = renderArtifactsSection(
    "Evidence", "Every evidence record registered durably for this work item.", "No evidence has been recorded for this work item.",
    projection.evidence, (item, index) => recordButton("evidence", item, `${item.result === "success" ? "✓" : "✗"} ${item.type}`, `${item.result} · ${item.produced_by}`, index)
  );
  const approvalsSection = renderApprovalsSection(projection);

  children.push(element("div", { className: "lifecycle-workspace" }, [
    element("div", { className: "artifacts-panels" }, [artifactsSection, evidenceSection, approvalsSection]),
    artifactsDetail(projection),
  ]));
  replaceContent(...children);
}

async function loadArtifacts(message = "Loading artifacts") {
  if (!state.artifactsWork || state.artifactsLoading) return;
  const request = ++state.requestSerial;
  const projectPath = state.selectionPath;
  const scope = `${state.artifactsWork.swarm_id}/${state.artifactsWork.id}`;
  state.artifactsLoading = true;
  state.artifactsError = "";
  nodes.refresh.disabled = true;
  if (!state.artifacts) renderArtifactsSkeleton();
  announce(message);
  try {
    const query = `swarm=${encodeURIComponent(state.artifactsWork.swarm_id)}&work=${encodeURIComponent(state.artifactsWork.id)}`;
    const payload = await requestJson(`/api/artifacts?${query}`);
    if (request !== state.requestSerial || projectPath !== state.selectionPath || scope !== `${state.artifactsWork?.swarm_id}/${state.artifactsWork?.id}`) return;
    state.artifacts = payload;
    state.artifactsLoading = false;
    renderArtifacts();
    announce(`Artifacts loaded for ${scope}: ${payload.artifacts.length} artifacts, ${payload.evidence.length} evidence records, ${payload.approvals.satisfaction.length} required approval roles.`);
  } catch (error) {
    if (request !== state.requestSerial || projectPath !== state.selectionPath) return;
    state.artifactsError = error.message;
    state.artifactsLoading = false;
    renderArtifacts();
    announce(`Artifacts could not be loaded. ${error.message}`);
  } finally {
    if (request === state.requestSerial) {
      state.artifactsLoading = false;
      syncNavigation();
    }
  }
}

function render() {
  nodes.title.textContent = viewNames[state.view];
  syncNavigation();
  if (state.view === "overview") renderOverview();
  else if (state.view === "activity") renderActivity();
  else if (state.view === "lifecycle") renderLifecycle();
  else if (state.view === "artifacts") renderArtifacts();
  else renderTable(tableViews[state.view]);
}

function renderFailure(message) {
  replaceContent(element("div", { className: "error-panel" }, [
    element("p", { className: "section-kicker", text: "Read interrupted" }),
    element("h2", { text: "The project stayed selected." }),
    element("p", { text: message }),
    element("p", { className: "muted", text: "Check the project's Agora records, then refresh or select another path." }),
  ]));
}

async function loadOverview(message = "Loading project data") {
  setLoading(true, message);
  try {
    const overview = await requestJson("/api/overview");
    state.overview = overview;
    setSelection(overview.selection);
    render();
    nodes.error.textContent = "";
    nodes.input.removeAttribute("aria-invalid");
    announce(`${overview.selection.project} loaded. ${viewNames[state.view]} is visible.`);
    if (state.view === "activity" && !state.activity) await loadActivity("Project selected. Loading durable activity");
    if (state.view === "lifecycle" && state.lifecycleWork && !state.lifecycle) await loadLifecycle("Project selected. Loading lifecycle");
    if (state.view === "artifacts" && state.artifactsWork && !state.artifacts) await loadArtifacts("Project selected. Loading artifacts");
  } catch (error) {
    renderFailure(error.message);
    announce(`Project data could not be loaded. ${error.message}`);
  } finally {
    setLoading(false);
    syncNavigation();
  }
}

nodes.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.loading) return;
  nodes.error.textContent = "";
  nodes.input.removeAttribute("aria-invalid");
  setLoading(true, "Validating project path");
  try {
    const payload = await requestJson("/api/projects/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: nodes.input.value }),
    });
    setSelection(payload.project);
    await loadOverview("Project selected. Loading durable state");
  } catch (error) {
    nodes.error.textContent = error.message;
    nodes.input.setAttribute("aria-invalid", "true");
    announce(`Project selection failed. ${error.message}`);
  } finally {
    setLoading(false);
  }
});

nodes.refresh.addEventListener("click", () => {
  if (state.view === "activity") loadActivity("Refreshing durable activity");
  else if (state.view === "lifecycle" && state.lifecycleWork) loadLifecycle("Refreshing lifecycle");
  else if (state.view === "artifacts" && state.artifactsWork) loadArtifacts("Refreshing artifacts");
  else loadOverview("Refreshing project data");
});
nodes.nav.forEach((button) => button.addEventListener("click", async () => {
  if (!state.overview) return;
  state.view = button.dataset.view;
  render();
  document.querySelector("#main-content").focus({ preventScroll: true });
  announce(`${viewNames[state.view]} is visible.`);
  if (state.view === "activity" && !state.activity) await loadActivity();
  if (state.view === "lifecycle" && state.lifecycleWork && !state.lifecycle) await loadLifecycle();
  if (state.view === "artifacts" && state.artifactsWork && !state.artifacts) await loadArtifacts();
}));

(async function restoreSelection() {
  try {
    const payload = await requestJson("/api/project");
    if (payload.project) {
      setSelection(payload.project);
      await loadOverview("Restoring selected project");
    }
  } catch (error) {
    announce(`Studio could not restore the project selection. ${error.message}`);
  }
})();
