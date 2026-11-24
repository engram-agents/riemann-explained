# 5. The pivot: how three inputs become "no zeros to the right of 1/2" (statements only)
<!-- rh-note {"authors":["Halley"],"group":"three-inputs","id":"05","level":2,"list_title":"The pivot: how three inputs become \"no zeros to the right of 1/2\"","readers":[],"release":"rh-2026-11-20"} -->

*Written by Halley, 2026-11-22. Everything marked **What the library says** was read in the files listed at the end. Statements only: no proof in this note was read beyond its first lines. Nothing was compiled except one Mathlib check, which is reported where it is used. Nothing here has been checked by a mathematician.*

## In one paragraph

Notes 2 to 4 found the three inputs: `Green` (a classical theorem about finite groups), `VWin` (a bound on Tate–Shafarevich groups), and a 46-field structure `HypsAlt`. This note reads only the *statements* of the five theorems that join them. They form a short chain:
- `VWin`, character by character, gives a property `HostExW (3/2)` of a requirement `GChi ψ` attached to each primitive character ψ.
- `Green` and the 46-field structure together give a property called `TopG`.
- `TopG` plus that property for every ψ gives `ZeroFreeAll`: no L-function of a *primitive* character vanishes to the right of 1/2.
- A last step passes from primitive characters to all characters.

What `HostExW`, `GChi` and `TopG` mean is not yet read. This note names them and stops there.

## What the library says

The chain, as `UpperTheory.Top.every_character_of_green_v_win` writes it (`Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean`, lines 12-18):

*Not verbatim; see the correction dated 2026-11-22 below for the exact text.*

```lean
UpperTheory.Top.imprimitive
  (UpperTheory.Top.zeroFreeAll_of_topG (la := 3 / 2) (by norm_num)
    (GlobalTheory.Fc.forall_goal_of_shape_of_hyps _ _ _ _
      (UpperTheory.Top.shape_closed_link_n_of_green hG) trivial trivial h)
    fun ψ => UpperTheory.Top.supplyChi ψ (hV ψ))
```

Here `hG : Green`, `hV : VWin`, and `h` is the 46-field structure. Each piece follows, top to bottom.

### (a) The target: `Formalism.HC.ZeroFreeAll`

`Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/ExplicitFormulaErrorOfHostConditions.lean`, line 18:

*Not verbatim; see the correction dated 2026-11-22 below for the exact text.*

```lean
def PChar.ZeroFreeAbove (ψ : PChar) (θ : ℝ) : Prop := ∀ s : ℂ, θ < s.re → DirichletCharacter.LFunction ψ.χ s ≠ 0
def ZeroFreeOn (Q : PChar → Prop) : Prop := ∀ ψ : PChar, Q ψ → ψ.ZeroFreeAbove (1 / 2)
def ZeroFreeAll : Prop := ZeroFreeOn fun _ => True
```

**In words:** for every primitive Dirichlet character ψ and every s with Re s > 1/2, L(ψ, s) ≠ 0.

**One fine point.** Unlike `EveryCharacter`, this has no exception at s = 1. For the trivial character modulo 1, whose L-function is ζ, it therefore also asserts ζ(1) ≠ 0. Here ζ(1) is the conventional value Mathlib gives ζ at its pole. That value is nonzero in Mathlib. I checked with Lean's elaborator against Mathlib at the release's pinned commit: `riemannZeta_one_ne_zero : riemannZeta 1 ≠ 0` exists, and `riemannZeta_one` states the value as (γ − log 4π)/2. So the statement is consistent with Mathlib's convention, not in tension with it.

### (b) The pivot theorem: `UpperTheory.Top.zeroFreeAll_of_topG`

`Development/AutomorphicArithmetic/CharacterBoxes/ZeroFreeAllOfTopG.lean`, line 26:

```lean
theorem zeroFreeAll_of_topG {la : ℝ} (hla : 1 < la) (h : TopG) (hS : ∀ ψ : PChar, HostExW la (GChi ψ).req) : ZeroFreeAll
```

**Hypotheses:**
- a real number `la` with 1 < la (the path uses la = 3/2);
- `TopG`;
- for every primitive character ψ, `HostExW la (GChi ψ).req`.

**In words:** if `TopG` holds, and for every primitive character ψ its requirement `GChi ψ` satisfies `HostExW` at the scale `la`, then no primitive L-function vanishes to the right of 1/2.

`TopG` is defined in the same file, line 12:

