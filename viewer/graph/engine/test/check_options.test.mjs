// PR 98 round 4, F1: the engine exports its option check from its public entry. `checkOptions` is the one `normalizeOptions` (pure, no DOM):
// it returns the normalized options or throws a TypeError, so a caller can ask the engine's own rule before it creates a graph.
import test from "node:test";
import assert from "node:assert/strict";
import * as entry from "../index.js";
import { normalizeOptions } from "../options.js";

test("F1 index.js exports checkOptions, and it is options.js's normalizeOptions (same function; same answer on a valid and an invalid input)", () => {
  assert.equal(typeof entry.checkOptions, "function", "the entry exports checkOptions");
  assert.equal(entry.checkOptions, normalizeOptions);
  assert.deepEqual(entry.checkOptions({ zoom: { frameMin: 1 } }), normalizeOptions({ zoom: { frameMin: 1 } }));
  for (const bad of [{ zoom: { frameMin: 0.01 } }, { zoom: { frameMin: 2 } }]) {
    assert.throws(() => entry.checkOptions(bad), (e) => e instanceof TypeError && /zoom\.frameMin/.test(e.message));
  }
});
