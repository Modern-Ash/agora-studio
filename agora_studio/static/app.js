"use strict";

const state = { overview: null, view: "overview", loading: false };
const viewNames = { overview: "Project overview", actors: "Actors", swarms: "Swarms", work: "Work", sessions: "Sessions" };

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
  nodes.refresh.disabled = loading || !state.overview;
  nodes.input.setAttribute("aria-busy", String(loading));
  nodes.refresh.classList.toggle("is-loading", loading);
  if (message) announce(message);
}

function setSelection(selection) {
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
  nodes.refresh.disabled = state.loading || !state.overview;
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

function render() {
  nodes.title.textContent = viewNames[state.view];
  syncNavigation();
  if (state.view === "overview") renderOverview();
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

nodes.refresh.addEventListener("click", () => loadOverview("Refreshing project data"));
nodes.nav.forEach((button) => button.addEventListener("click", () => {
  if (!state.overview) return;
  state.view = button.dataset.view;
  render();
  document.querySelector("#main-content").focus({ preventScroll: true });
  announce(`${viewNames[state.view]} is visible.`);
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
