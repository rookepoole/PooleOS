#![no_std]
#![deny(warnings)]

use core::cmp::Ordering;

use sha2::{Digest, Sha256};

pub const CONTRACT_ID: &str = "PINIT1";
pub const MAGIC: [u8; 8] = *b"PINIT1\0\0";
pub const MAJOR_VERSION: u16 = 1;
pub const MINOR_VERSION: u16 = 0;
pub const HEADER_BYTES: usize = 192;
pub const RECORD_ALIGNMENT: usize = 8;
pub const COMPONENT_BYTES: usize = 80;
pub const SERVICE_BYTES: usize = 96;
pub const DEPENDENCY_BYTES: usize = 16;
pub const RESOURCE_BYTES: usize = 48;
pub const CAPABILITY_BYTES: usize = 48;
pub const MAX_BUNDLE_BYTES: usize = 1024 * 1024 - 96;
pub const MAX_COMPONENTS: usize = 32;
pub const MAX_SERVICES: usize = 32;
pub const MAX_DEPENDENCIES: usize = 128;
pub const MAX_RESOURCES: usize = 128;
pub const MAX_CAPABILITIES: usize = 256;
pub const MAX_STRING_BYTES: usize = 8192;
pub const MAX_NAME_BYTES: usize = 63;
pub const MAX_COMPONENT_BLOB_BYTES: usize = 512 * 1024;
pub const MAX_COMPONENT_IMAGE_BYTES: u32 = 64 * 1024 * 1024;
const MAX_NAMES: usize = MAX_COMPONENTS + MAX_SERVICES + MAX_RESOURCES;

pub const FLAG_TRANSACTIONAL_START: u32 = 1 << 0;
pub const FLAG_REVERSE_ROLLBACK: u32 = 1 << 1;
pub const FLAG_DEFAULT_DENY: u32 = 1 << 2;
pub const FLAG_ROOT_DROPS_BOOTSTRAP: u32 = 1 << 3;
pub const FLAG_OUTER_SIGNATURE_REQUIRED: u32 = 1 << 4;
pub const FLAG_MANIFEST_SIGNATURE_REQUIRED: u32 = 1 << 5;
pub const FLAG_ROLLBACK_STATE_REQUIRED: u32 = 1 << 6;
pub const FLAG_COMPONENT_ABI_REQUIRED: u32 = 1 << 7;
pub const REQUIRED_FLAGS: u32 = FLAG_TRANSACTIONAL_START
    | FLAG_REVERSE_ROLLBACK
    | FLAG_DEFAULT_DENY
    | FLAG_ROOT_DROPS_BOOTSTRAP
    | FLAG_OUTER_SIGNATURE_REQUIRED
    | FLAG_MANIFEST_SIGNATURE_REQUIRED
    | FLAG_ROLLBACK_STATE_REQUIRED
    | FLAG_COMPONENT_ABI_REQUIRED;

pub const BOOT_NORMAL: u32 = 1 << 0;
pub const BOOT_SAFE: u32 = 1 << 1;
pub const BOOT_PREVIOUS: u32 = 1 << 2;
pub const BOOT_DIAGNOSTIC: u32 = 1 << 3;
pub const KNOWN_BOOT_MODES: u32 = BOOT_NORMAL | BOOT_SAFE | BOOT_PREVIOUS | BOOT_DIAGNOSTIC;

const COMPONENT_EXECUTABLE: u16 = 1;
const COMPONENT_DATA: u16 = 2;
const COMPONENT_REQUIRED: u16 = 1 << 0;
const COMPONENT_READ_ONLY: u16 = 1 << 1;
const COMPONENT_EXECUTABLE_FLAG: u16 = 1 << 2;
const PXABI1: [u8; 8] = *b"PXABI1\0\0";
const PINITD1: [u8; 8] = *b"PINITD1\0";

const SERVICE_REQUIRED: u16 = 1 << 0;
const SERVICE_CRITICAL: u16 = 1 << 1;
const SERVICE_BOOTSTRAP: u16 = 1 << 2;
const SERVICE_DROP_BOOTSTRAP: u16 = 1 << 3;
const SERVICE_ALLOW_DEGRADED: u16 = 1 << 4;
const SERVICE_STATELESS: u16 = 1 << 5;
const SERVICE_KNOWN_FLAGS: u16 = SERVICE_REQUIRED
    | SERVICE_CRITICAL
    | SERVICE_BOOTSTRAP
    | SERVICE_DROP_BOOTSTRAP
    | SERVICE_ALLOW_DEGRADED
    | SERVICE_STATELESS;
const ROOT_SERVICE_FLAGS: u16 = SERVICE_REQUIRED
    | SERVICE_CRITICAL
    | SERVICE_BOOTSTRAP
    | SERVICE_DROP_BOOTSTRAP
    | SERVICE_STATELESS;

const RESTART_NEVER: u16 = 0;
const RESTART_ON_FAILURE: u16 = 1;
const RESTART_ALWAYS: u16 = 2;
const FAILURE_ROLLBACK_BUNDLE: u16 = 1;
const FAILURE_CONTINUE_DEGRADED: u16 = 2;
const READINESS_IMMEDIATE: u16 = 0;
const READINESS_EXPLICIT: u16 = 1;
const SHUTDOWN_REVERSE_DEPENDENCY: u16 = 1;
const DEPENDENCY_STRONG: u16 = 1;
const DEPENDENCY_WEAK: u16 = 2;

const RESOURCE_MEMORY_PAGES: u16 = 1;
const RESOURCE_THREAD_SLOTS: u16 = 2;
const RESOURCE_ENDPOINT_SLOTS: u16 = 3;
const RESOURCE_ADDRESS_SPACE: u16 = 4;
const RESOURCE_LOG_SINK: u16 = 5;
const RESOURCE_REQUIRED: u32 = 1 << 0;
const RESOURCE_REVOCABLE: u32 = 1 << 1;
const RESOURCE_ZERO_ON_REVOKE: u32 = 1 << 2;
const RESOURCE_SHAREABLE: u32 = 1 << 3;
const RESOURCE_EXCLUSIVE: u32 = 1 << 4;
const RESOURCE_KNOWN_FLAGS: u32 = RESOURCE_REQUIRED
    | RESOURCE_REVOCABLE
    | RESOURCE_ZERO_ON_REVOKE
    | RESOURCE_SHAREABLE
    | RESOURCE_EXCLUSIVE;

const RIGHT_READ: u64 = 1 << 0;
const RIGHT_WRITE: u64 = 1 << 1;
const RIGHT_MAP_OR_BIND: u64 = 1 << 2;
const RIGHT_MANAGE_OR_GRANT: u64 = 1 << 3;

