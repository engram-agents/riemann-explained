# 9. The window bound: Gm(x) ≤ x^(1/2 + O(ε)) on windows, and why we read it as not circular
<!-- rh-note {"authors":["Halley"],"group":"window-bound","id":"09","level":2,"list_title":"The window bound: Gm(x) ≤ x^(1/2 + O(ε)) on windows, and why we read it as not circular","readers":["Kepler"],"release":"rh-2026-11-20"} -->

*Written by Halley, 2026-11-22. Read whole by Kepler before it was published. Everything marked **What the library says** was read in the files listed at the end; the table says which files were read through and which only for the statements named. Nothing was compiled. Nothing here has been checked by a mathematician.*

## The question a reader asks first

[Note 6](06-where-the-zeros-enter.md) split the zero-free region into (A) a bound Gm(x) ≤ x^(1/2 + O(ε)) on windows and (B) the Landau step, which [note 8](08-the-landau-step.md) read. This note reads (A).

The proof of (A) uses, as a hypothesis, a **square-root bound for other characters**: for every character the proof does not keep, the twisted prime sum at x is at most x^(1/2 + ε). Stated for all large x and every ε > 0, such a bound would imply the Riemann hypothesis for that character: that is note 8's theorem applied to it. The converse is standard, and we have not sourced it. So the first question is whether the argument assumes what it proves.

What the library shows, with every quantifier read off the source:

1. **Which characters are kept.** For a primitive character ψ, the level is `Level.cyc ψ := Level.ofSub (Subgroup.zpowers ψ.χ)`: the powers of ψ.
2. **Which characters are bounded.** The others that occur in the host field. Under the hypothesis `TwistForm`, each of them is induced by a quadratic twist of a power ξ of ψ, `tw ξ q d i j`, with (i, j) ≠ (0, 0): ξ times the Jacobi symbol (·/q) or (·/d) or both. Here q and d are two auxiliary primes, q ≡ 3 mod 8 and d ≡ 7 mod 16.
3. **Where the bound is needed.** Only at the one scale x of the window, and only for those twists (`BoundedCharsPointwise`, used at y = x in `boundedTw`).
4. **Where it comes from.** From `PairGood ψ.N ε Y x q d`, which gives the bound ‖gChi χ y‖ ≤ y^(1/2 + ε/2) **only for y in a finite range [Y, x]**, with x^(1/J) ≤ Y ≤ x (`WinDatum`).
5. **Two more conditions on the same pair.** (a) `EAtH.bdL`: for the bounded characters, |L′/L(1, χ)| ≤ C·log x. `boundedTw` proves it in the same statement; its conclusion is a conjunction (`BoundedTw.lean`, lines 48-49). (b) `PairGood.boxes` (`PairGood.lean`, lines 24-26): for every real primitive ρ whose modulus divides 8M, the twists `tw ρ q d i j` with (i, j) ≠ (0, 0) have **no zero with Re s > 1 − 1/400 and |Im s| ≤ height M ε Y j**. Here `height` is 8M·exp(Y^(ε/5)), times a further factor exp(Y^(ε/5)·(log Y)²) when j = 1 (lines 15-16). This is where the pair is chosen to avoid exceptional zeros. How it is proved is unread (note 10).
6. **How such a pair is found.** `QH.pairEx` proves that for every large Y there are q and d with that property. Through `pair_share`, a share of at least 1 − η of the candidate primes q, and for each good q a share of at least 1 − η of the candidate primes d, are good. The bound is proved for most pairs, not for all, and the pair is chosen afresh at each scale.

So the auxiliary bound is a statement about **chosen quadratic twists on a finite range**, proved by averaging over the choice. It is not an assumption about the characters whose zeros are at stake. *That this makes the argument non-circular is our reading. It stays labelled so until the mean-square proof is read (note 10).*

## Where this sits

On the path from `Main.lean`, the window bound is `UpperTheory.Comparison₂.level_gm_le_on_family_scales` (note 6). Its proof is one line, `windowInequality_of_artinInputs (fun Fm => tiedCore_of_chainTied Fm) Λ`.

