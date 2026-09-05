use super::*;

fn manager() -> PhysicalMemoryManager {
    let (bytes, core) = fixture();
    PhysicalMemoryManager::from_handoff(&poole_handoff::decode(&bytes).unwrap(), core, 128).unwrap()
}

fn rejects_all_free_paths(
    manager: &mut PhysicalMemoryManager,
    access: &mut FakePageAccess,
    handle: AllocationHandle,
) {
    let before = manager.summary();
    let io = (access.write_count, access.read_count);
    assert_eq!(
        manager.free(handle),
        Err(PhysicalMemoryError::AllocationRetained)
    );
    assert_eq!(
        manager.free_scrubbed(handle, access),
        Err(PhysicalMemoryError::AllocationRetained)
    );
    assert_eq!(
        manager.free_scrubbed_automatic(handle, access),
        Err(PhysicalMemoryError::AllocationRetained)
    );
    assert_eq!(manager.summary(), before);
    assert_eq!((access.write_count, access.read_count), io);
    assert_eq!(manager.validate_allocation(handle), Ok(()));
}

#[test]
fn copied_handles_cannot_scrub_grow_or_free_retained_pages() {
    let mut manager = manager();
    let handle = manager.allocate(Zone::Dma32, 2, 7).unwrap();
    let retained = manager.retain_allocation(handle).unwrap();
    assert_eq!(retained.handle(), handle);
    assert_eq!(
        manager.retain_allocation(handle).unwrap_err(),
        PhysicalMemoryError::AllocationRetained
    );
    let mut access = FakePageAccess::new(handle.start_page, 2, STALE_PATTERN);
    rejects_all_free_paths(&mut manager, &mut access, handle);
    assert!(access.words.iter().all(|word| *word == STALE_PATTERN));
    let returned = manager.release_retention(retained).unwrap();
    assert_eq!(returned, handle);
    assert_eq!(manager.summary().allocated_pages, 2);
    let receipt = manager.free_scrubbed(returned, &mut access).unwrap();
    assert_eq!(receipt.verified_bytes, 2 * PAGE_BYTES);
    assert_eq!(manager.free(handle), Err(PhysicalMemoryError::StaleHandle));
}

#[test]
fn equal_handles_in_distinct_managers_cannot_release_each_others_retention() {
    let mut first = manager();
    let mut second = manager();
    let a = first.allocate(Zone::Dma32, 1, 7).unwrap();
    let b = second.allocate(Zone::Dma32, 1, 7).unwrap();
    assert_eq!(a, b);
    let retained_a = first.retain_allocation(a).unwrap();
    let retained_b = second.retain_allocation(b).unwrap();
    let before = second.summary();
    let (error, retained_a) = second.release_retention(retained_a).unwrap_err();
    assert_eq!(error, PhysicalMemoryError::RetentionIdentity);
    assert_eq!(second.summary(), before);
    assert_eq!(first.free(a), Err(PhysicalMemoryError::AllocationRetained));
    assert_eq!(second.free(b), Err(PhysicalMemoryError::AllocationRetained));
    first.release_retention(retained_a).unwrap();
    second.release_retention(retained_b).unwrap();
    first.free(a).unwrap();
    second.free(b).unwrap();
}

#[test]
fn lost_tokens_retain_pages_and_live_tokens_survive_manager_moves() {
    let mut first = manager();
    let a = first.allocate(Zone::Dma32, 1, 7).unwrap();
    let b = first.allocate(Zone::Dma32, 1, 7).unwrap();
    let c = first.allocate(Zone::Dma32, 1, 7).unwrap();
    {
        let _lost = first.retain_allocation(a).unwrap();
    }
    std::mem::forget(first.retain_allocation(b).unwrap());
    let live = first.retain_allocation(c).unwrap();
    let mut moved = first;
    let mut access = FakePageAccess::new(a.start_page, 3, STALE_PATTERN);
    rejects_all_free_paths(&mut moved, &mut access, a);
    rejects_all_free_paths(&mut moved, &mut access, b);
    moved.release_retention(live).unwrap();
    moved.free(c).unwrap();
    assert_eq!(moved.summary().allocated_pages, 2);
}

