---------------------------- MODULE PooleScheduler ---------------------------
EXTENDS FiniteSets, Naturals

CONSTANTS Tasks, LowTask, MediumTask, HighTask, NoTask, MaxBypass,
          UnsafeLostCancelWake, UnsafeLostTimeoutWake, UnsafeDuplicateWake,
          UnsafeNoPriorityInheritance, UnsafePriorityBypass,
          UnsafeFairnessBypass, UnsafeLeakyTeardown

TaskStates == {"Dormant", "Runnable", "Running", "Blocked", "Dead"}
WakeReasons == {"None", "Cancelled", "TimedOut", "LockGranted", "OwnerGone"}

BoolBit(value) == IF value THEN 1 ELSE 0

ASSUME /\ Cardinality(Tasks) = 3
       /\ LowTask \in Tasks
       /\ MediumTask \in Tasks \ {LowTask}
       /\ HighTask \in Tasks \ {LowTask, MediumTask}
       /\ NoTask \notin Tasks
       /\ MaxBypass = 2
       /\ UnsafeLostCancelWake \in BOOLEAN
       /\ UnsafeLostTimeoutWake \in BOOLEAN
       /\ UnsafeDuplicateWake \in BOOLEAN
       /\ UnsafeNoPriorityInheritance \in BOOLEAN
       /\ UnsafePriorityBypass \in BOOLEAN
       /\ UnsafeFairnessBypass \in BOOLEAN
       /\ UnsafeLeakyTeardown \in BOOLEAN
       /\ BoolBit(UnsafeLostCancelWake) + BoolBit(UnsafeLostTimeoutWake)
            + BoolBit(UnsafeDuplicateWake) + BoolBit(UnsafeNoPriorityInheritance)
            + BoolBit(UnsafePriorityBypass) + BoolBit(UnsafeFairnessBypass)
            + BoolBit(UnsafeLeakyTeardown) <= 1

BasePriority(task) ==
    CASE task = LowTask -> 1
      [] task = MediumTask -> 2
      [] task = HighTask -> 3

VARIABLES taskState, runCount, current, lockOwner, waiting, wakeReason,
          bypassCount, dispatchPrioritySound

vars == <<taskState, runCount, current, lockOwner, waiting, wakeReason,
          bypassCount, dispatchPrioritySound>>

Waiters(ownerTask) ==
    {waiter \in Tasks : waiting[waiter] /\ lockOwner = ownerTask}

WaiterPriorities(ownerTask) ==
    {BasePriority(waiter) : waiter \in Waiters(ownerTask)}

RequiredEffectivePriority(task) ==
    LET priorities == {BasePriority(task)} \cup WaiterPriorities(task)
    IN CHOOSE priority \in priorities:
            \A other \in priorities: priority >= other

EffectivePriority(task) ==
    IF UnsafeNoPriorityInheritance
       THEN BasePriority(task)
       ELSE RequiredEffectivePriority(task)

IsRunnable(task) == taskState[task] = "Runnable" /\ runCount[task] > 0

HighestRunnable(task) ==
    /\ IsRunnable(task)
    /\ \A other \in Tasks:
            IsRunnable(other) => EffectivePriority(other) <= EffectivePriority(task)

NoBypassOverflow(selected) ==
    \A other \in Tasks \ {selected}:
        IsRunnable(other) => bypassCount[other] < MaxBypass

HighestWaiter(waiter) ==
    /\ waiting[waiter]
    /\ \A other \in Tasks:
            waiting[other] => BasePriority(other) <= BasePriority(waiter)

TypeOK ==
    /\ taskState \in [Tasks -> TaskStates]
    /\ runCount \in [Tasks -> 0..2]
    /\ current \in Tasks \cup {NoTask}
    /\ lockOwner \in Tasks \cup {NoTask}
    /\ waiting \in [Tasks -> BOOLEAN]
    /\ wakeReason \in [Tasks -> WakeReasons]
    /\ bypassCount \in [Tasks -> 0..(MaxBypass + 1)]
    /\ dispatchPrioritySound \in BOOLEAN

Init ==
    /\ taskState = [task \in Tasks |->
            IF task = LowTask THEN "Running" ELSE "Dormant"]
    /\ runCount = [task \in Tasks |-> 0]
    /\ current = LowTask
    /\ lockOwner = LowTask
    /\ waiting = [task \in Tasks |-> FALSE]
    /\ wakeReason = [task \in Tasks |-> "None"]
    /\ bypassCount = [task \in Tasks |-> 0]
    /\ dispatchPrioritySound = TRUE

Activate(task) ==
    /\ taskState[task] = "Dormant"
    /\ taskState' = [taskState EXCEPT ![task] = "Runnable"]
    /\ runCount' = [runCount EXCEPT ![task] = 1]
    /\ bypassCount' = [bypassCount EXCEPT ![task] = 0]
    /\ wakeReason' = [wakeReason EXCEPT ![task] = "None"]
    /\ UNCHANGED <<current, lockOwner, waiting, dispatchPrioritySound>>

