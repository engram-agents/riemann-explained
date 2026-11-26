# Graph engine: the interface

This is the ONE document of everything a caller may use. Anything not listed here is private and may change.
A test reads the lists under **Exports**, **Options**, **Handle** and **Events** and compares them with the code.

The engine draws a tree of nodes with cross links, loads children on demand through a function the caller passes,
and holds only what is visible plus a bounded cache. It knows nothing about any page: it builds no content, writes
no text, fetches nothing, imports nothing outside this folder, and keeps no state outside the handle it returns.
Two graphs on one page work: each lives under its own container.

**Visible** has one meaning in this document: a node is visible when every one of its ancestors is open (a top-level node
always is). It says nothing about the camera: a visible node may be off the screen, and `select` and `visible` follow
this definition, not what is on screen.

Files: `index.js` (an ES module), `engine.css` (structure and states only; link it with a stylesheet link).

## Exports

- `createGraph`
- `checkOptions`
- `DEFAULTS`
- `EVENTS`
- `VERSION`

`createGraph(container, options)` returns a handle. `container` is an element the caller owns; the engine adds one
child to it and removes it on `destroy()`. The container needs a size (the stage fills it). A wrong container or a
wrong option is a `TypeError` thrown at once: those are programming errors. Wrong DATA is never thrown, always an event.
`checkOptions(options)` is the engine's own check of an options object, the very one `createGraph` runs first: pure (no DOM, no container), it returns the normalized options or throws the same `TypeError`, so a caller can ask the engine's rule (a bound such as the `zoom.frameMin` range) before it creates a graph, instead of keeping a copy of the numbers. `DEFAULTS` is the frozen default of every option. `EVENTS` is the list of event names. `VERSION` is a string.

## Options

Every option has a default in `DEFAULTS`. An unknown option name is a `TypeError`.

- `roots`
- `loadChildren`
- `renderFace`
- `sizes`
- `zoom`
- `layout`
- `semantic`
- `input`
- `maxChildren`
- `maxHeld`
- `fitOnStart`
- `onListenerError`

| option | meaning |
|---|---|
| `roots` | array of NodeSpec, the top-level nodes. They are attached right after `createGraph` returns, so a listener added at once sees every event about them. |
| `loadChildren(nodeId)` | returns a Promise of an array of NodeSpec, the children of that node. The ONLY way children arrive; the engine calls it once per node it opens, never for a node that was not opened, and not again while the answer is cached. Rejecting is an `error` event (`load-failed`). Default: no node has children. |
| `renderFace(nodeSpec)` | returns an Element, the face of the node. The engine appends it as it is and never reads it. It is called once when the node is drawn. Throwing or returning a non-element is an `error` event (`face-failed`, `bad-face`) and the node is drawn with an empty face. Default: an empty face. |
| `sizes` | `nodeW`, `nodeH` (a closed node), `gapX`, `gapY`, `pad` (inside an open node), `head` (an open node's face height), `top` (space below it), `topInset` (space above the first row), `stroke` (bar thickness), `arrow`, `arrowGap` (link drawing). |
| `zoom` | `min`, `max`, `fitMax`, `fitPad`, `fitMin`, `frameMin`, `frameMaxOpen`, `frameMaxClosed`, `framePadOpen`, `framePadClosed`. `fitMin` (`DEFAULTS` holds `null`, resolved to `min` at creation, and an explicit `null` means not given; otherwise `min <= fitMin <= fitMax`): the start fit never goes below it, and when clamped it is top-anchored and centred horizontally (a drawing wider than the stage is cut on both sides); `fit()` and the reader's own zoom are not affected. `frameMin` (`DEFAULTS` holds `null`, resolved to `min` at creation, and an explicit `null` means not given; otherwise `min <= frameMin <=` the open-framing cap, `min(zoom.max, zoom.frameMaxOpen, semantic.frameOpenShare * semantic.openPx / sizes.nodeW)`, so a floor never overrides the cap that keeps closed children below `openPx`; above it is a `TypeError` at creation): framing an opened node (`reveal`, a semantic open) never goes below it, and when clamped it is top-anchored (the node's top at `framePadOpen`) and centred horizontally; framing a closed node, `fit()` and the reader's own zoom are not affected. |
| `layout` | `siblings`. `siblings` is `"rows"` (the default; an absent or `undefined` `siblings` means `"rows"`) or `"column"`; anything else is a `TypeError` at creation, like the other options. With `"rows"` every sibling set is laid out in rows by dependency depth. With `"column"`, a set where no sibling's premises name another sibling (by id) and no sibling is a stem child is a column in the data's order (centred, nothing drawn between members), and in a set with some such links the siblings with none follow the rows as a column. A sibling with a link to or from another sibling by id, or that is a stem child of a real (non-root) parent (`parentLinksTo`: that stem is a drawn edge), counts as linked; a `parentLinksTo` flag in the root's top list draws no stem and does not count. A premise naming the node itself or an id outside the set is not a link. An edge drawn because a premise names a sibling's descendant (resolved to the nearest visible ancestor) does not make the set linked: only ids within the set are tested, in both modes. |
| `semantic` | `openPx` (a node opens when it is at least this wide on screen), `closePx` (an open node closes when narrower; must be below `openPx`), `reArmShare`, `frameOpenShare`, `frameClosedShare`. |
| `input` | `tapSlopPx` (8), `tapMs` (300), `wheelStep`, `wheelCtrlStep`, `keyZoom`, `keyPanPx`. |
| `maxChildren` | default 40. A node that has more children than this is refused (see **Refusals**), never drawn. |
| `maxHeld` | default 16. The LRU cache holds at most this many closed nodes' child lists. |
| `fitOnStart` | default true. Fit the roots into the container once they are drawn. |
| `onListenerError(error, eventType)` | where an exception thrown by an event listener goes. Default: rethrown outside the engine's own call so the page's error reporting sees it. The engine carries on either way. |

