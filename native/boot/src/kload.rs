use core::ffi::c_void;
use core::ptr::null_mut;
use core::slice::{from_raw_parts, from_raw_parts_mut};

use pooleboot::bootload::{self, ConfigSummary, ManifestSummary};

use super::{
    EFI_COMPROMISED_DATA, EFI_LOADER_DATA, EFI_OUT_OF_RESOURCES, EFI_SUCCESS, EfiBootServices,
    EfiGuid, EfiHandle, EfiStatus, function,
};

const EFI_ALLOCATE_ANY_PAGES: u32 = 0;
const EFI_FILE_MODE_READ: u64 = 1;
const EFI_LOADED_IMAGE_PROTOCOL_REVISION: u32 = 0x1000;
const EFI_SIMPLE_FILE_SYSTEM_PROTOCOL_REVISION: u64 = 0x0001_0000;
const EFI_FILE_PROTOCOL_REVISION: u64 = 0x0001_0000;
const EFI_FILE_PROTOCOL_REVISION2: u64 = 0x0002_0000;

const LOADED_IMAGE_GUID: EfiGuid = EfiGuid {
    data1: 0x5b1b_31a1,
    data2: 0x9562,
    data3: 0x11d2,
    data4: [0x8e, 0x3f, 0x00, 0xa0, 0xc9, 0x69, 0x72, 0x3b],
};
const SIMPLE_FILE_SYSTEM_GUID: EfiGuid = EfiGuid {
    data1: 0x964e_5b22,
    data2: 0x6459,
    data3: 0x11d2,
    data4: [0x8e, 0x39, 0x00, 0xa0, 0xc9, 0x69, 0x72, 0x3b],
};
const FILE_INFO_GUID: EfiGuid = EfiGuid {
    data1: 0x0957_6e92,
    data2: 0x6d3f,
    data3: 0x11d2,
    data4: [0x8e, 0x39, 0x00, 0xa0, 0xc9, 0x69, 0x72, 0x3b],
};

const CONFIG_PATH: [u16; 22] = [
    0x005c, 0x0045, 0x0046, 0x0049, 0x005c, 0x0050, 0x004f, 0x004f, 0x004c, 0x0045, 0x004f, 0x0053,
    0x005c, 0x0042, 0x004f, 0x004f, 0x0054, 0x002e, 0x0043, 0x0046, 0x0047, 0x0000,
];
#[repr(C)]
struct EfiLoadedImageProtocol {
    revision: u32,
    parent_handle: EfiHandle,
    system_table: *mut c_void,
    device_handle: EfiHandle,
    file_path: *mut c_void,
    reserved: *mut c_void,
    load_options_size: u32,
    load_options: *mut c_void,
    image_base: *mut c_void,
    image_size: u64,
    image_code_type: u32,
    image_data_type: u32,
    unload: usize,
}

#[repr(C)]
struct EfiSimpleFileSystemProtocol {
    revision: u64,
    open_volume: usize,
}

#[repr(C)]
struct EfiFileProtocol {
    revision: u64,
    open: usize,
    close: usize,
    delete: usize,
    read: usize,
    write: usize,
    get_position: usize,
    set_position: usize,
    get_info: usize,
    set_info: usize,
    flush: usize,
}

type HandleProtocol = extern "efiapi" fn(EfiHandle, *const EfiGuid, *mut *mut c_void) -> EfiStatus;
type OpenVolume =
    extern "efiapi" fn(*mut EfiSimpleFileSystemProtocol, *mut *mut EfiFileProtocol) -> EfiStatus;
type FileOpen = extern "efiapi" fn(
    *mut EfiFileProtocol,
    *mut *mut EfiFileProtocol,
    *const u16,
    u64,
    u64,
) -> EfiStatus;
type FileClose = extern "efiapi" fn(*mut EfiFileProtocol) -> EfiStatus;
type FileRead = extern "efiapi" fn(*mut EfiFileProtocol, *mut usize, *mut c_void) -> EfiStatus;
type FileGetInfo =
    extern "efiapi" fn(*mut EfiFileProtocol, *const EfiGuid, *mut usize, *mut c_void) -> EfiStatus;
