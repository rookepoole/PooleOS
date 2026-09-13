use std::collections::BTreeMap;
use std::sync::{
    Arc, Barrier,
    atomic::{AtomicUsize, Ordering},
};

use poole_handoff::*;
use poolekernel::physical_memory::{
    AllocationHandle, PageAccessError, PhysicalMemoryError, PhysicalMemoryManager,
    PhysicalPageAccess, Zone,
};
use poolekernel::reclamation::task_lifetimes::{
    Error, Resources, STACK_OWNER, STACK_PAGE_COUNT, Storage,
};
use poolekernel::reclamation::{Error as PoolError, Limits};
use poolekernel::scheduler_smp::{self as sched, CpuId, TaskId, TaskState};
use poolekernel::virtual_memory::{self as vm, AddressSpace, TableMemory};

#[derive(Default)]
struct Memory {
    pages: BTreeMap<u64, [u64; 512]>,
    writes: u64,
    fail_write: bool,
    fail_read: bool,
    corrupt_read: bool,
    physical_writes: u64,
    physical_reads: u64,
    fail_write_after: Option<u64>,
    fail_read_after: Option<u64>,
}

impl PhysicalPageAccess for Memory {
    fn write_word(
        &mut self,
        address: u64,
        index: usize,
        value: u64,
    ) -> Result<(), PageAccessError> {
        if self.fail_write || self.fail_write_after == Some(self.physical_writes) {
            return Err(PageAccessError::Access);
        }
        self.physical_writes += 1;
        self.pages.entry(address).or_insert([u64::MAX; 512])[index] = value;
        Ok(())
    }

    fn read_word(&mut self, address: u64, index: usize) -> Result<u64, PageAccessError> {
        if self.fail_read || self.fail_read_after == Some(self.physical_reads) {
            return Err(PageAccessError::Access);
        }
        self.physical_reads += 1;
        Ok(if self.corrupt_read {
            1
        } else {
            self.pages[&address][index]
        })
    }
}

impl TableMemory for Memory {
    fn prepare_page(&mut self, address: u64) -> Result<(), vm::Error> {
        self.pages.entry(address).or_insert([0; 512]);
        Ok(())
    }
    fn read_entry(&mut self, address: u64, index: usize) -> Result<u64, vm::Error> {
        self.pages
            .get(&address)
            .and_then(|page| page.get(index))
            .copied()
            .ok_or(vm::Error::MemoryAccess)
    }
    fn write_entry(&mut self, address: u64, index: usize, value: u64) -> Result<(), vm::Error> {
        *self
            .pages
            .get_mut(&address)
            .and_then(|page| page.get_mut(index))
            .ok_or(vm::Error::MemoryAccess)? = value;
        self.writes += 1;
        Ok(())
    }
    fn finish(&mut self) -> Result<(), vm::Error> {
        Ok(())
    }
    fn physical_write_count(&self) -> u64 {
        self.writes
    }
    fn temporary_pte_write_count(&self) -> u64 {
        0
    }
    fn hardware_invalidation_count(&self) -> u64 {
        0
    }
}