const CAP_REVOCABLE: u32 = 1 << 0;
const CAP_DERIVABLE: u32 = 1 << 1;
const CAP_TRANSFERABLE: u32 = 1 << 2;
const CAP_LIFECYCLE_BOUND: u32 = 1 << 3;
const CAP_KNOWN_FLAGS: u32 = CAP_REVOCABLE | CAP_DERIVABLE | CAP_TRANSFERABLE | CAP_LIFECYCLE_BOUND;
const AVAILABILITY_REQUIRED: u16 = 1;
const AVAILABILITY_OPTIONAL: u16 = 2;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Truncated,
    Oversized,
    Magic,
    Version,
    HeaderSize,
    TotalSize,
    Flags,
    VersionFloor,
    RootService,
    BootModes,
    Abi,
    Reserved,
    Count,
    TableSize,
    TableLayout,
    TableBounds,
    Padding,
    BodyDigest,
    Name,
    StringBounds,
    StringTerminator,
    StringTable,
    NameDuplicate,
    ComponentRecord,
    ComponentKind,
    ComponentImageSize,
    ComponentAlignment,
    ComponentBlobSize,
    ComponentBlobBounds,
    ComponentDigest,
    ServiceRecord,
    ServiceFlags,
    Timeout,
    RestartPolicy,
    FailurePolicy,
    Lifecycle,
    HealthPolicy,
    StateSchema,
    ServiceBudget,
    DependencyRecord,
    DependencyKind,
    DependencyCycle,
    DependencyReachability,
    DependencyAvailability,
    StartupRank,
    ResourceRecord,
    ResourceFlags,
    ResourceBounds,
    CapabilityRecord,
    CapabilityParent,
    CapabilityRights,
    CapabilityFlags,
    CapabilityLifecycle,
    CapabilityAvailability,
    CapabilitySource,
    CapabilityAttenuation,
    CapabilityRevocation,
    CapabilityRoute,
    ActivationRole,
    ActivationVersion,
    ActivationOuterPayloadDigest,
    ActivationOuterFileDigest,
    ActivationOuterSignature,
    ActivationManifestSignature,
    ActivationRollbackState,
    ActivationRollback,
    ActivationKernelAbi,
    ActivationPbp,
    ActivationBootMode,
    ActivationCapabilityAllocator,
    ActivationResourceBroker,
    ActivationComponentContracts,
    ActivationTransactionCapacity,
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::Truncated => "pinit_truncated",
            Self::Oversized => "pinit_oversized",
            Self::Magic => "pinit_magic",
            Self::Version => "pinit_version",
            Self::HeaderSize => "pinit_header_size",
            Self::TotalSize => "pinit_total_size",
            Self::Flags => "pinit_flags",
            Self::VersionFloor => "pinit_version_floor",
            Self::RootService => "pinit_root_service",
            Self::BootModes => "pinit_boot_modes",
            Self::Abi => "pinit_abi",
            Self::Reserved => "pinit_reserved",
            Self::Count => "pinit_count",
            Self::TableSize => "pinit_table_size",
            Self::TableLayout => "pinit_table_layout",
            Self::TableBounds => "pinit_table_bounds",
            Self::Padding => "pinit_padding",
            Self::BodyDigest => "pinit_body_digest",
            Self::Name => "pinit_name",
            Self::StringBounds => "pinit_string_bounds",
            Self::StringTerminator => "pinit_string_terminator",
            Self::StringTable => "pinit_string_table",
            Self::NameDuplicate => "pinit_name_duplicate",
            Self::ComponentRecord => "pinit_component_record",
            Self::ComponentKind => "pinit_component_kind",
            Self::ComponentImageSize => "pinit_component_image_size",
            Self::ComponentAlignment => "pinit_component_alignment",
            Self::ComponentBlobSize => "pinit_component_blob_size",
            Self::ComponentBlobBounds => "pinit_component_blob_bounds",
            Self::ComponentDigest => "pinit_component_digest",
            Self::ServiceRecord => "pinit_service_record",
            Self::ServiceFlags => "pinit_service_flags",
            Self::Timeout => "pinit_timeout",
            Self::RestartPolicy => "pinit_restart_policy",
            Self::FailurePolicy => "pinit_failure_policy",
            Self::Lifecycle => "pinit_lifecycle",
            Self::HealthPolicy => "pinit_health_policy",
            Self::StateSchema => "pinit_state_schema",
            Self::ServiceBudget => "pinit_service_budget",
            Self::DependencyRecord => "pinit_dependency_record",
            Self::DependencyKind => "pinit_dependency_kind",
            Self::DependencyCycle => "pinit_dependency_cycle",
            Self::DependencyReachability => "pinit_dependency_reachability",
            Self::DependencyAvailability => "pinit_dependency_availability",
            Self::StartupRank => "pinit_startup_rank",
            Self::ResourceRecord => "pinit_resource_record",
            Self::ResourceFlags => "pinit_resource_flags",
            Self::ResourceBounds => "pinit_resource_bounds",
            Self::CapabilityRecord => "pinit_capability_record",
            Self::CapabilityParent => "pinit_capability_parent",
            Self::CapabilityRights => "pinit_capability_rights",
            Self::CapabilityFlags => "pinit_capability_flags",
            Self::CapabilityLifecycle => "pinit_capability_lifecycle",
            Self::CapabilityAvailability => "pinit_capability_availability",
            Self::CapabilitySource => "pinit_capability_source",
            Self::CapabilityAttenuation => "pinit_capability_attenuation",
            Self::CapabilityRevocation => "pinit_capability_revocation",
            Self::CapabilityRoute => "pinit_capability_route",
            Self::ActivationRole => "pinit_activation_role",
            Self::ActivationVersion => "pinit_activation_version",
            Self::ActivationOuterPayloadDigest => "pinit_activation_outer_payload_digest_verified",
            Self::ActivationOuterFileDigest => "pinit_activation_outer_file_digest_verified",
            Self::ActivationOuterSignature => "pinit_activation_outer_signature_verified",
            Self::ActivationManifestSignature => "pinit_activation_manifest_signature_verified",
            Self::ActivationRollbackState => "pinit_activation_rollback_state_authenticated",
            Self::ActivationRollback => "pinit_activation_rollback",
            Self::ActivationKernelAbi => "pinit_activation_kernel_abi",
            Self::ActivationPbp => "pinit_activation_pbp",
            Self::ActivationBootMode => "pinit_activation_boot_mode",
            Self::ActivationCapabilityAllocator => "pinit_activation_capability_allocator_ready",
            Self::ActivationResourceBroker => "pinit_activation_resource_broker_ready",
            Self::ActivationComponentContracts => "pinit_activation_component_contracts_verified",
            Self::ActivationTransactionCapacity => "pinit_activation_transaction_capacity_verified",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Bundle<'a> {
    pub bundle_version: u64,
    pub minimum_secure_version: u64,
    pub root_service_id: u32,
    pub allowed_boot_modes: u32,
    pub required_kernel_abi_major: u16,
    pub minimum_kernel_abi_minor: u16,
    pub required_pbp_major: u16,
    pub minimum_pbp_minor: u16,
    pub start_timeout_ms: u32,
    pub rollback_timeout_ms: u32,
    pub max_total_restarts: u32,
    pub component_count: u16,
    pub service_count: u16,
    pub dependency_count: u16,
    pub resource_count: u16,
    pub capability_count: u16,
    pub start_order: [u32; MAX_SERVICES],
    pub body_sha256: [u8; 32],
    pub raw: &'a [u8],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ActivationContext {
    pub outer_role: u32,
    pub outer_artifact_version: u64,
    pub outer_payload_digest_verified: bool,
    pub outer_file_digest_verified: bool,
    pub outer_signature_verified: bool,
    pub manifest_signature_verified: bool,
    pub rollback_state_authenticated: bool,
    pub trusted_minimum_secure_version: u64,
    pub kernel_abi_major: u16,
    pub kernel_abi_minor: u16,
    pub pbp_major: u16,
    pub pbp_minor: u16,
    pub boot_mode: u32,
    pub capability_allocator_ready: bool,
    pub resource_broker_ready: bool,
    pub component_contracts_verified: bool,
    pub transaction_capacity_verified: bool,
}

impl ActivationContext {
    pub const fn development() -> Self {
        Self {
            outer_role: 2,
            outer_artifact_version: 1,
            outer_payload_digest_verified: true,
            outer_file_digest_verified: true,
            outer_signature_verified: false,
            manifest_signature_verified: false,
            rollback_state_authenticated: false,
            trusted_minimum_secure_version: 0,
            kernel_abi_major: 1,
            kernel_abi_minor: 0,
            pbp_major: 1,
            pbp_minor: 0,
            boot_mode: BOOT_NORMAL,
            capability_allocator_ready: false,
            resource_broker_ready: false,
            component_contracts_verified: false,
            transaction_capacity_verified: false,
        }
    }

    pub const fn synthetic_qualified() -> Self {
        Self {
            outer_role: 2,
            outer_artifact_version: 1,
            outer_payload_digest_verified: true,
            outer_file_digest_verified: true,
            outer_signature_verified: true,
            manifest_signature_verified: true,
            rollback_state_authenticated: true,
            trusted_minimum_secure_version: 1,
            kernel_abi_major: 1,
            kernel_abi_minor: 0,
            pbp_major: 1,
            pbp_minor: 0,
            boot_mode: BOOT_NORMAL,
            capability_allocator_ready: true,
            resource_broker_ready: true,
            component_contracts_verified: true,
            transaction_capacity_verified: true,
        }
    }
}

