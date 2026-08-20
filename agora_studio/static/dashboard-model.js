"use strict";

(function exposeDashboardModel(root) {

  function workKey(work) {
    return `${work.swarm_id}/${work.id}`;
  }

  function isWorkInProgress(work, detail = null) {
    const state = (detail?.lifecycle?.method?.states || []).find(
      (candidate) => candidate.id === work?.state,
    );
    return state ? state.terminal !== true : true;
  }

  function isBlocked(work) {
    return String(work.operational_status || "").toLowerCase() === "blocked";
  }

  function activeSwarms(swarms) {
    return (swarms || []).filter((swarm) => swarm.status === "active");
  }

  function assignmentFor(work, swarms) {
    const swarm = (swarms || []).find((candidate) => candidate.id === work.swarm_id);
    const entries = Object.entries(swarm?.assignments || {});
    if (!entries.length) return { role: null, actor: null, additional: 0 };
    const [role, actor] = entries[0];
    return { role, actor, additional: Math.max(0, entries.length - 1) };
  }

  function currentTransitions(lifecycle) {
    const current = lifecycle?.method?.current_state;
    return (lifecycle?.method?.transitions || []).filter(
      (transition) => transition.from === current,
    );
  }

  function pendingGates(lifecycle) {
    return currentTransitions(lifecycle)
      .filter((transition) => transition.gate && (transition.blockers || []).length)
      .map((transition) => ({
        id: transition.gate,
        target: transition.to,
        blockers: transition.blockers || [],
        required_approval_roles: transition.required_approval_roles || [],
      }));
  }

  function pendingApprovals(artifacts, lifecycle = null) {
    const missing = currentTransitions(lifecycle).flatMap((transition) =>
      (transition.blockers || [])
        .filter((blocker) => blocker?.category === "approval")
        .flatMap((blocker) => blocker.references || []));
    return [...new Set(missing)].map((role) => ({ role, satisfied: false }));
  }

  function gateDecisionContext(work, swarms, detail) {
    const gate = pendingGates(detail?.lifecycle)[0] || null;
    const role = (gate?.blockers || [])
      .filter((blocker) => blocker?.category === "approval")
      .flatMap((blocker) => blocker.references || [])[0] || null;
    const swarm = (swarms || []).find((candidate) => candidate.id === work?.swarm_id);
    const actor = role ? swarm?.assignments?.[role] || null : null;
    const evidence = detail?.artifacts?.evidence || [];
    return {
      gate,
      role,
      actor,
      evidence,
      ready: Boolean(gate && role && actor),
    };
  }

  function evidenceMissing(work, detail) {
    if (!isWorkInProgress(work, detail)) return false;
    const blockers = currentTransitions(detail?.lifecycle).flatMap(
      (transition) => transition.blockers || [],
    );
    return blockers.some((blocker) => blocker?.category === "evidence");
  }

  function stateOrder(work, details) {
    const ordered = [];
    const seen = new Set();
    (work || []).forEach((item) => {
      const lifecycle = details?.[workKey(item)]?.lifecycle;
      (lifecycle?.method?.states || []).forEach((state) => {
        if (!seen.has(state.id)) {
          seen.add(state.id);
          ordered.push(state.id);
        }
      });
    });
    (work || []).forEach((item) => {
      if (!seen.has(item.state)) {
        seen.add(item.state);
        ordered.push(item.state);
      }
    });
    return ordered;
  }

  function boardColumns(work, details) {
    const items = work || [];
    return stateOrder(items, details).map((state) => ({
      state,
      items: items.filter((item) => item.state === state),
    }));
  }

  function metrics(overview, details) {
    const work = overview?.work || [];
    const detailValues = Object.values(details || {});
    const failedSessions = (overview?.sessions || []).filter(
      (session) => String(session.status || "").toLowerCase() === "failed",
    ).length;
    return {
      activeSwarms: overview?.status?.swarm_statuses?.active ?? activeSwarms(overview?.swarms).length,
      workInProgress: work.filter((item) => isWorkInProgress(item, details?.[workKey(item)])).length,
      blockedWork: work.filter(isBlocked).length,
      pendingApprovals: detailValues.reduce(
        (total, detail) => total + pendingApprovals(detail.artifacts, detail.lifecycle).length,
        0,
      ),
      missingEvidence: work.filter((item) => evidenceMissing(item, details?.[workKey(item)])).length,
      failedSessions,
    };
  }

  function recentActivity(events, limit = 8) {
    return [...(events || [])]
      .sort((left, right) => String(right.timestamp).localeCompare(String(left.timestamp)))
      .slice(0, limit);
  }

  root.DashboardModel = {
    activeSwarms,
    assignmentFor,
    boardColumns,
    currentTransitions,
    evidenceMissing,
    gateDecisionContext,
    isBlocked,
    isWorkInProgress,
    metrics,
    pendingApprovals,
    pendingGates,
    recentActivity,
    workKey,
  };
}(globalThis));
