//! PKRECLAIM1 core: bounded, pinned object ownership, not a CPU grace-period API.
//!
//! Callers must not hold the metadata gate across preemption or interrupt work.
//! Admission never waits: contention returns `Busy`. Dropping a pin uses one
//! atomic decrement and never takes the gate. No API can forcibly clear pins.

use core::cell::UnsafeCell;
use core::mem::MaybeUninit;
use core::ops::Deref;

use crate::atomics::{AtomicU32, LoadOrder, RmwOrder};
use crate::locks::{TicketPermit, TicketSpinLock};

pub const CONTRACT_ID: &str = "PKRECLAIM1-CORE";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Limits,
    Owner,
    ForeignPool,
    Stale,
    Busy,
    Capacity,
    GenerationExhausted,
    PinLimit,
    Retired,
    NotRetired,
    Pinned,
    Draining,
}

/// Trusted caller labels, not capabilities or evidence of scheduler quiescence.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Owner {
    pub task_generation: u64,
    pub address_space_generation: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Limits {
    pub pins_per_object: u32,
    pub generations_per_slot: u64,
}

impl Default for Limits {
    fn default() -> Self {
        Self {
            pins_per_object: u32::MAX - 1,
            generations_per_slot: u64::MAX,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Phase {
    Free,
    Live,
    Retired,
}

#[derive(Clone, Copy)]
struct Entry {
    phase: Phase,
    generation: u64,
    owner: Owner,
}

impl Entry {
    const EMPTY: Self = Self {
        phase: Phase::Free,
        generation: 0,
        owner: Owner {
            task_generation: 0,
            address_space_generation: 0,
        },
    };
}

struct Slot<T> {
    pins: AtomicU32,
    value: UnsafeCell<MaybeUninit<T>>,
}

impl<T> Slot<T> {
    const fn new() -> Self {
        Self {
            pins: AtomicU32::new(0),
            value: UnsafeCell::new(MaybeUninit::uninit()),
        }
    }
}

struct State<const N: usize> {
    entries: [Entry; N],
    draining: bool,
}

/// Allocation-free storage for N values. Values are immutable while pinned.
///
/// Forgotten pins retain storage until the entire pool is exclusively dropped.
/// Capacity pressure, owner death and shutdown never justify forced reclamation.
pub struct Pool<T, const N: usize> {
    gate: TicketSpinLock,
    state: UnsafeCell<State<N>>,
    slots: [Slot<T>; N],
    limits: Limits,
}

// SAFETY: the private PKLOCK1 gate serializes metadata and pin admission.
// Payload mutation requires Free, or Retired with an acquire-observed zero pin
// count. Shared payload access requires a counted Pin and T: Sync; transferring
// ownership through publish/reclaim on another thread requires T: Send.
unsafe impl<T: Send + Sync, const N: usize> Sync for Pool<T, N> {}

/// Opaque pool-bound identity. It pins the pool's address, not the object's life.
pub struct Handle<'a, T, const N: usize> {
    pool: &'a Pool<T, N>,
    slot: usize,
    generation: u64,
}

impl<T, const N: usize> Copy for Handle<'_, T, N> {}

impl<T, const N: usize> Clone for Handle<'_, T, N> {
    fn clone(&self) -> Self {
        *self
    }
}

impl<T, const N: usize> Handle<'_, T, N> {
    pub const fn slot(self) -> usize {
        self.slot
    }

    pub const fn generation(self) -> u64 {
        self.generation
    }
}

/// A counted shared borrow, including after retirement. No unpinned `&T` escapes.
///
/// ```compile_fail
/// use poolekernel::reclamation::{Limits, Owner, Pool};
/// let pool = Pool::<u64, 1>::new(Limits::default()).unwrap();
/// let owner = Owner { task_generation: 1, address_space_generation: 1 };
/// let handle = pool.publish(owner, 7).ok().unwrap();
/// let pin = pool.pin(handle).ok().unwrap();
/// let reference = &*pin;
/// drop(pin);
/// println!("{reference}");
/// ```
pub struct Pin<'a, T, const N: usize> {
    pool: &'a Pool<T, N>,
    slot: usize,
}

impl<T, const N: usize> Deref for Pin<'_, T, N> {
    type Target = T;

    fn deref(&self) -> &T {
        // SAFETY: admission incremented this slot's count while Live, under
        // the gate. Reclamation cannot move/drop T until this Pin is dropped.
        unsafe { (&*self.pool.slots[self.slot].value.get()).assume_init_ref() }
    }
}

impl<T, const N: usize> Drop for Pin<'_, T, N> {
    fn drop(&mut self) {
        // The acquire zero-load in reclaim observes this release and preceding
        // payload reads. Admission is the only increment path, under the gate.
        self.pool.slots[self.slot]
            .pins
            .fetch_sub(1, RmwOrder::Release);
    }
}

struct Gate<'a, T, const N: usize> {
    pool: &'a Pool<T, N>,
    permit: TicketPermit,
}

impl<T, const N: usize> Gate<'_, T, N> {
    fn state(&mut self) -> &mut State<N> {
        // SAFETY: only this private guard can hold the pool's metadata gate.
        // Payloads and pin counters are separate from this exclusive reference.
        unsafe { &mut *self.pool.state.get() }
    }
}

impl<T, const N: usize> Drop for Gate<'_, T, N> {
    fn drop(&mut self) {
        // No public API exposes the lock or its permit. A failure is an internal
        // invariant violation and must not silently permit further access.
        self.pool
            .gate
            .unlock(self.permit)
            .expect("PKRECLAIM1 gate ownership");
    }
}