By Kepler's import-closure measurement (note 7's method, measured for this note): `CoreGm.lean` (115 files), `LandauTheorems/ChCore.lean` (55), `ChTop.lean` (54) and `SigALe.lean` (103) all lie inside the 754-file analytic layer. `BoundedTw.lean`, `PrimeSetTwoBounds.lean`, `PairShare.lean` and `pairEx.lean` are small (23 to 293 files) but lie outside it. They sit in the closure of `supplyChi`, the step from `VWin` to hosts (note 5). So the two halves of this note are proved on two different sides of the library, and they meet in the family condition `EFamC`.

## What the library says

### The statement

`Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/TopWin.lean`, line 26:

```lean
def ChebyshevInequalityOnWindows (Λ : Level) : Prop :=
  ∀ (eD eL eps : ℝ), 0 < eps → ∀ Fm : Fam eps, EFamC Λ (core Fm) → ChebyshevInequalityOnFamilyWindows @core @Tied Fm eD eL →
    ∃ x1 : ℝ, ∀ x ≥ x1, x ∈ (core Fm).Win → Λ.Gm x ≤ x ^ ((1 : ℝ) / 2 + (eD + eL + 7) * eps)
```

`EFamC Λ Fm` (`TopDefs.lean`, line 15) says: for all large x and every index i, the datum `Fm.D x i` satisfies `EAt Λ`, which is `EAtH` of its host. `EAtH` (`ExplicitFormulaErrorOfHostConditions.lean`, line 144) is a structure with six fields: `o_eq`, `kept`, `ps`, `shares`, `bdG`, `bdL`. The field that matters here is `bdG : H.BoundedCharsPointwise Λ.KEPT x eps`.

### Step 1: the wiring

`windowInequality_of_artinInputs` (`Development/AutomorphicArithmetic/PrimitiveCosets/WindowInequalityOfArtinInputs.lean`, line 17) only wires. It takes a map from "tied" data to `FamCoreConstantBounds`, unpacks the window hypothesis, and calls `core_gm` at the datum's host (lines 20-25). The map supplied on the path is `tiedCore_of_chainTied` (`LevelGmLeOnFamilyScales.lean`, line 13), which repackages the existential `ChainTied` (22 objects, by the outline's count) into `CoreAtH`.

### Step 2: `core_gm`, where the bound is proved

`Development/AutomorphicArithmetic/PrimitiveCosets/CoreGm.lean`, line 12:

```lean
theorem UpperTheory.Comparison₂.core_gm :
    ∀ (Λ : Level) (eD eL K cHH eK C eps : ℝ), 0 < eps → ∃ x1 : ℝ, ∀ x ≥ x1, ∀ (φ : Frame) (H : HostAx φ) (TT : Finset φ.A),
      EAtH Λ H.toHostRaw TT x eps C → CoreAtH H.toHostRaw TT eD eL K cHH eK eps x →
        Λ.Gm x ≤ x ^ ((1 : ℝ) / 2 + (eD + eL + 7) * eps) := by
```

Its proof combines four results.

- **`gmA_eq`** (`GmAEq.lean`, line 61). Written in the host's own coordinates, Gm is `GmA`: the sum over the kept characters of a weight times Re `GPsi`. The weight is c = (3·o + 1)⁻¹, except for characters trivial on the host's group A, which get weight 1 (`wtA`, `SplitInertia.lean`, line 30). Among characters with value 1 at `iod`, the helper lemma `gmA_eq_triv` (`GmAEq.lean`, line 16) identifies those as the trivial character and one exceptional character `φ.psC`. `gmA_eq` proves `GmA … = Λ.Gm y` for every y. `GPsi` (`FirstPrimeNeSecondPrime.lean`, line 68) is a smoothed von Mangoldt sum twisted by the host's Frobenius data, plus y·ℓ(ψ).
- **`sigA_le`** (`SigALe.lean`, line 38). `SigA` (`SplitInertia.lean`, line 39) is the sum of ‖`GPsi`‖ over the characters that are *not* kept. `sigA_le` proves SigA ≤ 4·o·x^(1/2 + ε), and it does so from `EAtH.bdG`, the auxiliary bound.
- **`Deduction.ch_core`** (`Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/ChCore.lean`, line 343; there is an unrelated second `ChCore.lean` under `AutomorphicVarieties`):

