-------------------------- MODULE PooleCapabilities ---------------------------
EXTENDS FiniteSets

CONSTANTS Caps, Principals, Rights, Objects, RootCap, RootPrincipal,
          RootObject, NoCap, UnsafeLocalRevoke

ASSUME /\ Cardinality(Caps) = 3
       /\ RootCap \in Caps
       /\ RootPrincipal \in Principals
       /\ RootObject \in Objects
       /\ NoCap \notin Caps
       /\ UnsafeLocalRevoke \in BOOLEAN

VARIABLES present, parent, holder, objectOf, rightsOf, ancestors, revoked

vars == <<present, parent, holder, objectOf, rightsOf, ancestors, revoked>>
Live == present \ revoked

TypeOK ==
    /\ present \subseteq Caps
    /\ revoked \subseteq present
    /\ parent \in [Caps -> Caps \cup {NoCap}]
    /\ holder \in [Caps -> Principals]
    /\ objectOf \in [Caps -> Objects]
    /\ rightsOf \in [Caps -> SUBSET Rights]
    /\ ancestors \in [Caps -> SUBSET Caps]

Init ==
    /\ present = {RootCap}
    /\ parent = [cap \in Caps |-> NoCap]
    /\ holder = [cap \in Caps |-> RootPrincipal]
    /\ objectOf = [cap \in Caps |-> RootObject]
    /\ rightsOf = [cap \in Caps |-> IF cap = RootCap THEN Rights ELSE {}]
    /\ ancestors = [cap \in Caps |-> {}]
    /\ revoked = {}

Derive(source, fresh, recipient, granted) ==
    /\ source \in Live
    /\ fresh \in Caps \ present
    /\ recipient \in Principals
    /\ granted \subseteq rightsOf[source]
    /\ present' = present \cup {fresh}
    /\ parent' = [parent EXCEPT ![fresh] = source]
    /\ holder' = [holder EXCEPT ![fresh] = recipient]
    /\ objectOf' = [objectOf EXCEPT ![fresh] = objectOf[source]]
    /\ rightsOf' = [rightsOf EXCEPT ![fresh] = granted]
    /\ ancestors' = [ancestors EXCEPT ![fresh] = ancestors[source] \cup {source}]
    /\ UNCHANGED revoked

Transfer(cap, recipient) ==
    /\ cap \in Live
    /\ recipient \in Principals
    /\ holder' = [holder EXCEPT ![cap] = recipient]
    /\ UNCHANGED <<present, parent, objectOf, rightsOf, ancestors, revoked>>

Revoke(cap) ==
    /\ cap \in Live
    /\ revoked' =
        IF UnsafeLocalRevoke
           THEN revoked \cup {cap}
           ELSE revoked \cup {item \in present: item = cap \/ cap \in ancestors[item]}
    /\ UNCHANGED <<present, parent, holder, objectOf, rightsOf, ancestors>>

Idle == UNCHANGED vars

Next ==
    \/ (\E source \in Caps, fresh \in Caps, recipient \in Principals,
             granted \in SUBSET Rights:
            Derive(source, fresh, recipient, granted))
    \/ (\E cap \in Caps, recipient \in Principals: Transfer(cap, recipient))
    \/ (\E cap \in Caps: Revoke(cap))
    \/ Idle

Spec == Init /\ [][Next]_vars

RootStable ==
    /\ RootCap \in present
    /\ parent[RootCap] = NoCap
    /\ ancestors[RootCap] = {}
    /\ objectOf[RootCap] = RootObject
    /\ rightsOf[RootCap] = Rights

Attenuation ==
    \A cap \in present \ {RootCap}:
        /\ parent[cap] \in present
        /\ rightsOf[cap] \subseteq rightsOf[parent[cap]]
        /\ objectOf[cap] = objectOf[parent[cap]]
        /\ ancestors[cap] = ancestors[parent[cap]] \cup {parent[cap]}

Acyclic == \A cap \in present: cap \notin ancestors[cap]

NoLiveDescendantOfRevoked ==
    \A cap \in Live: ancestors[cap] \cap revoked = {}

RevocationClosure ==
    \A revokedCap \in revoked:
        \A cap \in present:
            revokedCap \in ancestors[cap] => cap \in revoked

=============================================================================