Preempt(task) ==
    /\ current = task
    /\ taskState[task] = "Running"
    /\ wakeReason[task] = "None"
    /\ taskState' = [taskState EXCEPT ![task] = "Runnable"]
    /\ runCount' = [runCount EXCEPT ![task] = 1]
    /\ current' = NoTask
    /\ bypassCount' = [bypassCount EXCEPT ![task] = 0]
    /\ UNCHANGED <<lockOwner, waiting, wakeReason, dispatchPrioritySound>>

Dispatch(task) ==
    /\ current = NoTask
    /\ IsRunnable(task)
    /\ (HighestRunnable(task) \/ UnsafePriorityBypass)
    /\ (NoBypassOverflow(task) \/ UnsafeFairnessBypass)
    /\ taskState' = [taskState EXCEPT ![task] = "Running"]
    /\ runCount' = [runCount EXCEPT ![task] = 0]
    /\ current' = task
    /\ bypassCount' = [other \in Tasks |->
            IF other = task
               THEN 0
               ELSE IF IsRunnable(other)
                       THEN bypassCount[other] + 1
                       ELSE bypassCount[other]]
    /\ dispatchPrioritySound' =
            (dispatchPrioritySound /\ HighestRunnable(task))
    /\ UNCHANGED <<lockOwner, waiting, wakeReason>>

AcquireLock(task) ==
    /\ current = task
    /\ taskState[task] = "Running"
    /\ wakeReason[task] = "None"
    /\ lockOwner = NoTask
    /\ lockOwner' = task
    /\ UNCHANGED <<taskState, runCount, current, waiting, wakeReason,
                   bypassCount, dispatchPrioritySound>>

BlockOnLock(task) ==
    /\ current = task
    /\ taskState[task] = "Running"
    /\ wakeReason[task] = "None"
    /\ lockOwner \in Tasks \ {task}
    /\ taskState' = [taskState EXCEPT ![task] = "Blocked"]
    /\ runCount' = [runCount EXCEPT ![task] = 0]
    /\ current' = NoTask
    /\ waiting' = [waiting EXCEPT ![task] = TRUE]
    /\ wakeReason' = [wakeReason EXCEPT ![task] = "None"]
    /\ bypassCount' = [bypassCount EXCEPT ![task] = 0]
    /\ UNCHANGED <<lockOwner, dispatchPrioritySound>>

CancelWait(task) ==
    /\ taskState[task] = "Blocked"
    /\ waiting[task]
    /\ IF UnsafeLostCancelWake
          THEN /\ UNCHANGED <<taskState, runCount, waiting, bypassCount>>
          ELSE /\ taskState' = [taskState EXCEPT ![task] = "Runnable"]
               /\ runCount' = [runCount EXCEPT
                       ![task] = IF UnsafeDuplicateWake THEN 2 ELSE 1]
               /\ waiting' = [waiting EXCEPT ![task] = FALSE]
               /\ bypassCount' = [bypassCount EXCEPT ![task] = 0]
    /\ wakeReason' = [wakeReason EXCEPT ![task] = "Cancelled"]
    /\ UNCHANGED <<current, lockOwner, dispatchPrioritySound>>

TimeoutWait(task) ==
    /\ taskState[task] = "Blocked"
    /\ waiting[task]
    /\ IF UnsafeLostTimeoutWake
          THEN /\ UNCHANGED <<taskState, runCount, waiting, bypassCount>>
          ELSE /\ taskState' = [taskState EXCEPT ![task] = "Runnable"]
               /\ runCount' = [runCount EXCEPT ![task] = 1]
               /\ waiting' = [waiting EXCEPT ![task] = FALSE]
               /\ bypassCount' = [bypassCount EXCEPT ![task] = 0]
    /\ wakeReason' = [wakeReason EXCEPT ![task] = "TimedOut"]
    /\ UNCHANGED <<current, lockOwner, dispatchPrioritySound>>

ReleaseToWaiter(task, waiter) ==
    /\ current = task
    /\ taskState[task] = "Running"
    /\ wakeReason[task] = "None"
    /\ lockOwner = task
    /\ HighestWaiter(waiter)
    /\ lockOwner' = waiter
    /\ taskState' = [taskState EXCEPT ![waiter] = "Runnable"]
    /\ runCount' = [runCount EXCEPT ![waiter] = 1]
    /\ waiting' = [waiting EXCEPT ![waiter] = FALSE]
    /\ wakeReason' = [wakeReason EXCEPT ![waiter] = "LockGranted"]
    /\ bypassCount' = [bypassCount EXCEPT ![waiter] = 0]
    /\ UNCHANGED <<current, dispatchPrioritySound>>

ReleaseUncontended(task) ==
    /\ current = task
    /\ taskState[task] = "Running"
    /\ wakeReason[task] = "None"
    /\ lockOwner = task
    /\ \A waiter \in Tasks: ~waiting[waiter]
    /\ lockOwner' = NoTask
    /\ UNCHANGED <<taskState, runCount, current, waiting, wakeReason,
                   bypassCount, dispatchPrioritySound>>

