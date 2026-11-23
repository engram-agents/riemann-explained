# fields/uses: which hypotheses and fields a Lean proof term uses

> **Read this before citing a verdict.** A report with `complete: false` supports **no** `unused` claim, and no `in_types_only` claim either: the walk stopped (term budget or depth limit), and a binder it did not reach is labelled `not_reached`. A note may cite an `unused` verdict only from a report with `complete: true`, and should say which tool version and options produced it. A `who_reads` list is a **lower bound**: it shows readers the tool found, never that no other reader exists (see Known limits: `partial def` readers are missed, and its scope and skip rules have no control yet). The JSON says so too: `"lower_bound": true`. A `direct` label whose only path is the empty path `""` means the binder was taken apart (`casesOn`, `match`, `obtain`) and NO field was used afterwards: it is not a reading of any field.

A small Lean 4 program that reads the **elaborated proof terms** of a compiled release and answers, for one declaration:

- **`uses DECL`**: for each binder (hypothesis or argument) of `DECL`, one or more labels:
  - `unused`: the proof term makes no use of the binder. This includes `have h2 := h` when `h2` is never used: a renaming is read through, so an unused renaming is no use.
  - `direct`: the body projects it (`h.2`, `h.right`), takes it apart (`obtain ⟨a, b⟩ := h`, `match`), or applies it as a function. The report gives the read path, positionally (`.2.2`) and by field name (`.right.right`).
  - `passed_whole`: it is an explicit argument to another constant. The report names the callee and the argument position. With `--follow N`, the tool reads what the callee does with that argument, up to depth N, and says where it stopped.
  - `instance_only`: it fills only instance-implicit slots (found by instance search). Source text never shows these uses.
  - `returned`: it is the body itself, or a field of the structure the body builds.
  - `in_types_only`: it occurs only inside types (binder types, and an eliminator's motive where the eliminator takes it as an implicit argument, as `subst` and `▸` produce) or in implicit and strict-implicit argument slots. A motive written as an explicit function argument (from `rw`, or `congrArg (fun x => …)`) is walked as a value; see Known limits. It is shown only when no other label applies. An implicit slot gets this label even when the callee's own proof uses that argument, so `in_types_only` does not mean "does not matter for the proof".
- **`flows_into`** (in the same report): which fields of the structure a declaration builds contain the binder.
- **`who_reads S.field`**: every declaration of the modules given with `--module` (widened with `--scan-prefix P`) whose term reads that field: through `Expr.proj`, the projection function, or `casesOn` (directly or inside a `match`) with the field's variable used. Generated declarations (matchers, `noConfusion`, internal helpers) are counted, not listed; so are declarations with no value, whose terms cannot be read (`no_value_declarations_skipped`): axioms, and the other constants with no definition body (inductive types, their constructors and recursors, `Quot`). Opaque constants have a value and are read.

Two facts the notes keep separate: **"Lean's proof term uses h"**, which this tool reports, and **"the source names h"**, which is text. Tactics can make them differ in either direction.

Auxiliary declarations made by elaboration (`DECL._proof_N`, `match_N` matchers, `_simp_N`) are followed and named under `followed`, never reported as callees. Local renamings (`have h2 := h; exact h2.2`) are read through.

## Running it

It needs a prebuilt tree: the release compiled with its toolchain, plus Mathlib's prebuilt `.lake` build. It never calls `lake`, and it writes nothing into that tree.

```
LEAN_PATH=<release build>:<mathlib .lake/build/lib/lean>:<each package's .lake/build/lib/lean> \
PATH=<toolchain>/bin:$PATH \
lean --run FieldsUses.lean -- --module Some.Module [--follow N] uses Full.Decl.Name [More.Decls ...]
```

The output is JSON. It starts with a scope header: the Lean version, the modules requested, the module count loaded, the query and the options. Each `uses` report says `complete` and how many subterms it visited.

**Memory.** Run every `lean` inside a memory-capped scope, e.g. `systemd-run --user --scope -q -p MemoryMax=10G -p MemorySwapMax=0 nice -n 15 lean …`; `run_controls.py` does this for every call. `--budget N` (default 2,000,000) caps the subterms one walk visits (the declaration's own walk; under `--follow`, each followed callee's walk has its own budget, so one query can visit several budgets' worth): past it the walk stops, the report says `complete: false` with a note, and no label is claimed for the unread part.

Errors are loud:
- exit 3: a requested module has no `.olean` (not compiled yet);
- exit 2: the declaration is not in the loaded environment;
- `no_body`: the declaration is an axiom, opaque, or similar;
- `complete: false`: the term budget was reached, and the labels cover only what was read; a binder the walk never reached is `not_reached`, never `unused`;
- `not_followed`: a `--follow` stopped (depth, not loaded, no body).

## Tests: controls first, then a mutation check

`controls/Controls.lean` holds small Mathlib-only theorems in pairs (C1-C21, C24 and C26-C30; there is no C22, C23 or C25: the design's controls for summarising a helper once and composing its summary were not built, because v2 does not summarise helpers, it only memoises the walk), and `controls/expected.json` gives what the tool must report for each (54 cases, including `who_reads`, a budget stop and the depth limit). C1-C10 were written before the classifier; C11-C19 were added after a reviewer's mutants survived the first set, each written before the code change it tests; C24, C26, C27 and C28 came with v2: nested beta redexes that must cost linearly (C24), one shared subterm under two different binders that must not share its result (C26), a binder taken apart with no field read against one with a field read (C27), and a reader with no value that `who_reads` must count (C28); C29 and C30, added after a reviewer's probe, pin two fields of the memo key. C27a's expected path was changed after its first run, from no path to the empty path `""` (same meaning, different form), and its note in `expected.json` says so. **A control counts only after its pair has been printed as elaborated terms and seen to differ in the way its row says.** Three first drafts failed that check (C2, C8, C10) and were rewritten. The runner refuses to run if `Controls.lean` no longer matches the hash recorded in `expected.json`.

```
python3 run_controls.py --root <prebuilt tree>                    # 54 cases
python3 run_controls.py --root <prebuilt tree> --mutation-check   # four planted bugs
```

The mutation check plants four bugs, one at a time, with `--mutate`, and requires each to fail exactly the cases named in `expected.json`:
1. instance slots treated as explicit: fails only C2a;
2. projections read without their index: fails every case that reads a path, and only those, with C3a and C3b together;
3. no reading through local renamings (`have`, beta): fails only C9a and the beta cases C13a/C13f and C24a/C24b/C24f;
4. no reading of positional destructuring (`casesOn`, `match`): fails only C3a, C27a and C27b.
`expected.json` records which of these lists were written before a run and which were set from one.

**What passing does not mean.** The classifier was written against these controls, so 54/54 shows agreement with them, not correctness on release terms. The planted bugs show the controls can fail; they do not show that every plausible wrong implementation fails (a reviewer's 14 one-line mutants of the first version left 11 survivors; on the current controls 10 of the 13 that still apply are killed, and the three survivors are listed below; a second reviewer's 13 mutants of the who_reads and callee code left 9 survivors, also listed below). Declarations of the release, run when their modules are compiled, are the first test the code was not written against.

## How v2 was checked against v1

v2 changes the traversal only: each distinct subterm is walked once per context, and occurrences are reported as sets. It does not change a label rule. Three checks on the release (a partial build of 7,243 declarations):

- **Differential.** v1 and v2 were run on all 7,243 declarations, each `lean` inside a 10 GB memory scope. v1 finished 7,207 (29 stopped at the budget, 7 killed at the memory cap); v2 finished all 7,243. On the 7,207 that v1 finished, the two agree on every label, path, callee, `flows_into` field, followed helper and binder name, and their occurrence sets are equal: 0 differences. The comparison script was written, and shown able to fail (one planted label gave exactly one difference), before the v2 results existed. Visits over those 7,207: 159,232,392 for v1, 2,520,789 for v2.
- **What the differential cannot say.** The 36 declarations v1 never finished have no v1 answer, so they are v2's only unchecked ground, and they are exactly the hard ones: the differential cannot speak for where v2 matters most. Nine of them are generated declarations with no source text. As a control that the tool can be wrong there and be seen to be, three of the other 27 were read by hand. They were picked by a rule fixed before selection (the smallest text extent), with expectations written and hashed before v2's labels were opened. In one of the three, one expectation failed: v2 labels three function hypotheses of a `simp` proof `direct`. A walk of the elaborated term showed why: the proof passes the propositions it rewrites as explicit arguments, and the hypotheses are applied inside them (see Known limits). Three is a control, not a sample.
- **A proof read by hand first.** The release theorem `tame_vanish` was read by hand on 2026-11-23, hours before this version was designed or written: its local finiteness hypothesis is dropped, and local Tate duality and the Euler characteristic hypothesis are used. v1 stopped at its budget there, all three `not_reached`. v2 finishes it (2,892 visits) and says the same: `unused`, `direct`, `direct`. The hand read came first, so this is not the tool confirming itself.
- **A prediction that missed.** Before reading v2's result for `tame_vanish`, the visits were predicted at 10,000 to 50,000, from a measurement of 10,721 distinct subterms in its term. The result was 2,892, below the band by about 3.5 times. A guess, unchecked: the subterm count included contexts the memo merges. Treat cost predictions for this tool as uncalibrated.

## Known limits

- Destructuring is read through `casesOn` only, not through `.rec`.
- An occurrence in an implicit argument slot counts as "in types".
- Extra arguments that a dependent eliminator receives after its minor premises are read as `passed_whole` to that eliminator.
- Type binders passed explicitly to type formers (`TensorProduct.tmul K …`) get `passed_whole`. This is correct by the rules above, but it is noise.
- Terms carry no source positions. The report gives term paths, not line numbers.
- Paths through a type with several constructors (`Or`) do not name the constructor, so `inl` field 1 and `inr` field 1 print alike.
- `flows_into` sees a constructor only in result position; one inside an `if` branch or another non-constructor call is not seen, which under-reports.
- v2 walks each distinct subterm once per context (a memo keyed on the term and the walk's position), so a proof term that shares subterms costs its number of distinct subterms, not its size as a tree. Occurrences are reported as SETS: two identical occurrences of a binder at the same place in the term are one occurrence. The budget still exists and still stops a walk honestly.
- The memo compares terms up to the names of bound variables, as Lean's own term equality does. Two `let`s that differ only in their binder's name, in the same place, are walked once, and only the first `let` name appears among the occurrences (labels, paths, callees and `flows_into` are unaffected; a reviewer's probe found this).
- Of the memo key's five context fields, four are pinned by a control (`inType` by C29, `encPos` by C30, `field` by C24f, `enclosing` by C21: dropping any one from the key fails exactly that case). `resultPos` has none: no term we could write differs from another only in result position. `enclosing` is pinned only through a budget edge: C21 cuts the walk with a small budget, and dropping `enclosing` changes the visit count at the cut, not a label; two shapes written to separate it by labels (the hypothesis passed to two different constants in one term, directly and under a lambda) gave identical labels and `passed` lists with and without it (Sol's probe, 2026-11-23). A larger key only costs sharing, never soundness, so these are limits of the controls, not defects of the walk. C26 was meant to test the memo under two binders but cannot fail: its shared lambda is beta-reduced before the walk, and binders become fresh free variables, so no subterm is shared across them.
- No control yet (deferred from v1, still deferred in v2): the `who_reads` module scope and `--scan-prefix`, its list of skipped generated declarations, its single visit of head and arguments, and the filter that keeps pseudo-callees out of `passed`.
- `who_reads` misses a reader declared `partial def`: a reviewer's probe found it neither listed nor counted. The cause is not traced yet (likely the opaque constant plus an internal helper that is skipped), so treat `partial def` readers as unseen.
- `--follow` reads a callee by its printed name, so a private callee (`_private.…`) is reported "not loaded".
- A declaration whose value is eta-reduced (`theorem f : p → q := g`) has fewer leading binders than its type; the report lists only the value's binders and does not say so.
- Under `--follow`, the top-level `complete` covers the declaration's own walk only; each followed callee has its own `complete`, which can be false under a true top-level flag.
- Untested branches: an `Expr.proj` node and its field-name lookup. Source-written projections elaborate to projection-function applications, so no control here produces an `Expr.proj`; it appears in elaborated helpers.
- A proposition passed as an explicit argument is walked as a value. `simp` and `rw` proofs pass the propositions they rewrite to `Iff`, `Eq.trans`, `of_eq_true`, `congrArg`, `forall_congr` and `implies_congr`, so a function hypothesis applied inside such a proposition is labelled `direct`, although the proof only rewrites a statement that mentions it (measured on a release theorem whose proof is `show …; simp only […]`). This errs toward reporting a use; it never reports a false `unused`.
- A motive passed as an explicit lambda (`rw`, `congrArg (fun x => Q hp x) h`) is walked as a value: a hypothesis that occurs only there reads `passed_whole` to the constant inside the lambda (here `Q`), and `--follow` shows what that constant does with it (in the reviewer's probe that found this, nothing); `subst` and `▸` give `in_types_only`, as stated above. In this shape the error reports a use where there is none; it does not report an absence.
- A hypothesis inside a lambda argument (`useFun (fun _ => hp)`) is reported as `passed_whole` to the callee at that position, although what is passed is a function returning it. `--follow` then describes what the callee does with the function, not with the hypothesis (a reviewer's probe found this).
- Callees named `<local function>`, `<lambda>` and `let y` stay in the occurrence list but are not reported under `passed` and are never followed.
