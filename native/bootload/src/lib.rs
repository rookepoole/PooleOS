#![no_std]
#![deny(warnings)]

pub use poole_boot_config as boot_config;
pub use poole_elf as elf;
pub use poole_manifest as manifest;

pub const CONTRACT_ID: &str = "PKLOAD2";
pub const VIRTUAL_BASE: u64 = poole_elf::MIN_VIRTUAL_BASE;
pub const EFI_FILE_INFO_FIXED_BYTES: usize = 80;
pub const MAX_FILE_INFO_BYTES: usize = 512;
pub const EFI_FILE_ATTRIBUTE_DIRECTORY: u64 = 0x10;
pub const EFI_FILE_VALID_ATTRIBUTES: u64 = 0x37;
pub const MAX_RESOURCE_DEPTH: usize = 8;
pub const MAX_UEFI_PATH_UNITS: usize = poole_manifest::MAX_PATH_BYTES + 1;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    FileInfoBounds,
    FileInfoShape,
    FileInfoAttributes,
    FileSize,
    ShortRead,
    PageCount,
    AddressRange,
    MappingPlan,
    ResourceOverflow,
    ResourceOrder,
    ResourceLeak,
    PathEncoding,
    ManifestBinding,
    BootConfig(poole_boot_config::Error),
    Manifest(poole_manifest::Error),
    Elf(poole_elf::Error),
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::FileInfoBounds => "file_info_bounds",
            Self::FileInfoShape => "file_info_shape",
            Self::FileInfoAttributes => "file_info_attributes",
            Self::FileSize => "file_size",
            Self::ShortRead => "short_read",
            Self::PageCount => "page_count",
            Self::AddressRange => "address_range",
            Self::MappingPlan => "mapping_plan",
            Self::ResourceOverflow => "resource_overflow",
            Self::ResourceOrder => "resource_order",
            Self::ResourceLeak => "resource_leak",
            Self::PathEncoding => "path_encoding",
            Self::ManifestBinding => "manifest_binding",
            Self::BootConfig(error) => error.code(),
            Self::Manifest(error) => error.code(),
            Self::Elf(error) => error.code(),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct OwnedPath {
    bytes: [u8; poole_manifest::MAX_PATH_BYTES],
    length: u16,
}

impl OwnedPath {
    pub fn copy_from(value: &str) -> Result<Self, Error> {
        if value.is_empty() || value.len() > poole_manifest::MAX_PATH_BYTES || !value.is_ascii() {
            return Err(Error::PathEncoding);
        }
        let mut bytes = [0u8; poole_manifest::MAX_PATH_BYTES];
        bytes[..value.len()].copy_from_slice(value.as_bytes());
        Ok(Self {
            bytes,
            length: value.len() as u16,
        })
    }

    pub fn as_bytes(&self) -> &[u8] {
        &self.bytes[..usize::from(self.length)]
    }

    pub const fn len(&self) -> usize {
        self.length as usize
    }

