------------------------------- MODULE PooleFS -------------------------------
EXTENDS FiniteSets, Naturals

CONSTANTS Blocks, OldBlock, SpareBlock, NoBlock,
          UnsafeTornWrite, UnsafePrematurePublish, UnsafeDoubleAllocation,
          UnsafeNonIdempotentReplay, UnsafeChecksumAcceptance,
          UnsafeRecoveryLeak

SystemStates == {"Mounted", "Crashed", "RecoveryInspect", "RecoveryApplied"}
TransactionStates == {"Unused", "Open", "Interrupted", "Finished"}
DataValues == {"Empty", "Old", "New", "Torn"}
BlockRoles == {"Free", "Live", "Staged"}
JournalStates == {"Empty", "Intent", "Committed"}
AuditFaults == {"None", "PrematurePublish", "InvalidChecksum"}

BoolBit(value) == IF value THEN 1 ELSE 0

ASSUME /\ Cardinality(Blocks) = 2
       /\ OldBlock \in Blocks
       /\ SpareBlock \in Blocks \ {OldBlock}
       /\ NoBlock \notin Blocks
       /\ UnsafeTornWrite \in BOOLEAN
       /\ UnsafePrematurePublish \in BOOLEAN
       /\ UnsafeDoubleAllocation \in BOOLEAN
       /\ UnsafeNonIdempotentReplay \in BOOLEAN
       /\ UnsafeChecksumAcceptance \in BOOLEAN
       /\ UnsafeRecoveryLeak \in BOOLEAN
       /\ BoolBit(UnsafeTornWrite) + BoolBit(UnsafePrematurePublish)
            + BoolBit(UnsafeDoubleAllocation)
            + BoolBit(UnsafeNonIdempotentReplay)
            + BoolBit(UnsafeChecksumAcceptance)
            + BoolBit(UnsafeRecoveryLeak) <= 1

VARIABLES systemState, transactionState, txTarget, pendingData, activeBlock,
          blockValue, blockChecksum, blockRole, journalState, journalTarget,
          journalChecksumValid, replayApplyCount, auditFault

vars == <<systemState, transactionState, txTarget, pendingData, activeBlock,
          blockValue, blockChecksum, blockRole, journalState, journalTarget,
          journalChecksumValid, replayApplyCount, auditFault>>

LiveBlocks == {block \in Blocks : blockRole[block] = "Live"}
StagedBlocks == {block \in Blocks : blockRole[block] = "Staged"}

CommittedRecordValid ==
    /\ journalState = "Committed"
    /\ journalChecksumValid
    /\ journalTarget \in Blocks
    /\ blockRole[journalTarget] \in {"Staged", "Live"}
    /\ blockChecksum[journalTarget]
    /\ blockValue[journalTarget] = "New"

CommitDecision ==
    CommittedRecordValid \/
        (UnsafeChecksumAcceptance /\ journalState = "Committed"
             /\ journalTarget \in Blocks)

HasRecoveryResidue ==
    \/ txTarget # NoBlock
    \/ journalState # "Empty"
    \/ StagedBlocks # {}

TypeOK ==
    /\ systemState \in SystemStates
    /\ transactionState \in TransactionStates
    /\ txTarget \in Blocks \cup {NoBlock}
    /\ pendingData \in BOOLEAN
    /\ activeBlock \in Blocks
    /\ blockValue \in [Blocks -> DataValues]
    /\ blockChecksum \in [Blocks -> BOOLEAN]
    /\ blockRole \in [Blocks -> BlockRoles]
    /\ journalState \in JournalStates
    /\ journalTarget \in Blocks \cup {NoBlock}
    /\ journalChecksumValid \in BOOLEAN
    /\ replayApplyCount \in 0..2
    /\ auditFault \in AuditFaults

Init ==
    /\ systemState = "Mounted"
    /\ transactionState = "Unused"
    /\ txTarget = NoBlock
    /\ pendingData = FALSE
    /\ activeBlock = OldBlock
    /\ blockValue = [block \in Blocks |->
            IF block = OldBlock THEN "Old" ELSE "Empty"]
    /\ blockChecksum = [block \in Blocks |-> block = OldBlock]
    /\ blockRole = [block \in Blocks |->
            IF block = OldBlock THEN "Live" ELSE "Free"]
    /\ journalState = "Empty"
    /\ journalTarget = NoBlock
    /\ journalChecksumValid = FALSE
    /\ replayApplyCount = 0
    /\ auditFault = "None"