fn fixture() -> (PhysicalMemoryManager, Memory) {
    let mut core = [0u8; 128];
    for (offset, value) in [
        (0, DEVELOPMENT_MODE | BOOT_SERVICES_EXITED),
        (8, 0x0200_0000),
        (16, 0x0004_0000),
        (24, 0xffff_ffff_8000_0000),
        (32, 0x0004_0000),
        (40, 0xffff_ffff_8000_8000),
        (48, 0xffff_ffff_8004_9000),
        (56, 0x0204_0000),
        (64, 0x0205_0000),
        (72, 0xffff_ffff_8005_0000),
    ] {
        core[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
    }
    for (offset, value) in [
        (104, 0u32),
        (108, 3),
        (112, 1),
        (116, 1),
        (120, 0x0002_0046),
    ] {
        core[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
    }
    let mut map = Vec::new();
    for (start, count, kind, source) in [
        (0x0100_0000u64, 4096u64, MEMORY_USABLE, 7u32),
        (0x0200_0000, 96, MEMORY_LOADER_RESERVED, 2),
    ] {
        map.extend_from_slice(&start.to_le_bytes());
        map.extend_from_slice(&count.to_le_bytes());
        map.extend_from_slice(&0xfu64.to_le_bytes());
        map.extend_from_slice(&kind.to_le_bytes());
        map.extend_from_slice(&source.to_le_bytes());
        map.extend_from_slice(&0u64.to_le_bytes());
    }
    let size = encoded_size(2, &[128, map.len()]).unwrap();
    core[80..88].copy_from_slice(&(size as u64).to_le_bytes());
    let mut bytes = vec![0; size];
    let mut encoder = Encoder::new(&mut bytes, 2, 0, 0).unwrap();
    encoder
        .push(RECORD_CORE, 1, RECORD_REQUIRED, 128, 1, &core)
        .unwrap();
    encoder
        .push(
            RECORD_MEMORY_MAP,
            1,
            RECORD_REQUIRED | RECORD_ARRAY,
            MEMORY_ENTRY_BYTES,
            2,
            &map,
        )
        .unwrap();
    let handoff = decode(encoder.finish().unwrap()).unwrap();
    let manager =
        PhysicalMemoryManager::from_handoff(&handoff, handoff.core().unwrap(), 128).unwrap();
    (manager, Memory::default())
}

fn space(manager: &mut PhysicalMemoryManager, memory: &mut Memory) -> AddressSpace {
    let tables = manager
        .allocate(Zone::Dma32, vm::TABLE_PAGE_COUNT, vm::TABLE_OWNER)
        .unwrap();
    AddressSpace::initialize(manager, tables, memory).unwrap()
}

fn resource<T>(
    manager: &mut PhysicalMemoryManager,
    memory: &mut Memory,
    payload: T,
) -> Resources<T> {
    with_stack(space(manager, memory), payload, manager)
        .ok()
        .unwrap()
}

fn with_stack<T>(
    space: AddressSpace,
    payload: T,
    manager: &mut PhysicalMemoryManager,
) -> Result<Resources<T>, (Error, AddressSpace, AllocationHandle, T)> {
    let stack = manager
        .allocate(Zone::Dma32, STACK_PAGE_COUNT, STACK_OWNER)
        .unwrap();
    Resources::new(space, stack, payload, manager)
}

#[test]
fn dispatch_execution_holds_actual_stack_until_architectural_release() {
    let (mut manager, mut memory) = fixture();
    let resources = resource(&mut manager, &mut memory, 42);
    let stack_handle = resources.execution_stack().handle();
    let root = resources.address_space().summary();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks.create(0, 1, 2, resources).ok().unwrap();
    tasks.activate(id, cpu(1)).unwrap();
    let execution = tasks.stage_dispatch(cpu(1), 1, 1).unwrap();
    let ticket = execution.ticket();
    assert_eq!(ticket.task, id);
    assert_eq!(ticket.target_cpu, 1);
    assert_eq!(*execution.resources().payload(), 42);
    assert_eq!(
        execution.resources().execution_stack().handle(),
        stack_handle
    );
    assert_eq!(execution.resources().address_space().summary(), root);
    tasks.acknowledge(ticket, ack(ticket)).unwrap();
    tasks.complete_current(cpu(1)).unwrap();
    assert_eq!(
        tasks.reclaim(id).err(),
        Some(Error::Pool(PoolError::Pinned))
    );
    assert_eq!(
        manager.free(stack_handle),
        Err(PhysicalMemoryError::AllocationRetained)
    );
    assert_eq!(memory.physical_writes, 0);
    // SAFETY: this is a host ownership test; no architectural consumer exists.
    unsafe { execution.confirm_quiescent() };
    let owned = tasks.reclaim(id).unwrap();
    let (mut address, stack, payload) = owned.into_parts(&mut manager).ok().unwrap();
    assert_eq!(payload, 42);
    address.release(&mut manager, &mut memory).unwrap();
    stack
        .release_scrubbed(&mut manager, &mut memory)
        .ok()
        .unwrap();
    assert_eq!(memory.physical_writes, 2048);
    assert_eq!(memory.physical_reads, 2048);
    assert_eq!(manager.summary().allocated_pages, 0);
}

#[test]
fn dispatch_execution_loss_never_fabricates_quiescence() {
    for loss in 0..3 {
        let (mut manager, mut memory) = fixture();
        let mut store = Storage::new(Limits::default()).unwrap();
        let mut tasks = store.attach().unwrap();
        let id = tasks
            .create(0, 1, 2, resource(&mut manager, &mut memory, ()))
            .ok()
            .unwrap();
        tasks.activate(id, cpu(1)).unwrap();
        let execution = tasks.stage_dispatch(cpu(1), 1, 1).unwrap();
        let ticket = execution.ticket();
        let handle = execution.resources().execution_stack().handle();
        match loss {
            0 => drop(execution),
            1 => std::mem::forget(execution),
            _ => {
                let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(move || {
                    let _held = execution;
                    panic!("host-only owner unwind");
                }));
                assert!(result.is_err());
            }
        }
        tasks.acknowledge(ticket, ack(ticket)).unwrap();
        tasks.complete_current(cpu(1)).unwrap();
        tasks.begin_shutdown().unwrap();
        for _ in 0..32 {
            assert_eq!(
                tasks.reclaim(id).err(),
                Some(Error::Pool(PoolError::Pinned))
            );
            assert!(!tasks.is_drained().unwrap());
            assert_eq!(
                manager.free(handle),
                Err(PhysicalMemoryError::AllocationRetained)
            );
        }
        drop(tasks);
        drop(store);
        assert_eq!(
            manager.free(handle),
            Err(PhysicalMemoryError::AllocationRetained)
        );
        assert_eq!(memory.physical_writes, 0);
    }
}

#[test]
fn dispatch_execution_pin_exhaustion_precedes_queue_mutation() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits {
        pins_per_object: 1,
        generations_per_slot: 2,
    })
    .unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 2, resource(&mut manager, &mut memory, ()))
        .ok()
        .unwrap();
    tasks.activate(id, cpu(1)).unwrap();
    let reader = tasks.pin(id).unwrap();
    let before = tasks.scheduler().summary();
    let task_before = tasks.snapshot(id).unwrap();
    for _ in 0..8 {
        assert_eq!(
            tasks.stage_dispatch(cpu(1), 1, 1).err(),
            Some(Error::Pool(PoolError::PinLimit))
        );
        assert_eq!(tasks.scheduler().summary(), before);
        assert_eq!(tasks.snapshot(id).unwrap(), task_before);
        assert!(!tasks.scheduler().has_pending());
    }
    drop(reader);
    let execution = tasks.stage_dispatch(cpu(1), 1, 1).unwrap();
    let ticket = execution.ticket();
    tasks.acknowledge(ticket, ack(ticket)).unwrap();
    tasks.complete_current(cpu(1)).unwrap();
    // SAFETY: no host-test CPU or alias was ever given the task's physical pages.
    unsafe { execution.confirm_quiescent() };
    assert!(tasks.reclaim(id).is_ok());
}

#[test]
fn dispatch_execution_invalid_admission_does_not_consume_pins() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits {
        pins_per_object: 1,
        generations_per_slot: 2,
    })
    .unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 2, resource(&mut manager, &mut memory, ()))
        .ok()
        .unwrap();
    tasks.activate(id, cpu(1)).unwrap();
    let before = tasks.scheduler().summary();
    for (lane, attempt, sequence) in [(1, 0, 1), (1, 1, 0), (2, 1, 1)] {
        assert!(tasks.stage_dispatch(cpu(lane), attempt, sequence).is_err());
        assert_eq!(tasks.scheduler().summary(), before);
        drop(tasks.pin(id).unwrap());
    }
    tasks.begin_shutdown().unwrap();
    assert_eq!(
        tasks.stage_dispatch(cpu(1), 1, 1).err(),
        Some(Error::Draining)
    );
    tasks.cancel(id).unwrap();
    assert!(tasks.reclaim(id).is_ok());
}

#[test]
fn dispatch_execution_cpu_holds_retire_independently() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let a = tasks
        .create(0, 1, 2, resource(&mut manager, &mut memory, 11))
        .ok()
        .unwrap();
    let b = tasks
        .create(1, 1, 4, resource(&mut manager, &mut memory, 22))
        .ok()
        .unwrap();
    tasks.activate(a, cpu(1)).unwrap();
    tasks.activate(b, cpu(2)).unwrap();
    let first = tasks.stage_dispatch(cpu(1), 1, 1).unwrap();
    tasks
        .acknowledge(first.ticket(), ack(first.ticket()))
        .unwrap();
    let second = tasks.stage_dispatch(cpu(2), 2, 1).unwrap();
    tasks
        .acknowledge(second.ticket(), ack(second.ticket()))
        .unwrap();
    tasks.complete_current(cpu(1)).unwrap();
    tasks.complete_current(cpu(2)).unwrap();
    assert_eq!(tasks.reclaim(a).err(), Some(Error::Pool(PoolError::Pinned)));
    assert_eq!(tasks.reclaim(b).err(), Some(Error::Pool(PoolError::Pinned)));
    // SAFETY: the synthetic lane has no hardware consumer or resumable context.
    unsafe { first.confirm_quiescent() };
    assert_eq!(*tasks.reclaim(a).unwrap().payload(), 11);
    assert_eq!(tasks.reclaim(b).err(), Some(Error::Pool(PoolError::Pinned)));
    assert_eq!(*second.resources().payload(), 22);
    // SAFETY: the second synthetic lane also has no hardware consumer.
    unsafe { second.confirm_quiescent() };
    assert_eq!(*tasks.reclaim(b).unwrap().payload(), 22);
}

