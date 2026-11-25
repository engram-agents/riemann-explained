// Links: a hidden endpoint is drawn at its NEAREST VISIBLE ANCESTOR, found from toPath alone (no load);
// parentLinksTo gives the direct stem from the parent (first row only).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createController } from "../controller.js";
import { recordingView, tiny } from "./helpers.mjs";

const tree = () => tiny([
  { id: "a", kids: ["a1", "a2"] },
  { id: "a1", kids: ["a1x", "a1y"], stem: true, premises: ["a2"] },     // a1 rests on a2, so a1 is the lower row
  { id: "a2", stem: true },
  { id: "a1x" }, { id: "a1y" },
  { id: "b", premises: ["a1y"] },                                          // b rests on a step two levels down inside a
]);
async function make(t) {
  const view = recordingView();
  const ctl = createController({ roots: t.roots, loadChildren: t.loader, maxHeld: 10, fitOnStart: false }, view);
  await ctl.ready;
  return { ctl, view };
}
const pairs = (ctl) => ctl.links().map((e) => e.kind + ":" + e.from.id + ">" + e.to.id).sort();

test("hidden endpoint: drawn at the nearest visible ancestor from toPath alone", async () => {
  const t = tree(), { ctl } = await make(t);
  // a closed: b's premise a1y is hidden two levels down; its nearest visible ancestor is a
  assert.deepEqual(pairs(ctl), ["rests:a>b"]);
  assert.deepEqual(t.calls, [], "no loader call was needed to place the link");
  // a open: a1 is visible and closed, so the link ends at a1 (not at a, the top of the path)
  await ctl.open("a");
  assert.deepEqual(pairs(ctl).filter((p) => p.endsWith(">b")), ["rests:a1>b"]);
  assert.deepEqual(t.calls, ["a"], "a1 was not loaded to draw the link");
  // a1 open: the premise itself is visible
  await ctl.open("a1");
  assert.deepEqual(pairs(ctl).filter((p) => p.endsWith(">b")), ["rests:a1y>b"]);
  // closing a1, then a, moves the end back up
  ctl.close("a1");
  assert.deepEqual(pairs(ctl).filter((p) => p.endsWith(">b")), ["rests:a1>b"]);
  ctl.close("a");
  assert.deepEqual(pairs(ctl), ["rests:a>b"]);
});

test("a link whose endpoint is an ancestor or a descendant of its own node draws no rests link", async () => {
  const t = tiny([{ id: "p", kids: ["c"], premises: ["c"] }, { id: "c", premises: ["p"], stem: true }]);
  const { ctl } = await make(t);
  await ctl.open("p");
  assert.deepEqual(ctl.links().filter((e) => e.kind === "rests"), []);
});

test("parentLinksTo gives the stem from the parent, for a first-row child only", async () => {
  const t = tree(), { ctl } = await make(t);
  await ctl.open("a");
  // a1 rests on a2 -> a2 is the premise (lower row, layer 1); a1 is the first row. Both say parentLinksTo.
  const stems = ctl.links().filter((e) => e.kind === "stem").map((e) => e.from.id + ">" + e.to.id);
  assert.equal(ctl.node("a1").layer, 0);
  assert.equal(ctl.node("a2").layer, 1);
  assert.deepEqual(stems, ["a1>a"]);
  assert.ok(ctl.node("a2").spec.parentLinksTo === true, "a2 says its parent rests on it, but it is not in the first row");
});

test("a link to an id that is nowhere in its toPath's held chain is skipped, never thrown", async () => {
  const t = tiny([{ id: "x" }, { id: "y", premises: ["x"] }]);
  t.roots[1].links = [{ to: "gone", toPath: ["gone"] }];
  const { ctl } = await make(t);
  assert.deepEqual(ctl.links(), []);
});