impl<T, const N: usize> Pool<T, N> {
    pub fn new(limits: Limits) -> Result<Self, Error> {
        if N == 0 || limits.pins_per_object == 0 || limits.generations_per_slot == 0 {
            return Err(Error::Limits);
        }
        Ok(Self {
            gate: TicketSpinLock::new(),
            state: UnsafeCell::new(State {
                entries: [Entry::EMPTY; N],
                draining: false,
            }),
            slots: [const { Slot::new() }; N],
            limits,
        })
    }

    fn enter(&self) -> Result<Gate<'_, T, N>, Error> {
        // One private owner token is sufficient: same-token contention and
        // recursion both fail immediately. This is not a scheduler owner ID.
        let permit = self.gate.try_lock(1).map_err(|_| Error::Busy)?;
        Ok(Gate { pool: self, permit })
    }

    fn validate(&self, handle: Handle<'_, T, N>, state: &State<N>) -> Result<usize, Error> {
        if !core::ptr::eq(self, handle.pool) {
            return Err(Error::ForeignPool);
        }
        let entry = &state.entries[handle.slot];
        if entry.phase == Phase::Free || entry.generation != handle.generation {
            return Err(Error::Stale);
        }
        Ok(handle.slot)
    }

    /// On every failure, return the original value without dropping it.
    #[allow(clippy::type_complexity)]
    pub fn publish(&self, owner: Owner, value: T) -> Result<Handle<'_, T, N>, (Error, T)> {
        let mut gate = match self.enter() {
            Ok(gate) => gate,
            Err(error) => return Err((error, value)),
        };
        if owner.task_generation == 0 || owner.address_space_generation == 0 {
            return Err((Error::Owner, value));
        }
        let state = gate.state();
        if state.draining {
            return Err((Error::Draining, value));
        }
        let index = state.entries.iter().position(|entry| {
            entry.phase == Phase::Free && entry.generation < self.limits.generations_per_slot
        });
        let Some(index) = index else {
            let error = if state.entries.iter().any(|entry| entry.phase == Phase::Free) {
                Error::GenerationExhausted
            } else {
                Error::Capacity
            };
            return Err((error, value));
        };
        let entry = &mut state.entries[index];
        let generation = entry.generation + 1; // Strictly below the nonwrapping limit.
        // SAFETY: Free slots contain no T and no pins. All metadata admissions
        // are excluded until initialization and Live publication complete.
        unsafe { (*self.slots[index].value.get()).write(value) };
        *entry = Entry {
            phase: Phase::Live,
            generation,
            owner,
        };
        Ok(Handle {
            pool: self,
            slot: index,
            generation,
        })
    }

    pub fn pin(&self, handle: Handle<'_, T, N>) -> Result<Pin<'_, T, N>, Error> {
        let mut gate = self.enter()?;
        let state = gate.state();
        let index = self.validate(handle, state)?;
        if state.draining {
            return Err(Error::Draining);
        }
        if state.entries[index].phase != Phase::Live {
            return Err(Error::Retired);
        }
        let pins = &self.slots[index].pins;
        if pins.load(LoadOrder::Relaxed) >= self.limits.pins_per_object {
            return Err(Error::PinLimit);
        }
        // Only this gate can increment; concurrent drops can only reduce the
        // count, so the preflight proves this RMW cannot overflow.
        pins.fetch_add(1, RmwOrder::Relaxed);
        Ok(Pin {
            pool: self,
            slot: index,
        })
    }

    pub fn retire(&self, handle: Handle<'_, T, N>, owner: Owner) -> Result<(), Error> {
        let mut gate = self.enter()?;
        let state = gate.state();
        let index = self.validate(handle, state)?;
        let entry = &mut state.entries[index];
        if entry.owner != owner {
            return Err(Error::Owner);
        }
        if entry.phase == Phase::Retired {
            return Err(Error::Retired);
        }
        entry.phase = Phase::Retired;
        Ok(())
    }

    /// Transfer T exactly once, after retirement and release of every pin.
    /// T's destructor runs in the caller, outside the metadata gate.
    pub fn reclaim(&self, handle: Handle<'_, T, N>, owner: Owner) -> Result<T, Error> {
        let mut gate = self.enter()?;
        let state = gate.state();
        let index = self.validate(handle, state)?;
        let entry = &mut state.entries[index];
        if entry.owner != owner {
            return Err(Error::Owner);
        }
        if entry.phase != Phase::Retired {
            return Err(Error::NotRetired);
        }
        if self.slots[index].pins.load(LoadOrder::Acquire) != 0 {
            return Err(Error::Pinned);
        }
        // SAFETY: Retired forbids new pins, zero observes all old pin releases,
        // and the gate excludes another reclaim. Mark Free before returning T.
        let value = unsafe { (*self.slots[index].value.get()).assume_init_read() };
        entry.phase = Phase::Free;
        Ok(value)
    }

    /// Seal admission permanently. Existing pins, retirement and reclaim survive.
    pub fn begin_shutdown(&self) -> Result<(), Error> {
        self.enter()?.state().draining = true;
        Ok(())
    }

    pub fn is_drained(&self) -> Result<bool, Error> {
        let mut gate = self.enter()?;
        let state = gate.state();
        Ok(state.draining && state.entries.iter().all(|entry| entry.phase == Phase::Free))
    }
}

impl<T, const N: usize> Drop for Pool<T, N> {
    fn drop(&mut self) {
        // Exclusive ownership rules out accessible handles/pins. Forgotten pins
        // cannot be accessed again; MaybeUninit prevents implicit double-drop.
        for (entry, slot) in self.state.get_mut().entries.iter_mut().zip(&mut self.slots) {
            if entry.phase != Phase::Free {
                entry.phase = Phase::Free;
                // SAFETY: exactly the Live and Retired slots still own a T.
                unsafe { slot.value.get_mut().assume_init_drop() };
            }
        }
    }
}

pub mod task_lifetimes;
