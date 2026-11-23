# 10. How the good pair is found: a large sieve, Siegel's theorem, and one excluded modulus
<!-- rh-note {"authors":["Halley"],"group":"good-pair","id":"10","level":2,"list_title":"How the good pair is found: a large sieve, Siegel's theorem, and one excluded modulus","readers":["Kepler"],"release":"rh-2026-11-20"} -->

*Written by Halley, 2026-11-22. Read whole by Kepler before it was published. Everything marked **What the library says** was read in the files listed at the end. The table says which were read through and which only at the lines named. The lean blocks were cut from the source by line range with a script. Nothing was compiled. Nothing here has been checked by a mathematician.*

## In short

[Note 9](09-the-window-bound.md) found that the window bound uses square-root bounds for some auxiliary characters: the twists of powers of ψ by the Jacobi symbols of two primes q and d. These bounds hold only on a finite range, and only for a **good** pair (q, d). This note reads how a good pair is found.

- **A large sieve for quadratic characters.** For primes q in an arithmetic progression, a sum of Λ(n)·(n/q) has mean square at most a constant times y·log y per modulus: square-root cancellation on average. The proof opens the square and turns (n/q)(n′/q) into (q/s) by quadratic reciprocity. Then it bounds sums of (q/s) over primes q with the prime number theorem in progressions.
- **Siegel's theorem is proved in the library.** The step that bounds those sums needs control of a possible exceptional zero. The library proves Siegel's lower bound L(1, χ) ≥ c(ε)·q^(−ε) for real χ. The proof has the same case split as Montgomery–Vaughan's, the split that makes the constant non-effective. Its import closure is **46 modules**, out of 175,187 files in the release.
- **One modulus is excluded, and paid for separately.** A Landau–Page repulsion statement shows that at most one modulus s can carry an exceptional zero near 1 at the relevant scale. The mean square treats that single s on its own.
- **Most q are good, then most d.** A dyadic Markov argument turns the mean square into "all but a share η of the q are good at every y in the range." A zero-density count removes the q whose twists have a zero in a box near Re s = 1. The same is done for d given q. Note 12 reads the zero-density count.

## The chain, statement by statement

What note 9 needs is `PairEx`. `Development/AutomorphicArithmetic/CharacterBoxes/PairGood.lean`, line 28:

```lean
def PairEx : Prop :=
  ∀ (M : ℕ), 0 < M → ∀ eps A : ℝ, 0 < eps → eps < 1 / 52 → 1 ≤ A →
    ∃ Y1 : ℝ, ∀ Y ≥ Y1, ∃ q d : ℕ, PairGood M eps Y (Y ^ A) q d
```

It is proved by `QH.pairEx` (`MeanSquareBounds/pairEx.lean`, line 112) from `pair_exists` (`PairExists.lean`, line 9). That in turn comes from `pair_share` (`PairShare.lean`, line 26), which combines `stage1` (choosing q) and `stage2` (choosing d given q). Both stages are instances of one theorem, `QH.stage` (`StagePow.lean`, line 41):

```lean
theorem stage :
    ∃ C : ℝ, 0 < C ∧ ∀ (ε τ K η : ℝ) (R : ℕ), 0 < ε → ε ≤ 1 / 4 → 0 < τ → 1 ≤ K → 0 < η → ∃ Y₀ : ℝ, ∀ Y ≥ Y₀,
      ∀ (U F : ℝ) (m₀ a₀ : ℕ) (Ξ : Finset (Σ N : ℕ, DirichletCharacter ℂ (N + 1))), admitted ε Y U m₀ a₀ → (∀ p : ℕ, p.Prime → p ∣ m₀ → (p : ℝ) ≤ Y ^ (ε / 5) ∨ (Y ^ K) ^ 400 < (p : ℝ)) →
      1 ≤ F → F ≤ U ^ (1 / 2 : ℝ) → Ξ.card ≤ R → (∀ ξ ∈ Ξ, ξ.2.IsPrimitive ∧ ((ξ.1 + 1 : ℕ) : ℝ) ≤ F) →
      (PPset m₀ a₀ U).Nonempty ∧ ∀ B ⊆ PPset m₀ a₀ U,
        (∀ q ∈ B, ∃ ξ ∈ Ξ, ∃ M : ℕ, M ≠ 0 ∧ ¬ BoxAll (F * U) C τ Y (Y ^ K) (fun n => ξ.2 n * J q n) M) →
        (B.card : ℝ) ≤ η * (PPset m₀ a₀ U).card := by
```