BeginTransaction(block) ==
    /\ systemState = "Mounted"
    /\ transactionState = "Unused"
    /\ txTarget = NoBlock
    /\ (blockRole[block] = "Free" \/ UnsafeDoubleAllocation)
    /\ transactionState' = "Open"
    /\ txTarget' = block
    /\ blockRole' = [blockRole EXCEPT ![block] = "Staged"]
    /\ UNCHANGED <<systemState, pendingData, activeBlock, blockValue,
                    blockChecksum, journalState, journalTarget,
                    journalChecksumValid, replayApplyCount, auditFault>>

WriteData ==
    /\ systemState = "Mounted"
    /\ transactionState = "Open"
    /\ txTarget \in Blocks
    /\ blockRole[txTarget] = "Staged"
    /\ blockValue[txTarget] = "Empty"
    /\ ~blockChecksum[txTarget]
    /\ ~pendingData
    /\ pendingData' = TRUE
    /\ UNCHANGED <<systemState, transactionState, txTarget, activeBlock,
                    blockValue, blockChecksum, blockRole, journalState,
                    journalTarget, journalChecksumValid, replayApplyCount,
                    auditFault>>

FlushData ==
    /\ systemState = "Mounted"
    /\ transactionState = "Open"
    /\ txTarget \in Blocks
    /\ blockRole[txTarget] = "Staged"
    /\ pendingData
    /\ pendingData' = FALSE
    /\ blockValue' = [blockValue EXCEPT ![txTarget] = "New"]
    /\ blockChecksum' = [blockChecksum EXCEPT ![txTarget] = TRUE]
    /\ UNCHANGED <<systemState, transactionState, txTarget, activeBlock,
                    blockRole, journalState, journalTarget,
                    journalChecksumValid, replayApplyCount, auditFault>>

PersistIntent ==
    /\ systemState = "Mounted"
    /\ transactionState = "Open"
    /\ txTarget \in Blocks
    /\ blockRole[txTarget] = "Staged"
    /\ blockValue[txTarget] = "New"
    /\ blockChecksum[txTarget]
    /\ ~pendingData
    /\ journalState = "Empty"
    /\ journalState' = "Intent"
    /\ journalTarget' = txTarget
    /\ journalChecksumValid' = TRUE
    /\ UNCHANGED <<systemState, transactionState, txTarget, pendingData,
                    activeBlock, blockValue, blockChecksum, blockRole,
                    replayApplyCount, auditFault>>

PersistCommit ==
    /\ systemState = "Mounted"
    /\ transactionState = "Open"
    /\ journalState = "Intent"
    /\ journalChecksumValid
    /\ journalTarget = txTarget
    /\ txTarget \in Blocks
    /\ blockRole[txTarget] = "Staged"
    /\ blockValue[txTarget] = "New"
    /\ blockChecksum[txTarget]
    /\ journalState' = "Committed"
    /\ UNCHANGED <<systemState, transactionState, txTarget, pendingData,
                    activeBlock, blockValue, blockChecksum, blockRole,
                    journalTarget, journalChecksumValid, replayApplyCount,
                    auditFault>>

PublishCommitted ==
    /\ systemState = "Mounted"
    /\ transactionState = "Open"
    /\ CommittedRecordValid
    /\ journalTarget = txTarget
    /\ activeBlock # txTarget
    /\ activeBlock' = txTarget
    /\ blockRole' = [block \in Blocks |->
            IF block = txTarget
               THEN "Live"
               ELSE IF block = activeBlock THEN "Free" ELSE blockRole[block]]
    /\ UNCHANGED <<systemState, transactionState, txTarget, pendingData,
                    blockValue, blockChecksum, journalState, journalTarget,
                    journalChecksumValid, replayApplyCount, auditFault>>

PublishPremature ==
    /\ UnsafePrematurePublish
    /\ systemState = "Mounted"
    /\ transactionState = "Open"
    /\ txTarget \in Blocks
    /\ blockRole[txTarget] = "Staged"
    /\ blockValue[txTarget] = "New"
    /\ blockChecksum[txTarget]
    /\ journalState # "Committed"
    /\ activeBlock # txTarget
    /\ activeBlock' = txTarget
    /\ blockRole' = [block \in Blocks |->
            IF block = txTarget
               THEN "Live"
               ELSE IF block = activeBlock THEN "Free" ELSE blockRole[block]]
    /\ auditFault' = "PrematurePublish"
    /\ UNCHANGED <<systemState, transactionState, txTarget, pendingData,
                    blockValue, blockChecksum, journalState, journalTarget,
                    journalChecksumValid, replayApplyCount>>

