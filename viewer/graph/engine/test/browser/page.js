// The test page: creates engines on the three hosts over a small generated tree and exposes a driver (T) for
// the Python test. This file is a test page, not part of the engine; it may use the document freely.
import { createGraph } from "../../index.js";

const FAN = 4, TOTAL = 400;
const kids = (i) => Math.max(0, Math.min(FAN, TOTAL - 1 - FAN * i));
const pathOf = (i) => { const p = []; for (let j = i; ; j = Math.floor((j - 1) / FAN)) { p.unshift("n" + j); if (j === 0) break; } return p; };
function spec(i) {
  const j = i === 0 ? -1 : (i - 1) % FAN;
  return { id: "n" + i, childCount: kids(i), path: pathOf(i), links: i > 0 && j % 2 === 1 ? [{ to: "n" + (i - 1), toPath: pathOf(i - 1) }] : [], parentLinksTo: j === 0, data: { i } };
}
const T = {
  log: [], handles: {},
  create(name, extra) {
    const host = document.getElementById(name);
    const o = Object.assign({
      roots: [spec(0)],
      loadChildren: (id) => { T.log.push([name, "load", id]); const i = Number(id.slice(1)); return Promise.resolve(Array.from({ length: kids(i) }, (_, j) => spec(FAN * i + 1 + j))); },
      renderFace: (s) => { const d = document.createElement("div"); d.className = "t-face"; d.textContent = s.id; return d; },
    }, extra || {});
    const h = createGraph(host, o);
    T.handles[name] = h;
    for (const t of ["tap", "open", "close", "loading", "error", "refused"]) h.on(t, (n, r) => T.log.push([name, t, n ? n.id : null, r === undefined ? null : r]));
    return Object.keys(h);
  },
  /* F4: a face that carries its own data-node attribute on a focusable button, to prove the engine never reads it */
  foreign(name) {
    const host = document.getElementById(name);
    const h = createGraph(host, {
      roots: [spec(0)],
      renderFace: (s) => {
        const d = document.createElement("div"); d.className = "t-face";
        const b = document.createElement("button"); b.className = "t-inner"; b.setAttribute("data-node", "other-id"); b.textContent = "inner";
        const q = document.createElement("button"); q.className = "t-plain"; q.textContent = "plain";
        d.appendChild(b); d.appendChild(q);
        return d;
      },
    });
    T.handles[name] = h;
    T.taps2 = [];
    h.on("tap", (n, d) => T.taps2.push({ id: n ? n.id : null, target: d.target.className, key: d.key === undefined ? null : d.key }));
    return h.ready;
  },
  ready(name) { return T.handles[name].ready; },
  fit(name) { T.handles[name].fit(); },
  destroy(name) { T.handles[name].destroy(); },
  open(name, id) { return T.handles[name].open(id); },
  reveal(name, path) { return T.handles[name].reveal(path); },
  cam(name) {
    const w = document.getElementById(name).querySelector(".ge-world");
    const m = /translate\(([-\d.e]+)px,\s*([-\d.e]+)px\)\s*scale\(([-\d.e]+)\)/.exec(w ? w.style.transform : "");
    return m ? { tx: Number(m[1]), ty: Number(m[2]), k: Number(m[3]) } : null;
  },
  nodes(name) { return document.getElementById(name).querySelectorAll("[data-node]").length; },
  under(name) { return document.getElementById(name).querySelectorAll("*").length; },
  taps() { return T.log.filter((e) => e[1] === "tap").map((e) => e[0] + ":" + e[2]); },
};
window.T = T;
window.__booted = true;
