# 8. The Landau step, read in the library's proof: a one-sided bound on windows forbids zeros
<!-- rh-note {"authors":["Halley"],"edition":2,"edition_date":"2026-11-25","group":"landau-step","id":"08","level":2,"list_title":"The Landau step, read in the library's proof: a one-sided bound on windows forbids zeros","readers":[],"release":"rh-2026-11-20"} -->

*Written by Halley, 2026-11-22. Everything marked **What the library says** was read in the files listed at the end; all 31 were opened and their proofs read, with two long routine computations skimmed, as the table says. Nothing was compiled. Nothing here has been checked by a mathematician.*

## The idea, in one line

For the k-th Taylor coefficient a_k of the Laplace transform of g, at any height γ,

> **|a_k(σ + iγ)| + Re a_k(σ) ≤ 2 ∫ max(g(u), 0) · u^k e^(−σu) / k! du.**

So an *upper* bound on g alone, needed only where the kernel u^k e^(−σu)/k! has its mass, controls the size of the Taylor coefficients at every height. A zero with real part above θ would make those coefficients grow too fast. *(This line is our summary of `Deduction.landau_window_ineq`, with the window integral and tail bound written out below. The inequality |g| + g ≤ 2·max(g, 0) is its line 86.)*

## Where this sits

[Note 6](06-where-the-zeros-enter.md) showed that the zero-free region comes from two facts about the function `Level.Gm`, a weighted sum of smoothed prime sums twisted by characters:
- (A) a bound Gm(x) ≤ x^(1/2 + O(ε)) on windows;
- (B) the "Landau step" `FormB`: such a bound on windows [Y, Y^la], for arbitrarily large Y, forbids zeros to the right of the exponent.

This note reads the proof of (B). It is self-contained: by Kepler's measurement of import closures (note 7), the theorem that does it, `Deduction.zeroFree_of_rpow_window`, depends on 30 library files out of 175,187.

## What the library says

### The objects

`Development/AutomorphicArithmetic/DedekindLFunctions/CharFamily.lean`:

- `Deduction.ramp f y = Σ_{n ≤ y} Λ(n)·f(n)·max(y/n − 1, 0)`, with Λ Mathlib's von Mangoldt function (line 10).
- `Deduction.Gchi χ y` (line 15):
  - for χ = 1 it is `ramp 1 y − y log y + (1 + γ) y`;
  - otherwise it is `ramp χ y + y·L′(1, χ)/L(1, χ)`.
- `Deduction.CharFamily` (line 24): a finite family of Dirichlet characters χᵢ with weights aᵢ > 0. Each χᵢ is either the character modulo 1 or non-trivial (field `adm`).
- `Deduction.Gm F y = Σᵢ aᵢ · Re Gchi(χᵢ, y)` (line 36), and `Deduction.ZeroFree F θ`: no L(χᵢ, s) vanishes for Re s > θ (line 38).

**How this `Gm` relates to note 6's `Level.Gm`, the open item from note 6.** `UpperTheory.Comparison₂.level_family` (`Development/AutomorphicArithmetic/PrimitiveCosets/LevelFamily.lean`, line 41) proves: for every level Λ there is a `CharFamily` F with `Deduction.Gm F y = Λ.Gm y` for all y, and `ZeroFree F θ ↔ Λ.ZeroFreeAbove θ`. The family is the level's kept characters, with weight 1 for the trivial character and `Λ.wt ψ` for the others (lines 9-10, 44). So the two `Gm` are the same function, and `formB` (note 6) is this note's theorem applied to that family.

### The theorem

`Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/ZeroFreeOfRpowWindow.lean`, line 11:

```lean
theorem zeroFree_of_rpow_window (F : CharFamily) {θ δ C : ℝ} (hθ : 0 < θ) (hθ1 : θ < 1) (hδ : 0 < δ)
    (h : ∀ Y₀ : ℝ, ∃ Y : ℝ, Y₀ ≤ Y ∧ ∀ y ∈ Set.Icc Y (Y ^ (1 + δ)), Gm F y ≤ C * y ^ θ) :
    ZeroFree F θ :=
  lemmaL F hθ hθ1 hδ (windowHyp_of_rpow F hδ h)
```

**In words:** let 0 < θ < 1 and δ > 0. If, for arbitrarily large Y, Gm(y) ≤ C·y^θ for every y in [Y, Y^(1+δ)], then no L-function of the family vanishes for Re s > θ.

### The proof, in nine steps

Throughout, u = log y, and g(u) = Gm(e^u) (`Deduction.gm`, `LandauZeroFreeCriterion.lean`, line 9).

**Step 1. The window hypothesis, in integral form.** `windowHyp_of_rpow` (`WindowHypOfRpow.lean`, line 27) turns "Gm ≤ C y^θ on the window" into `WindowHyp`:
- for every η > 0 and arbitrarily large Y there is R ≥ 0 with Gm ≤ R on [Y, Y^(1+δ)];
- and ∫_window R(y) y^(−θ−1) dy ≤ Y^η.

`windowHypU_of_windowHyp` (`WindowHypUOfWindowHyp.lean`, line 29) restates this in the variable u, on windows [U, (1+δ)U] (`WindowHypU`, `LandauZeroFreeCriterion.lean`, line 25).

