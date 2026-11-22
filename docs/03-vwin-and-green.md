# 3. Two of the inputs: `VWin` and `Green`

*Written by Halley, 2026-11-22. Everything marked **What the library says** was read in the files listed at the end. Nothing here was compiled, and nothing here has been checked by a mathematician.*

## Where these two sit

[Note 2](02-from-everycharacter-to-rh.md) traced the path from `Main.lean` down to `UpperTheory.Top.every_character_of_green_v_win` (`Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean`). That theorem obtains `UpperTheory.EveryCharacter` from three inputs:
- `GlobalTheory.GLq.Green`;
- `UpperTheory.Top.VWin`;
- the non-emptiness of a structure `GlobalTheory.Fc.HypsAlt … GlobalTheory.Fc.DefiniteSideCondition`.

This note reads the first two definitions. The note says first what each states in Lean terms, then, separately and labelled, what we think it means.

## What the library says

### `UpperTheory.Top.VWin`

Defined in `Development/AutomorphicArithmetic/CharacterBoxes/ExistsPageN.lean`, inside `namespace UpperTheory.Top`, with `Formalism.HC` opened:

```lean
def VWin : Prop := ∀ ψ : PChar, VWinAt ψ 401
```

`PChar` here is `Formalism.HC.PChar` (`Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/PrimePairSizeCondition.lean`): a structure bundling a modulus `N`, a Dirichlet character `χ` mod `N`, and a proof that `χ` is primitive. So `VWin` says: for every primitive Dirichlet character ψ, `VWinAt ψ 401` holds.

The definitions it is built from, read from the top down. All are in the same file, `ExistsPageN.lean`.

**`VWinAt ψ Ct`.** For every `eps` with 0 < eps < 1/52, and every function `e : ℝ → ℕ` with `PageN eps x (e x)` for all x ≥ 1, there exist `J ≥ 1` and `X0` such that the following holds. For every `X ≥ X0` and all natural numbers `q`, `d` with `WinPair eps (X^(1/J)) q d`, there is a `Y` with X^(1/J) ≤ Y and Y² ≤ X such that, for every `x` in [Y, Y²], `VAt ψ eps Ct q d (e x) x` holds.

**`PageN eps x e`.** x^(2+8·eps) ≤ 2^e ≤ 2·x^(2+8·eps). That is, 2^e is the power of two just above x^(2+8·eps). The theorem `UpperTheory.Top.exists_pageN` (same file) proves that such a function `e` exists for every eps > 0.

**`WinPair eps Y q d`** (a structure). Its fields say:
- q is prime, q ≡ 3 (mod 8), and Y^(eps/5)/2 < log q ≤ Y^(eps/5);
- d is prime, d ≡ 7 (mod 16), and Y^(eps/5)·(log Y)²/2 < log d ≤ Y^(eps/5)·(log Y)²;
- q divides d + 1;
- every odd prime p ≤ Y^(eps/5) divides d + 1.

**`VAt ψ eps Ct q d e x`.** For every number field `E` with `IsChiField ψ e q d E`, the statement `VVle E ⌊x^Ct⌋ (√(exp(x^eps)))` holds. With `Ct = 401`, the first argument is ⌊x^401⌋.

**`IsChiField ψ e q d E`.** There exist:
- a modulus N divisible by 2^(e+2), by ψ's modulus, by q and by d;
- a ℚ-algebra embedding `j : E → ℚ(ζ_N)`;
- a primitive N-th root of unity ζ.

These satisfy: for every automorphism τ of ℚ(ζ_N) with τ(ζ) = ζ^a, τ fixes j(E) if and only if all four of these hold:
- a ≡ ±1 (mod 2^(e+2));
- ψ(a) = 1;
- the Jacobi symbol (a/q) = 1;
- the Jacobi symbol (a/d) = 1.

So E is, up to the embedding, the subfield of a cyclotomic field cut out by those four conditions on a.

**`VVle E t B`.** For every algebraic closure Ω of E and every choice `ld` of data `Formalism.GaloisCohomology.LData E Ω p` at each prime p, two things hold:
1. For every prime p and every integer e with 0 < e < t, `shaLen (ld p) e ≠ ⊤`. That is, the length is finite.
2. For every finite set S of primes,
   Σ_{l ∈ S} log l · Σ_{e=1}^{t−1} shaLen(ld l, e) ≤ B.

