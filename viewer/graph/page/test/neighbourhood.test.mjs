/* page/neighbourhood.js, the parts that need no document: the order of a side's rows and how many fit. Made-up ids and titles. */
import test from "node:test";
import assert from "node:assert/strict";
import { orderRows, rowsPerSide, NB_SIZES, MIN_ROWS } from "../neighbourhood.js";

const T = new Map([["a", { title: "Beta" }], ["b", { title: "Alpha" }], ["c", { title: "Alpha" }], ["d", { title: "Gamma" }], ["e", { title: "Delta" }]]);
const R = (id, names) => ({ id, names, same_group: false });

test("N1 rows are heaviest by names first, ties by title, then by id", () => {
  const rows = [R("a", 2), R("d", 5), R("c", 2), R("b", 2), R("e", 9)];
  assert.deepEqual(orderRows(rows, T).map((r) => r.id), ["e", "d", "b", "c", "a"]);       // e 9, d 5, then the three with 2 names: Alpha b, Alpha c (id), Beta a
});

test("N2 ordering is by plain code-unit order of the title, not a locale's, and does not change its input", () => {
  const t = new Map([["x", { title: "b" }], ["y", { title: "B" }], ["z", { title: "a" }]]);
  const rows = [R("x", 1), R("y", 1), R("z", 1)];
  assert.deepEqual(orderRows(rows, t).map((r) => r.id), ["y", "z", "x"]);     // "B" < "a" < "b" in code units
  assert.deepEqual(rows.map((r) => r.id), ["x", "y", "z"]);
});

test("N3 a row whose id has no title row is ordered by the id as its title", () => {
  assert.deepEqual(orderRows([R("q", 1), R("p", 1)], new Map()).map((r) => r.id), ["p", "q"]);
});

test("N4 a side shows at least two rows whatever the stage, and all of them when they fit", () => {
  assert.equal(rowsPerSide(100, 10), MIN_ROWS);
  assert.equal(rowsPerSide(100, 2), 2);
  assert.equal(rowsPerSide(100, 1), 1);
  assert.equal(rowsPerSide(100, 0), 0);
  assert.equal(rowsPerSide(5000, 7), 7);
});

test("N5 at 390 x 844 (a folded stage of 772 px) a side with many rows shows 4 and the more row; the unfolded 653 px shows 3 and the more row", () => {
  assert.equal(rowsPerSide(772, 40), 4);
  assert.equal(rowsPerSide(653, 40), 3);
  const slots = (h) => Math.floor((h - NB_SIZES.backH - NB_SIZES.centreH - 2 * NB_SIZES.headH - NB_SIZES.padY) / 2 / (NB_SIZES.rowH + NB_SIZES.gap));
  assert.equal(slots(772), 5);        // 4 files and the more row
});

test("N6 when everything fits no more row is made: exactly as many as fit show all", () => {
  assert.equal(rowsPerSide(772, 5), 5);
  assert.equal(rowsPerSide(772, 6), 4);
});