#[test]
fn dispatch_execution_reuse_rejects_prior_generation_ack() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let old = tasks
        .create(0, 1, 2, resource(&mut manager, &mut memory, ()))
        .ok()
        .unwrap();
    tasks.activate(old, cpu(1)).unwrap();
    let first = tasks.stage_dispatch(cpu(1), 1, 1).unwrap();
    let old_ticket = first.ticket();
    tasks.acknowledge(old_ticket, ack(old_ticket)).unwrap();
    tasks.complete_current(cpu(1)).unwrap();
    let (error, replacement) = tasks
        .create(0, 1, 2, resource(&mut manager, &mut memory, ()))
        .err()
        .unwrap();
    assert_eq!(error, Error::Occupied);
    // SAFETY: no context was installed or executed by this host-only harness.
    unsafe { first.confirm_quiescent() };
    let _retired = tasks.reclaim(old).unwrap();
    let new = tasks.create(0, 1, 2, replacement).ok().unwrap();
    assert!(new.generation > old.generation);
    tasks.activate(new, cpu(1)).unwrap();
    let second = tasks.stage_dispatch(cpu(1), 2, 2).unwrap();
    let before = tasks.scheduler().summary();
    assert_eq!(
        tasks.acknowledge(old_ticket, ack(old_ticket)),
        Err(Error::Scheduler(sched::Error::TicketMismatch))
    );
    assert_eq!(tasks.scheduler().summary(), before);
    tasks
        .acknowledge(second.ticket(), ack(second.ticket()))
        .unwrap();
    tasks.complete_current(cpu(1)).unwrap();
    assert_eq!(
        tasks.reclaim(new).err(),
        Some(Error::Pool(PoolError::Pinned))
    );
    // SAFETY: the second generation also never acquired a hardware consumer.
    unsafe { second.confirm_quiescent() };
    assert!(tasks.reclaim(new).is_ok());
}

#[test]
fn task_execution_stack_cannot_be_freed_through_a_copied_handle() {
    let (mut manager, mut memory) = fixture();
    let resources = resource(&mut manager, &mut memory, ());
    let stack = resources.execution_stack().handle();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks.create(0, 1, 1, resources).ok().unwrap();
    let reader = tasks.pin(id).unwrap();
    assert_eq!(
        manager.free(stack),
        Err(PhysicalMemoryError::AllocationRetained)
    );
    tasks.cancel_dormant(id).unwrap();
    assert_eq!(
        tasks.reclaim(id).err(),
        Some(Error::Pool(PoolError::Pinned))
    );
    drop(reader);
}

#[test]
fn task_reader_retains_physical_tables_against_copied_allocator_handles() {
    use poolekernel::physical_memory::PhysicalMemoryError;

    let (mut manager, mut memory) = fixture();
    let tables = manager
        .allocate(Zone::Dma32, vm::TABLE_PAGE_COUNT, vm::TABLE_OWNER)
        .unwrap();
    let address = AddressSpace::initialize(&mut manager, tables, &mut memory).unwrap();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 1, with_stack(address, (), &mut manager).ok().unwrap())
        .ok()
        .unwrap();
    tasks.activate(id, cpu(0)).unwrap();
    let reader = tasks.pin(id).unwrap();
    assert_eq!(
        reader.address_space().summary().root_generation,
        tables.generation
    );
    tasks.cancel(id).unwrap();
    assert_eq!(
        tasks.reclaim(id).err(),
        Some(Error::Pool(PoolError::Pinned))
    );
    assert_eq!(
        manager.free(tables),
        Err(PhysicalMemoryError::AllocationRetained)
    );
    drop(reader);
    let resources = tasks.reclaim(id).unwrap();
    assert_eq!(
        manager.free(tables),
        Err(PhysicalMemoryError::AllocationRetained)
    );
    let (mut address, stack, ()) = resources.into_parts(&mut manager).ok().unwrap();
    stack
        .release_scrubbed(&mut manager, &mut memory)
        .ok()
        .unwrap();
    address.release(&mut manager, &mut memory).unwrap();
    assert_eq!(manager.free(tables), Err(PhysicalMemoryError::StaleHandle));
    assert_eq!(manager.summary().allocated_pages, 0);
}

fn cpu(value: u8) -> CpuId {
    CpuId::new(value).unwrap()
}

fn ack(ticket: sched::TransferTicket) -> sched::RemoteAck {
    sched::RemoteAck {
        target_cpu: ticket.target_cpu,
        attempt: ticket.request_attempt,
        sequence: ticket.request_sequence,
        operation: sched::CALL_FUNCTION_OPERATION,
        status: sched::ACK_ACCEPTED,
        error: sched::ERROR_NONE,
        result: sched::CALL_FUNCTION_RESULT,
    }
}

struct Payload(Arc<AtomicUsize>);
impl Drop for Payload {
    fn drop(&mut self) {
        self.0.fetch_add(1, Ordering::SeqCst);
    }
}

#[test]
fn retains_actual_space_until_last_reader_and_explicit_physical_release() {
    let (mut manager, mut memory) = fixture();
    let address = space(&mut manager, &mut memory);
    let root = address.summary();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 1, with_stack(address, 42, &mut manager).ok().unwrap())
        .ok()
        .unwrap();
    tasks.activate(id, cpu(0)).unwrap();
    let reader = tasks.pin(id).unwrap();
    assert_eq!(reader.address_space().summary(), root);
    assert_eq!(tasks.dispatch_local(cpu(0)).unwrap(), id);
    assert_eq!(tasks.snapshot(id).unwrap().state, TaskState::Dead);
    assert_eq!(
        tasks.reclaim(id).err(),
        Some(Error::Pool(PoolError::Pinned))
    );
    assert_eq!(
        tasks.pin(id).err().map(|e| e),
        Some(Error::Pool(PoolError::Retired))
    );
    assert_eq!(*reader.payload(), 42);
    drop(reader);
    let (mut address, stack, payload) = tasks
        .reclaim(id)
        .unwrap()
        .into_parts(&mut manager)
        .ok()
        .unwrap();
    assert_eq!(payload, 42);
    stack
        .release_scrubbed(&mut manager, &mut memory)
        .ok()
        .unwrap();
    assert_eq!(manager.summary().allocated_pages, 4);
    address.release(&mut manager, &mut memory).unwrap();
    assert_eq!(manager.summary().allocated_pages, 0);
    assert!(
        memory
            .pages
            .values()
            .all(|page| page.iter().all(|word| *word == 0))
    );
    assert_eq!(tasks.reclaim(id).err(), Some(Error::Missing));
}

#[test]
fn task_slot_cannot_recycle_until_reclaimed_and_old_generation_stays_stale() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let first = tasks
        .create(0, 1, 1, resource(&mut manager, &mut memory, 1))
        .ok()
        .unwrap();
    tasks.cancel_dormant(first).unwrap();
    let second = resource(&mut manager, &mut memory, 2);
    let (error, second) = tasks.create(0, 1, 1, second).err().unwrap();
    assert_eq!(error, Error::Occupied);
    let _first = tasks.reclaim(first).unwrap();
    let next = tasks.create(0, 1, 1, second).ok().unwrap();
    assert_eq!(next.generation, first.generation + 1);
    assert_eq!(tasks.pin(first).err(), Some(Error::Stale));
    assert_eq!(tasks.cancel(first), Err(Error::Stale));
    assert_eq!(*tasks.pin(next).unwrap().payload(), 2);
}