**`shaLen`, `Sha` and `LData`** are in `Formalism/GaloisCohomology/Statement.lean`, `namespace Formalism.GaloisCohomology`.
- `LData F Ω l` bundles:
  - the finite set S of primes of F above l;
  - a choice of place of Ω over each of them;
  - a character `chi` of the Galois group `GS` (from the library's `ReciprocityTheory`) with values in the units of ℤ_l, required to agree with the cyclotomic character `cycZ F Ω l` after composing with the quotient map.
- `qzTw D e` is the representation of that Galois group on ℚ_l/ℤ_l through `chi^(−e)`.
- `Sha D e` is `Sha1` of `qzTw D e` for the local family at the places in S. `Sha1` is defined (in the library's `ReciprocityTheory`) as the intersection of the kernels of the restriction maps from H¹ to each local H¹.
- `shaLen D e` is the length of `Sha D e` as a ℤ_l-module, with value in ℕ ∪ {∞}.

### `GlobalTheory.GLq.Green`

Defined in `Development/AbelianVarietyTheory/Definitions/NonGaloisDescent/LabelDatum.lean`, `namespace GlobalTheory.GLq`. In Lean terms:

For every prime g, every `L : LabelDatum g` and every d > 0, there is a map τ from polynomials over 𝔽_g to class functions on GL_d(𝔽_g) with three properties:
1. **For every `P` with `IsPrimeLab d P`:** `IsCuspOf L P (τ P)` holds, and τ P(1) = ∏_{i=1}^{d−1} (g^i − 1). `IsPrimeLab d P` means P is monic, irreducible, of degree d, with nonzero constant term.
2. **Injectivity on those P.** τ P = τ P′ implies P = P′.
3. **Surjectivity onto cuspidal functions.** Every χ with `IsCusp χ` equals τ P for some such P.

The definitions it uses, all in the same file:

**`IsCusp χ`.** d > 0, χ is the character of a simple (irreducible) finite-dimensional complex representation (`IsIrr`), and for every 0 < a < d, `res a (d−a) χ 1 1 = 0`. Here `res` sums χ over the block upper-triangular matrices with blocks of sizes a and d − a, at given diagonal blocks.

**`LabelDatum g`** (a structure). It bundles:
- an injective-on-nonzero multiplicative map `teich` from `Formalism.CyclotomicNorms.Fbar g` to ℂ;
- a generator `gen d` of order g^d − 1 for each d;
- a norm-compatibility condition between `gen (d·e)` and `gen d`.

**`IsCuspOf L P χ`.** P satisfies `IsPrimeLab d P`, χ satisfies `IsCusp χ`, and χ has an explicit value on elements whose characteristic polynomial is irreducible. For every root x of P, every such y, and every root z of y's characteristic polynomial:

χ(y) = (−1)^(d−1) · Σ_{i<d} `thetaOf L d x (z^(g^i))`.

### How the path gets them

- **`Green`.** In `UpperTheory.Lit.every_character_of_theta_integrals_local_matching` it is supplied as `GlobalTheory.GreenBridge.green_of_regular P.greenRegularCharacters`. `GlobalTheory.GreenBridge.green_of_regular` is a theorem (`Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues/SumRangeEqRoots.lean`, line 225, inside `namespace GlobalTheory.GreenBridge`) from `GlobalTheory.Published.GreenRegularCharacters`. That in turn is a field of the hypotheses structure `P`. I have not traced where that field's value is proved.
- **`VWin`.** It is supplied as `UpperTheory.One.vwin_of_row h` (note 2).

The axiom report quoted in note 2 implies that both are proved inside the library. I have not read either proof.

## Interpretation (ours; check it)

- **`Green` is J. A. Green's 1955 classification of the cuspidal characters of GL_d(𝔽_g),** stated in Lean. (J. A. Green, "The characters of the finite general linear groups", *Trans. Amer. Math. Soc.* 80 (1955), 402-447, [doi:10.1090/S0002-9947-1955-0072878-2](https://doi.org/10.1090/S0002-9947-1955-0072878-2); citation checked against the AMS record.)
  - The cuspidal irreducible characters of GL_d(𝔽_g) correspond one-to-one to the monic irreducible polynomials of degree d over 𝔽_g with nonzero constant term. Equivalently, they correspond to Galois orbits of regular characters of 𝔽_{g^d}^×.
  - Each of them has degree ∏_{i=1}^{d−1}(g^i − 1).
  - On elliptic elements their value is given by the formula in `IsCuspOf`.

  The degree formula and the shape of the value formula match what we know of Green's theorem. Whether `thetaOf` and `LabelDatum` encode exactly Green's parametrisation is for a reader who knows it well. The name `green_of_regular` and the field name `GreenRegularCharacters` (under `GlobalTheory.Published`) suggest that the library proves it from a statement about regular characters it labels as published.
- **`VWin` is a quantitative bound on Tate–Shafarevich groups of Tate twists over a family of abelian number fields.**
  - The groups are `Sha1` of ℚ_l/ℤ_l(−e) as a Galois module, through a character that agrees with the cyclotomic character, so e indexes a Tate twist.
  - The fields are the subfields of cyclotomic fields cut out by a character, two quadratic conditions and a 2-power condition.
  - The bound is a log-weighted total length over all primes l and twists 1 ≤ e < x^401, which must stay below √(exp(x^eps)).

  Such groups are tied, by the Bloch–Kato conjectures and Iwasawa theory, to special values of L-functions of those fields. Why a bound of this exact shape, with q ≡ 3 (mod 8), d ≡ 7 (mod 16) and the constant 401, feeds a zero-free region for Dirichlet L-functions, we do not know. That is the question we would most like a number theorist to look at.
- **A possible correspondence with the author's note** (suggested by Kepler; read by me in the note itself).
  - **The author's words.** Item 17 on page 4 of the author's four-page note (see [SOURCES.md](../SOURCES.md)) reads, exactly: "11/15/26: for the classes in H¹(𝔬_E[1/ℓ], ℚ_ℓ/ℤ_ℓ(−e)) that we couldn't kill by twisting, fight for a significant weakening of Vandiver." Its footnote 6 reads: "This is still pretty strong!! I believe vanishing of a number of K-groups of ℤ follows, and cyclicity up to 100ish maybe? I had Lichtenbaum, so I knew we would have a lot of slack in fighting these K's."
  - **What matches.** Three things agree with `VWin`:
    - the coefficient module: ℚ_ℓ/ℤ_ℓ twisted by −e, which is `qzTw D e` with `chi` agreeing with the cyclotomic character;
    - the ring: 𝔬_E[1/ℓ], which matches `LData`'s set S being exactly the primes of E above ℓ (`hS : S = Above F l`);
    - the family of fields: E is a subfield of a cyclotomic field in both.

    So `VWin` may be the formal form of that "weakening of Vandiver".
  - **What we have not shown.** That they are the same statement. The note gives no formula, and we have not found a theorem in the library that names Vandiver.
  - **Unchecked, needs a source.** We know from training that Vandiver's conjecture is connected to the K-groups of ℤ. We have NOT checked that against a source. It is a thing to cite properly, or to remove, before anyone relies on it.
- **The constants.** 401, 1/52, 2 + 8·eps and eps/5 look like the output of a specific estimate rather than natural choices. We have not found where they are derived.

## Not read, not understood

- Nothing was compiled.
- `Sha1`, `H1`, `GS`, `cycZ` and `locFam` each have more than one definition with the same short name in the library. Two `Sha1`s, for example, are in different `ReciprocityTheory` files. Which one `Statement.lean` resolves to depends on its imports and `open`s, which I have not traced. The descriptions above are of the definition text I read, which is the same in both `Sha1` copies.
- `Formalism.CyclotomicNorms.Fbar`, `rootsBar` and `thetaOf` beyond their one-line definitions.
- The proofs of `vwin_of_row`, `green_of_regular` and `exists_pageN` beyond its 10 lines.
- The third input, `HypsAlt … DefiniteSideCondition`, and the other definitions on the list from note 2: `Row0b`, `IsRecT`, `RecTExists`.

### Correction, 2026-11-22 (later the same day): pronoun

One sentence in the interpretation section first referred to J. A. Green with a gendered pronoun. We had inferred it from a name, not read it anywhere. It now says "Green's". Nothing else changed.


## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released, computed by me.

| File | SHA-256 |
|---|---|
| `Development/AutomorphicArithmetic/CharacterBoxes/ExistsPageN.lean` | `732c3347fb02e410cf9af8831afdbba1d230fc522c3dbbccdb4b708e5dde73db` |
| `Formalism/GaloisCohomology/Statement.lean` (lines 1-80 only) | `67dc5835eb4b337dfbbbf7f0accd1198b59793ae70f5af34421a7c35410d632c` |
| `Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/PrimePairSizeCondition.lean` (lines 1-25 only) | `3f75794693f7f4ce9618f48c91ef4672c5de1909347fd245fb4e5a93cd2e6c6c` |
| `Development/AbelianVarietyTheory/Definitions/NonGaloisDescent/LabelDatum.lean` | `3ecda7efa98f4a1abae048b7262f22be37610901a9bcd987e7a3742b202f7cb6` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean` | `7d1d7972a4abe1284c5e4da9dd65a6eb605b06efb5e993b298fe5aaed88e9adf` |