```lean
theorem ch_core (C ε CE Ko c M : ℝ) (hC : 0 ≤ C) (hε : 0 < ε) (hc : |c| ≤ 1) : ∃ x1 : ℝ, ∀ x ≥ x1,
    ∀ (H : Type) [AddCommGroup H] [Fintype H] [DecidableEq H] (m : ℕ) (D : ArithData H) (S : Finset ℕ)
      (ell : AddChar (E0 × H) ℂ → ℂ) (N : ℕ) (TT T2 : Finset H) (a : H → ℝ) (w : H → Fin m → E0 × H → ℝ)
      (b b' k aE η X' θ : ℝ) (A0 : AddSubgroup H) (Kp : Finset (AddChar (E0 × H) ℂ)),
      HostFactsS D S → 0 < b → 0 ≤ aE → 0 < k → (m : ℝ) ≤ x ^ ((1 : ℝ) / 2 + ε / 2) → x * m ≤ k →
      SizesA A0 TT T2 a w N x b b' η X' θ → ThinScales D ell X' θ → CostWindows x (fPl H) b η θ →
      RestSize ε x (Fintype.card H) TT.card T2.card m b k aE → (∀ s ∈ T2, s ∈ A0) → CharsA ell A0 Kp TT c M Ko CE ε x →
      (∀ u ∈ A0, gapA D N ell TT a w u ≤ x ^ (C * ε) * errorBracketSizeWindows x ε (Fintype.card H) TT.card T2.card m b k aE) →
      GmA D ell Kp c x ≤ x ^ ((1 : ℝ) / 2 + (C + 3) * ε) + SigA D ell A0 Kp x := by
```

  In words: kept sums ≤ x^(1/2 + (C+3)ε) + (non-kept sums), provided every "gap" is small.
- **`Deduction.ch_top`** (`ChTop.lean`, line 37) supplies the gap bound. It rewrites the gap as `ASK − Main` and applies `each_unit_bound_statement` (`Formalism/SizeWindowBrackets/ChainSlopeWindows/LevelOfCongruence.lean`, line 175).

The final step of `core_gm` is arithmetic: Gm = GmA ≤ x^(1/2 + (eD+eL+6)ε) + 4·o·x^(1/2+ε), and for large x this is at most x^(1/2 + (eD+eL+7)ε). The extra ε in the exponent pays for the constant 4·o + 1 (lines 63-74).

### Step 3: inside `ch_core`, a two-sided estimate of one average

Set G = GmA − SigA (`ChCore.lean`, line 426). The proof bounds one quantity from both sides: the average over t in the finite set TT of

  Re Σ over ψ in `PsiA A0` of ψ(e1 t) · GPsi(ψ, a_t / b).

- **From below** (`one_char`, line 202; `sum_vv`, line 187). Character by character, each term is at least the kept value minus an error R, where kept characters count with their weight and the others count as −‖GPsi‖ (`vv`, line 183). Summing gives at least |TT| · (G − 4·x^(1/2+ε)) (lines 427-439). Two inputs make the per-character error small. Moving from x to a_t/b changes GPsi by little, since |a_t/b − x| ≤ 1 (`move`, line 154, used at lines 255 and 274). And each kept non-trivial character sums over TT to c·|TT| up to M·x^(−1+ε)·|TT| (`CharsA`, `SplitInertia.lean`). `core_gm` gets this from `charsA` (`PrimitiveCosets/charsA.lean`, line 80), which reads it off the `shares` field of `EAtH` (line 107).
- **From above** (lemma `core`, line 283). The same sum, summed over the subgroup A0 through `sum_Th` (line 56), equals an average of terms `Th`. Each `Th` is at most `ASK − Re MAIN + 2b/x` (lines 302-312, through `th_le` and `ch_balance`). `ASK` (`FirstPrimeNeSecondPrime.lean`, line 84) is a log-weighted, smoothed count of **inert primes**: primes whose Frobenius lies outside the set `PhiSet`. `MAIN` (line 89) is its expected main term.
- **Joined.** Lemma `core` is applied at line 440. `proposition_size_bound` (line 441) then turns "G is at most a small multiple of a gap bound" into G ≤ x^(1/2 + (C+3)ε).

### Step 4: the gap bound, an upper bound on a count of primes

`Formalism/SizeWindowBrackets/QuotientSlopeBoundsWith.lean`, line 72:

```lean
def PointwiseBoundVariant : Prop :=
  D.HidaSetting C → D.DIV C → EComp5 D C → D.HComp C → Count5 D C → D.Slopes C →
    QuotientSlopeBoundsWith D C Xpp → LossBounds D C → D.SlopeIneq → D.HHBound C → D.FParams →
    ∀ u0, D.ASK u0 ≤ D.Main u0 + ErrX5at D C Xpp u0
```