#[test]
fn rejects_bad_task_ids_without_indexing_or_state_mutation() {
    let mut store = Storage::<u64>::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let before = tasks.scheduler().summary();
    for id in [
        TaskId {
            slot: 255,
            generation: 1,
        },
        TaskId {
            slot: 0,
            generation: 0,
        },
    ] {
        assert!(tasks.pin(id).is_err());
        assert!(tasks.cancel(id).is_err());
        assert!(tasks.reclaim(id).is_err());
    }
    assert_eq!(tasks.scheduler().summary(), before);
}

#[test]
fn failed_scheduler_admission_returns_owned_resources_without_a_task() {
    let (mut manager, mut memory) = fixture();
    let drops = Arc::new(AtomicUsize::new(0));
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let mut resource = resource(&mut manager, &mut memory, Payload(drops.clone()));
    let root = resource.address_space().summary();
    for (slot, priority, affinity) in [(9, 1, 1), (0, 0, 1), (0, 32, 1), (0, 1, 0), (0, 1, 16)] {
        let before = tasks.scheduler().summary();
        let (_, returned) = tasks
            .create(slot, priority, affinity, resource)
            .err()
            .unwrap();
        resource = returned;
        assert_eq!(resource.address_space().summary(), root);
        assert_eq!(drops.load(Ordering::SeqCst), 0);
        assert_eq!(tasks.scheduler().summary(), before);
    }
    let id = tasks.create(0, 1, 1, resource).ok().unwrap();
    assert_eq!(id.generation, 1);
    tasks.cancel_dormant(id).unwrap();
    drop(tasks.reclaim(id).unwrap());
    assert_eq!(drops.load(Ordering::SeqCst), 1);
}

#[test]
fn cancellation_removes_runnable_and_blocked_ownership() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    for slot in 0..2 {
        let id = tasks
            .create(slot, 1, 15, resource(&mut manager, &mut memory, slot))
            .ok()
            .unwrap();
        tasks.activate(id, cpu(slot)).unwrap();
        if slot == 1 {
            tasks.block(id).unwrap();
        }
        assert_eq!(tasks.retire(id), Err(Error::NotDead));
        assert_eq!(tasks.reclaim(id).err(), Some(Error::NotRetired));
        tasks.cancel(id).unwrap();
        assert_eq!(tasks.scheduler().queue_len(cpu(slot)).unwrap(), 0);
        assert!(tasks.reclaim(id).is_ok());
    }
    tasks.scheduler().validate().unwrap();
}

#[test]
fn remote_transfer_running_and_bad_ack_cannot_reclaim() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 2, resource(&mut manager, &mut memory, 7))
        .ok()
        .unwrap();
    tasks.activate(id, cpu(1)).unwrap();
    let execution = tasks.stage_dispatch(cpu(1), 2, 3).unwrap();
    let ticket = execution.ticket();
    let before = tasks.scheduler().summary();
    let mut wrong = ack(ticket);
    wrong.sequence += 1;
    assert_eq!(
        tasks.acknowledge(ticket, wrong),
        Err(Error::Scheduler(sched::Error::Acknowledgement))
    );
    assert_eq!(tasks.scheduler().summary(), before);
    assert_eq!(
        tasks.cancel(id),
        Err(Error::Scheduler(sched::Error::PendingBusy))
    );
    assert_eq!(
        tasks.retire(id),
        Err(Error::Scheduler(sched::Error::PendingBusy))
    );
    assert_eq!(tasks.reclaim(id).err(), Some(Error::NotRetired));
    tasks.acknowledge(ticket, ack(ticket)).unwrap();
    assert_eq!(tasks.snapshot(id).unwrap().state, TaskState::Running);
    assert_eq!(tasks.cancel(id), Err(Error::Scheduler(sched::Error::State)));
    assert_eq!(tasks.retire(id), Err(Error::NotDead));
    let reader = tasks.pin(id).unwrap();
    tasks.complete_current(cpu(1)).unwrap();
    assert_eq!(
        tasks.reclaim(id).err(),
        Some(Error::Pool(PoolError::Pinned))
    );
    drop(reader);
    assert_eq!(
        tasks.reclaim(id).err(),
        Some(Error::Pool(PoolError::Pinned))
    );
    // SAFETY: this host harness never publishes a CPU context or hardware alias.
    unsafe { execution.confirm_quiescent() };
    assert!(tasks.reclaim(id).is_ok());
}

#[test]
fn offline_timeout_restores_scheduler_but_does_not_release_resources() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 1, resource(&mut manager, &mut memory, 9))
        .ok()
        .unwrap();
    tasks.activate(id, cpu(0)).unwrap();
    let snapshot = tasks.snapshot(id).unwrap();
    let reader = tasks.pin(id).unwrap();
    let ticket = tasks.stage_offline_probe(id, 1, 1).unwrap();
    let mut wrong = ticket;
    wrong.transaction += 1;
    assert_eq!(
        tasks.timeout_offline(wrong),
        Err(Error::Scheduler(sched::Error::TicketMismatch))
    );
    assert!(tasks.cancel(id).is_err());
    tasks.timeout_offline(ticket).unwrap();
    assert_eq!(tasks.snapshot(id).unwrap(), snapshot);
    assert_eq!(
        tasks.acknowledge(ticket, ack(ticket)),
        Err(Error::Scheduler(sched::Error::PendingMissing))
    );
    assert_eq!(manager.summary().allocated_pages, 8);
    tasks.cancel(id).unwrap();
    assert_eq!(
        tasks.reclaim(id).err(),
        Some(Error::Pool(PoolError::Pinned))
    );
    drop(reader);
    assert!(tasks.reclaim(id).is_ok());
}

#[test]
fn shutdown_seals_admission_but_allows_retirement_and_drain() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 1, resource(&mut manager, &mut memory, 4))
        .ok()
        .unwrap();
    let reader = tasks.pin(id).unwrap();
    tasks.begin_shutdown().unwrap();
    tasks.begin_shutdown().unwrap();
    assert!(!tasks.is_drained().unwrap());
    assert_eq!(tasks.pin(id).err(), Some(Error::Draining));
    assert_eq!(tasks.activate(id, cpu(0)), Err(Error::Draining));
    assert_eq!(tasks.dispatch_local(cpu(0)), Err(Error::Draining));
    let rejected = resource(&mut manager, &mut memory, 5);
    let (error, returned) = tasks.create(1, 1, 1, rejected).err().unwrap();
    assert_eq!(error, Error::Draining);
    assert_eq!(*returned.payload(), 5);
    tasks.cancel_dormant(id).unwrap();
    assert_eq!(
        tasks.reclaim(id).err(),
        Some(Error::Pool(PoolError::Pinned))
    );
    drop(reader);
    assert!(tasks.reclaim(id).is_ok());
    assert!(tasks.is_drained().unwrap());
}

