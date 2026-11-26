/* The page's ONE element creator (R1). Every page module builds elements through el(); text goes in only as
   text nodes; a tag or attribute outside the tables below THROWS. Nothing here parses markup. */

/* The tag table. No svg, path or g: links are the engine's div strokes. */
export const TAGS = Object.freeze(["div", "span", "button", "nav", "ol", "ul", "li", "p", "h2"]);

/* Attributes allowed on every tag, and the one extra a button may carry. aria-* is matched by pattern below. */
const COMMON = new Set(["class", "data-id", "role", "tabindex", "hidden"]);
const PER_TAG = { button: new Set(["type"]) };
const ARIA = /^aria-[a-z]+$/;
const CLASS_TOKEN = /^[a-z][a-z0-9_-]*$/;

/* R3: every id from data is checked against this before it becomes a class, a selector, a data attribute or a file name. */
const ID = /^[a-z0-9][a-z0-9._-]*$/;

export function isId(v) { return typeof v === "string" && ID.test(v); }
export function assertId(v) {
  if (!isId(v)) throw new TypeError("not a valid step id");
  return v;
}
/* R4: the only file address the page builds, and the only link it creates besides the fixed list address. */
export function stepPath(id) { return "step/" + assertId(id) + ".json"; }
export function hashFor(id) { return "#" + assertId(id); }

function allowed(tag, name) {
  if (COMMON.has(name) || ARIA.test(name)) return true;
  const extra = Object.prototype.hasOwnProperty.call(PER_TAG, tag) ? PER_TAG[tag] : null;
  return !!extra && extra.has(name);
}

function checkAttr(tag, name, value) {
  if (!allowed(tag, name)) throw new TypeError("attribute not allowed: " + tag + " " + name);
  if (typeof value !== "string") throw new TypeError("attribute value must be a string: " + name);
  if (name === "class") {
    value.split(" ").forEach((t) => { if (!CLASS_TOKEN.test(t)) throw new TypeError("bad class token"); });
  } else if (name === "data-id") {
    if (!isId(value)) throw new TypeError("data-id is not a valid id");
  } else if (name === "type") {
    if (value !== "button") throw new TypeError("a button's type is only button");
  }
}

/* makeEl(doc) -> el. A factory so tests can pass a stand-in document; the page uses the default `el` below. */
export function makeEl(doc) {
  return function el(tag, attrs, children) {
    if (typeof tag !== "string" || !TAGS.includes(tag)) throw new TypeError("tag not allowed");
    const d = doc || globalThis.document;
    const node = d.createElement(tag);
    if (attrs) {
      for (const name of Object.keys(attrs)) {
        checkAttr(tag, name, attrs[name]);
        node.setAttribute(name, attrs[name]);
      }
    }
    for (const c of children || []) {
      if (typeof c === "string") node.appendChild(d.createTextNode(c));
      else if (typeof c === "number" && Number.isFinite(c)) node.appendChild(d.createTextNode(String(c)));
      else if (c && typeof c === "object" && (c.nodeType === 1 || c.nodeType === 3)) node.appendChild(c);
      else throw new TypeError("bad child");
    }
    return node;
  };
}

export const el = makeEl(null);

/* A text node, for the places that need one without an element around it. */
export function text(s) { return globalThis.document.createTextNode(String(s)); }
