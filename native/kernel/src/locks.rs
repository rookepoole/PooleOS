//! Allocation-free PKLOCK1 synchronization primitives and diagnostics.

use core::hint::spin_loop;

use crate::atomics::{AtomicU32, AtomicU64, CompareExchangeOrder, LoadOrder, RmwOrder, StoreOrder};

pub const CONTRACT_ID: &str = "PKLOCK1";
pub const SELECTED_MOVE_ID: &str = "N12-CONCURRENCY-LOCKS-001";
pub const MAX_OUTSTANDING_TICKETS: u32 = 32;
pub const MAX_HELD_LOCKS: usize = 8;
pub const MAX_MUTEX_WAITERS: usize = 8;
pub const MAX_NOTIFICATION_WAITERS: usize = 8;
pub const MAX_MUTEX_BYPASS: u8 = 7;
pub const LIVE_PROBE_PAGE_TABLE_INDEX: usize = 510;
pub const LIVE_PROBE_VIRTUAL_ADDRESS: u64 = 0x001f_e000;
pub const LIVE_PROBE_MODE_MAGIC: u32 = 0x504b_4c31;
pub const LIVE_NEXT_OFFSET: usize = 0;
pub const LIVE_SERVING_OFFSET: usize = 4;
pub const LIVE_OWNER_OFFSET: usize = 8;
pub const LIVE_ACQUISITIONS_OFFSET: usize = 12;
pub const LIVE_CPU_MASK_OFFSET: usize = 16;
pub const LIVE_TICKET_BASE_OFFSET: usize = 32;
const WRITER_BIT: u32 = 1 << 31;
const READER_MASK: u32 = 0x0000_ffff;
const WAITING_WRITER_MASK: u32 = 0x7fff_0000;
const WAITING_WRITER_ONE: u32 = 1 << 16;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    OwnerToken,
    OwnerRange,
    Recursive,
    Busy,
    Timeout,
    QueueFull,
    QueueMissing,
    DuplicateWaiter,
    NotOwner,
    Rank,
    RankOrder,
    RankCycle,
    HeldCapacity,
    InterruptContext,
    PreemptionContext,
    SleepForbidden,
    Priority,
    Deadline,
    Handoff,
    Counter,
    Sequence,
    Invariant,
}

