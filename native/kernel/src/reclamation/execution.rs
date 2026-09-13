//! PKEXEC1: mandatory object retention before a scheduler dispatch escapes.
//! This is an ownership boundary, not a hardware-quiescence detector.

use super::task_lifetimes::{Reader, Resources};
use crate::scheduler_smp::TransferTicket;

pub const CONTRACT_ID: &str = "PKEXEC1";

/// Holds the actual task resources independently of scheduler completion.
/// Dropping, forgetting or unwinding this value intentionally retains its pin.
/// Only explicit architectural quiescence may release that pin.
///
/// ```compile_fail
/// use poolekernel::reclamation::execution::Dispatch;
/// fn duplicate<'a>(value: &Dispatch<'a, ()>) -> Dispatch<'a, ()> { value.clone() }
/// ```
///
/// ```compile_fail
/// use poolekernel::reclamation::execution::Dispatch;
/// fn invent_quiescence(value: Dispatch<'_, ()>) { value.confirm_quiescent(); }
/// ```
///
/// ```compile_fail
/// use poolekernel::reclamation::execution::Dispatch;
/// fn release_twice(value: Dispatch<'_, ()>) {
///     unsafe { value.confirm_quiescent(); value.confirm_quiescent(); }
/// }
/// ```
///
/// ```compile_fail
/// use poolekernel::reclamation::{Limits, task_lifetimes::Storage};
/// use poolekernel::scheduler_smp::CpuId;
/// fn replace_storage(storage: &mut Storage<()>) {
///     let mut tasks = storage.attach().unwrap();
///     let execution = tasks.stage_dispatch(CpuId::new(1).unwrap(), 1, 1).unwrap();
///     drop(tasks);
///     *storage = Storage::new(Limits::default()).unwrap();
///     let _ = execution.resources();
/// }
/// ```
#[must_use = "discarding a dispatch retains resources until boot-lifetime teardown"]
pub struct Dispatch<'a, T> {
    ticket: TransferTicket,
    reader: Option<Reader<'a, T>>,
}

impl<'a, T> Dispatch<'a, T> {
    pub(crate) fn new(ticket: TransferTicket, reader: Reader<'a, T>) -> Self {
        Self {
            ticket,
            reader: Some(reader),
        }
    }

    /// Copyable protocol identity only; it cannot release the execution hold.
    pub const fn ticket(&self) -> TransferTicket {
        self.ticket
    }

    pub fn resources(&self) -> &Resources<T> {
        self.reader.as_ref().expect("PKEXEC1 retained reader")
    }

    /// Release this hold, not the allocations or other outstanding readers.
    ///
    /// # Safety
    /// The architecture adapter must prevent every present or future CPU use
    /// of this dispatch's context, root and stack. It must revoke resumable
    /// contexts and aliases and finish all required local/remote invalidations
    /// before calling this function. A scheduler ACK, Dead state, timeout,
    /// cancellation or offline label is not this evidence. A never-published
    /// dispatch may be released only after future publication is impossible.
    ///
    /// This hold does not stabilize the address of Storage or arbitrary payload
    /// allocations. Hardware adapters must separately own stable context storage
    /// and must not let raw pointers into this Rust object escape its lifetime.
    pub unsafe fn confirm_quiescent(mut self) {
        drop(self.reader.take());
    }
}

impl<T> Drop for Dispatch<'_, T> {
    fn drop(&mut self) {
        if let Some(reader) = self.reader.take() {
            core::mem::forget(reader);
        }
    }
}
