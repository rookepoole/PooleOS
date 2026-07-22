use core::arch::asm;
use core::ffi::c_void;
use core::ptr::{null_mut, write_bytes};
use core::slice::{from_raw_parts, from_raw_parts_mut};
use core::sync::atomic::{Ordering, compiler_fence};

use poole_boot_exit::{self as contract, ExitResult, FinalMap, HandoffCandidate, Lifecycle};
#[cfg(feature = "development-transfer")]
use poole_boot_exit::{DevelopmentTransfer, DevelopmentTransferLifecycle};
use poole_live_handoff::{self as live, ExitBuildInput, KernelInput, RetainedInput};

use super::{
    EFI_BUFFER_TOO_SMALL, EFI_COMPROMISED_DATA, EFI_INVALID_PARAMETER, EFI_LOADER_DATA,
    EFI_OUT_OF_RESOURCES, EFI_SUCCESS, EfiBootServices, EfiHandle, EfiStatus, GetMemoryMap,
    GopSummary, allocate_pool_call, diagnostic, free_pool_call, function, kload, kmap, livehandoff,
};

const EFI_ALLOCATE_ANY_PAGES: u32 = 0;

#[cfg(any(
    all(
        feature = "development-trap-returning",
        feature = "development-trap-double-fault"
    ),
    all(
        feature = "development-trap-returning",
        feature = "development-trap-malformed-frame"
    ),
    all(
        feature = "development-trap-double-fault",
        feature = "development-trap-malformed-frame"
    ),
    all(
        feature = "development-cpu-policy",
        feature = "development-trap-returning"
    ),
    all(
        feature = "development-cpu-policy",
        feature = "development-trap-double-fault"
    ),
    all(
        feature = "development-cpu-policy",
        feature = "development-trap-malformed-frame"
    ),
    all(
        feature = "development-xstate-policy",
        feature = "development-trap-returning"
    ),
    all(
        feature = "development-xstate-policy",
        feature = "development-trap-double-fault"
    ),
    all(
        feature = "development-xstate-policy",
        feature = "development-trap-malformed-frame"
    ),
    all(
        feature = "development-xstate-policy",
        feature = "development-cpu-policy"
    ),
    all(
        feature = "development-xstate-exception",
        feature = "development-trap-returning"
    ),
    all(
        feature = "development-xstate-exception",
        feature = "development-trap-double-fault"
    ),
    all(
        feature = "development-xstate-exception",
        feature = "development-trap-malformed-frame"
    ),
    all(
        feature = "development-xstate-exception",
        feature = "development-cpu-policy"
    ),
    all(
        feature = "development-xstate-exception",
        feature = "development-xstate-policy"
    ),
    all(
        feature = "development-privilege-msr-policy",
        feature = "development-trap-returning"
    ),
    all(
        feature = "development-privilege-msr-policy",
        feature = "development-trap-double-fault"
    ),
    all(
        feature = "development-privilege-msr-policy",
        feature = "development-trap-malformed-frame"
    ),
    all(
        feature = "development-privilege-msr-policy",
        feature = "development-cpu-policy"
    ),
    all(
        feature = "development-privilege-msr-policy",
        feature = "development-xstate-policy"
    ),
    all(
        feature = "development-privilege-msr-policy",
        feature = "development-xstate-exception"
    ),
))]
compile_error!("only one post-PKXFER1 development scenario may be selected");

#[cfg(feature = "development-transfer")]
const DEVELOPMENT_TRAP_SCENARIO: u8 = if cfg!(feature = "development-trap-returning") {
    1
} else if cfg!(feature = "development-trap-double-fault") {
    2
} else if cfg!(feature = "development-trap-malformed-frame") {
    3
} else if cfg!(feature = "development-cpu-policy") {
    4
} else if cfg!(feature = "development-xstate-policy") {
    5
} else if cfg!(feature = "development-xstate-exception") {
    6
} else if cfg!(feature = "development-privilege-msr-policy") {
    7
} else {
    0
};

type AllocatePages = extern "efiapi" fn(u32, u32, usize, *mut u64) -> EfiStatus;
type FreePages = extern "efiapi" fn(u64, usize) -> EfiStatus;
type ExitBootServices = extern "efiapi" fn(EfiHandle, usize) -> EfiStatus;