#[test]
fn stale_allocation_generations_cannot_admit_a_new_retention() {
    let mut manager = manager();
    let old = manager.allocate(Zone::Dma32, 1, 7).unwrap();
    let retained = manager.retain_allocation(old).unwrap();
    manager.release_retention(retained).unwrap();
    manager.free(old).unwrap();
    let new = manager.allocate(Zone::Dma32, 1, 7).unwrap();
    assert_eq!(new.start_page, old.start_page);
    assert_ne!(new.generation, old.generation);
    assert_eq!(
        manager.retain_allocation(old).unwrap_err(),
        PhysicalMemoryError::StaleHandle
    );
    let retained = manager.retain_allocation(new).unwrap();
    assert_eq!(manager.free(old), Err(PhysicalMemoryError::StaleHandle));
    manager.release_retention(retained).unwrap();
    manager.free(new).unwrap();
}

#[test]
fn retention_does_not_change_direct_map_coverage_or_metadata_exclusion() {
    let mut manager = manager();
    let handle = manager.allocate(Zone::Dma32, 1, 7).unwrap();
    let before = manager.preview_direct_map_manifest().unwrap();
    let retained = manager.retain_allocation(handle).unwrap();
    assert_eq!(manager.preview_direct_map_manifest().unwrap(), before);
    manager.release_retention(retained).unwrap();
    manager.allocation_entries_mut()[usize::from(handle.slot)].release_excluded = true;
    assert_eq!(
        manager.retain_allocation(handle).unwrap_err(),
        PhysicalMemoryError::MetadataOwnership
    );
    assert_eq!(
        manager.free(handle),
        Err(PhysicalMemoryError::MetadataOwnership)
    );
}

#[test]
fn retention_survives_manager_migration_and_repeated_ledger_growth() {
    let mut bootstrap = manager();
    let handle = bootstrap.allocate(Zone::Dma32, 1, 7).unwrap();
    let retained = bootstrap.retain_allocation(handle).unwrap();
    let mut access = FakePageAccess::new(DMA_END_PAGE, 128, STALE_PATTERN);
    let migration = bootstrap.migrate_to_metadata(&mut access).unwrap();
    let (error, retained) = bootstrap.release_retention(retained).unwrap_err();
    assert_eq!(error, PhysicalMemoryError::MetadataState);
    // SAFETY: the test arena holds the sealed migrated manager and outlives it.
    let manager =
        unsafe { &mut *(migration.manager_address as usize as *mut PhysicalMemoryManager) };
    rejects_all_free_paths(manager, &mut access, handle);
    for _ in 0..2 {
        manager.grow_metadata_ledgers(&mut access).unwrap();
        rejects_all_free_paths(manager, &mut access, handle);
        assert_eq!(manager.verify_metadata_integrity(), Ok(()));
    }
    manager.release_retention(retained).unwrap();
    manager
        .free_scrubbed_automatic(handle, &mut access)
        .unwrap();
    assert_eq!(manager.verify_metadata_integrity(), Ok(()));
}

#[test]
fn mapped_and_external_ledger_seals_cover_retention_identity() {
    let mut bootstrap = manager();
    let mut access = FakePageAccess::new(DMA_END_PAGE, 128, STALE_PATTERN);
    let migration = bootstrap.migrate_to_metadata(&mut access).unwrap();
    // SAFETY: the test arena holds the sealed migrated manager and outlives it.
    let manager =
        unsafe { &mut *(migration.manager_address as usize as *mut PhysicalMemoryManager) };
    let handle = manager.allocate(Zone::Dma32, 1, 7).unwrap();
    let mut retained = manager.retain_allocation(handle).unwrap();
    for external in [false, true] {
        if external {
            manager.grow_metadata_ledgers(&mut access).unwrap();
        }
        let slot = usize::from(handle.slot);
        let identity = manager.allocation_entries()[slot].retention_id;
        manager.allocation_entries_mut()[slot].retention_id = 0;
        assert!(manager.verify_metadata_integrity().is_err());
        let (error, token) = manager.release_retention(retained).unwrap_err();
        assert_eq!(error, PhysicalMemoryError::MetadataCorruption);
        retained = token;
        manager.allocation_entries_mut()[slot].retention_id = identity;
        assert_eq!(manager.verify_metadata_integrity(), Ok(()));
    }
    manager.release_retention(retained).unwrap();
    manager.free(handle).unwrap();
}
