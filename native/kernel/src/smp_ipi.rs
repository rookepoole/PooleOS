//! Pure PKSMP5 multi-AP startup, IPI, shootdown, and rollback contract.

use core::mem::{offset_of, size_of};

use crate::{
    interrupt_time::{MadtTopology, Processor},
    smp, smp_runtime,
};

pub const CONTRACT_ID: &str = "PKSMP5";
pub const SELECTED_MOVE_ID: &str = "N8-SMP-MULTI-AP-001";
pub const SELECTOR: u64 = 14;
pub const EXPECTED_PROCESSOR_COUNT: usize = 4;
pub const AP_COUNT: usize = 3;
pub const EXPECTED_BSP_APIC_ID: u32 = 0;
#[used]
#[unsafe(link_section = ".text.pksmp5_literals")]
pub static EXPECTED_APIC_IDS: [u32; AP_COUNT] = [1, 2, 3];
pub const PARTIAL_STARTED_MASK: u64 = (1 << 1) | (1 << 2);
pub const TARGET_CPU_MASK: u64 = (1 << 1) | (1 << 2) | (1 << 3);
pub const OFFLINE_APIC_ID: u32 = 4;
pub const OFFLINE_CPU_MASK: u64 = 1 << OFFLINE_APIC_ID;
pub const MULTI_AP_QUOTA_PAGES: u64 = 128;

pub const PAGE_BYTES: u64 = smp_runtime::PAGE_BYTES;
pub const APIC_PAGE_TABLE_OFFSET: u64 = smp_runtime::RESERVED_PAGE_OFFSET;
pub const APIC_PDPT_INDEX: usize = 3;
pub const APIC_PAGE_DIRECTORY_INDEX: usize = 503;
pub const APIC_PAGE_TABLE_INDEX: usize = 0;
pub const APIC_PHYSICAL_ADDRESS: u64 = 0xfee0_0000;
pub const APIC_EOI_OFFSET: u64 = 0x0b0;
pub const APIC_SPURIOUS_OFFSET: u64 = 0x0f0;

pub const EXTENSION_MAGIC: u64 = 0x504b_534d_5035_4950;
pub const EXTENSION_VERSION: u32 = 3;
pub const SERVICE_STATE_PREPARED: u32 = 1;
pub const SERVICE_STATE_ONLINE: u32 = 2;
pub const SERVICE_STATE_PANIC: u32 = 3;
pub const SERVICE_STATE_QUIESCED: u32 = 4;
pub const SERVICE_STATE_FAULTED: u32 = u32::MAX;

pub const REQUEST_IDLE: u32 = 0;
pub const REQUEST_ARMED: u32 = 1;
pub const ACK_NONE: u32 = 0;
pub const ACK_ACCEPTED: u32 = 1;
pub const ACK_DENIED: u32 = 2;

pub const ERROR_NONE: u32 = 0;
pub const ERROR_CAPABILITY: u32 = 1;
pub const ERROR_REQUEST_STATE: u32 = 2;
pub const ERROR_OPERATION: u32 = 3;
pub const ERROR_VECTOR: u32 = 4;
pub const ERROR_TARGET: u32 = 5;
pub const ERROR_CHECKSUM: u32 = 6;
pub const ERROR_STALE_SEQUENCE: u32 = 7;
pub const ERROR_DUPLICATE_SEQUENCE: u32 = 8;
pub const ERROR_ATTEMPT: u32 = 9;
pub const ERROR_PAYLOAD: u32 = 10;
pub const ERROR_PANIC_LATCHED: u32 = 11;
pub const ERROR_SHOOTDOWN_STATE: u32 = 12;
pub const ERROR_SHOOTDOWN_ROOT: u32 = 13;
pub const ERROR_SHOOTDOWN_GENERATION: u32 = 14;
pub const ERROR_SHOOTDOWN_TARGET: u32 = 15;
pub const ERROR_SHOOTDOWN_ADDRESS: u32 = 16;
pub const ERROR_SHOOTDOWN_CHECKSUM: u32 = 17;

pub const CAPABILITY_HIGH: u64 = 0x504f_4f4c_454f_5349;
pub const CAPABILITY_LOW: u64 = 0x504b_534d_5035_0001;
pub const REQUEST_CHECKSUM_SEED: u64 = 0x4950_4952_4551_0001;
pub const RESPONSE_CHECKSUM_SEED: u64 = 0x4950_4952_5350_0001;

pub const RESCHEDULE_PAYLOAD: u64 = 0;
pub const SHOOTDOWN_GENERATION: u64 = 2;
pub const CALL_NOOP_TOKEN: u64 = 0x504b_4e4f_4f50_0001;
pub const CALL_DRIVER_TIMER_TOKEN: u64 = 0x504b_4452_5652_0001;
pub const CALL_SERVICE_RECLAIM_TOKEN: u64 = 0x504b_5352_5643_0001;
pub const DIAGNOSTIC_TOKEN: u64 = 0x504b_4449_4147_0001;
pub const PANIC_NOTICE_TOKEN: u64 = 0x504b_5041_4e49_0001;
pub const STOP_TOKEN: u64 = 0x504b_5354_4f50_0001;

pub const RESULT_RESCHEDULE_OBSERVED: u64 = 0x5253_4348_4544_0001;
pub const RESULT_SHOOTDOWN_INVALIDATED: u64 = 0x5348_4f4f_5400_0002;
pub const RESULT_CALL_ALLOWLIST_NOOP: u64 = 0x4341_4c4c_4e4f_4f50;
pub const RESULT_CALL_DRIVER_TIMER: u64 = 0x4452_5652_5449_4d45;
pub const RESULT_CALL_SERVICE_RECLAIM: u64 = 0x5352_5643_5243_4c4d;
pub const RESULT_DIAGNOSTIC_OBSERVED: u64 = 0x4449_4147_4e4f_0001;
pub const RESULT_PANIC_LATCHED: u64 = 0x5041_4e49_4300_0001;
pub const RESULT_STOP_QUIESCED: u64 = 0x5354_4f50_0000_0001;

pub const LIVE_ACCEPTED_COUNT: u32 = 3;
pub const LIVE_DENIED_COUNT: u32 = 1;
pub const LIVE_DELIVERY_COUNT: u32 = LIVE_ACCEPTED_COUNT + LIVE_DENIED_COUNT;
pub const LIVE_TIMEOUT_COUNT: u32 = 1;
pub const LIVE_FINAL_ATTEMPT: u64 = 4;
pub const LIVE_FINAL_SEQUENCE: u64 = 3;

pub const SHOOTDOWN_MAGIC: u64 = 0x504b_534d_5035_544c;
pub const SHOOTDOWN_VERSION: u32 = 2;
pub const SHOOTDOWN_STATE_PREPARED: u32 = 1;
pub const SHOOTDOWN_STATE_ARMED: u32 = 2;
pub const SHOOTDOWN_STATE_ACKED: u32 = 3;
pub const SHOOTDOWN_STATE_TIMED_OUT: u32 = 4;
pub const SHOOTDOWN_STATE_QUIESCED: u32 = 5;
pub const SHOOTDOWN_STATE_FAULTED: u32 = u32::MAX;
pub const RECLAIM_BLOCKED: u32 = 1;
pub const RECLAIM_AUTHORIZED: u32 = 2;
pub const RECLAIM_RELEASED: u32 = 3;
pub const SHOOTDOWN_REQUEST_CHECKSUM_SEED: u64 = 0x5348_4f4f_5452_4551;
pub const SHOOTDOWN_RESPONSE_CHECKSUM_SEED: u64 = 0x5348_4f4f_5452_5350;
const AGGREGATE_FNV_OFFSET: u64 = 0xcbf2_9ce4_8422_2325;
const AGGREGATE_FNV_PRIME: u64 = 0x0000_0100_0000_01b3;
const AGGREGATE_ROOT_DOMAIN: u64 = 0x524f_4f54_0000_0001;
const AGGREGATE_OLD_FRAME_DOMAIN: u64 = 0x4f4c_4446_0000_0001;
const AGGREGATE_NEW_FRAME_DOMAIN: u64 = 0x4e45_5746_0000_0001;
pub const RETIRED_GENERATION: u64 = 1;
pub const ACTIVE_GENERATION: u64 = 2;
pub const PROBE_VIRTUAL_ADDRESS: u64 = 0x001f_f000;
pub const PROBE_PAGE_TABLE_INDEX: usize = 511;
pub const OLD_FRAME_VALUE: u64 = 0x504b_534d_5035_4f4c;
pub const NEW_FRAME_VALUE: u64 = 0x504b_534d_5035_4e57;
pub const SHOOTDOWN_FRAME_OWNER: u16 = 0x0914;

pub const fn local_target_mask(apic_id: u32) -> Option<u64> {
    if apic_id == 0 || apic_id >= 64 {
        None
    } else {
        Some(1u64 << apic_id)
    }
}

pub fn select_exact_aps(
    topology: &MadtTopology,
    bsp_apic_id: u32,
) -> Result<[Processor; AP_COUNT], smp::Error> {
    if topology.processor_count != EXPECTED_PROCESSOR_COUNT
        || topology.enabled_processor_count != EXPECTED_PROCESSOR_COUNT
        || bsp_apic_id != EXPECTED_BSP_APIC_ID
    {
        return Err(smp::Error::ProcessorCount);
    }
    let bsp = topology
        .processors
        .iter()
        .take(topology.processor_count)
        .copied()
        .find(|processor| processor.enabled && processor.apic_id == bsp_apic_id)
        .ok_or(smp::Error::BspMissing)?;
    if bsp.x2apic {
        return Err(smp::Error::X2ApicUnsupported);
    }
    let mut aps = [bsp; AP_COUNT];
    for (index, expected_apic_id) in EXPECTED_APIC_IDS.into_iter().enumerate() {
        let target = topology
            .processors
            .iter()
            .take(topology.processor_count)
            .copied()
            .find(|processor| processor.enabled && processor.apic_id == expected_apic_id)
            .ok_or(smp::Error::TargetMissing)?;
        if target.x2apic {
            return Err(smp::Error::X2ApicUnsupported);
        }
        if target.apic_id >= 64 {
            return Err(smp::Error::TargetApicId);
        }
        aps[index] = target;
    }
    Ok(aps)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u32)]
pub enum Operation {
    Reschedule = 1,
    Shootdown = 2,
    CallFunction = 3,
    Diagnostic = 4,
    Panic = 5,
    Stop = 6,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum CallPayload {
    Noop = 1,
    DriverTimerBottomHalf = 2,
    ServiceGenerationReclaim = 3,
}

impl CallPayload {
    pub const ALL: [Self; 3] = [
        Self::Noop,
        Self::DriverTimerBottomHalf,
        Self::ServiceGenerationReclaim,
    ];