FinishTransaction ==
    /\ systemState = "Mounted"
    /\ transactionState = "Open"
    /\ txTarget \in Blocks
    /\ activeBlock = txTarget
    /\ blockRole[txTarget] = "Live"
    /\ CommittedRecordValid
    /\ ~pendingData
    /\ transactionState' = "Finished"
    /\ txTarget' = NoBlock
    /\ journalState' = "Empty"
    /\ journalTarget' = NoBlock
    /\ journalChecksumValid' = FALSE
    /\ UNCHANGED <<systemState, pendingData, activeBlock, blockValue,
                    blockChecksum, blockRole, replayApplyCount, auditFault>>

CrashMounted ==
    /\ systemState = "Mounted"
    /\ systemState' = "Crashed"
    /\ transactionState' =
            IF transactionState = "Open" THEN "Interrupted"
            ELSE transactionState
    /\ pendingData' = FALSE
    /\ IF UnsafeTornWrite /\ pendingData /\ txTarget \in Blocks
          THEN /\ blockValue' = [blockValue EXCEPT ![txTarget] = "Torn"]
               /\ blockChecksum' = [blockChecksum EXCEPT ![txTarget] = TRUE]
          ELSE /\ UNCHANGED <<blockValue, blockChecksum>>
    /\ UNCHANGED <<txTarget, activeBlock, blockRole, journalState,
                    journalTarget, journalChecksumValid, replayApplyCount,
                    auditFault>>

CrashRecovery ==
    /\ systemState \in {"RecoveryInspect", "RecoveryApplied"}
    /\ systemState' = "Crashed"
    /\ pendingData' = FALSE
    /\ UNCHANGED <<transactionState, txTarget, activeBlock, blockValue,
                    blockChecksum, blockRole, journalState, journalTarget,
                    journalChecksumValid, replayApplyCount, auditFault>>

CorruptJournal ==
    /\ systemState = "Crashed"
    /\ journalState # "Empty"
    /\ journalChecksumValid
    /\ journalChecksumValid' = FALSE
    /\ UNCHANGED <<systemState, transactionState, txTarget, pendingData,
                    activeBlock, blockValue, blockChecksum, blockRole,
                    journalState, journalTarget, replayApplyCount, auditFault>>

CorruptStagedData(block) ==
    /\ systemState = "Crashed"
    /\ blockRole[block] = "Staged"
    /\ block # activeBlock
    /\ (blockValue[block] # "Torn" \/ blockChecksum[block])
    /\ blockValue' = [blockValue EXCEPT ![block] = "Torn"]
    /\ blockChecksum' = [blockChecksum EXCEPT ![block] = FALSE]
    /\ UNCHANGED <<systemState, transactionState, txTarget, pendingData,
                    activeBlock, blockRole, journalState, journalTarget,
                    journalChecksumValid, replayApplyCount, auditFault>>

StartRecovery ==
    /\ systemState = "Crashed"
    /\ systemState' = "RecoveryInspect"
    /\ UNCHANGED <<transactionState, txTarget, pendingData, activeBlock,
                    blockValue, blockChecksum, blockRole, journalState,
                    journalTarget, journalChecksumValid, replayApplyCount,
                    auditFault>>

ApplyRecoveryCommit ==
    /\ systemState = "RecoveryInspect"
    /\ CommitDecision
    /\ LET target == journalTarget
           alreadyPublished == activeBlock = target
           increment == IF alreadyPublished
                           THEN IF UnsafeNonIdempotentReplay THEN 1 ELSE 0
                           ELSE 1
       IN /\ replayApplyCount + increment <= 2
          /\ systemState' = "RecoveryApplied"
          /\ activeBlock' = target
          /\ blockRole' = [block \in Blocks |->
                  IF block = target
                     THEN "Live"
                     ELSE IF block = activeBlock /\ activeBlock # target
                             THEN "Free"
                             ELSE blockRole[block]]
          /\ replayApplyCount' = replayApplyCount + increment
          /\ auditFault' =
                  IF CommittedRecordValid THEN auditFault
                  ELSE "InvalidChecksum"
    /\ UNCHANGED <<transactionState, txTarget, pendingData, blockValue,
                    blockChecksum, journalState, journalTarget,
                    journalChecksumValid>>

