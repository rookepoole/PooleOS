-------------------------- MODULE PooleVirtualMemory --------------------------
EXTENDS FiniteSets, Naturals

CONSTANTS Domains, CPUs, Pages, VirtualAddresses, MaxGeneration,
          NoDomain, NoTranslation, UnsafeStaleMapping, UnsafeEarlyReuse

Translations == [page : Pages, generation : 0..MaxGeneration]

ASSUME /\ Cardinality(Domains) = 2
       /\ Cardinality(CPUs) = 2
       /\ Cardinality(Pages) = 2
       /\ Cardinality(VirtualAddresses) = 1
       /\ MaxGeneration \in Nat \ {0}
       /\ NoDomain \notin Domains
       /\ NoTranslation \notin Translations
       /\ UnsafeStaleMapping \in BOOLEAN
       /\ UnsafeEarlyReuse \in BOOLEAN
       /\ ~(UnsafeStaleMapping /\ UnsafeEarlyReuse)

VARIABLES owner, generation, pageTable, tlb, retired, pending, transferTarget

vars == <<owner, generation, pageTable, tlb, retired, pending, transferTarget>>

TypeOK ==
    /\ owner \in [Pages -> Domains]
    /\ generation \in [Pages -> 0..MaxGeneration]
    /\ pageTable \in [Domains -> [VirtualAddresses -> Translations \cup {NoTranslation}]]
    /\ tlb \in [CPUs -> [Domains -> [VirtualAddresses -> Translations \cup {NoTranslation}]]]
    /\ retired \in [Domains -> [VirtualAddresses -> Translations \cup {NoTranslation}]]
    /\ pending \in [Domains -> [VirtualAddresses -> SUBSET CPUs]]
    /\ transferTarget \in [Pages -> Domains \cup {NoDomain}]

Init ==
    /\ owner \in [Pages -> Domains]
    /\ generation = [page \in Pages |-> 0]
    /\ pageTable = [domain \in Domains |-> [va \in VirtualAddresses |-> NoTranslation]]
    /\ tlb = [cpu \in CPUs |->
                [domain \in Domains |-> [va \in VirtualAddresses |-> NoTranslation]]]
    /\ retired = [domain \in Domains |-> [va \in VirtualAddresses |-> NoTranslation]]
    /\ pending = [domain \in Domains |-> [va \in VirtualAddresses |-> {}]]
    /\ transferTarget = [page \in Pages |-> NoDomain]

Map(domain, va, page) ==
    /\ owner[page] = domain
    /\ transferTarget[page] = NoDomain
    /\ pageTable[domain][va] = NoTranslation
    /\ retired[domain][va] = NoTranslation
    /\ pending[domain][va] = {}
    /\ \A cpu \in CPUs: tlb[cpu][domain][va] = NoTranslation
    /\ pageTable' = [pageTable EXCEPT
            ![domain][va] = [page |-> page, generation |-> generation[page]]]
    /\ UNCHANGED <<owner, generation, tlb, retired, pending, transferTarget>>

TlbFill(cpu, domain, va) ==
    /\ pageTable[domain][va] # NoTranslation
    /\ pending[domain][va] = {}
    /\ tlb' = [tlb EXCEPT ![cpu][domain][va] = pageTable[domain][va]]
    /\ UNCHANGED <<owner, generation, pageTable, retired, pending, transferTarget>>

TlbEvict(cpu, domain, va) ==
    /\ tlb[cpu][domain][va] # NoTranslation
    /\ cpu \notin pending[domain][va]
    /\ tlb' = [tlb EXCEPT ![cpu][domain][va] = NoTranslation]
    /\ UNCHANGED <<owner, generation, pageTable, retired, pending, transferTarget>>

BeginTransfer(page, target) ==
    /\ transferTarget[page] = NoDomain
    /\ generation[page] < MaxGeneration
    /\ target \in Domains \ {owner[page]}
    /\ transferTarget' = [transferTarget EXCEPT ![page] = target]
    /\ UNCHANGED <<owner, generation, pageTable, tlb, retired, pending>>

CancelTransfer(page) ==
    /\ transferTarget[page] # NoDomain
    /\ transferTarget' = [transferTarget EXCEPT ![page] = NoDomain]
    /\ UNCHANGED <<owner, generation, pageTable, tlb, retired, pending>>

Unmap(domain, va) ==
    /\ pageTable[domain][va] # NoTranslation
    /\ retired[domain][va] = NoTranslation
    /\ pending[domain][va] = {}
    /\ LET translation == pageTable[domain][va]
           cached == {cpu \in CPUs: tlb[cpu][domain][va] = translation}
       IN /\ pageTable' = [pageTable EXCEPT ![domain][va] = NoTranslation]
          /\ pending' = [pending EXCEPT ![domain][va] = cached]
          /\ retired' = [retired EXCEPT
                  ![domain][va] = IF cached = {} THEN NoTranslation ELSE translation]
    /\ UNCHANGED <<owner, generation, tlb, transferTarget>>

