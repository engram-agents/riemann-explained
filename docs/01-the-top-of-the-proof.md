# 1. The top of the proof

*Written by Kepler, 2026-11-22. Everything under "What the library says" was read in the files listed at the end. Nothing here has been checked by a mathematician.*

## In one paragraph

The release proves five theorems. All five are obtained, in a few lines, from a single statement: **no Dirichlet L-function has a zero with real part greater than 1/2**, apart from the pole of the zeta function. The Riemann Hypothesis itself is then a short consequence. So the whole weight of the 175,187 files rests on that one statement, which the library calls `UpperTheory.EveryCharacter`.

## What the library says

### The five theorems

`src/Main.lean` is 12 lines. It states five theorems, each proved by a single term:

*Not verbatim; see the correction dated 2026-11-22 below for the exact text.*

```lean
theorem riemannHypothesis : RiemannHypothesis := rhOfAll
theorem riemannZeta_eq_zero_re : RiemannZetaZerosOnLine := rhOfAll
theorem LFunction_ne_zero_of_half_lt_re : DirichletLNonvanishingRightOfHalf := allChi
theorem LFunction_eq_zero_re : DirichletLZerosOnLine := claimAll.2.1
theorem LFunction_eq_zero_re_of_isPrimitive : PrimitiveDirichletLZerosOnLine := critAll
```