#[derive(Clone, Copy)]
struct Header {
    bundle_version: u64,
    minimum_secure_version: u64,
    root_service_id: u32,
    allowed_boot_modes: u32,
    kernel_major: u16,
    kernel_minor: u16,
    pbp_major: u16,
    pbp_minor: u16,
    component_count: usize,
    service_count: usize,
    dependency_count: usize,
    resource_count: usize,
    capability_count: usize,
    component_offset: usize,
    service_offset: usize,
    dependency_offset: usize,
    resource_offset: usize,
    capability_offset: usize,
    string_offset: usize,
    string_bytes: usize,
    blob_offset: usize,
    blob_bytes: usize,
    start_timeout_ms: u32,
    rollback_timeout_ms: u32,
    max_total_restarts: u32,
    body_sha256: [u8; 32],
}

#[derive(Clone, Copy)]
struct NameRef {
    offset: usize,
    bytes: usize,
}

const EMPTY_NAME: NameRef = NameRef {
    offset: 0,
    bytes: 0,
};

#[derive(Clone, Copy)]
struct ServiceMeta {
    flags: u16,
    restart_policy: u16,
    ready_resource_id: u32,
    capability_count: u16,
    resource_count: u16,
    dependency_count: u16,
    startup_rank: u16,
    max_restarts: u32,
}

const EMPTY_SERVICE: ServiceMeta = ServiceMeta {
    flags: 0,
    restart_policy: 0,
    ready_resource_id: 0,
    capability_count: 0,
    resource_count: 0,
    dependency_count: 0,
    startup_rank: 0,
    max_restarts: 0,
};

#[derive(Clone, Copy)]
struct DependencyMeta {
    dependent: u32,
    prerequisite: u32,
    kind: u16,
}

const EMPTY_DEPENDENCY: DependencyMeta = DependencyMeta {
    dependent: 0,
    prerequisite: 0,
    kind: 0,
};

#[derive(Clone, Copy)]
struct ResourceMeta {
    provider: u32,
    kind: u16,
}

const EMPTY_RESOURCE: ResourceMeta = ResourceMeta {
    provider: 0,
    kind: 0,
};

#[derive(Clone, Copy)]
struct CapabilityMeta {
    holder: u32,
    resource: u32,
    rights: u64,
    flags: u32,
    revoke_group: u32,
    availability: u16,
}

const EMPTY_CAPABILITY: CapabilityMeta = CapabilityMeta {
    holder: 0,
    resource: 0,
    rights: 0,
    flags: 0,
    revoke_group: 0,
    availability: 0,
};

fn read_u16(bytes: &[u8], offset: usize) -> Result<u16, Error> {
    let value = bytes.get(offset..offset + 2).ok_or(Error::Truncated)?;
    Ok(u16::from_le_bytes([value[0], value[1]]))
}

fn read_u32(bytes: &[u8], offset: usize) -> Result<u32, Error> {
    let value = bytes.get(offset..offset + 4).ok_or(Error::Truncated)?;
    Ok(u32::from_le_bytes([value[0], value[1], value[2], value[3]]))
}

fn read_u64(bytes: &[u8], offset: usize) -> Result<u64, Error> {
    let value = bytes.get(offset..offset + 8).ok_or(Error::Truncated)?;
    Ok(u64::from_le_bytes([
        value[0], value[1], value[2], value[3], value[4], value[5], value[6], value[7],
    ]))
}

fn sha256(bytes: &[u8]) -> [u8; 32] {
    let value = Sha256::digest(bytes);
    let mut output = [0u8; 32];
    output.copy_from_slice(&value);
    output
}

fn align(value: usize) -> Result<usize, Error> {
    value
        .checked_add(RECORD_ALIGNMENT - 1)
        .map(|item| item & !(RECORD_ALIGNMENT - 1))
        .ok_or(Error::TableLayout)
}

fn table(data: &[u8], offset: usize, count: usize, size: usize) -> Result<&[u8], Error> {
    let bytes = count.checked_mul(size).ok_or(Error::TableBounds)?;
    let end = offset.checked_add(bytes).ok_or(Error::TableBounds)?;
    if offset < HEADER_BYTES {
        return Err(Error::TableBounds);
    }
    data.get(offset..end).ok_or(Error::TableBounds)
}

fn all_zero(bytes: &[u8]) -> bool {
    bytes.iter().all(|byte| *byte == 0)
}