#[test]
fn shutdown_with_pending_dispatch_retains_until_ack_completion_and_reader_drop() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 2, resource(&mut manager, &mut memory, 1))
        .ok()
        .unwrap();
    tasks.activate(id, cpu(1)).unwrap();
    let execution = tasks.stage_dispatch(cpu(1), 1, 1).unwrap();
    let ticket = execution.ticket();
    tasks.begin_shutdown().unwrap();
    assert!(!tasks.is_drained().unwrap());
    assert!(tasks.cancel(id).is_err());
    tasks.acknowledge(ticket, ack(ticket)).unwrap();
    tasks.complete_current(cpu(1)).unwrap();
    assert_eq!(
        tasks.reclaim(id).err(),
        Some(Error::Pool(PoolError::Pinned))
    );
    assert!(!tasks.is_drained().unwrap());
    // SAFETY: the host backend performs no CPU execution or architectural access.
    unsafe { execution.confirm_quiescent() };
    assert!(tasks.reclaim(id).is_ok());
    assert!(tasks.is_drained().unwrap());
}

#[test]
fn forgotten_reader_retains_capacity_without_forced_reclamation() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 1, resource(&mut manager, &mut memory, 1))
        .ok()
        .unwrap();
    std::mem::forget(tasks.pin(id).unwrap());
    tasks.cancel_dormant(id).unwrap();
    tasks.begin_shutdown().unwrap();
    for _ in 0..32 {
        assert_eq!(
            tasks.reclaim(id).err(),
            Some(Error::Pool(PoolError::Pinned))
        );
        assert!(!tasks.is_drained().unwrap());
        assert_eq!(manager.summary().allocated_pages, 8);
    }
}

#[test]
fn scoped_host_readers_survive_task_retirement() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 1, resource(&mut manager, &mut memory, 17))
        .ok()
        .unwrap();
    let ready = Barrier::new(5);
    let release = Barrier::new(5);
    std::thread::scope(|scope| {
        for _ in 0..4 {
            let reader = tasks.pin(id).unwrap();
            let (ready, release) = (&ready, &release);
            scope.spawn(move || {
                ready.wait();
                release.wait();
                assert_eq!(*reader.payload(), 17);
                assert!(!reader.address_space().summary().root_released);
            });
        }
        ready.wait();
        tasks.cancel_dormant(id).unwrap();
        assert_eq!(
            tasks.reclaim(id).err(),
            Some(Error::Pool(PoolError::Pinned))
        );
        release.wait();
    });
    assert!(tasks.reclaim(id).is_ok());
}

#[test]
fn bounded_generations_exhaust_without_wrapping_or_losing_value() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits {
        pins_per_object: 1,
        generations_per_slot: 1,
    })
    .unwrap();
    let mut tasks = store.attach().unwrap();
    let mut resources = resource(&mut manager, &mut memory, 1);
    for generation in 1..=8 {
        let id = tasks.create(0, 1, 1, resources).ok().unwrap();
        assert_eq!(id.generation, generation);
        tasks.cancel_dormant(id).unwrap();
        resources = tasks.reclaim(id).unwrap();
    }
    let before = tasks.scheduler().summary();
    let (error, resources) = tasks.create(0, 1, 1, resources).err().unwrap();
    assert_eq!(error, Error::Pool(PoolError::GenerationExhausted));
    assert_eq!(tasks.scheduler().summary(), before);
    assert_eq!(*resources.payload(), 1);
}

#[test]
fn pin_budget_failure_preserves_existing_reader_and_state() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits {
        pins_per_object: 1,
        generations_per_slot: 2,
    })
    .unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 1, resource(&mut manager, &mut memory, 3))
        .ok()
        .unwrap();
    let reader = tasks.pin(id).unwrap();
    assert_eq!(tasks.pin(id).err(), Some(Error::Pool(PoolError::PinLimit)));
    drop(reader);
    assert!(tasks.pin(id).is_ok());
}

#[test]
fn controller_drop_retains_readers_and_forbids_namespace_reset() {
    let (mut manager, mut memory) = fixture();
    let drops = Arc::new(AtomicUsize::new(0));
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(
            0,
            1,
            1,
            resource(&mut manager, &mut memory, Payload(drops.clone())),
        )
        .ok()
        .unwrap();
    let reader = tasks.pin(id).unwrap();
    drop(tasks);
    assert_eq!(reader.address_space().summary().table_pages, 4);
    assert_eq!(drops.load(Ordering::SeqCst), 0);
    drop(reader);
    assert_eq!(store.attach().err().map(|e| e), Some(Error::Attached));
    drop(store);
    assert_eq!(drops.load(Ordering::SeqCst), 1);
    assert_eq!(manager.summary().allocated_pages, 8);
}

#[test]
fn rejects_already_released_address_space() {
    let (mut manager, mut memory) = fixture();
    let mut address = space(&mut manager, &mut memory);
    address.release(&mut manager, &mut memory).unwrap();
    let (error, address, stack, payload) = with_stack(address, 2, &mut manager).err().unwrap();
    assert_eq!(error, Error::AddressSpace);
    assert!(address.summary().root_released);
    assert_eq!(payload, 2);
    manager.free(stack).unwrap();
}

#[test]
fn mapped_space_keeps_frame_and_unmap_receipt_until_owned_again() {
    let (mut manager, mut memory) = fixture();
    let mut address = space(&mut manager, &mut memory);
    let frame = manager.allocate(Zone::Dma32, 1, vm::DATA_OWNER).unwrap();
    address
        .map(
            &manager,
            &mut memory,
            vm::USER_WINDOW_START,
            frame,
            vm::Permissions::USER_RW,
            vm::CachePolicy::WriteBack,
        )
        .unwrap();
    let pending = address
        .begin_unmap(&mut memory, vm::USER_WINDOW_START)
        .unwrap();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 1, with_stack(address, 1, &mut manager).ok().unwrap())
        .ok()
        .unwrap();
    let reader = tasks.pin(id).unwrap();
    tasks.cancel_dormant(id).unwrap();
    assert_eq!(reader.address_space().summary().pending_invalidations, 1);
    assert_eq!(manager.summary().allocated_pages, 9);
    drop(reader);
    let (mut address, stack, _) = tasks
        .reclaim(id)
        .unwrap()
        .into_parts(&mut manager)
        .ok()
        .unwrap();
    assert_eq!(
        address.release(&mut manager, &mut memory),
        Err(vm::Error::ReleaseBusy)
    );
    address.acknowledge_inactive(pending).unwrap();
    address.complete_unmap(&mut manager, pending).unwrap();
    address.release(&mut manager, &mut memory).unwrap();
    stack
        .release_scrubbed(&mut manager, &mut memory)
        .ok()
        .unwrap();
    assert_eq!(manager.summary().allocated_pages, 0);
}