AcknowledgeShootdown(cpu, domain, va) ==
    /\ cpu \in pending[domain][va]
    /\ retired[domain][va] # NoTranslation
    /\ tlb[cpu][domain][va] = retired[domain][va]
    /\ LET remaining == pending[domain][va] \ {cpu}
       IN /\ tlb' = [tlb EXCEPT ![cpu][domain][va] = NoTranslation]
          /\ pending' = [pending EXCEPT ![domain][va] = remaining]
          /\ retired' = [retired EXCEPT
                  ![domain][va] = IF remaining = {} THEN NoTranslation ELSE @]
    /\ UNCHANGED <<owner, generation, pageTable, transferTarget>>

PageTableClear(page) ==
    \A domain \in Domains, va \in VirtualAddresses:
        IF pageTable[domain][va] = NoTranslation
           THEN TRUE
           ELSE pageTable[domain][va].page # page

TlbClear(page) ==
    \A cpu \in CPUs, domain \in Domains, va \in VirtualAddresses:
        IF tlb[cpu][domain][va] = NoTranslation
           THEN TRUE
           ELSE tlb[cpu][domain][va].page # page

RetiredClear(page) ==
    \A domain \in Domains, va \in VirtualAddresses:
        IF retired[domain][va] = NoTranslation
           THEN TRUE
           ELSE retired[domain][va].page # page

TransferReady(page) ==
    IF UnsafeStaleMapping
       THEN TlbClear(page) /\ RetiredClear(page)
       ELSE IF UnsafeEarlyReuse
               THEN PageTableClear(page)
               ELSE PageTableClear(page) /\ TlbClear(page) /\ RetiredClear(page)

CompleteTransfer(page) ==
    /\ transferTarget[page] # NoDomain
    /\ generation[page] < MaxGeneration
    /\ TransferReady(page)
    /\ owner' = [owner EXCEPT ![page] = transferTarget[page]]
    /\ generation' = [generation EXCEPT ![page] = @ + 1]
    /\ transferTarget' = [transferTarget EXCEPT ![page] = NoDomain]
    /\ UNCHANGED <<pageTable, tlb, retired, pending>>

Idle == UNCHANGED vars

Next ==
    \/ (\E domain \in Domains, va \in VirtualAddresses, page \in Pages:
            Map(domain, va, page))
    \/ (\E cpu \in CPUs, domain \in Domains, va \in VirtualAddresses:
            TlbFill(cpu, domain, va))
    \/ (\E cpu \in CPUs, domain \in Domains, va \in VirtualAddresses:
            TlbEvict(cpu, domain, va))
    \/ (\E page \in Pages, target \in Domains: BeginTransfer(page, target))
    \/ (\E page \in Pages: CancelTransfer(page))
    \/ (\E domain \in Domains, va \in VirtualAddresses: Unmap(domain, va))
    \/ (\E cpu \in CPUs, domain \in Domains, va \in VirtualAddresses:
            AcknowledgeShootdown(cpu, domain, va))
    \/ (\E page \in Pages: CompleteTransfer(page))
    \/ Idle

Spec == Init /\ [][Next]_vars

TransferTargetSafety ==
    \A page \in Pages:
        transferTarget[page] # NoDomain =>
            /\ transferTarget[page] \in Domains \ {owner[page]}
            /\ generation[page] < MaxGeneration

PageTableSafety ==
    \A domain \in Domains, va \in VirtualAddresses:
        pageTable[domain][va] # NoTranslation =>
            /\ owner[pageTable[domain][va].page] = domain
            /\ generation[pageTable[domain][va].page] = pageTable[domain][va].generation

TlbSafety ==
    \A cpu \in CPUs, domain \in Domains, va \in VirtualAddresses:
        tlb[cpu][domain][va] # NoTranslation =>
            /\ owner[tlb[cpu][domain][va].page] = domain
            /\ generation[tlb[cpu][domain][va].page] = tlb[cpu][domain][va].generation

RetiredSafety ==
    \A domain \in Domains, va \in VirtualAddresses:
        retired[domain][va] # NoTranslation =>
            /\ owner[retired[domain][va].page] = domain
            /\ generation[retired[domain][va].page] = retired[domain][va].generation

RetiredPendingConsistency ==
    \A domain \in Domains, va \in VirtualAddresses:
        /\ (retired[domain][va] = NoTranslation) <=> (pending[domain][va] = {})
        /\ retired[domain][va] # NoTranslation =>
            \A cpu \in CPUs:
                (cpu \in pending[domain][va]) <=>
                    (tlb[cpu][domain][va] = retired[domain][va])

PendingImpliesUnmapped ==
    \A domain \in Domains, va \in VirtualAddresses:
        pending[domain][va] # {} => pageTable[domain][va] = NoTranslation

=============================================================================
