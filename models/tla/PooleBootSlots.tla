---------------------------- MODULE PooleBootSlots ----------------------------
EXTENDS FiniteSets, Naturals

CONSTANTS Slots, MaxAttempts, NoSlot, UnsafeRollback

ASSUME /\ Cardinality(Slots) = 2
       /\ NoSlot \notin Slots
       /\ MaxAttempts \in Nat \ {0}
       /\ UnsafeRollback \in BOOLEAN

VARIABLES active, knownGood, candidate, attempts, phase

vars == <<active, knownGood, candidate, attempts, phase>>
Phases == {"steady", "staged", "trial"}

TypeOK ==
    /\ active \in Slots
    /\ knownGood \subseteq Slots
    /\ candidate \in Slots \cup {NoSlot}
    /\ attempts \in [Slots -> 0..MaxAttempts]
    /\ phase \in Phases

Init ==
    /\ active \in Slots
    /\ knownGood = {active}
    /\ candidate = NoSlot
    /\ attempts = [slot \in Slots |-> 0]
    /\ phase = "steady"

Stage(slot) ==
    /\ phase = "steady"
    /\ slot \in Slots \ knownGood
    /\ candidate' = slot
    /\ phase' = "staged"
    /\ UNCHANGED <<active, knownGood, attempts>>

StartTrial ==
    /\ phase = "staged"
    /\ candidate \in Slots
    /\ attempts[candidate] < MaxAttempts
    /\ active' = candidate
    /\ attempts' = [attempts EXCEPT ![candidate] = @ + 1]
    /\ phase' = "trial"
    /\ UNCHANGED <<knownGood, candidate>>

TrialSuccess ==
    /\ phase = "trial"
    /\ candidate = active
    /\ knownGood' = knownGood \cup {active}
    /\ candidate' = NoSlot
    /\ phase' = "steady"
    /\ UNCHANGED <<active, attempts>>

TrialFailure ==
    /\ phase = "trial"
    /\ candidate = active
    /\ \E fallback \in knownGood:
        /\ active' = fallback
        /\ knownGood' = IF UnsafeRollback THEN {} ELSE knownGood
        /\ IF attempts[candidate] < MaxAttempts
              THEN /\ candidate' = candidate
                   /\ phase' = "staged"
              ELSE /\ candidate' = NoSlot
                   /\ phase' = "steady"
    /\ UNCHANGED attempts

DiscardCandidate ==
    /\ phase = "staged"
    /\ candidate \in Slots
    /\ candidate' = NoSlot
    /\ phase' = "steady"
    /\ UNCHANGED <<active, knownGood, attempts>>

Idle == UNCHANGED vars

Next ==
    \/ (\E slot \in Slots: Stage(slot))
    \/ StartTrial
    \/ TrialSuccess
    \/ TrialFailure
    \/ DiscardCandidate
    \/ Idle

Spec == Init /\ [][Next]_vars

Recoverable == knownGood # {}

SteadyActiveKnownGood == phase # "trial" => active \in knownGood

TrialRollbackAvailable ==
    phase = "trial" => knownGood \ {active} # {}

CandidateConsistency ==
    /\ (phase = "steady" => candidate = NoSlot)
    /\ (phase \in {"staged", "trial"} => candidate \in Slots \ knownGood)
    /\ (phase = "staged" => active \in knownGood)
    /\ (phase = "trial" => active = candidate)

AttemptBound == \A slot \in Slots: attempts[slot] <= MaxAttempts

=============================================================================
