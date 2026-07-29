------------------------------- MODULE PooleIPC ------------------------------
EXTENDS FiniteSets, Naturals

CONSTANTS Principals, Endpoints, Calls, Tokens, Client, Server, Endpoint0,
          NoCall, NoToken, MaxQueue, MaxEpoch, UnsafeUnauthorizedCall,
          UnsafeTokenReuse, UnsafeStaleReply, UnsafeLeakyTeardown

CallStates == {"Fresh", "Queued", "InFlight", "Replied", "Cancelled",
               "TimedOut", "Aborted"}
TokenStates == {"Free", "Live", "Retired", "Used"}
TerminalStates == {"Replied", "Cancelled", "TimedOut", "Aborted"}

ASSUME /\ Cardinality(Principals) = 2
       /\ Cardinality(Endpoints) = 1
       /\ Cardinality(Calls) = 2
       /\ Cardinality(Tokens) = 2
       /\ Client \in Principals
       /\ Server \in Principals \ {Client}
       /\ Endpoint0 \in Endpoints
       /\ NoCall \notin Calls
       /\ NoToken \notin Tokens
       /\ MaxQueue = 1
       /\ MaxEpoch = 1
       /\ UnsafeUnauthorizedCall \in BOOLEAN
       /\ UnsafeTokenReuse \in BOOLEAN
       /\ UnsafeStaleReply \in BOOLEAN
       /\ UnsafeLeakyTeardown \in BOOLEAN
       /\ ~(UnsafeUnauthorizedCall /\ UnsafeTokenReuse)
       /\ ~(UnsafeUnauthorizedCall /\ UnsafeStaleReply)
       /\ ~(UnsafeUnauthorizedCall /\ UnsafeLeakyTeardown)
       /\ ~(UnsafeTokenReuse /\ UnsafeStaleReply)
       /\ ~(UnsafeTokenReuse /\ UnsafeLeakyTeardown)
       /\ ~(UnsafeStaleReply /\ UnsafeLeakyTeardown)

CanCall(principal, endpoint) == principal = Client /\ endpoint = Endpoint0

VARIABLES open, epoch, queue, status, caller, endpointOf, callEpoch,
          replyToken, tokenStatus, tokenCall, tokenEpoch, replyAccepted,
          replyFresh

vars == <<open, epoch, queue, status, caller, endpointOf, callEpoch,
          replyToken, tokenStatus, tokenCall, tokenEpoch, replyAccepted,
          replyFresh>>

TypeOK ==
    /\ open \subseteq Endpoints
    /\ epoch \in [Endpoints -> 0..MaxEpoch]
    /\ queue \in [Endpoints -> SUBSET Calls]
    /\ status \in [Calls -> CallStates]
    /\ caller \in [Calls -> Principals]
    /\ endpointOf \in [Calls -> Endpoints]
    /\ callEpoch \in [Calls -> 0..MaxEpoch]
    /\ replyToken \in [Calls -> Tokens \cup {NoToken}]
    /\ tokenStatus \in [Tokens -> TokenStates]
    /\ tokenCall \in [Tokens -> Calls \cup {NoCall}]
    /\ tokenEpoch \in [Tokens -> 0..MaxEpoch]
    /\ replyAccepted \subseteq Calls
    /\ replyFresh \in [Calls -> BOOLEAN]

Init ==
    /\ open = Endpoints
    /\ epoch = [endpoint \in Endpoints |-> 0]
    /\ queue = [endpoint \in Endpoints |-> {}]
    /\ status = [call \in Calls |-> "Fresh"]
    /\ caller = [call \in Calls |-> Client]
    /\ endpointOf = [call \in Calls |-> Endpoint0]
    /\ callEpoch = [call \in Calls |-> 0]
    /\ replyToken = [call \in Calls |-> NoToken]
    /\ tokenStatus = [token \in Tokens |-> "Free"]
    /\ tokenCall = [token \in Tokens |-> NoCall]
    /\ tokenEpoch = [token \in Tokens |-> 0]
    /\ replyAccepted = {}
    /\ replyFresh = [call \in Calls |-> TRUE]

