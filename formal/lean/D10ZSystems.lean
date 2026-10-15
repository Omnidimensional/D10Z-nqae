import D10ZRefinement

namespace D10Z.Systems

def transactionResult {S : Type} (initial : S) (attempt : Option S) : S :=
  match attempt with
  | some final => final
  | none => initial

theorem transaction_rollback_on_failure {S : Type} (initial : S) :
    transactionResult initial none = initial := by
  rfl

def replay {S C : Type} (step : S → C → S) (initial : S) : List C → S
  | [] => initial
  | cmd :: rest => replay step (step initial cmd) rest

theorem replay_same_inputs_same_result {S C : Type} (step : S → C → S)
    (initial : S) (commands : List C) :
    replay step initial commands = replay step initial commands := by
  rfl

inductive EventOutcome where
  | committed
  | rejected
  deriving DecidableEq, Repr

structure AuditEvent where
  sequence : Nat
  beforeVersion : Nat
  afterVersion : Nat
  outcome : EventOutcome
  deriving Repr

def AuditEventValid (e : AuditEvent) : Prop :=
  match e.outcome with
  | .committed => e.afterVersion = e.beforeVersion + 1
  | .rejected => e.afterVersion = e.beforeVersion

theorem rejected_audit_event_preserves_version (e : AuditEvent)
    (h : AuditEventValid e) (hr : e.outcome = .rejected) :
    e.afterVersion = e.beforeVersion := by
  simp [AuditEventValid, hr] at h
  exact h

structure Store (S : Type) where
  current : S
  version : Nat
  historyLength : Nat

structure Versioned (S : Type) where
  state : S
  version : Nat

inductive CommitResult (S : Type) where
  | committed (store : Store S)
  | stale (prior : Store S)
  | invalid (prior : Store S)

def atomicCommit {S : Type} (store : Store S) (expected : Nat)
    (candidate : Versioned S) : CommitResult S :=
  if expected ≠ store.version then .stale store
  else if candidate.version ≠ expected + 1 then .invalid store
  else .committed ⟨candidate.state, candidate.version, store.historyLength + 1⟩

theorem stale_commit_preserves_store {S : Type} (store : Store S)
    (expected : Nat) (candidate : Versioned S) (h : expected ≠ store.version) :
    atomicCommit store expected candidate = .stale store := by
  simp [atomicCommit, h]

theorem invalid_commit_preserves_store {S : Type} (store : Store S)
    (expected : Nat) (candidate : Versioned S)
    (h₁ : expected = store.version) (h₂ : candidate.version ≠ expected + 1) :
    atomicCommit store expected candidate = .invalid store := by
  simp [atomicCommit, h₁, h₂]

theorem committed_store_advances_history {S : Type} (store : Store S)
    (expected : Nat) (candidate : Versioned S)
    (h₁ : expected = store.version) (h₂ : candidate.version = expected + 1) :
    match atomicCommit store expected candidate with
    | .committed next => next.historyLength = store.historyLength + 1
    | _ => False := by
  simp [atomicCommit, h₁, h₂]

end D10Z.Systems