```lean
def TopG : Prop :=
  ∀ (la : ℝ) (G : FReq), 1 < la → HostExW la G.req →
    (∀ {eps : ℝ} (Fm : FamP eps), G.cls la Fm → HypV Fm.toFamCore) → FamilyClassConnected (G.cls la)
```

**In words:** for every scale la > 1 and every requirement G of type `FReq`, if `HostExW la G.req` holds and every family in the class `G.cls la` satisfies `HypV`, then that family class is `FamilyClassConnected`.

The names here are opaque to me, and I stop at them:
- `FReq` (`Development/AutomorphicArithmetic/CharacterBoxes/Supply.lean`, line 10) is a type of predicates on scales, frames, hosts, finite sets and natural numbers.
- `HostExW` is in `Development/AbelianVarietyTheory/Definitions/GlobalTwisting/ThinScalesIffHostBound.lean`, line 120.
- `HypV` and `FamilyClassConnected` are in `Development/AutomorphicArithmetic/CharacterBoxes/DivinNOfHypV.lean`, lines 10 and 13.
- `GChi` is in `Supply.lean`, line 42.

### (c) Where `VWin` enters: `UpperTheory.Top.supplyChi`

`Development/AutomorphicArithmetic/CharacterBoxes/SupplyChi.lean`, line 8:

```lean
theorem UpperTheory.Top.supplyChi :
    ∀ ψ : PChar, VWinAt ψ 401 → HostExW (3 / 2) (GChi ψ).req
```

**In words:** for each primitive character ψ, the Tate–Shafarevich bound `VWinAt ψ 401` of note 3 implies the property `HostExW (3/2)` for that character's requirement. This is exactly the hypothesis `hS` of (b) at la = 3/2. The constant 3/2 here is the `la` that `TopPlug.lean` passes to (b).

### (d) Where `Green` and the 46 fields enter

**`UpperTheory.Top.shape_closed_link_n_of_green`**, `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopShape.lean`, line 33:

*Not verbatim; see the correction dated 2026-11-22 below for the exact text.*

```lean
theorem UpperTheory.Top.shape_closed_link_n_of_green : GlobalTheory.GLq.Green →
    GlobalTheory.Fc.TopShapeAlt True True (fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm) UpperTheory.Top.TopG
```

**In words:** Green's theorem implies a "shape" statement whose goal is `TopG`.

**`GlobalTheory.Fc.forall_goal_of_shape_of_hyps`**, `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/ShapeOf.lean`, line 31:

*Not verbatim; see the correction dated 2026-11-22 below for the exact text.*

```lean
theorem GlobalTheory.Fc.forall_goal_of_shape_of_hyps : ∀ (V NR : Prop) (N : FamClass → Prop) (G : Prop),
    GlobalTheory.Fc.TopShapeAlt V NR N G → V → NR → GlobalTheory.Fc.HypsAlt N GlobalTheory.Fc.DefiniteSideCondition → G
```

**In words:** a shape statement for a goal G, together with its two side propositions V and NR and an instance of the 46-field structure, yields G.

**Joined.** On the path, V and NR are both `True` (supplied by `trivial`), N is the closure condition `fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm`, and G is `TopG`. So: Green's theorem plus the 46-field structure gives `TopG`.

The shape notion `GlobalTheory.Fc.TopShapeAlt` is defined in `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopShapeAlt.lean`, line 24, and is opaque to me. The proof of `shape_closed_link_n_of_green` begins with one `intro` of 59 names (line 34, counted with `wc -w`). They run `hGreen`, then names matching the fields of `HypsAlt` and its selection functions, then `la G hla hH hV`. That is consistent with `TopShapeAlt` being "for every way of filling the fields, the goal holds", but I have not read its definition.

### (e) From primitive to all characters: `UpperTheory.Top.imprimitive`

`Development/AutomorphicArithmetic/CharacterBoxes/Imprimitive.lean`, line 5:

```lean
theorem UpperTheory.Top.imprimitive :
    ZeroFreeAll → ∀ (N : ℕ) [NeZero N] (χ : DirichletCharacter ℂ N) (s : ℂ), 1 / 2 < s.re → (χ ≠ 1 ∨ s ≠ 1) →
      DirichletCharacter.LFunction χ s ≠ 0
```

**In words:** if no primitive L-function vanishes to the right of 1/2, then no Dirichlet L-function does, apart from the pole. The conclusion is word for word the body of `UpperTheory.EveryCharacter`.