#[test]
fn all_eight_task_slots_recycle_with_exact_destructor_counts() {
    let drops = Arc::new(AtomicUsize::new(0));
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    for _ in 0..16 {
        // Keep the same scheduler/pool namespace for all 128 generations.
        // Each fully drained PMM batch has its own finite scrub-evidence ledger.
        let (mut manager, mut memory) = fixture();
        let ids: Vec<_> = (0..8)
            .map(|slot| {
                tasks
                    .create(
                        slot,
                        1,
                        15,
                        resource(&mut manager, &mut memory, Payload(drops.clone())),
                    )
                    .ok()
                    .unwrap()
            })
            .collect();
        for id in ids {
            tasks.cancel_dormant(id).unwrap();
            let (mut address, stack, payload) = tasks
                .reclaim(id)
                .unwrap()
                .into_parts(&mut manager)
                .ok()
                .unwrap();
            address.release(&mut manager, &mut memory).unwrap();
            stack
                .release_scrubbed(&mut manager, &mut memory)
                .ok()
                .unwrap();
            drop(payload);
        }
        assert_eq!(manager.summary().allocated_pages, 0);
        tasks.scheduler().validate().unwrap();
    }
    assert_eq!(drops.load(Ordering::SeqCst), 128);
    tasks.begin_shutdown().unwrap();
    assert!(tasks.is_drained().unwrap());
}

#[test]
fn invalid_requests_do_not_consume_finite_pool_generation_budget() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits {
        pins_per_object: 1,
        generations_per_slot: 1,
    })
    .unwrap();
    let mut tasks = store.attach().unwrap();
    let mut resources = resource(&mut manager, &mut memory, 1);
    for _ in 0..64 {
        let (error, returned) = tasks.create(0, 0, 1, resources).err().unwrap();
        assert_eq!(error, Error::Scheduler(sched::Error::Priority));
        resources = returned;
    }
    assert!(tasks.create(0, 1, 1, resources).is_ok());
}

#[test]
fn duplicate_root_is_rejected_even_while_first_owner_is_retired() {
    let (mut manager, mut memory) = fixture();
    let tables = manager
        .allocate(Zone::Dma32, vm::TABLE_PAGE_COUNT, vm::TABLE_OWNER)
        .unwrap();
    let first = AddressSpace::initialize(&manager, tables, &mut memory).unwrap();
    // Duplicated inactive metadata must not admit a second physical owner.
    let duplicate = AddressSpace::initialize(&manager, tables, &mut memory).unwrap();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 1, with_stack(first, 1, &mut manager).ok().unwrap())
        .ok()
        .unwrap();
    tasks.cancel_dormant(id).unwrap();
    let before = tasks.scheduler().summary();
    let (error, returned, stack, payload) = with_stack(duplicate, 2, &mut manager).err().unwrap();
    assert_eq!(
        error,
        Error::PhysicalMemory(
            poolekernel::physical_memory::PhysicalMemoryError::AllocationRetained
        )
    );
    assert_eq!(returned.summary().root_generation, tables.generation);
    assert_eq!(payload, 2);
    assert_eq!(tasks.scheduler().summary(), before);
    manager.free(stack).unwrap();
}

#[test]
fn all_frames_aliases_and_pending_unmaps_are_mandatorily_retained() {
    let (mut manager, mut memory) = fixture();
    let tables = manager
        .allocate(Zone::Dma32, vm::TABLE_PAGE_COUNT, vm::TABLE_OWNER)
        .unwrap();
    let mut address = AddressSpace::initialize(&manager, tables, &mut memory).unwrap();
    let mut frames = Vec::new();
    for index in 0..vm::MAX_FRAMES {
        let frame = manager.allocate(Zone::Dma32, 1, vm::DATA_OWNER).unwrap();
        address
            .map(
                &manager,
                &mut memory,
                vm::USER_WINDOW_START + index as u64 * 4096,
                frame,
                vm::Permissions::USER_RW,
                vm::CachePolicy::WriteBack,
            )
            .unwrap();
        frames.push(frame);
    }
    let alias = vm::USER_WINDOW_START + 4 * 4096;
    address
        .map(
            &manager,
            &mut memory,
            alias,
            frames[0],
            vm::Permissions::USER_RW,
            vm::CachePolicy::WriteBack,
        )
        .unwrap();
    let pending = address
        .begin_unmap(&mut memory, vm::USER_WINDOW_START + 4096)
        .unwrap();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 2, with_stack(address, (), &mut manager).ok().unwrap())
        .ok()
        .unwrap();
    tasks.activate(id, cpu(1)).unwrap();
    let reader = tasks.pin(id).unwrap();
    let execution = tasks.stage_dispatch(cpu(1), 99, 1).unwrap();
    let ticket = execution.ticket();
    for handle in std::iter::once(tables).chain(frames.iter().copied()) {
        assert_eq!(
            manager.free(handle),
            Err(PhysicalMemoryError::AllocationRetained)
        );
    }
    tasks.acknowledge(ticket, ack(ticket)).unwrap();
    assert_eq!(tasks.complete_current(cpu(1)).unwrap(), id);
    assert_eq!(
        tasks.reclaim(id).err(),
        Some(Error::Pool(PoolError::Pinned))
    );
    assert_eq!(
        reader.address_space().summary().bound_frames,
        vm::MAX_FRAMES
    );
    drop(reader);
    assert_eq!(
        tasks.reclaim(id).err(),
        Some(Error::Pool(PoolError::Pinned))
    );
    // SAFETY: no CPU or external actor ever accessed these host-owned pages.
    unsafe { execution.confirm_quiescent() };
    let resources = tasks.reclaim(id).unwrap();
    for handle in std::iter::once(tables).chain(frames.iter().copied()) {
        assert_eq!(
            manager.free(handle),
            Err(PhysicalMemoryError::AllocationRetained)
        );
    }
    let (mut address, stack, ()) = resources.into_parts(&mut manager).ok().unwrap();
    address.acknowledge_inactive(pending).unwrap();
    address.complete_unmap(&mut manager, pending).unwrap();
    for index in [0, 2, 3, 4] {
        let pending = address
            .begin_unmap(&mut memory, vm::USER_WINDOW_START + index * 4096)
            .unwrap();
        address.acknowledge_inactive(pending).unwrap();
        address.complete_unmap(&mut manager, pending).unwrap();
    }
    address.release(&mut manager, &mut memory).unwrap();
    stack
        .release_scrubbed(&mut manager, &mut memory)
        .ok()
        .unwrap();
    assert_eq!(manager.summary().allocated_pages, 0);
}

#[test]
fn late_frame_retention_failure_returns_original_space_and_payload() {
    let (mut manager, mut memory) = fixture();
    let tables = manager
        .allocate(Zone::Dma32, vm::TABLE_PAGE_COUNT, vm::TABLE_OWNER)
        .unwrap();
    let mut address = AddressSpace::initialize(&manager, tables, &mut memory).unwrap();
    let frame = manager.allocate(Zone::Dma32, 1, vm::DATA_OWNER).unwrap();
    address
        .map(
            &manager,
            &mut memory,
            vm::USER_WINDOW_START,
            frame,
            vm::Permissions::USER_RW,
            vm::CachePolicy::WriteBack,
        )
        .unwrap();
    let conflict = manager.retain_allocation(frame).unwrap();
    let before = address.summary();
    let drops = Arc::new(AtomicUsize::new(0));
    let (error, address, stack, payload) =
        with_stack(address, Payload(drops.clone()), &mut manager)
            .err()
            .unwrap();
    assert_eq!(
        error,
        Error::PhysicalMemory(PhysicalMemoryError::AllocationRetained)
    );
    assert_eq!(address.summary(), before);
    assert_eq!(drops.load(Ordering::SeqCst), 0);
    let tables_token = manager.retain_allocation(tables).unwrap();
    manager.release_retention(tables_token).unwrap();
    manager.release_retention(conflict).unwrap();
    let resources = Resources::new(address, stack, payload, &mut manager)
        .ok()
        .unwrap();
    drop(resources);
    assert_eq!(drops.load(Ordering::SeqCst), 1);
    for handle in [tables, frame, stack] {
        assert_eq!(
            manager.free(handle),
            Err(PhysicalMemoryError::AllocationRetained)
        );
    }
}