ConsumeWake(task) ==
    /\ current = task
    /\ taskState[task] = "Running"
    /\ wakeReason[task] # "None"
    /\ wakeReason' = [wakeReason EXCEPT ![task] = "None"]
    /\ UNCHANGED <<taskState, runCount, current, lockOwner, waiting,
                   bypassCount, dispatchPrioritySound>>

Teardown(task) ==
    /\ taskState[task] \notin {"Dormant", "Dead"}
    /\ UnsafeLeakyTeardown =>
            /\ taskState[task] = "Runnable"
            /\ current # task
            /\ lockOwner # task
            /\ ~waiting[task]
    /\ IF UnsafeLeakyTeardown
          THEN /\ taskState' = [taskState EXCEPT ![task] = "Dead"]
               /\ UNCHANGED <<runCount, current, lockOwner, waiting,
                               wakeReason, bypassCount>>
          ELSE /\ taskState' = [other \in Tasks |->
                       IF other = task
                          THEN "Dead"
                          ELSE IF lockOwner = task /\ waiting[other]
                                  THEN "Runnable"
                                  ELSE taskState[other]]
               /\ runCount' = [other \in Tasks |->
                       IF other = task
                          THEN 0
                          ELSE IF lockOwner = task /\ waiting[other]
                                  THEN 1
                                  ELSE runCount[other]]
               /\ current' = IF current = task THEN NoTask ELSE current
               /\ lockOwner' = IF lockOwner = task THEN NoTask ELSE lockOwner
               /\ waiting' = [other \in Tasks |->
                       IF other = task \/ (lockOwner = task /\ waiting[other])
                          THEN FALSE
                          ELSE waiting[other]]
               /\ wakeReason' = [other \in Tasks |->
                       IF other = task
                          THEN "None"
                          ELSE IF lockOwner = task /\ waiting[other]
                                  THEN "OwnerGone"
                                  ELSE wakeReason[other]]
               /\ bypassCount' = [other \in Tasks |->
                       IF other = task \/ (lockOwner = task /\ waiting[other])
                          THEN 0
                          ELSE bypassCount[other]]
    /\ UNCHANGED dispatchPrioritySound

Idle == UNCHANGED vars

Next ==
    \/ (\E task \in Tasks: Activate(task))
    \/ (\E task \in Tasks: Preempt(task))
    \/ (\E task \in Tasks: Dispatch(task))
    \/ (\E task \in Tasks: AcquireLock(task))
    \/ (\E task \in Tasks: BlockOnLock(task))
    \/ (\E task \in Tasks: CancelWait(task))
    \/ (\E task \in Tasks: TimeoutWait(task))
    \/ (\E task \in Tasks, waiter \in Tasks: ReleaseToWaiter(task, waiter))
    \/ (\E task \in Tasks: ReleaseUncontended(task))
    \/ (\E task \in Tasks: ConsumeWake(task))
    \/ (\E task \in Tasks: Teardown(task))
    \/ Idle

Spec == Init /\ [][Next]_vars

TerminalQuiescent ==
    \A task \in Tasks:
        taskState[task] = "Dead" =>
            /\ runCount[task] = 0
            /\ current # task
            /\ lockOwner # task
            /\ ~waiting[task]
            /\ wakeReason[task] = "None"
            /\ bypassCount[task] = 0

DormantQuiescent ==
    \A task \in Tasks:
        taskState[task] = "Dormant" =>
            /\ runCount[task] = 0
            /\ current # task
            /\ lockOwner # task
            /\ ~waiting[task]
            /\ wakeReason[task] = "None"
            /\ bypassCount[task] = 0

RunnableQueueConsistent ==
    \A task \in Tasks:
        (taskState[task] = "Runnable") <=> (runCount[task] > 0)

NoDuplicateRunnable ==
    \A task \in Tasks: runCount[task] <= 1

CurrentConsistent ==
    /\ current = NoTask => \A task \in Tasks: taskState[task] # "Running"
    /\ current \in Tasks =>
            /\ taskState[current] = "Running"
            /\ \A other \in Tasks \ {current}: taskState[other] # "Running"

WaitingConsistent ==
    \A task \in Tasks: waiting[task] <=> taskState[task] = "Blocked"

BlockedHasOwner ==
    \A task \in Tasks:
        taskState[task] = "Blocked" => lockOwner \in Tasks \ {task}

LockOwnerActive ==
    lockOwner = NoTask \/
        (lockOwner \in Tasks /\ taskState[lockOwner] \in {"Runnable", "Running"})

WakeDeliverySound ==
    \A task \in Tasks:
        wakeReason[task] # "None" =>
            /\ taskState[task] \in {"Runnable", "Running"}
            /\ ~waiting[task]

LockGrantConsistent ==
    \A task \in Tasks:
        wakeReason[task] = "LockGranted" => lockOwner = task

PriorityInheritanceSound ==
    \A task \in Tasks: EffectivePriority(task) = RequiredEffectivePriority(task)

DispatchPrioritySound == dispatchPrioritySound

BypassBound ==
    \A task \in Tasks: bypassCount[task] <= MaxBypass

BypassRelevant ==
    \A task \in Tasks:
        taskState[task] # "Runnable" => bypassCount[task] = 0

=============================================================================