    pub const fn is_empty(&self) -> bool {
        self.length == 0
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FileMetadata {
    pub file_size: usize,
    pub physical_size: u64,
    pub attributes: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ConfigSummary {
    pub byte_count: usize,
    pub entry_count: usize,
    pub default_entry_hash: u64,
    pub timeout_ms: u32,
    pub boot_attempt_limit: u8,
    pub selected_slot: u8,
    pub manifest_max_bytes: u32,
    pub manifest_path: OwnedPath,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ManifestSummary {
    pub byte_count: usize,
    pub artifact_count: usize,
    pub manifest_id_hash: u64,
    pub slot: u8,
    pub manifest_version: u64,
    pub minimum_secure_version: u64,
    pub kernel_version: u64,
    pub kernel_path: OwnedPath,
    pub kernel_file_bytes: usize,
    pub kernel_image_bytes: usize,
    pub kernel_sha256: [u8; 32],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct KernelAllocationPlan {
    pub file_size: usize,
    pub image_size: usize,
    pub page_count: usize,
    pub entry_offset: u32,
    pub relocation_count: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LoadedKernel {
    pub image: poole_elf::ImagePlan,
    pub page_count: usize,
    pub loaded_fnv1a64: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ResourceKind {
    RootFile,
    ConfigFile,
    ConfigPool,
    ManifestFile,
    ManifestPool,
    KernelFile,
    KernelPool,
    KernelPages,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ResourceStack {
    resources: [Option<ResourceKind>; MAX_RESOURCE_DEPTH],
    length: usize,
}

impl ResourceStack {
    pub const fn new() -> Self {
        Self {
            resources: [None; MAX_RESOURCE_DEPTH],
            length: 0,
        }
    }

    pub fn push(&mut self, resource: ResourceKind) -> Result<(), Error> {
        if self.length == self.resources.len() {
            return Err(Error::ResourceOverflow);
        }
        self.resources[self.length] = Some(resource);
        self.length += 1;
        Ok(())
    }

    pub fn release(&mut self, expected: ResourceKind) -> Result<(), Error> {
        if self.length == 0 || self.resources[self.length - 1] != Some(expected) {
            return Err(Error::ResourceOrder);
        }
        self.length -= 1;
        self.resources[self.length] = None;
        Ok(())
    }

    pub const fn outstanding(&self) -> usize {
        self.length
    }

    pub fn finish(self) -> Result<(), Error> {
        if self.length == 0 {
            Ok(())
        } else {
            Err(Error::ResourceLeak)
        }
    }
}

impl Default for ResourceStack {
    fn default() -> Self {
        Self::new()
    }
}

fn read_u64(bytes: &[u8], offset: usize) -> Result<u64, Error> {
    let value = bytes.get(offset..offset + 8).ok_or(Error::FileInfoBounds)?;
    Ok(u64::from_le_bytes([
        value[0], value[1], value[2], value[3], value[4], value[5], value[6], value[7],
    ]))
}

pub fn validate_file_info(
    bytes: &[u8],
    returned_size: usize,
    maximum_file_size: usize,
) -> Result<FileMetadata, Error> {
    if !(EFI_FILE_INFO_FIXED_BYTES + 2..=MAX_FILE_INFO_BYTES).contains(&returned_size)
        || returned_size > bytes.len()
    {
        return Err(Error::FileInfoBounds);
    }
    if !(returned_size - EFI_FILE_INFO_FIXED_BYTES).is_multiple_of(2) {
        return Err(Error::FileInfoShape);
    }
    let declared_size = read_u64(bytes, 0)?;
    if declared_size != returned_size as u64
        || bytes[returned_size - 2] != 0
        || bytes[returned_size - 1] != 0
    {
        return Err(Error::FileInfoShape);
    }
    let file_size_u64 = read_u64(bytes, 8)?;
    let physical_size = read_u64(bytes, 16)?;
    let attributes = read_u64(bytes, 72)?;
    if attributes & !EFI_FILE_VALID_ATTRIBUTES != 0
        || attributes & EFI_FILE_ATTRIBUTE_DIRECTORY != 0
    {
        return Err(Error::FileInfoAttributes);
    }
    let file_size = usize::try_from(file_size_u64).map_err(|_| Error::FileSize)?;
    if file_size == 0 || file_size > maximum_file_size || physical_size < file_size_u64 {
        return Err(Error::FileSize);
    }
    Ok(FileMetadata {
        file_size,
        physical_size,
        attributes,
    })
}

pub fn validate_exact_read(requested_size: usize, returned_size: usize) -> Result<(), Error> {
    if requested_size == 0 || returned_size != requested_size {
        Err(Error::ShortRead)
    } else {
        Ok(())
    }
}

pub fn page_count(byte_count: usize) -> Result<usize, Error> {
    if byte_count == 0 || byte_count > poole_elf::MAX_IMAGE_BYTES as usize {
        return Err(Error::PageCount);
    }
    byte_count
        .checked_add(poole_elf::PAGE_SIZE as usize - 1)
        .map(|rounded| rounded / poole_elf::PAGE_SIZE as usize)
        .filter(|pages| *pages != 0)
        .ok_or(Error::PageCount)
}

pub fn parse_config(bytes: &[u8]) -> Result<ConfigSummary, Error> {
    let mut storage = [poole_boot_config::Entry::EMPTY; poole_boot_config::MAX_ENTRIES];
    let config = poole_boot_config::parse(bytes, &mut storage).map_err(Error::BootConfig)?;
    let selected = config
        .entries
        .iter()
        .find(|entry| entry.id == config.default_entry)
        .ok_or(Error::BootConfig(poole_boot_config::Error::DefaultEntry))?;
    Ok(ConfigSummary {
        byte_count: bytes.len(),
        entry_count: config.entries.len(),
        default_entry_hash: poole_elf::fnv1a64(config.default_entry.as_bytes()),
        timeout_ms: config.timeout_ms,
        boot_attempt_limit: config.boot_attempt_limit,
        selected_slot: selected.slot,
        manifest_max_bytes: selected.manifest_max_bytes,
        manifest_path: OwnedPath::copy_from(selected.manifest)?,
    })
}

pub fn encode_uefi_path(path: &OwnedPath) -> Result<[u16; MAX_UEFI_PATH_UNITS], Error> {
    if path.is_empty() || path.len() + 1 > MAX_UEFI_PATH_UNITS {
        return Err(Error::PathEncoding);
    }
    let mut units = [0u16; MAX_UEFI_PATH_UNITS];
    for (index, byte) in path.as_bytes().iter().copied().enumerate() {
        if !(b'!'..=b'~').contains(&byte) {
            return Err(Error::PathEncoding);
        }
        units[index] = u16::from(byte);
    }
    Ok(units)
}

pub fn parse_manifest(bytes: &[u8], selected_slot: u8) -> Result<ManifestSummary, Error> {
    let mut storage = [poole_manifest::Artifact::EMPTY; poole_manifest::MAX_ARTIFACTS];
    let manifest = poole_manifest::parse(bytes, &mut storage).map_err(Error::Manifest)?;
    if manifest.slot != selected_slot {
        return Err(Error::ManifestBinding);
    }
    let kernel = manifest.kernel().map_err(Error::Manifest)?;
    let kernel_file_bytes =
        usize::try_from(kernel.file_bytes).map_err(|_| Error::ManifestBinding)?;
    let kernel_image_bytes =
        usize::try_from(kernel.image_bytes).map_err(|_| Error::ManifestBinding)?;
    if kernel_file_bytes == 0
        || kernel_file_bytes > poole_elf::MAX_FILE_BYTES
        || kernel_image_bytes == 0
        || kernel_image_bytes > poole_elf::MAX_IMAGE_BYTES as usize
    {
        return Err(Error::ManifestBinding);
    }
    Ok(ManifestSummary {
        byte_count: bytes.len(),
        artifact_count: manifest.artifacts.len(),
        manifest_id_hash: poole_elf::fnv1a64(manifest.manifest_id.as_bytes()),
        slot: manifest.slot,
        manifest_version: manifest.manifest_version,
        minimum_secure_version: manifest.minimum_secure_version,
        kernel_version: kernel.version,
        kernel_path: OwnedPath::copy_from(kernel.path)?,
        kernel_file_bytes,
        kernel_image_bytes,
        kernel_sha256: kernel.sha256,
    })
}

pub fn verify_manifest_kernel(manifest: &ManifestSummary, bytes: &[u8]) -> Result<[u8; 32], Error> {
    if bytes.len() != manifest.kernel_file_bytes {
        return Err(Error::ManifestBinding);
    }
    let digest = poole_manifest::sha256(bytes);
    if digest != manifest.kernel_sha256 {
        return Err(Error::ManifestBinding);
    }
    Ok(digest)
}

pub fn validate_image_plan(plan: &poole_elf::ImagePlan) -> Result<(), Error> {
    if plan.virtual_base != VIRTUAL_BASE
        || plan.physical_base < poole_elf::MIN_PHYSICAL_BASE
        || plan.physical_base >= poole_elf::MAX_PHYSICAL_EXCLUSIVE
        || !plan.physical_base.is_multiple_of(poole_elf::PAGE_SIZE)
        || plan.image_size == 0
        || u64::from(plan.image_size) > poole_elf::MAX_IMAGE_BYTES
        || !plan.image_size.is_multiple_of(poole_elf::PAGE_SIZE as u32)
    {
        return Err(Error::AddressRange);
    }
    let expected_permissions = [
        poole_elf::Permissions::READ,
        poole_elf::Permissions::READ_EXECUTE,
        poole_elf::Permissions::READ,
        poole_elf::Permissions::READ_WRITE,
    ];
    let mut previous_end = 0u64;
    for (index, (mapping, expected)) in plan.mappings.iter().zip(expected_permissions).enumerate() {
        if mapping.permissions != expected
            || mapping.permissions.write && mapping.permissions.execute
            || mapping.memory_size == 0
            || !mapping
                .virtual_offset
                .is_multiple_of(poole_elf::PAGE_SIZE as u32)
            || !mapping
                .memory_size
                .is_multiple_of(poole_elf::PAGE_SIZE as u32)
        {
            return Err(Error::MappingPlan);
        }
        let start = u64::from(mapping.virtual_offset);
        let end = start
            .checked_add(u64::from(mapping.memory_size))
            .ok_or(Error::MappingPlan)?;
        if (index == 0 && start != 0) || start < previous_end || end > u64::from(plan.image_size) {
            return Err(Error::MappingPlan);
        }
        previous_end = end;
    }
    let executable = plan.mappings[1];
    let entry = u64::from(plan.entry_offset);
    let executable_end = u64::from(executable.virtual_offset)
        .checked_add(u64::from(executable.memory_size))
        .ok_or(Error::MappingPlan)?;
    if entry < u64::from(executable.virtual_offset)
        || entry >= executable_end
        || plan.entry_virtual != VIRTUAL_BASE + entry
        || plan.entry_physical != plan.physical_base + entry
    {
        return Err(Error::MappingPlan);
    }
    Ok(())
}

pub fn plan_kernel(bytes: &[u8]) -> Result<KernelAllocationPlan, Error> {
    let plan = poole_elf::inspect(bytes, poole_elf::MIN_PHYSICAL_BASE, VIRTUAL_BASE)
        .map_err(Error::Elf)?;
    validate_image_plan(&plan)?;
    Ok(KernelAllocationPlan {
        file_size: bytes.len(),
        image_size: plan.image_size as usize,
        page_count: page_count(plan.image_size as usize)?,
        entry_offset: plan.entry_offset,
        relocation_count: plan.relocation_count,
    })
}

pub fn plan_manifest_kernel(
    bytes: &[u8],
    manifest: &ManifestSummary,
) -> Result<KernelAllocationPlan, Error> {
    verify_manifest_kernel(manifest, bytes)?;
    let plan = plan_kernel(bytes)?;
    if plan.file_size != manifest.kernel_file_bytes
        || plan.image_size != manifest.kernel_image_bytes
    {
        return Err(Error::ManifestBinding);
    }
    Ok(plan)
}

pub fn load_kernel(
    bytes: &[u8],
    physical_base: u64,
    destination: &mut [u8],
) -> Result<LoadedKernel, Error> {
    let image =
        poole_elf::load(bytes, physical_base, VIRTUAL_BASE, destination).map_err(Error::Elf)?;
    validate_image_plan(&image)?;
    let pages = page_count(image.image_size as usize)?;
    let allocated_bytes = pages
        .checked_mul(poole_elf::PAGE_SIZE as usize)
        .ok_or(Error::PageCount)?;
    if destination.len() < allocated_bytes {
        return Err(Error::PageCount);
    }
    Ok(LoadedKernel {
        image,
        page_count: pages,
        loaded_fnv1a64: poole_elf::fnv1a64(&destination[..image.image_size as usize]),
    })
}

pub fn load_manifest_kernel(
    bytes: &[u8],
    manifest: &ManifestSummary,
    physical_base: u64,
    destination: &mut [u8],
) -> Result<LoadedKernel, Error> {
    verify_manifest_kernel(manifest, bytes)?;
    let loaded = load_kernel(bytes, physical_base, destination)?;
    if loaded.image.image_size as usize != manifest.kernel_image_bytes {
        return Err(Error::ManifestBinding);
    }
    Ok(loaded)
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;

    const CONFIG: &[u8] = b"POOLEOS-BOOTCFG/1.0\nentry_count=1\ndefault_entry=normal\ntimeout_ms=0\nboot_attempt_limit=3\nentry.normal.mode=normal\nentry.normal.slot=1\nentry.normal.manifest=\\EFI\\POOLEOS\\MANIFEST_A.PBM\nentry.normal.manifest_max_bytes=65536\nend=PBC1\n";
    const MANIFEST: &[u8] = b"POOLEOS-SYSTEM-MANIFEST/1.0\nmanifest_id=PSM-CYCLE103-SLOT1\nslot=1\nmanifest_version=1\nminimum_secure_version=1\nartifact_count=1\nartifact.kernel.type=kernel\nartifact.kernel.format=PKELF1\nartifact.kernel.version=1\nartifact.kernel.path=\\EFI\\POOLEOS\\KERNEL.ELF\nartifact.kernel.file_bytes=3\nartifact.kernel.image_bytes=4096\nartifact.kernel.sha256=BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD\nartifact.kernel.entry_contract=PKENTRY1\nend=PSM1\n";

    fn file_info(file_size: u64, physical_size: u64, attributes: u64) -> [u8; 84] {
        let mut bytes = [0u8; 84];
        bytes[0..8].copy_from_slice(&84u64.to_le_bytes());
        bytes[8..16].copy_from_slice(&file_size.to_le_bytes());
        bytes[16..24].copy_from_slice(&physical_size.to_le_bytes());
        bytes[72..80].copy_from_slice(&attributes.to_le_bytes());
        bytes[80..82].copy_from_slice(&[b'X', 0]);
        bytes
    }

    fn valid_plan() -> poole_elf::ImagePlan {
        let physical_base = 0x20_0000;
        poole_elf::ImagePlan {
            file_size: 0x7000,
            image_size: 0x8000,
            entry_offset: 0x4000,
            entry_virtual: VIRTUAL_BASE + 0x4000,
            entry_physical: physical_base + 0x4000,
            physical_base,
            virtual_base: VIRTUAL_BASE,
            relocation_count: 1,
            relro_offset: 0x6000,
            relro_size: 0x1000,
            segments: [
                poole_elf::SegmentPlan {
                    file_offset: 0,
                    virtual_offset: 0,
                    file_size: 0x4000,
                    memory_size: 0x4000,
                    permissions: poole_elf::Permissions::READ,
                },
                poole_elf::SegmentPlan {
                    file_offset: 0x4000,
                    virtual_offset: 0x4000,
                    file_size: 0x1000,
                    memory_size: 0x1000,
                    permissions: poole_elf::Permissions::READ_EXECUTE,
                },
                poole_elf::SegmentPlan {
                    file_offset: 0x5000,
                    virtual_offset: 0x5000,
                    file_size: 0x2000,
                    memory_size: 0x3000,
                    permissions: poole_elf::Permissions::READ_WRITE,
                },
            ],
            mappings: [
                poole_elf::MappingPlan {
                    virtual_offset: 0,
                    memory_size: 0x4000,
                    permissions: poole_elf::Permissions::READ,
                },
                poole_elf::MappingPlan {
                    virtual_offset: 0x4000,
                    memory_size: 0x1000,
                    permissions: poole_elf::Permissions::READ_EXECUTE,
                },
                poole_elf::MappingPlan {
                    virtual_offset: 0x6000,
                    memory_size: 0x1000,
                    permissions: poole_elf::Permissions::READ,
                },
                poole_elf::MappingPlan {
                    virtual_offset: 0x7000,
                    memory_size: 0x1000,
                    permissions: poole_elf::Permissions::READ_WRITE,
                },
            ],
        }
    }

    #[test]
    fn file_info_accepts_one_bounded_regular_file() {
        assert_eq!(
            validate_file_info(&file_info(123, 512, 0x20), 84, 1024),
            Ok(FileMetadata {
                file_size: 123,
                physical_size: 512,
                attributes: 0x20,
            })
        );
    }

    #[test]
    fn file_info_rejects_bounds_shape_directory_and_size() {
        assert_eq!(
            validate_file_info(&[0; 81], 81, 1024),
            Err(Error::FileInfoBounds)
        );
        let mut wrong_size = file_info(1, 512, 0x20);
        wrong_size[0] = 82;
        assert_eq!(
            validate_file_info(&wrong_size, 84, 1024),
            Err(Error::FileInfoShape)
        );
        assert_eq!(
            validate_file_info(&file_info(1, 512, EFI_FILE_ATTRIBUTE_DIRECTORY), 84, 1024),
            Err(Error::FileInfoAttributes)
        );
        assert_eq!(
            validate_file_info(&file_info(0, 0, 0), 84, 1024),
            Err(Error::FileSize)
        );
        assert_eq!(
            validate_file_info(&file_info(513, 512, 0), 84, 1024),
            Err(Error::FileSize)
        );
    }

    #[test]
    fn exact_read_rejects_zero_and_short_results() {
        assert_eq!(validate_exact_read(12, 12), Ok(()));
        assert_eq!(validate_exact_read(12, 11), Err(Error::ShortRead));
        assert_eq!(validate_exact_read(0, 0), Err(Error::ShortRead));
    }

    #[test]
    fn page_math_is_bounded_and_rounds_up() {
        assert_eq!(page_count(1), Ok(1));
        assert_eq!(page_count(4096), Ok(1));
        assert_eq!(page_count(4097), Ok(2));
        assert_eq!(page_count(0), Err(Error::PageCount));
        assert_eq!(
            page_count(poole_elf::MAX_IMAGE_BYTES as usize + 1),
            Err(Error::PageCount)
        );
    }

    #[test]
    fn live_config_summary_is_allocation_independent() {
        let summary = parse_config(CONFIG).unwrap();
        assert_eq!(summary.byte_count, CONFIG.len());
        assert_eq!(summary.entry_count, 1);
        assert_eq!(summary.timeout_ms, 0);
        assert_eq!(summary.boot_attempt_limit, 3);
        assert_eq!(summary.selected_slot, 1);
        assert_eq!(summary.manifest_max_bytes, 65_536);
        assert_eq!(
            summary.manifest_path.as_bytes(),
            b"\\EFI\\POOLEOS\\MANIFEST_A.PBM"
        );
    }

    #[test]
    fn manifest_summary_binds_slot_path_size_version_and_digest() {
        let summary = parse_manifest(MANIFEST, 1).unwrap();
        assert_eq!(summary.byte_count, MANIFEST.len());
        assert_eq!(summary.artifact_count, 1);
        assert_eq!(summary.slot, 1);
        assert_eq!(summary.manifest_version, 1);
        assert_eq!(summary.minimum_secure_version, 1);
        assert_eq!(summary.kernel_version, 1);
        assert_eq!(
            summary.kernel_path.as_bytes(),
            b"\\EFI\\POOLEOS\\KERNEL.ELF"
        );
        assert_eq!(summary.kernel_file_bytes, 3);
        assert_eq!(summary.kernel_image_bytes, 4096);
        assert_eq!(
            verify_manifest_kernel(&summary, b"abc"),
            Ok(summary.kernel_sha256)
        );
        assert_eq!(
            verify_manifest_kernel(&summary, b"abd"),
            Err(Error::ManifestBinding)
        );
        assert_eq!(parse_manifest(MANIFEST, 2), Err(Error::ManifestBinding));
    }

    #[test]
    fn owned_paths_encode_to_bounded_nul_terminated_uefi_units() {
        let path = OwnedPath::copy_from("\\EFI\\POOLEOS\\SYSTEM_A.PBM").unwrap();
        let units = encode_uefi_path(&path).unwrap();
        assert_eq!(units[path.len()], 0);
        assert_eq!(units[0], u16::from(b'\\'));
        assert_eq!(units[path.len() - 1], u16::from(b'M'));
        assert!(units[path.len() + 1..].iter().all(|unit| *unit == 0));
    }

    #[test]
    fn malformed_config_preserves_pbc1_error() {
        assert_eq!(
            parse_config(b"not-pbc1\n"),
            Err(Error::BootConfig(poole_boot_config::Error::Magic))
        );
    }

    #[test]
    fn mapping_plan_accepts_rx_and_rw_separation() {
        assert_eq!(validate_image_plan(&valid_plan()), Ok(()));
    }

    #[test]
    fn mapping_plan_rejects_writable_executable_memory() {
        let mut plan = valid_plan();
        plan.mappings[1].permissions.write = true;
        assert_eq!(validate_image_plan(&plan), Err(Error::MappingPlan));
    }

    #[test]
    fn mapping_plan_rejects_entry_outside_executable_memory() {
        let mut plan = valid_plan();
        plan.entry_offset = 0x5000;
        plan.entry_virtual = VIRTUAL_BASE + 0x5000;
        plan.entry_physical = plan.physical_base + 0x5000;
        assert_eq!(validate_image_plan(&plan), Err(Error::MappingPlan));
    }

    #[test]
    fn resource_stack_requires_reverse_order_and_no_leaks() {
        let mut resources = ResourceStack::new();
        resources.push(ResourceKind::RootFile).unwrap();
        resources.push(ResourceKind::ConfigFile).unwrap();
        assert_eq!(
            resources.release(ResourceKind::RootFile),
            Err(Error::ResourceOrder)
        );
        resources.release(ResourceKind::ConfigFile).unwrap();
        resources.release(ResourceKind::RootFile).unwrap();
        assert_eq!(resources.finish(), Ok(()));
    }

    #[test]
    fn resource_stack_detects_leaks_and_overflow() {
        let mut resources = ResourceStack::new();
        for _ in 0..MAX_RESOURCE_DEPTH {
            resources.push(ResourceKind::KernelPool).unwrap();
        }
        assert_eq!(
            resources.push(ResourceKind::KernelPool),
            Err(Error::ResourceOverflow)
        );
        assert_eq!(resources.finish(), Err(Error::ResourceLeak));
    }

    #[test]
    fn invalid_kernel_is_rejected_before_page_allocation() {
        assert_eq!(
            plan_kernel(b"not-an-elf"),
            Err(Error::Elf(poole_elf::Error::HeaderTruncated))
        );
    }
}
