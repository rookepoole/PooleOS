# Bounded Early Serial Delivery

Contract: PSERIAL1. Scope: PooleKernel's exclusive early COM1 writer, not a
general-purpose asynchronous serial driver or application device grant.

## State And Authority

The existing bounded loopback probe establishes presence. A pure transmitter
owns a1024-byte FIFO; the x86 adapter retains only the same fixed UART registers.
No heap allocation, shared producer, interrupt handler or new capability exists.
`available` means the probe succeeded, not that later writes are guaranteed.

A healthy byte costs one LSR read and one write. Each drain is limited to4096
total LSR reads, including reads for successfully sent backlog bytes. A failed
drain retains every unsent byte in order. Backlogged non-newline appends do not
poll again. Newline and the interval between user dispatches each allow a bounded
drain; no delay, deadline or loop allowance is enlarged. THRE authorizes a write;
`0xff` is treated as unavailable bus state, not readiness. TEMT is not required.

Once capacity is exceeded, saturation is sticky and every subsequent byte is
rejected. The already accepted prefix may drain; appending after a lost byte is
forbidden, preventing a syntactically plausible diagnostic stream across a gap.
The adapter emits one independent debugcon loss marker. Pending, transmitted,
timeout and rejection accounting is explicit, with saturating counters. COM1
loss on a host without debugcon remains distinguishable only through incomplete
COM1 evidence and other available diagnostics. Missing required records cannot
be treated as a pass. A valid earlier prefix does not prove later delivery or
exclude saturation after the qualified observation window.

The logger's existing CRLF conversion remains outside the transmitter. The early
ring remains a separate overwrite-oriented crash history, not a transmit queue.
Emergency paths construct a fresh bounded writer; they cannot guarantee delivery
of a previous owner's retained tail. A halted kernel cannot promise future retries.
Neither these paths nor permanent/disconnected hardware have a lossless guarantee.

## Verification Boundary

The old permanent-disable policy has a retained failing counterexample. Host
tests cover absent devices, last allowed poll, repeated stalls, byte ordering,
FIFO wrap, saturation, floating bus, total drain budget and saturating counters.

`development-serial-recovery` is an explicit diagnostic profile tied to isolated
application input. At dispatch64 it withholds4096 LSR ready observations before
the ordinary RUN record. The record must arrive exactly, followed by an explicit
observation of one timeout, zero pending/rejected bytes and its exact CRLF length.
The diagnostic oracle validates that observation before passing all other markers
unchanged to the ordinary application oracle. Missing, duplicate, reordered,
failed or length-mismatched challenges reject. Ordinary oracles reject the extra
observation, so this image is never selected as the everyday preview.

Actual qualification results and remaining work are recorded in
[Cycle302](checkpoints/cycle302-bounded-serial.md). A controlled stall establishes
the implemented mechanism, not the historical cause of Cycle301's VirtualBox
interruption. All-path stack bounds, interrupt-driven production logging,
permanent-device failure handling and physical UART qualification remain open.
No complete desktop, persistent editing, production ISO, signing or release claim
follows from PSERIAL1.