type AllocatePool = extern "efiapi" fn(u32, usize, *mut *mut c_void) -> EfiStatus;
type FreePool = extern "efiapi" fn(*mut c_void) -> EfiStatus;
type AllocatePages = extern "efiapi" fn(u32, u32, usize, *mut u64) -> EfiStatus;
type FreePages = extern "efiapi" fn(u64, usize) -> EfiStatus;

#[derive(Clone, Copy)]
struct Calls {
    handle_protocol: HandleProtocol,
    allocate_pool: AllocatePool,
    free_pool: FreePool,
    allocate_pages: AllocatePages,
    free_pages: FreePages,
}

struct PoolFile {
    pointer: *mut c_void,
    byte_count: usize,
}

#[derive(Clone, Copy)]
pub(super) struct Failure {
    pub stage: &'static str,
    pub code: &'static str,
    pub status: EfiStatus,
}

#[derive(Clone, Copy)]
pub(super) struct Summary {
    pub config: ConfigSummary,
    pub manifest: ManifestSummary,
    pub kernel_digest_prefix: u64,
    pub kernel_file_bytes: usize,
    pub kernel_image_bytes: u32,
    pub page_count: usize,
    pub entry_offset: u32,
    pub relocation_count: u32,
    pub loaded_fnv1a64: u64,
    pub mapping_count: usize,
    pub mappings: [bootload::elf::MappingPlan; bootload::elf::MAPPING_COUNT],
    pub kernel_physical_base: u64,
    pub kernel_virtual_base: u64,
    pub kernel_entry_virtual: u64,
    pub kernel_sha256: [u8; 32],
    pub closed_file_count: usize,
    pub freed_pool_count: usize,
}

fn firmware_failure(stage: &'static str, status: EfiStatus) -> Failure {
    Failure {
        stage,
        code: "firmware_status",
        status,
    }
}

fn contract_failure(stage: &'static str, error: bootload::Error) -> Failure {
    Failure {
        stage,
        code: error.code(),
        status: EFI_COMPROMISED_DATA,
    }
}

fn close_file(file: *mut EfiFileProtocol, stage: &'static str) -> Result<(), Failure> {
    if file.is_null() {
        return Err(contract_failure(stage, bootload::Error::ResourceLeak));
    }
    let close: FileClose =
        unsafe { function((*file).close) }.map_err(|status| firmware_failure(stage, status))?;
    let status = close(file);
    if status == EFI_SUCCESS {
        Ok(())
    } else {
        Err(firmware_failure(stage, status))
    }
}

fn free_pool(calls: Calls, pointer: *mut c_void, stage: &'static str) -> Result<(), Failure> {
    if pointer.is_null() {
        return Err(contract_failure(stage, bootload::Error::ResourceLeak));
    }
    let status = (calls.free_pool)(pointer);
    if status == EFI_SUCCESS {
        Ok(())
    } else {
        Err(firmware_failure(stage, status))
    }
}

fn cleanup_file_failure(
    calls: Calls,
    file: *mut EfiFileProtocol,
    pool: *mut c_void,
    failure: Failure,
) -> Failure {
    let close_result = close_file(file, "kload.file.close_cleanup");
    let free_result = if pool.is_null() {
        Ok(())
    } else {
        free_pool(calls, pool, "kload.file.pool_cleanup")
    };
    close_result
        .err()
        .or_else(|| free_result.err())
        .unwrap_or(failure)
}

