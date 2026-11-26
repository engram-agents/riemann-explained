// The engine's state machine. No DOM: everything it draws goes through a `view` object it is given, so the
// layout, the visible set, the loading and the bounded holding run (and are tested) under node.
//
// view (what the controller calls):
//   mount(node)  unmount(node)  place(node)      one drawn element per visible node
//   setLinks(links, selectedId)  setWorld(w, h)  setCamera(cam)  setSelected(prevNode|null, node|null)
//   viewport() -> {w, h}   destroy()
// All state lives in the closure of createController: two controllers share nothing.

import { normalizeOptions, openFrameCap } from "./options.js";
import { EVENTS, createEmitter } from "./emitter.js";
import { checkSpec, isId } from "./ids.js";
import { layoutTree } from "./layout.js";
import { computeLinks } from "./links.js";
import { frame, zoomAbout, toWorld } from "./camera.js";

export function createController(rawOptions, view) {
  const o = normalizeOptions(rawOptions);
  const emitter = createEmitter(EVENTS, o.onListenerError);
  const emit = emitter.emit;

  const nodes = new Map();          // id -> record, for every node in the tree (all of them are visible)
  const cache = new Map();          // id -> NodeSpec[] of a closed node's children, least recently used first
  const root = { root: true, id: "", spec: { links: [], path: [], data: null }, parent: null, depth: 0, children: [], open: true,
    premises: [], clean: false, x: 0, y: 0, w: 0, h: 0, rx: 0, ry: 0, layer: 0, inner: null };
  let cam = { k: 1, tx: 0, ty: 0 }, selected = null, destroyed = false, measured = 0, vis = [], links = [], started = false;

  const pub = (n) => ({ id: n.id, path: n.spec.path.slice(), depth: n.depth, childCount: n.childCount, open: n.open, data: n.spec.data });
  const pubOrNull = (n) => (n && !n.root ? pub(n) : null);

  /* ---------- records ---------- */
  function record(spec, parent) {
    return { id: spec.id, spec, parent, depth: parent.depth + 1, childCount: spec.childCount, premises: spec.links.map((l) => l.to),
      children: null, open: false, loading: false, blocked: null, pinned: false, noAuto: false, manualWant: false, gen: 0, pending: null,
      childSpecs: null, clean: false, mounted: false, layer: 0, x: 0, y: 0, w: 0, h: 0, rx: 0, ry: 0, inner: null };
  }
  const dirty = (n) => { for (let p = n; p; p = p.parent) p.clean = false; };

  /* Validate a batch of NodeSpecs as the children of `parent`; null when fine, else {reason, detail}. */
  function validate(specs, parent) {
    if (specs.length > o.maxChildren) return { reason: "fan-out", detail: specs.length + " > " + o.maxChildren };
    if (!parent.root && specs.length !== parent.childCount) return { reason: "invalid-spec", detail: "childCount " + parent.childCount + ", loader returned " + specs.length };
    const ids = new Set();
    for (let i = 0; i < specs.length; i++) {
      const bad = checkSpec(specs[i], parent.root ? [] : parent.spec.path);
      if (bad) return { reason: bad.reason, detail: "children[" + i + "]: " + bad.detail };
      if (ids.has(specs[i].id) || nodes.has(specs[i].id)) return { reason: "duplicate-id", detail: "children[" + i + "]" };
      ids.add(specs[i].id);
    }
    return null;
  }
  function attach(parent, specs) {
    const kids = specs.map((s) => record(s, parent));
    for (const k of kids) nodes.set(k.id, k);
    parent.children = kids; parent.childSpecs = specs; dirty(parent);
  }
  /* Release every descendant of n: its element goes, its record goes. */
  function release(n) {
    (function walk(p) {
      for (const c of p.children || []) {
        walk(c);
        if (c.mounted) { view.unmount(c); c.mounted = false; }
        nodes.delete(c.id);
        if (selected === c) selected = null;
        c.gen++;                    // an answer still on its way for c is discarded
      }
      p.children = null;
    })(n);
  }
  function remember(id, specs) {
    cache.delete(id); cache.set(id, specs);
    while (cache.size > o.maxHeld) cache.delete(cache.keys().next().value);
  }

  /* ---------- drawing ---------- */
  function render() {
    if (destroyed) return;
    measured += layoutTree(root, o.sizes, o.layout.siblings);
    const list = [];
    (function walk(p) { if (!p.open || !p.children) return; for (const c of p.children) { list.push(c); walk(c); } })(root);
    for (const n of list) { if (!n.mounted) { view.mount(n); n.mounted = true; } view.place(n); }
    vis = list;
    view.setWorld(root.w, root.h);
    links = computeLinks(vis, nodes);
    view.setLinks(links, selected ? selected.id : null);
    emit("visible", vis.map(pub));
  }
  function setCam(c) { cam = c; view.setCamera(cam); }
  function vp() { return view.viewport(); }

  /* ---------- open / close ---------- */
  function refuse(n, reason, detail) { emit("refused", pubOrNull(n), reason, detail); }

  function finishOpen(n, specs, manual) {
    attach(n, specs);
    n.open = true; n.loading = false; n.pinned = manual || n.manualWant; n.manualWant = false; n.noAuto = false;
    render();
    emit("open", pub(n));
    return true;
  }

  function openNode(id, manual) {
    if (destroyed) return Promise.resolve(false);
    const n = nodes.get(id);
    if (!n) return Promise.resolve(false);
    if (n.open) { if (manual) { n.pinned = true; n.noAuto = false; } return Promise.resolve(true); }
    if (n.childCount === 0) return Promise.resolve(false);
    if (manual) n.manualWant = true;
    if (n.pending) return n.pending;
    if (n.blocked) { refuse(n, n.blocked, "refused earlier"); return Promise.resolve(false); }
    if (n.childCount > o.maxChildren) { n.blocked = "fan-out"; refuse(n, "fan-out", n.childCount + " > " + o.maxChildren); return Promise.resolve(false); }
    const cached = cache.get(id);
    if (cached) {      // a cached list is checked again, against what is held NOW, exactly like a fresh answer
      const bad = validate(cached, n);
      cache.delete(id);                // a refused list holds no slot; the node stays refused and is not asked again
      if (bad) { n.blocked = bad.reason; view.place(n); refuse(n, bad.reason, bad.detail); return Promise.resolve(false); }
      return Promise.resolve(finishOpen(n, cached, manual));
    }
    n.loading = true; view.place(n);
    emit("loading", pub(n));
    const gen = ++n.gen;
    const current = () => !destroyed && nodes.get(id) === n && n.gen === gen;
    const p = (async () => {
      let res;
      try { res = await o.loadChildren(id); }
      catch (e) { if (current()) { n.loading = false; n.noAuto = true; view.place(n); emit("error", pub(n), "load-failed", String(e && e.message ? e.message : e)); } return false; }
      if (!current()) return false;
      n.loading = false;
      if (!Array.isArray(res)) { n.noAuto = true; view.place(n); emit("error", pub(n), "bad-result", "not an array"); return false; }
      const bad = validate(res, n);
      if (bad) { n.blocked = bad.reason; view.place(n); refuse(n, bad.reason, bad.detail); return false; }
      return finishOpen(n, res, manual);
    })().finally(() => { if (n.pending === p) n.pending = null; });   // a cancelled load's end must not clear a newer load's promise
    n.pending = p;
    return p;
  }

  function closeNode(n, manual) {
    if (!n.open) {
      if (n.pending) { n.gen++; n.loading = false; n.manualWant = false; n.pending = null; view.place(n); }   // cancel a load in flight: its answer is discarded; the next open loads afresh
      return false;
    }
    const bx = n.x + n.w / 2, by = n.y;
    remember(n.id, n.childSpecs);
    release(n);
    n.open = false; n.childSpecs = null; n.pinned = false; n.noAuto = manual; dirty(n);
    render();
    cam = { k: cam.k, tx: cam.tx + (bx - (n.x + n.w / 2)) * cam.k, ty: cam.ty + (by - n.y) * cam.k };   // the node stays where it was on screen
    view.setCamera(cam);
    emit("close", pub(n));
    return true;
  }

  /* ---------- camera and semantic zoom ---------- */
  function frameNode(n) {
    const open = n.open && n.children && n.children.length > 0, S = o.semantic, Z = o.zoom;
    const kmax = open ? openFrameCap(o) : Math.min(Z.frameMaxClosed, S.frameClosedShare * S.openPx / o.sizes.nodeW);
    const v = vp();
    if (!(v.w > 0 && v.h > 0 && n.w > 0 && n.h > 0)) return;
    setCam(frame(v, n.x, n.y, n.w, n.h, kmax, open ? Z.framePadOpen : Z.framePadClosed, open ? Z.frameMin : Z.min));
  }
  /* kmin is the floor of the fit: zoom.min for the handle's fit() (the whole drawing), zoom.fitMin for the start fit. */
  function fitAt(kmin) {
    if (destroyed || !(root.w > 0 && root.h > 0)) return;
    const v = vp();
    if (!(v.w > 0 && v.h > 0)) return;
    setCam(frame(v, 0, 0, root.w, root.h, o.zoom.fitMax, o.zoom.fitPad, kmin));
  }
  const fit = () => fitAt(o.zoom.min);

  /* Zooming in on a node opens it; zooming out closes what has become too small to read. */
  function semantic(sx, sy, zoomIn) {
    const S = o.semantic, k = cam.k;
    if (zoomIn) {
      const p = toWorld(cam, sx, sy);
      let hit = null;
      for (const n of vis) if (p.x >= n.x && p.x <= n.x + n.w && p.y >= n.y && p.y <= n.y + n.h && (!hit || n.depth > hit.depth)) hit = n;
      if (hit && !hit.open && hit.childCount > 0 && !hit.noAuto && !hit.pending && hit.w * k >= S.openPx) {
        openNode(hit.id, false).then((ok) => { if (ok && !destroyed) frameNode(hit); });
      }
    } else {
      const c = vis.filter((n) => n.open && !n.pinned && n.w * k < S.closePx).sort((a, b) => b.depth - a.depth)[0];
      if (c) closeNode(c, false);
      for (const n of vis) if (n.noAuto && n.w * k < S.reArmShare * S.openPx) n.noAuto = false;
    }
  }
  function zoomAt(sx, sy, f, user) {
    setCam(zoomAbout(cam, sx, sy, f, o.zoom.min, o.zoom.max));
    if (user && f !== 1) semantic(sx, sy, f > 1);
  }
  function panBy(dx, dy) { setCam({ k: cam.k, tx: cam.tx + dx, ty: cam.ty + dy }); }

  /* ---------- the public operations ---------- */
  async function reveal(path) {
    if (destroyed) return false;
    if (!Array.isArray(path) || path.length === 0 || !path.every(isId)) { refuse(null, "invalid-path", "reveal"); return false; }
    await ready;
    for (let i = 0; i < path.length - 1; i++) {
      const n = nodes.get(path[i]);
      if (!n || (i > 0 && n.parent !== nodes.get(path[i - 1]))) { emit("error", null, "path-not-found", path[i]); return false; }
      if (!n.open && !(await openNode(n.id, false))) return false;
      if (destroyed) return false;
    }
    const last = nodes.get(path[path.length - 1]);
    if (!last || (path.length > 1 && last.parent !== nodes.get(path[path.length - 2]))) { emit("error", null, "path-not-found", path[path.length - 1]); return false; }
    frameNode(last);
    return true;
  }
  function select(id) {
    if (destroyed) return false;
    const prev = selected;
    if (id === null || id === undefined) { selected = null; view.setSelected(prev, null); view.setLinks(links, null); return true; }
    const n = isId(id) ? nodes.get(id) : null;
    if (!n) return false;
    selected = n; view.setSelected(prev, n); view.setLinks(links, n.id);
    return true;
  }
  function tap(id, detail) {
    if (destroyed) return;
    const n = id === null || id === undefined ? null : nodes.get(id);
    emit("tap", n ? pub(n) : null, detail || {});
  }
  function destroy() {
    if (destroyed) return;
    destroyed = true;
    emitter.clear();
    for (const n of nodes.values()) n.gen++;
    nodes.clear(); cache.clear(); root.children = []; vis = []; links = [];
    view.destroy();
  }

  /* ---------- start: the roots arrive after createController returns, so a listener attached at once sees every event ---------- */
  const ready = Promise.resolve().then(() => {
    if (destroyed) return false;
    const bad = validate(o.roots, root);
    started = true;
    if (bad) { refuse(null, bad.reason, bad.detail); return false; }
    attach(root, o.roots);
    render();
    if (o.fitOnStart) fitAt(o.zoom.fitMin);
    return true;
  });

  const guard = (fn, dead) => (...a) => (destroyed ? dead : fn(...a));
  return {
    ready,
    open: (id) => (started ? openNode(id, true) : ready.then(() => openNode(id, true))),
    close: guard((id) => { const n = isId(id) ? nodes.get(id) : null; return n ? closeNode(n, true) : false; }, false),
    reveal, fit, select, destroy,
    on: emitter.on, off: emitter.off,
    // below: used by the input layer and by the tests; not part of the handle
    zoomAt: guard(zoomAt, undefined), panBy: guard(panBy, undefined), tap, faceError: (n, reason) => emit("error", pub(n), reason),
    node: (id) => nodes.get(id),
    visibleNodes: () => vis.slice(),
    links: () => links.slice(),
    world: () => ({ w: root.w, h: root.h }),
    camera: () => ({ ...cam }),
    stats() {
      let cached = 0;
      for (const s of cache.values()) cached += s.length;
      return { held: nodes.size + cached, visible: vis.length, cached: cache.size, cachedNodes: cached, measured, started };
    },
  };
}
