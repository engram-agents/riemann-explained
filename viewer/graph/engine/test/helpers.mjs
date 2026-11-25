// Shared test helpers. Not shipped (tests are not part of the engine's files).
// A recording view stands in for the DOM view: it counts what the engine asks to be drawn,
// and refuses (throws) a double mount or an unmount of something never mounted.

export function recordingView(size = { w: 390, h: 844 }) {
  const mounted = new Map();
  const v = {
    mounted, links: [], world: { w: 0, h: 0 }, cam: null, selected: null, destroyed: false,
    mountCalls: 0, unmountCalls: 0,
    mount(n) { if (mounted.has(n.id)) throw new Error("double mount " + n.id); mounted.set(n.id, n); v.mountCalls++; },
    unmount(n) { if (!mounted.delete(n.id)) throw new Error("unmount of a node never mounted " + n.id); v.unmountCalls++; },
    place(n) { if (!mounted.has(n.id)) throw new Error("place of an unmounted node " + n.id); },
    setLinks(l) { v.links = l; },
    setWorld(w, h) { v.world = { w, h }; },
    setCamera(c) { v.cam = { k: c.k, tx: c.tx, ty: c.ty }; },
    setSelected(prev, n) { v.selected = n ? n.id : null; },
    viewport() { return size; },
    destroy() { v.destroyed = true; },
  };
  return v;
}

/* The real level data (nested steps with `premises`) as NodeSpecs and an async, call-counting loader. */
export function fromLevel(data) {
  const byId = new Map(), pathOf = new Map(), parentOf = new Map();
  (function walk(list, parentId, prefix) {
    for (const s of list) {
      byId.set(s.id, s); parentOf.set(s.id, parentId); pathOf.set(s.id, [...prefix, s.id]);
      walk(s.children, s.id, [...prefix, s.id]);
    }
  })(data.steps, null, []);
  function spec(s) {
    const pid = parentOf.get(s.id);
    return {
      id: s.id, childCount: s.children.length, path: pathOf.get(s.id),
      links: s.premises.map((p) => ({ to: p, toPath: pathOf.get(p) })),
      parentLinksTo: pid ? byId.get(pid).premises.includes(s.id) : false,
      data: s,
    };
  }
  const calls = [];
  const loader = async (id) => { calls.push(id); await null; return byId.get(id).children.map(spec); };
  return { roots: data.steps.map(spec), loader, calls, byId, parentOf, pathOf, spec };
}

/* A generated complete 40-ary tree (heap numbering) cut at `total` nodes; ids n0, n1, ...  */
export function generated({ fanout = 40, total = 100000 } = {}) {
  const kids = (i) => Math.max(0, Math.min(fanout, total - 1 - fanout * i));
  const pathOf = (i) => { const p = []; for (let j = i; ; j = Math.floor((j - 1) / fanout)) { p.unshift("n" + j); if (j === 0) break; } return p; };
  const child = (i, j) => fanout * i + 1 + j;
  function spec(i) {
    const j = i === 0 ? -1 : (i - 1) % fanout;
    const links = i > 0 && j % 3 !== 0 ? [{ to: "n" + (i - 1), toPath: pathOf(i - 1) }] : [];
    return { id: "n" + i, childCount: kids(i), path: pathOf(i), links, parentLinksTo: j === 0, data: { i } };
  }
  const calls = [];
  const loader = async (id) => {
    calls.push(id); await null;
    const i = Number(id.slice(1));
    return Array.from({ length: kids(i) }, (_, j) => spec(child(i, j)));
  };
  return { roots: [spec(0)], loader, calls, kids, pathOf, child, spec, total, fanout };
}

/* A tiny hand-made tree: id, kids (ids), premises (sibling or other ids). Builds NodeSpecs with real paths. */
export function tiny(defs) {
  const byId = new Map(defs.map((d) => [d.id, d])), parentOf = new Map(), pathOf = new Map();
  for (const d of defs) for (const k of d.kids || []) parentOf.set(k, d.id);
  const pth = (id) => { const p = []; for (let c = id; c; c = parentOf.get(c)) p.unshift(c); return p; };
  for (const d of defs) pathOf.set(d.id, pth(d.id));
  const spec = (d) => ({
    id: d.id, childCount: (d.kids || []).length, path: pathOf.get(d.id),
    links: (d.premises || []).map((p) => ({ to: p, toPath: pathOf.get(p) })),
    parentLinksTo: d.stem === true, data: null,
  });
  const calls = [];
  return {
    roots: defs.filter((d) => !parentOf.has(d.id)).map(spec),
    loader: async (id) => { calls.push(id); await null; return (byId.get(id).kids || []).map((k) => spec(byId.get(k))); },
    calls, spec, byId, pathOf, parentOf,
  };
}