#[derive(Clone, Copy)]
struct Calls {
    get_memory_map: GetMemoryMap,
    allocate_pool: super::AllocatePool,
    free_pool: super::FreePool,
    allocate_pages: AllocatePages,
    free_pages: FreePages,
    exit_boot_services: ExitBootServices,
}

struct PreAttemptResources {
    retained: Option<kmap::Retained>,
    stack: u64,
    handoff: u64,
    normalized: *mut c_void,
    raw: *mut c_void,
}

#[derive(Clone, Copy)]
pub(super) struct Failure {
    pub stage: &'static str,
    pub code: &'static str,
    pub status: EfiStatus,
}

fn firmware_failure(stage: &'static str, status: EfiStatus) -> Failure {
    Failure {
        stage,
        code: "firmware_status",
        status,
    }
}

fn contract_failure(stage: &'static str, error: contract::Error) -> Failure {
    Failure {
        stage,
        code: error.code(),
        status: EFI_COMPROMISED_DATA,
    }
}

#[cfg(feature = "development-transfer")]
fn transfer_failure(stage: &'static str, error: contract::TransferError) -> Failure {
    Failure {
        stage,
        code: error.code(),
        status: EFI_COMPROMISED_DATA,
    }
}

fn live_failure(stage: &'static str, error: live::Error) -> Failure {
    let code = match error {
        live::Error::DescriptorSize => "descriptor_size",
        live::Error::DescriptorVersion => "descriptor_version",
        live::Error::MemoryMapShape => "memory_map_shape",
        live::Error::MemoryType => "memory_type",
        live::Error::MemoryRange => "memory_range",
        live::Error::MemoryOverlap => "memory_overlap",
        live::Error::ScratchCapacity => "scratch_capacity",
        live::Error::OutputCapacity => "output_capacity",
        live::Error::Handoff(_) => "pbp1_codec",
        live::Error::PreExitProfile => "pre_exit_profile",
        live::Error::ExitProfile => "exit_profile",
        live::Error::RetainedRange => "retained_range",
        live::Error::ArtifactSet => "artifact_set",
    };
    Failure {
        stage,
        code,
        status: EFI_COMPROMISED_DATA,
    }
}

fn calls(boot_services: &EfiBootServices) -> Result<Calls, Failure> {
    Ok(Calls {
        get_memory_map: unsafe { function(boot_services.get_memory_map) }
            .map_err(|status| firmware_failure("exit.get_memory_map_pointer", status))?,
        allocate_pool: unsafe { function(boot_services.allocate_pool) }
            .map_err(|status| firmware_failure("exit.allocate_pool_pointer", status))?,
        free_pool: unsafe { function(boot_services.free_pool) }
            .map_err(|status| firmware_failure("exit.free_pool_pointer", status))?,
        allocate_pages: unsafe { function(boot_services.allocate_pages) }
            .map_err(|status| firmware_failure("exit.allocate_pages_pointer", status))?,
        free_pages: unsafe { function(boot_services.free_pages) }
            .map_err(|status| firmware_failure("exit.free_pages_pointer", status))?,
        exit_boot_services: unsafe { function(boot_services.exit_boot_services) }
            .map_err(|status| firmware_failure("exit.exit_boot_services_pointer", status))?,
    })
}

fn allocate_pool(
    calls: Calls,
    byte_count: usize,
    stage: &'static str,
) -> Result<*mut c_void, Failure> {
    let mut pointer = null_mut();
    let status = allocate_pool_call(
        calls.allocate_pool,
        EFI_LOADER_DATA,
        byte_count,
        &mut pointer,
    );
    if status != EFI_SUCCESS || pointer.is_null() {
        Err(firmware_failure(
            stage,
            if status == EFI_SUCCESS {
                EFI_OUT_OF_RESOURCES
            } else {
                status
            },
        ))
    } else {
        Ok(pointer)
    }
}

fn allocate_pages(calls: Calls, page_count: usize, stage: &'static str) -> Result<u64, Failure> {
    let mut address = 0u64;
    let status = (calls.allocate_pages)(
        EFI_ALLOCATE_ANY_PAGES,
        EFI_LOADER_DATA,
        page_count,
        &mut address,
    );
    if status != EFI_SUCCESS || address == 0 || address > usize::MAX as u64 {
        Err(firmware_failure(
            stage,
            if status == EFI_SUCCESS {
                EFI_OUT_OF_RESOURCES
            } else {
                status
            },
        ))
    } else {
        Ok(address)
    }
}