fn parse_header(data: &[u8]) -> Result<Header, Error> {
    if data.len() < HEADER_BYTES {
        return Err(Error::Truncated);
    }
    if data.len() > MAX_BUNDLE_BYTES {
        return Err(Error::Oversized);
    }
    if data[..8] != MAGIC {
        return Err(Error::Magic);
    }
    if read_u16(data, 8)? != MAJOR_VERSION || read_u16(data, 10)? != MINOR_VERSION {
        return Err(Error::Version);
    }
    if usize::from(read_u16(data, 12)?) != HEADER_BYTES
        || usize::from(read_u16(data, 14)?) != RECORD_ALIGNMENT
    {
        return Err(Error::HeaderSize);
    }
    if usize::try_from(read_u32(data, 16)?).map_err(|_| Error::TotalSize)? != data.len() {
        return Err(Error::TotalSize);
    }
    if read_u32(data, 20)? != REQUIRED_FLAGS {
        return Err(Error::Flags);
    }
    let bundle_version = read_u64(data, 24)?;
    let minimum_secure_version = read_u64(data, 32)?;
    if bundle_version == 0 || minimum_secure_version == 0 || bundle_version < minimum_secure_version
    {
        return Err(Error::VersionFloor);
    }
    let root_service_id = read_u32(data, 40)?;
    if root_service_id == 0 {
        return Err(Error::RootService);
    }
    let allowed_boot_modes = read_u32(data, 44)?;
    if allowed_boot_modes == 0 || allowed_boot_modes & !KNOWN_BOOT_MODES != 0 {
        return Err(Error::BootModes);
    }
    let kernel_major = read_u16(data, 48)?;
    let kernel_minor = read_u16(data, 50)?;
    let pbp_major = read_u16(data, 52)?;
    let pbp_minor = read_u16(data, 54)?;
    if kernel_major == 0 || pbp_major == 0 {
        return Err(Error::Abi);
    }
    let component_count = usize::from(read_u16(data, 56)?);
    let service_count = usize::from(read_u16(data, 58)?);
    let dependency_count = usize::from(read_u16(data, 60)?);
    let resource_count = usize::from(read_u16(data, 62)?);
    let capability_count = usize::from(read_u16(data, 64)?);
    if read_u16(data, 66)? != 0 {
        return Err(Error::Reserved);
    }
    if !(1..=MAX_COMPONENTS).contains(&component_count)
        || !(1..=MAX_SERVICES).contains(&service_count)
        || dependency_count > MAX_DEPENDENCIES
        || !(1..=MAX_RESOURCES).contains(&resource_count)
        || !(1..=MAX_CAPABILITIES).contains(&capability_count)
    {
        return Err(Error::Count);
    }
    let component_offset = usize::try_from(read_u32(data, 68)?).map_err(|_| Error::TableLayout)?;
    let service_offset = usize::try_from(read_u32(data, 72)?).map_err(|_| Error::TableLayout)?;
    let dependency_offset = usize::try_from(read_u32(data, 76)?).map_err(|_| Error::TableLayout)?;
    let resource_offset = usize::try_from(read_u32(data, 80)?).map_err(|_| Error::TableLayout)?;
    let capability_offset = usize::try_from(read_u32(data, 84)?).map_err(|_| Error::TableLayout)?;
    let string_offset = usize::try_from(read_u32(data, 88)?).map_err(|_| Error::TableLayout)?;
    let string_bytes = usize::try_from(read_u32(data, 92)?).map_err(|_| Error::TableSize)?;
    let blob_offset = usize::try_from(read_u32(data, 96)?).map_err(|_| Error::TableLayout)?;
    let blob_bytes = usize::try_from(read_u32(data, 100)?).map_err(|_| Error::ComponentBlobSize)?;
    if string_bytes == 0 || string_bytes > MAX_STRING_BYTES || blob_bytes == 0 {
        return Err(Error::TableSize);
    }
    if blob_bytes > MAX_COMPONENT_BLOB_BYTES {
        return Err(Error::ComponentBlobSize);
    }
    let start_timeout_ms = read_u32(data, 104)?;
    let rollback_timeout_ms = read_u32(data, 108)?;
    let max_total_restarts = read_u32(data, 112)?;
    if !(1..=300_000).contains(&start_timeout_ms) || !(1..=300_000).contains(&rollback_timeout_ms) {
        return Err(Error::Timeout);
    }
    if max_total_restarts > 1024 {
        return Err(Error::Lifecycle);
    }
    if read_u32(data, 116)? != 0 || !all_zero(&data[152..HEADER_BYTES]) {
        return Err(Error::Reserved);
    }
    let expected_component = HEADER_BYTES;
    let expected_service = expected_component
        .checked_add(
            component_count
                .checked_mul(COMPONENT_BYTES)
                .ok_or(Error::TableLayout)?,
        )
        .ok_or(Error::TableLayout)?;
    let expected_dependency = expected_service
        .checked_add(
            service_count
                .checked_mul(SERVICE_BYTES)
                .ok_or(Error::TableLayout)?,
        )
        .ok_or(Error::TableLayout)?;
    let expected_resource = expected_dependency
        .checked_add(
            dependency_count
                .checked_mul(DEPENDENCY_BYTES)
                .ok_or(Error::TableLayout)?,
        )
        .ok_or(Error::TableLayout)?;
    let expected_capability = expected_resource
        .checked_add(
            resource_count
                .checked_mul(RESOURCE_BYTES)
                .ok_or(Error::TableLayout)?,
        )
        .ok_or(Error::TableLayout)?;
    let expected_string = expected_capability
        .checked_add(
            capability_count
                .checked_mul(CAPABILITY_BYTES)
                .ok_or(Error::TableLayout)?,
        )
        .ok_or(Error::TableLayout)?;
    let expected_blob = align(
        expected_string
            .checked_add(string_bytes)
            .ok_or(Error::TableLayout)?,
    )?;
    if [
        component_offset,
        service_offset,
        dependency_offset,
        resource_offset,
        capability_offset,
        string_offset,
    ] != [
        expected_component,
        expected_service,
        expected_dependency,
        expected_resource,
        expected_capability,
        expected_string,
    ] || blob_offset != expected_blob
        || blob_offset
            .checked_add(blob_bytes)
            .ok_or(Error::TableLayout)?
            != data.len()
    {
        return Err(Error::TableLayout);
    }
    if !all_zero(
        data.get(string_offset + string_bytes..blob_offset)
            .ok_or(Error::TableBounds)?,
    ) {
        return Err(Error::Padding);
    }
    let mut body_sha256 = [0u8; 32];
    body_sha256.copy_from_slice(&data[120..152]);
    if sha256(&data[HEADER_BYTES..]) != body_sha256 {
        return Err(Error::BodyDigest);
    }
    Ok(Header {
        bundle_version,
        minimum_secure_version,
        root_service_id,
        allowed_boot_modes,
        kernel_major,
        kernel_minor,
        pbp_major,
        pbp_minor,
        component_count,
        service_count,
        dependency_count,
        resource_count,
        capability_count,
        component_offset,
        service_offset,
        dependency_offset,
        resource_offset,
        capability_offset,
        string_offset,
        string_bytes,
        blob_offset,
        blob_bytes,
        start_timeout_ms,
        rollback_timeout_ms,
        max_total_restarts,
        body_sha256,
    })
}

fn valid_name(bytes: &[u8]) -> bool {
    if bytes.is_empty() || bytes.len() > MAX_NAME_BYTES || !bytes[0].is_ascii_lowercase() {
        return false;
    }
    let last = bytes[bytes.len() - 1];
    if !(last.is_ascii_lowercase() || last.is_ascii_digit()) {
        return false;
    }
    if bytes.iter().any(|byte| {
        !(byte.is_ascii_lowercase() || byte.is_ascii_digit() || matches!(*byte, b'.' | b'_' | b'-'))
    }) {
        return false;
    }
    !bytes.windows(2).any(|pair| pair == b"..")
}

fn name_ref(table: &[u8], offset: u32, bytes: u16) -> Result<NameRef, Error> {
    let offset = usize::try_from(offset).map_err(|_| Error::StringBounds)?;
    let bytes = usize::from(bytes);
    let end = offset.checked_add(bytes).ok_or(Error::StringBounds)?;
    if bytes == 0 || bytes > MAX_NAME_BYTES || end >= table.len() {
        return Err(Error::StringBounds);
    }
    if table[end] != 0 {
        return Err(Error::StringTerminator);
    }
    if !valid_name(&table[offset..end]) {
        return Err(Error::Name);
    }
    Ok(NameRef { offset, bytes })
}

fn push_name(
    names: &mut [NameRef; MAX_NAMES],
    count: &mut usize,
    value: NameRef,
    table: &[u8],
) -> Result<(), Error> {
    for existing in &names[..*count] {
        if table[existing.offset..existing.offset + existing.bytes]
            == table[value.offset..value.offset + value.bytes]
        {
            return Err(Error::NameDuplicate);
        }
    }
    names[*count] = value;
    *count += 1;
    Ok(())
}

fn compare_names(left: NameRef, right: NameRef, table: &[u8]) -> Ordering {
    table[left.offset..left.offset + left.bytes]
        .cmp(&table[right.offset..right.offset + right.bytes])
}

fn validate_string_table(
    names: &mut [NameRef; MAX_NAMES],
    count: usize,
    table: &[u8],
) -> Result<(), Error> {
    for index in 0..count {
        let mut smallest = index;
        for candidate in index + 1..count {
            if compare_names(names[candidate], names[smallest], table) == Ordering::Less {
                smallest = candidate;
            }
        }
        names.swap(index, smallest);
    }
    let mut cursor = 0usize;
    for value in &names[..count] {
        if value.offset != cursor {
            return Err(Error::StringTable);
        }
        cursor = cursor
            .checked_add(value.bytes + 1)
            .ok_or(Error::StringTable)?;
    }
    if cursor != table.len() {
        return Err(Error::StringTable);
    }
    Ok(())
}

fn resource_limit(kind: u16) -> Option<u64> {
    match kind {
        RESOURCE_MEMORY_PAGES => Some(65536),
        RESOURCE_THREAD_SLOTS => Some(1024),
        RESOURCE_ENDPOINT_SLOTS => Some(4096),
        RESOURCE_ADDRESS_SPACE | RESOURCE_LOG_SINK => Some(1),
        _ => None,
    }
}

fn resource_rights(kind: u16) -> u64 {
    match kind {
        RESOURCE_MEMORY_PAGES | RESOURCE_THREAD_SLOTS | RESOURCE_ENDPOINT_SLOTS => {
            RIGHT_READ | RIGHT_WRITE | RIGHT_MAP_OR_BIND | RIGHT_MANAGE_OR_GRANT
        }
        RESOURCE_ADDRESS_SPACE => RIGHT_READ | RIGHT_WRITE | RIGHT_MAP_OR_BIND,
        RESOURCE_LOG_SINK => RIGHT_WRITE,
        _ => 0,
    }
}

fn has_dependency(
    dependencies: &[DependencyMeta; MAX_DEPENDENCIES],
    count: usize,
    dependent: u32,
    prerequisite: u32,
) -> bool {
    dependencies[..count]
        .iter()
        .any(|item| item.dependent == dependent && item.prerequisite == prerequisite)
}

