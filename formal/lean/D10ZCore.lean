/-
D10Z CORE: indexed transition kernel.
This model is a mathematical specification; it does not itself certify Python.
-/
namespace D10Z

structure State (n : Nat) where
  value : Fin n → Nat
  edge : Fin n → Fin n → Bool
  version : Nat

def setValue {n : Nat} (s : State n) (i : Fin n) (v : Nat) : State n :=
  { s with
    value := fun j => if j = i then v else s.value j
    version := s.version + 1 }

def addEdge {n : Nat} (s : State n) (src dst : Fin n) : State n :=
  { s with
    edge := fun x y => if x = src ∧ y = dst then true else s.edge x y
    version := s.version + 1 }

def removeEdge {n : Nat} (s : State n) (src dst : Fin n) : State n :=
  { s with
    edge := fun x y => if x = src ∧ y = dst then false else s.edge x y
    version := s.version + 1 }

@[simp] theorem setValue_target {n : Nat} (s : State n) (i : Fin n) (v : Nat) :
    (setValue s i v).value i = v := by
  simp [setValue]

theorem setValue_other {n : Nat} (s : State n) (i j : Fin n) (v : Nat)
    (h : j ≠ i) : (setValue s i v).value j = s.value j := by
  simp [setValue, h]

@[simp] theorem setValue_preserves_edges {n : Nat} (s : State n) (i : Fin n) (v : Nat)
    (x y : Fin n) : (setValue s i v).edge x y = s.edge x y := by
  rfl

@[simp] theorem setValue_increments_version {n : Nat} (s : State n) (i : Fin n) (v : Nat) :
    (setValue s i v).version = s.version + 1 := by
  rfl

@[simp] theorem addEdge_target_true {n : Nat} (s : State n) (src dst : Fin n) :
    (addEdge s src dst).edge src dst = true := by
  simp [addEdge]

theorem addEdge_preserves_other_edges {n : Nat} (s : State n)
    (src dst x y : Fin n) (h : ¬ (x = src ∧ y = dst)) :
    (addEdge s src dst).edge x y = s.edge x y := by
  by_cases hx : x = src
  · by_cases hy : y = dst
    · exact False.elim (h ⟨hx, hy⟩)
    · simp [addEdge, hx, hy]
  · simp [addEdge, hx]

@[simp] theorem addEdge_preserves_values {n : Nat} (s : State n) (src dst x : Fin n) :
    (addEdge s src dst).value x = s.value x := by
  rfl

@[simp] theorem addEdge_increments_version {n : Nat} (s : State n) (src dst : Fin n) :
    (addEdge s src dst).version = s.version + 1 := by
  rfl

@[simp] theorem removeEdge_target_false {n : Nat} (s : State n) (src dst : Fin n) :
    (removeEdge s src dst).edge src dst = false := by
  simp [removeEdge]

theorem removeEdge_preserves_other_edges {n : Nat} (s : State n)
    (src dst x y : Fin n) (h : ¬ (x = src ∧ y = dst)) :
    (removeEdge s src dst).edge x y = s.edge x y := by
  by_cases hx : x = src
  · by_cases hy : y = dst
    · exact False.elim (h ⟨hx, hy⟩)
    · simp [removeEdge, hx, hy]
  · simp [removeEdge, hx]

@[simp] theorem removeEdge_preserves_values {n : Nat} (s : State n) (src dst x : Fin n) :
    (removeEdge s src dst).value x = s.value x := by
  rfl

@[simp] theorem removeEdge_increments_version {n : Nat} (s : State n) (src dst : Fin n) :
    (removeEdge s src dst).version = s.version + 1 := by
  rfl

inductive Result (α : Type) where
  | accepted (value : α)
  | rejected (prior : α) (code : String)
  deriving Repr

def reject {α : Type} (prior : α) (code : String) : Result α :=
  .rejected prior code

theorem reject_preserves_state {α : Type} (s : α) (code : String) :
    reject s code = Result.rejected s code := by
  rfl

def runTwo {n : Nat} (s : State n) (i j : Fin n) (a b : Nat) : State n :=
  setValue (setValue s i a) j b

theorem runTwo_version {n : Nat} (s : State n) (i j : Fin n) (a b : Nat) :
    (runTwo s i j a b).version = s.version + 2 := by
  simp [runTwo, setValue, Nat.add_assoc]

end D10Z