**Step 2. The transform.** For Re s > 2 let Φ(s) = ∫₀^∞ g(u) e^(−su) du. By the change of variables y = e^u (`poleData_change`, `poleData.lean`, line 114), this is a Mellin transform of `Gchi`. The library computes it for each character:
- **for χ ≠ 1** (`mellin_Gchi_of_ne_one`, `mellinGchiOfNeOne.lean`, line 116):
  ∫₁^∞ Gχ(y) y^(−s−1) dy = −(L′/L(s) − s·L′/L(1)) / (s(s−1));
- **for χ = 1** (`mellin_Gchi_modOne`, `mellinGchiModOne.lean`, line 115):
  ∫₁^∞ Gχ(y) y^(−s−1) dy = −(ζ′/ζ(s) + 1/(s−1) + 1 − (1+γ)s) / (s(s−1)).

Both Mellin theorems are stated for Re s > 1 (hypothesis `hs : 1 < s.re`); Re s > 2 is the half-plane in which `PoleData` states the Laplace form. The extra terms in `Gchi` (the y·L′/L(1) term, and −y log y + (1+γ)y for ζ) are what make these transforms regular at s = 1. The one-term identity behind both is `mellin_ramp` (`MellinRamp.lean`, line 10): ∫₁^∞ (y/n − 1)₊ y^(−s−1) dy = n^(−s)/(s(s−1)). With Mathlib's Σ Λ(n)χ(n)n^(−s) = −L′/L(s), it gives the formulas.

**Step 3. Poles at zeros, with a sign.** `poleData_abstract` (`poleData.lean`, line 22) shows the transform continues to Re s > 0 and is analytic away from zeros. At a zero ρ of multiplicity m it has a simple pole with residue m·(−1/(ρ(ρ−1))) (lines 27-28).

`poleData` (line 248) assembles the family's Φ as Σᵢ (aᵢ/2)·(Φ_χᵢ + Φ_χ̄ᵢ), pairing each character's transform with that of its inverse, so that Φ is the transform of the real function g. It proves that Φ satisfies `PoleData` (`LandauZeroFreeCriterion.lean`, line 15). In particular, at a pole on the real axis the residue c has Re c > 0 (field `pole`, line 22).

The library proves the sign itself (`poleData.lean`, lines 346-383). At a zero ρ the family's residue is S·(−1/(ρ(ρ−1))), with S = Σᵢ (aᵢ/2)(m₁ᵢ + m₂ᵢ) > 0, the weighted multiplicities of ρ for χᵢ and for χᵢ⁻¹. For a real zero 0 < ρ < 1, ρ(ρ − 1) < 0, so the residue is positive (`hneg`, line 382). The upper bound ρ < 1 comes from the separate fact that nothing vanishes on Re s ≥ 1.

**Step 4. Taylor coefficients are moments.** `landau_coeff` (`LandauCoeff.lean`): for Re s > 2,

a_k(s) := (−1)^k Φ^(k)(s)/k! = ∫₀^∞ g(u) u^k e^(−su)/k! du.

**Step 5. The key inequality.** `landau_window_ineq` (`landauWindowIneq.lean`, line 27). Suppose g ≤ R ≥ 0 on a window [U, V]. Then for every k and γ,

|a_k(σ + iγ)| ≤ 2 (σ−θ)^(−k) ∫_[U,V] R(u) e^(−θu) du − Re a_k(σ) + 2C₀ ∫_(outside [U,V]) u^k e^((2−σ)u)/k! du.

It uses three bounds:
- |a_k(σ+iγ)| ≤ ∫|g|·w and Re a_k(σ) = ∫g·w, where w(u) = u^k e^(−σu)/k!;
- |g| + g ≤ 2R on the window (line 86);
- w(u) ≤ (σ−θ)^(−k) e^(−θu), from `landau_kernel_max` (`LandauKernelMax.lean`): u^k e^(−au)/k! ≤ a^(−k), which is e^(au) ≥ (au)^k/k!.

Outside the window it uses the growth bound |g(u)| ≤ C₀ e^(2u) (`PoleData.growth`).

**Step 6. Choosing σ and k.** `landau_tails` (`landauTails.lean`, line 80): for δ > 0 there is σ > 2 and a constant C such that, for every U ≥ 1, some k ≥ U makes the kernel's mass off [U, (1+δ)U] at most C/σ^k. The proof is a Chernoff-type bound, `landau_tails_chernoff`, line 18. The choice is k = ⌈(1 + δ/2)·σ·U⌉ (line 98), and σ is large, depending on δ (lines 83-89). *Our reading:* the kernel u^k e^(−(σ−2)u) peaks at u = k/(σ−2), about (1 + δ/2)·U when σ is large, which is the middle of the window.

Putting Steps 1, 5 and 6 together gives `landau_window_key` (`landauWindow.lean`, line 40): there are σ > 2 and C such that, for every η > 0 and arbitrarily large U, some k ≥ U gives, for every γ,

**|a_k(σ + iγ)| + Re a_k(σ) ≤ C·e^(ηU) / (σ − θ)^k.**