    pub const fn token(self) -> u64 {
        match self {
            Self::Noop => CALL_NOOP_TOKEN,
            Self::DriverTimerBottomHalf => CALL_DRIVER_TIMER_TOKEN,
            Self::ServiceGenerationReclaim => CALL_SERVICE_RECLAIM_TOKEN,
        }
    }

    pub const fn result(self) -> u64 {
        match self {
            Self::Noop => RESULT_CALL_ALLOWLIST_NOOP,
            Self::DriverTimerBottomHalf => RESULT_CALL_DRIVER_TIMER,
            Self::ServiceGenerationReclaim => RESULT_CALL_SERVICE_RECLAIM,
        }
    }

    pub const fn from_token(token: u64) -> Option<Self> {
        match token {
            CALL_NOOP_TOKEN => Some(Self::Noop),
            CALL_DRIVER_TIMER_TOKEN => Some(Self::DriverTimerBottomHalf),
            CALL_SERVICE_RECLAIM_TOKEN => Some(Self::ServiceGenerationReclaim),
            _ => None,
        }
    }
}

impl Operation {
    pub const ALL: [Self; 6] = [
        Self::Reschedule,
        Self::Shootdown,
        Self::CallFunction,
        Self::Diagnostic,
        Self::Panic,
        Self::Stop,
    ];

    pub const fn from_u32(value: u32) -> Option<Self> {
        match value {
            1 => Some(Self::Reschedule),
            2 => Some(Self::Shootdown),
            3 => Some(Self::CallFunction),
            4 => Some(Self::Diagnostic),
            5 => Some(Self::Panic),
            6 => Some(Self::Stop),
            _ => None,
        }
    }

    #[inline(always)]
    pub const fn vector(self) -> u8 {
        0xdf + self as u8
    }

    #[inline(always)]
    pub const fn payload(self) -> u64 {
        match self {
            Self::Reschedule => RESCHEDULE_PAYLOAD,
            Self::Shootdown => SHOOTDOWN_GENERATION,
            Self::CallFunction => CALL_NOOP_TOKEN,
            Self::Diagnostic => DIAGNOSTIC_TOKEN,
            Self::Panic => PANIC_NOTICE_TOKEN,
            Self::Stop => STOP_TOKEN,
        }
    }