#[test]
fn failed_owner_release_returns_retention_for_retry_with_original_manager() {
    let (mut manager, mut memory) = fixture();
    let (mut other, mut other_memory) = fixture();
    let resources = resource(&mut manager, &mut memory, 41);
    let other_resources = resource(&mut other, &mut other_memory, 42);
    let summary = resources.address_space().summary();
    let (error, resources) = resources.into_parts(&mut other).err().unwrap();
    assert_eq!(
        error,
        Error::PhysicalMemory(PhysicalMemoryError::RetentionIdentity)
    );
    assert_eq!(resources.address_space().summary(), summary);
    assert_eq!(*resources.payload(), 41);
    let (mut address, stack, _) = resources.into_parts(&mut manager).ok().unwrap();
    address.release(&mut manager, &mut memory).unwrap();
    stack
        .release_scrubbed(&mut manager, &mut memory)
        .ok()
        .unwrap();
    let (mut address, stack, _) = other_resources.into_parts(&mut other).ok().unwrap();
    address.release(&mut other, &mut other_memory).unwrap();
    stack
        .release_scrubbed(&mut other, &mut other_memory)
        .ok()
        .unwrap();
    assert_eq!(manager.summary().allocated_pages, 0);
    assert_eq!(other.summary().allocated_pages, 0);
}

#[test]
fn scheduler_rejects_duplicate_physical_roots_from_distinct_manager_namespaces() {
    let (mut manager, mut memory) = fixture();
    let (mut other, mut other_memory) = fixture();
    let first = resource(&mut manager, &mut memory, 1);
    let second = resource(&mut other, &mut other_memory, 2);
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks.create(0, 1, 1, first).ok().unwrap();
    tasks.cancel_dormant(id).unwrap();
    let (error, returned) = tasks.create(1, 1, 1, second).err().unwrap();
    assert_eq!(error, Error::DuplicateRoot);
    assert_eq!(*returned.payload(), 2);
}

#[test]
fn stack_retention_survives_task_reclaim_until_full_scrubbed_release() {
    let (mut manager, mut memory) = fixture();
    let resources = resource(&mut manager, &mut memory, 7);
    let handle = resources.execution_stack().handle();
    let mut storage = Storage::new(Limits::default()).unwrap();
    let mut tasks = storage.attach().unwrap();
    let id = tasks.create(0, 1, 1, resources).ok().unwrap();
    tasks.cancel_dormant(id).unwrap();
    let (mut address, stack, payload) = tasks
        .reclaim(id)
        .unwrap()
        .into_parts(&mut manager)
        .ok()
        .unwrap();
    assert_eq!(payload, 7);
    assert_eq!(
        manager.free(handle),
        Err(PhysicalMemoryError::AllocationRetained)
    );
    address.release(&mut manager, &mut memory).unwrap();
    assert_eq!(manager.summary().allocated_pages, STACK_PAGE_COUNT);
    let receipt = stack
        .release_scrubbed(&mut manager, &mut memory)
        .ok()
        .unwrap();
    assert_eq!(
        (
            receipt.generation,
            receipt.start_page,
            receipt.page_count,
            receipt.owner
        ),
        (
            handle.generation,
            handle.start_page,
            STACK_PAGE_COUNT,
            STACK_OWNER
        )
    );
    assert_eq!(
        (receipt.zeroed_bytes, receipt.verified_bytes),
        (16384, 16384)
    );
    assert_eq!(memory.physical_writes, 2048);
    assert_eq!(memory.physical_reads, 2048);
    assert_eq!(manager.summary().allocated_pages, 0);
    assert_eq!(manager.free(handle), Err(PhysicalMemoryError::StaleHandle));
}

#[test]
fn invalid_stack_layout_returns_every_input_without_retaining_tables() {
    for (pages, owner) in [
        (1, STACK_OWNER),
        (3, STACK_OWNER),
        (5, STACK_OWNER),
        (4, STACK_OWNER + 1),
    ] {
        let (mut manager, mut memory) = fixture();
        let address = space(&mut manager, &mut memory);
        let stack = manager.allocate(Zone::Dma32, pages, owner).unwrap();
        let before = manager.summary();
        let drops = Arc::new(AtomicUsize::new(0));
        let (error, mut address, returned, payload) =
            Resources::new(address, stack, Payload(drops.clone()), &mut manager)
                .err()
                .unwrap();
        assert_eq!(error, Error::StackLayout);
        assert_eq!(returned, stack);
        assert_eq!(manager.summary(), before);
        assert_eq!(drops.load(Ordering::SeqCst), 0);
        address.release(&mut manager, &mut memory).unwrap();
        manager.free(returned).unwrap();
        assert_eq!(manager.summary().allocated_pages, 0);
        drop(payload);
        assert_eq!(drops.load(Ordering::SeqCst), 1);
    }
}

#[test]
fn stale_stack_handle_cannot_retain_a_replacement_allocation() {
    let (mut manager, mut memory) = fixture();
    let address = space(&mut manager, &mut memory);
    let stale = manager
        .allocate(Zone::Dma32, STACK_PAGE_COUNT, STACK_OWNER)
        .unwrap();
    manager.free(stale).unwrap();
    let replacement = manager
        .allocate(Zone::Dma32, STACK_PAGE_COUNT, STACK_OWNER)
        .unwrap();
    let (_, mut address, returned, ()) = Resources::new(address, stale, (), &mut manager)
        .err()
        .unwrap();
    assert_eq!(returned, stale);
    address.release(&mut manager, &mut memory).unwrap();
    manager.free(replacement).unwrap();
    assert_eq!(manager.summary().allocated_pages, 0);
}