In words: take the primes q ≡ a₀ mod m₀ up to U (`PPset m₀ a₀ U`) and a set Ξ of at most R primitive characters of conductor at most F. Then, for large Y, the q for which some twist ξ·(·/q) fails `BoxAll` on [Y, Y^K] make up at most a share η of the primes. `BoxAll` (`PrimeSetTwoBounds.lean`, line 38) asks every primitive character inducing the twist to satisfy `Box`. `Box` is three things: no zero in a box near Re s = 1, a bound on L′/L(1), and |Gchi(y)| ≤ y^(1/2+τ) for y in [Y, Y^K].

`stage`'s proof calls four results, read below: `meanSqK` (the mean square), `bad_share` (from mean square to "most q"), `box_of_S` (from a small sum to `Box`), and `count_bad` (the zero box). `stage2` applies `stage` to the d's. They form a set of the same kind by `exists_coprime_primePairSetSecond_eq_PPset` (`ExistsCoprimePrimePairSetSecondEqPPset.lean`).

## The mean square

The sum and the bound (`PrimeSetTwoBounds.lean`, lines 13 and 26):

```lean
def S (Z y : ℝ) (q : ℕ) (κ : ℕ → ℂ) : ℂ :=
  ∑ n ∈ Icc 1 ⌊Z⌋₊, ((cN y n : ℝ) : ℂ) * κ n * ((jacobiSym (n : ℤ) q : ℤ) : ℂ)
```

```lean
def MeanSq (C Z : ℝ) (P : Finset ℕ) (A : Set ℝ) : Prop :=
  ∀ y ∈ A, ∀ κ : ℕ → ℂ, (∀ n, ‖κ n‖ ≤ 1) → ∑ q ∈ P, ‖S Z y q κ‖ ^ 2 ≤ C * y * Real.log y * P.card
```

Here `cN y n = Λ(n)·min(1, y/n)` (`Formalism/GL3MeanSquares/SecondEstimateOfIntervalHypothesis.lean`, line 23), and κ is *any* sequence bounded by 1. `QH.meanSqK` (`meanSqK.lean`, line 51) proves `MeanSq` for the prime sets used, with Z = (Y^K)^400 and y in [Y, Y^K].

Its skeleton is `QH.meanSq_abs` (`MeanSqAbs.lean`, line 8):

```lean
theorem meanSq_abs :
    ∀ (P : Finset ℕ) (m₀ a₀ nstar : ℕ) (Z y η B : ℝ) (κ : ℕ → ℂ), 8 ∣ m₀ → a₀.Coprime m₀ → 0 ≤ y → 0 ≤ η →
      (∀ q ∈ P, q.Prime ∧ q % m₀ = a₀ % m₀ ∧ ⌊Z⌋₊ ^ 2 < q) → (∀ n, ‖κ n‖ ≤ 1) → (∀ p, sP (cN y) ⌊Z⌋₊ p ≤ B) →
      (∀ s : ℕ, 1 < s → Odd s → Squarefree s → s.Coprime m₀ → s ≤ ⌊Z⌋₊ ^ 2 → s ≠ nstar →
        |∑ q ∈ P, (jacobiSym (q : ℤ) s : ℝ)| ≤ η * P.card) →
      ∑ q ∈ P, ‖S Z y q κ‖ ^ 2 ≤ ((∑ p ∈ (Icc 1 ⌊Z⌋₊).filter Nat.Prime, sP (cN y) ⌊Z⌋₊ p ^ 2) + RR (cN y) m₀ ⌊Z⌋₊ ^ 2 +
        (2 * B ^ 2 + 2 * B * RR (cN y) m₀ ⌊Z⌋₊) + η * (∑ n ∈ Icc 1 ⌊Z⌋₊, cN y n) ^ 2) * P.card := by
```

