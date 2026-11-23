# 12. The zero-density box: few characters have a zero near Re s = 1
<!-- rh-note {"authors":["Halley"],"group":"window-bound","id":"12","level":2,"list_title":"The zero-density box: few characters have a zero near Re s = 1","readers":["Kepler"],"release":"rh-2026-11-20"} -->

*Written by Halley, 2026-11-22. Read whole by Kepler before it was published. Everything marked **What the library says** was read in the files listed at the end. The table says, file by file, what was read: a file read through, a proof read for its step structure, or a statement only. The lean blocks were cut from the source by line range with a script. Nothing was compiled. Nothing here has been checked by a mathematician.*

## In short

[Note 10](10-how-the-good-pair-is-found.md) chooses the auxiliary primes so that the twisted characters have no zero in a box near Re s = 1. It needs to know that **few** characters have such a zero. This note reads that count.

- **The statement.** For every Q ≥ 3, at most C·Q^(1/4) primitive Dirichlet characters of modulus at most Q have a zero with Re s > 1 − 1/400 and |Im s| ≤ Q.
- **How much stands behind it:** **26 modules**, counting the theorem's own file, out of 175,187 files in the release. That is the import closure of `CountZAll.lean`, which I measured with Kepler's `import_closure.py` (note 7's method). The proof itself sits in ten files matching `CountZ*.lean`: eight step files (1,096 lines) plus the definitions file `CountZDefs.lean` (80 lines) and the assembly `CountZAll.lean` (17 lines), 1,193 lines in all, counted with `wc -l`.
- **The argument has three parts.**
  - *Detection.* At such a zero, a mollified Dirichlet series must be large on one of a few dyadic blocks.
  - *Counting.* A duality inequality bounds how many characters can be large on the same block. It uses only the trivial bound for sums of χ·χ̄′.
  - *Parameters.* A choice of parameters turns that into Q^(1/4).

## What the library says

### The statement and its assembly

`Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountSt.lean`, line 7:

```lean
def ZeroDensityBox : Prop :=
  ∃ C : ℝ, ∀ (Q : ℝ) (S : Finset (Σ N : ℕ, DirichletCharacter ℂ (N + 1))), 3 ≤ Q →
    (∀ p ∈ S, p.2.IsPrimitive ∧ ((p.1 + 1 : ℕ) : ℝ) ≤ Q ∧
      ∃ s : ℂ, 1 - 1 / 400 < s.re ∧ |s.im| ≤ Q ∧ DirichletCharacter.LFunction p.2 s = 0) →
    (S.card : ℝ) ≤ C * Q ^ (1 / 4 : ℝ)
```

`CountZAll.lean`, line 13, assembles it from five named steps:

```lean
theorem zero_density_box : Formalism.HermitianLattices.Ext.PrimitiveCharacterCasts.ZeroDensityBox :=
  final_bound_of_assembly (coefficient_square_bound Formalism.FX.divisor_weight_bound) (zero_detection mollifier_identity)
    (blockCountOf_statement duality_inequality (pair_twist_bound pair_sum_bound)) numeric_constants
```

Each step is a `Prop` defined in `CountZDefs.lean` (80 lines, read through). `final_bound_of_assembly` (`CountZFinal.lean`) has the type `CoeffSq → Detect → BlockCount → Num → ZeroDensityBox`, and its body is not read.

`count_bad`, which note 10 uses, re-indexes this statement: it is about primes q that carry a bad character of modulus f·q, with f ≤ F (`CountBadCore.lean`, lines 18-61).

### Step 1: the mollifier identity

```lean
def MollId : Prop :=
  ∀ (q : ℕ) [NeZero q] (χ : DirichletCharacter ℂ q) (s : ℂ) (Y N K : ℕ), 1 ≤ Y → Y ≤ N → Y * N ≤ K →
    (∑ n ∈ Icc 1 N, χ (n : ZMod q) * (n : ℂ) ^ (-s)) *
        (∑ d ∈ Icc 1 Y, (((μ d : ℤ)) : ℂ) * χ (d : ZMod q) * (d : ℂ) ^ (-s)) =
      1 + ∑ n ∈ Ioc Y K, mco Y N n * χ (n : ZMod q) * (n : ℂ) ^ (-s)
```

Here `mco Y N n` is the sum of μ(d) over the factorizations n = d·m with d ≤ Y and m ≤ N (lines 18-19). `mollifier_identity` (`CountZMoll.lean`, line 79) proves it. The helper `mco_eq_zero` (line 53) shows the coefficient vanishes for 2 ≤ n ≤ Y. That is why the sum on the right starts after Y.

### Step 2: zero detection

The parameters (`CountZDefs.lean`, lines 48-51), with X = ⌈Q⌉: Y = X⁴, J = 8·(⌊log₂ X⌋ + 1), N = 2^J.

```lean
def q0 (Q : ℝ) : ℕ := ⌈Q⌉₊
def pY (Q : ℝ) : ℕ := q0 Q ^ 4
def pJ (Q : ℝ) : ℕ := 8 * (Nat.log 2 (q0 Q) + 1)
def pN (Q : ℝ) : ℕ := 2 ^ pJ Q
```

```lean
def Detect : Prop :=
  ∀ (Q : ℝ), 20 ≤ Q → ∀ p : PC, p.2.IsPrimitive → p.1 ≠ 0 → ((p.1 + 1 : ℕ) : ℝ) ≤ Q →
    ∀ ρ : ℂ, s0 < ρ.re → |ρ.im| ≤ Q → DirichletCharacter.LFunction p.2 ρ = 0 →
      ∃ j ∈ range (pJ Q), 1 / (2 * (pJ Q : ℝ)) ≤ ‖blk (pY Q) (pN Q) (pY Q * 2 ^ j) p ρ‖
```

`blk Y N U p s` is the block Σ_{U < n ≤ 2U} mco(n)·χ(n)·n^(−s) (lines 21-22). `zero_detection` (`CountZDetect.lean`, line 43) proves `Detect` from the identity. Its steps, read in structure:
1. It bounds the tail of L(ρ, χ) beyond N by a partial-summation estimate (`Formalism.FX.l_function_partial_sum`) and the bound for character sums over an interval.
2. Since N ≥ X⁸ and Re ρ > 15/16, it shows tail × Y ≤ 1/2 (`hnum`).
3. At a zero, L(ρ) = 0, so the partial sum to N equals minus the tail. Multiplying by the mollifier, whose size is at most Y (`mollM_norm_le`), the identity says that 1 + (the sum of the blocks) has norm at most 1/2.
4. So the J dyadic blocks sum to something of norm at least 1/2, and one of them has norm at least 1/(2J).

### Step 3: counting characters with a large block

The duality inequality (`CountZDefs.lean`, line 24; proved as `duality_inequality`, `CountZDual.lean`, line 9):

```lean
def DualIneq : Prop :=
  ∀ (ι κ : Type) (S : Finset ι) (I : Finset κ) (b : κ → ℂ) (v : ι → κ → ℂ) (Δ : ℝ), 0 ≤ Δ →
    (∀ i ∈ S, ∑ j ∈ S, ‖∑ n ∈ I, v i n * (starRingEnd ℂ) (v j n)‖ ≤ Δ) →
    ∑ i ∈ S, ‖∑ n ∈ I, b n * v i n‖ ^ 2 ≤ (∑ n ∈ I, ‖b n‖ ^ 2) * Δ
```

`blockCountOf_statement` (`CountZBlock.lean`, line 23) applies it as follows:
- the coefficients are b(n) = mco(n)·n^(−s0), with s0 = 1 − 1/400;
- each character with a zero ρ gives v(n) = χ(n)·n^(−(ρ − s0)), so that b·v is a term of the block;
- the row bound is Δ = U + |T|·8Q³ (lines 29-31), and the inequality is applied at line 114.

The diagonal of the row bound is at most U (`hdiag`, line 40). The off-diagonal (`hoff`, line 61) comes from `PairTwist`, a partial-summation form of `PairSum`:

```lean
def PairSum : Prop :=
  ∀ p p' : PC, p.2.IsPrimitive → p'.2.IsPrimitive → p ≠ p' → ∀ M : ℕ,
    ‖∑ n ∈ range M, cv p n * (starRingEnd ℂ) (cv p' n)‖ ≤ (((p.1 + 1) * (p'.1 + 1) : ℕ) : ℝ)
```

`pair_sum_bound` (`CountZPair.lean`, line 98) proves `PairSum` in two lines. χ·χ̄′ is a non-trivial character of modulus q·q′ (`mulLevel_ne_one`), so its partial sums are bounded by its modulus.

The coefficient side is `CoeffSq` (line 44), proved by `coefficient_square_bound` (`CountZMoll.lean`, line 133) from a divisor bound:

```lean
def CoeffSq : Prop :=
  ∃ C : ℝ, 0 ≤ C ∧ ∀ Y N U : ℕ, 1 ≤ U →
    ∑ n ∈ Ioc U (2 * U), (‖mco Y N n‖ * (n : ℝ) ^ (-s0)) ^ 2 ≤ C * (U : ℝ) ^ (-(197 / 200 : ℝ))
```

Putting the pieces together, a set T of characters, each with a block of size at least 1/(2J), has at most 8J²·C·U^(3/200) members (`BlockCount`, lines 58-66). This holds provided 8Q³·C·U^(−197/200) is small enough to absorb the off-diagonal term.

### Step 4: the parameters

`Num` (lines 68-72) says that, for large Q, the dyadic block sizes U = Y·2^j satisfy that smallness condition for every j < J. It also says the total over the J blocks, 1 + J·8J²·C·(Y·2^J)^(3/200), is at most C′·Q^(1/4). `numeric_constants` (`CountZNum.lean`, line 10) proves it, and its proof is not read.

## Interpretation (ours; check it)

- **Why the exponent is 1/4.** *Our arithmetic from the definitions, not from the proof of `Num`:* Y·2^J is about X⁴·X⁸ = X¹², and (X¹²)^(3/200) = X^(36/200). With the factors of J ≈ 8·log₂ X, that is below X^(1/4) for large X. So 1/4 is a convenient round bound, not a sharp one.
- **Why the trivial pair bound is enough.** Near Re s = 1 the weights n^(−s) are small enough that the crude bound |Σ χχ̄′| ≤ q·q′ for distinct characters suffices. The price is the factor Q³ in Δ, which the large block sizes U absorb. *Among the theorems the assembly cites, none is a Pólya–Vinogradov or large-sieve inequality; we did not search every helper.*
- **The method's name.** This has the shape of the mollifier zero-detection method associated in the literature with Montgomery, combined with a duality inequality of Halász–Montgomery type. *Both names are from training, not sourced: the Montgomery–Vaughan I chapter we opened (Chapter 11) does not treat zero-density estimates.*

- **Checking it by hand.** A reader can check this proof by hand: each of its three steps is one inequality, and the note's arithmetic for them was redone independently by the second writer.

## Not read, not understood

- **Bodies not read:** `final_bound_of_assembly`, `numeric_constants`, `duality_inequality`, `coefficient_square_bound`, `pair_twist_bound`, and `mollifier_identity` past its helpers' statements.
- **Read only in step structure:** `zero_detection` and `blockCountOf_statement`. Their arithmetic was not checked line by line.
- **Where the box height Q in note 10 comes from:** `PairGood.boxes` uses `height M ε Y j`. How `stage` passes from that height to this statement's Q is in `StagePow.lean`, which note 10 read only for its calls.

### Clarification, 2026-11-22 (later the same day): from the box height to Q, and why Q^(1/4) is enough

The last "Not read" bullet above asked how `stage` passes from the box height of note 10 to this note's Q. It is now read (`Development/AutomorphicArithmetic/MeanSquareBounds/StagePow.lean`):

- **The height.** `stage` works with the primes q in `PPset m₀ a₀ U` (√U < q ≤ U) and characters ξ of conductor at most F, where F ≤ U^(1/2) (line 44). The zero box it asks about has height Q = F·U.
- **The primes with a zero in the box.** `count_bad` bounds them (lines 142-150): their number is at most Cb·(F·U)^(1/4) ≤ Cb·U^(3/8). For large U, `hpow` (line 74) gives Cb·U^(3/8) ≤ (η/2)·U^(9/10). `hcount` (line 78) gives U^(9/10) ≤ |PPset m₀ a₀ U|. So these primes are at most a share η/2 of the prime set.
- **Where the size of the prime set comes from.** `hcount` is `count_a` (line 56): the call that uses the Siegel-derived bound only at ε = 1, as note 10's Clarification found.
- **The primes where a sum is large.** For each ξ, `bad_share` (line 55, applied at lines 155-158) bounds them by a share η/(2(R + 1)). A union bound over the at most R characters ξ (lines 159-169) gives at most η/2 more.

*Interpretation, ours:* this is why a bound as weak as Q^(1/4) is enough here. The bad primes number at most about U^(3/8), and the prime set has at least U^(9/10) members, so 3/8 is below 9/10 with room.

## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released, computed by me.

| File | SHA-256 |
|---|---|
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountSt.lean` (read through) | `8c5e4fd7618d0c52d762af0151b75ca0f37a9b97507525a3c68ffdedd2431186` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountZAll.lean` (read through) | `682e0fc4791a75d11dc4e35aed0a6008fc599db38825f50d2332ef11e1e8a5a3` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountZDefs.lean` (read through) | `830e04d639855a0b79081b10161a0ebafd2a257f726c1b30e0fd76eee2e966d1` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountZDetect.lean` (step structure of zero_detection) | `e59ff678e421c71682fc577679f29a048aa33aa884d1ee23711288b30c53f5ee` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountZBlock.lean` (step structure of blockCountOf_statement) | `baf647cd5d587edb1b36df0facd9e81b194a81d1ffe4d6866ecdaaf068b078bc` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountZPair.lean` (pair_sum_bound read; helpers by statement) | `2bc182b7c27e6d8f7110240a86b2836b7f40b60a1619fb986fdb4f2d258ccb6c` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountZDual.lean` (statement) | `a3d1bcc8c28fc58f3813347bd00d8b43531d6717265e0dc1098b80ab42c7d452` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountZMoll.lean` (statements) | `0d23e54a14a89d975d14785c76d310b01e8e1070327a604fed1498b14b01af37` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountZTwist.lean` (statement) | `864285aee213020348c4af19c96242de92ffa09cd708a959f7b58ba2f7d5ac71` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountZFinal.lean` (statement) | `d1b3e107efc6f023b5c32445364d9289934e0618c26a1656fc350f61530207fc` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountZNum.lean` (statement) | `ca4a4ad56d04bafb69a9f97bd21da6b706eee322c1d250c25ce262a8ff4cfaa9` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/CountBadCore.lean` (read through) | `6fd10096d015d9c2d6fbd8c3eb10a9f0d1cb3e4b6118b9d60c2040b570b1cde8` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/StagePow.lean` (lines named in the Clarification) | `0664861db51e1c2c2ada99121d6988d15f47c2ecab5a6b3bc62b127c32ae75d1` |
