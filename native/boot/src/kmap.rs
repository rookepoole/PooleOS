use core::arch::asm;
use core::arch::x86_64::__cpuid;
use core::ptr::read_volatile;
use core::slice::from_raw_parts;
use core::sync::atomic::{Ordering, compiler_fence};

use poole_kmap::{
    CacheBits, CpuProfile, Error, FramebufferSnapshot, Lifecycle, Mapping, Permissions, Request,
    RetainedRequest, RetainedSummary, TABLE_ENTRIES, TABLE_PAGE_COUNT, TableAddresses, TableReader,
};

use super::{
    DEBUG_EXIT_PORT, EFI_COMPROMISED_DATA, EFI_LOADER_DATA, EFI_OUT_OF_RESOURCES, EFI_SUCCESS,
    EFI_UNSUPPORTED, EfiBootServices, EfiStatus, GopSummary, emit_bytes, function, kload, out_byte,
};

const EFI_ALLOCATE_ANY_PAGES: u32 = 0;
const IA32_EFER: u32 = 0xc000_0080;
const CR0_WRITE_PROTECT: u64 = 1 << 16;
const CR0_PAGING: u64 = 1 << 31;
const CR4_PAE: u64 = 1 << 5;
const CR4_LA57: u64 = 1 << 12;
const CR4_PCIDE: u64 = 1 << 17;
const EFER_LONG_MODE_ACTIVE: u64 = 1 << 10;
const EFER_NO_EXECUTE_ENABLE: u64 = 1 << 11;
const CPUID_EXTENDED_FEATURES: u32 = 0x8000_0001;
const CPUID_ADDRESS_WIDTHS: u32 = 0x8000_0008;
const CPUID_NX: u32 = 1 << 20;
const RFLAGS_INTERRUPT_ENABLE: u64 = 1 << 9;
const CR3_NON_PCID_FLAGS: u64 = poole_kmap::ENTRY_PWT | poole_kmap::ENTRY_PCD;

type AllocatePages = extern "efiapi" fn(u32, u32, usize, *mut u64) -> EfiStatus;
type FreePages = extern "efiapi" fn(u64, usize) -> EfiStatus;

#[derive(Clone, Copy)]
pub(super) struct Failure {
    pub stage: &'static str,
    pub code: &'static str,
    pub status: EfiStatus,
}

#[derive(Clone, Copy)]
pub(super) struct Summary {
    pub plan: poole_kmap::Summary,
    pub retained_plan: Option<RetainedSummary>,
    pub physical_address_bits: u8,
    pub table_page_count: usize,
    pub mapped_fnv1a64: u64,
    pub framebuffer_cache_signature: u8,
    pub framebuffer_first_page_size: u64,
    pub framebuffer_last_page_size: u64,
    pub tables_freed: usize,
    pub firmware_calls_while_active: usize,
}

pub(super) struct Retained {
    pub summary: Summary,
    pub table_physical_base: u64,
    lifecycle: Lifecycle,
}

fn firmware_failure(stage: &'static str, status: EfiStatus) -> Failure {
    Failure {
        stage,
        code: "firmware_status",
        status,
    }
}

fn contract_status(error: Error) -> EfiStatus {
    if matches!(
        error,
        Error::NxUnsupported
            | Error::NxDisabled
            | Error::FiveLevelPaging
            | Error::PcidEnabled
            | Error::PhysicalAddressBits
    ) {
        EFI_UNSUPPORTED
    } else {
        EFI_COMPROMISED_DATA
    }
}

fn contract_failure(stage: &'static str, error: Error) -> Failure {
    Failure {
        stage,
        code: error.code(),
        status: contract_status(error),
    }
}

fn missing_framebuffer() -> Failure {
    Failure {
        stage: "kmap.framebuffer_required",
        code: "framebuffer_missing",
        status: EFI_UNSUPPORTED,
    }
}

fn read_cr0() -> u64 {
    let value: u64;
    unsafe {
        asm!("mov {}, cr0", out(reg) value, options(nomem, nostack, preserves_flags));
    }
    value
}

fn read_cr3() -> u64 {
    let value: u64;
    unsafe {
        asm!("mov {}, cr3", out(reg) value, options(nomem, nostack, preserves_flags));
    }
    value
}

