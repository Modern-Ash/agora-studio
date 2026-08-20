"use strict";

(function exposeDashboardModel(root) {
  const terminalStates = new Set(["completed", "done", "closed", "cancelled", "canceled", "failed"]);
  const inactiveSwarmStates = new Set(["completed", "closed", "cancelled", "canceled", "failed"]);

  function workKey(work) {
    return `${work.swarm_id}/${work.id}`;
  }

  function isWorkInProgress(work) {
    return !terminalStates.has(String(work.state || "").toLowerCase());
  }

  function isBlocked(work) {
    return String(work.operational_status || "").toLowerCase() === "blocked";
  }

  function activeSwarms(swarms) {
    return (swarms || []).filter(
      (swarm) => !inactiveSwarmStates.has(String(swarm.status || "").toLowerCase()),
    );
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
    const required = [...new Set(currentTransitions(lifecycle).flatMap(
      (transition) => transition.required_approval_roles || [],
    ))];
    if (required.length) {
      const satisfied = new Set((artifacts?.approvals?.records || []).map((item) => item.role));
      return required
        .filter((role) => !satisfied.has(role))
        .map((role) => ({ role, satisfied: false }));
    }
    return (artifacts?.approvals?.satisfaction || []).filter((item) => !item.satisfied);
  }

  function gateDecisionContext(work, swarms, detail) {
    const gate = pendingGates(detail?.lifecycle)[0] || null;
    const satisfied = new Set(
      (detail?.artifacts?.approvals?.records || []).map((item) => item.role),
    );
    const role = (gate?.required_approval_roles || []).find(
      (candidate) => !satisfied.has(candidate),
    ) || null;
    const swarm = (swarms || []).find((candidate) => candidate.id === work?.swarm_id);
    const actor = role ? swarm?.assignments?.[role] || null : null;
    const evidence = (detail?.artifacts?.evidence || []).filter(
      (record) => record.result === "success",
    );
    return {
      gate,
      role,
      actor,
      evidence,
      ready: Boolean(gate && role && actor && evidence.length),
    };
  }

  function evidenceMissing(work, detail) {
    if (!isWorkInProgress(work)) return false;
    const blockers = currentTransitions(detail?.lifecycle).flatMap(
      (transition) => transition.blockers || [],
    );
    if (blockers.some((blocker) => /evidence/i.test(String(blocker)))) return true;
    return !(work.evidence_results || []).includes("success");
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
      activeSwarms: activeSwarms(overview?.swarms).length,
      workInProgress: work.filter(isWorkInProgress).length,
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
