// A TEST DOUBLE of the engine, written to viewer/graph/engine/INTERFACE.md (the engine's own document), not to the spec:
// createGraph(container, options) -> a frozen handle {open, close, reveal, fit, select, destroy, on, off, ready};
// events tap(node|null, detail), open, close, visible, loading, error(node, reason, detail), refused(node, reason, detail);
// renderFace takes ONE argument; roots attach in a microtask; `ready` resolves true once they are drawn.
// It draws a plain flow of boxes (no camera, no links) so the page layer can be driven without the real engine.
// Test-only: lives under test/, never shipped. A call log is kept on container.__log for assertions.
const ID = /^[a-z0-9][a-z0-9._-]*$/;

export function createGraph(container, options) {
  const doc = container.ownerDocument;
  const SZ = Object.assign({ nodeW: 300, nodeH: 190 }, options.sizes || {});    // the engine's own defaults, overridden as the page asks
  const log = (container.__log = []);
  container.__options = options;      // the arguments createGraph received, for the cases that pin what the page passes (layout, zoom, the links of a node)
  const stage = doc.createElement("div");
  stage.className = "ge-stage dbl-stage";
  stage.style.cssText = "display:flex;flex-wrap:wrap;gap:8px;padding:8px;align-content:flex-start;position:absolute;inset:0;overflow:auto";
  container.appendChild(stage);
  const listeners = { tap: [], open: [], close: [], visible: [], loading: [], error: [], refused: [] };
  const held = new Map();     // id -> {spec, el, kids, open, depth}
  let dead = false;

  const emit = (name, ...args) => { for (const f of listeners[name].slice()) f(...args); };
  const plain = (n) => ({ id: n.spec.id, path: n.spec.path.slice(), depth: n.spec.path.length, childCount: n.spec.childCount, open: n.open, data: n.spec.data });

  function draw(spec, into) {
    if (!ID.test(spec.id) || spec.path[spec.path.length - 1] !== spec.id) { emit("refused", null, "invalid-id", {}); return null; }
    const el = doc.createElement("div");
    el.className = "ge-node";
    el.setAttribute("data-node", spec.id);
    el.style.cssText = "width:" + SZ.nodeW + "px;min-height:" + SZ.nodeH + "px;position:relative";
    const face = doc.createElement("div");
    face.className = "ge-face";
    face.style.cssText = "height:" + SZ.nodeH + "px";
    try { face.appendChild(options.renderFace(spec)); } catch (e) { emit("error", null, "face-failed", {}); }
    el.appendChild(face);
    const kids = doc.createElement("div");
    kids.className = "dbl-kids";
    kids.style.cssText = "display:flex;flex-wrap:wrap;gap:6px";
    el.appendChild(kids);
    into.appendChild(el);
    const n = { spec, el, kids, open: false };
    held.set(spec.id, n);
    return n;
  }
  const visible = () => emit("visible", [...held.values()].map(plain));

  async function open(id) {
    log.push(["open", id]);
    const n = held.get(id);
    if (!n || n.spec.childCount === 0) return false;
    if (n.open) return true;
    emit("loading", plain(n));
    let kids;
    try { kids = await options.loadChildren(id); } catch (e) { emit("error", plain(n), "load-failed", { message: String(e && e.message) }); return false; }
    if (dead || n.open) return n.open;
    if (kids.length > options.maxChildren) { emit("refused", plain(n), "fan-out", {}); return false; }
    for (const k of kids) draw(k, n.kids);
    n.open = true;
    n.el.classList.add("ge-open");
    emit("open", plain(n));
    visible();
    return true;
  }
  function close(id) {
    log.push(["close", id]);
    const n = held.get(id);
    if (!n || !n.open) return false;
    for (const d of [...held.values()]) if (d !== n && d.spec.path.length > n.spec.path.length && d.spec.path.slice(0, n.spec.path.length).join("/") === n.spec.path.join("/")) held.delete(d.spec.id);
    while (n.kids.firstChild) n.kids.removeChild(n.kids.firstChild);
    n.open = false;
    n.el.classList.remove("ge-open");
    emit("close", plain(n));
    visible();
    return true;
  }
  async function reveal(path) {
    log.push(["reveal", path.slice()]);
    for (let i = 0; i < path.length; i++) {
      if (!path.slice(0, i + 1).every((x) => ID.test(x))) { emit("refused", null, "invalid-path", {}); return true; }
    }
    for (let i = 0; i < path.length - 1; i++) {
      if (!held.get(path[i])) { emit("error", null, "path-not-found", {}); return true; }
      await open(path[i]);
    }
    if (!held.get(path[path.length - 1])) { emit("error", null, "path-not-found", {}); return true; }
    return true;
  }
  function select(id) {
    log.push(["select", id]);
    for (const n of held.values()) n.el.classList.toggle("ge-selected", n.spec.id === id);
    return id === null || held.has(id);
  }

  stage.addEventListener("click", (e) => {
    const t = e.target.closest ? e.target.closest("[data-node]") : null;
    const n = t ? held.get(t.getAttribute("data-node")) : null;
    emit("tap", n ? plain(n) : null, { target: e.target, clientX: e.clientX, clientY: e.clientY, pointerType: "mouse" });
  });

  const ready = Promise.resolve().then(() => {
    if (dead) return false;
    for (const r of options.roots) draw(r, stage);
    visible();
    return true;
  });

  const handle = Object.freeze({
    open, close, reveal,
    fit: () => { log.push(["fit"]); },
    select,
    destroy: () => { dead = true; for (const k of Object.keys(listeners)) listeners[k].length = 0; if (stage.parentNode) stage.parentNode.removeChild(stage); held.clear(); },
    on: (name, fn) => { if (!(name in listeners)) throw new TypeError("unknown event"); listeners[name].push(fn); return () => handle.off(name, fn); },
    off: (name, fn) => { const l = listeners[name]; const i = l.indexOf(fn); if (i >= 0) l.splice(i, 1); },
    ready,
  });
  container.__open = (id) => open(id);       // test hooks: what a semantic zoom does on the real engine
  container.__close = (id) => close(id);
  return handle;
}
export const DEFAULTS = Object.freeze({});
export const EVENTS = Object.freeze(Object.keys({ tap: 1, open: 1, close: 1, visible: 1, loading: 1, error: 1, refused: 1 }));
export const VERSION = "double";
// The real engine's checkOptions (INTERFACE.md) is the one rule for the options; the double draws boxes and checks none, so its answer is the options as given.
export const checkOptions = (options) => options;