Enqueue(principal, endpoint, call) ==
    /\ call \in Calls
    /\ principal \in Principals
    /\ endpoint \in open
    /\ status[call] = "Fresh"
    /\ Cardinality(queue[endpoint]) < MaxQueue
    /\ (CanCall(principal, endpoint) \/ UnsafeUnauthorizedCall)
    /\ queue' = [queue EXCEPT ![endpoint] = @ \cup {call}]
    /\ status' = [status EXCEPT ![call] = "Queued"]
    /\ caller' = [caller EXCEPT ![call] = principal]
    /\ endpointOf' = [endpointOf EXCEPT ![call] = endpoint]
    /\ callEpoch' = [callEpoch EXCEPT ![call] = epoch[endpoint]]
    /\ UNCHANGED <<open, epoch, replyToken, tokenStatus, tokenCall,
                   tokenEpoch, replyAccepted, replyFresh>>

Dispatch(endpoint, call, token) ==
    /\ endpoint \in open
    /\ call \in queue[endpoint]
    /\ status[call] = "Queued"
    /\ tokenStatus[token] = "Free"
    /\ queue' = [queue EXCEPT ![endpoint] = @ \ {call}]
    /\ status' = [status EXCEPT ![call] = "InFlight"]
    /\ replyToken' = [replyToken EXCEPT ![call] = token]
    /\ tokenStatus' = [tokenStatus EXCEPT ![token] = "Live"]
    /\ tokenCall' = [tokenCall EXCEPT ![token] = call]
    /\ tokenEpoch' = [tokenEpoch EXCEPT ![token] = callEpoch[call]]
    /\ UNCHANGED <<open, epoch, caller, endpointOf, callEpoch,
                   replyAccepted, replyFresh>>

Cancel(call) ==
    /\ status[call] \in {"Queued", "InFlight"}
    /\ queue' = [queue EXCEPT ![endpointOf[call]] = @ \ {call}]
    /\ status' = [status EXCEPT ![call] = "Cancelled"]
    /\ tokenStatus' =
        IF status[call] = "InFlight"
           THEN [tokenStatus EXCEPT ![replyToken[call]] = "Retired"]
           ELSE tokenStatus
    /\ UNCHANGED <<open, epoch, caller, endpointOf, callEpoch, replyToken,
                   tokenCall, tokenEpoch, replyAccepted, replyFresh>>

Timeout(call) ==
    /\ status[call] \in {"Queued", "InFlight"}
    /\ queue' = [queue EXCEPT ![endpointOf[call]] = @ \ {call}]
    /\ status' = [status EXCEPT ![call] = "TimedOut"]
    /\ tokenStatus' =
        IF status[call] = "InFlight"
           THEN [tokenStatus EXCEPT ![replyToken[call]] = "Retired"]
           ELSE tokenStatus
    /\ UNCHANGED <<open, epoch, caller, endpointOf, callEpoch, replyToken,
                   tokenCall, tokenEpoch, replyAccepted, replyFresh>>

Reply(token) ==
    /\ tokenCall[token] # NoCall
    /\ LET call == tokenCall[token]
           endpoint == endpointOf[call]
           fresh == /\ tokenStatus[token] = "Live"
                    /\ status[call] = "InFlight"
                    /\ endpoint \in open
                    /\ tokenEpoch[token] = callEpoch[call]
                    /\ callEpoch[call] = epoch[endpoint]
       IN /\ IF UnsafeStaleReply
                 THEN fresh \/
                      (tokenStatus[token] = "Retired" /\
                       status[call] \in {"Cancelled", "TimedOut", "Aborted"})
                 ELSE fresh
          /\ status' = [status EXCEPT ![call] = "Replied"]
          /\ tokenStatus' = [tokenStatus EXCEPT
                  ![token] = IF UnsafeTokenReuse /\ fresh THEN "Live" ELSE "Used"]
          /\ replyAccepted' = replyAccepted \cup {call}
          /\ replyFresh' = [replyFresh EXCEPT ![call] = fresh]
    /\ UNCHANGED <<open, epoch, queue, caller, endpointOf, callEpoch,
                   replyToken, tokenCall, tokenEpoch>>

Teardown(endpoint) ==
    /\ endpoint \in open
    /\ epoch[endpoint] < MaxEpoch
    /\ open' = open \ {endpoint}
    /\ epoch' = [epoch EXCEPT ![endpoint] = @ + 1]
    /\ IF UnsafeLeakyTeardown
          THEN UNCHANGED <<queue, status, tokenStatus>>
          ELSE /\ queue' = [queue EXCEPT ![endpoint] = {}]
               /\ status' = [call \in Calls |->
                       IF endpointOf[call] = endpoint /\
                          status[call] \in {"Queued", "InFlight"}
                          THEN "Aborted"
                          ELSE status[call]]
               /\ tokenStatus' = [token \in Tokens |->
                       IF tokenStatus[token] = "Live" /\
                          tokenCall[token] # NoCall /\
                          endpointOf[tokenCall[token]] = endpoint
                          THEN "Retired"
                          ELSE tokenStatus[token]]
    /\ UNCHANGED <<caller, endpointOf, callEpoch, replyToken, tokenCall,
                   tokenEpoch, replyAccepted, replyFresh>>