impl Error {
    pub const fn label(self) -> &'static str {
        match self {
            Self::OwnerToken => "owner_token",
            Self::OwnerRange => "owner_range",
            Self::Recursive => "recursive",
            Self::Busy => "busy",
            Self::Timeout => "timeout",
            Self::QueueFull => "queue_full",
            Self::QueueMissing => "queue_missing",
            Self::DuplicateWaiter => "duplicate_waiter",
            Self::NotOwner => "not_owner",
            Self::Rank => "rank",
            Self::RankOrder => "rank_order",
            Self::RankCycle => "rank_cycle",
            Self::HeldCapacity => "held_capacity",
            Self::InterruptContext => "interrupt_context",
            Self::PreemptionContext => "preemption_context",
            Self::SleepForbidden => "sleep_forbidden",
            Self::Priority => "priority",
            Self::Deadline => "deadline",
            Self::Handoff => "handoff",
            Self::Counter => "counter",
            Self::Sequence => "sequence",
            Self::Invariant => "invariant",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum LockRank {
    Irq = 1,
    RunQueue = 2,
    Mutex = 3,
    ReaderWriter = 4,
    Sequence = 5,
}

impl LockRank {
    const fn index(self) -> usize {
        self as usize - 1
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LockContext {
    pub owner: u32,
    pub interrupt_depth: u8,
    pub preemption_depth: u8,
    pub interrupts_enabled: bool,
    pub can_sleep: bool,
    held: [u8; MAX_HELD_LOCKS],
    held_count: usize,
}

impl LockContext {
    pub const fn task(owner: u32) -> Result<Self, Error> {
        if owner == 0 {
            return Err(Error::OwnerToken);
        }
        Ok(Self {
            owner,
            interrupt_depth: 0,
            preemption_depth: 0,
            interrupts_enabled: true,
            can_sleep: true,
            held: [0; MAX_HELD_LOCKS],
            held_count: 0,
        })
    }

    pub const fn interrupt(owner: u32, depth: u8) -> Result<Self, Error> {
        if owner == 0 {
            return Err(Error::OwnerToken);
        }
        if depth == 0 {
            return Err(Error::InterruptContext);
        }
        Ok(Self {
            owner,
            interrupt_depth: depth,
            preemption_depth: 1,
            interrupts_enabled: false,
            can_sleep: false,
            held: [0; MAX_HELD_LOCKS],
            held_count: 0,
        })
    }

    pub const fn held_count(&self) -> usize {
        self.held_count
    }

    pub fn authorize(&self, rank: LockRank) -> Result<(), Error> {
        if self.owner == 0 {
            return Err(Error::OwnerToken);
        }
        if self.held_count == MAX_HELD_LOCKS {
            return Err(Error::HeldCapacity);
        }
        if self.held[..self.held_count].contains(&(rank as u8)) {
            return Err(Error::Recursive);
        }
        if let Some(last) = self.held[..self.held_count].last()
            && *last >= rank as u8
        {
            return Err(Error::RankOrder);
        }
        Ok(())
    }

    fn acquired(&mut self, rank: LockRank) -> Result<(), Error> {
        self.authorize(rank)?;
        self.held[self.held_count] = rank as u8;
        self.held_count += 1;
        Ok(())
    }

    fn released(&mut self, rank: LockRank) -> Result<(), Error> {
        if self.held_count == 0 || self.held[self.held_count - 1] != rank as u8 {
            return Err(Error::RankOrder);
        }
        self.held_count -= 1;
        self.held[self.held_count] = 0;
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LockOrderGraph {
    edges: [u8; 5],
    pub recorded_edges: u32,
    pub rejected_cycles: u32,
}

impl LockOrderGraph {
    pub const fn new() -> Self {
        Self {
            edges: [0; 5],
            recorded_edges: 0,
            rejected_cycles: 0,
        }
    }

    pub fn record_dependency(&mut self, from: LockRank, to: LockRank) -> Result<(), Error> {
        if from == to {
            self.rejected_cycles = increment(self.rejected_cycles)?;
            return Err(Error::RankCycle);
        }
        if self.path_exists(to.index(), from.index()) {
            self.rejected_cycles = increment(self.rejected_cycles)?;
            return Err(Error::RankCycle);
        }
        let bit = 1u8 << to.index();
        if self.edges[from.index()] & bit == 0 {
            self.edges[from.index()] |= bit;
            self.recorded_edges = increment(self.recorded_edges)?;
        }
        Ok(())
    }

    pub fn record_acquire(&mut self, context: &LockContext, rank: LockRank) -> Result<(), Error> {
        context.authorize(rank)?;
        let before = *self;
        for held in context.held[..context.held_count].iter().copied() {
            let held = rank_from_u8(held)?;
            if let Err(error) = self.record_dependency(held, rank) {
                *self = before;
                return Err(error);
            }
        }
        Ok(())
    }

    pub fn edge(&self, from: LockRank, to: LockRank) -> bool {
        self.edges[from.index()] & (1u8 << to.index()) != 0
    }

    fn path_exists(&self, from: usize, to: usize) -> bool {
        let mut pending = 1u8 << from;
        let mut visited = 0u8;
        while pending != 0 {
            let node = pending.trailing_zeros() as usize;
            let bit = 1u8 << node;
            pending &= !bit;
            if node == to {
                return true;
            }
            if visited & bit == 0 {
                visited |= bit;
                pending |= self.edges[node] & !visited;
            }
        }
        false
    }
}

impl Default for LockOrderGraph {
    fn default() -> Self {
        Self::new()
    }
}

fn rank_from_u8(value: u8) -> Result<LockRank, Error> {
    match value {
        1 => Ok(LockRank::Irq),
        2 => Ok(LockRank::RunQueue),
        3 => Ok(LockRank::Mutex),
        4 => Ok(LockRank::ReaderWriter),
        5 => Ok(LockRank::Sequence),
        _ => Err(Error::Rank),
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TicketPermit {
    pub owner: u32,
    pub ticket: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TicketSnapshot {
    pub next: u32,
    pub serving: u32,
    pub owner: u32,
    pub cancelled: u32,
    pub acquisitions: u32,
    pub contentions: u32,
    pub timeouts: u32,
}

pub struct TicketSpinLock {
    next: AtomicU32,
    serving: AtomicU32,
    owner: AtomicU32,
    cancelled: AtomicU32,
    acquisitions: AtomicU32,
    contentions: AtomicU32,
    timeouts: AtomicU32,
}

impl TicketSpinLock {
    pub const fn new() -> Self {
        Self {
            next: AtomicU32::new(0),
            serving: AtomicU32::new(0),
            owner: AtomicU32::new(0),
            cancelled: AtomicU32::new(0),
            acquisitions: AtomicU32::new(0),
            contentions: AtomicU32::new(0),
            timeouts: AtomicU32::new(0),
        }
    }

    pub fn try_lock(&self, owner: u32) -> Result<TicketPermit, Error> {
        self.validate_owner(owner)?;
        let serving = self.serving.load(LoadOrder::Acquire);
        let next = self.next.load(LoadOrder::Acquire);
        if next != serving {
            return Err(Error::Busy);
        }
        self.next
            .compare_exchange(next, next.wrapping_add(1), CompareExchangeOrder::ACQ_REL)
            .map_err(|_| Error::Busy)?;
        self.claim(owner, serving)
    }

    pub fn lock(&self, owner: u32) -> Result<TicketPermit, Error> {
        self.validate_owner(owner)?;
        let ticket = self.reserve_ticket()?;
        loop {
            if self.serving.load(LoadOrder::Acquire) == ticket {
                return self.claim(owner, ticket);
            }
            self.contentions.fetch_add(1, RmwOrder::Relaxed);
            spin_loop();
        }
    }

    pub fn lock_bounded(&self, owner: u32, attempts: u32) -> Result<TicketPermit, Error> {
        self.validate_owner(owner)?;
        if attempts == 0 {
            return Err(Error::Deadline);
        }
        let ticket = self.reserve_ticket()?;
        for _ in 0..attempts {
            if self.serving.load(LoadOrder::Acquire) == ticket {
                return self.claim(owner, ticket);
            }
            self.contentions.fetch_add(1, RmwOrder::Relaxed);
            spin_loop();
        }
        if self.serving.load(LoadOrder::Acquire) == ticket {
            return self.claim(owner, ticket);
        }
        self.cancel(ticket)?;
        self.timeouts.fetch_add(1, RmwOrder::Relaxed);
        Err(Error::Timeout)
    }

    pub fn unlock(&self, permit: TicketPermit) -> Result<(), Error> {
        if permit.owner == 0 {
            return Err(Error::OwnerToken);
        }
        if self.serving.load(LoadOrder::Acquire) != permit.ticket {
            return Err(Error::NotOwner);
        }
        self.owner
            .compare_exchange(permit.owner, 0, CompareExchangeOrder::RELEASE)
            .map_err(|_| Error::NotOwner)?;
        self.serving.fetch_add(1, RmwOrder::Release);
        self.advance_cancelled();
        Ok(())
    }

    pub fn snapshot(&self) -> TicketSnapshot {
        TicketSnapshot {
            next: self.next.load(LoadOrder::Acquire),
            serving: self.serving.load(LoadOrder::Acquire),
            owner: self.owner.load(LoadOrder::Acquire),
            cancelled: self.cancelled.load(LoadOrder::Acquire),
            acquisitions: self.acquisitions.load(LoadOrder::Acquire),
            contentions: self.contentions.load(LoadOrder::Acquire),
            timeouts: self.timeouts.load(LoadOrder::Acquire),
        }
    }

    fn validate_owner(&self, owner: u32) -> Result<(), Error> {
        if owner == 0 {
            return Err(Error::OwnerToken);
        }
        if self.owner.load(LoadOrder::Acquire) == owner {
            return Err(Error::Recursive);
        }
        Ok(())
    }

    fn reserve_ticket(&self) -> Result<u32, Error> {
        loop {
            let next = self.next.load(LoadOrder::Acquire);
            let serving = self.serving.load(LoadOrder::Acquire);
            if next.wrapping_sub(serving) >= MAX_OUTSTANDING_TICKETS {
                // Other owners can advance both counters between the loads.
                if self.next.load(LoadOrder::Acquire) != next {
                    spin_loop();
                    continue;
                }
                return Err(Error::QueueFull);
            }
            match self.next.compare_exchange_weak(
                next,
                next.wrapping_add(1),
                CompareExchangeOrder::ACQ_REL,
            ) {
                Ok(_) => return Ok(next),
                Err(_) => spin_loop(),
            }
        }
    }

    fn claim(&self, owner: u32, ticket: u32) -> Result<TicketPermit, Error> {
        self.owner
            .compare_exchange(0, owner, CompareExchangeOrder::ACQUIRE)
            .map_err(|_| Error::Invariant)?;
        self.acquisitions.fetch_add(1, RmwOrder::Relaxed);
        Ok(TicketPermit { owner, ticket })
    }

    fn cancel(&self, ticket: u32) -> Result<(), Error> {
        let serving = self.serving.load(LoadOrder::Acquire);
        if ticket.wrapping_sub(serving) >= MAX_OUTSTANDING_TICKETS {
            return Err(Error::Invariant);
        }
        self.cancelled
            .fetch_or(1u32 << (ticket & 31), RmwOrder::AcqRel);
        self.advance_cancelled();
        Ok(())
    }

    fn advance_cancelled(&self) {
        loop {
            if self.owner.load(LoadOrder::Acquire) != 0 {
                return;
            }
            let serving = self.serving.load(LoadOrder::Acquire);
            let bit = 1u32 << (serving & 31);
            if self.cancelled.load(LoadOrder::Acquire) & bit == 0 {
                return;
            }
            let cancelled = self.cancelled.load(LoadOrder::Acquire);
            if self
                .cancelled
                .compare_exchange(cancelled, cancelled & !bit, CompareExchangeOrder::ACQ_REL)
                .is_err()
            {
                continue;
            }
            let _ = self.serving.compare_exchange(
                serving,
                serving.wrapping_add(1),
                CompareExchangeOrder::ACQ_REL,
            );
        }
    }
}

impl Default for TicketSpinLock {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct IrqGuard {
    permit: TicketPermit,
    owner: u32,
    rank: LockRank,
    lock_address: usize,
    restore_interrupts: bool,
    restore_preemption_depth: u8,
}

pub struct IrqSaveSpinLock {
    inner: TicketSpinLock,
    rank: LockRank,
}

impl IrqSaveSpinLock {
    pub const fn new(rank: LockRank) -> Self {
        Self {
            inner: TicketSpinLock::new(),
            rank,
        }
    }

    pub fn lock_bounded(
        &self,
        context: &mut LockContext,
        graph: &mut LockOrderGraph,
        attempts: u32,
    ) -> Result<IrqGuard, Error> {
        if context.interrupt_depth != 0 {
            return Err(Error::InterruptContext);
        }
        if context.preemption_depth != 0 {
            return Err(Error::PreemptionContext);
        }
        let before = *context;
        let graph_before = *graph;
        context.authorize(self.rank)?;
        graph.record_acquire(context, self.rank)?;
        context.interrupts_enabled = false;
        context.preemption_depth = 1;
        let permit = match self.inner.lock_bounded(context.owner, attempts) {
            Ok(value) => value,
            Err(error) => {
                *context = before;
                *graph = graph_before;
                return Err(error);
            }
        };
        if let Err(error) = context.acquired(self.rank) {
            let _ = self.inner.unlock(permit);
            *context = before;
            *graph = graph_before;
            return Err(error);
        }
        Ok(IrqGuard {
            permit,
            owner: context.owner,
            rank: self.rank,
            lock_address: self as *const Self as usize,
            restore_interrupts: before.interrupts_enabled,
            restore_preemption_depth: before.preemption_depth,
        })
    }

    pub fn unlock(&self, context: &mut LockContext, guard: IrqGuard) -> Result<(), Error> {
        if context.owner != guard.owner
            || self.rank != guard.rank
            || guard.lock_address != self as *const Self as usize
        {
            return Err(Error::NotOwner);
        }
        let before = *context;
        context.released(self.rank)?;
        if let Err(error) = self.inner.unlock(guard.permit) {
            *context = before;
            return Err(error);
        }
        context.preemption_depth = guard.restore_preemption_depth;
        context.interrupts_enabled = guard.restore_interrupts;
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct MutexWaiter {
    owner: u32,
    priority: u8,
    ticket: u32,
    deadline: u64,
    bypass: u8,
}

const EMPTY_MUTEX_WAITER: MutexWaiter = MutexWaiter {
    owner: 0,
    priority: 0,
    ticket: 0,
    deadline: 0,
    bypass: 0,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MutexAcquire {
    Acquired,
    Blocked { ticket: u32, donate_priority: u8 },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WakeReason {
    Granted,
    TimedOut,
    Cancelled,
    OwnerDead,
    Notified,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Wake {
    pub owner: u32,
    pub ticket: u32,
    pub reason: WakeReason,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MutexSnapshot {
    pub owner: u32,
    pub owner_base_priority: u8,
    pub owner_effective_priority: u8,
    pub waiter_count: u8,
    pub next_ticket: u32,
    pub handoffs: u32,
    pub owner_deaths: u32,
    pub maximum_bypass: u8,
}

#[derive(Clone, Copy)]
pub struct SleepMutex {
    rank: LockRank,
    owner: u32,
    owner_base_priority: u8,
    owner_effective_priority: u8,
    waiters: [MutexWaiter; MAX_MUTEX_WAITERS],
    waiter_count: usize,
    next_ticket: u32,
    handoff_pending: bool,
    handoffs: u32,
    owner_deaths: u32,
    maximum_bypass: u8,
}

impl SleepMutex {
    pub const fn new(rank: LockRank) -> Self {
        Self {
            rank,
            owner: 0,
            owner_base_priority: 0,
            owner_effective_priority: 0,
            waiters: [EMPTY_MUTEX_WAITER; MAX_MUTEX_WAITERS],
            waiter_count: 0,
            next_ticket: 1,
            handoff_pending: false,
            handoffs: 0,
            owner_deaths: 0,
            maximum_bypass: 0,
        }
    }

    pub fn try_lock(
        &mut self,
        context: &mut LockContext,
        graph: &mut LockOrderGraph,
        priority: u8,
    ) -> Result<(), Error> {
        validate_sleep_context(context, priority)?;
        context.authorize(self.rank)?;
        if self.owner == context.owner {
            return Err(Error::Recursive);
        }
        if self.owner != 0 {
            return Err(Error::Busy);
        }
        graph.record_acquire(context, self.rank)?;
        context.acquired(self.rank)?;
        self.owner = context.owner;
        self.owner_base_priority = priority;
        self.owner_effective_priority = priority;
        self.handoff_pending = false;
        Ok(())
    }

    pub fn lock_or_enqueue(
        &mut self,
        context: &mut LockContext,
        graph: &mut LockOrderGraph,
        priority: u8,
        deadline: u64,
        now: u64,
    ) -> Result<MutexAcquire, Error> {
        validate_sleep_context(context, priority)?;
        context.authorize(self.rank)?;
        if deadline <= now {
            return Err(Error::Deadline);
        }
        if self.owner == 0 {
            self.try_lock(context, graph, priority)?;
            return Ok(MutexAcquire::Acquired);
        }
        if self.owner == context.owner {
            return Err(Error::Recursive);
        }
        if self.waiters[..self.waiter_count]
            .iter()
            .any(|waiter| waiter.owner == context.owner)
        {
            return Err(Error::DuplicateWaiter);
        }
        if self.waiter_count == MAX_MUTEX_WAITERS {
            return Err(Error::QueueFull);
        }
        let ticket = self.next_ticket;
        self.next_ticket = self.next_ticket.checked_add(1).ok_or(Error::Counter)?;
        self.waiters[self.waiter_count] = MutexWaiter {
            owner: context.owner,
            priority,
            ticket,
            deadline,
            bypass: 0,
        };
        self.waiter_count += 1;
        self.owner_effective_priority = self.owner_effective_priority.max(priority);
        Ok(MutexAcquire::Blocked {
            ticket,
            donate_priority: self.owner_effective_priority,
        })
    }

    pub fn unlock(&mut self, context: &mut LockContext) -> Result<Option<Wake>, Error> {
        if self.owner != context.owner || self.handoff_pending {
            return Err(Error::NotOwner);
        }
        let next_handoffs = if self.waiter_count == 0 {
            self.handoffs
        } else {
            increment(self.handoffs)?
        };
        context.released(self.rank)?;
        if self.waiter_count == 0 {
            self.clear_owner();
            return Ok(None);
        }
        let selected = self.select_waiter()?;
        let waiter = self.remove_waiter(selected)?;
        self.owner = waiter.owner;
        self.owner_base_priority = waiter.priority;
        self.owner_effective_priority = waiter.priority;
        self.handoff_pending = true;
        self.handoffs = next_handoffs;
        self.recompute_donation();
        Ok(Some(Wake {
            owner: waiter.owner,
            ticket: waiter.ticket,
            reason: WakeReason::Granted,
        }))
    }

    pub fn claim_handoff(
        &mut self,
        context: &mut LockContext,
        graph: &mut LockOrderGraph,
        wake: Wake,
    ) -> Result<(), Error> {
        if wake.reason != WakeReason::Granted
            || !self.handoff_pending
            || self.owner != context.owner
            || wake.owner != context.owner
        {
            return Err(Error::Handoff);
        }
        graph.record_acquire(context, self.rank)?;
        context.acquired(self.rank)?;
        self.handoff_pending = false;
        Ok(())
    }

    pub fn timeout(&mut self, owner: u32, now: u64) -> Result<Wake, Error> {
        let index = self.waiter_index(owner)?;
        let waiter = self.waiters[index];
        if waiter.deadline > now {
            return Err(Error::Deadline);
        }
        let waiter = self.remove_waiter(index)?;
        self.recompute_donation();
        Ok(Wake {
            owner: waiter.owner,
            ticket: waiter.ticket,
            reason: WakeReason::TimedOut,
        })
    }

    pub fn cancel(&mut self, owner: u32) -> Result<Wake, Error> {
        let waiter = self.remove_waiter(self.waiter_index(owner)?)?;
        self.recompute_donation();
        Ok(Wake {
            owner: waiter.owner,
            ticket: waiter.ticket,
            reason: WakeReason::Cancelled,
        })
    }

    pub fn owner_died(
        &mut self,
        owner: u32,
    ) -> Result<([Option<Wake>; MAX_MUTEX_WAITERS], u8), Error> {
        if owner == 0 || self.owner != owner {
            return Err(Error::NotOwner);
        }
        let next_owner_deaths = increment(self.owner_deaths)?;
        let mut wakes = [None; MAX_MUTEX_WAITERS];
        let count = self.waiter_count;
        for slot in wakes.iter_mut().take(count) {
            let waiter = self.remove_waiter(0)?;
            *slot = Some(Wake {
                owner: waiter.owner,
                ticket: waiter.ticket,
                reason: WakeReason::OwnerDead,
            });
        }
        self.clear_owner();
        self.owner_deaths = next_owner_deaths;
        Ok((wakes, count as u8))
    }

    pub const fn snapshot(&self) -> MutexSnapshot {
        MutexSnapshot {
            owner: self.owner,
            owner_base_priority: self.owner_base_priority,
            owner_effective_priority: self.owner_effective_priority,
            waiter_count: self.waiter_count as u8,
            next_ticket: self.next_ticket,
            handoffs: self.handoffs,
            owner_deaths: self.owner_deaths,
            maximum_bypass: self.maximum_bypass,
        }
    }

    fn select_waiter(&mut self) -> Result<usize, Error> {
        let starved = self.waiters[..self.waiter_count]
            .iter()
            .enumerate()
            .filter(|(_, waiter)| waiter.bypass >= MAX_MUTEX_BYPASS)
            .min_by_key(|(_, waiter)| waiter.ticket)
            .map(|(index, _)| index);
        let selected = starved.unwrap_or_else(|| {
            self.waiters[..self.waiter_count]
                .iter()
                .enumerate()
                .max_by_key(|(_, waiter)| (waiter.priority, core::cmp::Reverse(waiter.ticket)))
                .map(|(index, _)| index)
                .unwrap_or(0)
        });
        for (index, waiter) in self.waiters[..self.waiter_count].iter_mut().enumerate() {
            if index != selected {
                waiter.bypass = waiter.bypass.saturating_add(1).min(MAX_MUTEX_BYPASS);
                self.maximum_bypass = self.maximum_bypass.max(waiter.bypass);
            }
        }
        Ok(selected)
    }

    fn waiter_index(&self, owner: u32) -> Result<usize, Error> {
        if owner == 0 {
            return Err(Error::OwnerToken);
        }
        self.waiters[..self.waiter_count]
            .iter()
            .position(|waiter| waiter.owner == owner)
            .ok_or(Error::QueueMissing)
    }

    fn remove_waiter(&mut self, index: usize) -> Result<MutexWaiter, Error> {
        if index >= self.waiter_count {
            return Err(Error::QueueMissing);
        }
        let waiter = self.waiters[index];
        for cursor in index + 1..self.waiter_count {
            self.waiters[cursor - 1] = self.waiters[cursor];
        }
        self.waiter_count -= 1;
        self.waiters[self.waiter_count] = EMPTY_MUTEX_WAITER;
        Ok(waiter)
    }

    fn recompute_donation(&mut self) {
        self.owner_effective_priority = self.owner_base_priority;
        for waiter in &self.waiters[..self.waiter_count] {
            self.owner_effective_priority = self.owner_effective_priority.max(waiter.priority);
        }
    }

    fn clear_owner(&mut self) {
        self.owner = 0;
        self.owner_base_priority = 0;
        self.owner_effective_priority = 0;
        self.handoff_pending = false;
    }
}

fn validate_sleep_context(context: &LockContext, priority: u8) -> Result<(), Error> {
    if context.interrupt_depth != 0 {
        return Err(Error::InterruptContext);
    }
    if context.preemption_depth != 0 {
        return Err(Error::PreemptionContext);
    }
    if !context.can_sleep {
        return Err(Error::SleepForbidden);
    }
    if !(1..=31).contains(&priority) {
        return Err(Error::Priority);
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct NotificationWaiter {
    owner: u32,
    ticket: u32,
    deadline: u64,
}

const EMPTY_NOTIFICATION_WAITER: NotificationWaiter = NotificationWaiter {
    owner: 0,
    ticket: 0,
    deadline: 0,
};

#[derive(Clone, Copy)]
pub struct Notification {
    waiters: [NotificationWaiter; MAX_NOTIFICATION_WAITERS],
    count: usize,
    next_ticket: u32,
    sequence: u64,
}

impl Notification {
    pub const fn new() -> Self {
        Self {
            waiters: [EMPTY_NOTIFICATION_WAITER; MAX_NOTIFICATION_WAITERS],
            count: 0,
            next_ticket: 1,
            sequence: 0,
        }
    }

    pub fn wait(&mut self, context: &LockContext, deadline: u64, now: u64) -> Result<u32, Error> {
        validate_sleep_context(context, 1)?;
        if deadline <= now {
            return Err(Error::Deadline);
        }
        if self.count == MAX_NOTIFICATION_WAITERS {
            return Err(Error::QueueFull);
        }
        if self.waiters[..self.count]
            .iter()
            .any(|waiter| waiter.owner == context.owner)
        {
            return Err(Error::DuplicateWaiter);
        }
        let ticket = self.next_ticket;
        self.next_ticket = self.next_ticket.checked_add(1).ok_or(Error::Counter)?;
        self.waiters[self.count] = NotificationWaiter {
            owner: context.owner,
            ticket,
            deadline,
        };
        self.count += 1;
        Ok(ticket)
    }

    pub fn notify_one(&mut self) -> Result<Wake, Error> {
        let waiter = self.remove(0)?;
        self.sequence = self.sequence.checked_add(1).ok_or(Error::Counter)?;
        Ok(Wake {
            owner: waiter.owner,
            ticket: waiter.ticket,
            reason: WakeReason::Notified,
        })
    }

    pub fn notify_all(&mut self) -> Result<([Option<Wake>; MAX_NOTIFICATION_WAITERS], u8), Error> {
        let mut wakes = [None; MAX_NOTIFICATION_WAITERS];
        let count = self.count;
        for slot in wakes.iter_mut().take(count) {
            *slot = Some(self.notify_one()?);
        }
        Ok((wakes, count as u8))
    }

    pub fn timeout(&mut self, owner: u32, now: u64) -> Result<Wake, Error> {
        let index = self.index(owner)?;
        if self.waiters[index].deadline > now {
            return Err(Error::Deadline);
        }
        let waiter = self.remove(index)?;
        Ok(Wake {
            owner: waiter.owner,
            ticket: waiter.ticket,
            reason: WakeReason::TimedOut,
        })
    }

    pub fn cancel(&mut self, owner: u32) -> Result<Wake, Error> {
        let waiter = self.remove(self.index(owner)?)?;
        Ok(Wake {
            owner: waiter.owner,
            ticket: waiter.ticket,
            reason: WakeReason::Cancelled,
        })
    }

    pub const fn waiter_count(&self) -> usize {
        self.count
    }

    pub const fn sequence(&self) -> u64 {
        self.sequence
    }

    fn index(&self, owner: u32) -> Result<usize, Error> {
        self.waiters[..self.count]
            .iter()
            .position(|waiter| waiter.owner == owner)
            .ok_or(Error::QueueMissing)
    }

    fn remove(&mut self, index: usize) -> Result<NotificationWaiter, Error> {
        if index >= self.count {
            return Err(Error::QueueMissing);
        }
        let waiter = self.waiters[index];
        for cursor in index + 1..self.count {
            self.waiters[cursor - 1] = self.waiters[cursor];
        }
        self.count -= 1;
        self.waiters[self.count] = EMPTY_NOTIFICATION_WAITER;
        Ok(waiter)
    }
}

impl Default for Notification {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RwPermit {
    pub owner: u32,
    pub ticket: u32,
    pub write: bool,
}

pub struct ReaderWriterLock {
    state: AtomicU32,
    reader_owners: AtomicU32,
    writer_owner: AtomicU32,
    writer_next: AtomicU32,
    writer_serving: AtomicU32,
    cancelled_writers: AtomicU32,
    reader_contentions: AtomicU32,
    writer_contentions: AtomicU32,
    writer_timeouts: AtomicU32,
}

impl ReaderWriterLock {
    pub const fn new() -> Self {
        Self {
            state: AtomicU32::new(0),
            reader_owners: AtomicU32::new(0),
            writer_owner: AtomicU32::new(0),
            writer_next: AtomicU32::new(0),
            writer_serving: AtomicU32::new(0),
            cancelled_writers: AtomicU32::new(0),
            reader_contentions: AtomicU32::new(0),
            writer_contentions: AtomicU32::new(0),
            writer_timeouts: AtomicU32::new(0),
        }
    }

    pub fn try_read(&self, owner: u32) -> Result<RwPermit, Error> {
        let bit = owner_bit(owner)?;
        if self.reader_owners.load(LoadOrder::Acquire) & bit != 0
            || self.writer_owner.load(LoadOrder::Acquire) == owner
        {
            return Err(Error::Recursive);
        }
        loop {
            let state = self.state.load(LoadOrder::Acquire);
            if state & (WRITER_BIT | WAITING_WRITER_MASK) != 0 {
                return Err(Error::Busy);
            }
            if state & READER_MASK == READER_MASK {
                return Err(Error::Counter);
            }
            if self
                .state
                .compare_exchange_weak(state, state + 1, CompareExchangeOrder::ACQUIRE)
                .is_ok()
            {
                self.reader_owners.fetch_or(bit, RmwOrder::AcqRel);
                return Ok(RwPermit {
                    owner,
                    ticket: 0,
                    write: false,
                });
            }
        }
    }

    pub fn read_bounded(&self, owner: u32, attempts: u32) -> Result<RwPermit, Error> {
        if attempts == 0 {
            return Err(Error::Deadline);
        }
        for _ in 0..attempts {
            match self.try_read(owner) {
                Ok(permit) => return Ok(permit),
                Err(Error::Busy) => {
                    self.reader_contentions.fetch_add(1, RmwOrder::Relaxed);
                    spin_loop();
                }
                Err(error) => return Err(error),
            }
        }
        Err(Error::Timeout)
    }

    pub fn read_lock(&self, owner: u32) -> Result<RwPermit, Error> {
        loop {
            match self.try_read(owner) {
                Ok(permit) => return Ok(permit),
                Err(Error::Busy) => {
                    self.reader_contentions.fetch_add(1, RmwOrder::Relaxed);
                    spin_loop();
                }
                Err(error) => return Err(error),
            }
        }
    }

    pub fn read_unlock(&self, permit: RwPermit) -> Result<(), Error> {
        if permit.write {
            return Err(Error::NotOwner);
        }
        let bit = owner_bit(permit.owner)?;
        let prior = self.reader_owners.fetch_and(!bit, RmwOrder::AcqRel);
        if prior & bit == 0 {
            return Err(Error::NotOwner);
        }
        let state = self.state.fetch_sub(1, RmwOrder::Release);
        if state & READER_MASK == 0 || state & WRITER_BIT != 0 {
            return Err(Error::Invariant);
        }
        Ok(())
    }

    pub fn try_write(&self, owner: u32) -> Result<RwPermit, Error> {
        owner_bit(owner)?;
        if self.writer_owner.load(LoadOrder::Acquire) == owner
            || self.reader_owners.load(LoadOrder::Acquire) & (1u32 << owner) != 0
        {
            return Err(Error::Recursive);
        }
        if self.writer_next.load(LoadOrder::Acquire) != self.writer_serving.load(LoadOrder::Acquire)
            || self.state.load(LoadOrder::Acquire) != 0
        {
            return Err(Error::Busy);
        }
        let ticket = self.reserve_waiting_writer()?;
        let state = self.state.load(LoadOrder::Acquire);
        if state & (WRITER_BIT | READER_MASK) == 0
            && self
                .state
                .compare_exchange(
                    state,
                    (state - WAITING_WRITER_ONE) | WRITER_BIT,
                    CompareExchangeOrder::ACQUIRE,
                )
                .is_ok()
        {
            self.writer_owner.store(owner, StoreOrder::Release);
            return Ok(RwPermit {
                owner,
                ticket,
                write: true,
            });
        }
        let removed = self.remove_waiting_writer();
        self.cancel_writer(ticket);
        removed?;
        Err(Error::Busy)
    }

    pub fn write_bounded(&self, owner: u32, attempts: u32) -> Result<RwPermit, Error> {
        owner_bit(owner)?;
        if attempts == 0 {
            return Err(Error::Deadline);
        }
        if self.writer_owner.load(LoadOrder::Acquire) == owner
            || self.reader_owners.load(LoadOrder::Acquire) & (1u32 << owner) != 0
        {
            return Err(Error::Recursive);
        }
        let ticket = self.reserve_waiting_writer()?;
        for _ in 0..attempts {
            if self.writer_serving.load(LoadOrder::Acquire) == ticket {
                let state = self.state.load(LoadOrder::Acquire);
                if state & (WRITER_BIT | READER_MASK) == 0
                    && self
                        .state
                        .compare_exchange(
                            state,
                            (state - WAITING_WRITER_ONE) | WRITER_BIT,
                            CompareExchangeOrder::ACQUIRE,
                        )
                        .is_ok()
                {
                    self.writer_owner.store(owner, StoreOrder::Release);
                    return Ok(RwPermit {
                        owner,
                        ticket,
                        write: true,
                    });
                }
            }
            self.writer_contentions.fetch_add(1, RmwOrder::Relaxed);
            spin_loop();
        }
        let removed = self.remove_waiting_writer();
        self.cancel_writer(ticket);
        removed?;
        self.writer_timeouts.fetch_add(1, RmwOrder::Relaxed);
        Err(Error::Timeout)
    }

    pub fn write_lock(&self, owner: u32) -> Result<RwPermit, Error> {
        owner_bit(owner)?;
        if self.writer_owner.load(LoadOrder::Acquire) == owner
            || self.reader_owners.load(LoadOrder::Acquire) & (1u32 << owner) != 0
        {
            return Err(Error::Recursive);
        }
        let ticket = self.reserve_waiting_writer()?;
        loop {
            if self.writer_serving.load(LoadOrder::Acquire) == ticket {
                let state = self.state.load(LoadOrder::Acquire);
                if state & (WRITER_BIT | READER_MASK) == 0
                    && self
                        .state
                        .compare_exchange(
                            state,
                            (state - WAITING_WRITER_ONE) | WRITER_BIT,
                            CompareExchangeOrder::ACQUIRE,
                        )
                        .is_ok()
                {
                    self.writer_owner.store(owner, StoreOrder::Release);
                    return Ok(RwPermit {
                        owner,
                        ticket,
                        write: true,
                    });
                }
            }
            self.writer_contentions.fetch_add(1, RmwOrder::Relaxed);
            spin_loop();
        }
    }

    pub fn write_unlock(&self, permit: RwPermit) -> Result<(), Error> {
        if !permit.write
            || self.writer_owner.load(LoadOrder::Acquire) != permit.owner
            || self.writer_serving.load(LoadOrder::Acquire) != permit.ticket
        {
            return Err(Error::NotOwner);
        }
        self.writer_owner.store(0, StoreOrder::Release);
        let state = self.state.fetch_and(!WRITER_BIT, RmwOrder::Release);
        if state & WRITER_BIT == 0 || state & READER_MASK != 0 {
            return Err(Error::Invariant);
        }
        self.writer_serving.fetch_add(1, RmwOrder::Release);
        self.advance_cancelled_writers();
        Ok(())
    }

    pub fn snapshot(&self) -> (u32, u32, u32, u32, u32) {
        (
            self.state.load(LoadOrder::Acquire),
            self.reader_contentions.load(LoadOrder::Acquire),
            self.writer_contentions.load(LoadOrder::Acquire),
            self.writer_timeouts.load(LoadOrder::Acquire),
            self.cancelled_writers.load(LoadOrder::Acquire),
        )
    }

    fn reserve_writer(&self) -> Result<u32, Error> {
        loop {
            let next = self.writer_next.load(LoadOrder::Acquire);
            let serving = self.writer_serving.load(LoadOrder::Acquire);
            if next.wrapping_sub(serving) >= MAX_OUTSTANDING_TICKETS {
                if self.writer_next.load(LoadOrder::Acquire) != next {
                    spin_loop();
                    continue;
                }
                return Err(Error::QueueFull);
            }
            if self
                .writer_next
                .compare_exchange_weak(next, next.wrapping_add(1), CompareExchangeOrder::ACQ_REL)
                .is_ok()
            {
                return Ok(next);
            }
        }
    }

    fn add_waiting_writer(&self) -> Result<(), Error> {
        loop {
            let state = self.state.load(LoadOrder::Acquire);
            if state & WAITING_WRITER_MASK == WAITING_WRITER_MASK {
                return Err(Error::QueueFull);
            }
            if self
                .state
                .compare_exchange_weak(
                    state,
                    state + WAITING_WRITER_ONE,
                    CompareExchangeOrder::ACQ_REL,
                )
                .is_ok()
            {
                return Ok(());
            }
        }
    }

    fn reserve_waiting_writer(&self) -> Result<u32, Error> {
        let ticket = self.reserve_writer()?;
        if let Err(error) = self.add_waiting_writer() {
            self.cancel_writer(ticket);
            return Err(error);
        }
        Ok(ticket)
    }

    fn remove_waiting_writer(&self) -> Result<(), Error> {
        loop {
            let state = self.state.load(LoadOrder::Acquire);
            if state & WAITING_WRITER_MASK == 0 {
                return Err(Error::Invariant);
            }
            if self
                .state
                .compare_exchange_weak(
                    state,
                    state - WAITING_WRITER_ONE,
                    CompareExchangeOrder::ACQ_REL,
                )
                .is_ok()
            {
                return Ok(());
            }
        }
    }

    fn cancel_writer(&self, ticket: u32) {
        self.cancelled_writers
            .fetch_or(1u32 << (ticket & 31), RmwOrder::AcqRel);
        self.advance_cancelled_writers();
    }

    fn advance_cancelled_writers(&self) {
        loop {
            if self.writer_owner.load(LoadOrder::Acquire) != 0 {
                return;
            }
            let serving = self.writer_serving.load(LoadOrder::Acquire);
            let bit = 1u32 << (serving & 31);
            let cancelled = self.cancelled_writers.load(LoadOrder::Acquire);
            if cancelled & bit == 0 {
                return;
            }
            if self
                .cancelled_writers
                .compare_exchange(cancelled, cancelled & !bit, CompareExchangeOrder::ACQ_REL)
                .is_err()
            {
                continue;
            }
            let _ = self.writer_serving.compare_exchange(
                serving,
                serving.wrapping_add(1),
                CompareExchangeOrder::ACQ_REL,
            );
        }
    }
}

impl Default for ReaderWriterLock {
    fn default() -> Self {
        Self::new()
    }
}

fn owner_bit(owner: u32) -> Result<u32, Error> {
    if owner == 0 {
        Err(Error::OwnerToken)
    } else if owner >= 32 {
        Err(Error::OwnerRange)
    } else {
        Ok(1u32 << owner)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SequenceRead {
    pub value: u64,
    pub sequence: u64,
    pub retries: u32,
}

pub struct SequenceLock {
    writer: TicketSpinLock,
    sequence: AtomicU64,
    value: AtomicU64,
    read_retries: AtomicU32,
}

impl SequenceLock {
    pub const fn new(value: u64) -> Self {
        Self {
            writer: TicketSpinLock::new(),
            sequence: AtomicU64::new(0),
            value: AtomicU64::new(value),
            read_retries: AtomicU32::new(0),
        }
    }

    pub fn write_bounded(&self, owner: u32, value: u64, attempts: u32) -> Result<u64, Error> {
        let permit = self.writer.lock_bounded(owner, attempts)?;
        let before = self.sequence.load(LoadOrder::Acquire);
        if before & 1 != 0 {
            let _ = self.writer.unlock(permit);
            return Err(Error::Sequence);
        }
        if self
            .sequence
            .compare_exchange(before, before + 1, CompareExchangeOrder::ACQ_REL)
            .is_err()
        {
            let _ = self.writer.unlock(permit);
            return Err(Error::Sequence);
        }
        self.value.store(value, StoreOrder::Relaxed);
        let odd = self.sequence.fetch_add(1, RmwOrder::Release);
        self.writer.unlock(permit)?;
        if odd != before + 1 {
            return Err(Error::Sequence);
        }
        Ok(odd + 1)
    }

    pub fn write(&self, owner: u32, value: u64) -> Result<u64, Error> {
        let permit = self.writer.lock(owner)?;
        let before = self.sequence.load(LoadOrder::Acquire);
        if before & 1 != 0 {
            let _ = self.writer.unlock(permit);
            return Err(Error::Sequence);
        }
        if self
            .sequence
            .compare_exchange(before, before + 1, CompareExchangeOrder::ACQ_REL)
            .is_err()
        {
            let _ = self.writer.unlock(permit);
            return Err(Error::Sequence);
        }
        self.value.store(value, StoreOrder::Relaxed);
        let odd = self.sequence.fetch_add(1, RmwOrder::Release);
        self.writer.unlock(permit)?;
        if odd != before + 1 {
            return Err(Error::Sequence);
        }
        Ok(odd + 1)
    }

    pub fn read_bounded(&self, attempts: u32) -> Result<SequenceRead, Error> {
        if attempts == 0 {
            return Err(Error::Deadline);
        }
        for retries in 0..attempts {
            let before = self.sequence.load(LoadOrder::Acquire);
            if before & 1 != 0 {
                self.read_retries.fetch_add(1, RmwOrder::Relaxed);
                spin_loop();
                continue;
            }
            let value = self.value.load(LoadOrder::Relaxed);
            let after = self.sequence.load(LoadOrder::Acquire);
            if before == after && after & 1 == 0 {
                return Ok(SequenceRead {
                    value,
                    sequence: after,
                    retries,
                });
            }
            self.read_retries.fetch_add(1, RmwOrder::Relaxed);
            spin_loop();
        }
        Err(Error::Timeout)
    }

    pub fn read(&self) -> SequenceRead {
        let mut retries = 0u32;
        loop {
            let before = self.sequence.load(LoadOrder::Acquire);
            if before & 1 == 0 {
                let value = self.value.load(LoadOrder::Relaxed);
                let after = self.sequence.load(LoadOrder::Acquire);
                if before == after && after & 1 == 0 {
                    return SequenceRead {
                        value,
                        sequence: after,
                        retries,
                    };
                }
            }
            retries = retries.wrapping_add(1);
            self.read_retries.fetch_add(1, RmwOrder::Relaxed);
            spin_loop();
        }
    }

    pub fn sequence(&self) -> u64 {
        self.sequence.load(LoadOrder::Acquire)
    }

    pub fn read_retries(&self) -> u32 {
        self.read_retries.load(LoadOrder::Acquire)
    }
}

fn increment(value: u32) -> Result<u32, Error> {
    value.checked_add(1).ok_or(Error::Counter)
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;

    #[test]
    fn ticket_spinlock_rejects_recursion_non_owner_and_rolls_back_timeout() {
        let lock = TicketSpinLock::new();
        let first = lock.try_lock(1).unwrap();
        assert_eq!(lock.try_lock(1), Err(Error::Recursive));
        assert_eq!(lock.lock_bounded(2, 4), Err(Error::Timeout));
        assert_eq!(
            lock.unlock(TicketPermit {
                owner: 2,
                ticket: 0
            }),
            Err(Error::NotOwner)
        );
        lock.unlock(first).unwrap();
        let snapshot = lock.snapshot();
        assert_eq!(snapshot.next, snapshot.serving);
        assert_eq!(snapshot.owner, 0);
        assert_eq!(snapshot.cancelled, 0);
        assert_eq!(snapshot.timeouts, 1);

        for start in [0, u32::MAX - 16] {
            let lock = TicketSpinLock::new();
            lock.next.store(start, StoreOrder::Relaxed);
            lock.serving.store(start, StoreOrder::Relaxed);
            for offset in 0..MAX_OUTSTANDING_TICKETS {
                assert_eq!(lock.reserve_ticket(), Ok(start.wrapping_add(offset)));
            }
            let before = lock.snapshot();
            assert_eq!(lock.reserve_ticket(), Err(Error::QueueFull));
            assert_eq!(lock.snapshot(), before);
        }

        let lock = TicketSpinLock::new();
        std::thread::scope(|scope| {
            for owner in 1..=4 {
                let lock = &lock;
                scope.spawn(move || {
                    for _ in 0..2048 {
                        let permit = lock.lock(owner).unwrap();
                        lock.unlock(permit).unwrap();
                    }
                });
            }
        });
        let snapshot = lock.snapshot();
        assert_eq!(snapshot.next, 8192);
        assert_eq!(snapshot.serving, snapshot.next);
        assert_eq!(snapshot.acquisitions, snapshot.next);
        assert_eq!(snapshot.owner, 0);
    }

    #[test]
    fn irqsave_restores_context_and_rejects_nested_interrupt_or_preemption() {
        let lock = IrqSaveSpinLock::new(LockRank::Irq);
        let mut graph = LockOrderGraph::new();
        let mut context = LockContext::task(1).unwrap();
        let guard = lock.lock_bounded(&mut context, &mut graph, 8).unwrap();
        assert!(!context.interrupts_enabled);
        assert_eq!(context.preemption_depth, 1);
        lock.unlock(&mut context, guard).unwrap();
        assert!(context.interrupts_enabled);
        assert_eq!(context.preemption_depth, 0);

        let mut interrupt = LockContext::interrupt(2, 1).unwrap();
        assert_eq!(
            lock.lock_bounded(&mut interrupt, &mut graph, 1),
            Err(Error::InterruptContext)
        );
        let mut preempted = LockContext::task(3).unwrap();
        preempted.preemption_depth = 1;
        assert_eq!(
            lock.lock_bounded(&mut preempted, &mut graph, 1),
            Err(Error::PreemptionContext)
        );
    }

    #[test]
    fn irqsave_rejects_foreign_guard_and_rolls_back_timeout_diagnostics() {
        let lock = IrqSaveSpinLock::new(LockRank::Sequence);
        let foreign = IrqSaveSpinLock::new(LockRank::Sequence);
        let mut graph = LockOrderGraph::new();
        let mut owner = LockContext::task(1).unwrap();
        let guard = lock.lock_bounded(&mut owner, &mut graph, 8).unwrap();

        let owner_before = owner;
        assert_eq!(foreign.unlock(&mut owner, guard), Err(Error::NotOwner));
        assert_eq!(owner, owner_before);

        let mut waiter = LockContext::task(2).unwrap();
        waiter.acquired(LockRank::RunQueue).unwrap();
        let waiter_before = waiter;
        let graph_before = graph;
        assert_eq!(
            lock.lock_bounded(&mut waiter, &mut graph, 1),
            Err(Error::Timeout)
        );
        assert_eq!(waiter, waiter_before);
        assert_eq!(graph, graph_before);
        assert!(!graph.edge(LockRank::RunQueue, LockRank::Sequence));

        lock.unlock(&mut owner, guard).unwrap();
    }

    #[test]
    fn rank_graph_records_edges_and_rejects_cycles_and_inversion() {
        let mut graph = LockOrderGraph::new();
        graph
            .record_dependency(LockRank::Irq, LockRank::Mutex)
            .unwrap();
        graph
            .record_dependency(LockRank::Mutex, LockRank::Sequence)
            .unwrap();
        assert_eq!(
            graph.record_dependency(LockRank::Sequence, LockRank::Irq),
            Err(Error::RankCycle)
        );
        let mut context = LockContext::task(7).unwrap();
        context.acquired(LockRank::Mutex).unwrap();
        assert_eq!(context.authorize(LockRank::RunQueue), Err(Error::RankOrder));
    }

    #[test]
    fn sleeping_mutex_donates_hands_off_times_out_and_tears_down_owner() {
        let mut graph = LockOrderGraph::new();
        let mut mutex = SleepMutex::new(LockRank::Mutex);
        let mut low = LockContext::task(1).unwrap();
        let mut high = LockContext::task(2).unwrap();
        let medium = LockContext::task(3).unwrap();
        mutex.try_lock(&mut low, &mut graph, 2).unwrap();
        assert_eq!(
            mutex.lock_or_enqueue(&mut high, &mut graph, 30, 20, 1),
            Ok(MutexAcquire::Blocked {
                ticket: 1,
                donate_priority: 30
            })
        );
        assert_eq!(
            mutex.lock_or_enqueue(&mut medium.clone(), &mut graph, 10, 2, 1),
            Ok(MutexAcquire::Blocked {
                ticket: 2,
                donate_priority: 30
            })
        );
        assert_eq!(mutex.timeout(3, 2).unwrap().reason, WakeReason::TimedOut);
        let wake = mutex.unlock(&mut low).unwrap().unwrap();
        assert_eq!(wake.owner, 2);
        mutex.claim_handoff(&mut high, &mut graph, wake).unwrap();
        let waiter = LockContext::task(4).unwrap();
        mutex
            .lock_or_enqueue(&mut waiter.clone(), &mut graph, 5, 30, 1)
            .unwrap();
        let (wakes, count) = mutex.owner_died(2).unwrap();
        assert_eq!(count, 1);
        assert_eq!(wakes[0].unwrap().reason, WakeReason::OwnerDead);
        assert_eq!(mutex.snapshot().owner, 0);
    }

    #[test]
    fn sleeping_mutex_drives_scheduler_block_donation_and_grant_wakeup() {
        use crate::scheduler::{
            COMPLETE_CPU_MASK, CpuId, Scheduler, WakeReason as SchedulerWakeReason,
        };

        let cpu0 = CpuId::new(0).unwrap();
        let cpu1 = CpuId::new(1).unwrap();
        let mut scheduler = Scheduler::new(COMPLETE_CPU_MASK).unwrap();
        let low_task = scheduler.create_task(0, 1, 2, 1).unwrap();
        let high_task = scheduler.create_task(1, 1, 30, 2).unwrap();
        scheduler.activate(low_task, cpu0).unwrap();
        scheduler.dispatch(cpu0).unwrap();

        let mut graph = LockOrderGraph::new();
        let mut mutex = SleepMutex::new(LockRank::Mutex);
        let mut low = LockContext::task(1).unwrap();
        let mut high = LockContext::task(2).unwrap();
        mutex.try_lock(&mut low, &mut graph, 2).unwrap();
        scheduler.yield_current(cpu0).unwrap();

        scheduler.activate(high_task, cpu1).unwrap();
        scheduler.dispatch(cpu1).unwrap();
        let blocked = mutex
            .lock_or_enqueue(&mut high, &mut graph, 30, 20, 1)
            .unwrap();
        assert_eq!(
            blocked,
            MutexAcquire::Blocked {
                ticket: 1,
                donate_priority: 30
            }
        );
        assert_eq!(scheduler.block_current_for_lock(cpu1), Ok(high_task));
        scheduler.donate_priority(low_task, 30).unwrap();
        assert_eq!(
            scheduler
                .task_snapshot(low_task)
                .unwrap()
                .effective_priority,
            30
        );

        scheduler.dispatch(cpu0).unwrap();
        let wake = mutex.unlock(&mut low).unwrap().unwrap();
        scheduler.revoke_priority_donation(low_task).unwrap();
        scheduler
            .wake_lock_waiter(high_task, cpu1, SchedulerWakeReason::LockGranted)
            .unwrap();
        mutex.claim_handoff(&mut high, &mut graph, wake).unwrap();
        assert_eq!(
            scheduler
                .task_snapshot(low_task)
                .unwrap()
                .effective_priority,
            2
        );
        assert_eq!(
            scheduler.task_snapshot(high_task).unwrap().wake_reason,
            SchedulerWakeReason::LockGranted
        );
        assert_eq!(scheduler.validate(), Ok(()));
    }

    #[test]
    fn notification_is_fifo_and_supports_timeout_cancel_and_broadcast() {
        let mut notification = Notification::new();
        let a = LockContext::task(1).unwrap();
        let b = LockContext::task(2).unwrap();
        let c = LockContext::task(3).unwrap();
        assert_eq!(notification.wait(&a, 10, 0), Ok(1));
        assert_eq!(notification.wait(&b, 10, 0), Ok(2));
        assert_eq!(notification.wait(&c, 2, 0), Ok(3));
        assert_eq!(notification.notify_one().unwrap().owner, 1);
        assert_eq!(
            notification.timeout(3, 2).unwrap().reason,
            WakeReason::TimedOut
        );
        assert_eq!(
            notification.cancel(2).unwrap().reason,
            WakeReason::Cancelled
        );
        notification.wait(&a, 20, 3).unwrap();
        notification.wait(&b, 20, 3).unwrap();
        let (_, count) = notification.notify_all().unwrap();
        assert_eq!(count, 2);
        assert_eq!(notification.waiter_count(), 0);
    }

    #[test]
    fn reader_writer_lock_prefers_queued_writer_and_cleans_timeout() {
        let lock = ReaderWriterLock::new();
        let reader = lock.try_read(1).unwrap();
        assert_eq!(lock.try_write(2), Err(Error::Busy));
        assert_eq!(lock.write_bounded(2, 4), Err(Error::Timeout));
        lock.read_unlock(reader).unwrap();
        let writer = lock.write_bounded(2, 8).unwrap();
        assert_eq!(lock.try_read(3), Err(Error::Busy));
        lock.write_unlock(writer).unwrap();
        let reader = lock.read_bounded(3, 8).unwrap();
        lock.read_unlock(reader).unwrap();
        let snapshot = lock.snapshot();
        assert_eq!(snapshot.0, 0);
        assert_eq!(snapshot.3, 1);
        assert_eq!(snapshot.4, 0);

        for start in [0, u32::MAX - 16] {
            let lock = ReaderWriterLock::new();
            lock.writer_next.store(start, StoreOrder::Relaxed);
            lock.writer_serving.store(start, StoreOrder::Relaxed);
            for offset in 0..MAX_OUTSTANDING_TICKETS {
                assert_eq!(lock.reserve_writer(), Ok(start.wrapping_add(offset)));
            }
            let next = lock.writer_next.load(LoadOrder::Acquire);
            assert_eq!(lock.reserve_writer(), Err(Error::QueueFull));
            assert_eq!(lock.writer_next.load(LoadOrder::Acquire), next);
            assert_eq!(lock.writer_serving.load(LoadOrder::Acquire), start);
        }

        let lock = ReaderWriterLock::new();
        std::thread::scope(|scope| {
            for owner in 1..=4 {
                let lock = &lock;
                scope.spawn(move || {
                    for _ in 0..2048 {
                        let permit = lock.write_lock(owner).unwrap();
                        lock.write_unlock(permit).unwrap();
                    }
                });
            }
        });
        assert_eq!(lock.writer_next.load(LoadOrder::Acquire), 8192);
        assert_eq!(lock.writer_serving.load(LoadOrder::Acquire), 8192);
        assert_eq!(lock.writer_owner.load(LoadOrder::Acquire), 0);
        assert_eq!(lock.state.load(LoadOrder::Acquire), 0);
    }

    #[test]
    fn sequence_lock_publishes_even_stable_snapshots() {
        let lock = SequenceLock::new(7);
        assert_eq!(lock.read_bounded(2).unwrap().value, 7);
        assert_eq!(lock.write_bounded(1, 0xfeed_beef, 8), Ok(2));
        let read = lock.read_bounded(8).unwrap();
        assert_eq!(read.value, 0xfeed_beef);
        assert_eq!(read.sequence, 2);
        assert_eq!(lock.sequence() & 1, 0);
    }

    #[test]
    fn bounded_queues_reject_invalid_contexts_without_mutation() {
        let mut mutex = SleepMutex::new(LockRank::Mutex);
        let mut graph = LockOrderGraph::new();
        let mut interrupt = LockContext::interrupt(1, 1).unwrap();
        let before = mutex.snapshot();
        assert_eq!(
            mutex.lock_or_enqueue(&mut interrupt, &mut graph, 10, 5, 0),
            Err(Error::InterruptContext)
        );
        assert_eq!(mutex.snapshot(), before);
        assert_eq!(
            TicketSpinLock::new().lock_bounded(0, 1),
            Err(Error::OwnerToken)
        );
        assert_eq!(ReaderWriterLock::new().try_read(32), Err(Error::OwnerRange));
    }
}
