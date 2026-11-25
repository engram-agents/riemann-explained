// The DOM view: everything the engine puts on the page, all under the container it was given. Implements the view
// interface the controller calls (see controller.js). Elements are made only through dom.js; setting
// element.style from code is allowed, a style attribute in markup is not (there is no markup).
import { CLASSES as C, el, setAttr } from "./dom.js";

const r3 = (n) => { if (!Number.isFinite(n)) throw new Error("a non-finite number reached the view"); return String(Math.round(n * 1000) / 1000); };

export function createView(container, o, hooks) {
  const doc = container.ownerDocument;
  const listeners = [];
  const els = new Map();            // node id -> {el, face, last}
  const S = o.sizes;

  const rootEl = el(doc, "div", { "class": C.root });
  const stage = el(doc, "div", { "class": C.stage, tabindex: "0" });
  const world = el(doc, "div", { "class": C.world });
  const linksEl = el(doc, "div", { "class": C.links, "aria-hidden": "true" });
  const nodesEl = el(doc, "div", { "class": C.nodes });
  world.appendChild(linksEl); world.appendChild(nodesEl); stage.appendChild(world); rootEl.appendChild(stage);

  // what the engine needs to work even before any stylesheet loads
  Object.assign(rootEl.style, { position: "relative", width: "100%", height: "100%", overflow: "hidden" });
  Object.assign(stage.style, { position: "absolute", left: "0", top: "0", width: "100%", height: "100%", overflow: "hidden", touchAction: "none" });
  Object.assign(world.style, { position: "absolute", left: "0", top: "0", transformOrigin: "0 0" });
  Object.assign(linksEl.style, { position: "absolute", left: "0", top: "0", pointerEvents: "none" });
  Object.assign(nodesEl.style, { position: "absolute", left: "0", top: "0" });
  container.appendChild(rootEl);

  const view = {
    stage,
    listen(target, type, fn, opts) { target.addEventListener(type, fn, opts); listeners.push({ target, type, fn, opts }); },
    setPanning(on) { stage.classList.toggle(C.panning, on); },

    mount(n) {
      const holder = el(doc, "div", { "class": C.face });
      let face = null;
      if (o.renderFace) {
        try { face = o.renderFace(n.spec); } catch (e) { hooks.faceError(n, "face-failed"); }
        if (face !== null && (!face || face.nodeType !== 1)) { hooks.faceError(n, "bad-face"); face = null; }
      }
      if (face) holder.appendChild(face);
      const node = el(doc, "div", { "class": C.node, "data-node": n.id, tabindex: "0", role: "group" }, [holder]);
      Object.assign(node.style, { position: "absolute", left: "0", top: "0", transformOrigin: "0 0", boxSizing: "border-box", zIndex: String(n.depth) });
      nodesEl.appendChild(node);
      els.set(n.id, { el: node, holder, last: "" });
    },
    unmount(n) {
      const e = els.get(n.id);
      if (!e) return;
      if (e.el.parentNode) e.el.parentNode.removeChild(e.el);
      els.delete(n.id);
    },
    place(n) {
      const e = els.get(n.id);
      if (!e) return;
      const open = n.open && Array.isArray(n.children) && n.children.length > 0;
      const sig = [n.x, n.y, n.w, n.h, open, n.loading, n.blocked, n.childCount > 0].join("|");
      if (sig === e.last) return;
      e.last = sig;
      const d = e.el;
      d.style.transform = "translate(" + r3(n.x) + "px," + r3(n.y) + "px)";
      d.style.width = r3(n.w) + "px"; d.style.height = r3(n.h) + "px";
      e.holder.style.height = open ? r3(S.head) + "px" : "100%";
      d.classList.toggle(C.open, open); d.classList.toggle(C.loading, !!n.loading); d.classList.toggle(C.refused, !!n.blocked);
      d.classList.toggle(C.parent, n.childCount > 0);
      d.classList.toggle(C.direct, !!(n.parent && !n.parent.root && n.spec.parentLinksTo));
      if (n.childCount > 0) setAttr(d, "aria-expanded", open ? "true" : "false");
    },
    setSelected(prev, n) {
      const a = prev && els.get(prev.id), b = n && els.get(n.id);
      if (a) a.el.classList.remove(C.selected);
      if (b) b.el.classList.add(C.selected);
    },
    setWorld(w, h) {
      world.style.width = r3(w) + "px"; world.style.height = r3(h) + "px";
    },
    setCamera(cam) { world.style.transform = "translate(" + r3(cam.tx) + "px," + r3(cam.ty) + "px) scale(" + r3(cam.k) + ")"; },
    setLinks(list, selectedId) {
      while (linksEl.firstChild) linksEl.removeChild(linksEl.firstChild);
      const T = S.stroke;
      // a stroke is a div: its place and size are numbers from the node geometry, set through element.style only
      const bar = (cls, x, y, w, h) => {
        const b = el(doc, "div", { "class": cls });
        Object.assign(b.style, { position: "absolute", left: r3(x) + "px", top: r3(y) + "px", width: r3(w) + "px", height: r3(h) + "px" });
        linksEl.appendChild(b);
      };
      const v = (cls, x, ya, yb) => bar(cls, x - T / 2, Math.min(ya, yb), T, Math.abs(yb - ya));
      const h = (cls, y, xa, xb) => bar(cls, Math.min(xa, xb) - T / 2, y - T / 2, Math.abs(xb - xa) + T, T);
      for (const e of list) {
        const p = e.from, d = e.to, x1 = p.x + p.w / 2, sel = selectedId && (p.id === selectedId || d.id === selectedId) ? " " + C.linkSel : "";
        const cls = C.link + (e.kind === "stem" ? " " + C.stem : "") + sel, hc = C.head + sel;
        const A = S.arrow;
        if (e.kind === "stem") {            // straight down from the parent's face to the child's top
          const yt = d.y + S.head;
          v(cls, x1, yt, p.y); bar(hc, x1 - A / 2, yt, A, A);
          continue;
        }
        // premise p (below) rests-into dependent d (above): up from p's top, across, up into d's bottom
        const x2 = d.x + d.w / 2, y1 = p.y;
        if (y1 >= d.y + d.h + 2 * S.arrowGap) {
          const ym = d.y + d.h + S.gapY / 2, ye = d.y + d.h;
          v(cls, x1, y1, ym); h(cls, ym, x1, x2); v(cls, x2, ym, ye + S.arrowGap); bar(hc, x2 - A / 2, ye, A, A);
        } else {                            // same row or no room between: go over the top of both, down into d
          const yo = Math.min(y1, d.y) - S.gapY / 2;
          v(cls, x1, y1, yo); h(cls, yo, x1, x2); v(cls, x2, yo, d.y - A); bar(hc, x2 - A / 2, d.y - A, A, A);
        }
      }
    },
    viewport() { const r = stage.getBoundingClientRect(); return { w: r.width, h: r.height }; },
    destroy() {
      for (const l of listeners.splice(0)) l.target.removeEventListener(l.type, l.fn, l.opts);
      els.clear();
      if (rootEl.parentNode) rootEl.parentNode.removeChild(rootEl);
    },
  };
  return view;
}
