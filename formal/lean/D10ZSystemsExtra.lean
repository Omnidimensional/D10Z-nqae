import D10ZSystems

namespace D10Z.SystemsExtra

theorem replay_append {S C : Type} (step : S → C → S) (initial : S)
    (left right : List C) :
    D10Z.Systems.replay step initial (left ++ right) =
      D10Z.Systems.replay step (D10Z.Systems.replay step initial left) right := by
  induction left generalizing initial with
  | nil => rfl
  | cons command rest ih =>
      simp [D10Z.Systems.replay, ih]

theorem commit_history_delta {S : Type} (store : D10Z.Systems.Store S)
    (expected : Nat) (candidate : D10Z.Systems.Versioned S)
    (hVersion : expected = store.version)
    (hNext : candidate.version = expected + 1) :
    match D10Z.Systems.atomicCommit store expected candidate with
    | .committed next => next.historyLength = store.historyLength + 1
    | _ => False := by
  simp [D10Z.Systems.atomicCommit, hVersion, hNext]

end D10Z.SystemsExtra