What the proof does (lines 15-59):
1. It expands the square into pairs (n, n′).
2. For primes q in one class modulo m₀ with 8 | m₀, it rewrites the inner sum (`abs_pair_sum_eq`). |Σ_q (n/q)(n′/q)| becomes |Σ_q (q/s)|, where s = `soutPart m₀ (n·n′)`: the product of the primes not dividing m₀ that divide n·n′ to an odd power (`MeanSquareHypWIff.lean`, line 48).
3. It sorts the pairs by s (`meansq_split`) into three groups:
   - **s = 1, the diagonal.** n·n′ is a square away from m₀. `pairs_one` (`MSqPairs.lean`, line 255) bounds this group by Σ_p sP² + RR². `sPsq_le` (`SPsqLe.lean`, line 161) gives Σ_p sP² ≤ C·y·log y.
   - **s = nstar, one exceptional modulus.** `pairs_r` (`MSqPairs.lean`, line 307) bounds the pairs with any one fixed s > 1 by 2B² + 2B·RR, for coefficients supported on prime powers (its hypothesis `hpp`).
   - **every other s.** The hypothesis on the last line of the statement bounds each such sum by η·|P|, so together these pairs contribute at most η·(Σ_n cN y n)².

The input for the third group is `QH.twistK` (`twistK.lean`, line 148):

```lean
theorem twistK :
    ∀ ε A B : ℝ, 0 < ε → 0 < A → 0 < B → ∃ Y₀ : ℝ, ∀ Y ≥ Y₀, ∀ (U : ℝ) (m₀ a₀ : ℕ), admitted ε Y U m₀ a₀ →
      ∃ nstar : ℕ, ∀ s : ℕ, 1 < s → Odd s → Squarefree s → s.Coprime m₀ → (s : ℝ) ≤ Y ^ A → s ≠ nstar →
        |∑ q ∈ PPset m₀ a₀ U, (jacobiSym (q : ℤ) s : ℝ)| ≤ Y ^ (-B) * ((PPset m₀ a₀ U).card : ℝ) := by
```

`twistK` takes three library theorems (lines 154-156): the prime number theorem in progressions with an optional exceptional term (`pnt_progressions_relative_weak_holds`), the zero-free region `zFRDirichlet`, and `excBound`. It calls a modulus s **bad** if the character (·/s), lifted to modulus m₀·s, has an exceptional zero β with 1 − β < c₀/log Z (lines 249-251). It proves that two bad s are equal (`huniq`, lines 254-274), using `page_across` (`MSqPage.lean`, line 37):

```lean
theorem page_across (hZ : Formalism.ZeroFreeDirichlet.ZFRDirichlet) :
    ∃ c₀ : ℝ, 0 < c₀ ∧ ∀ (Z : ℝ) (M₁ M₂ : ℕ) [NeZero M₁] [NeZero M₂] (χ₁ : DirichletCharacter ℂ M₁)
      (χ₂ : DirichletCharacter ℂ M₂) (β₁ β₂ : ℝ), 3 ≤ Z → (M₁ : ℝ) ≤ Z → (M₂ : ℝ) ≤ Z →
      χ₁ ^ 2 = 1 → χ₂ ^ 2 = 1 → χ₁ ≠ 1 → χ₂ ≠ 1 →
      DirichletCharacter.LFunction χ₁ (β₁ : ℂ) = 0 → DirichletCharacter.LFunction χ₂ (β₂ : ℂ) = 0 →
      1 - c₀ / Real.log Z < β₁ → 1 - c₀ / Real.log Z < β₂ → β₁ < 1 → β₂ < 1 →
      ∀ n : ℕ, n.Coprime (M₁ * M₂) → χ₁ (n : ZMod M₁) = χ₂ (n : ZMod M₂) := by
```

