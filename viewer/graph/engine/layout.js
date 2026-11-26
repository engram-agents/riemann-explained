// Layout of an open node from its OWN children. Pure: no DOM.
//
// The column rule below applies only when the option layout.siblings is "column" (the caller passes it as `siblings`);
// the default "rows" lays every set out in rows by dependency depth exactly as before.
//
// SIBLING SET = the `children` array of one open node, or the root's top list, in ARRAY ORDER (the data's order).
// A LINK between siblings a and b exists when b.premises contains a.id or a.premises contains b.id, with a !== b.
// A premise naming the node itself, or an id that is not in this sibling set, is NOT a link.
// LINKED = siblings with at least one link, or whose parent rests on them (a stem is a drawn edge: spec.parentLinksTo
// on the node record). LOOSE = the others.
//   - a set with no link at all is a COLUMN in array order, each sibling centred on the column axis; nothing is
//     drawn between them (a drawn link means "rests on" and nothing else);
//   - a set where every sibling is linked is laid out in ROWS by dependency depth, as before;
//   - a MIXED set: the linked siblings are laid out in rows among themselves alone, and the loose ones follow below
//     as a column in array order; the block and the column are both centred on the set's width.
// A column member's `layer` is its row index (the linked block's rows come first). Stem children are never in the column:
// with no sibling link they share row 0 of the linked block, so each keeps its stem from the parent.
// Ported from the prototype's core.js (place / measure / position), with two differences: a node's measured size
// is kept (`clean`), so opening one node re-measures it and its ancestors only; and the sizes are options.
//
// A node record (the fields this file reads and writes):
//   reads   root (true for the virtual top), open, children (array, or null when closed), premises (ids)
//   writes  x, y, w, h (world coordinates), rx, ry (relative to the parent's body), layer, inner, clean
// A node is re-measured unless `clean === true`; the caller sets `clean = false` on the node and every ancestor
// whenever the node's children change.

export function layoutTree(root, S, siblings) {
  const column = siblings === "column";      // layout.siblings: anything but "column" is the rows of fd42c540, for every set
  let measured = 0;
  const isOpen = (n) => n.root === true || (n.open === true && Array.isArray(n.children) && n.children.length > 0);

  /* a step sits below every sibling that rests on it; a cycle among siblings stops, it does not loop */
  function layers(kids) {
    const memo = {};
    function L(k, guard) {
      if (memo[k.id] !== undefined) return memo[k.id];
      if (guard > kids.length) return 0;
      let v = 0;
      for (const m of kids) if (m !== k && m.premises.indexOf(k.id) >= 0) v = Math.max(v, L(m, guard + 1) + 1);
      memo[k.id] = v;
      return v;
    }
    for (const k of kids) k.layer = L(k, 0);
  }

  function measure(n) {
    if (n.clean === true) return;
    measured++;
    if (isOpen(n)) {
      const inner = place(n.children);
      n.inner = inner;
      if (n.root) { n.w = inner.w; n.h = inner.h + S.topInset; }
      else { n.w = Math.max(S.nodeW, inner.w + 2 * S.pad); n.h = S.head + S.top + inner.h + S.pad; }
    } else { n.w = S.nodeW; n.h = S.nodeH; n.inner = null; }
    n.clean = true;
  }

  /* The rows of a set of LINKED siblings: today's algorithm (fd42c540), unchanged. Sets rx (left edge at 0), ry, layer. */
  function rowsBlock(kids) {
    layers(kids);
    const rows = [];
    for (const k of kids) (rows[k.layer] = rows[k.layer] || []).push(k);
    let y = 0, minX = Infinity, maxX = -Infinity;
    rows.forEach((row, li) => {
      const items = row.map((k, i) => {
        let want = null;
        if (li > 0) {
          const deps = kids.filter((m) => m.layer < li && m.premises.indexOf(k.id) >= 0);
          if (deps.length) want = deps.reduce((s, m) => s + m.rx + m.w / 2, 0) / deps.length;
        }
        return { k, i, want };
      });
      items.sort((a, b) => {
        if (a.want === null && b.want === null) return a.i - b.i;
        if (a.want === null) return 1;
        if (b.want === null) return -1;
        return (a.want - b.want) || (a.i - b.i);
      });
      let cur = null, rowH = 0;
      for (const it of items) {
        const k = it.k;
        let left = it.want === null ? (cur === null ? 0 : cur) : it.want - k.w / 2;
        if (cur !== null && left < cur) left = cur;
        k.rx = left; k.ry = y; cur = left + k.w + S.gapX; rowH = Math.max(rowH, k.h);
        minX = Math.min(minX, left); maxX = Math.max(maxX, left + k.w);
      }
      y += rowH + S.gapY;
    });
    for (const k of kids) k.rx -= minX;
    return { w: maxX - minX, h: y - S.gapY, rows: rows.length };
  }

  function place(kids) {
    if (!kids.length) return { w: 0, h: 0 };
    kids.forEach(measure);
    if (!column) { const all = rowsBlock(kids); return { w: all.w, h: all.h }; }
    /* LINKED: at least one link to or from a sibling (self and foreign premises are not links). LOOSE: the others. */
    const byId = new Map(kids.map((k) => [k.id, k]));
    const linkedSet = new Set();
    for (const k of kids) for (const p of k.premises) if (p !== k.id && byId.has(p)) { linkedSet.add(k); linkedSet.add(byId.get(p)); }
    /* a stem is a drawn edge: a sibling its parent rests on (spec.parentLinksTo, from the controller's node record) is LINKED */
    for (const k of kids) if (k.spec && k.spec.parentLinksTo === true) linkedSet.add(k);
    const linked = kids.filter((k) => linkedSet.has(k)), loose = kids.filter((k) => !linkedSet.has(k));
    const block = linked.length ? rowsBlock(linked) : { w: 0, h: 0, rows: 0 };
    if (!loose.length) return { w: block.w, h: block.h };
    let colW = 0;
    for (const k of loose) colW = Math.max(colW, k.w);
    const W = Math.max(block.w, colW), shift = (W - block.w) / 2;
    for (const k of linked) k.rx += shift;
    let y = linked.length ? block.h + S.gapY : 0;
    loose.forEach((k, i) => { k.rx = (W - k.w) / 2; k.ry = y; k.layer = block.rows + i; y += k.h + S.gapY; });
    return { w: W, h: y - S.gapY };
  }

  function position(n) {
    if (!n.inner) return;
    const ox = n.root ? 0 : n.x + (n.w - n.inner.w) / 2, oy = n.root ? S.topInset : n.y + S.head + S.top;
    for (const c of n.children) { c.x = ox + c.rx; c.y = oy + c.ry; position(c); }
  }

  measure(root);
  root.x = 0; root.y = 0;
  position(root);
  return measured;
}
