use core::ffi::c_void;
use core::fmt;
use core::ptr::null_mut;
use core::slice::{from_raw_parts, from_raw_parts_mut};

use poole_live_handoff::{
    self as live, ArtifactInput, BuildInput, FramebufferInput, KernelInput, MAX_MEMORY_ENTRIES,
    PROFILE_ARTIFACT_COUNT,
};

use super::{
    EFI_BUFFER_TOO_SMALL, EFI_COMPROMISED_DATA, EFI_LOADER_DATA, EFI_OUT_OF_RESOURCES, EFI_SUCCESS,
    EfiBootServices, EfiStatus, GetMemoryMap, GopSummary, allocate_pool_call, free_pool_call,
    function,
};

const MAX_MAP_ATTEMPTS: usize = 4;

#[derive(Clone, Copy)]
struct Calls {
    get_memory_map: GetMemoryMap,
    allocate_pool: super::AllocatePool,
    free_pool: super::FreePool,
}

#[derive(Clone, Copy)]
pub(super) struct Failure {
    pub stage: &'static str,
    pub code: &'static str,
    pub status: EfiStatus,
}

#[derive(Clone, Copy)]
pub(super) struct Summary {
    pub handoff: live::Summary,
    pub descriptor_size: usize,
    pub map_attempts: usize,
    pub pools_freed: usize,
    pub bytes_unchanged: bool,
}

struct Hex<'a>(&'a [u8]);

impl fmt::Display for Hex<'_> {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        for byte in self.0 {
            write!(formatter, "{byte:02X}")?;
        }
        Ok(())
    }
}

fn firmware_failure(stage: &'static str, status: EfiStatus) -> Failure {
    Failure {
        stage,
        code: "firmware_status",
        status,
    }
}