fn read_cr4() -> u64 {
    let value: u64;
    unsafe {
        asm!("mov {}, cr4", out(reg) value, options(nomem, nostack, preserves_flags));
    }
    value
}

fn write_cr3(value: u64) {
    unsafe {
        asm!("mov cr3, {}", in(reg) value, options(nostack, preserves_flags));
    }
}

fn read_msr(register: u32) -> u64 {
    let low: u32;
    let high: u32;
    unsafe {
        asm!(
            "rdmsr",
            in("ecx") register,
            out("eax") low,
            out("edx") high,
            options(nomem, nostack, preserves_flags)
        );
    }
    u64::from(low) | (u64::from(high) << 32)
}

fn cpu_profile() -> Result<CpuProfile, Failure> {
    let maximum_extended = __cpuid(0x8000_0000).eax;
    let features = if maximum_extended >= CPUID_EXTENDED_FEATURES {
        Some(__cpuid(CPUID_EXTENDED_FEATURES))
    } else {
        None
    };
    let widths = if maximum_extended >= CPUID_ADDRESS_WIDTHS {
        Some(__cpuid(CPUID_ADDRESS_WIDTHS))
    } else {
        None
    };
    let cr0 = read_cr0();
    let cr4 = read_cr4();
    let efer = read_msr(IA32_EFER);
    let profile = CpuProfile {
        paging: cr0 & CR0_PAGING != 0,
        pae: cr4 & CR4_PAE != 0,
        long_mode: efer & EFER_LONG_MODE_ACTIVE != 0,
        write_protect: cr0 & CR0_WRITE_PROTECT != 0,
        nx_supported: features.is_some_and(|value| value.edx & CPUID_NX != 0),
        nx_enabled: efer & EFER_NO_EXECUTE_ENABLE != 0,
        five_level_paging: cr4 & CR4_LA57 != 0,
        pcid_enabled: cr4 & CR4_PCIDE != 0,
        physical_address_bits: widths.map_or(0, |value| value.eax as u8),
    };
    poole_kmap::validate_cpu(profile)
        .map_err(|error| contract_failure("kmap.cpu_profile", error))?;
    Ok(profile)
}

fn physical_mask(bits: u8) -> u64 {
    ((1u64 << bits) - 1) & !(poole_kmap::PAGE_SIZE - 1)
}

struct PhysicalReader;

impl TableReader for PhysicalReader {
    fn read_entry(&self, table_address: u64, index: usize) -> Result<u64, Error> {
        if table_address > usize::MAX as u64 || index >= TABLE_ENTRIES {
            return Err(Error::TranslationAddress);
        }
        let pointer = (table_address as usize as *const u64).wrapping_add(index);
        Ok(unsafe { read_volatile(pointer) })
    }
}

fn table_ref(address: u64) -> Result<&'static [u64; TABLE_ENTRIES], Failure> {
    if address > usize::MAX as u64 {
        return Err(contract_failure("kmap.table_pointer", Error::TableAddress));
    }
    Ok(unsafe { &*(address as usize as *const [u64; TABLE_ENTRIES]) })
}

fn table_mut(address: u64) -> Result<&'static mut [u64; TABLE_ENTRIES], Failure> {
    if address > usize::MAX as u64 {
        return Err(contract_failure("kmap.table_pointer", Error::TableAddress));
    }
    Ok(unsafe { &mut *(address as usize as *mut [u64; TABLE_ENTRIES]) })
}

fn require_identity(
    reader: &PhysicalReader,
    root: u64,
    address: u64,
    physical_address_bits: u8,
    stage: &'static str,
) -> Result<(), Failure> {
    let translation = poole_kmap::translate(reader, root, address, physical_address_bits)
        .map_err(|error| contract_failure(stage, error))?;
    if translation.physical_address != address {
        return Err(contract_failure(stage, Error::TranslationAddress));
    }
    Ok(())
}

