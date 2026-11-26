// A tiny stand-in for `document` so dom.js and data.js can be tested under plain node (no npm, no jsdom).
// Test-only: lives under test/, never shipped.
export function makeFakeDoc() {
  const made = [];
  const doc = {
    made,
    createElement: (t) => node(t),
    createTextNode: (s) => ({ nodeType: 3, textContent: String(s) }),
    createDocumentFragment: () => ({ nodeType: 11, children: [], appendChild(c) { this.children.push(c); return c; } }),
    createElementNS: () => { throw new Error("createElementNS must never be called"); },
  };
  function node(tag) {
    const n = {
      tagName: tag.toUpperCase(), attrs: {}, children: [], nodeType: 1, ownerDocument: doc,
      setAttribute(k, v) { this.attrs[k] = String(v); },
      appendChild(c) { this.children.push(c); return c; },
    };
    made.push(n);
    return n;
  }
  return doc;
}
