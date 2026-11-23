/-
Controls for the fields/uses tool (README.md, cases C1-C21). Mathlib only.
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

-- v1.4 (2026-11-23), from the reviewer fairy's surviving mutants on PR 7. Each pair was printed as terms first.
-- C11: a hypothesis applied as a function vs one never used
theorem c11_applied (p q : Prop) (f : p → q) (hp : p) : q := f hp
theorem c11_unapplied (p q : Prop) (f : p → q) (hq : q) : q := hq

-- C12: a use inside a `let` value vs the same use inline
def c12_let (n : ℕ) (f : ℕ → ℕ) : ℕ := let y := f n; y + 1
def c12_inline (n : ℕ) (f : ℕ → ℕ) : ℕ := f n + 1

-- C13: a beta-redex that duplicates its argument vs the reduced form
theorem c13_beta (a : Prop) (h : a) : a ∧ a := (fun x => And.intro x x) h
theorem c13_direct (a : Prop) (h : a) : a ∧ a := And.intro h h

-- C14: a projection applied to a further argument vs a plain projection
theorem c14_overapplied (p q r : Prop) (h : p ∧ (q → r)) (hq : q) : r := h.2 hq
theorem c14_plain (p q r : Prop) (h : p ∧ (q → r)) : q → r := h.2

-- C15: who_reads: one declaration reads field x (by projection, and by a match), another reads only y
structure Pair2 where
  x : ℕ
  y : ℕ
def reads_x (s : Pair2) : ℕ := s.x
def reads_x_match (s : Pair2) : ℕ := match s with | ⟨a, _⟩ => a
def reads_y (s : Pair2) : ℕ := s.y

-- v1.4b, from the fairy's mutants that survived the first v1.4 run. Printed as terms first.
-- C17: a projection of a compound expression that contains h, vs no h there
def c17_projOf (f : ℕ → Pair2) (n : ℕ) : ℕ := (f n).x
def c17_noArg (f : ℕ → Pair2) (n : ℕ) (m : ℕ) : ℕ := (f m).x
-- C18: h only in the binder type of an inner lambda, vs h returned
theorem c18_innerType (n : ℕ) (h : 0 < n) : (∀ (f : (m : ℕ) → 0 < m → Prop), f n h → f n h) ∧ True :=
  ⟨fun _ hf => hf, trivial⟩
theorem c18_value (n : ℕ) (h : 0 < n) : 0 < n ∧ 0 < n := ⟨h, h⟩
-- C19: a strict-implicit slot, vs an explicit one
theorem siUse ⦃p : Prop⦄ (h : p) : p := h
theorem c19_strict (p : Prop) (h : p) : p := @siUse p h

-- v1.4d, from reviewer round 2. C20: a value use 260 applications deep (beyond the walk's depth limit)
set_option maxRecDepth 20000 in
theorem c20_deep (p : Prop) (h : p) : p := id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (id (h))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))
-- C21: h occurs in a type (hk's type) before its value use; a small budget cuts between them
theorem c21_typeThenValue (n : ℕ) (h : 0 < n) (k : (m : ℕ) → 0 < m → Prop) (hk : k n h) : k n h ∧ 0 < n := ⟨hk, h⟩
-- C15c: a private declaration that reads field x
private def privReader (s : Pair2) : ℕ := s.x

end FUControls