pub fn parse(data: &[u8]) -> Result<Bundle<'_>, Error> {
    let header = parse_header(data)?;
    let string_table = data
        .get(header.string_offset..header.string_offset + header.string_bytes)
        .ok_or(Error::TableBounds)?;
    let blob = data
        .get(header.blob_offset..header.blob_offset + header.blob_bytes)
        .ok_or(Error::TableBounds)?;
    let mut names = [EMPTY_NAME; MAX_NAMES];
    let mut name_count = 0usize;

    let component_table = table(
        data,
        header.component_offset,
        header.component_count,
        COMPONENT_BYTES,
    )?;
    let mut component_kinds = [0u16; MAX_COMPONENTS];
    let mut blob_cursor = 0usize;
    for index in 0..header.component_count {
        let record = &component_table[index * COMPONENT_BYTES..(index + 1) * COMPONENT_BYTES];
        if read_u32(record, 0)? != u32::try_from(index + 1).map_err(|_| Error::ComponentRecord)?
            || read_u16(record, 14)? != 0
            || !all_zero(&record[72..])
        {
            return Err(Error::ComponentRecord);
        }
        let kind = read_u16(record, 4)?;
        let flags = read_u16(record, 6)?;
        let format_id = &record[16..24];
        let image_bytes = read_u32(record, 32)?;
        match kind {
            COMPONENT_EXECUTABLE => {
                if flags != COMPONENT_REQUIRED | COMPONENT_READ_ONLY | COMPONENT_EXECUTABLE_FLAG
                    || format_id != PXABI1
                {
                    return Err(Error::ComponentKind);
                }
                if image_bytes == 0 || image_bytes > MAX_COMPONENT_IMAGE_BYTES {
                    return Err(Error::ComponentImageSize);
                }
            }
            COMPONENT_DATA => {
                if flags != COMPONENT_REQUIRED | COMPONENT_READ_ONLY
                    || format_id != PINITD1
                    || image_bytes != 0
                {
                    return Err(Error::ComponentKind);
                }
            }
            _ => return Err(Error::ComponentKind),
        }
        component_kinds[index] = kind;
        let destination_alignment = read_u32(record, 36)?;
        if destination_alignment == 0
            || destination_alignment > 4096
            || !destination_alignment.is_power_of_two()
        {
            return Err(Error::ComponentAlignment);
        }
        let expected = align(blob_cursor)?;
        if !all_zero(
            blob.get(blob_cursor..expected)
                .ok_or(Error::ComponentBlobBounds)?,
        ) {
            return Err(Error::Padding);
        }
        let relative_offset =
            usize::try_from(read_u32(record, 24)?).map_err(|_| Error::ComponentBlobBounds)?;
        let blob_bytes =
            usize::try_from(read_u32(record, 28)?).map_err(|_| Error::ComponentBlobBounds)?;
        if relative_offset != expected || blob_bytes == 0 {
            return Err(Error::ComponentBlobBounds);
        }
        let end = relative_offset
            .checked_add(blob_bytes)
            .ok_or(Error::ComponentBlobBounds)?;
        let component_blob = blob
            .get(relative_offset..end)
            .ok_or(Error::ComponentBlobBounds)?;
        if sha256(component_blob) != record[40..72] {
            return Err(Error::ComponentDigest);
        }
        blob_cursor = end;
        let name = name_ref(string_table, read_u32(record, 8)?, read_u16(record, 12)?)?;
        push_name(&mut names, &mut name_count, name, string_table)?;
    }
    if blob_cursor != blob.len() {
        return Err(Error::ComponentBlobBounds);
    }

    let mut services = [EMPTY_SERVICE; MAX_SERVICES];
    let service_table = table(
        data,
        header.service_offset,
        header.service_count,
        SERVICE_BYTES,
    )?;
    for index in 0..header.service_count {
        let record = &service_table[index * SERVICE_BYTES..(index + 1) * SERVICE_BYTES];
        let service_id = read_u32(record, 0)?;
        let component_id = read_u32(record, 4)?;
        if service_id != u32::try_from(index + 1).map_err(|_| Error::ServiceRecord)?
            || component_id == 0
            || usize::try_from(component_id).map_err(|_| Error::ServiceRecord)?
                > header.component_count
            || component_kinds
                [usize::try_from(component_id - 1).map_err(|_| Error::ServiceRecord)?]
                != COMPONENT_EXECUTABLE
            || !all_zero(&record[68..])
        {
            return Err(Error::ServiceRecord);
        }
        let flags = read_u16(record, 14)?;
        if flags & !SERVICE_KNOWN_FLAGS != 0
            || flags & SERVICE_CRITICAL != 0 && flags & SERVICE_REQUIRED == 0
            || flags & SERVICE_REQUIRED != 0 && flags & SERVICE_ALLOW_DEGRADED != 0
        {
            return Err(Error::ServiceFlags);
        }
        let startup_timeout = read_u32(record, 16)?;
        let stop_timeout = read_u32(record, 20)?;
        if startup_timeout == 0
            || startup_timeout > header.start_timeout_ms
            || stop_timeout == 0
            || stop_timeout > header.rollback_timeout_ms
        {
            return Err(Error::Timeout);
        }
        let restart_policy = read_u16(record, 24)?;
        let failure_policy = read_u16(record, 26)?;
        let readiness_policy = read_u16(record, 28)?;
        if !matches!(
            restart_policy,
            RESTART_NEVER | RESTART_ON_FAILURE | RESTART_ALWAYS
        ) {
            return Err(Error::RestartPolicy);
        }
        if !matches!(
            failure_policy,
            FAILURE_ROLLBACK_BUNDLE | FAILURE_CONTINUE_DEGRADED
        ) {
            return Err(Error::FailurePolicy);
        }
        if !matches!(readiness_policy, READINESS_IMMEDIATE | READINESS_EXPLICIT)
            || read_u16(record, 30)? != SHUTDOWN_REVERSE_DEPENDENCY
        {
            return Err(Error::Lifecycle);
        }
        if flags & SERVICE_REQUIRED != 0 && failure_policy != FAILURE_ROLLBACK_BUNDLE
            || flags & SERVICE_REQUIRED == 0 && failure_policy != FAILURE_CONTINUE_DEGRADED
        {
            return Err(Error::FailurePolicy);
        }
        let max_restarts = read_u32(record, 32)?;
        let restart_window = read_u32(record, 36)?;
        let backoff_initial = read_u32(record, 40)?;
        let backoff_max = read_u32(record, 44)?;
        if restart_policy == RESTART_NEVER {
            if max_restarts != 0 || restart_window != 0 || backoff_initial != 0 || backoff_max != 0
            {
                return Err(Error::RestartPolicy);
            }
        } else if !(1..=64).contains(&max_restarts)
            || backoff_initial == 0
            || backoff_initial > backoff_max
            || backoff_max > restart_window
            || restart_window > 3_600_000
        {
            return Err(Error::RestartPolicy);
        }
        let health_timeout = read_u32(record, 48)?;
        let ready_resource_id = read_u32(record, 52)?;
        if health_timeout == 0
            || health_timeout > startup_timeout
            || readiness_policy == READINESS_EXPLICIT && ready_resource_id == 0
        {
            return Err(Error::HealthPolicy);
        }
        let state_schema_version = read_u32(record, 64)?;
        if (flags & SERVICE_STATELESS != 0) != (state_schema_version == 0) {
            return Err(Error::StateSchema);
        }
        services[index] = ServiceMeta {
            flags,
            restart_policy,
            ready_resource_id,
            capability_count: read_u16(record, 56)?,
            resource_count: read_u16(record, 58)?,
            dependency_count: read_u16(record, 60)?,
            startup_rank: read_u16(record, 62)?,
            max_restarts,
        };
        let name = name_ref(string_table, read_u32(record, 8)?, read_u16(record, 12)?)?;
        push_name(&mut names, &mut name_count, name, string_table)?;
    }

    let mut dependencies = [EMPTY_DEPENDENCY; MAX_DEPENDENCIES];
    let dependency_table = table(
        data,
        header.dependency_offset,
        header.dependency_count,
        DEPENDENCY_BYTES,
    )?;
    let mut previous_pair = (0u32, 0u32);
    for index in 0..header.dependency_count {
        let record = &dependency_table[index * DEPENDENCY_BYTES..(index + 1) * DEPENDENCY_BYTES];
        let dependent = read_u32(record, 0)?;
        let prerequisite = read_u32(record, 4)?;
        let pair = (dependent, prerequisite);
        if pair <= previous_pair
            || dependent == prerequisite
            || dependent == 0
            || prerequisite == 0
            || usize::try_from(dependent).map_err(|_| Error::DependencyRecord)?
                > header.service_count
            || usize::try_from(prerequisite).map_err(|_| Error::DependencyRecord)?
                > header.service_count
        {
            return Err(Error::DependencyRecord);
        }
        let kind = read_u16(record, 8)?;
        if !matches!(kind, DEPENDENCY_STRONG | DEPENDENCY_WEAK)
            || read_u16(record, 10)? != 0
            || read_u32(record, 12)? != 0
        {
            return Err(Error::DependencyKind);
        }
        dependencies[index] = DependencyMeta {
            dependent,
            prerequisite,
            kind,
        };
        previous_pair = pair;
    }

    let mut resources = [EMPTY_RESOURCE; MAX_RESOURCES];
    let resource_table = table(
        data,
        header.resource_offset,
        header.resource_count,
        RESOURCE_BYTES,
    )?;
    for index in 0..header.resource_count {
        let record = &resource_table[index * RESOURCE_BYTES..(index + 1) * RESOURCE_BYTES];
        let resource_id = read_u32(record, 0)?;
        let provider = read_u32(record, 4)?;
        let kind = read_u16(record, 14)?;
        if resource_id != u32::try_from(index + 1).map_err(|_| Error::ResourceRecord)?
            || usize::try_from(provider).map_err(|_| Error::ResourceRecord)? > header.service_count
            || read_u32(record, 20)? != 0
            || read_u32(record, 44)? != 0
        {
            return Err(Error::ResourceRecord);
        }
        let limit = resource_limit(kind).ok_or(Error::ResourceRecord)?;
        let flags = read_u32(record, 16)?;
        if flags & !RESOURCE_KNOWN_FLAGS != 0
            || flags & RESOURCE_REVOCABLE == 0
            || (flags & RESOURCE_SHAREABLE != 0) == (flags & RESOURCE_EXCLUSIVE != 0)
            || kind != RESOURCE_MEMORY_PAGES && flags & RESOURCE_ZERO_ON_REVOKE != 0
        {
            return Err(Error::ResourceFlags);
        }
        let minimum = read_u64(record, 24)?;
        let maximum = read_u64(record, 32)?;
        if minimum == 0
            || minimum > maximum
            || maximum > limit
            || read_u32(record, 40)? == 0
            || matches!(kind, RESOURCE_ADDRESS_SPACE | RESOURCE_LOG_SINK)
                && (minimum != 1 || maximum != 1)
        {
            return Err(Error::ResourceBounds);
        }
        resources[index] = ResourceMeta { provider, kind };
        let name = name_ref(string_table, read_u32(record, 8)?, read_u16(record, 12)?)?;
        push_name(&mut names, &mut name_count, name, string_table)?;
    }

    let mut capabilities = [EMPTY_CAPABILITY; MAX_CAPABILITIES];
    let capability_table = table(
        data,
        header.capability_offset,
        header.capability_count,
        CAPABILITY_BYTES,
    )?;
    for index in 0..header.capability_count {
        let record = &capability_table[index * CAPABILITY_BYTES..(index + 1) * CAPABILITY_BYTES];
        let capability_id = read_u32(record, 0)?;
        let parent = read_u32(record, 4)?;
        let holder = read_u32(record, 8)?;
        let resource = read_u32(record, 12)?;
        if capability_id != u32::try_from(index + 1).map_err(|_| Error::CapabilityRecord)?
            || holder == 0
            || usize::try_from(holder).map_err(|_| Error::CapabilityRecord)? > header.service_count
            || resource == 0
            || usize::try_from(resource).map_err(|_| Error::CapabilityRecord)?
                > header.resource_count
            || !all_zero(&record[40..])
        {
            return Err(Error::CapabilityRecord);
        }
        if parent >= capability_id {
            return Err(Error::CapabilityParent);
        }
        let resource_meta =
            resources[usize::try_from(resource - 1).map_err(|_| Error::CapabilityRecord)?];
        let rights = read_u64(record, 16)?;
        if rights == 0 || rights & !resource_rights(resource_meta.kind) != 0 {
            return Err(Error::CapabilityRights);
        }
        let flags = read_u32(record, 24)?;
        if flags & !CAP_KNOWN_FLAGS != 0
            || flags & (CAP_REVOCABLE | CAP_LIFECYCLE_BOUND) != CAP_REVOCABLE | CAP_LIFECYCLE_BOUND
        {
            return Err(Error::CapabilityFlags);
        }
        let revoke_group = read_u32(record, 28)?;
        let availability = read_u16(record, 38)?;
        if revoke_group == 0
            || read_u32(record, 32)? != 0
            || usize::from(read_u16(record, 36)?) > MAX_CAPABILITIES
        {
            return Err(Error::CapabilityLifecycle);
        }
        if !matches!(availability, AVAILABILITY_REQUIRED | AVAILABILITY_OPTIONAL) {
            return Err(Error::CapabilityAvailability);
        }
        if parent == 0 {
            if resource_meta.provider == 0 && holder != header.root_service_id
                || resource_meta.provider != 0
                    && holder != header.root_service_id
                    && holder != resource_meta.provider
            {
                return Err(Error::CapabilitySource);
            }
        } else {
            let parent_meta =
                capabilities[usize::try_from(parent - 1).map_err(|_| Error::CapabilityParent)?];
            if parent_meta.flags & CAP_DERIVABLE == 0
                || parent_meta.resource != resource
                || rights & !parent_meta.rights != 0
            {
                return Err(Error::CapabilityAttenuation);
            }
            if revoke_group != parent_meta.revoke_group {
                return Err(Error::CapabilityRevocation);
            }
            if availability == AVAILABILITY_REQUIRED
                && parent_meta.availability != AVAILABILITY_REQUIRED
            {
                return Err(Error::CapabilityAvailability);
            }
        }
        capabilities[index] = CapabilityMeta {
            holder,
            resource,
            rights,
            flags,
            revoke_group,
            availability,
        };
    }

    validate_string_table(&mut names, name_count, string_table)?;
    let root_index = usize::try_from(header.root_service_id - 1).map_err(|_| Error::RootService)?;
    if root_index >= header.service_count
        || services[root_index].flags != ROOT_SERVICE_FLAGS
        || services[root_index].restart_policy != RESTART_NEVER
    {
        return Err(Error::RootService);
    }
    for (index, service) in services[..header.service_count].iter().enumerate() {
        if index != root_index && service.flags & (SERVICE_BOOTSTRAP | SERVICE_DROP_BOOTSTRAP) != 0
        {
            return Err(Error::RootService);
        }
    }
    if dependencies[..header.dependency_count]
        .iter()
        .any(|item| item.dependent == header.root_service_id)
    {
        return Err(Error::RootService);
    }

    let mut indegree = [0u16; MAX_SERVICES];
    for item in &dependencies[..header.dependency_count] {
        let dependent = usize::try_from(item.dependent - 1).map_err(|_| Error::DependencyRecord)?;
        indegree[dependent] = indegree[dependent]
            .checked_add(1)
            .ok_or(Error::DependencyRecord)?;
        if item.kind == DEPENDENCY_STRONG
            && services[dependent].flags & SERVICE_REQUIRED != 0
            && services
                [usize::try_from(item.prerequisite - 1).map_err(|_| Error::DependencyRecord)?]
            .flags
                & SERVICE_REQUIRED
                == 0
        {
            return Err(Error::DependencyAvailability);
        }
    }
    let mut start_order = [0u32; MAX_SERVICES];
    let mut selected = [false; MAX_SERVICES];
    for (rank, start) in start_order
        .iter_mut()
        .enumerate()
        .take(header.service_count)
    {
        let mut ready = None;
        for service in 0..header.service_count {
            if !selected[service] && indegree[service] == 0 {
                ready = Some(service);
                break;
            }
        }
        let ready = ready.ok_or(Error::DependencyCycle)?;
        selected[ready] = true;
        let service_id = u32::try_from(ready + 1).map_err(|_| Error::DependencyCycle)?;
        *start = service_id;
        if usize::from(services[ready].startup_rank) != rank {
            return Err(Error::StartupRank);
        }
        for item in &dependencies[..header.dependency_count] {
            if item.prerequisite == service_id {
                let dependent =
                    usize::try_from(item.dependent - 1).map_err(|_| Error::DependencyRecord)?;
                indegree[dependent] = indegree[dependent]
                    .checked_sub(1)
                    .ok_or(Error::DependencyRecord)?;
            }
        }
    }

    let mut reachable = [false; MAX_SERVICES];
    reachable[root_index] = true;
    loop {
        let mut changed = false;
        for item in &dependencies[..header.dependency_count] {
            if item.kind == DEPENDENCY_STRONG {
                let prerequisite =
                    usize::try_from(item.prerequisite - 1).map_err(|_| Error::DependencyRecord)?;
                let dependent =
                    usize::try_from(item.dependent - 1).map_err(|_| Error::DependencyRecord)?;
                if reachable[prerequisite] && !reachable[dependent] {
                    reachable[dependent] = true;
                    changed = true;
                }
            }
        }
        if !changed {
            break;
        }
    }
    if reachable[..header.service_count]
        .iter()
        .any(|value| !*value)
    {
        return Err(Error::DependencyReachability);
    }

    let mut ranks = [0usize; MAX_SERVICES];
    for (rank, service_id) in start_order[..header.service_count].iter().enumerate() {
        ranks[usize::try_from(*service_id - 1).map_err(|_| Error::StartupRank)?] = rank;
    }
    let mut total_restarts = 0u32;
    for service_id in 1..=header.service_count {
        let service = services[service_id - 1];
        let mut held_count = 0usize;
        let mut resource_seen = [false; MAX_RESOURCES];
        let mut held_resources = 0usize;
        for capability in &capabilities[..header.capability_count] {
            if usize::try_from(capability.holder).map_err(|_| Error::ServiceBudget)? == service_id {
                held_count += 1;
                let resource =
                    usize::try_from(capability.resource - 1).map_err(|_| Error::ServiceBudget)?;
                if !resource_seen[resource] {
                    resource_seen[resource] = true;
                    held_resources += 1;
                }
            }
        }
        let incoming = dependencies[..header.dependency_count]
            .iter()
            .filter(|item| usize::try_from(item.dependent).ok() == Some(service_id))
            .count();
        if usize::from(service.capability_count) != held_count
            || usize::from(service.resource_count) != held_resources
            || usize::from(service.dependency_count) != incoming
        {
            return Err(Error::ServiceBudget);
        }
        let ready_resource =
            usize::try_from(service.ready_resource_id - 1).map_err(|_| Error::HealthPolicy)?;
        if ready_resource >= header.resource_count
            || resources[ready_resource].kind != RESOURCE_ENDPOINT_SLOTS
        {
            return Err(Error::HealthPolicy);
        }
        total_restarts = total_restarts
            .checked_add(service.max_restarts)
            .ok_or(Error::Lifecycle)?;
    }
    if total_restarts != header.max_total_restarts {
        return Err(Error::Lifecycle);
    }
    for capability in &capabilities[..header.capability_count] {
        let resource = resources
            [usize::try_from(capability.resource - 1).map_err(|_| Error::CapabilityRoute)?];
        if resource.provider != 0 && resource.provider != capability.holder {
            if !has_dependency(
                &dependencies,
                header.dependency_count,
                capability.holder,
                resource.provider,
            ) {
                return Err(Error::CapabilityRoute);
            }
            let provider =
                usize::try_from(resource.provider - 1).map_err(|_| Error::CapabilityRoute)?;
            let holder =
                usize::try_from(capability.holder - 1).map_err(|_| Error::CapabilityRoute)?;
            if ranks[provider] >= ranks[holder] {
                return Err(Error::CapabilityRoute);
            }
        }
    }

    Ok(Bundle {
        bundle_version: header.bundle_version,
        minimum_secure_version: header.minimum_secure_version,
        root_service_id: header.root_service_id,
        allowed_boot_modes: header.allowed_boot_modes,
        required_kernel_abi_major: header.kernel_major,
        minimum_kernel_abi_minor: header.kernel_minor,
        required_pbp_major: header.pbp_major,
        minimum_pbp_minor: header.pbp_minor,
        start_timeout_ms: header.start_timeout_ms,
        rollback_timeout_ms: header.rollback_timeout_ms,
        max_total_restarts: header.max_total_restarts,
        component_count: u16::try_from(header.component_count).map_err(|_| Error::Count)?,
        service_count: u16::try_from(header.service_count).map_err(|_| Error::Count)?,
        dependency_count: u16::try_from(header.dependency_count).map_err(|_| Error::Count)?,
        resource_count: u16::try_from(header.resource_count).map_err(|_| Error::Count)?,
        capability_count: u16::try_from(header.capability_count).map_err(|_| Error::Count)?,
        start_order,
        body_sha256: header.body_sha256,
        raw: data,
    })
}