Sizes and zoom values are numbers in CSS pixels and scales. All are checked; a bad one is a `TypeError`.

## NodeSpec

```
{ id: string, childCount: int, links: [{to: string, toPath: string[]}], parentLinksTo: boolean, path: string[], data: any }
```

- `id` is unique in the whole tree and matches `^[a-z0-9][a-z0-9._-]*$`. It is the engine's key and the only text of
  the caller that ever reaches the page by the engine's hand (as a data attribute).
- `childCount` is a non-negative integer: how many children `loadChildren` will return. 0 means a leaf. An answer of
  any other length is refused whole (`invalid-spec`, see **Refusals**), so it is a promise the engine checks, not a hint.
- `path` runs from a top-level node down to this node INCLUDING it. For a top-level node it is `[id]`; for a child it is
  its parent's path plus its own id. Every element matches the id pattern.
- `links` says "this node rests on `to`". `toPath` is the path of `to`, in the same form. The engine finds the end of a
  link from `toPath` alone and never loads to draw one.
- `parentLinksTo` is true when this node's parent rests directly on it. A first-row child with it gets a stem from its parent.
- `data` is carried and handed back in events and to `renderFace`; the engine never reads it.

## Handle

The object `createGraph` returns. Frozen.

- `open`
- `close`
- `reveal`
- `fit`
- `select`
- `destroy`
- `on`
- `off`
- `ready`

| member | promises |
|---|---|
| `open(id)` | Promise of true when the node is open on return (already open counts), false when it is not (unknown id, a leaf, refused, load failed, closed again while loading). The node stays open against zoom-out until the caller closes it. An `open` issued after a load was cancelled by `close`, while that first answer is still on its way, starts a fresh load (the loader is called again) and resolves when that load lands. |
| `close(id)` | true if a node was closed, else false. Releases every descendant's element and state; the node's own children are kept in the cache. Closing a node that is still loading cancels the load: its answer is discarded whenever it arrives, and never drawn. A node closed this way is not reopened by zoom until it is zoomed well out first. |
| `reveal(path)` | Promise of a boolean: true when the node was framed on screen, false when it was not (a bad path, an unknown step, an ancestor that did not open, the graph destroyed). Opens each ancestor in order, loading as needed, then frames the node. An unknown step is an `error` event (`path-not-found`), a bad path a `refused` event (`invalid-path`); an ancestor that does not open says why through its own event. |
| `fit()` | frames the whole drawing. |
| `select(id)` | marks one visible node (class `ge-selected`) and its links; `select(null)` clears. Returns false for an id that is not visible. |
| `destroy()` | removes every listener the engine added and every element it made, drops all state. Safe to call twice; after it every method does nothing. |
| `on(event, fn)` | adds a listener, returns a function that removes it. An unknown event name throws. |
| `off(event, fn)` | removes a listener. |
| `ready` | a Promise of true once the roots are drawn, false if they were refused. |