**Step 7. The two cases.** Suppose some zero ρ₀ has Re ρ₀ > θ. All poles have Re ρ ≤ 2 < σ (`landau_pole_re_le`, `LandauPoleReLe.lean`) and are isolated (`landau_finite`, `LandauFinite.lean`). `landau_dichotomy` (`LandauDichotomy.lean`, line 24) splits into two cases:
- **(i) A real pole closest to σ.** There is a real β > θ that is the only pole in some disc around σ of radius r ≤ σ − θ (with σ − β < r).
- **(ii) Otherwise.** There is a pole-free disc around σ of radius D ≤ σ − θ, but some pole lies closer than D to the line Re s = σ. `landau_nearest` (`LandauNearest.lean`, line 36) then picks a height γ at which σ + iγ has a *unique* nearest pole ρ, at distance d < D. It does so by avoiding the finitely many heights at which two nearby poles are equidistant from σ + iγ (the set `B`, line 53).

The proof of the dichotomy is a fact about circles. Take the pole nearest to σ, at distance d. If no pole is closer than d to the line Re s = σ, then any pole at distance exactly d with real part at least σ − d must be the real point σ − d (`eq_ofReal_sub_of_dist_le_of_le_sub_re`, line 10). That is how the argument is led to a real zero, where Step 3's sign applies.

**Step 8. The contradiction.**
- **Case (i).** Near β, Φ(s) = c/(s−β) + analytic, so its Taylor coefficients at σ are c/(σ−β)^(k+1) up to an error O(1/r′^k) for some r′ with σ − β < r′ < r (`landau_pole_asym`, `LandauPoleAsym.lean`, line 19). Since Re c > 0 (Step 3), Re a_k(σ) grows like (σ−β)^(−k), while |a_k(σ)| ≥ 0. That beats C·e^(ηU)/(σ−θ)^k, because σ − β < σ − θ and η can be taken small with k ≥ U.
- **Case (ii).** At σ + iγ the same expansion makes |a_k(σ+iγ)| grow like d^(−k). Meanwhile Re a_k(σ) ≥ −M/r′^k by Cauchy's estimate on the pole-free disc around σ (`landau_cauchy`, `LandauCauchy.lean`, line 9), with d < r′ < D ≤ σ − θ. Again the left side outgrows the right.
- In both cases, `landau_growth_contra` (`LandauGrowthContra.lean`) does the final arithmetic: c/d^k eventually beats C·e^(ηU)/e^k when d < e, η is small and k ≥ U. `landau_window_contra` (`landauWindow.lean`, line 20) wraps it. Conclusion: every pole, hence every zero with Re > 0, has Re ≤ θ (`landau_window`, line 83).

**Step 9. The edge.** `lemmaL` (`lemmaL.lean`, line 13) combines Step 8 with the separate fact that no L(χᵢ, s) vanishes for Re s ≥ 1 (`charFamily_LFunction_ne_zero_of_one_le_re`). That gives `ZeroFree F θ`.

## Which classical theorem this is