fn read_file(
    calls: Calls,
    root: *mut EfiFileProtocol,
    path: &[u16],
    maximum_file_size: usize,
    open_stage: &'static str,
    info_stage: &'static str,
    read_stage: &'static str,
) -> Result<PoolFile, Failure> {
    let open: FileOpen =
        unsafe { function((*root).open) }.map_err(|status| firmware_failure(open_stage, status))?;
    let mut file = null_mut();
    let status = open(root, &mut file, path.as_ptr(), EFI_FILE_MODE_READ, 0);
    if status != EFI_SUCCESS || file.is_null() {
        return Err(firmware_failure(
            open_stage,
            if status == EFI_SUCCESS {
                EFI_COMPROMISED_DATA
            } else {
                status
            },
        ));
    }
    let revision = unsafe { (*file).revision };
    if revision != EFI_FILE_PROTOCOL_REVISION && revision != EFI_FILE_PROTOCOL_REVISION2 {
        return Err(cleanup_file_failure(
            calls,
            file,
            null_mut(),
            contract_failure(info_stage, bootload::Error::FileInfoShape),
        ));
    }
    let get_info: FileGetInfo = match unsafe { function((*file).get_info) } {
        Ok(call) => call,
        Err(status) => {
            return Err(cleanup_file_failure(
                calls,
                file,
                null_mut(),
                firmware_failure(info_stage, status),
            ));
        }
    };
    let mut info = [0u8; bootload::MAX_FILE_INFO_BYTES];
    let mut info_size = info.len();
    let info_status = get_info(
        file,
        &FILE_INFO_GUID,
        &mut info_size,
        info.as_mut_ptr().cast(),
    );
    if info_status != EFI_SUCCESS {
        return Err(cleanup_file_failure(
            calls,
            file,
            null_mut(),
            firmware_failure(info_stage, info_status),
        ));
    }
    let metadata = match bootload::validate_file_info(&info, info_size, maximum_file_size) {
        Ok(metadata) => metadata,
        Err(error) => {
            return Err(cleanup_file_failure(
                calls,
                file,
                null_mut(),
                contract_failure(info_stage, error),
            ));
        }
    };
    let mut pool = null_mut();
    let pool_status = (calls.allocate_pool)(EFI_LOADER_DATA, metadata.file_size, &mut pool);
    if pool_status != EFI_SUCCESS || pool.is_null() {
        return Err(cleanup_file_failure(
            calls,
            file,
            null_mut(),
            firmware_failure(
                read_stage,
                if pool_status == EFI_SUCCESS {
                    EFI_OUT_OF_RESOURCES
                } else {
                    pool_status
                },
            ),
        ));
    }
    let read: FileRead = match unsafe { function((*file).read) } {
        Ok(call) => call,
        Err(status) => {
            return Err(cleanup_file_failure(
                calls,
                file,
                pool,
                firmware_failure(read_stage, status),
            ));
        }
    };
    let mut read_size = metadata.file_size;
    let read_status = read(file, &mut read_size, pool);
    if read_status != EFI_SUCCESS {
        return Err(cleanup_file_failure(
            calls,
            file,
            pool,
            firmware_failure(read_stage, read_status),
        ));
    }
    if let Err(error) = bootload::validate_exact_read(metadata.file_size, read_size) {
        return Err(cleanup_file_failure(
            calls,
            file,
            pool,
            contract_failure(read_stage, error),
        ));
    }
    if let Err(failure) = close_file(file, "kload.file.close") {
        let free_result = free_pool(calls, pool, "kload.file.pool_cleanup");
        return Err(free_result.err().unwrap_or(failure));
    }
    Ok(PoolFile {
        pointer: pool,
        byte_count: metadata.file_size,
    })
}

fn close_root_with_failure(root: *mut EfiFileProtocol, failure: Failure) -> Failure {
    close_file(root, "kload.root.close_cleanup")
        .err()
        .unwrap_or(failure)
}

fn free_pool_and_close_root(
    calls: Calls,
    pool: *mut c_void,
    root: *mut EfiFileProtocol,
    failure: Failure,
) -> Failure {
    let free_result = free_pool(calls, pool, "kload.pool.cleanup");
    let close_result = close_file(root, "kload.root.close_cleanup");
    free_result
        .err()
        .or_else(|| close_result.err())
        .unwrap_or(failure)
}