Reopen(endpoint) ==
    /\ endpoint \notin open
    /\ queue[endpoint] = {}
    /\ \A call \in Calls:
            endpointOf[call] = endpoint => status[call] \notin {"Queued", "InFlight"}
    /\ \A token \in Tokens:
            tokenStatus[token] = "Live" =>
                tokenCall[token] # NoCall /\ endpointOf[tokenCall[token]] # endpoint
    /\ open' = open \cup {endpoint}
    /\ UNCHANGED <<epoch, queue, status, caller, endpointOf, callEpoch,
                   replyToken, tokenStatus, tokenCall, tokenEpoch,
                   replyAccepted, replyFresh>>

Idle == UNCHANGED vars

Next ==
    \/ (\E principal \in Principals, endpoint \in Endpoints, call \in Calls:
            Enqueue(principal, endpoint, call))
    \/ (\E endpoint \in Endpoints, call \in Calls, token \in Tokens:
            Dispatch(endpoint, call, token))
    \/ (\E call \in Calls: Cancel(call))
    \/ (\E call \in Calls: Timeout(call))
    \/ (\E token \in Tokens: Reply(token))
    \/ (\E endpoint \in Endpoints: Teardown(endpoint))
    \/ (\E endpoint \in Endpoints: Reopen(endpoint))
    \/ Idle

Spec == Init /\ [][Next]_vars

QueueBound ==
    \A endpoint \in Endpoints: Cardinality(queue[endpoint]) <= MaxQueue

QueueStateConsistent ==
    \A endpoint \in Endpoints, call \in Calls:
        (call \in queue[endpoint]) <=>
            (status[call] = "Queued" /\ endpointOf[call] = endpoint)

QueuedCallAuthorized ==
    \A endpoint \in Endpoints:
        \A call \in queue[endpoint]:
            CanCall(caller[call], endpoint)

InFlightCallConsistent ==
    \A call \in Calls:
        status[call] = "InFlight" =>
            /\ replyToken[call] \in Tokens
            /\ tokenStatus[replyToken[call]] = "Live"
            /\ tokenCall[replyToken[call]] = call
            /\ endpointOf[call] \in open
            /\ tokenEpoch[replyToken[call]] = callEpoch[call]
            /\ callEpoch[call] = epoch[endpointOf[call]]

LiveTokenConsistent ==
    \A token \in Tokens:
        tokenStatus[token] = "Live" =>
            /\ tokenCall[token] \in Calls
            /\ status[tokenCall[token]] = "InFlight"
            /\ replyToken[tokenCall[token]] = token

TerminalCallHasNoLiveToken ==
    \A call \in Calls:
        status[call] \in TerminalStates =>
            replyToken[call] = NoToken \/ tokenStatus[replyToken[call]] # "Live"

TokenLifecycleConsistent ==
    \A token \in Tokens:
        /\ (tokenStatus[token] = "Free" => tokenCall[token] = NoCall)
        /\ (tokenStatus[token] = "Used" =>
                tokenCall[token] \in replyAccepted /\
                status[tokenCall[token]] = "Replied")
        /\ (tokenStatus[token] = "Retired" =>
                tokenCall[token] \in Calls /\
                status[tokenCall[token]] \in {"Cancelled", "TimedOut", "Aborted"})

AcceptedRepliesFresh ==
    \A call \in replyAccepted:
        status[call] = "Replied" /\ replyFresh[call]

ClosedEndpointQuiescent ==
    \A endpoint \in Endpoints:
        endpoint \notin open =>
            /\ queue[endpoint] = {}
            /\ \A call \in Calls:
                    endpointOf[call] = endpoint =>
                        status[call] \notin {"Queued", "InFlight"}
            /\ \A token \in Tokens:
                    tokenStatus[token] = "Live" /\ tokenCall[token] # NoCall =>
                        endpointOf[tokenCall[token]] # endpoint

LiveTokenInjective ==
    \A left \in Tokens, right \in Tokens:
        left # right /\ tokenStatus[left] = "Live" /\ tokenStatus[right] = "Live" =>
            tokenCall[left] # tokenCall[right]

=============================================================================
