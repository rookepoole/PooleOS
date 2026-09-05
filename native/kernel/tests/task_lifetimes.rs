use std::collections::BTreeMap;
use std::sync::{
    Arc, Barrier,
    atomic::{AtomicUsize, Ordering},
};

use poole_handoff::*;
use poolekernel::physical_memory::{PhysicalMemoryManager, Zone};
use poolekernel::reclamation::task_lifetimes::{Error, Resources, Storage};
use poolekernel::reclamation::{Error as PoolError, Limits};
use poolekernel::scheduler_smp::{self as sched, CpuId, TaskId, TaskState};
use poolekernel::virtual_memory::{self as vm, AddressSpace, TableMemory};

#[derive(Default)]
struct Memory {
    pages: BTreeMap<u64, [u64; 512]>,
    writes: u64,
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
        .create(0, 1, 1, Resources::new(address, 42))
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
    let (mut address, payload) = tasks.reclaim(id).unwrap().into_parts();
    assert_eq!(payload, 42);
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
        .create(0, 1, 1, Resources::new(space(&mut manager, &mut memory), 1))
        .ok()
        .unwrap();
    tasks.cancel_dormant(first).unwrap();
    let second = Resources::new(space(&mut manager, &mut memory), 2);
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
    let mut resource = Resources::new(space(&mut manager, &mut memory), Payload(drops.clone()));
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
            .create(
                slot,
                1,
                15,
                Resources::new(space(&mut manager, &mut memory), slot),
            )
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
        .create(0, 1, 2, Resources::new(space(&mut manager, &mut memory), 7))
        .ok()
        .unwrap();
    tasks.activate(id, cpu(1)).unwrap();
    let ticket = tasks.stage_dispatch(cpu(1), 2, 3).unwrap();
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
    assert!(tasks.reclaim(id).is_ok());
}

#[test]
fn offline_timeout_restores_scheduler_but_does_not_release_resources() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 1, Resources::new(space(&mut manager, &mut memory), 9))
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
    assert_eq!(manager.summary().allocated_pages, 4);
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
        .create(0, 1, 1, Resources::new(space(&mut manager, &mut memory), 4))
        .ok()
        .unwrap();
    let reader = tasks.pin(id).unwrap();
    tasks.begin_shutdown().unwrap();
    tasks.begin_shutdown().unwrap();
    assert!(!tasks.is_drained().unwrap());
    assert_eq!(tasks.pin(id).err(), Some(Error::Draining));
    assert_eq!(tasks.activate(id, cpu(0)), Err(Error::Draining));
    assert_eq!(tasks.dispatch_local(cpu(0)), Err(Error::Draining));
    let rejected = Resources::new(space(&mut manager, &mut memory), 5);
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
        .create(0, 1, 2, Resources::new(space(&mut manager, &mut memory), 1))
        .ok()
        .unwrap();
    tasks.activate(id, cpu(1)).unwrap();
    let ticket = tasks.stage_dispatch(cpu(1), 1, 1).unwrap();
    tasks.begin_shutdown().unwrap();
    assert!(!tasks.is_drained().unwrap());
    assert!(tasks.cancel(id).is_err());
    tasks.acknowledge(ticket, ack(ticket)).unwrap();
    tasks.complete_current(cpu(1)).unwrap();
    assert!(tasks.reclaim(id).is_ok());
    assert!(tasks.is_drained().unwrap());
}

#[test]
fn forgotten_reader_retains_capacity_without_forced_reclamation() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 1, Resources::new(space(&mut manager, &mut memory), 1))
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
        assert_eq!(manager.summary().allocated_pages, 4);
    }
}

#[test]
fn scoped_host_readers_survive_task_retirement() {
    let (mut manager, mut memory) = fixture();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(
            0,
            1,
            1,
            Resources::new(space(&mut manager, &mut memory), 17),
        )
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
    let mut resources = Resources::new(space(&mut manager, &mut memory), 1);
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
        .create(0, 1, 1, Resources::new(space(&mut manager, &mut memory), 3))
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
            Resources::new(space(&mut manager, &mut memory), Payload(drops.clone())),
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
    assert_eq!(manager.summary().allocated_pages, 4);
}

#[test]
fn rejects_already_released_address_space() {
    let (mut manager, mut memory) = fixture();
    let mut address = space(&mut manager, &mut memory);
    address.release(&mut manager, &mut memory).unwrap();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let (error, resources) = tasks
        .create(0, 1, 1, Resources::new(address, 2))
        .err()
        .unwrap();
    assert_eq!(error, Error::AddressSpace);
    assert!(resources.address_space().summary().root_released);
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
        .create(0, 1, 1, Resources::new(address, 1))
        .ok()
        .unwrap();
    let reader = tasks.pin(id).unwrap();
    tasks.cancel_dormant(id).unwrap();
    assert_eq!(reader.address_space().summary().pending_invalidations, 1);
    assert_eq!(manager.summary().allocated_pages, 5);
    drop(reader);
    let (mut address, _) = tasks.reclaim(id).unwrap().into_parts();
    assert_eq!(
        address.release(&mut manager, &mut memory),
        Err(vm::Error::ReleaseBusy)
    );
    address.acknowledge_inactive(pending).unwrap();
    address.complete_unmap(&mut manager, pending).unwrap();
    address.release(&mut manager, &mut memory).unwrap();
    assert_eq!(manager.summary().allocated_pages, 0);
}

#[test]
fn all_eight_task_slots_recycle_with_exact_destructor_counts() {
    let (mut manager, mut memory) = fixture();
    let drops = Arc::new(AtomicUsize::new(0));
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    for _ in 0..16 {
        let ids: Vec<_> = (0..8)
            .map(|slot| {
                tasks
                    .create(
                        slot,
                        1,
                        15,
                        Resources::new(space(&mut manager, &mut memory), Payload(drops.clone())),
                    )
                    .ok()
                    .unwrap()
            })
            .collect();
        for id in ids {
            tasks.cancel_dormant(id).unwrap();
            let (mut address, payload) = tasks.reclaim(id).unwrap().into_parts();
            address.release(&mut manager, &mut memory).unwrap();
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
    let mut resources = Resources::new(space(&mut manager, &mut memory), 1);
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
    // The caller can currently duplicate PKVM1 metadata using its copyable PMM
    // handle. Admission must reject two task owners of that physical root.
    let duplicate = AddressSpace::initialize(&manager, tables, &mut memory).unwrap();
    let mut store = Storage::new(Limits::default()).unwrap();
    let mut tasks = store.attach().unwrap();
    let id = tasks
        .create(0, 1, 1, Resources::new(first, 1))
        .ok()
        .unwrap();
    tasks.cancel_dormant(id).unwrap();
    let before = tasks.scheduler().summary();
    let (error, returned) = tasks
        .create(1, 1, 1, Resources::new(duplicate, 2))
        .err()
        .unwrap();
    assert_eq!(error, Error::DuplicateRoot);
    assert_eq!(*returned.payload(), 2);
    assert_eq!(tasks.scheduler().summary(), before);
}