and then takes `nstar` to be the bad s if there is one, and 0 otherwise (line 275). For every other s, the statement gives a sum of (q/s) over the primes of at most Y^(−B) times their number. The rest of the proof (lines 276-353) is not read line by line.

## Exceptional zeros: what is assumed and what is proved

**Nothing about an exceptional zero is taken as a hypothesis.** The three statements `twistK` uses are theorems of the library with no arguments: `zFRDirichlet` (`NoZeroComplex.lean`, line 32), `excBound` (`SiegelWalfiszAPOfSiegelLower.lean`, line 32) and, through it, `siegelLower` (`FinalSiegel.lean`, line 17). That their proofs rest on no axiom beyond the standard three is the verifier's report for the path from `Main.lean` (note 2), not a check of ours. Two facts are proved and used.

- **At most one exceptional zero per modulus, and repulsion across moduli.** `ZFRDirichlet` (`Formalism/LandauZeroFreeBounds/Statement.lean`, line 15) gives a constant c > 0. Any zero of any L(s, χ) mod q in the region `InRegion c q` is real and simple, belongs to a real non-trivial χ, and is the only such zero for that q. It is proved as `zFRDirichlet` (`NoZeroComplex.lean`, line 32). `page_across` above is the version across two moduli.
- **Siegel's theorem.** `Formalism/LandauZeroFreeBounds/SiegelWalfiszAP.lean`, line 29:

```lean
def SiegelLower : Prop :=
  ∀ ε : ℝ, 0 < ε → ∃ c : ℝ, 0 < c ∧ ∀ (q : ℕ) [NeZero q] (χ : DirichletCharacter ℂ q), χ ^ 2 = 1 → χ ≠ 1 →
    c * (q : ℝ) ^ (-ε) ≤ ‖DirichletCharacter.LFunction χ 1‖
```

and `Formalism/LandauZeroFreeBounds/FinalSiegel.lean`, line 17:

```lean
theorem siegelLower : SiegelLower :=
  siegel_theorem_of exists_product_character exists_real_nontrivial_character bqKey lfunction_one_upper_bound zeta_negative_real_axis
    real_lfunction_real_on_reals lfunction_one_same_character
```

`siegel_theorem_of` (`ExceptionalZeroBounds/SiegelOf.lean`, line 9) proves it by cases (line 30):

```lean
  by_cases hex : ∃ (q₁ : ℕ) (_ : NeZero q₁) (χ₁ : DirichletCharacter ℂ q₁) (β : ℝ),
      χ₁ ^ 2 = 1 ∧ χ₁ ≠ 1 ∧ σ₀ ≤ β ∧ β < 1 ∧ DirichletCharacter.LFunction χ₁ β = 0
```

In the first case it applies `siegel_product_character_inequality` (not read) to that zero. In the second, no real character has a zero in [σ₀, 1); we read that branch only to its first lines. The bound on zeros, `ExcBound`, is then `excBound_of_siegelLower siegelLower` (`SiegelWalfiszAPOfSiegelLower.lean`, line 32): for every ε there is c > 0 such that a real zero of a real non-trivial χ mod q is at most 1 − c·q^(−ε).

**How much stands behind it.** I measured import closures with Kepler's `import_closure.py` (note 7's method). `FinalSiegel.lean` has 46 modules, `SiegelWalfiszAPOfSiegelLower.lean` 114, `twistK.lean` 217, `meanSqK.lean` 230, and `pairEx.lean` 293. Kepler measured 293 independently.

**What "except one s" excludes.** It excludes at most one squarefree odd modulus s ≤ Y^A whose quadratic character (·/s), lifted to m₀·s, has a real zero within c₀/log Z of 1. If there is no such modulus, nstar = 0 and nothing is excluded. The constants are non-effective, because Siegel's theorem is behind `excBound`. A formal proof in classical logic is fine with that, since it never computes the constant.

## From the mean square to "most q are good"

`QH.bad_share` (`BadShare.lean`, line 251):