    #[inline(always)]
    pub const fn result(self) -> u64 {
        match self {
            Self::Reschedule => RESULT_RESCHEDULE_OBSERVED,
            Self::Shootdown => RESULT_SHOOTDOWN_INVALIDATED,
            Self::CallFunction => RESULT_CALL_ALLOWLIST_NOOP,
            Self::Diagnostic => RESULT_DIAGNOSTIC_OBSERVED,
            Self::Panic => RESULT_PANIC_LATCHED,
            Self::Stop => RESULT_STOP_QUIESCED,
        }
    }
}

pub const IPI_VECTORS: [u8; 6] = [0xe0, 0xe1, 0xe2, 0xe3, 0xe4, 0xe5];

#[derive(Clone, Copy)]
#[repr(C)]
pub struct IpiExtension {
    pub magic: u64,
    pub version: u32,
    pub service_state: u32,
    pub capability_high: u64,
    pub capability_low: u64,
    pub request_capability_high: u64,
    pub request_capability_low: u64,
    pub request_attempt: u64,
    pub request_sequence: u64,
    pub payload: u64,
    pub request_checksum: u64,
    pub ack_attempt: u64,
    pub ack_sequence: u64,
    pub result: u64,
    pub response_checksum: u64,
    pub last_accepted_sequence: u64,
    pub request_operation: u32,
    pub request_vector: u32,
    pub request_target_apic_id: u32,
    pub request_status: u32,
    pub ack_operation: u32,
    pub ack_status: u32,
    pub ack_error: u32,
    pub delivery_count: u32,
    pub eoi_count: u32,
    pub accepted_count: u32,
    pub denied_count: u32,
    pub reschedule_count: u32,
    pub shootdown_count: u32,
    pub call_function_count: u32,
    pub diagnostic_count: u32,
    pub stop_count: u32,
    pub panic_count: u32,
    pub panic_latched: u32,
    pub spurious_count: u32,
    pub apic_error_count: u32,
    pub shootdown_magic: u64,
    pub shootdown_version: u32,
    pub shootdown_state: u32,
    pub shootdown_error: u32,
    pub shootdown_reserved: u32,
    pub shootdown_root_physical: u64,
    pub shootdown_virtual_address: u64,
    pub shootdown_retired_generation: u64,
    pub shootdown_active_generation: u64,
    pub shootdown_target_mask: u64,
    pub shootdown_ack_mask: u64,
    pub shootdown_old_frame_physical: u64,
    pub shootdown_new_frame_physical: u64,
    pub shootdown_observed_before: u64,
    pub shootdown_observed_after: u64,
    pub shootdown_invalidation_count: u64,
    pub shootdown_request_checksum: u64,
    pub shootdown_response_checksum: u64,
    pub shootdown_last_ack_generation: u64,
    pub shootdown_timeout_count: u32,
    pub shootdown_reclaim_state: u32,
}

pub const EXTENSION_BASE_OFFSET: usize = smp_runtime::MAILBOX_BYTES;
pub const EXTENSION_BYTES: usize = size_of::<IpiExtension>();
pub const MAILBOX_BYTES: usize = EXTENSION_BASE_OFFSET + EXTENSION_BYTES;

macro_rules! extension_offset {
    ($field:ident) => {
        EXTENSION_BASE_OFFSET + offset_of!(IpiExtension, $field)
    };
}

pub const MAGIC_OFFSET: usize = extension_offset!(magic);
pub const VERSION_OFFSET: usize = extension_offset!(version);
pub const SERVICE_STATE_OFFSET: usize = extension_offset!(service_state);
pub const CAPABILITY_HIGH_OFFSET: usize = extension_offset!(capability_high);
pub const CAPABILITY_LOW_OFFSET: usize = extension_offset!(capability_low);
pub const REQUEST_CAPABILITY_HIGH_OFFSET: usize = extension_offset!(request_capability_high);
pub const REQUEST_CAPABILITY_LOW_OFFSET: usize = extension_offset!(request_capability_low);
pub const REQUEST_ATTEMPT_OFFSET: usize = extension_offset!(request_attempt);
pub const REQUEST_SEQUENCE_OFFSET: usize = extension_offset!(request_sequence);
pub const PAYLOAD_OFFSET: usize = extension_offset!(payload);
pub const REQUEST_CHECKSUM_OFFSET: usize = extension_offset!(request_checksum);
pub const ACK_ATTEMPT_OFFSET: usize = extension_offset!(ack_attempt);
pub const ACK_SEQUENCE_OFFSET: usize = extension_offset!(ack_sequence);
pub const RESULT_OFFSET: usize = extension_offset!(result);
pub const RESPONSE_CHECKSUM_OFFSET: usize = extension_offset!(response_checksum);
pub const LAST_ACCEPTED_SEQUENCE_OFFSET: usize = extension_offset!(last_accepted_sequence);
pub const REQUEST_OPERATION_OFFSET: usize = extension_offset!(request_operation);
pub const REQUEST_VECTOR_OFFSET: usize = extension_offset!(request_vector);
pub const REQUEST_TARGET_APIC_ID_OFFSET: usize = extension_offset!(request_target_apic_id);
pub const REQUEST_STATUS_OFFSET: usize = extension_offset!(request_status);
pub const ACK_OPERATION_OFFSET: usize = extension_offset!(ack_operation);
pub const ACK_STATUS_OFFSET: usize = extension_offset!(ack_status);
pub const ACK_ERROR_OFFSET: usize = extension_offset!(ack_error);
pub const DELIVERY_COUNT_OFFSET: usize = extension_offset!(delivery_count);
pub const EOI_COUNT_OFFSET: usize = extension_offset!(eoi_count);
pub const ACCEPTED_COUNT_OFFSET: usize = extension_offset!(accepted_count);
pub const DENIED_COUNT_OFFSET: usize = extension_offset!(denied_count);
pub const RESCHEDULE_COUNT_OFFSET: usize = extension_offset!(reschedule_count);
pub const SHOOTDOWN_COUNT_OFFSET: usize = extension_offset!(shootdown_count);
pub const CALL_FUNCTION_COUNT_OFFSET: usize = extension_offset!(call_function_count);
pub const DIAGNOSTIC_COUNT_OFFSET: usize = extension_offset!(diagnostic_count);
pub const STOP_COUNT_OFFSET: usize = extension_offset!(stop_count);
pub const PANIC_COUNT_OFFSET: usize = extension_offset!(panic_count);
pub const PANIC_LATCHED_OFFSET: usize = extension_offset!(panic_latched);
pub const SPURIOUS_COUNT_OFFSET: usize = extension_offset!(spurious_count);
pub const APIC_ERROR_COUNT_OFFSET: usize = extension_offset!(apic_error_count);
pub const SHOOTDOWN_MAGIC_OFFSET: usize = extension_offset!(shootdown_magic);
pub const SHOOTDOWN_VERSION_OFFSET: usize = extension_offset!(shootdown_version);
pub const SHOOTDOWN_STATE_OFFSET: usize = extension_offset!(shootdown_state);
pub const SHOOTDOWN_ERROR_OFFSET: usize = extension_offset!(shootdown_error);
pub const SHOOTDOWN_ROOT_PHYSICAL_OFFSET: usize = extension_offset!(shootdown_root_physical);
pub const SHOOTDOWN_VIRTUAL_ADDRESS_OFFSET: usize = extension_offset!(shootdown_virtual_address);
pub const SHOOTDOWN_RETIRED_GENERATION_OFFSET: usize =
    extension_offset!(shootdown_retired_generation);
pub const SHOOTDOWN_ACTIVE_GENERATION_OFFSET: usize =
    extension_offset!(shootdown_active_generation);
pub const SHOOTDOWN_TARGET_MASK_OFFSET: usize = extension_offset!(shootdown_target_mask);
pub const SHOOTDOWN_ACK_MASK_OFFSET: usize = extension_offset!(shootdown_ack_mask);
pub const SHOOTDOWN_OLD_FRAME_PHYSICAL_OFFSET: usize =
    extension_offset!(shootdown_old_frame_physical);
pub const SHOOTDOWN_NEW_FRAME_PHYSICAL_OFFSET: usize =
    extension_offset!(shootdown_new_frame_physical);
pub const SHOOTDOWN_OBSERVED_BEFORE_OFFSET: usize = extension_offset!(shootdown_observed_before);
pub const SHOOTDOWN_OBSERVED_AFTER_OFFSET: usize = extension_offset!(shootdown_observed_after);
pub const SHOOTDOWN_INVALIDATION_COUNT_OFFSET: usize =
    extension_offset!(shootdown_invalidation_count);
pub const SHOOTDOWN_REQUEST_CHECKSUM_OFFSET: usize = extension_offset!(shootdown_request_checksum);
pub const SHOOTDOWN_RESPONSE_CHECKSUM_OFFSET: usize =
    extension_offset!(shootdown_response_checksum);
pub const SHOOTDOWN_LAST_ACK_GENERATION_OFFSET: usize =
    extension_offset!(shootdown_last_ack_generation);
pub const SHOOTDOWN_TIMEOUT_COUNT_OFFSET: usize = extension_offset!(shootdown_timeout_count);
pub const SHOOTDOWN_RECLAIM_STATE_OFFSET: usize = extension_offset!(shootdown_reclaim_state);

const _: () = assert!(EXTENSION_BASE_OFFSET == 352);
const _: () = assert!(EXTENSION_BYTES == 344);
const _: () = assert!(MAGIC_OFFSET == 352);
const _: () = assert!(REQUEST_ATTEMPT_OFFSET == 400);
const _: () = assert!(ACK_ATTEMPT_OFFSET == 432);
const _: () = assert!(REQUEST_OPERATION_OFFSET == 472);
const _: () = assert!(APIC_ERROR_COUNT_OFFSET == 548);
const _: () = assert!(SHOOTDOWN_MAGIC_OFFSET == 552);
const _: () = assert!(SHOOTDOWN_ROOT_PHYSICAL_OFFSET == 576);
const _: () = assert!(SHOOTDOWN_LAST_ACK_GENERATION_OFFSET == 680);
const _: () = assert!(SHOOTDOWN_RECLAIM_STATE_OFFSET == 692);
const _: () = assert!(MAILBOX_BYTES == 696);
const _: () = assert!((APIC_PHYSICAL_ADDRESS >> 30) as usize & 0x1ff == APIC_PDPT_INDEX);
const _: () = assert!((APIC_PHYSICAL_ADDRESS >> 21) as usize & 0x1ff == APIC_PAGE_DIRECTORY_INDEX);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct IpiSnapshot {
    pub magic: u64,
    pub version: u32,
    pub service_state: u32,
    pub capability_high: u64,
    pub capability_low: u64,
    pub request_capability_high: u64,
    pub request_capability_low: u64,
    pub request_attempt: u64,
    pub request_sequence: u64,
    pub payload: u64,
    pub request_checksum: u64,
    pub ack_attempt: u64,
    pub ack_sequence: u64,
    pub result: u64,
    pub response_checksum: u64,
    pub last_accepted_sequence: u64,
    pub request_operation: u32,
    pub request_vector: u32,
    pub request_target_apic_id: u32,
    pub request_status: u32,
    pub ack_operation: u32,
    pub ack_status: u32,
    pub ack_error: u32,
    pub delivery_count: u32,
    pub eoi_count: u32,
    pub accepted_count: u32,
    pub denied_count: u32,
    pub reschedule_count: u32,
    pub shootdown_count: u32,
    pub call_function_count: u32,
    pub diagnostic_count: u32,
    pub stop_count: u32,
    pub panic_count: u32,
    pub panic_latched: u32,
    pub spurious_count: u32,
    pub apic_error_count: u32,
    pub shootdown: ShootdownSnapshot,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ShootdownSnapshot {
    pub magic: u64,
    pub version: u32,
    pub state: u32,
    pub error: u32,
    pub root_physical: u64,
    pub virtual_address: u64,
    pub retired_generation: u64,
    pub active_generation: u64,
    pub target_mask: u64,
    pub ack_mask: u64,
    pub old_frame_physical: u64,
    pub new_frame_physical: u64,
    pub observed_before: u64,
    pub observed_after: u64,
    pub invalidation_count: u64,
    pub request_checksum: u64,
    pub response_checksum: u64,
    pub last_ack_generation: u64,
    pub timeout_count: u32,
    pub reclaim_state: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ShootdownRequest {
    pub root_physical: u64,
    pub virtual_address: u64,
    pub retired_generation: u64,
    pub active_generation: u64,
    pub target_mask: u64,
    pub old_frame_physical: u64,
    pub new_frame_physical: u64,
    pub checksum: u64,
}

impl ShootdownRequest {
    pub const fn canonical(
        root_physical: u64,
        old_frame_physical: u64,
        new_frame_physical: u64,
    ) -> Self {
        Self::canonical_for_target(1, root_physical, old_frame_physical, new_frame_physical)
    }

    pub const fn canonical_for_target(
        target_apic_id: u32,
        root_physical: u64,
        old_frame_physical: u64,
        new_frame_physical: u64,
    ) -> Self {
        let mut value = Self {
            root_physical,
            virtual_address: PROBE_VIRTUAL_ADDRESS,
            retired_generation: RETIRED_GENERATION,
            active_generation: ACTIVE_GENERATION,
            target_mask: match local_target_mask(target_apic_id) {
                Some(mask) => mask,
                None => 0,
            },
            old_frame_physical,
            new_frame_physical,
            checksum: 0,
        };
        value.checksum = shootdown_request_checksum(&value);
        value
    }
}

pub const fn shootdown_request_checksum(request: &ShootdownRequest) -> u64 {
    SHOOTDOWN_REQUEST_CHECKSUM_SEED
        ^ request.root_physical
        ^ request.virtual_address
        ^ request.retired_generation
        ^ request.active_generation
        ^ request.target_mask
        ^ request.old_frame_physical
        ^ request.new_frame_physical
}

pub const fn shootdown_response_checksum(snapshot: &ShootdownSnapshot) -> u64 {
    SHOOTDOWN_RESPONSE_CHECKSUM_SEED
        ^ snapshot.root_physical
        ^ snapshot.virtual_address
        ^ snapshot.active_generation
        ^ snapshot.target_mask
        ^ snapshot.ack_mask
        ^ snapshot.observed_before
        ^ snapshot.observed_after
        ^ snapshot.invalidation_count
        ^ snapshot.last_ack_generation
        ^ snapshot.state as u64
        ^ snapshot.error as u64
}

pub fn validate_shootdown_request(
    request: &ShootdownRequest,
    expected_root: u64,
    last_ack_generation: u64,
) -> Result<(), u32> {
    validate_shootdown_request_for_target(request, expected_root, last_ack_generation, 1)
}

pub fn validate_shootdown_request_for_target(
    request: &ShootdownRequest,
    expected_root: u64,
    last_ack_generation: u64,
    target_apic_id: u32,
) -> Result<(), u32> {
    if request.root_physical != expected_root || !request.root_physical.is_multiple_of(PAGE_BYTES) {
        return Err(ERROR_SHOOTDOWN_ROOT);
    }
    if request.virtual_address != PROBE_VIRTUAL_ADDRESS
        || !request.virtual_address.is_multiple_of(PAGE_BYTES)
    {
        return Err(ERROR_SHOOTDOWN_ADDRESS);
    }
    if request.retired_generation != RETIRED_GENERATION
        || request.active_generation != request.retired_generation.wrapping_add(1)
        || request.active_generation <= last_ack_generation
    {
        return Err(ERROR_SHOOTDOWN_GENERATION);
    }
    if local_target_mask(target_apic_id) != Some(request.target_mask) {
        return Err(ERROR_SHOOTDOWN_TARGET);
    }
    if request.old_frame_physical == request.new_frame_physical
        || request.old_frame_physical == 0
        || request.new_frame_physical == 0
        || !request.old_frame_physical.is_multiple_of(PAGE_BYTES)
        || !request.new_frame_physical.is_multiple_of(PAGE_BYTES)
    {
        return Err(ERROR_SHOOTDOWN_ADDRESS);
    }
    if request.checksum != shootdown_request_checksum(request) {
        return Err(ERROR_SHOOTDOWN_CHECKSUM);
    }
    Ok(())
}

pub fn validate_shootdown_ack(
    snapshot: &ShootdownSnapshot,
    request: &ShootdownRequest,
) -> Result<(), Error> {
    validate_shootdown_ack_for_target(snapshot, request, 1)
}

pub fn validate_shootdown_ack_for_target(
    snapshot: &ShootdownSnapshot,
    request: &ShootdownRequest,
    target_apic_id: u32,
) -> Result<(), Error> {
    validate_shootdown_request_for_target(request, request.root_physical, 0, target_apic_id)
        .map_err(|_| Error::Target)?;
    if snapshot.magic != SHOOTDOWN_MAGIC
        || snapshot.version != SHOOTDOWN_VERSION
        || snapshot.state != SHOOTDOWN_STATE_ACKED
        || snapshot.error != ERROR_NONE
    {
        return Err(Error::MailboxShape);
    }
    if snapshot.root_physical != request.root_physical
        || snapshot.virtual_address != request.virtual_address
        || snapshot.retired_generation != request.retired_generation
        || snapshot.active_generation != request.active_generation
        || snapshot.old_frame_physical != request.old_frame_physical
        || snapshot.new_frame_physical != request.new_frame_physical
    {
        return Err(Error::Result);
    }
    if snapshot.target_mask != request.target_mask
        || snapshot.ack_mask != request.target_mask
        || local_target_mask(target_apic_id) != Some(snapshot.ack_mask)
    {
        return Err(Error::Target);
    }
    if snapshot.observed_before != OLD_FRAME_VALUE
        || snapshot.observed_after != NEW_FRAME_VALUE
        || snapshot.invalidation_count != 1
        || snapshot.last_ack_generation != request.active_generation
    {
        return Err(Error::Result);
    }
    if snapshot.request_checksum != request.checksum
        || snapshot.response_checksum != shootdown_response_checksum(snapshot)
    {
        return Err(Error::Checksum);
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct GenerationRetirementReceipt {
    pub root_physical: u64,
    pub retired_generation: u64,
    pub active_generation: u64,
    pub target_mask: u64,
    pub ack_mask: u64,
    pub invalidation_count: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ReclaimError {
    State,
    Request,
    Acknowledgement,
    Duplicate,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ReclaimStage {
    Prepared,
    Armed,
    TimedOut,
    Acknowledged,
    Authorized,
    Released,
}

pub struct DeferredReclaim {
    request: ShootdownRequest,
    stage: ReclaimStage,
}

impl DeferredReclaim {
    pub fn new(request: ShootdownRequest) -> Result<Self, ReclaimError> {
        validate_shootdown_request(&request, request.root_physical, 0)
            .map_err(|_| ReclaimError::Request)?;
        Ok(Self {
            request,
            stage: ReclaimStage::Prepared,
        })
    }

    pub fn arm(&mut self) -> Result<(), ReclaimError> {
        if !matches!(self.stage, ReclaimStage::Prepared | ReclaimStage::TimedOut) {
            return Err(ReclaimError::State);
        }
        self.stage = ReclaimStage::Armed;
        Ok(())
    }

    pub fn timeout(&mut self) -> Result<(), ReclaimError> {
        if self.stage != ReclaimStage::Armed {
            return Err(ReclaimError::State);
        }
        self.stage = ReclaimStage::TimedOut;
        Ok(())
    }

    pub fn acknowledge(&mut self, snapshot: &ShootdownSnapshot) -> Result<(), ReclaimError> {
        if self.stage != ReclaimStage::Armed {
            return Err(ReclaimError::State);
        }
        validate_shootdown_ack(snapshot, &self.request)
            .map_err(|_| ReclaimError::Acknowledgement)?;
        self.stage = ReclaimStage::Acknowledged;
        Ok(())
    }

    pub fn authorize(&mut self) -> Result<GenerationRetirementReceipt, ReclaimError> {
        if self.stage != ReclaimStage::Acknowledged {
            return Err(ReclaimError::State);
        }
        self.stage = ReclaimStage::Authorized;
        Ok(GenerationRetirementReceipt {
            root_physical: self.request.root_physical,
            retired_generation: self.request.retired_generation,
            active_generation: self.request.active_generation,
            target_mask: self.request.target_mask,
            ack_mask: self.request.target_mask,
            invalidation_count: 1,
        })
    }

    pub fn released(&mut self, receipt: GenerationRetirementReceipt) -> Result<(), ReclaimError> {
        if self.stage != ReclaimStage::Authorized
            || receipt.root_physical != self.request.root_physical
            || receipt.retired_generation != self.request.retired_generation
            || receipt.active_generation != self.request.active_generation
            || receipt.target_mask != self.request.target_mask
            || receipt.ack_mask != self.request.target_mask
            || receipt.invalidation_count != 1
        {
            return Err(ReclaimError::Acknowledgement);
        }
        self.stage = ReclaimStage::Released;
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MultiApStage {
    Empty,
    Reserved,
    Prepared,
    PartialStarted,
    PartialTimedOut,
    PartialParked,
    PartialReleased,
    RetryReserved,
    RetryPrepared,
    Online,
    Exercised,
    Quiesced,
    Parked,
    Validated,
    Released,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MultiApReceipt {
    pub target_mask: u64,
    pub started_mask: u64,
    pub online_mask: u64,
    pub quiesced_mask: u64,
    pub parked_mask: u64,
    pub validated_mask: u64,
    pub released_mask: u64,
    pub timeout_count: u32,
    pub retry_count: u32,
    pub partial_rollback_count: u32,
}

pub struct MultiApTransaction {
    stage: MultiApStage,
    started_mask: u64,
    online_mask: u64,
    quiesced_mask: u64,
    parked_mask: u64,
    validated_mask: u64,
    released_mask: u64,
    timeout_count: u32,
    retry_count: u32,
    partial_rollback_count: u32,
}

impl MultiApTransaction {
    pub const fn new() -> Self {
        Self {
            stage: MultiApStage::Empty,
            started_mask: 0,
            online_mask: 0,
            quiesced_mask: 0,
            parked_mask: 0,
            validated_mask: 0,
            released_mask: 0,
            timeout_count: 0,
            retry_count: 0,
            partial_rollback_count: 0,
        }
    }

    pub const fn stage(&self) -> MultiApStage {
        self.stage
    }

    fn require_mask(mask: u64, allow_partial: bool) -> Result<(), Error> {
        if mask == 0 || mask & !TARGET_CPU_MASK != 0 || (!allow_partial && mask != TARGET_CPU_MASK)
        {
            return Err(Error::Target);
        }
        Ok(())
    }

    pub fn reserve(&mut self) -> Result<(), Error> {
        if self.stage != MultiApStage::Empty {
            return Err(Error::Transition);
        }
        self.stage = MultiApStage::Reserved;
        Ok(())
    }

    pub fn prepare(&mut self) -> Result<(), Error> {
        if self.stage != MultiApStage::Reserved {
            return Err(Error::Transition);
        }
        self.stage = MultiApStage::Prepared;
        Ok(())
    }

    pub fn partial_started(&mut self, mask: u64) -> Result<(), Error> {
        Self::require_mask(mask, true)?;
        if self.stage != MultiApStage::Prepared || mask != PARTIAL_STARTED_MASK {
            return Err(Error::Transition);
        }
        self.started_mask = mask;
        self.stage = MultiApStage::PartialStarted;
        Ok(())
    }

    pub fn partial_timeout(&mut self, offline_apic_id: u32) -> Result<(), Error> {
        if self.stage != MultiApStage::PartialStarted
            || offline_apic_id != OFFLINE_APIC_ID
            || local_target_mask(offline_apic_id) != Some(OFFLINE_CPU_MASK)
        {
            return Err(Error::Target);
        }
        self.timeout_count = self.timeout_count.checked_add(1).ok_or(Error::Counter)?;
        self.stage = MultiApStage::PartialTimedOut;
        Ok(())
    }

    pub fn partial_parked(&mut self, mask: u64) -> Result<(), Error> {
        if self.stage != MultiApStage::PartialTimedOut || mask != self.started_mask {
            return Err(Error::Rollback);
        }
        self.parked_mask = mask;
        self.stage = MultiApStage::PartialParked;
        Ok(())
    }

    pub fn partial_released(&mut self, released_mask: u64) -> Result<(), Error> {
        if self.stage != MultiApStage::PartialParked || released_mask != TARGET_CPU_MASK {
            return Err(Error::Rollback);
        }
        self.released_mask = released_mask;
        self.partial_rollback_count = self
            .partial_rollback_count
            .checked_add(1)
            .ok_or(Error::Counter)?;
        self.stage = MultiApStage::PartialReleased;
        Ok(())
    }

    pub fn retry_reserve(&mut self) -> Result<(), Error> {
        if self.stage != MultiApStage::PartialReleased {
            return Err(Error::Transition);
        }
        self.started_mask = 0;
        self.online_mask = 0;
        self.quiesced_mask = 0;
        self.parked_mask = 0;
        self.validated_mask = 0;
        self.released_mask = 0;
        self.retry_count = self.retry_count.checked_add(1).ok_or(Error::Counter)?;
        self.stage = MultiApStage::RetryReserved;
        Ok(())
    }

    pub fn retry_prepare(&mut self) -> Result<(), Error> {
        if self.stage != MultiApStage::RetryReserved {
            return Err(Error::Transition);
        }
        self.stage = MultiApStage::RetryPrepared;
        Ok(())
    }

    pub fn all_online(&mut self, started_mask: u64, online_mask: u64) -> Result<(), Error> {
        Self::require_mask(started_mask, false)?;
        if self.stage != MultiApStage::RetryPrepared || online_mask != started_mask {
            return Err(Error::Transition);
        }
        self.started_mask = started_mask;
        self.online_mask = online_mask;
        self.stage = MultiApStage::Online;
        Ok(())
    }

    pub fn exercised(&mut self, ack_mask: u64) -> Result<(), Error> {
        if self.stage != MultiApStage::Online || ack_mask != TARGET_CPU_MASK {
            return Err(Error::Target);
        }
        self.stage = MultiApStage::Exercised;
        Ok(())
    }

    pub fn quiesced(&mut self, mask: u64) -> Result<(), Error> {
        if self.stage != MultiApStage::Exercised || mask != TARGET_CPU_MASK {
            return Err(Error::Transition);
        }
        self.quiesced_mask = mask;
        self.stage = MultiApStage::Quiesced;
        Ok(())
    }

    pub fn parked(&mut self, mask: u64) -> Result<(), Error> {
        if self.stage != MultiApStage::Quiesced || mask != self.started_mask {
            return Err(Error::Rollback);
        }
        self.parked_mask = mask;
        self.stage = MultiApStage::Parked;
        Ok(())
    }

    pub fn validated(&mut self, mask: u64) -> Result<(), Error> {
        if self.stage != MultiApStage::Parked || mask != TARGET_CPU_MASK {
            return Err(Error::Transition);
        }
        self.validated_mask = mask;
        self.stage = MultiApStage::Validated;
        Ok(())
    }

    pub fn released(&mut self, mask: u64) -> Result<MultiApReceipt, Error> {
        if self.stage != MultiApStage::Validated || mask != TARGET_CPU_MASK {
            return Err(Error::Transition);
        }
        self.released_mask = mask;
        self.stage = MultiApStage::Released;
        Ok(MultiApReceipt {
            target_mask: TARGET_CPU_MASK,
            started_mask: self.started_mask,
            online_mask: self.online_mask,
            quiesced_mask: self.quiesced_mask,
            parked_mask: self.parked_mask,
            validated_mask: self.validated_mask,
            released_mask: self.released_mask,
            timeout_count: self.timeout_count,
            retry_count: self.retry_count,
            partial_rollback_count: self.partial_rollback_count,
        })
    }
}

impl Default for MultiApTransaction {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum MultiReclaimStage {
    Prepared,
    Armed,
    TimedOut,
    Acknowledging,
    Authorized,
    Released,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MultiGenerationRetirementReceipt {
    pub retired_generation: u64,
    pub active_generation: u64,
    pub target_mask: u64,
    pub ack_mask: u64,
    pub invalidation_count: u64,
    pub root_checksum: u64,
    pub old_frame_checksum: u64,
    pub new_frame_checksum: u64,
}

pub struct MultiDeferredReclaim {
    requests: [ShootdownRequest; AP_COUNT],
    stage: MultiReclaimStage,
    ack_mask: u64,
    invalidation_count: u64,
}

fn aggregate_fold_u64(mut checksum: u64, value: u64) -> u64 {
    for byte in value.to_le_bytes() {
        checksum ^= u64::from(byte);
        checksum = checksum.wrapping_mul(AGGREGATE_FNV_PRIME);
    }
    checksum
}

fn finish_aggregate_checksum(checksum: u64, domain: u64) -> u64 {
    if checksum == 0 { domain } else { checksum }
}

fn aggregate_request_checksums(requests: &[ShootdownRequest; AP_COUNT]) -> (u64, u64, u64) {
    let mut roots = AGGREGATE_FNV_OFFSET ^ AGGREGATE_ROOT_DOMAIN;
    let mut old_frames = AGGREGATE_FNV_OFFSET ^ AGGREGATE_OLD_FRAME_DOMAIN;
    let mut new_frames = AGGREGATE_FNV_OFFSET ^ AGGREGATE_NEW_FRAME_DOMAIN;
    for request in requests {
        roots = aggregate_fold_u64(
            aggregate_fold_u64(roots, request.target_mask),
            request.root_physical,
        );
        old_frames = aggregate_fold_u64(
            aggregate_fold_u64(old_frames, request.target_mask),
            request.old_frame_physical,
        );
        new_frames = aggregate_fold_u64(
            aggregate_fold_u64(new_frames, request.target_mask),
            request.new_frame_physical,
        );
    }
    (
        finish_aggregate_checksum(roots, AGGREGATE_ROOT_DOMAIN),
        finish_aggregate_checksum(old_frames, AGGREGATE_OLD_FRAME_DOMAIN),
        finish_aggregate_checksum(new_frames, AGGREGATE_NEW_FRAME_DOMAIN),
    )
}

impl MultiDeferredReclaim {
    pub fn new(requests: [ShootdownRequest; AP_COUNT]) -> Result<Self, ReclaimError> {
        for (index, request) in requests.iter().enumerate() {
            validate_shootdown_request_for_target(
                request,
                request.root_physical,
                0,
                EXPECTED_APIC_IDS[index],
            )
            .map_err(|_| ReclaimError::Request)?;
        }
        Ok(Self {
            requests,
            stage: MultiReclaimStage::Prepared,
            ack_mask: 0,
            invalidation_count: 0,
        })
    }

    pub fn arm(&mut self) -> Result<(), ReclaimError> {
        if !matches!(
            self.stage,
            MultiReclaimStage::Prepared | MultiReclaimStage::TimedOut
        ) {
            return Err(ReclaimError::State);
        }
        self.stage = MultiReclaimStage::Armed;
        Ok(())
    }

    pub fn timeout(&mut self, offline_mask: u64) -> Result<(), ReclaimError> {
        if self.stage != MultiReclaimStage::Armed || offline_mask != OFFLINE_CPU_MASK {
            return Err(ReclaimError::State);
        }
        self.stage = MultiReclaimStage::TimedOut;
        Ok(())
    }

    pub fn acknowledge(
        &mut self,
        target_apic_id: u32,
        snapshot: &ShootdownSnapshot,
    ) -> Result<(), ReclaimError> {
        if !matches!(
            self.stage,
            MultiReclaimStage::Armed | MultiReclaimStage::Acknowledging
        ) {
            return Err(ReclaimError::State);
        }
        let index = EXPECTED_APIC_IDS
            .iter()
            .position(|apic_id| *apic_id == target_apic_id)
            .ok_or(ReclaimError::Acknowledgement)?;
        let local_mask = local_target_mask(target_apic_id).ok_or(ReclaimError::Acknowledgement)?;
        if self.ack_mask & local_mask != 0 {
            return Err(ReclaimError::Duplicate);
        }
        validate_shootdown_ack_for_target(snapshot, &self.requests[index], target_apic_id)
            .map_err(|_| ReclaimError::Acknowledgement)?;
        self.ack_mask |= local_mask;
        self.invalidation_count = self
            .invalidation_count
            .checked_add(snapshot.invalidation_count)
            .ok_or(ReclaimError::Acknowledgement)?;
        self.stage = MultiReclaimStage::Acknowledging;
        Ok(())
    }

    pub fn authorize(&mut self) -> Result<MultiGenerationRetirementReceipt, ReclaimError> {
        if self.stage != MultiReclaimStage::Acknowledging
            || self.ack_mask != TARGET_CPU_MASK
            || self.invalidation_count != AP_COUNT as u64
        {
            return Err(ReclaimError::State);
        }
        self.stage = MultiReclaimStage::Authorized;
        Ok(self.receipt())
    }

    fn receipt(&self) -> MultiGenerationRetirementReceipt {
        let (root_checksum, old_frame_checksum, new_frame_checksum) =
            aggregate_request_checksums(&self.requests);
        MultiGenerationRetirementReceipt {
            retired_generation: RETIRED_GENERATION,
            active_generation: ACTIVE_GENERATION,
            target_mask: TARGET_CPU_MASK,
            ack_mask: self.ack_mask,
            invalidation_count: self.invalidation_count,
            root_checksum,
            old_frame_checksum,
            new_frame_checksum,
        }
    }

    pub fn released(
        &mut self,
        receipt: MultiGenerationRetirementReceipt,
    ) -> Result<(), ReclaimError> {
        if self.stage != MultiReclaimStage::Authorized || receipt != self.receipt() {
            return Err(ReclaimError::Acknowledgement);
        }
        self.stage = MultiReclaimStage::Released;
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    ResourceAddress,
    PageRole,
    MailboxShape,
    Capability,
    RequestState,
    Operation,
    Vector,
    Target,
    Checksum,
    Attempt,
    Sequence,
    Payload,
    PanicState,
    Counter,
    Result,
    Idt,
    Transition,
    Rollback,
}

#[cfg(not(target_os = "none"))]
impl Error {
    pub const fn label(self) -> &'static str {
        match self {
            Self::ResourceAddress => "ipi_resource_address",
            Self::PageRole => "ipi_page_role",
            Self::MailboxShape => "ipi_mailbox_shape",
            Self::Capability => "ipi_capability",
            Self::RequestState => "ipi_request_state",
            Self::Operation => "ipi_operation",
            Self::Vector => "ipi_vector",
            Self::Target => "ipi_target",
            Self::Checksum => "ipi_checksum",
            Self::Attempt => "ipi_attempt",
            Self::Sequence => "ipi_sequence",
            Self::Payload => "ipi_payload",
            Self::PanicState => "ipi_panic_state",
            Self::Counter => "ipi_counter",
            Self::Result => "ipi_result",
            Self::Idt => "ipi_idt",
            Self::Transition => "ipi_transition",
            Self::Rollback => "ipi_rollback",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Request {
    pub capability_high: u64,
    pub capability_low: u64,
    pub attempt: u64,
    pub sequence: u64,
    pub operation: u32,
    pub vector: u32,
    pub target_apic_id: u32,
    pub status: u32,
    pub payload: u64,
    pub checksum: u64,
}

impl Request {
    #[inline(always)]
    pub const fn canonical(
        attempt: u64,
        sequence: u64,
        operation: Operation,
        target_apic_id: u32,
    ) -> Self {
        let mut value = Self {
            capability_high: CAPABILITY_HIGH,
            capability_low: CAPABILITY_LOW,
            attempt,
            sequence,
            operation: operation as u32,
            vector: operation.vector() as u32,
            target_apic_id,
            status: REQUEST_ARMED,
            payload: operation.payload(),
            checksum: 0,
        };
        value.checksum = request_checksum(&value);
        value
    }

    #[inline(always)]
    pub const fn canonical_call(
        attempt: u64,
        sequence: u64,
        target_apic_id: u32,
        payload: CallPayload,
    ) -> Self {
        let mut value = Self::canonical(attempt, sequence, Operation::CallFunction, target_apic_id);
        value.payload = payload.token();
        value.checksum = request_checksum(&value);
        value
    }
}

pub const fn request_checksum(request: &Request) -> u64 {
    REQUEST_CHECKSUM_SEED
        ^ request.capability_high
        ^ request.capability_low
        ^ request.attempt
        ^ request.sequence
        ^ request.payload
        ^ request.operation as u64
        ^ request.vector as u64
        ^ request.target_apic_id as u64
}

pub const fn response_checksum(snapshot: &IpiSnapshot) -> u64 {
    RESPONSE_CHECKSUM_SEED
        ^ snapshot.ack_attempt
        ^ snapshot.ack_sequence
        ^ snapshot.result
        ^ snapshot.last_accepted_sequence
        ^ snapshot.ack_operation as u64
        ^ snapshot.ack_status as u64
        ^ snapshot.ack_error as u64
        ^ snapshot.delivery_count as u64
        ^ snapshot.accepted_count as u64
        ^ snapshot.denied_count as u64
}

#[cfg(not(target_os = "none"))]
fn payload_valid(operation: Operation, payload: u64) -> bool {
    if operation == Operation::CallFunction {
        CallPayload::from_token(payload).is_some()
    } else {
        payload == operation.payload()
    }
}

#[cfg(not(target_os = "none"))]
pub fn validate_request(
    request: &Request,
    handler_operation: Operation,
    target_apic_id: u32,
    prior_ack_attempt: u64,
    last_accepted_sequence: u64,
    panic_latched: bool,
) -> Result<(), u32> {
    if request.status != REQUEST_ARMED {
        return Err(ERROR_REQUEST_STATE);
    }
    if request.capability_high != CAPABILITY_HIGH || request.capability_low != CAPABILITY_LOW {
        return Err(ERROR_CAPABILITY);
    }
    if request.attempt != prior_ack_attempt.wrapping_add(1) {
        return Err(ERROR_ATTEMPT);
    }
    if request.operation != handler_operation as u32 {
        return Err(ERROR_OPERATION);
    }
    if request.vector != u32::from(handler_operation.vector()) {
        return Err(ERROR_VECTOR);
    }
    if request.target_apic_id != target_apic_id {
        return Err(ERROR_TARGET);
    }
    if request.checksum != request_checksum(request) {
        return Err(ERROR_CHECKSUM);
    }
    if request.sequence == last_accepted_sequence {
        return Err(ERROR_DUPLICATE_SEQUENCE);
    }
    if request.sequence < last_accepted_sequence {
        return Err(ERROR_STALE_SEQUENCE);
    }
    if request.sequence != last_accepted_sequence.wrapping_add(1) {
        return Err(ERROR_STALE_SEQUENCE);
    }
    if !payload_valid(handler_operation, request.payload) {
        return Err(ERROR_PAYLOAD);
    }
    if panic_latched && !matches!(handler_operation, Operation::Diagnostic | Operation::Stop) {
        return Err(ERROR_PANIC_LATCHED);
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct HandlerLayout {
    pub fault: u64,
    pub reschedule: u64,
    pub shootdown: u64,
    pub call_function: u64,
    pub diagnostic: u64,
    pub panic: u64,
    pub stop: u64,
    pub apic_error: u64,
    pub spurious: u64,
}

impl HandlerLayout {
    fn all(self) -> [u64; 9] {
        [
            self.fault,
            self.reschedule,
            self.shootdown,
            self.call_function,
            self.diagnostic,
            self.panic,
            self.stop,
            self.apic_error,
            self.spurious,
        ]
    }

    const fn for_operation(self, operation: Operation) -> u64 {
        match operation {
            Operation::Reschedule => self.reschedule,
            Operation::Shootdown => self.shootdown,
            Operation::CallFunction => self.call_function,
            Operation::Diagnostic => self.diagnostic,
            Operation::Panic => self.panic,
            Operation::Stop => self.stop,
        }
    }
}

fn put_u16(page: &mut [u8; PAGE_BYTES as usize], offset: usize, value: u16) {
    page[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
}

fn put_u32(page: &mut [u8; PAGE_BYTES as usize], offset: usize, value: u32) {
    page[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
}

fn write_idt_gate(page: &mut [u8; PAGE_BYTES as usize], vector: u8, handler: u64, ist: u8) {
    let offset = usize::from(vector) * 16;
    put_u16(page, offset, handler as u16);
    put_u16(page, offset + 2, smp_runtime::KERNEL_CODE_SELECTOR as u16);
    page[offset + 4] = ist;
    page[offset + 5] = 0x8e;
    put_u16(page, offset + 6, (handler >> 16) as u16);
    put_u32(page, offset + 8, (handler >> 32) as u32);
}

pub fn build_idt_page(
    layout: smp_runtime::ResourceLayout,
    handlers: HandlerLayout,
) -> Result<[u8; PAGE_BYTES as usize], Error> {
    let trampoline_end = layout
        .trampoline()
        .checked_add(PAGE_BYTES)
        .ok_or(Error::ResourceAddress)?;
    if handlers
        .all()
        .into_iter()
        .any(|handler| handler < layout.trampoline() || handler >= trampoline_end)
    {
        return Err(Error::ResourceAddress);
    }
    let mut page = [0u8; PAGE_BYTES as usize];
    for vector in smp_runtime::EXCEPTION_VECTORS {
        write_idt_gate(
            &mut page,
            vector,
            handlers.fault,
            if vector == 8 { 2 } else { 1 },
        );
    }
    write_idt_gate(&mut page, 64, handlers.fault, 1);
    for operation in Operation::ALL {
        write_idt_gate(
            &mut page,
            operation.vector(),
            handlers.for_operation(operation),
            1,
        );
    }
    for vector in 230..=239 {
        write_idt_gate(&mut page, vector, handlers.fault, 1);
    }
    write_idt_gate(&mut page, 240, handlers.apic_error, 1);
    write_idt_gate(&mut page, 255, handlers.spurious, 1);
    Ok(page)
}

pub fn validate_final(
    snapshot: &IpiSnapshot,
    expected_target_apic_id: u32,
    timeout_count: u32,
) -> Result<(), Error> {
    if snapshot.magic != EXTENSION_MAGIC
        || snapshot.version != EXTENSION_VERSION
        || snapshot.service_state != SERVICE_STATE_QUIESCED
    {
        return Err(Error::MailboxShape);
    }
    if snapshot.capability_high != CAPABILITY_HIGH || snapshot.capability_low != CAPABILITY_LOW {
        return Err(Error::Capability);
    }
    if snapshot.request_target_apic_id != expected_target_apic_id
        || snapshot.request_status != REQUEST_IDLE
    {
        return Err(Error::Target);
    }
    if snapshot.ack_attempt != LIVE_FINAL_ATTEMPT {
        return Err(Error::Attempt);
    }
    if snapshot.ack_sequence != LIVE_FINAL_SEQUENCE
        || snapshot.last_accepted_sequence != LIVE_FINAL_SEQUENCE
    {
        return Err(Error::Sequence);
    }
    if snapshot.ack_operation != Operation::Stop as u32
        || snapshot.ack_status != ACK_ACCEPTED
        || snapshot.ack_error != ERROR_NONE
        || snapshot.result != RESULT_STOP_QUIESCED
    {
        return Err(Error::Result);
    }
    if snapshot.delivery_count != LIVE_DELIVERY_COUNT
        || snapshot.eoi_count != LIVE_DELIVERY_COUNT
        || snapshot.accepted_count != LIVE_ACCEPTED_COUNT
        || snapshot.denied_count != LIVE_DENIED_COUNT
        || timeout_count > LIVE_TIMEOUT_COUNT
        || snapshot.reschedule_count != 0
        || snapshot.shootdown_count != 1
        || snapshot.call_function_count != 0
        || snapshot.diagnostic_count != 1
        || snapshot.panic_count != 0
        || snapshot.stop_count != 1
        || snapshot.spurious_count != 0
        || snapshot.apic_error_count != 0
    {
        return Err(Error::Counter);
    }
    if snapshot.panic_latched != 0 {
        return Err(Error::PanicState);
    }
    if snapshot.response_checksum != response_checksum(snapshot) {
        return Err(Error::Checksum);
    }
    let request = ShootdownRequest {
        root_physical: snapshot.shootdown.root_physical,
        virtual_address: snapshot.shootdown.virtual_address,
        retired_generation: snapshot.shootdown.retired_generation,
        active_generation: snapshot.shootdown.active_generation,
        target_mask: snapshot.shootdown.target_mask,
        old_frame_physical: snapshot.shootdown.old_frame_physical,
        new_frame_physical: snapshot.shootdown.new_frame_physical,
        checksum: snapshot.shootdown.request_checksum,
    };
    validate_shootdown_request_for_target(
        &request,
        request.root_physical,
        0,
        expected_target_apic_id,
    )
    .map_err(|_| Error::Result)?;
    validate_shootdown_ack_for_target(&snapshot.shootdown, &request, expected_target_apic_id)?;
    if snapshot.shootdown.timeout_count != timeout_count
        || snapshot.shootdown.reclaim_state != RECLAIM_RELEASED
    {
        return Err(Error::Counter);
    }
    Ok(())
}

pub fn validate_scheduler_final(
    snapshot: &IpiSnapshot,
    expected_target_apic_id: u32,
    timeout_count: u32,
) -> Result<(), Error> {
    if snapshot.ack_attempt != 7
        || snapshot.ack_sequence != 6
        || snapshot.last_accepted_sequence != 6
        || snapshot.delivery_count != 7
        || snapshot.eoi_count != 7
        || snapshot.accepted_count != 6
        || snapshot.denied_count != 1
        || snapshot.reschedule_count != 0
        || snapshot.shootdown_count != 1
        || snapshot.call_function_count != 3
        || snapshot.diagnostic_count != 1
        || snapshot.panic_count != 0
        || snapshot.stop_count != 1
        || snapshot.response_checksum != response_checksum(snapshot)
    {
        return Err(Error::Counter);
    }
    let mut normalized = *snapshot;
    normalized.ack_attempt = LIVE_FINAL_ATTEMPT;
    normalized.ack_sequence = LIVE_FINAL_SEQUENCE;
    normalized.last_accepted_sequence = LIVE_FINAL_SEQUENCE;
    normalized.delivery_count = LIVE_DELIVERY_COUNT;
    normalized.eoi_count = LIVE_DELIVERY_COUNT;
    normalized.accepted_count = LIVE_ACCEPTED_COUNT;
    normalized.denied_count = LIVE_DENIED_COUNT;
    normalized.call_function_count = 0;
    normalized.response_checksum = response_checksum(&normalized);
    validate_final(&normalized, expected_target_apic_id, timeout_count)
}

pub fn validate_ap_worker_final(
    snapshot: &IpiSnapshot,
    expected_target_apic_id: u32,
    timeout_count: u32,
) -> Result<(), Error> {
    if snapshot.ack_attempt != 8
        || snapshot.ack_sequence != 7
        || snapshot.last_accepted_sequence != 7
        || snapshot.delivery_count != 8
        || snapshot.eoi_count != 8
        || snapshot.accepted_count != 7
        || snapshot.denied_count != 1
        || snapshot.reschedule_count != 0
        || snapshot.shootdown_count != 1
        || snapshot.call_function_count != 4
        || snapshot.diagnostic_count != 1
        || snapshot.panic_count != 0
        || snapshot.stop_count != 1
        || snapshot.response_checksum != response_checksum(snapshot)
    {
        return Err(Error::Counter);
    }
    let mut normalized = *snapshot;
    normalized.ack_attempt = LIVE_FINAL_ATTEMPT;
    normalized.ack_sequence = LIVE_FINAL_SEQUENCE;
    normalized.last_accepted_sequence = LIVE_FINAL_SEQUENCE;
    normalized.delivery_count = LIVE_DELIVERY_COUNT;
    normalized.eoi_count = LIVE_DELIVERY_COUNT;
    normalized.accepted_count = LIVE_ACCEPTED_COUNT;
    normalized.denied_count = LIVE_DENIED_COUNT;
    normalized.call_function_count = 0;
    normalized.response_checksum = response_checksum(&normalized);
    validate_final(&normalized, expected_target_apic_id, timeout_count)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TransactionStage {
    Empty,
    Reserved,
    Prepared,
    StartupSent,
    Online,
    Exercised,
    Quiesced,
    Parked,
    Validated,
    Released,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RollbackReceipt {
    pub failed_at: TransactionStage,
    pub ap_parked: bool,
    pub capability_revoked: bool,
    pub mmio_revoked: bool,
    pub resources_zeroed: bool,
    pub resources_released: bool,
}

pub struct IpiTransaction {
    stage: TransactionStage,
    ap_started: bool,
}

impl IpiTransaction {
    pub const fn new() -> Self {
        Self {
            stage: TransactionStage::Empty,
            ap_started: false,
        }
    }

    pub const fn stage(&self) -> TransactionStage {
        self.stage
    }

    fn advance(&mut self, expected: TransactionStage, next: TransactionStage) -> Result<(), Error> {
        if self.stage != expected {
            return Err(Error::Transition);
        }
        self.stage = next;
        if next == TransactionStage::StartupSent {
            self.ap_started = true;
        }
        Ok(())
    }

    pub fn reserve(&mut self) -> Result<(), Error> {
        self.advance(TransactionStage::Empty, TransactionStage::Reserved)
    }

    pub fn prepare(&mut self) -> Result<(), Error> {
        self.advance(TransactionStage::Reserved, TransactionStage::Prepared)
    }

    pub fn startup_sent(&mut self) -> Result<(), Error> {
        self.advance(TransactionStage::Prepared, TransactionStage::StartupSent)
    }

    pub fn online(&mut self) -> Result<(), Error> {
        self.advance(TransactionStage::StartupSent, TransactionStage::Online)
    }

    pub fn exercised(&mut self) -> Result<(), Error> {
        self.advance(TransactionStage::Online, TransactionStage::Exercised)
    }

    pub fn quiesced(&mut self) -> Result<(), Error> {
        self.advance(TransactionStage::Exercised, TransactionStage::Quiesced)
    }

    pub fn parked(&mut self) -> Result<(), Error> {
        self.advance(TransactionStage::Quiesced, TransactionStage::Parked)
    }

    pub fn validated(&mut self) -> Result<(), Error> {
        self.advance(TransactionStage::Parked, TransactionStage::Validated)
    }

    pub fn released(&mut self) -> Result<(), Error> {
        self.advance(TransactionStage::Validated, TransactionStage::Released)
    }

    pub fn rollback(&mut self, park_succeeded: bool) -> Result<RollbackReceipt, Error> {
        let failed_at = self.stage;
        if self.ap_started && !park_succeeded {
            return Err(Error::Rollback);
        }
        self.stage = TransactionStage::Released;
        Ok(RollbackReceipt {
            failed_at,
            ap_parked: !self.ap_started || park_succeeded,
            capability_revoked: true,
            mmio_revoked: true,
            resources_zeroed: true,
            resources_released: true,
        })
    }
}

impl Default for IpiTransaction {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn response() -> IpiSnapshot {
        let mut value = IpiSnapshot {
            magic: EXTENSION_MAGIC,
            version: EXTENSION_VERSION,
            service_state: SERVICE_STATE_QUIESCED,
            capability_high: CAPABILITY_HIGH,
            capability_low: CAPABILITY_LOW,
            request_capability_high: CAPABILITY_HIGH,
            request_capability_low: CAPABILITY_LOW,
            request_attempt: LIVE_FINAL_ATTEMPT,
            request_sequence: LIVE_FINAL_SEQUENCE,
            payload: STOP_TOKEN,
            request_checksum: 0,
            ack_attempt: LIVE_FINAL_ATTEMPT,
            ack_sequence: LIVE_FINAL_SEQUENCE,
            result: RESULT_STOP_QUIESCED,
            response_checksum: 0,
            last_accepted_sequence: LIVE_FINAL_SEQUENCE,
            request_operation: Operation::Stop as u32,
            request_vector: Operation::Stop.vector() as u32,
            request_target_apic_id: 1,
            request_status: REQUEST_IDLE,
            ack_operation: Operation::Stop as u32,
            ack_status: ACK_ACCEPTED,
            ack_error: ERROR_NONE,
            delivery_count: LIVE_DELIVERY_COUNT,
            eoi_count: LIVE_DELIVERY_COUNT,
            accepted_count: LIVE_ACCEPTED_COUNT,
            denied_count: LIVE_DENIED_COUNT,
            reschedule_count: 0,
            shootdown_count: 1,
            call_function_count: 0,
            diagnostic_count: 1,
            stop_count: 1,
            panic_count: 0,
            panic_latched: 0,
            spurious_count: 0,
            apic_error_count: 0,
            shootdown: ShootdownSnapshot {
                magic: SHOOTDOWN_MAGIC,
                version: SHOOTDOWN_VERSION,
                state: SHOOTDOWN_STATE_ACKED,
                error: ERROR_NONE,
                root_physical: PAGE_BYTES,
                virtual_address: PROBE_VIRTUAL_ADDRESS,
                retired_generation: RETIRED_GENERATION,
                active_generation: ACTIVE_GENERATION,
                target_mask: local_target_mask(1).unwrap(),
                ack_mask: local_target_mask(1).unwrap(),
                old_frame_physical: 2 * PAGE_BYTES,
                new_frame_physical: 3 * PAGE_BYTES,
                observed_before: OLD_FRAME_VALUE,
                observed_after: NEW_FRAME_VALUE,
                invalidation_count: 1,
                request_checksum: 0,
                response_checksum: 0,
                last_ack_generation: ACTIVE_GENERATION,
                timeout_count: LIVE_TIMEOUT_COUNT,
                reclaim_state: RECLAIM_RELEASED,
            },
        };
        let request =
            Request::canonical(LIVE_FINAL_ATTEMPT, LIVE_FINAL_SEQUENCE, Operation::Stop, 1);
        value.request_checksum = request.checksum;
        let shootdown_request =
            ShootdownRequest::canonical(PAGE_BYTES, 2 * PAGE_BYTES, 3 * PAGE_BYTES);
        value.shootdown.request_checksum = shootdown_request.checksum;
        value.shootdown.response_checksum = shootdown_response_checksum(&value.shootdown);
        value.response_checksum = response_checksum(&value);
        value
    }

    #[test]
    fn mailbox_offsets_are_frozen() {
        assert_eq!(EXTENSION_BASE_OFFSET, 352);
        assert_eq!(MAILBOX_BYTES, 696);
        assert_eq!(REQUEST_ATTEMPT_OFFSET, 400);
        assert_eq!(RESPONSE_CHECKSUM_OFFSET, 456);
        assert_eq!(APIC_ERROR_COUNT_OFFSET, 548);
        assert_eq!(SHOOTDOWN_MAGIC_OFFSET, 552);
        assert_eq!(SHOOTDOWN_RECLAIM_STATE_OFFSET, 692);
    }

    #[test]
    fn operations_own_six_contiguous_vectors_and_allowlisted_payloads() {
        for (index, operation) in Operation::ALL.into_iter().enumerate() {
            assert_eq!(operation.vector(), 0xe0 + index as u8);
            assert_eq!(Operation::from_u32(operation as u32), Some(operation));
            assert_ne!(operation.result(), 0);
        }
        assert_eq!(Operation::from_u32(0), None);
        assert_eq!(Operation::from_u32(7), None);
    }

    #[test]
    fn canonical_requests_bind_every_authority_field() {
        let request = Request::canonical(4, 3, Operation::CallFunction, 1);
        assert_eq!(request.checksum, request_checksum(&request));
        for mutate in 0..9 {
            let mut hostile = request;
            match mutate {
                0 => hostile.capability_high ^= 1,
                1 => hostile.capability_low ^= 1,
                2 => hostile.attempt ^= 1,
                3 => hostile.sequence ^= 1,
                4 => hostile.operation ^= 1,
                5 => hostile.vector ^= 1,
                6 => hostile.target_apic_id ^= 1,
                7 => hostile.payload ^= 1,
                _ => hostile.checksum ^= 1,
            }
            assert_ne!(hostile.checksum, request_checksum(&hostile));
        }
    }

    #[test]
    fn call_function_accepts_only_three_typed_payloads() {
        for payload in CallPayload::ALL {
            let request = Request::canonical_call(1, 1, 1, payload);
            assert_eq!(request.payload, payload.token());
            assert_eq!(
                validate_request(&request, Operation::CallFunction, 1, 0, 0, false),
                Ok(())
            );
        }
        let mut forged = Request::canonical_call(1, 1, 1, CallPayload::Noop);
        forged.payload = 0xdead_beef;
        forged.checksum = request_checksum(&forged);
        assert_eq!(
            validate_request(&forged, Operation::CallFunction, 1, 0, 0, false),
            Err(ERROR_PAYLOAD)
        );
    }

    #[test]
    fn request_validation_rejects_capability_replay_routing_and_payload_faults() {
        let valid = Request::canonical(2, 2, Operation::Shootdown, 1);
        assert_eq!(
            validate_request(&valid, Operation::Shootdown, 1, 1, 1, false),
            Ok(())
        );
        let cases: [(Request, u32); 10] = [
            (
                Request {
                    capability_high: 0,
                    ..valid
                },
                ERROR_CAPABILITY,
            ),
            (
                Request {
                    status: REQUEST_IDLE,
                    ..valid
                },
                ERROR_REQUEST_STATE,
            ),
            (
                Request {
                    attempt: 3,
                    ..valid
                },
                ERROR_ATTEMPT,
            ),
            (
                Request {
                    operation: 3,
                    ..valid
                },
                ERROR_OPERATION,
            ),
            (
                Request {
                    vector: 0xe2,
                    ..valid
                },
                ERROR_VECTOR,
            ),
            (
                Request {
                    target_apic_id: 2,
                    ..valid
                },
                ERROR_TARGET,
            ),
            (
                Request {
                    checksum: 0,
                    ..valid
                },
                ERROR_CHECKSUM,
            ),
            (
                Request {
                    sequence: 1,
                    checksum: request_checksum(&Request {
                        sequence: 1,
                        ..valid
                    }),
                    ..valid
                },
                ERROR_DUPLICATE_SEQUENCE,
            ),
            (
                Request {
                    sequence: 0,
                    checksum: request_checksum(&Request {
                        sequence: 0,
                        ..valid
                    }),
                    ..valid
                },
                ERROR_STALE_SEQUENCE,
            ),
            (
                Request {
                    payload: 3,
                    checksum: request_checksum(&Request {
                        payload: 3,
                        ..valid
                    }),
                    ..valid
                },
                ERROR_PAYLOAD,
            ),
        ];
        for (hostile, error) in cases {
            assert_eq!(
                validate_request(&hostile, Operation::Shootdown, 1, 1, 1, false),
                Err(error)
            );
        }
    }

    #[test]
    fn panic_latch_allows_only_diagnostic_and_stop() {
        for operation in Operation::ALL {
            let request = Request::canonical(2, 2, operation, 1);
            let result = validate_request(&request, operation, 1, 1, 1, true);
            if matches!(operation, Operation::Diagnostic | Operation::Stop) {
                assert_eq!(result, Ok(()));
            } else {
                assert_eq!(result, Err(ERROR_PANIC_LATCHED));
            }
        }
    }

    #[test]
    fn final_live_shape_requires_exact_counts_and_timeout() {
        let valid = response();
        assert_eq!(validate_final(&valid, 1, LIVE_TIMEOUT_COUNT), Ok(()));
        let mut second = valid;
        second.request_target_apic_id = 2;
        second.request_checksum =
            Request::canonical(LIVE_FINAL_ATTEMPT, LIVE_FINAL_SEQUENCE, Operation::Stop, 2)
                .checksum;
        second.shootdown.target_mask = local_target_mask(2).unwrap();
        second.shootdown.ack_mask = local_target_mask(2).unwrap();
        second.shootdown.request_checksum = ShootdownRequest::canonical_for_target(
            2,
            second.shootdown.root_physical,
            second.shootdown.old_frame_physical,
            second.shootdown.new_frame_physical,
        )
        .checksum;
        second.shootdown.response_checksum = shootdown_response_checksum(&second.shootdown);
        second.response_checksum = response_checksum(&second);
        assert_eq!(validate_final(&second, 2, LIVE_TIMEOUT_COUNT), Ok(()));
        let mut hostile = valid;
        hostile.eoi_count -= 1;
        assert_eq!(
            validate_final(&hostile, 1, LIVE_TIMEOUT_COUNT),
            Err(Error::Counter)
        );
        hostile = valid;
        hostile.response_checksum ^= 1;
        assert_eq!(
            validate_final(&hostile, 1, LIVE_TIMEOUT_COUNT),
            Err(Error::Checksum)
        );
        assert_eq!(validate_final(&valid, 1, 0), Err(Error::Counter));
    }

    #[test]
    fn idt_uses_distinct_ipi_error_and_spurious_handlers() {
        let layout = smp_runtime::ResourceLayout::new(0x20, 32).expect("layout");
        let base = layout.trampoline();
        let handlers = HandlerLayout {
            fault: base + 0x100,
            reschedule: base + 0x110,
            shootdown: base + 0x120,
            call_function: base + 0x130,
            diagnostic: base + 0x140,
            panic: base + 0x150,
            stop: base + 0x160,
            apic_error: base + 0x170,
            spurious: base + 0x180,
        };
        let idt = build_idt_page(layout, handlers).expect("idt");
        let gate = |vector: u8| {
            let offset = usize::from(vector) * 16;
            u64::from(u16::from_le_bytes(
                idt[offset..offset + 2].try_into().unwrap(),
            )) | (u64::from(u16::from_le_bytes(
                idt[offset + 6..offset + 8].try_into().unwrap(),
            )) << 16)
                | (u64::from(u32::from_le_bytes(
                    idt[offset + 8..offset + 12].try_into().unwrap(),
                )) << 32)
        };
        assert_eq!(gate(0xe0), handlers.reschedule);
        assert_eq!(gate(0xe5), handlers.stop);
        assert_eq!(gate(240), handlers.apic_error);
        assert_eq!(gate(255), handlers.spurious);
        assert_eq!(gate(3), handlers.fault);
    }

    #[test]
    fn transaction_requires_ordered_quiescence_and_bounded_rollback() {
        let mut transaction = IpiTransaction::new();
        assert_eq!(transaction.reserve(), Ok(()));
        assert_eq!(transaction.prepare(), Ok(()));
        assert_eq!(transaction.startup_sent(), Ok(()));
        assert_eq!(transaction.online(), Ok(()));
        assert_eq!(transaction.exercised(), Ok(()));
        assert_eq!(transaction.quiesced(), Ok(()));
        assert_eq!(transaction.parked(), Ok(()));
        assert_eq!(transaction.validated(), Ok(()));
        assert_eq!(transaction.released(), Ok(()));

        let mut failed = IpiTransaction::new();
        failed.reserve().unwrap();
        failed.prepare().unwrap();
        failed.startup_sent().unwrap();
        assert_eq!(failed.rollback(false), Err(Error::Rollback));
        let receipt = failed.rollback(true).expect("parked rollback");
        assert!(receipt.ap_parked);
        assert!(receipt.capability_revoked);
        assert!(receipt.mmio_revoked);
        assert!(receipt.resources_zeroed);
        assert!(receipt.resources_released);
    }

    #[test]
    fn shootdown_request_binds_root_generation_mask_address_and_frames() {
        let request = ShootdownRequest::canonical(PAGE_BYTES, 2 * PAGE_BYTES, 3 * PAGE_BYTES);
        assert_eq!(validate_shootdown_request(&request, PAGE_BYTES, 0), Ok(()));
        for mutate in 0..8 {
            let mut hostile = request;
            match mutate {
                0 => hostile.root_physical ^= PAGE_BYTES,
                1 => hostile.virtual_address ^= PAGE_BYTES,
                2 => hostile.retired_generation = 0,
                3 => hostile.active_generation = 3,
                4 => hostile.target_mask ^= 1,
                5 => hostile.old_frame_physical = hostile.new_frame_physical,
                6 => hostile.new_frame_physical += 1,
                _ => hostile.checksum ^= 1,
            }
            assert!(validate_shootdown_request(&hostile, PAGE_BYTES, 0).is_err());
        }
        assert_eq!(
            validate_shootdown_request(&request, PAGE_BYTES, ACTIVE_GENERATION),
            Err(ERROR_SHOOTDOWN_GENERATION)
        );
    }

    #[test]
    fn deferred_reclaim_requires_exact_remote_ack_before_release() {
        let request = ShootdownRequest::canonical(PAGE_BYTES, 2 * PAGE_BYTES, 3 * PAGE_BYTES);
        let valid = response().shootdown;
        let mut reclaim = DeferredReclaim::new(request).unwrap();
        assert_eq!(reclaim.authorize(), Err(ReclaimError::State));
        reclaim.arm().unwrap();
        reclaim.timeout().unwrap();
        assert_eq!(reclaim.authorize(), Err(ReclaimError::State));
        reclaim.arm().unwrap();
        let mut stale = valid;
        stale.last_ack_generation = RETIRED_GENERATION;
        stale.response_checksum = shootdown_response_checksum(&stale);
        assert_eq!(
            reclaim.acknowledge(&stale),
            Err(ReclaimError::Acknowledgement)
        );
        reclaim.acknowledge(&valid).unwrap();
        let receipt = reclaim.authorize().unwrap();
        assert_eq!(reclaim.released(receipt), Ok(()));
        assert_eq!(
            reclaim.released(receipt),
            Err(ReclaimError::Acknowledgement)
        );
    }

    fn multi_requests() -> [ShootdownRequest; AP_COUNT] {
        core::array::from_fn(|index| {
            let base = 1 + index as u64 * 3;
            ShootdownRequest::canonical_for_target(
                EXPECTED_APIC_IDS[index],
                base * PAGE_BYTES,
                (base + 1) * PAGE_BYTES,
                (base + 2) * PAGE_BYTES,
            )
        })
    }

    fn multi_ack(index: usize, request: ShootdownRequest) -> ShootdownSnapshot {
        let mut value = response().shootdown;
        value.root_physical = request.root_physical;
        value.target_mask = request.target_mask;
        value.ack_mask = request.target_mask;
        value.old_frame_physical = request.old_frame_physical;
        value.new_frame_physical = request.new_frame_physical;
        value.request_checksum = request.checksum;
        value.timeout_count = u32::from(index == 0);
        value.response_checksum = shootdown_response_checksum(&value);
        value
    }

    #[test]
    fn local_masks_bind_three_aps_and_one_offline_control() {
        assert_eq!(Some(0x2), local_target_mask(1));
        assert_eq!(Some(0x4), local_target_mask(2));
        assert_eq!(Some(0x8), local_target_mask(3));
        assert_eq!(Some(0x10), local_target_mask(OFFLINE_APIC_ID));
        assert_eq!(None, local_target_mask(0));
        assert_eq!(None, local_target_mask(64));
        assert_eq!(0x0e, TARGET_CPU_MASK);
    }

    #[test]
    fn multi_ap_transaction_requires_partial_rollback_and_exact_retry_masks() {
        let mut transaction = MultiApTransaction::new();
        transaction.reserve().unwrap();
        transaction.prepare().unwrap();
        transaction.partial_started(PARTIAL_STARTED_MASK).unwrap();
        transaction.partial_timeout(OFFLINE_APIC_ID).unwrap();
        transaction.partial_parked(PARTIAL_STARTED_MASK).unwrap();
        transaction.partial_released(TARGET_CPU_MASK).unwrap();
        transaction.retry_reserve().unwrap();
        transaction.retry_prepare().unwrap();
        transaction
            .all_online(TARGET_CPU_MASK, TARGET_CPU_MASK)
            .unwrap();
        transaction.exercised(TARGET_CPU_MASK).unwrap();
        transaction.quiesced(TARGET_CPU_MASK).unwrap();
        transaction.parked(TARGET_CPU_MASK).unwrap();
        transaction.validated(TARGET_CPU_MASK).unwrap();
        let receipt = transaction.released(TARGET_CPU_MASK).unwrap();
        assert_eq!(MultiApStage::Released, transaction.stage());
        assert_eq!(TARGET_CPU_MASK, receipt.started_mask);
        assert_eq!(TARGET_CPU_MASK, receipt.online_mask);
        assert_eq!(TARGET_CPU_MASK, receipt.released_mask);
        assert_eq!(1, receipt.timeout_count);
        assert_eq!(1, receipt.retry_count);
        assert_eq!(1, receipt.partial_rollback_count);
    }

    #[test]
    fn multi_ap_transaction_rejects_partial_or_forged_completion() {
        let mut transaction = MultiApTransaction::new();
        assert_eq!(transaction.prepare(), Err(Error::Transition));
        transaction.reserve().unwrap();
        transaction.prepare().unwrap();
        assert_eq!(transaction.partial_started(1 << 1), Err(Error::Transition));
        transaction.partial_started(PARTIAL_STARTED_MASK).unwrap();
        assert_eq!(transaction.partial_timeout(3), Err(Error::Target));
        transaction.partial_timeout(OFFLINE_APIC_ID).unwrap();
        assert_eq!(transaction.partial_parked(1 << 1), Err(Error::Rollback));
    }

    #[test]
    fn multi_reclaim_authorizes_only_after_all_unique_local_acks() {
        let requests = multi_requests();
        let mut reclaim = MultiDeferredReclaim::new(requests).unwrap();
        reclaim.arm().unwrap();
        reclaim.timeout(OFFLINE_CPU_MASK).unwrap();
        reclaim.arm().unwrap();
        assert_eq!(reclaim.authorize(), Err(ReclaimError::State));
        for index in 0..AP_COUNT {
            let ack = multi_ack(index, requests[index]);
            reclaim.acknowledge(EXPECTED_APIC_IDS[index], &ack).unwrap();
            if index + 1 != AP_COUNT {
                assert_eq!(reclaim.authorize(), Err(ReclaimError::State));
            }
        }
        let receipt = reclaim.authorize().unwrap();
        assert_eq!(TARGET_CPU_MASK, receipt.target_mask);
        assert_eq!(TARGET_CPU_MASK, receipt.ack_mask);
        assert_eq!(AP_COUNT as u64, receipt.invalidation_count);
        assert_ne!(0, receipt.root_checksum);
        assert_ne!(0, receipt.old_frame_checksum);
        assert_ne!(0, receipt.new_frame_checksum);
        assert_ne!(receipt.old_frame_checksum, receipt.new_frame_checksum);
        reclaim.released(receipt).unwrap();
        assert_eq!(
            reclaim.released(receipt),
            Err(ReclaimError::Acknowledgement)
        );
    }

    #[test]
    fn multi_reclaim_rejects_duplicate_forged_and_cross_ap_acks() {
        let requests = multi_requests();
        let mut reclaim = MultiDeferredReclaim::new(requests).unwrap();
        reclaim.arm().unwrap();
        let first = multi_ack(0, requests[0]);
        reclaim.acknowledge(1, &first).unwrap();
        assert_eq!(reclaim.acknowledge(1, &first), Err(ReclaimError::Duplicate));

        let mut forged = multi_ack(1, requests[1]);
        forged.ack_mask = local_target_mask(3).unwrap();
        forged.response_checksum = shootdown_response_checksum(&forged);
        assert_eq!(
            reclaim.acknowledge(2, &forged),
            Err(ReclaimError::Acknowledgement)
        );
        assert_eq!(
            reclaim.acknowledge(4, &multi_ack(1, requests[1])),
            Err(ReclaimError::Acknowledgement)
        );
    }
}