fn release_kernel_resources(
    calls: Calls,
    physical_base: u64,
    page_count: usize,
    kernel_pool: *mut c_void,
    root: *mut EfiFileProtocol,
) -> Result<(), Failure> {
    let page_status = (calls.free_pages)(physical_base, page_count);
    let page_result = if page_status == EFI_SUCCESS {
        Ok(())
    } else {
        Err(firmware_failure("kload.kernel.pages_free", page_status))
    };
    let pool_result = free_pool(calls, kernel_pool, "kload.kernel.pool_free");
    let root_result = close_file(root, "kload.root.close");
    page_result
        .err()
        .or_else(|| pool_result.err())
        .or_else(|| root_result.err())
        .map_or(Ok(()), Err)
}

fn release_file_resources_or_kernel(
    calls: Calls,
    physical_base: u64,
    page_count: usize,
    kernel_pool: *mut c_void,
    root: *mut EfiFileProtocol,
) -> Result<(), Failure> {
    let pool_result = free_pool(calls, kernel_pool, "kload.kernel.pool_free");
    let root_result = close_file(root, "kload.root.close");
    if pool_result.is_ok() && root_result.is_ok() {
        return Ok(());
    }
    let page_status = (calls.free_pages)(physical_base, page_count);
    let page_result = if page_status == EFI_SUCCESS {
        Ok(())
    } else {
        Err(firmware_failure(
            "kload.kernel.pages_cleanup_after_file_release",
            page_status,
        ))
    };
    page_result
        .err()
        .or_else(|| pool_result.err())
        .or_else(|| root_result.err())
        .map_or(Ok(()), Err)
}

