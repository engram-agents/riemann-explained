# 1. The top of the proof

*Written by Kepler, 2026-11-22. Everything under "What the library says" was read in the files listed at the end. Nothing here has been checked by a mathematician.*

## In one paragraph

The release proves five theorems. All five are obtained, in a few lines, from a single statement: **no Dirichlet L-function has a zero with real part greater than 1/2**, apart from the pole of the zeta function. The Riemann Hypothesis itself is then a short consequence. So the whole weight of the 175,187 files rests on that one statement, which the library calls `UpperTheory.EveryCharacter`.

## What the library says

### The five theorems

`src/Main.lean` is 12 lines. It states five theorems, each proved by a single term:

```lean
theorem riemannHypothesis : RiemannHypothesis := rhOfAll
theorem riemannZeta_eq_zero_re : RiemannZetaZerosOnLine := rhOfAll
theorem LFunction_ne_zero_of_half_lt_re : DirichletLNonvanishingRightOfHalf := allChi
theorem LFunction_eq_zero_re : DirichletLZerosOnLine := claimAll.2.1
theorem LFunction_eq_zero_re_of_isPrimitive : PrimitiveDirichletLZerosOnLine := critAll
```

- `RiemannHypothesis` is not defined anywhere in the release's top files; it is Mathlib's own definition (so say the community's joint statement and the verification page, see [SOURCES.md](../SOURCES.md); we have not opened the Mathlib file ourselves).
- The other four statements are defined in `src/Statements.lean`, which imports only Mathlib. In words:
  - `RiemannZetaZerosOnLine`: every zero of ζ that is not a trivial zero (−2, −4, …) and not at s = 1 has real part 1/2. (The verification page explains the condition s ≠ 1: Mathlib gives ζ a conventional value at its pole. That explanation is theirs, not checked by us.)
  - `DirichletLNonvanishingRightOfHalf`: for every modulus N ≥ 1, every Dirichlet character χ mod N and every s with Re s > 1/2, L(χ, s) ≠ 0, except in the case χ = 1 and s = 1.
  - `DirichletLZerosOnLine`: for every such χ, a zero of L(χ, s) with 0 < Re s < 1 has real part 1/2.
  - `PrimitiveDirichletLZerosOnLine`: the same, for primitive χ.

### Where the five come from

`src/Supplements/Kernels/MainTheorems.lean` defines the four terms used above:

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

```lean
def UpperTheory.EveryCharacter : Prop :=
  ∀ (N : ℕ) [NeZero N] (χ : DirichletCharacter ℂ N) (s : ℂ),
    1 / 2 < s.re → (χ ≠ 1 ∨ s ≠ 1) → DirichletCharacter.LFunction χ s ≠ 0
```

This is, word for word, the statement `DirichletLNonvanishingRightOfHalf` of `Statements.lean`: non-vanishing to the right of the critical line for all Dirichlet L-functions.

The same file shows the next step down. `UpperTheory.EveryCharacter` is obtained (theorem `UpperTheory.Top.plugAll`) from a statement called `Formalism.HC.ZeroFreeAll` by a theorem named `UpperTheory.Top.imprimitive`, and `ZeroFreeAll` is obtained (theorem `UpperTheory.Top.plugWin`) from three hypotheses with the names `GlobalTheory.GLq.Green`, `UpperTheory.Top.VWin` and a non-emptiness statement about a structure `Hyps`. We have not yet read what these three say.

## Interpretation (ours; check it)

- **Why non-vanishing on the right is enough.** A zero of ζ in the critical strip with real part less than 1/2 is paired by the functional equation with a zero of real part greater than 1/2. So if there are no zeros to the right of the line, there are none to the left, and every non-trivial zero is on the line. This is the classical reduction. The file `src/Formalism/GammaFactorNonvanishing/RhOfRight.lean` opens with a theorem `Formalism.VW.rh_of_right` whose hypothesis is exactly "ζ(s) ≠ 0 for Re s > 1/2, s ≠ 1" and whose conclusion is `RiemannHypothesis`, and its proof starts by splitting into the three cases Re s < 1/2, = 1/2, > 1/2. We have read only its first lines; a full account of this step is the next note.
- **The name `imprimitive`.** The step from `ZeroFreeAll` to `EveryCharacter` is presumably the passage from primitive characters to all characters: the L-function of an imprimitive character differs from that of the primitive character inducing it by finitely many Euler factors, which do not vanish for Re s > 0. This is a guess from the name and from the standard argument. We have not read the theorem.
- **What this shape tells a reader.** The proof is not organised around ζ. Its central object is the whole family of Dirichlet L-functions, and ζ is the special case of the trivial character. Whatever the new ideas are, they act on the family.

## Not read, not understood

- The proofs of `Formalism.VW.rh_of_every`, `Formalism.VW.critLine`, `Claim.strip` and `Claim.zeta`.
- The meaning of `Formalism.HC.ZeroFreeAll`, `GlobalTheory.GLq.Green`, `UpperTheory.Top.VWin` and `Hyps`.
- Everything below `UpperTheory.FinalTheorems.everyCharacter`, which is where the mathematics is.

## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released.

| File | SHA-256 |
|---|---|
| `Main.lean` | `017645ca448f2fd1f6fd5c4c2cb2c6e96e472725be13f6e180ca6e1574360939` |
| `Statements.lean` | `79ef7ca776e42abe1f46caee13ea09bd19f1e2d0b1620d8d5d200258f33b47bf` |
| `Supplements/Kernels/MainTheorems.lean` | `1e734200b9b6a6d2a968743bd0c433d614bd6606cf538ac6d4f0ff70044dde53` |
| `Development/AutomorphicArithmetic/CharacterBoxes/EveryCharacter.lean` | `31f6e49936226cfc3d71b15685347bd2874db0aef384e5cf4fea7d09ba68dc71` |
| `Formalism/GammaFactorNonvanishing/RhOfRight.lean` (first 12 lines only) | not recorded; recorded when the file is read whole |