fn release_pre_attempt(
    boot_services: &EfiBootServices,
    calls: Calls,
    resources: PreAttemptResources,
    primary: Failure,
) -> Failure {
    let mut failure = Some(primary);
    if let Some(retained) = resources.retained
        && let Err(value) = kmap::release_retained(boot_services, retained)
    {
        failure.get_or_insert(Failure {
            stage: value.stage,
            code: value.code,
            status: value.status,
        });
    }
    for (address, pages, stage) in [
        (
            resources.stack,
            contract::STACK_PAGE_COUNT,
            "exit.stack_pages_free",
        ),
        (
            resources.handoff,
            contract::HANDOFF_CAPACITY_BYTES / contract::PAGE_SIZE as usize,
            "exit.handoff_pages_free",
        ),
    ] {
        if address != 0 {
            let status = (calls.free_pages)(address, pages);
            if status != EFI_SUCCESS {
                failure.get_or_insert(firmware_failure(stage, status));
            }
        }
    }
    for (pointer, stage) in [
        (resources.normalized, "exit.normalized_pool_free"),
        (resources.raw, "exit.raw_map_pool_free"),
    ] {
        if !pointer.is_null() {
            let status = free_pool_call(calls.free_pool, pointer);
            if status != EFI_SUCCESS {
                failure.get_or_insert(firmware_failure(stage, status));
            }
        }
    }
    failure.unwrap_or(primary)
}

fn kernel_input(kernel: &kload::Summary, uefi_revision: u32) -> Result<KernelInput, Failure> {
    let physical_size = (kernel.page_count as u64)
        .checked_mul(contract::PAGE_SIZE)
        .ok_or_else(|| contract_failure("exit.kernel_range", contract::Error::TransferState))?;
    Ok(KernelInput {
        physical_base: kernel.kernel_physical_base,
        physical_size,
        virtual_base: kernel.kernel_virtual_base,
        virtual_size: kernel.kernel_image_bytes as u64,
        entry_virtual: kernel.kernel_entry_virtual,
        sha256: kernel.kernel_sha256,
        boot_attempt: 0,
        boot_attempt_limit: u32::from(kernel.config.boot_attempt_limit),
        boot_slot: u32::from(kernel.config.selected_slot),
        selected_entry: 1,
        uefi_revision,
    })
}

fn fatal_after_attempt(failure: Failure) -> ! {
    diagnostic(format_args!(
        "POOLEBOOT/0.1 FATAL stage={} code={} status=0x{:016X} after_exit_attempt=1\n",
        failure.stage, failure.code, failure.status as u64
    ));
    unsafe {
        asm!("cli", options(nomem, nostack));
    }
    loop {
        unsafe {
            asm!("hlt", options(nomem, nostack));
        }
    }
}

#[cfg(not(feature = "development-transfer"))]
fn stop_before_transfer() -> ! {
    unsafe {
        asm!("cli", options(nomem, nostack));
    }
    loop {
        unsafe {
            asm!("hlt", options(nomem, nostack));
        }
    }
}

#[cfg(feature = "development-transfer")]
unsafe fn transfer_to_kernel(transfer: DevelopmentTransfer) -> ! {
    compiler_fence(Ordering::SeqCst);
    // SAFETY: PKXFER1 has validated the retained page-table root, canonical mapped
    // destinations, aligned stack, immutable handoff, zero-authority profile, and
    // successful ExitBootServices boundary. This is the one terminal dispatch.
    unsafe {
        asm!(
            "cli",
            "cld",
            "mov cr3, rax",
            "mov rsp, rcx",
            "jmp r11",
            in("rax") transfer.transfer_cr3,
            in("rcx") transfer.stack_top_virtual,
            in("rdi") transfer.handoff_virtual,
            in("rsi") transfer.handoff_byte_count,
            in("rdx") u64::from_le_bytes(poole_handoff::MAGIC),
            in("r10") u64::from(transfer.trap_scenario),
            in("r11") transfer.kernel_entry_virtual,
            options(noreturn),
        );
    }
}