ApplyRecoveryRollback ==
    /\ systemState = "RecoveryInspect"
    /\ ~CommitDecision
    /\ systemState' = "RecoveryApplied"
    /\ UNCHANGED <<transactionState, txTarget, pendingData, activeBlock,
                    blockValue, blockChecksum, blockRole, journalState,
                    journalTarget, journalChecksumValid, replayApplyCount,
                    auditFault>>

FinishRecovery ==
    /\ systemState = "RecoveryApplied"
    /\ LET leak == UnsafeRecoveryLeak /\ HasRecoveryResidue
       IN /\ systemState' = "Mounted"
          /\ transactionState' =
                  IF transactionState = "Unused" THEN "Unused"
                  ELSE "Finished"
          /\ pendingData' = FALSE
          /\ IF leak
                THEN /\ UNCHANGED <<txTarget, blockRole, journalState,
                                      journalTarget, journalChecksumValid>>
                ELSE /\ txTarget' = NoBlock
                     /\ blockRole' = [block \in Blocks |->
                             IF blockRole[block] = "Staged"
                                THEN "Free"
                                ELSE blockRole[block]]
                     /\ journalState' = "Empty"
                     /\ journalTarget' = NoBlock
                     /\ journalChecksumValid' = FALSE
    /\ UNCHANGED <<activeBlock, blockValue, blockChecksum,
                    replayApplyCount, auditFault>>

Idle == UNCHANGED vars

Next ==
    \/ (\E block \in Blocks: BeginTransaction(block))
    \/ WriteData
    \/ FlushData
    \/ PersistIntent
    \/ PersistCommit
    \/ PublishCommitted
    \/ PublishPremature
    \/ FinishTransaction
    \/ CrashMounted
    \/ CrashRecovery
    \/ CorruptJournal
    \/ (\E block \in Blocks: CorruptStagedData(block))
    \/ StartRecovery
    \/ ApplyRecoveryCommit
    \/ ApplyRecoveryRollback
    \/ FinishRecovery
    \/ Idle

Spec == Init /\ [][Next]_vars

AllocationOwnershipSound ==
    /\ blockRole[activeBlock] = "Live"
    /\ Cardinality(LiveBlocks) = 1
    /\ \A block \in StagedBlocks: block # activeBlock

ChecksummedDataValid ==
    \A block \in Blocks:
        blockChecksum[block] => blockValue[block] \in {"Old", "New"}

PublicationOrderSound == auditFault # "PrematurePublish"

ChecksumRejectionSound == auditFault # "InvalidChecksum"

VisibleOldOrNew ==
    /\ blockChecksum[activeBlock]
    /\ blockValue[activeBlock] \in {"Old", "New"}

JournalShapeSound ==
    /\ (journalState = "Empty") <=>
            (journalTarget = NoBlock /\ ~journalChecksumValid)
    /\ journalState # "Empty" =>
            /\ journalTarget \in Blocks
            /\ journalTarget = txTarget
            /\ blockRole[journalTarget] \in {"Staged", "Live"}

TransactionStateSound ==
    /\ transactionState = "Unused" => txTarget = NoBlock
    /\ transactionState = "Open" =>
            /\ systemState = "Mounted"
            /\ txTarget \in Blocks
    /\ transactionState = "Interrupted" =>
            /\ systemState # "Mounted"
            /\ txTarget \in Blocks
    /\ pendingData =>
            /\ transactionState = "Open"
            /\ txTarget \in Blocks
            /\ blockRole[txTarget] = "Staged"
    /\ systemState # "Mounted" =>
            /\ transactionState # "Open"
            /\ ~pendingData
    /\ txTarget = NoBlock => StagedBlocks = {}
    /\ txTarget \in Blocks => blockRole[txTarget] \in {"Staged", "Live"}

RecoveryStateSound ==
    /\ systemState = "Crashed" => ~pendingData
    /\ systemState \in {"RecoveryInspect", "RecoveryApplied"} =>
            /\ ~pendingData
            /\ transactionState # "Open"

MountedQuiescent ==
    systemState = "Mounted" /\ transactionState # "Open" =>
        /\ txTarget = NoBlock
        /\ ~pendingData
        /\ journalState = "Empty"
        /\ journalTarget = NoBlock
        /\ ~journalChecksumValid
        /\ StagedBlocks = {}

ReplayIdempotent == replayApplyCount <= 1

StagingBound == Cardinality(StagedBlocks) <= 1

=============================================================================