fn mapping_request(kernel: &kload::Summary, physical_address_bits: u8) -> Result<Request, Failure> {
    let mut mappings = [Mapping::EMPTY; poole_kmap::MAX_MAPPINGS];
    for (target, source) in mappings.iter_mut().zip(kernel.mappings.iter()) {
        *target = Mapping {
            virtual_offset: source.virtual_offset,
            byte_count: source.memory_size,
            permissions: Permissions {
                read: source.permissions.read,
                write: source.permissions.write,
                execute: source.permissions.execute,
            },
        };
    }
    Ok(Request {
        physical_base: kernel.kernel_physical_base,
        virtual_base: kernel.kernel_virtual_base,
        image_bytes: kernel.kernel_image_bytes,
        page_count: u32::try_from(kernel.page_count)
            .map_err(|_| contract_failure("kmap.request_page_count", Error::PageCount))?,
        entry_virtual: kernel.kernel_entry_virtual,
        mapping_count: u8::try_from(kernel.mapping_count)
            .map_err(|_| contract_failure("kmap.request_mapping_count", Error::MappingCount))?,
        mappings,
        physical_address_bits,
    })
}

fn cache_code(cache: CacheBits) -> u8 {
    u8::from(cache.pwt) | (u8::from(cache.pcd) << 1) | (u8::from(cache.pat) << 2)
}

fn framebuffer_cache_signature(snapshot: FramebufferSnapshot) -> u8 {
    cache_code(snapshot.first.cache) | (cache_code(snapshot.last.cache) << 3)
}

fn capture_and_disable_interrupts() -> u64 {
    let flags: u64;
    unsafe {
        asm!("pushfq", "pop {}", out(reg) flags, options(nomem, preserves_flags));
        asm!("cli", options(nomem, nostack));
    }
    flags
}

fn restore_interrupts(flags: u64) {
    if flags & RFLAGS_INTERRUPT_ENABLE != 0 {
        unsafe {
            asm!("sti", options(nomem, nostack));
        }
    }
}

fn rollback_abort() -> ! {
    emit_bytes(b"POOLEBOOT/0.1 FATAL stage=kmap.rollback code=rollback_mismatch\n");
    unsafe {
        out_byte(DEBUG_EXIT_PORT, 0x23);
        asm!("cli", options(nomem, nostack));
    }
    loop {
        unsafe {
            asm!("hlt", options(nomem, nostack));
        }
    }
}

fn release_tables(
    free_pages: FreePages,
    allocation_base: u64,
    primary_failure: Option<Failure>,
) -> Result<(), Failure> {
    let status = free_pages(allocation_base, TABLE_PAGE_COUNT);
    if status != EFI_SUCCESS {
        return Err(firmware_failure("kmap.tables_free", status));
    }
    if let Some(failure) = primary_failure {
        return Err(failure);
    }
    Ok(())
}