We opened one source: H. L. Montgomery and R. C. Vaughan, *Multiplicative Number Theory I*, Cambridge University Press, 2006 (publication date from the DOI record, [10.1017/CBO9780511618314](https://doi.org/10.1017/CBO9780511618314)), Chapter 15 "Oscillations of error terms", §15.1 "Applications of Landau's theorem", pages 463-464. We read the copy of the chapter posted on Vaughan's university page; the chapter's own DOI is 10.1017/CBO9780511618314.017. Two results there are the classical form of this note's theorem.
- **Lemma 15.1** (an analogue of Landau's theorem on Dirichlet series with non-negative coefficients, their Theorem 1.7, which we did not open). If A(x) ≥ 0 for all large x, and σ_c is the abscissa of convergence of ∫₁^∞ A(x)x^(−σ)dx, then F(s) = ∫₁^∞ A(x)x^(−s)dx is analytic for σ > σ_c but not at s = σ_c.
- **Theorems 15.2 and 15.3.** A one-sided bound on ψ(x) − x *for all large x* forces every zeta zero to the left of its exponent. Theorem 15.3's proof uses the positivity device 1 + cos(φ − γ log x) ≥ 0. It compares F(s) with ½e^(iφ)F(s+iγ) + ½e^(−iφ)F(s−iγ) as s tends to the critical exponent along the real axis.

**Where the library's version differs** (our reading of the two texts side by side):
1. **Windows instead of a tail.** The classical hypothesis holds for all large x. The library needs it only on windows [Y, Y^(1+δ)] for arbitrarily large Y. It can afford this because it never takes a limit s → θ⁺. It works at a fixed σ > 2 and lets the order k of the Taylor coefficient grow, and the kernel u^k e^(−σu)/k! then concentrates its mass where the window is (Step 6).
2. **The same positivity device, at the level of Taylor coefficients.** |a_k(σ+iγ)| + Re a_k(σ) equals the supremum over φ of ∫ g·(1 + cos(φ − γu))·w(u) du, where u = log x. This is Montgomery–Vaughan's 1 + cos(φ − γ log x), applied to each Taylor coefficient instead of to F near its abscissa. *This identification is ours; the library does not name it.*
3. **A family with weights, and the Riesz mean.** The library's function is not ψ(x) − x. It is a positively weighted sum over a family of characters of the smoothed sums Σ Λ(n)χ(n)(y/n − 1), minus main terms. Pairing each character with its inverse keeps it real. Which weights make the overall argument work is decided elsewhere (note 6, and Kepler's note 7 layer).

We did not find the windowed form, or this Taylor-coefficient proof, stated in the source we opened. We do not know whether it is in the literature. That is a question for a reader who knows the oscillation-theorem literature.

## Interpretation (ours; check it)

- **Why this step is "classical" and still worth reading.** The conclusion is Landau's (1905, cited in Montgomery–Vaughan's references). What is new, or at least not in the textbook form we opened, is that the hypothesis is needed only on sparse windows. Everything else in the library exists to supply bounds of exactly that shape (note 6's (A)). So the windowed Landau step is the interface between the analytic and the arithmetic halves of the proof.
- **Why the smoothing (y/n − 1) matters: the sign of a residue** (suggested by Kepler; I checked the signs). With the unsmoothed sum ψ_χ(y) = Σ_{n≤y} Λ(n)χ(n), the Mellin transform is ∫₁^∞ ψ_χ(y) y^(−s−1) dy = −(L′/L)(s)/s. At a real zero 0 < β < 1 of multiplicity m its residue is −m/β, which is *negative*. With the library's weight (y/n − 1) the transform is −(L′/L)(s)/(s(s−1)), and the residue is −m/(β(β−1)), which is *positive* (Step 3).
  - Step 8 case (i) needs the positive sign. An *upper* bound g ≤ R controls |a_k(σ)| + Re a_k(σ), and a real pole with positive residue makes Re a_k(σ) grow without bound.
  - With a negative residue, Re a_k(σ) would go to −∞ while |a_k(σ)| grows by about the same amount, so in their sum the pole's contribution would cancel, leaving only the error term (of size M/r′^k, Step 8). An upper bound would then say nothing about a real zero. One would need a lower bound instead.
  - So, on this reading, the first Riesz mean is what lets a one-sided *upper* bound exclude real zeros as well as complex ones.
- **The headline inequality is a single line of real analysis.** |g| + g = 2 max(g, 0). The rest is bookkeeping: Laplace transforms, residues, Cauchy estimates and a Chernoff tail. A number theorist can read Steps 1-9 in about the time it takes to read Montgomery–Vaughan §15.1. *That is a judgement, not a measurement.*

## Not read, not understood

- **Skimmed rather than read step by step:** the proofs in `mellinGchiModOne.lean` (the ζ case of Step 2, lines 10-203) and the ζ branch of `poleData_char` (lines 145-229). Both are long routine computations; their statements were read exactly.
- Montgomery–Vaughan's Theorem 1.7 and its proof, which Lemma 15.1 adapts. We opened only Chapter 15.
- Landau's 1905 paper itself (*Math. Ann.* 61, 527-550), cited from Montgomery–Vaughan's reference list, not opened.
- Why the half-plane is Re s > 2 and not Re s > 1. This is now settled, and is not a gap: the library uses the crude bound Λ(n) ≤ n, so |ramp(y)| ≤ 2y² (`Gchi_growth_ramp`, `GchiGrowth.lean`, line 9). That makes the Laplace integral converge absolutely only for Re s > 2. Nothing in the argument needs a sharper half-plane, because σ is taken large anyway.

### Correction, 2026-11-23: the heading said "proved"

Until 2026-11-23 this note's heading read "The Landau step, proved". A reader can take that as "we proved it", or as "a computer has checked the proof". Neither is what this note supports. What it supports is the line under the heading: we read the library's proof in the 31 files listed below, with two long computations skimmed, and nothing was compiled. The heading now says "read in the library's proof". The body is unchanged. Ariadne found the problem while reading the note titles as a lay visitor would.

### Added 2026-11-24: the argument in one paragraph, and two corrections

In short: an upper bound on $E_F$, the weighted error term of a family of Dirichlet characters, needed only on windows that start arbitrarily far out, bounds the Taylor coefficients of its Laplace transform at every height, and a zero to the right of $\theta$ would make those coefficients grow too fast. The library's proof of this step is one line: a lemma turns the bound $E_F(y) \le C y^\theta$ on windows $[Y, Y^{1+\delta}]$, for arbitrarily large $Y$, into an integral form of the hypothesis (which the closing lemma restates in the variable $u = \log y$), and the closing lemma finishes. The closing lemma takes the family's transform from the continuation lemma, which continues it to $\mathrm{Re}\ s > 0$ with a pole at each zero and at the conjugate of each zero, of positive residue at a real zero between 0 and 1 (Step 3), and applies the window lemma: every pole has real part at most $\theta$. A zero with $\mathrm{Re}\ s \ge 1$ is excluded separately, by a lemma of its own. The window lemma works at a fixed $\sigma > 2$ with $a_k$, the $k$-th Taylor coefficient of the transform up to the sign $(-1)^k$, which is the moment $\int_0^\infty g(u)\  u^k e^{-su}/k!\  du$ of $g(u) = E_F(e^u)$ (Step 4). Because $|g| + g = 2\max(g, 0)$, an upper bound on $g$ over a window bounds $|a_k(\sigma + i\gamma)| + \mathrm{Re}\ a_k(\sigma)$ at every height $\gamma$ (Step 5), and with $k = \lceil (1 + \delta/2)\sigma U \rceil$ the integral of $u^k e^{(2-\sigma)u}/k!$ outside the window $[U, (1+\delta)U]$, where $U = \log Y$, which is what the growth bound $|g(u)| \le C_0 e^{2u}$ leaves to control there, is at most $C/\sigma^k$ (Step 6). A pole with real part above $\theta$ would make these coefficients grow like $d^{-k}$, where $d < \sigma - \theta$ is the distance from the point of evaluation ($\sigma$, or $\sigma + i\gamma$) to the nearest pole, which is faster than the bound, $C e^{\eta U}/(\sigma - \theta)^k$ with $\eta > 0$ as small as we like, allows: through the positive residue if the pole nearest to $\sigma$ is real and no pole lies to its right, and otherwise at a height where one pole is the unique nearest (Steps 7 and 8). We read these proofs on 2026-11-22, in the files the note lists, with two long computations skimmed, as the list of what we did not read says.
<!-- rh-block {"date":"2026-11-22","decls":[{"module":"Development.AutomorphicArithmetic.DedekindLFunctions.LandauTheorems.ZeroFreeOfRpowWindow","name":"Deduction.zeroFree_of_rpow_window"}],"file":"Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/ZeroFreeOfRpowWindow.lean","id":"08.b01","kind":"argument","lines":[11,14],"reader":"Halley"} -->

Two corrections to the section "Which classical theorem this is", from opening the book again on 2026-11-24:
- **A page.** That section gives pages 463-464 for Lemma 15.1 and Theorems 15.2 and 15.3. Lemma 15.1 is on page 463 and Theorem 15.2 on page 464, but Theorem 15.3 is on page 466.
- **Theorem 1.7 is now opened.** It is on page 16, in Chapter 1 ("Dirichlet series: I") of the same posted copy. We read its statement: a Dirichlet series with non-negative coefficients and a finite abscissa of convergence $\sigma_c$ has a singularity at the point $\sigma_c$. So the section's "which we did not open", and the line about it under "Not read, not understood", no longer hold for the statement. We did not read its proof.

### Added 2026-11-24: the proof in order, a sketch (Halley)

Notation: $E_F$ is a weighted sum, over a finite family of Dirichlet characters with positive weights, of the real parts of the smoothed sums $\sum_{n \le y} \Lambda(n)\chi(n)(y/n - 1)$ with their main terms removed; $u = \log y$ and $g(u) = E_F(e^u)$. Hypothesis: $0 < \theta < 1$, $\delta > 0$, and for every $Y_0$ some $Y \ge Y_0$ with $E_F(y) \le C y^\theta$ for all $y$ in $[Y, Y^{1+\delta}]$. Conclusion: no $L$-function of the family vanishes for $\mathrm{Re}\ s > \theta$.

1. **Integral form of the hypothesis.** The bound becomes: for every $\eta > 0$ and arbitrarily large $Y$ there is $R \ge 0$ with $E_F \le R$ on $[Y, Y^{1+\delta}]$ and $\int R(y)\  y^{-\theta-1}\  dy \le Y^\eta$ over that window. In $u$, the windows are $[U, (1+\delta)U]$ with $U = \log Y$.
2. **The transform.** For $\mathrm{Re}\ s > 2$ let $\Phi(s) = \int_0^\infty g(u) e^{-su}\  du$. For each character this is a Mellin transform computed in closed form: $-(L'/L(s) - s\  L'/L(1))/(s(s-1))$ for $\chi \ne 1$ and $-(\zeta'/\zeta(s) + 1/(s-1) + 1 - (1+\gamma)s)/(s(s-1))$ for $\chi = 1$, both from the one-term identity $\int_1^\infty \max(y/n - 1, 0)\  y^{-s-1}\  dy = n^{-s}/(s(s-1))$. Because $E_F$ takes real parts, the family's $\Phi$ is $\sum_i (a_i/2)(\Phi_{\chi_i} + \Phi_{\bar\chi_i})$. We skimmed the proof of the $\chi = 1$ closed form; we did not read it line by line. Both closed forms were checked against the statement of the continuation lemma, not against the two computations themselves.
3. **Poles at zeros, with a sign.** $\Phi$ continues to $\mathrm{Re}\ s > 0$, analytic away from the zeros of the family's $L$-functions and their conjugates, with a simple pole at each. At a zero $\rho$ the residue is $S \cdot (-1/(\rho(\rho - 1)))$ with $S > 0$ the weighted multiplicity, so at a real zero $0 < \rho < 1$ the residue is positive ($\rho < 1$ because nothing vanishes on $\mathrm{Re}\ s \ge 1$). We skimmed the part of this proof that treats $\zeta$; we did not read it line by line.
4. **Taylor coefficients are moments.** With $a_k(s) = (-1)^k \Phi^{(k)}(s)/k!$, for $\mathrm{Re}\ s > 2$: $a_k(s) = \int_0^\infty g(u)\  u^k e^{-su}/k!\  du$.
5. **The key inequality.** If $g \le R$ with $R \ge 0$ on a window $[U, V]$, then for every $k$ and $\gamma$, $|a_k(\sigma + i\gamma)| + \mathrm{Re}\ a_k(\sigma)$ is at most $2(\sigma - \theta)^{-k}\int_U^V R(u) e^{-\theta u}\  du$ plus a tail term outside the window. This uses $|g| + g = 2\max(g, 0) \le 2R$ on the window, the kernel bound $u^k e^{-au}/k! \le a^{-k}$, and the growth bound $|g(u)| \le C_0 e^{2u}$ outside it.
6. **Choosing $\sigma$ and $k$.** For $\delta > 0$ there are $\sigma > 2$ and $C$ such that for every $U \ge 1$ the choice $k = \lceil (1 + \delta/2)\sigma U \rceil \ge U$ makes $\int u^k e^{(2-\sigma)u}/k!\  du$ over $u > 0$ outside $[U, (1+\delta)U]$ at most $C/\sigma^k$. With steps 1 and 5 this gives the key window bound: for every $\eta > 0$ and arbitrarily large $U$, some $k \ge U$ has $|a_k(\sigma + i\gamma)| + \mathrm{Re}\ a_k(\sigma) \le C e^{\eta U}/(\sigma - \theta)^k$ for every $\gamma$.
7. **Two cases.** Suppose some zero has real part above $\theta$. Poles have real part at most $2 < \sigma$ and are isolated. Either (i) a real pole $\beta > \theta$ lies alone in a disc around $\sigma$ of radius at most $\sigma - \theta$, or (ii) there is a pole-free disc of radius $D \le \sigma - \theta$ around $\sigma$ but some pole nearer than $D$ to the line $\mathrm{Re}\ s = \sigma$. In case (ii) there is a height $\gamma$ at which $\sigma + i\gamma$ has a unique nearest pole, at distance $d < D$.
8. **The contradiction.** In case (i), near $\beta$ the coefficients are $c/(\sigma - \beta)^{k+1}$ up to $O(r'^{-k})$ for some radius $r'$ with $\sigma - \beta < r' < r$, where $r$ is the radius of the disc in case (i), and $\mathrm{Re}\ c > 0$ by step 3, so $\mathrm{Re}\ a_k(\sigma)$ grows like $(\sigma - \beta)^{-k}$, which beats $C e^{\eta U}/(\sigma - \theta)^k$ for small $\eta$ and $k \ge U$. In case (ii), $|a_k(\sigma + i\gamma)|$ grows like $d^{-k}$ while Cauchy's estimate on the pole-free disc keeps $\mathrm{Re}\ a_k(\sigma) \ge -M/r'^k$ with $d < r' < D$. Either way the left side outgrows the bound, so every pole, and hence every zero with $\mathrm{Re}\ s > 0$, has real part at most $\theta$.
9. **The edge.** Separately, no $L(s, \chi_i)$ vanishes for $\mathrm{Re}\ s \ge 1$. Together with step 8 this gives the conclusion: the family is zero-free to the right of $\theta$.
<!-- rh-block {"basis":"source","date":"2026-11-22","decls":[{"module":"Development.AutomorphicArithmetic.DedekindLFunctions.LandauTheorems.ZeroFreeOfRpowWindow","name":"Deduction.zeroFree_of_rpow_window"},{"module":"Development.AutomorphicArithmetic.DedekindLFunctions.LandauTheorems.lemmaL","name":"Deduction.lemmaL"},{"module":"Development.AutomorphicArithmetic.DedekindLFunctions.LandauTheorems.landauWindow","name":"Deduction.landau_window"},{"module":"Development.AutomorphicArithmetic.DedekindLFunctions.LandauTheorems.landauTails","name":"Deduction.landau_tails"},{"module":"Development.AutomorphicArithmetic.DedekindLFunctions.LandauTheorems.poleData","name":"Deduction.poleData"},{"module":"Development.AutomorphicArithmetic.DedekindLFunctions.LandauTheorems.landauWindowIneq","name":"Deduction.landau_window_ineq"},{"module":"Development.AutomorphicArithmetic.DedekindLFunctions.LandauTheorems.LandauDichotomy","name":"Deduction.landau_dichotomy"},{"module":"Development.AutomorphicArithmetic.DedekindLFunctions.LandauTheorems.LandauNearest","name":"Deduction.landau_nearest"}],"file":"Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/ZeroFreeOfRpowWindow.lean","id":"08.b02","kind":"sketch","lines":[11,14],"reader":"Halley","second_readers":[{"date":"2026-11-24","reader":"Kepler"}],"span":2,"unexpanded":["Step 1: the exponent arithmetic turning $C y^\\theta$ into an integral bound below $Y^\\eta$, and the change of variable $y = e^u$.","Step 2: the one-term identity, and the summation over $n$ giving each closed form (the $\\chi = 1$ case we skimmed, as step 2 says).","Step 3: the continuation, the pole set and the residue formula. Also the conjugate symmetry, the local form of $L'/L$ at a zero, and measurability, which the continuation uses.","Step 4: differentiating the Laplace integral $k$ times under the integral sign, and the moment formula.","Step 5: the key inequality, the kernel bound $u^k e^{-au}/k! \\le a^{-k}$, and the growth bound $|g(u)| \\le C_0 e^{2u}$.","Step 6: the integral of the kernel, and the tail estimate outside the window.","Step 7: that poles have real part at most 2 and are isolated, the two cases, and the height with a unique nearest pole.","Step 8: the coefficient asymptotics near a pole, Cauchy's estimate, that $c/d^k$ eventually beats $C e^{\\eta U}/\\tau^k$ when $d \u003c \\tau$ (for a radius $\\tau$; $\\eta$ small and $k \\ge U$), and the assembly of steps 5 to 8.","Step 9: joining the edge fact."],"unexpanded_detail":["Counts are by whole-word text search for linarith, nlinarith, positivity, norm_num, field_simp, simp, simpa, ring, omega, gcongr, fun_prop, push_cast and exact_mod_cast, not by the compiler; they are a guide, not a measurement. Also searched and absent from these files: decide, aesop, norm_cast, abel, continuity, measurability, tauto, polyrith. Not counted: linear_combination (5), simp_rw (5) and ring_nf (1), which also occur. (simpa, push_cast and exact_mod_cast were added after Kepler's second read found simpa missing.)","`WindowHypOfRpow.lean`, step 1: the exponent arithmetic turning $C y^\\theta$ into an integral bound below $Y^\\eta$ (13 calls)","`WindowHypUOfWindowHyp.lean`, step 1: the change of variable $y = e^u$ (1 call)","`MellinRamp.lean`, step 2: the one-term identity $\\int_1^\\infty \\max(y/n - 1, 0) y^{-s-1} dy = n^{-s}/(s(s-1))$ (19 calls)","`mellinGchiOfNeOne.lean`, step 2: the closed form for $\\chi \\ne 1$, summing the one-term identity over $n$ (40 calls)","`mellinGchiModOne.lean`, step 2: the closed form for $\\chi = 1$ (63 calls; the file was skimmed, as step 2 says)","`poleData.lean`, step 3: the continuation, the pole set and the residue formula, outside the ζ branch (54 calls in the whole file, the skimmed ζ branch included: simp 13, ring 10, linarith 9, norm_num 5, exact_mod_cast 4, and others)","`GchiConj.lean`, `LFunctionConj.lean`, `LogDerivLocal.lean`, `measurableGchi.lean`, step 3: the conjugate symmetry, the local form of $L'/L$ at a zero, and measurability used by `poleData` (4, 7, 4, 4 calls); step assigned from who calls these files (text search: only `poleData.lean`), since note 08 lists them only in its file table","`IteratedDerivLaplace.lean`, step 4: differentiating the Laplace integral $k$ times under the integral sign (14 calls); step assigned from who calls the file (text search: only `LandauCoeff.lean`), since note 08 lists it only in its file table","`LandauCoeff.lean`, step 4: the moment formula for $a_k$ (3 calls)","`landauWindowIneq.lean`, step 5: the key inequality (27 calls: ring 10, simp 7, linarith 5, fun_prop 2, positivity 2, push_cast 1)","`LandauKernelMax.lean`, step 5: $u^k e^{-au}/k! \\le a^{-k}$ (2 calls)","`GchiGrowth.lean`, step 5: the growth bound $|g(u)| \\le C_0 e^{2u}$ (16 calls)","`kernelIntegral.lean`, step 6: the integral of the kernel $u^k e^{-au}/k!$ (4 calls); step assigned from who calls the file (text search: only `landauTails.lean`), since note 08 lists it only in its file table","`landauTails.lean`, step 6: the tail estimate outside the window (58 calls: linarith 20, ring 12, nlinarith 10, positivity 8, field_simp 3, gcongr 3, simp 2)","`LandauPoleReLe.lean` and `LandauFinite.lean`, step 7: poles have real part at most 2 and are isolated (7 and 3 calls)","`LandauDichotomy.lean`, step 7: the two cases (12 calls)","`LandauNearest.lean`, step 7: the height with a unique nearest pole (23 calls: linarith 17, simp 3, positivity 1, ring 1, push_cast 1)","`LandauPoleAsym.lean`, step 8: the coefficient asymptotics near a pole (12 calls)","`LandauCauchy.lean`, step 8: Cauchy's estimate on the pole-free disc (3 calls)","`LandauGrowthContra.lean`, step 8: $c/d^k$ eventually beats $C e^{\\eta U}/e^k$ (6 calls)","`landauWindow.lean`, steps 5 to 8: putting the pieces together (41 calls: linarith 26, positivity 6, simpa 3, simp 3, ring 2, exact_mod_cast 1)","`lemmaL.lean`, step 9: joining the edge fact (2 calls)","Closing entry: 2 files whose automation carries no step of this sketch, `LevelFamily.lean` (5 calls, the link to note 6's `Level.Gm`) and `LandauZeroFreeCriterion.lean` (1 call, definitions)"]} -->

## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released, computed by me.

| File | SHA-256 |
|---|---|
| `Development/AutomorphicArithmetic/DedekindLFunctions/CharFamily.lean` (read) | `ca0ca8acb80ff4ffc36896204650f9ca16167193a22c36a140402b27cfc8c336` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/CharFamilyLFunctionNeZeroOfOneLeRe.lean` (read) | `bd25dd6f7b19d2683b3cb937b3cca4edfe798a492e3dcedeade371f0e3ff48b3` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/GchiConj.lean` (read) | `88a3897329c8a53bd97aaa46b1235bbf3e1d1a8a4b5281f44cc7399c20a4c37e` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/GchiGrowth.lean` (read) | `3943c2eba98d5ed2a2e521f4a1986281a8e031f9319e2acc3160de6d521db02e` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/IteratedDerivLaplace.lean` (read) | `3beee9b6dbdb25ae9e3c6fecb83e21cfee34c01e2065b5c5c383ce725f85189b` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/LFunctionConj.lean` (read) | `913ec01ca1654d6ba1281693c8f52ee63a1437f0fcac4c139d9db6f7eb0e1862` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/LandauCauchy.lean` (read) | `fdd3d3cdebfe075a825bd3249713b362daef806e79e4a10341cdc1104a023b39` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/LandauCoeff.lean` (read) | `e8bd6a4a51c2299ccdd213fd7b99a67c7a2968b14cd8752cf15ab3aa14874543` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/LandauDichotomy.lean` (read) | `f358ff8aecbe34019afe20224ae9a5890c99d55f6b6f7d838c1277e3b1d255ad` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/LandauFinite.lean` (read) | `1c24afcda94b779f176b3e46a2cad08e32414bd41aeee9d890e187391479129a` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/LandauGrowthContra.lean` (read) | `2f3e6d7a5d2e7b1cf2b0b92c82f50b2ebb661ab8fb519092795fcade18f88df5` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/LandauKernelMax.lean` (read) | `9fe6836f5bbab547e0b1d154ad4133a0b0d6aaf9ba8cde93b6310a49d5dd5259` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/LandauNearest.lean` (read) | `ae084dbb3f161d2dd369ff224f2117b818243b501ca596d3da2c92d83b65a67c` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/LandauPoleAsym.lean` (read) | `c70dba4115698a4ee22654f0aaf213b886afe28a2d1d44a8e4370aec72fc3944` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/LandauPoleReLe.lean` (read) | `da3615e42c27329c6b8ba7e948cba526d86b45c423225c8c111946cf409ef2ef` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/LogDerivLocal.lean` (read) | `5b7228c12addef3e12bc5665819fccaf5bdc9845bf29578614e7cfa409a515b0` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/MellinRamp.lean` (read) | `b3a4ff30ab74518685987e24c0617626b0ef698f1bae8ffa73dab3bc6944e948` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/WindowHypOfRpow.lean` (read) | `f9238ed2d6c67f1cbe383a33cc3759c00bed31b97a10253fbee59279290c6a5c` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/WindowHypUOfWindowHyp.lean` (read) | `2e4ac8197f1fda900ba710cef10627ebd0576d2bc4207d919f0a8a769ba13c98` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/ZeroFreeOfRpowWindow.lean` (read) | `3252473ba2654b05e9d2ea0781ea91b4c7eadcca0def18b0f21d20212c2f0316` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/kernelIntegral.lean` (read) | `b487d899307a350276d6c5fa1be392104f912a6ccd3e32f426828d7421030502` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/landauTails.lean` (read) | `5700277144d95eea3d90d3d4e2efa3743c3d892753ed41ed27f6f38a2e92708c` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/landauWindow.lean` (read) | `57f49606e6ffd8cab45672d8d4b9c7ded6c0b6b0d140821cc51b5baeb4f67ab5` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/landauWindowIneq.lean` (read) | `e3d5d760bcefe1242d4f5b0ced44fc055f1fa8dfe048a2222cf2c39ae812e59c` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/lemmaL.lean` (read) | `4ce94b876b46e0a3b038c4bfe9ade933c7225170bf07421109ee862fd5941e3d` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/measurableGchi.lean` (read) | `4838a8a6154d8fa0fb87a4008feeb663bca977cdc66fcdb16b6294e3177d5e4b` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/mellinGchiModOne.lean` (statements read; proofs, lines 10-203, skimmed) | `57054bee6a57d89958d6a4d862f74083e68afea8ce0af701b49881e2043767c5` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/mellinGchiOfNeOne.lean` (read) | `22192caa33f0e9b840298329573ca3ea15e3e5d9e60624efcda3562f8ddff26a` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/poleData.lean` (read; the ζ branch, lines 145-229, skimmed) | `78fb8ae795a01ad687440b035c377a9fde71088c726d1ac862ba0fd8bb1fc3c0` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauZeroFreeCriterion.lean` (read) | `d4c5a8ba961bb0e91121212b697217904bf0ba56c2e89c00435fb7ee416a22d7` |
| `Development/AutomorphicArithmetic/PrimitiveCosets/LevelFamily.lean` (read) | `99ab2af08664a9d1cf3afbe5113894d2b56bb64eb052a378f62d027d0f74354e` |