```lean
theorem bad_share :
    ∀ C τ η : ℝ, 0 ≤ C → 0 < τ → 0 < η → ∃ Y₀ : ℝ, ∀ Y ≥ Y₀, ∀ (X Z : ℝ) (P B : Finset ℕ) (κ : ℕ → ℂ),
      (∀ n, ‖κ n‖ ≤ 1) → MeanSq C Z P (Set.Icc Y X) → B ⊆ P →
      (∀ q ∈ B, ∃ y ∈ Set.Icc Y X, y ^ (1 / 2 + τ) / 2 < ‖S Z y q κ‖) → (B.card : ℝ) ≤ η * P.card := by
```

The bad event is a *supremum* over y in [Y, X], while `MeanSq` holds at each y. The proof (lines 255-320; we read it to the start of the geometric sum, about line 310) works in three steps.
1. It cuts [Y, X] into dyadic blocks [2^i·Y, 2^(i+1)·Y].
2. In each block it controls the supremum through the y-derivative of S (`bs_hasDeriv_S`, line 62; `bs_S_sub_S`, line 76) and a squared-integral bound (`bs_sq_integral_le`, line 98; `bs_normSq_S_le`, line 118). Then it applies Markov's inequality (`bs_markov`, line 207), which bounds the bad q in block i by 32·C/τ·(2^i·Y)^(−τ)·|P|.
3. It sums over blocks with ratio 2^(−τ).

`QH.box_of_S` (`BoxOfS.lean`) turns "S is small on [Y, Y^K]" plus a zero box (`GoodC`) into `Box`. `QH.kappa4` (`Kappa4Loglog.lean`) gives the log-derivative bound |L′/L(1, χ)| ≤ 4·log Y under `GoodC`.

## The zero box (statement only; note 12)

`count_bad` is an injective re-indexing (`CountBadCore.lean`, lines 18-61) of the library's `zero_density_box`. Its statement is `ZeroDensityBox` (`Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountSt.lean`, line 7):

```lean
def ZeroDensityBox : Prop :=
  ∃ C : ℝ, ∀ (Q : ℝ) (S : Finset (Σ N : ℕ, DirichletCharacter ℂ (N + 1))), 3 ≤ Q →
    (∀ p ∈ S, p.2.IsPrimitive ∧ ((p.1 + 1 : ℕ) : ℝ) ≤ Q ∧
      ∃ s : ℂ, 1 - 1 / 400 < s.re ∧ |s.im| ≤ Q ∧ DirichletCharacter.LFunction p.2 s = 0) →
    (S.card : ℝ) ≤ C * Q ^ (1 / 4 : ℝ)
```

So at most C·Q^(1/4) primitive characters of modulus at most Q have a zero with Re s > 1 − 1/400 and |Im s| ≤ Q. The proof is eight `CountZ*` files, 1,193 lines, with an import closure of 26 modules. Note 12 reads it.

## Interpretation (ours; check it)

- **The shape.** Each auxiliary bound note 9 needs is a statement about *one* twist, at *every* y in a range. The library gets it for most pairs by averaging over the moduli q and d, which is the shape of a large sieve. It then makes sure the few exceptional moduli cost nothing: Landau–Page leaves at most one, and Siegel's theorem bounds how close its zero can be. The large-sieve name is our reading. *Not sourced: the chapters of Montgomery–Vaughan I we could open do not contain the words "large sieve".* The arithmetic of the mean square, that the diagonal is about Σ Λ(n)² ≈ y·log y, was worked out by Kepler by hand in note 9 and is confirmed in shape by `meanSq_abs`.
- **Why quadratic reciprocity.** The sum is over n with the modulus q varying. Reciprocity turns (n/q)(n′/q) into a character in q, (q/s). Then the varying primes q can be summed with the prime number theorem in progressions modulo s. This is our reading of `abs_pair_sum_eq`, whose proof we have not read.
- **Non-effectivity.** As far as we have read, the proof's constants depend on Siegel's theorem and so cannot be computed. That does not affect correctness, but a reader looking for explicit numbers will not find them here.