fn prepare_and_activate(
    kernel: &kload::Summary,
    gop: GopSummary,
    profile: CpuProfile,
    original_cr3: u64,
    allocation_base: u64,
    retained: Option<RetainedRequest>,
) -> Result<(Summary, Lifecycle), Failure> {
    let mask = physical_mask(profile.physical_address_bits);
    if original_cr3 & !(mask | CR3_NON_PCID_FLAGS) != 0 {
        return Err(contract_failure(
            "kmap.original_cr3_shape",
            Error::TranslationAddress,
        ));
    }
    let original_root = original_cr3 & mask;
    let candidate_cr3 = allocation_base | (original_cr3 & CR3_NON_PCID_FLAGS);
    let addresses = TableAddresses::contiguous(original_root, allocation_base)
        .map_err(|error| contract_failure("kmap.table_addresses", error))?;
    let reader = PhysicalReader;
    let table_last = allocation_base
        .checked_add(TABLE_PAGE_COUNT as u64 * poole_kmap::PAGE_SIZE - 1)
        .ok_or_else(|| contract_failure("kmap.table_range", Error::TableAddress))?;
    let kernel_last = kernel
        .kernel_physical_base
        .checked_add(u64::from(kernel.kernel_image_bytes) - 1)
        .ok_or_else(|| contract_failure("kmap.kernel_range", Error::PhysicalAddress))?;
    require_identity(
        &reader,
        original_root,
        allocation_base,
        profile.physical_address_bits,
        "kmap.table_identity_first",
    )?;
    require_identity(
        &reader,
        original_root,
        table_last,
        profile.physical_address_bits,
        "kmap.table_identity_last",
    )?;
    require_identity(
        &reader,
        original_root,
        kernel.kernel_physical_base,
        profile.physical_address_bits,
        "kmap.kernel_identity_first",
    )?;
    require_identity(
        &reader,
        original_root,
        kernel_last,
        profile.physical_address_bits,
        "kmap.kernel_identity_last",
    )?;
    for artifact in &kernel.artifacts {
        let allocation_bytes = (artifact.page_count as u64)
            .checked_mul(poole_kmap::PAGE_SIZE)
            .ok_or_else(|| contract_failure("kmap.retained_input_range", Error::RetainedRange))?;
        let last = artifact
            .physical_base
            .checked_add(allocation_bytes)
            .and_then(|end| end.checked_sub(1))
            .ok_or_else(|| contract_failure("kmap.retained_input_range", Error::RetainedRange))?;
        if artifact.role == 0
            || artifact.physical_base == 0
            || !artifact.physical_base.is_multiple_of(poole_kmap::PAGE_SIZE)
            || artifact.page_count == 0
            || artifact.file_bytes == 0
            || artifact.file_bytes as u64 > allocation_bytes
        {
            return Err(contract_failure(
                "kmap.retained_input_shape",
                Error::RetainedRange,
            ));
        }
        require_identity(
            &reader,
            original_root,
            artifact.physical_base,
            profile.physical_address_bits,
            "kmap.retained_input_identity_first",
        )?;
        require_identity(
            &reader,
            original_root,
            last,
            profile.physical_address_bits,
            "kmap.retained_input_identity_last",
        )?;
    }
    if let Some(retained) = retained {
        let stack_last = retained
            .stack_physical_base
            .checked_add(u64::from(retained.stack_page_count) * poole_kmap::PAGE_SIZE - 1)
            .ok_or_else(|| contract_failure("kmap.stack_range", Error::RetainedRange))?;
        let handoff_last = retained
            .handoff_physical_base
            .checked_add(u64::from(retained.handoff_capacity_bytes) - 1)
            .ok_or_else(|| contract_failure("kmap.handoff_range", Error::RetainedRange))?;
        for (address, stage) in [
            (retained.stack_physical_base, "kmap.stack_identity_first"),
            (stack_last, "kmap.stack_identity_last"),
            (
                retained.handoff_physical_base,
                "kmap.handoff_identity_first",
            ),
            (handoff_last, "kmap.handoff_identity_last"),
        ] {
            require_identity(
                &reader,
                original_root,
                address,
                profile.physical_address_bits,
                stage,
            )?;
        }
    }
    let original_framebuffer = poole_kmap::snapshot_framebuffer(
        &reader,
        original_root,
        gop.physical_base,
        gop.byte_count,
        profile.physical_address_bits,
    )
    .map_err(|error| contract_failure("kmap.framebuffer_original", error))?;
    let request = mapping_request(kernel, profile.physical_address_bits)?;
    let original_root_table = table_ref(addresses.original_root)?;
    let candidate_root_table = table_mut(addresses.candidate_root)?;
    let pdpt = table_mut(addresses.pdpt)?;
    let page_directory = table_mut(addresses.page_directory)?;
    let page_table = table_mut(addresses.page_table)?;
    let retained_plan = match retained {
        Some(retained) => Some(
            poole_kmap::populate_retained(
                &request,
                retained,
                addresses,
                original_root_table,
                candidate_root_table,
                pdpt,
                page_directory,
                page_table,
            )
            .map_err(|error| contract_failure("kmap.populate_retained", error))?,
        ),
        None => {
            poole_kmap::populate(
                &request,
                addresses,
                original_root_table,
                candidate_root_table,
                pdpt,
                page_directory,
                page_table,
            )
            .map_err(|error| contract_failure("kmap.populate", error))?;
            None
        }
    };
    let plan = retained_plan
        .map_or_else(
            || {
                poole_kmap::verify(
                    &request,
                    addresses,
                    original_root_table,
                    candidate_root_table,
                    pdpt,
                    page_directory,
                    page_table,
                )
            },
            |value| Ok(value.kernel),
        )
        .map_err(|error| contract_failure("kmap.verify_pre_activation", error))?;

    let mut lifecycle = Lifecycle::new(original_cr3, candidate_cr3);
    let interrupt_flags = capture_and_disable_interrupts();
    compiler_fence(Ordering::SeqCst);
    write_cr3(candidate_cr3);
    let observed_candidate = read_cr3();
    let activation = lifecycle
        .observe_activation(observed_candidate)
        .map_err(|error| contract_failure("kmap.activate", error));
    let active_result = if activation.is_ok() {
        let translation_result = match (retained, retained_plan) {
            (Some(retained), Some(expected)) => poole_kmap::verify_retained_translations(
                &reader,
                addresses.candidate_root,
                &request,
                retained,
                expected,
            )
            .map(|()| expected.kernel)
            .map_err(|error| contract_failure("kmap.verify_retained_translations", error)),
            (None, None) => {
                poole_kmap::verify_kernel_translations(&reader, addresses.candidate_root, &request)
                    .map_err(|error| contract_failure("kmap.verify_translations", error))
            }
            _ => Err(contract_failure(
                "kmap.retained_state",
                Error::RetainedRange,
            )),
        };
        match translation_result {
            Ok(observed_plan) if observed_plan == plan => {
                let mapped_bytes = unsafe {
                    from_raw_parts(
                        request.virtual_base as usize as *const u8,
                        request.image_bytes as usize,
                    )
                };
                let mapped_fnv1a64 = pooleboot::elf::fnv1a64(mapped_bytes);
                if mapped_fnv1a64 != kernel.loaded_fnv1a64 {
                    Err(contract_failure(
                        "kmap.alias_digest",
                        Error::TranslationAddress,
                    ))
                } else {
                    let candidate_framebuffer = poole_kmap::snapshot_framebuffer(
                        &reader,
                        addresses.candidate_root,
                        gop.physical_base,
                        gop.byte_count,
                        profile.physical_address_bits,
                    )
                    .map_err(|error| contract_failure("kmap.framebuffer_candidate", error));
                    match candidate_framebuffer {
                        Ok(candidate_framebuffer) => {
                            match poole_kmap::verify_framebuffer_preserved(
                                original_framebuffer,
                                candidate_framebuffer,
                            ) {
                                Ok(()) => Ok((mapped_fnv1a64, candidate_framebuffer)),
                                Err(error) => {
                                    Err(contract_failure("kmap.framebuffer_preserved", error))
                                }
                            }
                        }
                        Err(failure) => Err(failure),
                    }
                }
            }
            Ok(_) => Err(contract_failure(
                "kmap.translation_summary",
                Error::LeafEntry,
            )),
            Err(failure) => Err(failure),
        }
    } else {
        Err(activation
            .err()
            .unwrap_or_else(|| contract_failure("kmap.activate", Error::ActivationMismatch)))
    };
    compiler_fence(Ordering::SeqCst);
    write_cr3(original_cr3);
    let observed_original = read_cr3();
    if observed_original != original_cr3 {
        rollback_abort();
    }
    if activation.is_ok() && lifecycle.observe_rollback(observed_original).is_err() {
        rollback_abort();
    }
    restore_interrupts(interrupt_flags);
    if !lifecycle.firmware_call_allowed() {
        return Err(contract_failure(
            "kmap.firmware_boundary",
            Error::FirmwareBeforeRollback,
        ));
    }
    let (mapped_fnv1a64, candidate_framebuffer) = active_result?;
    Ok((
        Summary {
            plan,
            retained_plan,
            physical_address_bits: profile.physical_address_bits,
            table_page_count: TABLE_PAGE_COUNT,
            mapped_fnv1a64,
            framebuffer_cache_signature: framebuffer_cache_signature(candidate_framebuffer),
            framebuffer_first_page_size: candidate_framebuffer.first.page_size,
            framebuffer_last_page_size: candidate_framebuffer.last.page_size,
            tables_freed: 0,
            firmware_calls_while_active: 0,
        },
        lifecycle,
    ))
}

