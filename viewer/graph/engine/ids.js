// The id pattern and the NodeSpec check. Pure: no DOM. An id (or a path element) is checked here BEFORE it is
// used for anything, and only an id that passed is ever written to the DOM (as a data attribute, in dom.js).

export const ID_RE = /^[a-z0-9][a-z0-9._-]*$/;
export const isId = (v) => typeof v === "string" && ID_RE.test(v);

const bad = (reason, detail) => ({ reason, detail });

/* Check one NodeSpec that is to become a child of a node whose path is `parentPath` ([] for a top-level node).
   Returns null when it is fine, else {reason, detail}. Reasons: invalid-spec, invalid-id, invalid-path. */
export function checkSpec(s, parentPath) {
  if (s === null || typeof s !== "object" || Array.isArray(s)) return bad("invalid-spec", "not an object");
  if (!isId(s.id)) return bad("invalid-id", "id");
  if (!Number.isInteger(s.childCount) || s.childCount < 0) return bad("invalid-spec", "childCount");
  if (typeof s.parentLinksTo !== "boolean") return bad("invalid-spec", "parentLinksTo");
  if (!Array.isArray(s.links)) return bad("invalid-spec", "links");
  for (const l of s.links) {
    if (l === null || typeof l !== "object") return bad("invalid-spec", "link");
    if (!isId(l.to)) return bad("invalid-id", "link.to");
    if (!Array.isArray(l.toPath) || !l.toPath.every(isId)) return bad("invalid-path", "link.toPath");
  }
  if (!Array.isArray(s.path) || s.path.length === 0 || !s.path.every(isId)) return bad("invalid-path", "path");
  if (s.path[s.path.length - 1] !== s.id) return bad("invalid-path", "path does not end at id");
  if (s.path.length !== parentPath.length + 1 || !parentPath.every((p, i) => p === s.path[i])) return bad("invalid-path", "path does not run through the parent");
  return null;
}