fn contract_failure(stage: &'static str, error: live::Error) -> Failure {
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

fn allocate(calls: Calls, byte_count: usize, stage: &'static str) -> Result<*mut c_void, Failure> {
    if byte_count == 0 {
        return Err(contract_failure(stage, live::Error::ScratchCapacity));
    }
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

fn release_pools(
    calls: Calls,
    pointers: &mut [*mut c_void; 3],
    primary: Option<Failure>,
) -> Result<(), Failure> {
    let mut failure = primary;
    for (index, pointer) in pointers.iter_mut().enumerate().rev() {
        if pointer.is_null() {
            continue;
        }
        let status = free_pool_call(calls.free_pool, *pointer);
        *pointer = null_mut();
        if status != EFI_SUCCESS && failure.is_none() {
            failure = Some(firmware_failure(
                match index {
                    0 => "pbp1.raw_map_pool_free",
                    1 => "pbp1.normalized_pool_free",
                    _ => "pbp1.container_pool_free",
                },
                status,
            ));
        }
    }
    failure.map_or(Ok(()), Err)
}

pub(super) fn framebuffer(gop: Option<GopSummary>) -> Option<FramebufferInput> {
    gop.map(|summary| {
        let (pixel_format, red_mask, green_mask, blue_mask) = match summary.layout.format {
            pooleboot::PixelFormat::Rgb => (1, 0x0000_00ff, 0x0000_ff00, 0x00ff_0000),
            pooleboot::PixelFormat::Bgr => (2, 0x00ff_0000, 0x0000_ff00, 0x0000_00ff),
        };
        FramebufferInput {
            physical_base: summary.physical_base,
            byte_count: summary.byte_count as u64,
            width: summary.layout.width as u32,
            height: summary.layout.height as u32,
            stride: summary.layout.stride as u32,
            pixel_format,
            red_mask,
            green_mask,
            blue_mask,
            reserved_mask: 0xff00_0000,
        }
    })
}

pub(super) fn artifacts(
    kernel: &super::kload::Summary,
) -> Result<[ArtifactInput; PROFILE_ARTIFACT_COUNT], live::Error> {
    let kernel_physical_size = (kernel.page_count as u64)
        .checked_mul(poole_handoff::PAGE_BYTES)
        .ok_or(live::Error::ArtifactSet)?;
    let mut values = [ArtifactInput {
        role: poole_handoff::ARTIFACT_KERNEL,
        flags: poole_handoff::ARTIFACT_HASH_VERIFIED | poole_handoff::ARTIFACT_EXECUTABLE,
        physical_base: kernel.kernel_physical_base,
        physical_size: kernel_physical_size,
        virtual_base: kernel.kernel_virtual_base,
        virtual_size: kernel.kernel_image_bytes as u64,
        entry_virtual: kernel.kernel_entry_virtual,
        sha256: kernel.kernel_sha256,
    }; PROFILE_ARTIFACT_COUNT];
    for (index, artifact) in kernel.artifacts.iter().enumerate() {
        let physical_size = (artifact.page_count as u64)
            .checked_mul(poole_handoff::PAGE_BYTES)
            .ok_or(live::Error::ArtifactSet)?;
        if artifact.file_bytes == 0 || artifact.file_bytes as u64 > physical_size {
            return Err(live::Error::ArtifactSet);
        }
        values[index + 1] = ArtifactInput {
            role: artifact.role.code(),
            flags: poole_handoff::ARTIFACT_HASH_VERIFIED,
            physical_base: artifact.physical_base,
            physical_size,
            virtual_base: 0,
            virtual_size: 0,
            entry_virtual: 0,
            sha256: artifact.sha256,
        };
    }
    Ok(values)
}

pub(super) fn emit_transcript(bytes: &[u8], summary: live::Summary) {
    super::diagnostic(format_args!("PBP1HEX/0.1 BEGIN bytes={}\n", bytes.len()));
    for (index, chunk) in bytes.chunks(live::MAX_TRANSCRIPT_CHUNK_BYTES).enumerate() {
        super::diagnostic(format_args!(
            "PBP1HEX/0.1 DATA offset={} hex={}\n",
            index * live::MAX_TRANSCRIPT_CHUNK_BYTES,
            Hex(chunk)
        ));
    }
    super::diagnostic(format_args!(
        "PBP1HEX/0.1 END bytes={} message_crc32={:08X} fnv1a64={:016X}\n",
        bytes.len(),
        summary.message_crc32,
        summary.fnv1a64
    ));
}

pub(super) fn produce(
    boot_services: &EfiBootServices,
    kernel: &super::kload::Summary,
    gop: Option<GopSummary>,
    uefi_revision: u32,
) -> Result<Summary, Failure> {
    let calls = Calls {
        get_memory_map: unsafe { function(boot_services.get_memory_map) }
            .map_err(|status| firmware_failure("pbp1.get_memory_map_pointer", status))?,
        allocate_pool: unsafe { function(boot_services.allocate_pool) }
            .map_err(|status| firmware_failure("pbp1.allocate_pool_pointer", status))?,
        free_pool: unsafe { function(boot_services.free_pool) }
            .map_err(|status| firmware_failure("pbp1.free_pool_pointer", status))?,
    };

    for attempt in 1..=MAX_MAP_ATTEMPTS {
        let mut required_size = 0usize;
        let mut map_key = 0usize;
        let mut descriptor_size = 0usize;
        let mut descriptor_version = 0u32;
        let probe_status = (calls.get_memory_map)(
            &mut required_size,
            null_mut(),
            &mut map_key,
            &mut descriptor_size,
            &mut descriptor_version,
        );
        let plan = pooleboot::plan_memory_map(probe_status, required_size, descriptor_size)
            .map_err(|_| contract_failure("pbp1.memory_map_probe", live::Error::MemoryMapShape))?;
        let maximum_entries = plan.allocation_size / plan.descriptor_size;
        if maximum_entries == 0 || maximum_entries > MAX_MEMORY_ENTRIES {
            return Err(contract_failure(
                "pbp1.memory_map_capacity",
                live::Error::MemoryMapShape,
            ));
        }
        let normalized_bytes = maximum_entries
            .checked_mul(poole_handoff::MEMORY_ENTRY_BYTES)
            .ok_or_else(|| {
                contract_failure("pbp1.normalized_size", live::Error::ScratchCapacity)
            })?;
        let mut pools = [null_mut(); 3];
        pools[0] = allocate(calls, plan.allocation_size, "pbp1.raw_map_pool_allocate")?;
        pools[1] = match allocate(calls, normalized_bytes, "pbp1.normalized_pool_allocate") {
            Ok(pointer) => pointer,
            Err(failure) => {
                return release_pools(calls, &mut pools, Some(failure)).and(Err(failure));
            }
        };
        pools[2] = match allocate(
            calls,
            poole_handoff::MAX_TOTAL_BYTES,
            "pbp1.container_pool_allocate",
        ) {
            Ok(pointer) => pointer,
            Err(failure) => {
                return release_pools(calls, &mut pools, Some(failure)).and(Err(failure));
            }
        };

        let mut map_size = plan.allocation_size;
        let final_status = (calls.get_memory_map)(
            &mut map_size,
            pools[0],
            &mut map_key,
            &mut descriptor_size,
            &mut descriptor_version,
        );
        if final_status == EFI_BUFFER_TOO_SMALL {
            release_pools(calls, &mut pools, None)?;
            continue;
        }
        let memory_map = match pooleboot::validate_memory_map_result(
            final_status,
            map_size,
            plan.allocation_size,
            descriptor_size,
        ) {
            Ok(summary) => summary,
            Err(_) => {
                let failure =
                    contract_failure("pbp1.memory_map_final", live::Error::MemoryMapShape);
                return release_pools(calls, &mut pools, Some(failure)).and(Err(failure));
            }
        };
        let raw = unsafe { from_raw_parts(pools[0].cast::<u8>(), memory_map.map_size) };
        let normalized = unsafe { from_raw_parts_mut(pools[1].cast::<u8>(), normalized_bytes) };
        let output =
            unsafe { from_raw_parts_mut(pools[2].cast::<u8>(), poole_handoff::MAX_TOTAL_BYTES) };
        let physical_size = (kernel.page_count as u64)
            .checked_mul(poole_handoff::PAGE_BYTES)
            .ok_or_else(|| contract_failure("pbp1.kernel_range", live::Error::MemoryRange))?;
        let input = BuildInput {
            raw_memory_map: raw,
            descriptor_size: memory_map.descriptor_size,
            descriptor_version,
            handoff_physical_base: pools[2] as usize as u64,
            kernel: KernelInput {
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
            },
            artifacts: artifacts(kernel)
                .map_err(|error| contract_failure("pbp1.artifact_set", error))?,
            framebuffer: framebuffer(gop),
        };
        let (bytes, handoff) = match live::build_pre_exit(input, normalized, output) {
            Ok(value) => value,
            Err(error) => {
                let failure = contract_failure("pbp1.encode", error);
                return release_pools(calls, &mut pools, Some(failure)).and(Err(failure));
            }
        };
        let before = live::fnv1a64(bytes);
        emit_transcript(bytes, handoff);
        let unchanged = before == live::fnv1a64(bytes)
            && poole_handoff::decode(bytes)
                .and_then(|decoded| {
                    live::validate_pre_exit_profile(&decoded)
                        .map_err(|_| poole_handoff::Error::KernelProfile)
                })
                .is_ok();
        if !unchanged {
            let failure =
                contract_failure("pbp1.logical_finalization", live::Error::PreExitProfile);
            return release_pools(calls, &mut pools, Some(failure)).and(Err(failure));
        }
        let summary = Summary {
            handoff,
            descriptor_size: memory_map.descriptor_size,
            map_attempts: attempt,
            pools_freed: 3,
            bytes_unchanged: true,
        };
        release_pools(calls, &mut pools, None)?;
        return Ok(summary);
    }
    Err(firmware_failure(
        "pbp1.memory_map_retry_exhausted",
        EFI_BUFFER_TOO_SMALL,
    ))
}