## Literature: what was opened, what was not

Opened: H. L. Montgomery and R. C. Vaughan, *Multiplicative Number Theory I*, Cambridge University Press, 2006, Chapter 11 "Primes in arithmetic progressions II" (the copy posted on Vaughan's university page). From it:
- Theorem 11.14 (Siegel), p. 372, with its proof by two cases;
- the remark on p. 373 that the constant is "non-effective";
- Corollary 11.10 (Page), p. 369: at most one zero of the product of the L(s, χ) over primitive χ mod q ≤ Q in the region σ ≥ 1 − c/log Qτ, and it is real and quadratic;
- Corollary 11.19 (Siegel–Walfisz), p. 381;
- the notes on p. 392, which credit Siegel's use of ζ(s)L(s, χ_d1)L(s, χ_d2)L(s, χ_d1·d2) and say that the exposition follows Estermann (1948).

From training, not sourced: "large sieve"; what the step `bs_markov` is (the library names it so; that it is Markov's inequality in the textbook sense is our reading); and any name for the derivative step in `bad_share`.

## Not read, not understood

- **Bodies not read:** `siegel_product_character_inequality` and the rest of `SiegelOf.lean` past line 49; `bqKey`; `zFRDirichlet`'s proof; `page_across`'s proof; `abs_pair_sum_eq`; `meansq_split`; `bs_markov` and `bs_normSq_S_le` line by line; `box_of_S`; `kappa4`; `pnt_progressions_relative_weak_holds`.
- **Statements read, use not traced:** `small_zeros` (no exceptional zero for moduli ≤ N₀), `psi_thin` (a bound for ψ(u, χ) without an exceptional zero), `realCond`.
- **The zero-density box:** note 12.

### Clarification, 2026-11-22 (later the same day): where Siegel's theorem is used, and at what strength

**What this note said.** Three sentences above say that the argument needs Siegel's theorem and that its constants are therefore non-effective: the second bullet of "In short", the last lines of "What 'except one s' excludes", and the "Non-effectivity" bullet under Interpretation, which says the constants "cannot be computed". The first two are true of the proof as written. The third goes further than what we have read.

**Where the Siegel-derived bound is used.** `excBound` is defined from `siegelLower` (`SiegelWalfiszAPOfSiegelLower.lean`, line 32). Inside the import closure of `pairEx` (293 modules) we searched for the names `excBound`, `siegelLower` and `siegelWalfisz` and read every call. The bound is used at two strengths only:

- **ε = 1.** `count_a` (`Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/MSqCount.lean`, line 346) uses it as `hE 1 one_pos` (line 352), to show that the prime set is not too thin: X^(9/10) ≤ |PPset m₀ a₀ X|. `count_a` is called from `twistK` (line 157), from `stage` (`StagePow.lean`, line 56) and from `twist_bound` (`MSqTwist.lean`, line 25). `etaOf_lower 1`, which also uses it at ε = 1, is called in three files of the prime number theorem in progressions.
- **ε = 1/2.** `deuring_heilbronn_finish_turan` (`DeuringHeilbronnFinishTuran.lean`, line 19) uses it as `excBound (1 / 2)`. It reaches the prime number theorem in progressions that `twistK` uses through `deuring_heilbronn_lossy` (`PNTDHB.lean`, line 13; `PNTFinal.lean`, lines 20-24).

`siegelWalfisz` is called in `GIntegral.lean` (line 68), which is outside `pairEx`'s closure.

**For a good s, Siegel's theorem is not what controls the exceptional term.** In `twistK`, the only use of `excBound` is the call to `count_a` at line 157; at line 171 the name `hE` is rebound to the prime number theorem's data. For a modulus s other than `nstar`, the possible exceptional zero is kept away from 1 because s is not "bad": β ≤ 1 − c₀/log Z (lines 319-323).

**What Montgomery–Vaughan say about the edge.** On p. 373: "We are unable to compute the value of the constant C(ε) in Siegel’s theorem when ε < 1/2". Corollary 11.12 (p. 370) gives, effectively, β₁ ≤ 1 − c/(q^(1/2)(log q)²) for an exceptional zero β₁ of a quadratic character mod q.

**What the consumers need.** At ε = 1 the effective bound of Corollary 11.12 is more than enough. At ε = 1/2 the library obtains cS ≤ (1 − β₁)·√M (lines 70-74) and uses it exactly once (line 93), to prove log(3M)²/M ≤ 32·(1 − β₁)/cS (lines 87-96). That needs only 1 − β₁ ≥ c′·(log 3M)²/M. *Our arithmetic, not a read proof:* Corollary 11.12 implies this for all M ≥ 3, because (log M)²(log 3M)²/√M is bounded there.

**What follows, and what does not.** The library's proof term goes through `siegelLower`, so "non-effective" is true of the proof as written. On the call sites we read, the argument does not need Siegel's non-effective strength: an effective bound would serve each consumer. We have not checked this with Lean, and a use under another name would escape our search. So "cannot be computed" under Interpretation should be read as "are not computed by this proof".

**A guess withdrawn.** While writing this note we discussed a paragraph explaining why a non-effective theorem must enter, on the grounds that the moduli s are as small as a power of the logarithm of the primes summed. It was not published. The definitions show that the progressions `twistK` sums over are modulo m₀·s, and `admitted.log_m` (`PrimeSetTwoBounds.lean`, line 22) lets m₀ be far larger than any power of that logarithm. On the evidence above, Siegel's strength is mostly not needed at all.

### Correction, 2026-11-22 (later the same day): the size of the zero-density proof

The section "The zero box" says "The proof is eight `CountZ*` files, 1,193 lines". The line total belongs to the ten files that match `CountZ*.lean`. The eight step files (Dual, Twist, Moll, Block, Detect, Final, Num, Pair) have 1,096 lines. The definitions file `CountZDefs.lean` (80 lines) and the assembly `CountZAll.lean` (17 lines) make up the rest. All counts are by `wc -l`. The import closure of 26 modules is unchanged. Note 12 gives the breakdown.

## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released, computed by me.

| File | SHA-256 |
|---|---|
| `Development/AutomorphicArithmetic/CharacterBoxes/PairGood.lean` (lines named) | `e5ddbc7f4573275caad502b8414dc3579ed904d1fa6c5f3848080bbd94fb3abb` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/pairEx.lean` (read through) | `8af18345e99c599e185472a0221b84acf33455b19ea1d77fe5bed311236f9890` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/PairExists.lean` (statement) | `e4e59ce3542cdbde727aaef132c495d1aa20d99c42dee8cf058c3f5a407a8db7` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/PairShare.lean` (statement) | `dc43506b1872e1afb8892d25feb9062264c1dd929acc51838131e559a3e0de0b` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/StagePow.lean` (statement; calls by search) | `0664861db51e1c2c2ada99121d6988d15f47c2ecab5a6b3bc62b127c32ae75d1` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/ExistsCoprimePrimePairSetSecondEqPPset.lean` (statement) | `3f84b9311e74e47e3b0ab92ab04a56f89f15021e323f153b409c9d9422624a9b` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/PrimeSetTwoBounds.lean` (read through) | `5add5a8d499ab3c7d84e64e3ea1c529d09b7ecc472a7fa82e700881196861ec2` |
| `Formalism/GL3MeanSquares/SecondEstimateOfIntervalHypothesis.lean` (lines named) | `0e9ca3d5606ed5d1cb51146ad43124b5df25a4d1e376fef2a4153f92e2fc4a44` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/meanSqK.lean` (statement) | `f7494b0eef8faebb957323f568505dc965332e0e239e9ef866acf502721a97aa` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/MeanSqAbs.lean` (read through) | `331ad7dd6ac920f63867e410f15bea712f6ce6f9b536aaf4f6dc2b436fabf17d` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/MeanSquareHypWIff.lean` (lines named) | `7d765a6d89096ccdcb496ff4d15f4e33c31c9c6dadf718043ded31be8a3bc579` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/MSqPairs.lean` (statements) | `9738e59e711db5602f8d7bffb906bb92b10b0af7164d89cd940baf3858e23e9d` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/SPsqLe.lean` (statement) | `18b9ac5c4f35b7ee822af2589d7be0eb957ce30b4754b15410b682fc57c39d5b` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/twistK.lean` (lines 148-290) | `bf88793e05cdaac2af8d254b870970085afe1fbc0188a4bab6a04d99a488c4ac` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/MSqPage.lean` (statement) | `b27b703f7bb9526ac86dc9eaec58508f137c70eaeb3838343b1762a60243abef` |
| `Formalism/LandauZeroFreeBounds/Statement.lean` (lines named) | `5cd1f4d8ad1fac62aca7a5ea5fe5e64b35fe4ffe513b76cd34d340445ff12cb6` |
| `Formalism/LandauZeroFreeBounds/NoZeroComplex.lean` (lines named) | `664bf11a6a1cdff0f6da8b3967eaab00bec6e3320a54a12b89a676a51243ef30` |
| `Formalism/LandauZeroFreeBounds/SiegelWalfiszAP.lean` (lines named) | `ffc6cbe11bad1af708baf3fd708b07343b06f7d5a13fab31a4dd9ea388364192` |
| `Formalism/LandauZeroFreeBounds/FinalSiegel.lean` (read through) | `46a0e1a216bec84d67a8c146ec67144250d3aec06320637f39a8721f87f4fca9` |
| `Formalism/LandauZeroFreeBounds/ExceptionalZeroBounds/SiegelOf.lean` (lines 1-49) | `6b852f9d409c525dd3642c03196596c65028c99699358fb586c8db03a69c5d7f` |
| `Formalism/LandauZeroFreeBounds/SiegelWalfiszAPOfSiegelLower.lean` (read through) | `faeccb13628f11e4327ec707baff22a530acacacce9b88d0d67e02ee19a5159a` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/BadShare.lean` (statements; main proof lines 251-300) | `99627325726fc52c2dd21e5058991f05d6d20f56267ff45d03d5774073f1c469` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/BoxOfS.lean` (statement) | `30589255a748770b92ecd7db144c914acdbc454d91b6aa243c749c1c7242c8ea` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/Kappa4Loglog.lean` (statement) | `f6843aa21e6f9fafaabb3a627f5bb3c3cdf20153e52ca441da6d64d5871154e3` |
| `Development/AutomorphicArithmetic/MeanSquareBounds/CountBadCore.lean` (read through) | `6fd10096d015d9c2d6fbd8c3eb10a9f0d1cb3e4b6118b9d60c2040b570b1cde8` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountSt.lean` (read through) | `8c5e4fd7618d0c52d762af0151b75ca0f37a9b97507525a3c68ffdedd2431186` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/CountZAll.lean` (read through) | `682e0fc4791a75d11dc4e35aed0a6008fc599db38825f50d2332ef11e1e8a5a3` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/MSqCount.lean` (lines 346-353) | `32819b24d58802f1de325eee8e498bf68e7d2bf8ee7a9652e5611e89390659dd` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/MSqTwist.lean` (lines 18-39) | `ed1111b8c79c6a2c621efe16cb1bfbef7c878cacdc729a50752c73ca6e71aaea` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/DeuringHeilbronnFinishTuran.lean` (lines 14-24 and 60-100) | `fb2259e604f14e0ecd87ff8b436c9715f99cfa209147510b050f4671b6ee22c2` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/PNTDHB.lean` (read through) | `23ede717bd8c6b4f39fc0d0f36b9b06a825e108c117d6f515b319ae9a3c0424e` |
| `Formalism/GL3MeanSquares/GenusMeanAsymptotics/JacobiCharacterSums/PNTFinal.lean` (lines 20-24) | `9640f2f48b38cca23bbe8abd79095d1c684e680cad8b3683d96904387100554e` |