pub fn authorize_activation(bundle: &Bundle<'_>, context: &ActivationContext) -> Result<(), Error> {
    if context.outer_role != 2 {
        return Err(Error::ActivationRole);
    }
    if context.outer_artifact_version != bundle.bundle_version {
        return Err(Error::ActivationVersion);
    }
    if !context.outer_payload_digest_verified {
        return Err(Error::ActivationOuterPayloadDigest);
    }
    if !context.outer_file_digest_verified {
        return Err(Error::ActivationOuterFileDigest);
    }
    if !context.outer_signature_verified {
        return Err(Error::ActivationOuterSignature);
    }
    if !context.manifest_signature_verified {
        return Err(Error::ActivationManifestSignature);
    }
    if !context.rollback_state_authenticated {
        return Err(Error::ActivationRollbackState);
    }
    if context.trusted_minimum_secure_version > bundle.bundle_version
        || bundle.bundle_version < bundle.minimum_secure_version
    {
        return Err(Error::ActivationRollback);
    }
    if context.kernel_abi_major != bundle.required_kernel_abi_major
        || context.kernel_abi_minor < bundle.minimum_kernel_abi_minor
    {
        return Err(Error::ActivationKernelAbi);
    }
    if context.pbp_major != bundle.required_pbp_major
        || context.pbp_minor < bundle.minimum_pbp_minor
    {
        return Err(Error::ActivationPbp);
    }
    if context.boot_mode == 0
        || !context.boot_mode.is_power_of_two()
        || bundle.allowed_boot_modes & context.boot_mode == 0
    {
        return Err(Error::ActivationBootMode);
    }
    if !context.capability_allocator_ready {
        return Err(Error::ActivationCapabilityAllocator);
    }
    if !context.resource_broker_ready {
        return Err(Error::ActivationResourceBroker);
    }
    if !context.component_contracts_verified {
        return Err(Error::ActivationComponentContracts);
    }
    if !context.transaction_capacity_verified {
        return Err(Error::ActivationTransactionCapacity);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;
    use std::vec;
    use std::vec::Vec;

    fn write_u16(bytes: &mut [u8], offset: usize, value: u16) {
        bytes[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
    }

    fn write_u32(bytes: &mut [u8], offset: usize, value: u32) {
        bytes[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
    }

    fn write_u64(bytes: &mut [u8], offset: usize, value: u64) {
        bytes[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
    }

    fn fixture() -> Vec<u8> {
        let component_name = b"poole.init\0";
        let resource_name = b"bootstrap.memory\0";
        let service_name = b"service.init\0";
        let mut strings = Vec::new();
        strings.extend_from_slice(resource_name);
        let component_name_offset = strings.len();
        strings.extend_from_slice(component_name);
        let service_name_offset = strings.len();
        strings.extend_from_slice(service_name);
        let blob = b"PINIT1 test component\n";
        let component_offset = HEADER_BYTES;
        let service_offset = component_offset + COMPONENT_BYTES;
        let dependency_offset = service_offset + SERVICE_BYTES;
        let resource_offset = dependency_offset;
        let capability_offset = resource_offset + RESOURCE_BYTES;
        let string_offset = capability_offset + CAPABILITY_BYTES;
        let blob_offset = align(string_offset + strings.len()).unwrap();
        let total = blob_offset + blob.len();
        let mut bytes = vec![0u8; total];
        bytes[..8].copy_from_slice(&MAGIC);
        write_u16(&mut bytes, 8, MAJOR_VERSION);
        write_u16(&mut bytes, 10, MINOR_VERSION);
        write_u16(&mut bytes, 12, HEADER_BYTES as u16);
        write_u16(&mut bytes, 14, RECORD_ALIGNMENT as u16);
        write_u32(&mut bytes, 16, total as u32);
        write_u32(&mut bytes, 20, REQUIRED_FLAGS);
        write_u64(&mut bytes, 24, 1);
        write_u64(&mut bytes, 32, 1);
        write_u32(&mut bytes, 40, 1);
        write_u32(&mut bytes, 44, BOOT_NORMAL);
        write_u16(&mut bytes, 48, 1);
        write_u16(&mut bytes, 52, 1);
        write_u16(&mut bytes, 56, 1);
        write_u16(&mut bytes, 58, 1);
        write_u16(&mut bytes, 62, 1);
        write_u16(&mut bytes, 64, 1);
        for (offset, value) in [
            (68, component_offset),
            (72, service_offset),
            (76, dependency_offset),
            (80, resource_offset),
            (84, capability_offset),
            (88, string_offset),
            (92, strings.len()),
            (96, blob_offset),
            (100, blob.len()),
        ] {
            write_u32(&mut bytes, offset, value as u32);
        }
        write_u32(&mut bytes, 104, 10_000);
        write_u32(&mut bytes, 108, 10_000);
        let component = component_offset;
        write_u32(&mut bytes, component, 1);
        write_u16(&mut bytes, component + 4, COMPONENT_EXECUTABLE);
        write_u16(
            &mut bytes,
            component + 6,
            COMPONENT_REQUIRED | COMPONENT_READ_ONLY | COMPONENT_EXECUTABLE_FLAG,
        );
        write_u32(&mut bytes, component + 8, component_name_offset as u32);
        write_u16(
            &mut bytes,
            component + 12,
            (component_name.len() - 1) as u16,
        );
        bytes[component + 16..component + 24].copy_from_slice(&PXABI1);
        write_u32(&mut bytes, component + 28, blob.len() as u32);
        write_u32(&mut bytes, component + 32, 4096);
        write_u32(&mut bytes, component + 36, 4096);
        bytes[component + 40..component + 72].copy_from_slice(&sha256(blob));
        let service = service_offset;
        write_u32(&mut bytes, service, 1);
        write_u32(&mut bytes, service + 4, 1);
        write_u32(&mut bytes, service + 8, service_name_offset as u32);
        write_u16(&mut bytes, service + 12, (service_name.len() - 1) as u16);
        write_u16(&mut bytes, service + 14, ROOT_SERVICE_FLAGS);
        write_u32(&mut bytes, service + 16, 1000);
        write_u32(&mut bytes, service + 20, 1000);
        write_u16(&mut bytes, service + 26, FAILURE_ROLLBACK_BUNDLE);
        write_u16(&mut bytes, service + 28, READINESS_EXPLICIT);
        write_u16(&mut bytes, service + 30, SHUTDOWN_REVERSE_DEPENDENCY);
        write_u32(&mut bytes, service + 48, 500);
        write_u32(&mut bytes, service + 52, 1);
        write_u16(&mut bytes, service + 56, 1);
        write_u16(&mut bytes, service + 58, 1);
        let resource = resource_offset;
        write_u32(&mut bytes, resource, 1);
        write_u32(&mut bytes, resource + 8, 0);
        write_u16(&mut bytes, resource + 12, (resource_name.len() - 1) as u16);
        write_u16(&mut bytes, resource + 14, RESOURCE_ENDPOINT_SLOTS);
        write_u32(
            &mut bytes,
            resource + 16,
            RESOURCE_REQUIRED | RESOURCE_REVOCABLE | RESOURCE_EXCLUSIVE,
        );
        write_u64(&mut bytes, resource + 24, 1);
        write_u64(&mut bytes, resource + 32, 8);
        write_u32(&mut bytes, resource + 40, 1);
        let cap = capability_offset;
        write_u32(&mut bytes, cap, 1);
        write_u32(&mut bytes, cap + 8, 1);
        write_u32(&mut bytes, cap + 12, 1);
        write_u64(
            &mut bytes,
            cap + 16,
            RIGHT_READ | RIGHT_WRITE | RIGHT_MAP_OR_BIND,
        );
        write_u32(&mut bytes, cap + 24, CAP_REVOCABLE | CAP_LIFECYCLE_BOUND);
        write_u32(&mut bytes, cap + 28, 1);
        write_u16(&mut bytes, cap + 38, AVAILABILITY_REQUIRED);
        bytes[string_offset..string_offset + strings.len()].copy_from_slice(&strings);
        bytes[blob_offset..].copy_from_slice(blob);
        let digest = sha256(&bytes[HEADER_BYTES..]);
        bytes[120..152].copy_from_slice(&digest);
        bytes
    }

    #[test]
    fn parses_canonical_single_service_bundle() {
        let bytes = fixture();
        let bundle = parse(&bytes).unwrap();
        assert_eq!(bundle.component_count, 1);
        assert_eq!(bundle.service_count, 1);
        assert_eq!(bundle.start_order[0], 1);
    }

    #[test]
    fn rejects_body_component_and_authority_drift() {
        let bytes = fixture();
        let mut changed = bytes.clone();
        *changed.last_mut().unwrap() ^= 1;
        assert_eq!(parse(&changed), Err(Error::BodyDigest));
        let mut component = bytes.clone();
        component[HEADER_BYTES + 40] ^= 1;
        let digest = sha256(&component[HEADER_BYTES..]);
        component[120..152].copy_from_slice(&digest);
        assert_eq!(parse(&component), Err(Error::ComponentDigest));
        let bundle = parse(&bytes).unwrap();
        assert_eq!(
            authorize_activation(&bundle, &ActivationContext::development()),
            Err(Error::ActivationOuterSignature)
        );
        assert_eq!(
            authorize_activation(&bundle, &ActivationContext::synthetic_qualified()),
            Ok(())
        );
    }

    #[test]
    fn rejects_data_component_as_service_target() {
        let mut bytes = fixture();
        let component = HEADER_BYTES;
        write_u16(&mut bytes, component + 4, COMPONENT_DATA);
        write_u16(
            &mut bytes,
            component + 6,
            COMPONENT_REQUIRED | COMPONENT_READ_ONLY,
        );
        bytes[component + 16..component + 24].copy_from_slice(&PINITD1);
        write_u32(&mut bytes, component + 32, 0);
        let digest = sha256(&bytes[HEADER_BYTES..]);
        bytes[120..152].copy_from_slice(&digest);
        assert_eq!(parse(&bytes), Err(Error::ServiceRecord));
    }
}