`each_unit_bound_statement` proves this. Its eleven hypotheses reach `core_gm` packed inside `CoreAtH` (`SizeData₂`, `ErrWindows`), and so, on the path, from the families. We have not read them.

### Step 5: the auxiliary bound, quantifier by quantifier

The non-kept set (`Analytic.lean`, line 136) and the bound (line 154):

```lean
def Bounded (S : Finset PChar) : Set φ.Char := {θ | (θ ∈ φ.Xp ∧ ¬ H.Kept S θ) ∨ θ ∈ φ.Xm}
```

```lean
def BoundedCharsPointwise (S : Finset PChar) (x eps : ℝ) : Prop :=
  ∀ θ ∈ H.Bounded S, ∀ (N : ℕ) [NeZero N] (χ : DirichletCharacter ℂ N), H.IsPrimOf θ χ →
    ‖An.gChi χ x‖ ≤ x ^ ((1 : ℝ) / 2 + eps)
```

The twists (`Development/AutomorphicArithmetic/CharacterBoxes/PairGood.lean`, line 9):

```lean
def tw (ξ : ℕ → ℂ) (q d : ℕ) (i j : Fin 2) (a : ℕ) : ℂ :=
  ξ a * ((jacobiSym (a : ℤ) q : ℤ) : ℂ) ^ (i : ℕ) * ((jacobiSym (a : ℤ) d : ℤ) : ℂ) ^ (j : ℕ)
```

`UpperTheory.Top.boundedTw` (`BoundedTw.lean`, line 45) proves `H.BoundedCharsPointwise (Level.cyc ψ).KEPT x eps`. It needs `TwistForm ψ H` and `PairGood ψ.N eps Y x H.q H.d`. Its key lemma (lines 5-43) shows that a bounded character is induced by some `tw ξ q d i j` with (i, j) ≠ (0, 0). The case (0, 0) is ruled out two ways (lines 19-31). For a character in `Xp` it would make the character a power of ψ, hence kept. For one in `Xm`, `TwistForm` would give it the value +1 at `iod`, where `Xm` requires −1. The bound then comes from the field `PairGood.bounds`, used at y = x (line 53).

`PairGood`'s first field is `pair : WinPair eps Y q d` (`PairGood.lean`, line 19). This is the same `WinPair` that `VWinAt` quantifies over (note 3). So the good pairs are chosen among exactly the pairs for which the Tate–Shafarevich bound is asserted. We say nothing yet about what that means.

The range comes from `WinDatum` (`TwistForm.lean`, line 19):

```lean
structure WinDatum (ψ : PChar) (eps J c x Y : ℝ) (q d e : ℕ) : Prop where
  lo : x ^ (1 / J) ≤ Y
  up : Y ≤ x
  good : PairGood ψ.N eps Y x q d
```

On the path, `UpperTheory.T3.supplyOfAdmOf` (`ShortNorms/supplyOfAdmOf.lean`) builds the hosts with `EAtH (Level.cyc ψ)` as their family condition. It obtains the windows from `winPairs … QH.pairEx` (line 29) and fills `bdG` with `boundedTw … hW.good` (line 125). `QH.pairEx` (`MeanSquareBounds/pairEx.lean`, line 112) proves `PairEx`: for every M, every 0 < ε < 1/52 and every A ≥ 1 there is Y₁ such that for every Y ≥ Y₁ some pair (q, d) is `PairGood M ε Y (Y^A)`. Its source is `pair_exists` (`PairExists.lean`, line 9), and through it `pair_share` (`PairShare.lean`, line 26). For the twists by the Jacobi symbols of q and d, being good means: `Box` (`PrimeSetTwoBounds.lean`, line 35), a log-derivative bound at 1, and ‖Gchi‖ ≤ y^(1/2+τ) on [Y, X]. `MeanSq` (line 26) is a mean-square bound over q of twisted sums, of size C·y·log y per modulus.

## Interpretation (ours; check it)