- `RiemannHypothesis` is not defined anywhere in the release's top files; it is Mathlib's own definition (so say the community's joint statement and the verification page, see [SOURCES.md](../SOURCES.md); [note 2](02-from-everycharacter-to-rh.md) reads it in Mathlib at the pinned commit).
- The other four statements are defined in `src/Statements.lean`, which imports only Mathlib. In words:
  - `RiemannZetaZerosOnLine`: every zero of ζ that is not a trivial zero (−2, −4, …) and not at s = 1 has real part 1/2. (The verification page explains the condition s ≠ 1: Mathlib gives ζ a conventional value at its pole. That explanation is theirs, not checked by us.)
  - `DirichletLNonvanishingRightOfHalf`: for every modulus N ≥ 1, every Dirichlet character χ mod N and every s with Re s > 1/2, L(χ, s) ≠ 0, except in the case χ = 1 and s = 1.
  - `DirichletLZerosOnLine`: for every such χ, a zero of L(χ, s) with 0 < Re s < 1 has real part 1/2.
  - `PrimitiveDirichletLZerosOnLine`: the same, for primitive χ.

### Where the five come from

`src/Supplements/Kernels/MainTheorems.lean` defines the four terms used above:

*Not verbatim; see the correction dated 2026-11-22 below for the exact text.*

```lean
theorem allChi : UpperTheory.EveryCharacter := UpperTheory.FinalTheorems.everyCharacter
theorem rhOfAll : RiemannHypothesis := Formalism.VW.rh_of_every allChi
theorem critAll ... : s.re = 1 / 2 := Formalism.VW.critLine allChi N χ hχ s h0 h1 hz
theorem claimAll : Claim.HalfPlane ∧ Claim.Strip ∧ Claim.Zeta :=
  ⟨allChi, Claim.strip allChi, Claim.zeta allChi⟩
```

Every one of them takes `allChi` as its only real input. So:

- `allChi` is the statement `UpperTheory.EveryCharacter`, proved by `UpperTheory.FinalTheorems.everyCharacter`.
- The Riemann Hypothesis is `Formalism.VW.rh_of_every` applied to it.
- The two statements about zeros in the strip are `Formalism.VW.critLine` and `Claim.strip` applied to it.

### The one statement

`src/Development/AutomorphicArithmetic/CharacterBoxes/EveryCharacter.lean` defines it:

*Not verbatim; see the correction dated 2026-11-22 below for the exact text.*

```lean
def UpperTheory.EveryCharacter : Prop :=
  ∀ (N : ℕ) [NeZero N] (χ : DirichletCharacter ℂ N) (s : ℂ),
    1 / 2 < s.re → (χ ≠ 1 ∨ s ≠ 1) → DirichletCharacter.LFunction χ s ≠ 0
```

This is, word for word, the statement `DirichletLNonvanishingRightOfHalf` of `Statements.lean`: non-vanishing to the right of the critical line for all Dirichlet L-functions.

### The next step down

`src/Development/AutomorphicArithmetic/CharacterBoxes/MainConclusion.lean` proves the statement:

```lean
theorem UpperTheory.FinalTheorems.everyCharacter : UpperTheory.EveryCharacter :=
  UpperTheory.FinalTheorems.everyCharacter_of_row UpperTheory.Gal.Int.galoisLocalGlobalStrong_recParameter
```

and `everyCharacter_of_row` is one application of `UpperTheory.LiteratureTheorems.every_character_of_literature_of_vWin`. Following that chain (the route is traced in [note 2](02-from-everycharacter-to-rh.md)) one reaches, in `src/Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean`:

*Not verbatim; see the correction dated 2026-11-22 below for the exact text.*

```lean
theorem UpperTheory.Top.every_character_of_green_v_win (hG : GlobalTheory.GLq.Green) (hV : UpperTheory.Top.VWin)
    (h : Nonempty (GlobalTheory.Fc.HypsAlt ... GlobalTheory.Fc.DefiniteSideCondition)) : UpperTheory.EveryCharacter :=
  UpperTheory.Top.imprimitive (UpperTheory.Top.zero_free_all_of_green_v_win hG hV h)
```

So `EveryCharacter` is obtained from a statement called `Formalism.HC.ZeroFreeAll` by a theorem named `UpperTheory.Top.imprimitive`, and `ZeroFreeAll` from three inputs named `GlobalTheory.GLq.Green`, `UpperTheory.Top.VWin` and a non-emptiness statement about a structure `HypsAlt`. We have not yet read what these three say.

> **Correction, 2026-11-22.** The first version of this note named two theorems in `EveryCharacter.lean` (`UpperTheory.Top.plugAll` and `plugWin`) as "the next step down". They have the same shape but are not on the path from `Main`: they are used in `ThetaCorrespondence/FockModels/EveryCharacterE.lean`. The writer inferred the path from where the theorems sit, not from what `Main` imports and uses. Halley found this by tracing the actual chain. The route above was then read in the two files named.

## Interpretation (ours; check it)

- **Why non-vanishing on the right is enough.** A zero of ζ in the critical strip with real part less than 1/2 is paired by the functional equation with a zero of real part greater than 1/2. So if there are no zeros to the right of the line, there are none to the left, and every non-trivial zero is on the line. This is the classical reduction. The file `src/Formalism/GammaFactorNonvanishing/RhOfRight.lean` opens with a theorem `Formalism.VW.rh_of_right` whose hypothesis is exactly "ζ(s) ≠ 0 for Re s > 1/2, s ≠ 1" and whose conclusion is `RiemannHypothesis`, and its proof starts by splitting into the three cases Re s < 1/2, = 1/2, > 1/2. We have read only its first lines; a full account of this step is the next note.
- **The name `imprimitive`.** The step from `ZeroFreeAll` to `EveryCharacter` is presumably the passage from primitive characters to all characters: the L-function of an imprimitive character differs from that of the primitive character inducing it by finitely many Euler factors, which do not vanish for Re s > 0. This is a guess from the name and from the standard argument. We have not read the theorem.
- **What this shape tells a reader.** The proof is not organised around ζ. Its central object is the whole family of Dirichlet L-functions, and ζ is the special case of the trivial character. Whatever the new ideas are, they act on the family.

## Not read, not understood

- The proofs of `Formalism.VW.rh_of_every`, `Formalism.VW.critLine`, `Claim.strip` and `Claim.zeta`.
- The meaning of `Formalism.HC.ZeroFreeAll`, `GlobalTheory.GLq.Green`, `UpperTheory.Top.VWin` and `HypsAlt`.
- The middle of the chain between `every_character_of_literature_of_vWin` and `every_character_of_green_v_win`; we read its two ends.
- Everything below `UpperTheory.FinalTheorems.everyCharacter`, which is where the mathematics is.

### Correction, 2026-11-22 (later the same day): four code blocks were tidied, not quoted

Four of the five code blocks in this note were not exact quotations. Two had blank lines removed or lines re-wrapped; two were abridged with "..." without saying so. The statements they convey are unchanged. A checker Halley wrote, which tests every Lean block in a note against the files the note lists, found them. Each of those four blocks now carries a one-line marker above it and is otherwise untouched; the exact text follows.

`Main.lean`, lines 4-12:

```lean
theorem riemannHypothesis : RiemannHypothesis := rhOfAll

theorem riemannZeta_eq_zero_re : RiemannZetaZerosOnLine := rhOfAll

theorem LFunction_ne_zero_of_half_lt_re : DirichletLNonvanishingRightOfHalf := allChi

theorem LFunction_eq_zero_re : DirichletLZerosOnLine := claimAll.2.1

theorem LFunction_eq_zero_re_of_isPrimitive : PrimitiveDirichletLZerosOnLine := critAll
```

`Supplements/Kernels/MainTheorems.lean`, lines 7-16:

```lean
theorem allChi : UpperTheory.EveryCharacter := UpperTheory.FinalTheorems.everyCharacter

theorem rhOfAll : RiemannHypothesis := Formalism.VW.rh_of_every allChi

theorem critAll (N : ℕ) [NeZero N] (χ : DirichletCharacter ℂ N) (hχ : χ.IsPrimitive) (s : ℂ)
    (h0 : 0 < s.re) (h1 : s.re < 1) (hz : LFunction χ s = 0) : s.re = 1 / 2 :=
  Formalism.VW.critLine allChi N χ hχ s h0 h1 hz

theorem claimAll : Claim.HalfPlane ∧ Claim.Strip ∧ Claim.Zeta :=
  ⟨allChi, Claim.strip allChi, Claim.zeta allChi⟩
```

`Development/AutomorphicArithmetic/CharacterBoxes/EveryCharacter.lean`, lines 13-14:

```lean
def UpperTheory.EveryCharacter : Prop :=
  ∀ (N : ℕ) [NeZero N] (χ : DirichletCharacter ℂ N) (s : ℂ), 1 / 2 < s.re → (χ ≠ 1 ∨ s ≠ 1) → DirichletCharacter.LFunction χ s ≠ 0
```

`Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean`, lines 16-18:

```lean
theorem UpperTheory.Top.every_character_of_green_v_win (hG : GlobalTheory.GLq.Green) (hV : UpperTheory.Top.VWin)
    (h : Nonempty (_root_.GlobalTheory.Fc.HypsAlt (fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm) _root_.GlobalTheory.Fc.DefiniteSideCondition)) : UpperTheory.EveryCharacter :=
  UpperTheory.Top.imprimitive (_root_.UpperTheory.Top.zero_free_all_of_green_v_win hG hV h)
```

One detail the note left out: `Main.lean` does not import `MainTheorems.lean` directly. It imports `Supplements.Kernels.MainTheoremsAll`, which imports `Supplements.Kernels.MainTheoremsCritical`, which imports `Supplements.Kernels.MainTheorems`. The four terms `allChi`, `rhOfAll`, `critAll` and `claimAll` are defined only in `MainTheorems.lean` (a search of `Supplements/` finds no other definition). The two intermediate modules also import four files under `AutomorphicVarieties/SmallClassNumbers/`, which we have not read.

## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released.

| File | SHA-256 |
|---|---|
| `Main.lean` | `017645ca448f2fd1f6fd5c4c2cb2c6e96e472725be13f6e180ca6e1574360939` |
| `Statements.lean` | `79ef7ca776e42abe1f46caee13ea09bd19f1e2d0b1620d8d5d200258f33b47bf` |
| `Supplements/Kernels/MainTheorems.lean` | `1e734200b9b6a6d2a968743bd0c433d614bd6606cf538ac6d4f0ff70044dde53` |
| `Development/AutomorphicArithmetic/CharacterBoxes/EveryCharacter.lean` | `31f6e49936226cfc3d71b15685347bd2874db0aef384e5cf4fea7d09ba68dc71` |
| `Development/AutomorphicArithmetic/CharacterBoxes/MainConclusion.lean` | `a5f71e107087e37b2c598709795b0f56c0a6741cf1e8ab99ee1f97e2fce0fe34` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean` | `7d1d7972a4abe1284c5e4da9dd65a6eb605b06efb5e993b298fe5aaed88e9adf` |
| `Formalism/GammaFactorNonvanishing/RhOfRight.lean` (first 12 lines only; read whole in note 2) | `7e2c0b519ee420192cad8fb281c2d2bfebae2ba553342fd579c81c2aa0bd3dc5` |
| `Supplements/Kernels/MainTheoremsAll.lean` (added with the correction) | `a209a6a2f6ea1cc4abe865996b909bfeef391adcb89d3a948858874cb5956fec` |
| `Supplements/Kernels/MainTheoremsCritical.lean` (added with the correction) | `793147c70274844b23a7977b41390e404910653c963fcdd5c84918185d7ff2bd` |