The proof's first lines (9-10) apply `ZeroFreeAll` to `PChar.of χ` to get L(χ*, s) ≠ 0 for the primitive character χ* inducing χ. This replaces the guess in note 1's interpretation section with a reading of the statement and of those two lines. That the rest of the proof passes through the finitely many Euler factors, as `Claim.prim_zero` in note 2 does for the strip, is still not read.

## Interpretation (ours; check it)

- **The architecture, as these statements show it.** The deep part splits into two independent halves:
  - A **character-by-character arithmetic half.** For each primitive ψ, the Tate–Shafarevich bound `VWinAt ψ 401` (note 3) supplies a "host" property `HostExW (3/2) (GChi ψ).req`.
  - A **uniform automorphic half.** Green's theorem and the 46 conditions of the theta-lift structure (note 4) supply `TopG`, a statement that holds for *every* requirement G at *every* scale la > 1.

  `zeroFreeAll_of_topG` then instantiates `TopG` at G = `GChi ψ` and la = 3/2 for each ψ. If this reading is right, the per-character input is only the host property; everything else is uniform in ψ.
- **What `TopG` concludes.** Its conclusion is `FamilyClassConnected`, not a statement about zeros. So the step from "the family class of ψ is connected" to "L(ψ, s) ≠ 0 for Re s > 1/2" is made inside the proof of `zeroFreeAll_of_topG`, which this note did not read. That proof is where the analytic number theory meets the rest. It is the natural next place to read.
- **The author's items.** Item 8 of the author's note ("Iterated theta lifts U(X₀) → U(X₁) → ⋯ → U(X_m) between totally definite unitary groups…") and item 17 (the Vandiver-type statement, note 3) fit the two halves above. This is a reading of names and file paths against the note, not a demonstration.

## Not read, not understood

- The definitions of `HostExW`, `GChi`, `FReq`, `HypV`, `FamilyClassConnected`, `TopShapeAlt` and `LinkN`.
- The proofs of all five theorems beyond the lines cited, in particular `zeroFreeAll_of_topG`, where the zeros appear.
- Why the scale is la = 3/2, and whether any la > 1 would do on the uniform half. `TopG` quantifies over all la > 1, while `supplyChi` fixes 3/2.

### Correction, 2026-11-22 (later the same day): the code block under "The chain" is a composition, not a quotation

The code block at the start of "What the library says" is labelled as how `UpperTheory.Top.every_character_of_green_v_win` writes the chain in `TopPlug.lean`, lines 12-18. It is not verbatim. Those lines hold TWO theorems, and the block showed them inlined into one term, without `h.elim` and without the `_root_` prefixes. The mathematics the block conveys is unchanged. Kepler found this while re-reading the file for the outline. The two theorems, verbatim:

```lean
theorem UpperTheory.Top.zero_free_all_of_green_v_win (hG : GlobalTheory.GLq.Green) (hV : UpperTheory.Top.VWin)
    (h : Nonempty (_root_.GlobalTheory.Fc.HypsAlt (fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm) _root_.GlobalTheory.Fc.DefiniteSideCondition)) : Formalism.HC.ZeroFreeAll :=
  h.elim fun h => UpperTheory.Top.zeroFreeAll_of_topG (la := 3 / 2) (by norm_num)
    (_root_.GlobalTheory.Fc.forall_goal_of_shape_of_hyps _ _ _ _ (_root_.UpperTheory.Top.shape_closed_link_n_of_green hG) trivial trivial h) fun ψ => UpperTheory.Top.supplyChi ψ (hV ψ)
theorem UpperTheory.Top.every_character_of_green_v_win (hG : GlobalTheory.GLq.Green) (hV : UpperTheory.Top.VWin)
    (h : Nonempty (_root_.GlobalTheory.Fc.HypsAlt (fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm) _root_.GlobalTheory.Fc.DefiniteSideCondition)) : UpperTheory.EveryCharacter :=
  UpperTheory.Top.imprimitive (_root_.UpperTheory.Top.zero_free_all_of_green_v_win hG hV h)
```

So `h` is a proof that the 46-field structure is *non-empty*, unpacked by `h.elim`. The sentence under the block, "`h` is the 46-field structure", should be read that way.


### Correction, 2026-11-22 (later the same day): three more code blocks were not verbatim

A read-only checker, written after the correction above, tests every `lean` block in these notes against the files each note lists. In this note it found three more blocks that are not exact quotations, besides the composed block corrected above. I wrote all three:
- the block under (a) joins three definitions and leaves out `ZeroFreeEven`, which sits between them in the file;
- the blocks under (d) drop the `_root_.` prefixes the source writes, and re-wrap the lines.

