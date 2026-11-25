// Which links to draw between the nodes that are visible. Pure: no DOM, and no loading.
//
// A link {to, toPath} on a visible node says "this node rests on `to`". The end of the link is `to` when that node
// is held (a held node is a visible one: closed nodes keep no descendants), else the NEAREST VISIBLE ANCESTOR,
// found by walking toPath from its end toward its start. Nothing is loaded to find it.
// parentLinksTo on a first-row child gives the direct stem from the parent.
// A link whose end is the node itself, one of its ancestors, or one of its descendants draws no rests link (a
// descendant is the stem's business).

const isAncestor = (a, n) => { for (let p = n.parent; p; p = p.parent) if (p === a) return true; return false; };

export function endpointOf(link, nodes) {
  const direct = nodes.get(link.to);
  if (direct) return direct;
  const p = link.toPath;
  for (let i = p.length - 1; i >= 0; i--) { const m = nodes.get(p[i]); if (m) return m; }
  return null;
}

/* vis: the visible node records in tree order; nodes: Map id -> record. Returns [{kind, from, to}], where for
   "rests" `from` is the premise's end (drawn at its top) and `to` the dependent (drawn into its bottom); for
   "stem" `from` is the child and `to` its parent. */
export function computeLinks(vis, nodes) {
  const out = [], seen = new Set();
  for (const n of vis) {
    for (const l of n.spec.links) {
      const ep = endpointOf(l, nodes);
      if (!ep || ep === n || isAncestor(ep, n) || isAncestor(n, ep)) continue;
      const key = ep.id + ">" + n.id;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ kind: "rests", from: ep, to: n });
    }
    if (n.parent && !n.parent.root && n.spec.parentLinksTo && n.layer === 0) out.push({ kind: "stem", from: n, to: n.parent });
  }
  return out;
}
