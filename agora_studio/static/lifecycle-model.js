"use strict";

(function exposeLifecycleModel(root) {
  function traversalCounts(traversals) {
    const counts = new Map();
    (traversals || []).forEach((item) => {
      const key = `${item.from}\u0000${item.to}`;
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return counts;
  }

  function layout(method, width = 920) {
    const states = Array.isArray(method.states) ? method.states : [];
    const transitions = Array.isArray(method.transitions) ? method.transitions : [];
    const stateIds = new Set(states.map((state) => state.id));
    const ranks = new Map();
    const initial = method.initial_state || states[0]?.id;
    if (initial) ranks.set(initial, 0);
    const queue = initial ? [initial] : [];
    while (queue.length) {
      const source = queue.shift();
      transitions.filter((edge) => edge.from === source).forEach((edge) => {
        if (stateIds.has(edge.to) && !ranks.has(edge.to)) {
          ranks.set(edge.to, ranks.get(source) + 1);
          queue.push(edge.to);
        }
      });
    }
    let orphanRank = Math.max(0, ...ranks.values()) + 1;
    states.forEach((state) => {
      if (!ranks.has(state.id)) ranks.set(state.id, orphanRank++);
    });
    const groups = new Map();
    states.forEach((state) => {
      const rank = ranks.get(state.id);
      if (!groups.has(rank)) groups.set(rank, []);
      groups.get(rank).push(state);
    });
    const rankCount = Math.max(1, ...ranks.values()) + 1;
    const horizontal = Math.max(150, (width - 140) / Math.max(1, rankCount - 1));
    const positions = {};
    let height = 260;
    [...groups.entries()].sort((a, b) => a[0] - b[0]).forEach(([rank, group]) => {
      group.forEach((state, index) => {
        positions[state.id] = { x: 70 + rank * horizontal, y: 80 + index * 118, rank };
        height = Math.max(height, 160 + index * 118);
      });
    });
    return {
      width: Math.max(width, 140 + (rankCount - 1) * horizontal),
      height,
      positions,
      edges: transitions.map((edge) => ({ ...edge, backEdge: ranks.get(edge.to) <= ranks.get(edge.from) })),
    };
  }

  function itemKey(kind, item) {
    return `${kind}:${item.id}`;
  }

  function selectionExists(projection, key) {
    if (!key) return false;
    const candidates = [
      ...(projection.method?.states || []).map((item) => itemKey("state", item)),
      ...(projection.method?.transitions || []).map((item) => itemKey("transition", item)),
      ...(projection.actual_path?.annotations || []).map((item) => itemKey("annotation", item)),
      ...(projection.specification?.revisions || []).map((item) => itemKey("revision", item)),
    ];
    return candidates.includes(key);
  }

  root.LifecycleModel = { itemKey, layout, selectionExists, traversalCounts };
}(globalThis));