## Events

Listeners are called synchronously, in the order added. `node` below is a plain object
`{id, path, depth, childCount, open, data}`; a fresh one each time.

- `tap`
- `open`
- `close`
- `visible`
- `loading`
- `error`
- `refused`

| event | arguments |
|---|---|
| `tap(node, detail)` | one pointer, moved at most `tapSlopPx`, released within `tapMs`; or Enter/Space on a focused node. `node` is null for a tap on empty stage. `detail` is `{target, clientX, clientY, pointerType}` (or `{target, key}`); `target` is the element that was pressed, so a caller can tell a tap on its own control inside a face. A drag or a pinch never taps. The node is found from `target` upward, as the first element the engine itself made for a node; an attribute in a face (a `data-node` of its own included) is never read. Keys act only on the stage and on the engine's node elements; a key pressed on a control inside a face is the face's own. |
| `open(node)` | the node's children are now drawn. |
| `close(node)` | the node's children were released. |
| `visible(nodes)` | after every change, the array of every visible node (every node whose ancestors are all open). |
| `loading(node)` | `loadChildren` was called for this node. |
| `error(node, reason, detail)` | `load-failed`, `bad-result`, `path-not-found`, `face-failed`, `bad-face`. `node` is null when no node is meant. |
| `refused(node, reason, detail)` | the data was not drawn. `node` is the parent whose children were refused, null for the roots. |

### Refusals

A refusal is an event, never a throw, and nothing of the refused data reaches the page. Reasons: `fan-out` (more than
`maxChildren` children, by `childCount` or by what the loader returned), `invalid-id` (an `id` or a link's `to` fails the
pattern), `invalid-path` (a `path` or `toPath` element fails the pattern, `path` does not end at `id`, or does not run through
the parent), `invalid-spec` (a wrong shape: `childCount`, `links`, `parentLinksTo`; or a loader answer whose length is not the node's `childCount`, the detail naming both numbers), `duplicate-id`. A batch is refused whole.
A child list that is served from the cache when a node is opened again is checked like a fresh answer, against the nodes held at that moment, and refused the same way.
A node whose children were refused stays closed and says so (class `ge-refused`) and is not asked again.

## What the engine does

- Layout of one opened node from its own children: rows by dependency depth among siblings (a node sits below every
  sibling that rests on it). With the option `layout.siblings` set to `"column"` an edgeless set is a column and the
  unlinked siblings of a mixed set follow the rows as a column (see the option's row); the default `"rows"` is rows for
  every set. A stem child (`parentLinksTo`) of a real (non-root) parent counts as linked, so it stays in the rows and
  keeps its stem; in the root's top list the flag draws no stem and does not count.
  Opening a node re-measures it and its ancestors only.
- Camera: pan, zoom about a point, fit; pointer and touch (two pointers pinch), wheel, and keys on the focused stage (arrows,
  plus and minus, 0 to fit). The stage has `touch-action: none`.
- Semantic zoom: after a user zoom, the deepest closed node under the focus opens when it is at least `semantic.openPx`
  wide on screen; an open node narrower than `semantic.closePx` closes.
- Links between visible nodes; an end that is not visible is drawn at its nearest visible ancestor.
- Bounded holding: nodes held never exceed the visible nodes plus `maxHeld * maxChildren`.

## Classes and attributes the engine sets (for the caller's stylesheet)

On the node element: `ge-node`, and as state `ge-open`, `ge-loading`, `ge-refused`, `ge-selected`, `ge-parent` (has
children), `ge-direct` (its parent rests on it); attribute `data-node` (the id; for the caller's stylesheet and tests, the engine never reads it back), `aria-expanded` on a node with children.
The face is inside an element with class `ge-face`. Links are drawn as right-angled strokes: thin `div` bars (class `ge-link`, plus `ge-stem` for a stem and `ge-link-sel` next to the selected node) and a small `div` arrowhead (`ge-head`), placed only through element.style numbers computed from node geometry, inside the transformed world so they scale with the camera. The engine draws no vector graphics and no canvas.