pub(super) fn exit_and_stop(
    image_handle: EfiHandle,
    boot_services: &EfiBootServices,
    kernel: &kload::Summary,
    gop: Option<GopSummary>,
    uefi_revision: u32,
) -> Result<(), Failure> {
    let calls = calls(boot_services)?;
    let raw = allocate_pool(
        calls,
        contract::RAW_MEMORY_MAP_CAPACITY,
        "exit.raw_map_pool_allocate",
    )?;
    let normalized = match allocate_pool(
        calls,
        contract::NORMALIZED_MEMORY_CAPACITY,
        "exit.normalized_pool_allocate",
    ) {
        Ok(value) => value,
        Err(failure) => {
            return Err(release_pre_attempt(
                boot_services,
                calls,
                PreAttemptResources {
                    retained: None,
                    stack: 0,
                    handoff: 0,
                    normalized: null_mut(),
                    raw,
                },
                failure,
            ));
        }
    };
    let handoff_pages = contract::HANDOFF_CAPACITY_BYTES / contract::PAGE_SIZE as usize;
    let handoff = match allocate_pages(calls, handoff_pages, "exit.handoff_pages_allocate") {
        Ok(value) => value,
        Err(failure) => {
            return Err(release_pre_attempt(
                boot_services,
                calls,
                PreAttemptResources {
                    retained: None,
                    stack: 0,
                    handoff: 0,
                    normalized,
                    raw,
                },
                failure,
            ));
        }
    };
    let stack = match allocate_pages(
        calls,
        contract::STACK_PAGE_COUNT,
        "exit.stack_pages_allocate",
    ) {
        Ok(value) => value,
        Err(failure) => {
            return Err(release_pre_attempt(
                boot_services,
                calls,
                PreAttemptResources {
                    retained: None,
                    stack: 0,
                    handoff,
                    normalized,
                    raw,
                },
                failure,
            ));
        }
    };
    unsafe {
        write_bytes(
            handoff as usize as *mut u8,
            0,
            contract::HANDOFF_CAPACITY_BYTES,
        );
        write_bytes(
            stack as usize as *mut u8,
            0,
            contract::STACK_PAGE_COUNT * contract::PAGE_SIZE as usize,
        );
    }
    let retained = match kmap::prepare_and_retain(boot_services, kernel, gop, stack, handoff) {
        Ok(value) => value,
        Err(value) => {
            let failure = Failure {
                stage: value.stage,
                code: value.code,
                status: value.status,
            };
            return Err(release_pre_attempt(
                boot_services,
                calls,
                PreAttemptResources {
                    retained: None,
                    stack,
                    handoff,
                    normalized,
                    raw,
                },
                failure,
            ));
        }
    };
    let retained_plan = match retained.summary.retained_plan {
        Some(value) => value,
        None => {
            let failure = contract_failure("exit.retained_plan", contract::Error::TransferState);
            return Err(release_pre_attempt(
                boot_services,
                calls,
                PreAttemptResources {
                    retained: Some(retained),
                    stack,
                    handoff,
                    normalized,
                    raw,
                },
                failure,
            ));
        }
    };
    diagnostic(format_args!(
        "POOLEBOOT/0.1 KERNEL_MAP_PLAN PASS contract={} mappings={} kernel_pages={} ro={} rx={} rw={} wx={} pml4={} pdpt={} pd={} pt={} leaf_fnv1a64={:016X}\n",
        poole_kmap::RETAINED_CONTRACT_ID,
        kernel.mapping_count,
        retained.summary.plan.mapped_page_count,
        retained.summary.plan.read_only_page_count,
        retained.summary.plan.read_execute_page_count,
        retained.summary.plan.read_write_page_count,
        retained.summary.plan.writable_executable_page_count,
        retained.summary.plan.pml4_index,
        retained.summary.plan.pdpt_index,
        retained.summary.plan.page_directory_index,
        retained.summary.plan.first_page_table_index,
        retained.summary.plan.leaf_fingerprint,
    ));
    diagnostic(format_args!(
        "POOLEBOOT/0.1 KERNEL_MAP_ACTIVE PASS table_pages={} kernel_pages={} physical_bits={} mapped_fnv1a64={:016X} framebuffer=preserved cache_signature={:02X} first_page_bytes={} last_page_bytes={}\n",
        retained.summary.table_page_count,
        retained.summary.plan.mapped_page_count,
        retained.summary.physical_address_bits,
        retained.summary.mapped_fnv1a64,
        retained.summary.framebuffer_cache_signature,
        retained.summary.framebuffer_first_page_size,
        retained.summary.framebuffer_last_page_size,
    ));
    diagnostic(format_args!(
        "POOLEBOOT/0.1 KERNEL_MAP_RETAIN PASS table_pages={} stack_pages={} handoff_pages={} guards={} total_pages={} stack_pt={} handoff_pt={} kernel_phys={:016X} root={:016X} stack_phys={:016X} stack_top={:016X} handoff_phys={:016X} handoff_virt={:016X} retained_fnv1a64={:016X} original_cr3=restored firmware_calls_while_active={}\n",
        retained.summary.table_page_count,
        retained_plan.stack_page_count,
        retained_plan.handoff_page_count,
        retained_plan.guard_page_count,
        retained_plan.total_mapped_page_count,
        retained_plan.stack_first_page_table_index,
        retained_plan.handoff_first_page_table_index,
        kernel.kernel_physical_base,
        retained.table_physical_base,
        stack,
        retained_plan.stack_top_virtual,
        handoff,
        retained_plan.handoff_virtual_base,
        retained_plan.retained_leaf_fingerprint,
        retained.summary.firmware_calls_while_active,
    ));

    let kernel_input = match kernel_input(kernel, uefi_revision) {
        Ok(value) => value,
        Err(failure) => {
            return Err(release_pre_attempt(
                boot_services,
                calls,
                PreAttemptResources {
                    retained: Some(retained),
                    stack,
                    handoff,
                    normalized,
                    raw,
                },
                failure,
            ));
        }
    };
    let artifact_inputs = match livehandoff::artifacts(kernel) {
        Ok(value) => value,
        Err(error) => {
            let failure = live_failure("exit.artifact_set", error);
            return Err(release_pre_attempt(
                boot_services,
                calls,
                PreAttemptResources {
                    retained: Some(retained),
                    stack,
                    handoff,
                    normalized,
                    raw,
                },
                failure,
            ));
        }
    };
    let mut lifecycle = Lifecycle::new();
    for _ in 0..contract::MAX_EXIT_ATTEMPTS {
        let mut map_size = contract::RAW_MEMORY_MAP_CAPACITY;
        let mut map_key = 0usize;
        let mut descriptor_size = 0usize;
        let mut descriptor_version = 0u32;
        let map_status = (calls.get_memory_map)(
            &mut map_size,
            raw,
            &mut map_key,
            &mut descriptor_size,
            &mut descriptor_version,
        );
        if map_status != EFI_SUCCESS {
            let failure = firmware_failure("exit.final_memory_map", map_status);
            if lifecycle.attempts() == 0 {
                return Err(release_pre_attempt(
                    boot_services,
                    calls,
                    PreAttemptResources {
                        retained: Some(retained),
                        stack,
                        handoff,
                        normalized,
                        raw,
                    },
                    failure,
                ));
            }
            fatal_after_attempt(failure);
        }
        let final_map = FinalMap {
            map_key,
            map_bytes: map_size,
            descriptor_size,
            descriptor_version,
        };
        if let Err(error) = lifecycle.observe_map(final_map) {
            let failure = contract_failure("exit.final_map_contract", error);
            if lifecycle.attempts() == 0 {
                return Err(release_pre_attempt(
                    boot_services,
                    calls,
                    PreAttemptResources {
                        retained: Some(retained),
                        stack,
                        handoff,
                        normalized,
                        raw,
                    },
                    failure,
                ));
            }
            fatal_after_attempt(failure);
        }
        let raw_map = unsafe { from_raw_parts(raw.cast::<u8>(), map_size) };
        let normalized_map = unsafe {
            from_raw_parts_mut(
                normalized.cast::<u8>(),
                contract::NORMALIZED_MEMORY_CAPACITY,
            )
        };
        let output = unsafe {
            from_raw_parts_mut(
                handoff as usize as *mut u8,
                contract::HANDOFF_CAPACITY_BYTES,
            )
        };
        let input = ExitBuildInput {
            raw_memory_map: raw_map,
            descriptor_size,
            descriptor_version,
            handoff_physical_base: handoff,
            kernel: kernel_input,
            artifacts: artifact_inputs,
            framebuffer: livehandoff::framebuffer(gop),
            retained: RetainedInput {
                page_table_root_physical: retained.table_physical_base,
                table_page_count: retained.summary.table_page_count as u32,
                stack_physical_base: stack,
                stack_page_count: retained_plan.stack_page_count,
                stack_top_virtual: retained_plan.stack_top_virtual,
                handoff_virtual_base: retained_plan.handoff_virtual_base,
                handoff_capacity_bytes: contract::HANDOFF_CAPACITY_BYTES as u32,
            },
        };
        let (bytes, handoff_summary) =
            match live::build_exit_candidate(input, normalized_map, output) {
                Ok(value) => value,
                Err(error) => {
                    let failure = live_failure("exit.pbp1_candidate", error);
                    if lifecycle.attempts() == 0 {
                        return Err(release_pre_attempt(
                            boot_services,
                            calls,
                            PreAttemptResources {
                                retained: Some(retained),
                                stack,
                                handoff,
                                normalized,
                                raw,
                            },
                            failure,
                        ));
                    }
                    fatal_after_attempt(failure);
                }
            };
        let candidate = HandoffCandidate {
            byte_count: bytes.len(),
            boot_services_exited: true,
            development_mode: true,
            stack_top_virtual: retained_plan.stack_top_virtual,
            page_table_root_physical: retained.table_physical_base,
            kernel_signature_verified: false,
            kernel_entry_profile_valid: false,
        };
        if let Err(error) = lifecycle.observe_handoff(candidate) {
            let failure = contract_failure("exit.pbp1_state", error);
            if lifecycle.attempts() == 0 {
                return Err(release_pre_attempt(
                    boot_services,
                    calls,
                    PreAttemptResources {
                        retained: Some(retained),
                        stack,
                        handoff,
                        normalized,
                        raw,
                    },
                    failure,
                ));
            }
            fatal_after_attempt(failure);
        }
        let before_exit = live::fnv1a64(bytes);
        compiler_fence(Ordering::SeqCst);
        let exit_status = (calls.exit_boot_services)(image_handle, map_key);
        compiler_fence(Ordering::SeqCst);
        let result = if exit_status == EFI_SUCCESS {
            ExitResult::Success
        } else if exit_status == EFI_INVALID_PARAMETER {
            ExitResult::InvalidParameter
        } else {
            ExitResult::OtherFailure
        };
        if let Err(error) = lifecycle.observe_exit(result) {
            fatal_after_attempt(Failure {
                stage: "exit.exit_boot_services",
                code: error.code(),
                status: exit_status,
            });
        }
        if result == ExitResult::InvalidParameter {
            continue;
        }
        if result != ExitResult::Success {
            fatal_after_attempt(firmware_failure("exit.exit_boot_services", exit_status));
        }
        unsafe {
            asm!("cli", options(nomem, nostack));
        }
        if live::fnv1a64(bytes) != before_exit
            || lifecycle.firmware_calls_after_exit() != 0
            || lifecycle.transfer_allowed()
        {
            fatal_after_attempt(contract_failure(
                "exit.post_success_state",
                contract::Error::FirmwareAfterExit,
            ));
        }
        diagnostic(format_args!(
            "POOLEBOOT/0.1 PBP1_FINAL PASS bytes={} records={} memory_entries={} framebuffer={} artifacts={} descriptor_bytes={} exit_attempts={} message_crc32={:08X} fnv1a64={:016X} state=boot_services_exited bytes_unchanged=1\n",
            handoff_summary.total_bytes,
            handoff_summary.record_count,
            handoff_summary.memory_entry_count,
            u8::from(handoff_summary.framebuffer_present),
            handoff_summary.artifact_count,
            descriptor_size,
            lifecycle.attempts(),
            handoff_summary.message_crc32,
            handoff_summary.fnv1a64,
        ));
        livehandoff::emit_transcript(bytes, handoff_summary);
        diagnostic(format_args!(
            "POOLEBOOT/0.1 EXIT_BOOT_SERVICES PASS contract={} attempts={} map_bytes={} descriptor_bytes={} descriptors={}\n",
            contract::CONTRACT_ID,
            lifecycle.attempts(),
            map_size,
            descriptor_size,
            final_map.descriptor_count(),
        ));
        diagnostic(format_args!(
            "POOLEBOOT/0.1 FIRMWARE_BOUNDARY PASS calls_after_exit={} kernel_pages={} artifact_pages={} table_pages={} stack_pages={} handoff_pages={}\n",
            lifecycle.firmware_calls_after_exit(),
            kernel.page_count,
            kernel
                .artifacts
                .iter()
                .map(|artifact| artifact.page_count)
                .sum::<usize>(),
            retained.summary.table_page_count,
            retained_plan.stack_page_count,
            retained_plan.handoff_page_count,
        ));
        #[cfg(not(feature = "development-transfer"))]
        {
            diagnostic(format_args!(
                "POOLEBOOT/0.1 BOUNDARY unsigned=1 secure_boot=not_tested selection=manifest_digest_untrusted artifacts=digest_verified_untrusted semantics=parsed_live_unsigned_denied authority=none actions=none kernel=retained handoff=retained mappings=retained entry=not_called exit_boot_services=called transfer=stopped\n"
            ));
            diagnostic(format_args!("POOLEBOOT/0.1 STOP BEFORE TRANSFER\n"));
            stop_before_transfer();
        }
        #[cfg(feature = "development-transfer")]
        {
            let transfer = DevelopmentTransfer {
                kernel_entry_virtual: kernel.kernel_entry_virtual,
                handoff_virtual: retained_plan.handoff_virtual_base,
                handoff_byte_count: bytes.len(),
                stack_top_virtual: retained_plan.stack_top_virtual,
                page_table_root_physical: retained.table_physical_base,
                transfer_cr3: retained.transfer_cr3,
                trap_scenario: DEVELOPMENT_TRAP_SCENARIO,
                boot_services_exited: true,
                development_mode: true,
                emulator_only: true,
                terminal_after_revalidation: true,
                production_kernel_entry_profile_valid: false,
                signature_verifications: 0,
                authority_grants: 0,
                actions_authorized: 0,
                state_writes: 0,
                firmware_calls_after_exit: lifecycle.firmware_calls_after_exit(),
            };
            let mut transfer_lifecycle = DevelopmentTransferLifecycle::arm(lifecycle, transfer)
                .unwrap_or_else(|error| {
                    fatal_after_attempt(transfer_failure("transfer.arm", error))
                });
            transfer_lifecycle
                .observe_dispatch()
                .unwrap_or_else(|error| {
                    fatal_after_attempt(transfer_failure("transfer.dispatch", error))
                });
            diagnostic(format_args!(
                "POOLEBOOT/0.1 TRANSFER_ARM PASS contract={} mode=development emulator_only=1 entry={:016X} handoff={:016X} bytes={} stack_top={:016X} root={:016X} cr3={:016X} trap_scenario={} signatures=0 authority=0 actions=0 writes=0 firmware_calls_after_exit={}\n",
                contract::TRANSFER_CONTRACT_ID,
                transfer.kernel_entry_virtual,
                transfer.handoff_virtual,
                transfer.handoff_byte_count,
                transfer.stack_top_virtual,
                transfer.page_table_root_physical,
                transfer.transfer_cr3,
                transfer.trap_scenario,
                transfer.firmware_calls_after_exit,
            ));
            diagnostic(format_args!(
                "POOLEBOOT/0.1 BOUNDARY unsigned=1 secure_boot=not_tested selection=manifest_digest_untrusted artifacts=digest_verified_untrusted semantics=parsed_live_unsigned_denied authority=none actions=none kernel=retained handoff=retained mappings=retained entry=armed exit_boot_services=called transfer=one_way_development\n"
            ));
            // SAFETY: arm and dispatch validation succeeded exactly once and no code
            // after this call may execute under either firmware or kernel ownership.
            unsafe { transfer_to_kernel(transfer) };
        }
    }
    Err(firmware_failure(
        "exit.retry_exhausted",
        EFI_BUFFER_TOO_SMALL,
    ))
}
