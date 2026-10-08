//! Shared native construction, with explicit ownership on every failure.
use super::*;
use poolekernel::user_entry::{
    spawn::{Construction, Error},
    timer::Mappings,
};

pub struct Built {
    pub prepared: PreparedImage,
    pub memory: Memory,
    pub handles: [AllocationHandle; 5],
    pub image: InitialImage,
}
pub struct Failure {
    pub error: Error,
    pub allocated_pages: u64,
    pub owner: Construction,
    pub memory: Option<Memory>,
}
impl Failure {
    pub fn retry(
        &mut self,
        manager: &mut PhysicalMemoryManager,
        core: CoreRecord,
        bits: u8,
    ) -> Result<(), Error> {
        if self.memory.is_none() {
            self.memory = Some(memory(manager, core, bits, self.owner.handles())?);
        }
        self.owner
            .abort(manager, self.memory.as_mut().ok_or(Error::Memory)?)
    }
}
fn memory(
    manager: &PhysicalMemoryManager,
    core: CoreRecord,
    bits: u8,
    handles: [Option<AllocationHandle>; 5],
) -> Result<Memory, Error> {
    Ok(Memory {
        access: Access::partial(manager, core.page_table_root_physical, bits, handles)
            .map_err(|_| Error::Memory)?,
        root: core.page_table_root_physical,
        bits,
        writes: 0,
    })
}
#[allow(clippy::result_large_err)]
pub fn build(
    manager: &mut PhysicalMemoryManager,
    core: CoreRecord,
    bits: u8,
    payload: &[u8],
    timer: Option<Mappings>,
) -> Result<Built, Failure> {
    let mut failed = Failure {
        error: Error::State,
        allocated_pages: 0,
        owner: Construction::new(),
        memory: None,
    };
    let result = (|| {
        for _ in 0..5 {
            failed.owner.allocate_next(manager)?;
        }
        let handles = failed.owner.handles().map(Option::unwrap);
        failed.memory = Some(memory(manager, core, bits, handles.map(Some))?);
        let image = InitialImage {
            code_page: USER_WINDOW_START,
            entry: USER_WINDOW_START + 16,
            stack_page: USER_WINDOW_START + 3 * PAGE_BYTES,
        };
        let prepared = failed.owner.build(
            manager,
            failed.memory.as_mut().ok_or(Error::Memory)?,
            payload,
            image,
            core,
            bits,
            timer,
        )?;
        Ok((prepared, handles, image))
    })();
    match result {
        Ok((prepared, handles, image)) => Ok(Built {
            prepared,
            handles,
            image,
            memory: failed.memory.take().unwrap(),
        }),
        Err(error) => {
            failed.error = error;
            failed.allocated_pages = failed
                .owner
                .handles()
                .into_iter()
                .flatten()
                .map(|h| h.page_count)
                .sum();
            // A failed abort retains the full retryable owner, never just an error code.
            let _ = failed.retry(manager, core, bits);
            Err(failed)
        }
    }
}

pub fn quota_case(
    manager: &mut PhysicalMemoryManager,
    core: CoreRecord,
    bits: u8,
    timer: Mappings,
) -> Result<(), ()> {
    let baseline = manager.summary().allocated_pages;
    match build(manager, core, bits, &[0x90], Some(timer)) {
        Err(failed)
            if failed.error == Error::Allocation
                && failed.allocated_pages == 5
                && failed.owner.handles().iter().all(Option::is_none)
                && manager.summary().allocated_pages == baseline =>
        {
            Ok(())
        }
        _ => Err(()),
    }
}

struct AfterWrite<'a> {
    inner: &'a mut Memory,
    at: u64,
    fired: bool,
}
impl TableMemory for AfterWrite<'_> {
    fn prepare_page(&mut self, p: u64) -> Result<(), virtual_memory::Error> {
        self.inner.prepare_page(p)
    }
    fn read_entry(&mut self, p: u64, i: usize) -> Result<u64, virtual_memory::Error> {
        self.inner.read_entry(p, i)
    }
    fn write_entry(&mut self, p: u64, i: usize, v: u64) -> Result<(), virtual_memory::Error> {
        let count = self.inner.writes;
        self.inner.write_entry(p, i, v)?;
        if count == self.at {
            self.fired = true;
            return Err(virtual_memory::Error::MemoryAccess);
        }
        Ok(())
    }
    fn finish(&mut self) -> Result<(), virtual_memory::Error> {
        self.inner.finish()
    }
    fn physical_write_count(&self) -> u64 {
        self.inner.physical_write_count()
    }
    fn temporary_pte_write_count(&self) -> u64 {
        0
    }
    fn hardware_invalidation_count(&self) -> u64 {
        0
    }
}

/// Actual native physical writes, under the original CR3 while a peer's owned
/// image remains suspended. Every case must roll back before that peer resumes.
#[inline(never)]
pub fn fault_cases(
    manager: &mut PhysicalMemoryManager,
    core: CoreRecord,
    bits: u8,
    timer: Mappings,
) -> Result<u64, u64> {
    let baseline = manager.summary().allocated_pages;
    let image = InitialImage {
        code_page: USER_WINDOW_START,
        entry: USER_WINDOW_START + 16,
        stack_page: USER_WINDOW_START + 3 * PAGE_BYTES,
    };
    let mut cases = 0;
    for at in [0, 3072, 3073, 5124, 5125, 6667] {
        let mut owner = Construction::new();
        for _ in 0..5 {
            owner.allocate_next(manager).map_err(|_| cases * 10 + 1)?;
        }
        let mut memory =
            memory(manager, core, bits, owner.handles()).map_err(|_| cases * 10 + 1)?;
        let mut fault = AfterWrite {
            inner: &mut memory,
            at,
            fired: false,
        };
        if owner
            .build(manager, &mut fault, &[0x90], image, core, bits, Some(timer))
            .is_ok()
            || !fault.fired
        {
            return Err(cases * 10 + 2);
        }
        for handle in owner.handles().into_iter().flatten() {
            if manager.free(handle) != Err(PhysicalMemoryError::AllocationRetained) {
                return Err(cases * 10 + 3);
            }
        }
        let next_write = memory.writes;
        let mut fault = AfterWrite {
            inner: &mut memory,
            at: next_write,
            fired: false,
        };
        if owner.abort(manager, &mut fault).is_ok()
            || !fault.fired
            || manager.summary().allocated_pages != baseline + 13
        {
            return Err(cases * 10 + 4);
        }
        owner
            .abort(manager, &mut memory)
            .map_err(|_| cases * 10 + 1)?;
        if manager.summary().allocated_pages != baseline
            || owner.handles().iter().any(Option::is_some)
        {
            return Err(cases * 10 + 5);
        }
        cases += 1;
    }
    Ok(cases)
}
