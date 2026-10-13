//! Late-bound startup handles for an owned image that has never executed.
#![forbid(unsafe_code)]

use super::{Cpu, Driver, Runtime, Slot, State, TableMemory, TaskId};
use crate::user_entry::startup::{Arguments, Startup};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Metadata,
    Contents,
    Memory(crate::virtual_memory::Error),
}

fn verify<M: TableMemory>(memory: &mut M, page: u64, bytes: &[u8]) -> Result<(), Error> {
    for (index, word) in bytes.chunks_exact(8).enumerate() {
        let actual = memory.read_entry(page, index).map_err(Error::Memory)?;
        if actual.to_le_bytes() != word {
            return Err(Error::Contents);
        }
    }
    Ok(())
}

impl<H: Cpu, D: Driver> Slot<H, D> {
    /// Exclusive trusted launch dispatcher only, before any possible CPU entry.
    /// The caller must keep the scheduler from dispatching throughout admission
    /// and this handoff. These bytes convey handles, never grant authority.
    ///
    /// Equal encoded lengths preserve the already-bound startup registers. Any
    /// memory error or unexpected old/new content quarantines the retained owner;
    /// neither retry nor activation can execute a partially updated image.
    pub fn replace_startup_arguments<M: TableMemory>(
        &mut self,
        id: TaskId,
        startup: &Startup,
        expected: &Arguments,
        replacement: &Arguments,
        memory: &mut M,
    ) -> Result<(), super::Error> {
        let task = self.owned_mut(id)?;
        if task.state != State::Prepared
            || task.pending_charge.is_some()
            || task.last_slice.is_some()
            || task.outcome.is_some()
            || task.runtime != Runtime::default()
        {
            return Err(super::Error::State);
        }
        let image = task
            .cpu
            .as_ref()
            .ok_or(super::Error::State)?
            .unexposed_admission()
            .map_err(super::Error::Cpu)?;
        let registers = startup
            .registers(image)
            .map_err(|_| super::Error::Arguments(Error::Metadata))?;
        if registers[1] != expected.bytes().len() as u64
            || expected.bytes().len() != replacement.bytes().len()
        {
            return Err(super::Error::Arguments(Error::Metadata));
        }
        // All read/write failures can follow an effect. Restore Prepared only
        // after checking the full original block and the complete final block.
        task.state = State::Quarantined;
        let mut update = || -> Result<(), Error> {
            verify(memory, image.stack_physical, expected.bytes())?;
            for (index, word) in replacement.bytes().chunks_exact(8).enumerate() {
                let value = u64::from_le_bytes(word.try_into().map_err(|_| Error::Metadata)?);
                memory
                    .write_entry(image.stack_physical, index, value)
                    .map_err(Error::Memory)?;
            }
            memory.finish().map_err(Error::Memory)?;
            verify(memory, image.stack_physical, replacement.bytes())?;
            memory.finish().map_err(Error::Memory)
        };
        update().map_err(super::Error::Arguments)?;
        task.state = State::Prepared;
        Ok(())
    }
}