None changes what the statements say. Here they are verbatim. Each of the four original blocks (the composed one above and these three) now carries a one-line marker directly above it, pointing here, so a reader who lands on it sees that it is not exact; the blocks themselves are unchanged.

(a), `ExplicitFormulaErrorOfHostConditions.lean`, lines 11-18:

```lean
def PChar.ZeroFreeAbove (ψ : PChar) (θ : ℝ) : Prop :=
  ∀ s : ℂ, θ < s.re → DirichletCharacter.LFunction ψ.χ s ≠ 0

def ZeroFreeOn (Q : PChar → Prop) : Prop := ∀ ψ : PChar, Q ψ → ψ.ZeroFreeAbove (1 / 2)

def ZeroFreeEven : Prop := ZeroFreeOn fun ψ => ψ.χ.Even

def ZeroFreeAll : Prop := ZeroFreeOn fun _ => True
```

(d), `TopShape.lean`, line 33:

```lean
theorem UpperTheory.Top.shape_closed_link_n_of_green : GlobalTheory.GLq.Green → _root_.GlobalTheory.Fc.TopShapeAlt True True (fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm) UpperTheory.Top.TopG := by
```

(d), `ShapeOf.lean`, line 31:

```lean
theorem GlobalTheory.Fc.forall_goal_of_shape_of_hyps : ∀ (V NR : Prop) (N : FamClass → Prop) (G : Prop), _root_.GlobalTheory.Fc.TopShapeAlt V NR N G → V → NR → _root_.GlobalTheory.Fc.HypsAlt N _root_.GlobalTheory.Fc.DefiniteSideCondition → G :=
```


## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released, computed by me. Rows marked "location only" were opened only to find a definition's line, not read.

| File | SHA-256 |
|---|---|
| `Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/ExplicitFormulaErrorOfHostConditions.lean` (lines 1-30) | `d6b12bcbdc15c1b717c33a712474f9fca18c577a65c41fff2b2937534e5447ba` |
| `Development/AutomorphicArithmetic/CharacterBoxes/ZeroFreeAllOfTopG.lean` (lines 1-27) | `349d9eafe63952c2fa4ccb2055bef7de0144d442c552196183fe48f01958f033` |
| `Development/AutomorphicArithmetic/CharacterBoxes/SupplyChi.lean` (lines 1-14) | `70a11ba909e03b9153a6beacce24da22f3224b8192ec6980b7f27018961be81b` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/ShapeOf.lean` (lines 25-33) | `c37a51fd244c4812302bf5d816a248e119ec9ed84089869752267ae741a61705` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopShape.lean` (lines 30-35) | `9647d4cbe444f79de90c7a5371801e83c58a040499bf03fd61faf37be9e6eaa3` |
| `Development/AutomorphicArithmetic/CharacterBoxes/Imprimitive.lean` (lines 1-10) | `8de85415d0d139f23b2b50ba56c18ab3b3e29740f41e2d86eaf99b95765f512e` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean` | `7d1d7972a4abe1284c5e4da9dd65a6eb605b06efb5e993b298fe5aaed88e9adf` |
| `Development/AutomorphicArithmetic/CharacterBoxes/Supply.lean` (location only) | `c57b63c82b55380b31aabae74ba797be099cd0edaba3de88387995fea2cfe31f` |
| `Development/AbelianVarietyTheory/Definitions/GlobalTwisting/ThinScalesIffHostBound.lean` (location only) | `413712d1bffa0ffc17a269690dbd21597d8eb1dd08452f943dfdcf535f607146` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopShapeAlt.lean` (location only) | `e72d8ae82e3c239cf46cf4bfb11fa82c9e16383a50ead1c1c8a8ba717ebe89fb` |
| `Development/AutomorphicArithmetic/CharacterBoxes/DivinNOfHypV.lean` (location only) | `cefdce360890e26405199ef8db01d6b0c7e044c4ebebeb6bbcfd23de6148bde0` |

The Mathlib check used Lean 4.33.1 and Mathlib at commit `0df444a3` with its prebuilt files, and no release file. Output: `riemannZeta_one : riemannZeta 1 = (↑Real.eulerMascheroniConstant - Complex.log (4 * ↑Real.pi)) / 2` and `riemannZeta_one_ne_zero : riemannZeta 1 ≠ 0`.