#[test]
fn late_stack_retention_conflict_leaves_all_tables_and_frames_unretained() {
    let (mut manager, mut memory) = fixture();
    let mut address = space(&mut manager, &mut memory);
    let frame = manager.allocate(Zone::Dma32, 1, vm::DATA_OWNER).unwrap();
    address
        .map(
            &manager,
            &mut memory,
            vm::USER_WINDOW_START,
            frame,
            vm::Permissions::USER_RW,
            vm::CachePolicy::WriteBack,
        )
        .unwrap();
    let stack = manager
        .allocate(Zone::Dma32, STACK_PAGE_COUNT, STACK_OWNER)
        .unwrap();
    let conflict = manager.retain_allocation(stack).unwrap();
    let before = manager.summary();
    let (error, mut address, returned, payload) = Resources::new(address, stack, 21, &mut manager)
        .err()
        .unwrap();
    assert_eq!(
        error,
        Error::PhysicalMemory(PhysicalMemoryError::AllocationRetained)
    );
    assert_eq!((returned, payload), (stack, 21));
    assert_eq!(manager.summary(), before);
    let frame_token = manager.retain_allocation(frame).unwrap();
    manager.release_retention(frame_token).unwrap();
    let pending = address
        .begin_unmap(&mut memory, vm::USER_WINDOW_START)
        .unwrap();
    address.acknowledge_inactive(pending).unwrap();
    address.complete_unmap(&mut manager, pending).unwrap();
    address.release(&mut manager, &mut memory).unwrap();
    manager.release_retention(conflict).unwrap();
    manager.free(stack).unwrap();
    assert_eq!(manager.summary().allocated_pages, 0);
}

#[test]
fn failed_stack_scrub_keeps_owner_and_allocation_for_retry() {
    for failure in 0..7 {
        let (mut manager, mut memory) = fixture();
        let resources = resource(&mut manager, &mut memory, ());
        let (mut address, stack, ()) = resources.into_parts(&mut manager).ok().unwrap();
        address.release(&mut manager, &mut memory).unwrap();
        let handle = stack.handle();
        match failure {
            0..=2 => memory.fail_write_after = Some([0, 513, 2047][failure]),
            3..=5 => memory.fail_read_after = Some([0, 513, 2047][failure - 3]),
            _ => memory.corrupt_read = true,
        }
        let (_, stack) = stack
            .release_scrubbed(&mut manager, &mut memory)
            .err()
            .unwrap();
        assert_eq!(stack.handle(), handle);
        assert_eq!(manager.summary().allocated_pages, STACK_PAGE_COUNT);
        assert_eq!(
            manager.free(handle),
            Err(PhysicalMemoryError::AllocationRetained)
        );
        memory.fail_write_after = None;
        memory.fail_read_after = None;
        memory.corrupt_read = false;
        let receipt = stack
            .release_scrubbed(&mut manager, &mut memory)
            .ok()
            .unwrap();
        assert_eq!(
            (receipt.zeroed_bytes, receipt.verified_bytes),
            (16384, 16384)
        );
        assert_eq!(manager.summary().allocated_pages, 0);
    }
}

#[test]
fn stack_release_on_wrong_manager_is_rejected_before_physical_access() {
    let (mut manager, mut memory) = fixture();
    let (mut other, mut other_memory) = fixture();
    let resources = resource(&mut manager, &mut memory, ());
    let other_resources = resource(&mut other, &mut other_memory, ());
    let (mut address, stack, ()) = resources.into_parts(&mut manager).ok().unwrap();
    let handle = stack.handle();
    let (_, stack) = stack
        .release_scrubbed(&mut other, &mut other_memory)
        .err()
        .unwrap();
    assert_eq!(
        (other_memory.physical_writes, other_memory.physical_reads),
        (0, 0)
    );
    assert_eq!(stack.handle(), handle);
    assert_eq!(
        manager.free(handle),
        Err(PhysicalMemoryError::AllocationRetained)
    );
    assert_eq!(
        other.free(other_resources.execution_stack().handle()),
        Err(PhysicalMemoryError::AllocationRetained)
    );
    address.release(&mut manager, &mut memory).unwrap();
    stack
        .release_scrubbed(&mut manager, &mut memory)
        .ok()
        .unwrap();
}

#[test]
fn losing_stack_owner_never_silently_releases_pages() {
    for forget in [false, true] {
        let (mut manager, mut memory) = fixture();
        let resources = resource(&mut manager, &mut memory, ());
        let (mut address, stack, ()) = resources.into_parts(&mut manager).ok().unwrap();
        let handle = stack.handle();
        address.release(&mut manager, &mut memory).unwrap();
        if forget {
            std::mem::forget(stack);
        } else {
            drop(stack);
        }
        assert_eq!(
            manager.free(handle),
            Err(PhysicalMemoryError::AllocationRetained)
        );
        assert_eq!(manager.summary().allocated_pages, STACK_PAGE_COUNT);
        assert_eq!((memory.physical_writes, memory.physical_reads), (0, 0));
    }
}

#[test]
fn overlapping_stacks_from_distinct_manager_namespaces_cannot_share_scheduler() {
    let (mut manager, mut memory) = fixture();
    let (mut other, mut other_memory) = fixture();
    let first = resource(&mut manager, &mut memory, 1);
    let _offset = other.allocate(Zone::Dma32, 1, vm::DATA_OWNER).unwrap();
    let second = resource(&mut other, &mut other_memory, 2);
    let first_stack = first.execution_stack().handle();
    let second_stack = second.execution_stack().handle();
    assert_ne!(
        first.address_space().summary().root_physical,
        second.address_space().summary().root_physical
    );
    assert!(second_stack.start_page < first_stack.start_page + first_stack.page_count);
    let mut storage = Storage::new(Limits::default()).unwrap();
    let mut tasks = storage.attach().unwrap();
    let id = tasks.create(0, 1, 1, first).ok().unwrap();
    tasks.cancel_dormant(id).unwrap();
    let before = tasks.scheduler().summary();
    let (error, returned) = tasks.create(1, 1, 1, second).err().unwrap();
    assert_eq!(error, Error::DuplicateStack);
    assert_eq!(returned.execution_stack().handle(), second_stack);
    assert_eq!(tasks.scheduler().summary(), before);
    assert_eq!(
        other.free(second_stack),
        Err(PhysicalMemoryError::AllocationRetained)
    );
}

#[test]
fn full_scrub_receipt_ledger_retains_the_next_stack_without_writes() {
    let (mut manager, mut memory) = fixture();
    for _ in 0..poolekernel::physical_memory::MAX_SCRUB_RECEIPTS {
        let resources = resource(&mut manager, &mut memory, ());
        let (mut address, stack, ()) = resources.into_parts(&mut manager).ok().unwrap();
        address.release(&mut manager, &mut memory).unwrap();
        stack
            .release_scrubbed(&mut manager, &mut memory)
            .ok()
            .unwrap();
        assert_eq!(manager.summary().allocated_pages, 0);
    }
    let resources = resource(&mut manager, &mut memory, ());
    let (mut address, stack, ()) = resources.into_parts(&mut manager).ok().unwrap();
    address.release(&mut manager, &mut memory).unwrap();
    let before = manager.summary();
    let accesses = (memory.physical_writes, memory.physical_reads);
    let handle = stack.handle();
    let (error, stack) = stack
        .release_scrubbed(&mut manager, &mut memory)
        .err()
        .unwrap();
    assert_eq!(error, PhysicalMemoryError::ReceiptCapacity);
    assert_eq!(stack.handle(), handle);
    assert_eq!(manager.summary(), before);
    assert_eq!((memory.physical_writes, memory.physical_reads), accesses);
    assert_eq!(
        manager.free(handle),
        Err(PhysicalMemoryError::AllocationRetained)
    );
}