#[allow(dead_code)]
pub(super) fn activate_and_restore(
    boot_services: &EfiBootServices,
    kernel: &kload::Summary,
    gop: Option<GopSummary>,
) -> Result<Summary, Failure> {
    let gop = gop.ok_or_else(missing_framebuffer)?;
    let profile = cpu_profile()?;
    let original_cr3 = read_cr3();
    let allocate_pages: AllocatePages = unsafe { function(boot_services.allocate_pages) }
        .map_err(|status| firmware_failure("kmap.allocate_pages_pointer", status))?;
    let free_pages: FreePages = unsafe { function(boot_services.free_pages) }
        .map_err(|status| firmware_failure("kmap.free_pages_pointer", status))?;
    let mut allocation_base = 0u64;
    let status = allocate_pages(
        EFI_ALLOCATE_ANY_PAGES,
        EFI_LOADER_DATA,
        TABLE_PAGE_COUNT,
        &mut allocation_base,
    );
    if status != EFI_SUCCESS {
        return Err(firmware_failure("kmap.tables_allocate", status));
    }
    if allocation_base == 0 {
        return Err(Failure {
            stage: "kmap.tables_allocate_shape",
            code: "zero_allocation",
            status: EFI_OUT_OF_RESOURCES,
        });
    }
    let prepared = prepare_and_activate(kernel, gop, profile, original_cr3, allocation_base, None);
    let (mut summary, mut lifecycle) = match prepared {
        Ok(value) => value,
        Err(failure) => {
            release_tables(free_pages, allocation_base, Some(failure))?;
            return Err(failure);
        }
    };
    release_tables(free_pages, allocation_base, None)?;
    lifecycle
        .observe_release()
        .map_err(|error| contract_failure("kmap.release_order", error))?;
    summary.tables_freed = TABLE_PAGE_COUNT;
    Ok(summary)
}