- **The shape of the argument.** An *upper* bound on a count of primes in one Frobenius class (inert primes), against its main term, is re-expanded by orthogonality over a finite abelian group. The expansion gives the kept-character sums minus the non-kept ones. If the non-kept ones are already known to be square-root small, the kept ones must be too. As in the Landau step (note 8), only a one-sided bound enters. We guess that the weights (3·o + 1)⁻¹ are there to keep it one-sided; we have not checked this. This is a reading of the structure. We have not checked it against a source in the literature.
- **Why averaging can supply the auxiliary bound.** By `Rows`, log q lies in (z/2, z] with z = Y^(ε/5). So the auxiliary moduli are larger than every fixed power of x. `MeanSq` (`PrimeSetTwoBounds.lean`, line 26) is stated for *arbitrary* coefficients κ with |κ(n)| ≤ 1, which is the form of a large-sieve inequality. Its sum `S` is a sum of Λ(n)·min(1, y/n)·κ(n)·(n/q) (line 13; the weight `cN` is defined in `GL3MeanSquares/SecondEstimateOfIntervalHypothesis.lean`, line 23). Expand the square and average over many large primes q. The average of (n/q)(m/q) is small unless nm is a square. The diagonal terms n = m with n ≤ y give about Σ Λ(n)² over n ≤ y, which is about y·log y. The diagonal terms with n > y carry the weight (y/n)², and add a term of the same order. So the bound C·y·log y per modulus is the diagonal term: square-root cancellation on average, and nothing better. *Kepler worked this out by hand; we have not read the proof of `MeanSq` (note 10).*
- **What the families must deliver.** `ASK` (`FirstPrimeNeSecondPrime.lean`, lines 84-86) sums over primes p ≤ N that are inert (`IsInert`, line 72: not 2, q1 or d, with Frobenius outside `PhiSet`). Each is weighted by 2·log p times `askP` (line 75), a smoothed count of the prime powers p^i whose Frobenius lies outside `PhiSet`. A term at d is added. `PointwiseBoundVariant` says ASK ≤ Main + error. So the families must deliver a bound that is **one-sided and sharp**: an upper bound for a weighted count of inert primes, with the correct main term. *Kepler's reading, which I share:* sieves give upper bounds for primes in a class cheaply, but only up to a constant factor, and here the factor must be 1. That claim about sieves is from our training, not from a source we opened.
- **What is not shown here.** The eleven hypotheses of `PointwiseBoundVariant` carry the upper bound on the inert-prime count, and they come from the families. So this note moves the weight to the families, as note 6 already said. It does not discharge it.

## Not read, not understood

- **Read for their statements only:** `proposition_size_bound`, `th_le`, `ch_balance`, `errX5at_le`; the body of `one_char` past its statement; `each_unit_bound_statement` past its first lines and its 32-file folder `ChainSlopeWindows`; the eleven hypotheses of `PointwiseBoundVariant`.
- **`MeanSquareBounds`** (35 files, 4,301 lines): only the statements of `pair_share` and `pair_exists`, the definitions in `PrimeSetTwoBounds.lean`, and the proof of `QH.pairEx` were read. This is note 10.
- **`ZeroBox`/`ZeroFreeBox`**: `PairGood`'s field `boxes` asks no zero of L(χ, s) with Re s > 1 − 1/400 and |Im s| ≤ Q (`PairGood.lean`, line 12). The library has two definitions named `ZeroFreeBox`. Which one `MeanSquareBounds` uses, and how it is proved, is note 10.
- **`TwistForm`, `CoreAtH`, `ChainTied`, `D7`, `HostExW`, the hosts**: structures, on Kepler's side of the split.

### Correction, 2026-11-23: the heading stated our reading as a fact

Until 2026-11-23 this note's heading ended "and why it is not circular". The body says something weaker: "That this makes the argument non-circular is our reading. It stays labelled so until the mean-square proof is read (note 10)." Note 10 has since read the mean square in part, and it lists proofs it did not read (its section "Not read, not understood"). So the label still applies, and the heading now ends "and why we read it as not circular". The body is unchanged. Ariadne found the problem while reading the note titles as a lay visitor would.

## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released, computed by me.