pub(super) fn load_manifest_kernel(
    image_handle: EfiHandle,
    boot_services: &EfiBootServices,
) -> Result<Summary, Failure> {
    let calls = Calls {
        handle_protocol: unsafe { function(boot_services.handle_protocol) }
            .map_err(|status| firmware_failure("kload.handle_protocol_pointer", status))?,
        allocate_pool: unsafe { function(boot_services.allocate_pool) }
            .map_err(|status| firmware_failure("kload.allocate_pool_pointer", status))?,
        free_pool: unsafe { function(boot_services.free_pool) }
            .map_err(|status| firmware_failure("kload.free_pool_pointer", status))?,
        allocate_pages: unsafe { function(boot_services.allocate_pages) }
            .map_err(|status| firmware_failure("kload.allocate_pages_pointer", status))?,
        free_pages: unsafe { function(boot_services.free_pages) }
            .map_err(|status| firmware_failure("kload.free_pages_pointer", status))?,
    };

    let mut loaded_interface = null_mut();
    let loaded_status =
        (calls.handle_protocol)(image_handle, &LOADED_IMAGE_GUID, &mut loaded_interface);
    if loaded_status != EFI_SUCCESS || loaded_interface.is_null() {
        return Err(firmware_failure(
            "kload.loaded_image",
            if loaded_status == EFI_SUCCESS {
                EFI_COMPROMISED_DATA
            } else {
                loaded_status
            },
        ));
    }
    let loaded = unsafe { &*(loaded_interface as *const EfiLoadedImageProtocol) };
    if loaded.revision < EFI_LOADED_IMAGE_PROTOCOL_REVISION || loaded.device_handle.is_null() {
        return Err(contract_failure(
            "kload.loaded_image_shape",
            bootload::Error::AddressRange,
        ));
    }

    let mut filesystem_interface = null_mut();
    let filesystem_status = (calls.handle_protocol)(
        loaded.device_handle,
        &SIMPLE_FILE_SYSTEM_GUID,
        &mut filesystem_interface,
    );
    if filesystem_status != EFI_SUCCESS || filesystem_interface.is_null() {
        return Err(firmware_failure(
            "kload.simple_filesystem",
            if filesystem_status == EFI_SUCCESS {
                EFI_COMPROMISED_DATA
            } else {
                filesystem_status
            },
        ));
    }
    let filesystem = unsafe { &*(filesystem_interface as *const EfiSimpleFileSystemProtocol) };
    if filesystem.revision != EFI_SIMPLE_FILE_SYSTEM_PROTOCOL_REVISION {
        return Err(contract_failure(
            "kload.simple_filesystem_shape",
            bootload::Error::FileInfoShape,
        ));
    }
    let open_volume: OpenVolume = unsafe { function(filesystem.open_volume) }
        .map_err(|status| firmware_failure("kload.open_volume_pointer", status))?;
    let mut root = null_mut();
    let root_status = open_volume(filesystem_interface.cast(), &mut root);
    if root_status != EFI_SUCCESS || root.is_null() {
        return Err(firmware_failure(
            "kload.open_volume",
            if root_status == EFI_SUCCESS {
                EFI_COMPROMISED_DATA
            } else {
                root_status
            },
        ));
    }

    let config_file = match read_file(
        calls,
        root,
        &CONFIG_PATH,
        bootload::boot_config::MAX_CONFIG_BYTES,
        "kload.config.open",
        "kload.config.info",
        "kload.config.read",
    ) {
        Ok(file) => file,
        Err(failure) => return Err(close_root_with_failure(root, failure)),
    };
    let config_bytes =
        unsafe { from_raw_parts(config_file.pointer.cast::<u8>(), config_file.byte_count) };
    let config = match bootload::parse_config(config_bytes) {
        Ok(config) => config,
        Err(error) => {
            return Err(free_pool_and_close_root(
                calls,
                config_file.pointer,
                root,
                contract_failure("kload.config.parse", error),
            ));
        }
    };
    let manifest_path = match bootload::encode_uefi_path(&config.manifest_path) {
        Ok(path) => path,
        Err(error) => {
            return Err(free_pool_and_close_root(
                calls,
                config_file.pointer,
                root,
                contract_failure("kload.config.manifest_path", error),
            ));
        }
    };
    if let Err(failure) = free_pool(calls, config_file.pointer, "kload.config.pool_free") {
        return Err(close_root_with_failure(root, failure));
    }

    let manifest_file = match read_file(
        calls,
        root,
        &manifest_path,
        config.manifest_max_bytes as usize,
        "kload.manifest.open",
        "kload.manifest.info",
        "kload.manifest.read",
    ) {
        Ok(file) => file,
        Err(failure) => return Err(close_root_with_failure(root, failure)),
    };
    let manifest_bytes =
        unsafe { from_raw_parts(manifest_file.pointer.cast::<u8>(), manifest_file.byte_count) };
    let manifest = match bootload::parse_manifest(manifest_bytes, config.selected_slot) {
        Ok(manifest) => manifest,
        Err(error) => {
            return Err(free_pool_and_close_root(
                calls,
                manifest_file.pointer,
                root,
                contract_failure("kload.manifest.parse", error),
            ));
        }
    };
    let kernel_path = match bootload::encode_uefi_path(&manifest.kernel_path) {
        Ok(path) => path,
        Err(error) => {
            return Err(free_pool_and_close_root(
                calls,
                manifest_file.pointer,
                root,
                contract_failure("kload.manifest.kernel_path", error),
            ));
        }
    };
    if let Err(failure) = free_pool(calls, manifest_file.pointer, "kload.manifest.pool_free") {
        return Err(close_root_with_failure(root, failure));
    }

    let kernel_file = match read_file(
        calls,
        root,
        &kernel_path,
        manifest.kernel_file_bytes,
        "kload.kernel.open",
        "kload.kernel.info",
        "kload.kernel.read",
    ) {
        Ok(file) => file,
        Err(failure) => return Err(close_root_with_failure(root, failure)),
    };
    let kernel_bytes =
        unsafe { from_raw_parts(kernel_file.pointer.cast::<u8>(), kernel_file.byte_count) };
    let allocation = match bootload::plan_manifest_kernel(kernel_bytes, &manifest) {
        Ok(plan) => plan,
        Err(error) => {
            return Err(free_pool_and_close_root(
                calls,
                kernel_file.pointer,
                root,
                contract_failure("kload.kernel.plan", error),
            ));
        }
    };
    let mut physical_base = 0u64;
    let allocate_status = (calls.allocate_pages)(
        EFI_ALLOCATE_ANY_PAGES,
        EFI_LOADER_DATA,
        allocation.page_count,
        &mut physical_base,
    );
    if allocate_status != EFI_SUCCESS {
        return Err(free_pool_and_close_root(
            calls,
            kernel_file.pointer,
            root,
            firmware_failure("kload.kernel.pages_allocate", allocate_status),
        ));
    }
    let allocation_bytes = match allocation
        .page_count
        .checked_mul(bootload::elf::PAGE_SIZE as usize)
    {
        Some(value) => value,
        None => {
            let failure = contract_failure("kload.kernel.pages_shape", bootload::Error::PageCount);
            return Err(release_kernel_resources(
                calls,
                physical_base,
                allocation.page_count,
                kernel_file.pointer,
                root,
            )
            .err()
            .unwrap_or(failure));
        }
    };
    if physical_base > usize::MAX as u64 {
        let failure = contract_failure("kload.kernel.pages_address", bootload::Error::AddressRange);
        return Err(release_kernel_resources(
            calls,
            physical_base,
            allocation.page_count,
            kernel_file.pointer,
            root,
        )
        .err()
        .unwrap_or(failure));
    }
    let destination =
        unsafe { from_raw_parts_mut(physical_base as usize as *mut u8, allocation_bytes) };
    let loaded =
        match bootload::load_manifest_kernel(kernel_bytes, &manifest, physical_base, destination) {
            Ok(loaded) => loaded,
            Err(error) => {
                let failure = contract_failure("kload.kernel.load", error);
                return Err(release_kernel_resources(
                    calls,
                    physical_base,
                    allocation.page_count,
                    kernel_file.pointer,
                    root,
                )
                .err()
                .unwrap_or(failure));
            }
        };

    let summary = Summary {
        config,
        manifest,
        kernel_digest_prefix: bootload::manifest::digest_prefix(&manifest.kernel_sha256),
        kernel_file_bytes: kernel_file.byte_count,
        kernel_image_bytes: loaded.image.image_size,
        page_count: loaded.page_count,
        entry_offset: loaded.image.entry_offset,
        relocation_count: loaded.image.relocation_count,
        loaded_fnv1a64: loaded.loaded_fnv1a64,
        mapping_count: loaded.image.mappings.len(),
        mappings: loaded.image.mappings,
        kernel_physical_base: loaded.image.physical_base,
        kernel_virtual_base: loaded.image.virtual_base,
        kernel_entry_virtual: loaded.image.entry_virtual,
        kernel_sha256: manifest.kernel_sha256,
        closed_file_count: 4,
        freed_pool_count: 3,
    };
    release_file_resources_or_kernel(
        calls,
        physical_base,
        allocation.page_count,
        kernel_file.pointer,
        root,
    )?;
    Ok(summary)
}

pub(super) fn release_kernel_pages(
    boot_services: &EfiBootServices,
    physical_base: u64,
    page_count: usize,
) -> Result<(), Failure> {
    if physical_base == 0 || page_count == 0 {
        return Err(contract_failure(
            "kload.kernel.pages_release_shape",
            bootload::Error::ResourceLeak,
        ));
    }
    let free_pages: FreePages = unsafe { function(boot_services.free_pages) }
        .map_err(|status| firmware_failure("kload.free_pages_pointer", status))?;
    let status = free_pages(physical_base, page_count);
    if status == EFI_SUCCESS {
        Ok(())
    } else {
        Err(firmware_failure("kload.kernel.pages_free", status))
    }
}