pub(super) fn prepare_and_retain(
    boot_services: &EfiBootServices,
    kernel: &kload::Summary,
    gop: Option<GopSummary>,
    stack_physical_base: u64,
    handoff_physical_base: u64,
) -> Result<Retained, Failure> {
    let gop = gop.ok_or_else(missing_framebuffer)?;
    let profile = cpu_profile()?;
    let original_cr3 = read_cr3();
    let allocate_pages: AllocatePages = unsafe { function(boot_services.allocate_pages) }
        .map_err(|status| firmware_failure("kmap.allocate_pages_pointer", status))?;
    let free_pages: FreePages = unsafe { function(boot_services.free_pages) }
        .map_err(|status| firmware_failure("kmap.free_pages_pointer", status))?;
    let mut allocation_base = 0u64;
    let status = allocate_pages(
        EFI_ALLOCATE_ANY_PAGES,
        EFI_LOADER_DATA,
        TABLE_PAGE_COUNT,
        &mut allocation_base,
    );
    if status != EFI_SUCCESS {
        return Err(firmware_failure("kmap.tables_allocate", status));
    }
    if allocation_base == 0 {
        return Err(Failure {
            stage: "kmap.tables_allocate_shape",
            code: "zero_allocation",
            status: EFI_OUT_OF_RESOURCES,
        });
    }
    let retained_request = RetainedRequest {
        stack_physical_base,
        stack_page_count: poole_kmap::STACK_PAGE_COUNT as u32,
        handoff_physical_base,
        handoff_capacity_bytes: poole_kmap::HANDOFF_CAPACITY_BYTES as u32,
    };
    let prepared = prepare_and_activate(
        kernel,
        gop,
        profile,
        original_cr3,
        allocation_base,
        Some(retained_request),
    );
    let (summary, mut lifecycle) = match prepared {
        Ok(value) => value,
        Err(failure) => {
            release_tables(free_pages, allocation_base, Some(failure))?;
            return Err(failure);
        }
    };
    if let Err(error) = lifecycle.observe_retention() {
        let failure = contract_failure("kmap.retention_order", error);
        release_tables(free_pages, allocation_base, Some(failure))?;
        return Err(failure);
    }
    Ok(Retained {
        summary,
        table_physical_base: allocation_base,
        lifecycle,
    })
}

pub(super) fn release_retained(
    boot_services: &EfiBootServices,
    mut retained: Retained,
) -> Result<Summary, Failure> {
    let free_pages: FreePages = unsafe { function(boot_services.free_pages) }
        .map_err(|status| firmware_failure("kmap.free_pages_pointer", status))?;
    release_tables(free_pages, retained.table_physical_base, None)?;
    retained
        .lifecycle
        .observe_release()
        .map_err(|error| contract_failure("kmap.release_order", error))?;
    retained.summary.tables_freed = TABLE_PAGE_COUNT;
    Ok(retained.summary)
}
