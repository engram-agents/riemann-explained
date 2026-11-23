/-
Controls for the fields/uses tool (SPEC-fields-uses-v1.md, C1-C10). Mathlib only.
Each pair differs in one way; expected classifications are in expected.json, written before the classifier.
-/
import Mathlib.Data.Nat.Prime.Basic
import Mathlib.Algebra.Group.Basic

namespace FUControls

-- C1: direct .2 vs unused
theorem c1_direct (p q : Prop) (h : p ∧ q) : q := h.2
theorem c1_unused (p q : Prop) (_h : p ∧ q) (hq : q) : q := hq

-- C2: instance only vs direct.
-- v1.3 (2026-11-23): the first C2a, `Nat.Prime.two_le (Fact.out)`, elaborated to the SAME body as C2b
-- (`@Fact.out _ hp`, a projection); only the binder's own info differed. C2a now reaches hp only through
-- an instance slot of a lemma that is not a projection.
theorem twoLeOfFact (p : ℕ) [Fact p.Prime] : 2 ≤ p := Nat.Prime.two_le Fact.out
theorem c2_inst (p : ℕ) [hp : Fact p.Prime] : 2 ≤ p := twoLeOfFact p
theorem c2_direct (p : ℕ) (hp : Fact p.Prime) : 2 ≤ p := hp.out.two_le

-- C3: positional destructuring vs projection, same path .2.2
theorem c3_destructure (a b c : Prop) (h : a ∧ b ∧ c) : c := by
  obtain ⟨_, _, hc⟩ := h
  exact hc
theorem c3_proj (a b c : Prop) (h : a ∧ b ∧ c) : c := h.2.2

-- C4: flows_into: h goes into field 2 vs nowhere
structure Trio (a b : Prop) where
  first : a
  second : b
  third : a
theorem c4_flows (a b : Prop) (x : a) (h : b) : Trio a b := ⟨x, h, x⟩
theorem c4_noflow (a b : Prop) (x : a) (h : b) (y : b) : Trio a b := ⟨x, y, x⟩

-- C5: passed whole to a callee that ignores it vs one that uses it
theorem ignores (p q : Prop) (_h : p) (hq : q) : q := hq
theorem usesIt (p : Prop) (h : p) : p := h
theorem c5_to_ignorer (p q : Prop) (h : p) (hq : q) : q := ignores p q h hq
theorem c5_to_user (p : Prop) (h : p) : p := usesIt p h

-- C6: simp [h] vs simp
theorem c6_simp_h (n : ℕ) (h : n = 3) : n + 0 = 3 := by simp [h]
theorem c6_simp (n : ℕ) (_h : n = 3) : n + 0 = n := by simp

-- C7: match with an auxiliary, and a first-wrapper
def c7_match (n : ℕ) (h : 0 < n) : ℕ :=
  match n, h with
  | k + 1, _ => k
theorem c7_target (p : Prop) (h : p) : p := h
theorem c7_wrapper (p : Prop) (h : p) : p := by
  first | exact @c7_target p h | exact c7_target p h

-- C8: a nested proof inside a DATA definition, which Lean abstracts into a `_proof_N` helper, vs the same proof inline
def c8_abstracted (n : ℕ) (h : 0 < n) : {m : ℕ // 0 < m} := ⟨n, Nat.lt_of_lt_of_le h (le_refl n)⟩
theorem c8_inline (n : ℕ) (h : 0 < n) : 0 < n := Nat.lt_of_lt_of_le h (le_refl n)

-- C9: local renaming vs direct
theorem c9_renamed (p q : Prop) (h : p ∧ q) : q := by
  have h2 := h
  exact h2.2
theorem c9_direct (p q : Prop) (h : p ∧ q) : q := h.2

-- C10: in types only vs direct
theorem c10_types_only (n : ℕ) (h : 0 < n) (f : (m : ℕ) → 0 < m → Prop) (hf : f n h) : f n h := hf
theorem c10_value (n : ℕ) (h : 0 < n) : 0 < n := h

end FUControls
