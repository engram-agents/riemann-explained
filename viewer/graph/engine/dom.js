// The ONE place the engine makes an element or sets an attribute. A fixed table of tags, a per-tag allow-list of
// attributes, a check on every value, and classes only from an enumerated table. There is no text API here: the
// engine writes no text at all; the caller's faces carry every word.
import { isId } from "./ids.js";

export const CLASSES = Object.freeze({
  root: "ge-root", stage: "ge-stage", world: "ge-world", links: "ge-links", nodes: "ge-nodes",
  node: "ge-node", face: "ge-face", open: "ge-open", loading: "ge-loading", refused: "ge-refused", selected: "ge-selected",
  parent: "ge-parent", direct: "ge-direct", panning: "ge-panning",
  link: "ge-link", stem: "ge-stem", head: "ge-head", linkSel: "ge-link-sel",
});
const KNOWN = new Set(Object.values(CLASSES));

const TAGS = Object.freeze({ div: true });

const CHECK = {
  "class": (v) => typeof v === "string" && v.length > 0 && v.split(" ").every((c) => KNOWN.has(c)),
  "data-node": isId,
  tabindex: (v) => v === "0" || v === "-1",
  role: (v) => v === "group" || v === "presentation",
  hidden: (v) => v === "",
};
const ALLOWED = Object.freeze({
  div: ["class", "data-node", "tabindex", "role", "hidden", "aria-*"],
});
const ARIA = /^aria-[a-z]+$/;

export function setAttr(node, name, value) {
  const tag = node.localName;
  const allowed = ALLOWED[tag];
  if (!allowed) throw new Error("tag not allowed: " + tag);
  if (ARIA.test(name)) {
    if (!allowed.includes("aria-*")) throw new Error("attribute not allowed on " + tag + ": " + name);
    if (value !== "true" && value !== "false") throw new Error("aria value not allowed: " + name);
  } else {
    if (!allowed.includes(name)) throw new Error("attribute not allowed on " + tag + ": " + name);
    if (!CHECK[name](value)) throw new Error("value not allowed for " + name);
  }
  node.setAttribute(name, String(value));
}

/* el(doc, tag, attrs, children): attrs is a plain object; children are elements (a caller's face included). */
export function el(doc, tag, attrs, children) {
  if (!Object.hasOwn(TAGS, tag)) throw new Error("tag not allowed: " + tag);
  const node = doc.createElement(tag);
  if (attrs) for (const k of Object.keys(attrs)) setAttr(node, k, attrs[k]);
  if (children) for (const c of children) {
    if (!c || c.nodeType !== 1) throw new Error("a child must be an element");
    node.appendChild(c);
  }
  return node;
}
