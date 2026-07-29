//! Pure PKSMP3 capability-gated IPI transport contract and validation.

use core::mem::{offset_of, size_of};

use crate::smp_runtime;

pub const CONTRACT_ID: &str = "PKSMP3";
pub const SELECTED_MOVE_ID: &str = "N8-SMP-IPI-001";
pub const SELECTOR: u64 = 14;

pub const PAGE_BYTES: u64 = smp_runtime::PAGE_BYTES;
pub const APIC_PAGE_TABLE_OFFSET: u64 = smp_runtime::RESERVED_PAGE_OFFSET;
pub const APIC_PDPT_INDEX: usize = 3;
pub const APIC_PAGE_DIRECTORY_INDEX: usize = 503;
pub const APIC_PAGE_TABLE_INDEX: usize = 0;
pub const APIC_PHYSICAL_ADDRESS: u64 = 0xfee0_0000;
pub const APIC_EOI_OFFSET: u64 = 0x0b0;
pub const APIC_SPURIOUS_OFFSET: u64 = 0x0f0;

pub const EXTENSION_MAGIC: u64 = 0x504b_534d_5033_4950;
pub const EXTENSION_VERSION: u32 = 1;
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

pub const CAPABILITY_HIGH: u64 = 0x504f_4f4c_454f_5349;
pub const CAPABILITY_LOW: u64 = 0x504b_534d_5033_0001;
pub const REQUEST_CHECKSUM_SEED: u64 = 0x4950_4952_4551_0001;
pub const RESPONSE_CHECKSUM_SEED: u64 = 0x4950_4952_5350_0001;

pub const RESCHEDULE_PAYLOAD: u64 = 0;
pub const SHOOTDOWN_GENERATION: u64 = 1;
pub const CALL_NOOP_TOKEN: u64 = 0x504b_4e4f_4f50_0001;
pub const DIAGNOSTIC_TOKEN: u64 = 0x504b_4449_4147_0001;
pub const PANIC_NOTICE_TOKEN: u64 = 0x504b_5041_4e49_0001;
pub const STOP_TOKEN: u64 = 0x504b_5354_4f50_0001;

pub const RESULT_RESCHEDULE_OBSERVED: u64 = 0x5253_4348_4544_0001;
pub const RESULT_SHOOTDOWN_TRANSPORT_ONLY: u64 = 0x5348_4f4f_5400_0001;
pub const RESULT_CALL_ALLOWLIST_NOOP: u64 = 0x4341_4c4c_4e4f_4f50;
pub const RESULT_DIAGNOSTIC_OBSERVED: u64 = 0x4449_4147_4e4f_0001;
pub const RESULT_PANIC_LATCHED: u64 = 0x5041_4e49_4300_0001;
pub const RESULT_STOP_QUIESCED: u64 = 0x5354_4f50_0000_0001;

pub const LIVE_ACCEPTED_COUNT: u32 = 6;
pub const LIVE_DENIED_COUNT: u32 = 4;
pub const LIVE_DELIVERY_COUNT: u32 = LIVE_ACCEPTED_COUNT + LIVE_DENIED_COUNT;
pub const LIVE_TIMEOUT_COUNT: u32 = 1;
pub const LIVE_FINAL_ATTEMPT: u64 = 10;
pub const LIVE_FINAL_SEQUENCE: u64 = 6;

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
            Self::Shootdown => RESULT_SHOOTDOWN_TRANSPORT_ONLY,
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

const _: () = assert!(EXTENSION_BASE_OFFSET == 352);
const _: () = assert!(EXTENSION_BYTES == 200);
const _: () = assert!(MAGIC_OFFSET == 352);
const _: () = assert!(REQUEST_ATTEMPT_OFFSET == 400);
const _: () = assert!(ACK_ATTEMPT_OFFSET == 432);
const _: () = assert!(REQUEST_OPERATION_OFFSET == 472);
const _: () = assert!(APIC_ERROR_COUNT_OFFSET == 548);
const _: () = assert!(MAILBOX_BYTES == 552);
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
    payload == operation.payload()
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
        || timeout_count != LIVE_TIMEOUT_COUNT
        || snapshot.reschedule_count != 1
        || snapshot.shootdown_count != 1
        || snapshot.call_function_count != 1
        || snapshot.diagnostic_count != 1
        || snapshot.panic_count != 1
        || snapshot.stop_count != 1
        || snapshot.spurious_count != 0
        || snapshot.apic_error_count != 0
    {
        return Err(Error::Counter);
    }
    if snapshot.panic_latched != 1 {
        return Err(Error::PanicState);
    }
    if snapshot.response_checksum != response_checksum(snapshot) {
        return Err(Error::Checksum);
    }
    Ok(())
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
            reschedule_count: 1,
            shootdown_count: 1,
            call_function_count: 1,
            diagnostic_count: 1,
            stop_count: 1,
            panic_count: 1,
            panic_latched: 1,
            spurious_count: 0,
            apic_error_count: 0,
        };
        let request =
            Request::canonical(LIVE_FINAL_ATTEMPT, LIVE_FINAL_SEQUENCE, Operation::Stop, 1);
        value.request_checksum = request.checksum;
        value.response_checksum = response_checksum(&value);
        value
    }

    #[test]
    fn mailbox_offsets_are_frozen() {
        assert_eq!(EXTENSION_BASE_OFFSET, 352);
        assert_eq!(MAILBOX_BYTES, 552);
        assert_eq!(REQUEST_ATTEMPT_OFFSET, 400);
        assert_eq!(RESPONSE_CHECKSUM_OFFSET, 456);
        assert_eq!(APIC_ERROR_COUNT_OFFSET, 548);
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
                    payload: 2,
                    checksum: request_checksum(&Request {
                        payload: 2,
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
}