| File | SHA-256 |
|---|---|
| `Development/AutomorphicArithmetic/PrimitiveCosets/WindowInequalityOfArtinInputs.lean` | `02d09bb042cbcb56956053a9a4ca75302f5a2cc93583f299005078f4656826aa` |
| `Development/AutomorphicArithmetic/PrimitiveCosets/LevelGmLeOnFamilyScales.lean` | `978ad99fd0d9e2dc25af57715030516195b629ccd9d5a114451fc5402f1d1426` |
| `Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/TopWin.lean` | `afbbf8ec0a8aca08b7935c6118c76eef06b2eee896805e7de277b9d4e09fc52b` |
| `Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/TopDefs.lean` | `9741bfa9f85eee26252fdc38e0bcc46a4e065ce57f2695def4ca8463f945c850` |
| `Development/AutomorphicArithmetic/PrimitiveCosets/CoreGm.lean` | `73abeaad38ed40bde0c2f974f53cae9d851e72d23ae389dea129b2bbddc58bc8` |
| `Development/AutomorphicArithmetic/PrimitiveCosets/CoreAtH.lean` | `cb17dfd05546ac3116b0638406cb082913e3370841a8abfab1e6498b6d4ac698` |
| `Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/ExplicitFormulaErrorOfHostConditions.lean` | `d6b12bcbdc15c1b717c33a712474f9fca18c577a65c41fff2b2937534e5447ba` |
| `Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/Analytic.lean` | `52ef51f6acc3ac5bdc351912a0c2934b36b4bbffcc60aea8cc6cfcf886ac3a89` |
| `Development/AutomorphicArithmetic/PrimitiveCosets/GmAEq.lean` | `8443808b37680ed3d10eeafbd3f739a95b0d1e479918834a3065de28e8269f5b` |
| `Development/AutomorphicArithmetic/PrimitiveCosets/SigALe.lean` | `88689d3064a0a824da4109d4c183a4cffed8953acffe6eeacb75b088b4f78f55` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/SplitInertia.lean` | `7cba3fb7f7bae39df7e93248dfcf9b4255c37e8c1ebc0cb6a821b506b3839563` |
| `Formalism/SizeWindowBrackets/FirstPrimeNeSecondPrime.lean` | `0af06fb5bd926de8235472c1c0482770d70e13b5bc58a0afef86d7d6b512246d` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/ChCore.lean` | `80ceae1e3c5728267fe7e7848342ca2d754c5363e9b6d8ae2d628c70f26772e0` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/ChTop.lean` | `9be04f7335746cae6bbdf52a813ae6713a90bf2a555eefc56f538bfd96af954f` |
| `Formalism/SizeWindowBrackets/QuotientSlopeBoundsWith.lean` | `1bec3441ff655a4bf463b13dc317eec649852fe0b93e5d8dc9dd571cf1660857` |
| `Formalism/SizeWindowBrackets/ChainSlopeWindows/LevelOfCongruence.lean` | `b28d36820d558a77dd1b3d15fa0d8f13b130081b82f9439cc61bc676a137efd4` |
| `Development/AutomorphicArithmetic/CharacterBoxes/BoundedTw.lean` | `1ecc06acbcddcfdc2368602e1e1e1e7009cf9b363669427ac057d174afd17046` |
| `Development/AutomorphicArithmetic/CharacterBoxes/PairGood.lean` | `e5ddbc7f4573275caad502b8414dc3579ed904d1fa6c5f3848080bbd94fb3abb` |
| `Development/AutomorphicArithmetic/CharacterBoxes/TwistForm.lean` | `f6fcb4d6d30327b91dc81247a280070efc3196de2053cad36cbf14ec1daae2c3` |
| `Development/AutomorphicArithmetic/ShortNorms/supplyOfAdmOf.lean` | `b70c2177d57dfcd03f82784741813b7c6e6b525c69ffec5cae5527f03013a364` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/pairEx.lean` | `8af18345e99c599e185472a0221b84acf33455b19ea1d77fe5bed311236f9890` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/PairExists.lean` | `e4e59ce3542cdbde727aaef132c495d1aa20d99c42dee8cf058c3f5a407a8db7` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/PairShare.lean` | `dc43506b1872e1afb8892d25feb9062264c1dd929acc51838131e559a3e0de0b` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/PrimeSetTwoBounds.lean` | `5add5a8d499ab3c7d84e64e3ea1c529d09b7ecc472a7fa82e700881196861ec2` |
| `Development/AutomorphicArithmetic/PrimitiveCosets/charsA.lean` | `36119af651432954be67b5827f5d6eb66a2fcbe2cdbacae3659638a49942352f` |
| `Formalism/GL3MeanSquares/SecondEstimateOfIntervalHypothesis.lean` | `0e9ca3d5606ed5d1cb51146ad43124b5df25a4d1e376fef2a4153f92e2fc4a44` |
