#![no_std]
#![deny(warnings)]

pub const CONTRACT_ID: &str = "PBEXIT1";
pub const TRANSFER_CONTRACT_ID: &str = "PKXFER1";
pub const MAX_EXIT_ATTEMPTS: usize = 4;
pub const RAW_MEMORY_MAP_CAPACITY: usize = 1024 * 1024;
pub const NORMALIZED_MEMORY_CAPACITY: usize = 16_384 * 40;
pub const HANDOFF_CAPACITY_BYTES: usize = 1024 * 1024;
pub const STACK_PAGE_COUNT: usize = 14;
pub const PAGE_SIZE: u64 = 4096;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    MemoryMapShape,
    DescriptorSize,
    DescriptorVersion,
    HandoffShape,
    TransferState,
    AttemptOrder,
    RetryStatus,
    RetryExhausted,
    FirmwareAfterExit,
    FirmwareAfterFirstAttempt,
    TransferForbidden,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TransferError {
    ExitBoundary,
    Envelope,
    Address,
    TransferState,
    Authority,
    Replay,
}

impl TransferError {
    pub const fn code(self) -> &'static str {
        match self {
            Self::ExitBoundary => "transfer_exit_boundary",
            Self::Envelope => "transfer_envelope",
            Self::Address => "transfer_address",
            Self::TransferState => "transfer_state",
            Self::Authority => "transfer_authority",
            Self::Replay => "transfer_replay",
        }
    }
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::MemoryMapShape => "memory_map_shape",
            Self::DescriptorSize => "descriptor_size",
            Self::DescriptorVersion => "descriptor_version",
            Self::HandoffShape => "handoff_shape",
            Self::TransferState => "transfer_state",
            Self::AttemptOrder => "attempt_order",
            Self::RetryStatus => "retry_status",
            Self::RetryExhausted => "retry_exhausted",
            Self::FirmwareAfterExit => "firmware_after_exit",
            Self::FirmwareAfterFirstAttempt => "firmware_after_first_attempt",
            Self::TransferForbidden => "transfer_forbidden",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FinalMap {
    pub map_key: usize,
    pub map_bytes: usize,
    pub descriptor_size: usize,
    pub descriptor_version: u32,
}

impl FinalMap {
    pub fn validate(self) -> Result<(), Error> {
        if !(40..=256).contains(&self.descriptor_size) || !self.descriptor_size.is_multiple_of(8) {
            return Err(Error::DescriptorSize);
        }
        if self.map_bytes == 0
            || self.map_bytes > RAW_MEMORY_MAP_CAPACITY
            || !self.map_bytes.is_multiple_of(self.descriptor_size)
        {
            return Err(Error::MemoryMapShape);
        }
        if self.descriptor_version != 1 {
            return Err(Error::DescriptorVersion);
        }
        Ok(())
    }

    pub const fn descriptor_count(self) -> usize {
        self.map_bytes / self.descriptor_size
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct HandoffCandidate {
    pub byte_count: usize,
    pub boot_services_exited: bool,
    pub development_mode: bool,
    pub stack_top_virtual: u64,
    pub page_table_root_physical: u64,
    pub kernel_signature_verified: bool,
    pub kernel_entry_profile_valid: bool,
}

impl HandoffCandidate {
    pub fn validate(self) -> Result<(), Error> {
        if self.byte_count == 0 || self.byte_count > HANDOFF_CAPACITY_BYTES {
            return Err(Error::HandoffShape);
        }
        if !self.boot_services_exited
            || !self.development_mode
            || self.stack_top_virtual == 0
            || !self.stack_top_virtual.is_multiple_of(16)
            || self.page_table_root_physical == 0
            || !self.page_table_root_physical.is_multiple_of(PAGE_SIZE)
        {
            return Err(Error::TransferState);
        }
        if self.kernel_signature_verified || self.kernel_entry_profile_valid {
            return Err(Error::TransferForbidden);
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FirmwareCall {
    GetMemoryMap,
    ExitBootServices,
    MemoryAllocation,
    Other,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ExitResult {
    Success,
    InvalidParameter,
    OtherFailure,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum State {
    Prepared,
    MapCaptured,
    HandoffFinalized,
    RetryRequired,
    Exited,
    Failed,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Lifecycle {
    state: State,
    attempts: usize,
    firmware_calls_after_exit: usize,
}

impl Lifecycle {
    pub const fn new() -> Self {
        Self {
            state: State::Prepared,
            attempts: 0,
            firmware_calls_after_exit: 0,
        }
    }

    pub const fn state(self) -> State {
        self.state
    }

    pub const fn attempts(self) -> usize {
        self.attempts
    }

    pub const fn firmware_calls_after_exit(self) -> usize {
        self.firmware_calls_after_exit
    }

    pub fn observe_firmware_call(&mut self, call: FirmwareCall) -> Result<(), Error> {
        if self.state == State::Exited {
            self.firmware_calls_after_exit += 1;
            return Err(Error::FirmwareAfterExit);
        }
        if self.attempts != 0
            && !matches!(
                call,
                FirmwareCall::GetMemoryMap
                    | FirmwareCall::ExitBootServices
                    | FirmwareCall::MemoryAllocation
            )
        {
            return Err(Error::FirmwareAfterFirstAttempt);
        }
        Ok(())
    }

    pub fn observe_map(&mut self, map: FinalMap) -> Result<(), Error> {
        if !matches!(self.state, State::Prepared | State::RetryRequired) {
            return Err(Error::AttemptOrder);
        }
        self.observe_firmware_call(FirmwareCall::GetMemoryMap)?;
        map.validate()?;
        self.state = State::MapCaptured;
        Ok(())
    }

    pub fn observe_handoff(&mut self, handoff: HandoffCandidate) -> Result<(), Error> {
        if self.state != State::MapCaptured {
            return Err(Error::AttemptOrder);
        }
        handoff.validate()?;
        self.state = State::HandoffFinalized;
        Ok(())
    }

    pub fn observe_exit(&mut self, result: ExitResult) -> Result<(), Error> {
        if self.state != State::HandoffFinalized || self.attempts >= MAX_EXIT_ATTEMPTS {
            return Err(Error::AttemptOrder);
        }
        self.observe_firmware_call(FirmwareCall::ExitBootServices)?;
        self.attempts += 1;
        match result {
            ExitResult::Success => {
                self.state = State::Exited;
                Ok(())
            }
            ExitResult::InvalidParameter if self.attempts < MAX_EXIT_ATTEMPTS => {
                self.state = State::RetryRequired;
                Ok(())
            }
            ExitResult::InvalidParameter => {
                self.state = State::Failed;
                Err(Error::RetryExhausted)
            }
            ExitResult::OtherFailure => {
                self.state = State::Failed;
                Err(Error::RetryStatus)
            }
        }
    }

    pub const fn transfer_allowed(self) -> bool {
        false
    }

    pub fn observe_transfer(self) -> Result<(), Error> {
        Err(Error::TransferForbidden)
    }
}

impl Default for Lifecycle {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DevelopmentTransfer {
    pub kernel_entry_virtual: u64,
    pub handoff_virtual: u64,
    pub handoff_byte_count: usize,
    pub stack_top_virtual: u64,
    pub page_table_root_physical: u64,
    pub transfer_cr3: u64,
    pub trap_scenario: u8,
    pub boot_services_exited: bool,
    pub development_mode: bool,
    pub emulator_only: bool,
    pub terminal_after_revalidation: bool,
    pub production_kernel_entry_profile_valid: bool,
    pub signature_verifications: u8,
    pub authority_grants: u8,
    pub actions_authorized: u8,
    pub state_writes: u8,
    pub firmware_calls_after_exit: usize,
}

impl DevelopmentTransfer {
    pub fn validate(self) -> Result<(), TransferError> {
        if self.handoff_byte_count < 64 || self.handoff_byte_count > HANDOFF_CAPACITY_BYTES {
            return Err(TransferError::Envelope);
        }
        let handoff_last = self
            .handoff_virtual
            .checked_add(self.handoff_byte_count as u64 - 1)
            .ok_or(TransferError::Address)?;
        if self.kernel_entry_virtual == 0
            || self.handoff_virtual == 0
            || !self.handoff_virtual.is_multiple_of(PAGE_SIZE)
            || self.stack_top_virtual == 0
            || !self.stack_top_virtual.is_multiple_of(16)
            || self.page_table_root_physical == 0
            || !self.page_table_root_physical.is_multiple_of(PAGE_SIZE)
            || self.transfer_cr3 & (PAGE_SIZE - 1) & !0x18 != 0
            || self.transfer_cr3 & !(PAGE_SIZE - 1) != self.page_table_root_physical
            || !is_canonical_x86_64(self.kernel_entry_virtual)
            || !is_canonical_x86_64(self.handoff_virtual)
            || !is_canonical_x86_64(handoff_last)
            || !is_canonical_x86_64(self.stack_top_virtual)
        {
            return Err(TransferError::Address);
        }
        if !self.boot_services_exited
            || !self.development_mode
            || !self.emulator_only
            || !self.terminal_after_revalidation
            || self.production_kernel_entry_profile_valid
            || self.trap_scenario > 8
        {
            return Err(TransferError::TransferState);
        }
        if self.signature_verifications != 0
            || self.authority_grants != 0
            || self.actions_authorized != 0
            || self.state_writes != 0
            || self.firmware_calls_after_exit != 0
        {
            return Err(TransferError::Authority);
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DevelopmentTransferState {
    Armed,
    Dispatched,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DevelopmentTransferLifecycle {
    state: DevelopmentTransferState,
}

impl DevelopmentTransferLifecycle {
    pub fn arm(exit: Lifecycle, transfer: DevelopmentTransfer) -> Result<Self, TransferError> {
        if exit.state() != State::Exited || exit.firmware_calls_after_exit() != 0 {
            return Err(TransferError::ExitBoundary);
        }
        transfer.validate()?;
        Ok(Self {
            state: DevelopmentTransferState::Armed,
        })
    }

    pub const fn state(self) -> DevelopmentTransferState {
        self.state
    }

    pub fn observe_dispatch(&mut self) -> Result<(), TransferError> {
        if self.state != DevelopmentTransferState::Armed {
            return Err(TransferError::Replay);
        }
        self.state = DevelopmentTransferState::Dispatched;
        Ok(())
    }
}

const fn is_canonical_x86_64(address: u64) -> bool {
    let sign = (address >> 47) & 1;
    let upper = address >> 48;
    (sign == 0 && upper == 0) || (sign == 1 && upper == 0xffff)
}

#[cfg(test)]
extern crate std;

#[cfg(test)]
mod tests {
    use super::*;

    fn map(key: usize) -> FinalMap {
        FinalMap {
            map_key: key,
            map_bytes: 48 * 96,
            descriptor_size: 48,
            descriptor_version: 1,
        }
    }

    fn handoff() -> HandoffCandidate {
        HandoffCandidate {
            byte_count: 4248,
            boot_services_exited: true,
            development_mode: true,
            stack_top_virtual: 0xffff_ffff_8003_9000,
            page_table_root_physical: 0x0300_0000,
            kernel_signature_verified: false,
            kernel_entry_profile_valid: false,
        }
    }

    #[test]
    fn accepts_exact_success_sequence() {
        let mut lifecycle = Lifecycle::new();
        lifecycle.observe_map(map(7)).unwrap();
        lifecycle.observe_handoff(handoff()).unwrap();
        lifecycle.observe_exit(ExitResult::Success).unwrap();
        assert_eq!(lifecycle.state(), State::Exited);
        assert_eq!(lifecycle.attempts(), 1);
        assert!(!lifecycle.transfer_allowed());
        assert_eq!(lifecycle.observe_transfer(), Err(Error::TransferForbidden));
    }

    #[test]
    fn retries_only_stale_map_keys_with_fresh_maps() {
        let mut lifecycle = Lifecycle::new();
        for attempt in 1..MAX_EXIT_ATTEMPTS {
            lifecycle.observe_map(map(attempt)).unwrap();
            lifecycle.observe_handoff(handoff()).unwrap();
            lifecycle
                .observe_exit(ExitResult::InvalidParameter)
                .unwrap();
        }
        lifecycle.observe_map(map(MAX_EXIT_ATTEMPTS)).unwrap();
        lifecycle.observe_handoff(handoff()).unwrap();
        assert_eq!(
            lifecycle.observe_exit(ExitResult::InvalidParameter),
            Err(Error::RetryExhausted)
        );
        assert_eq!(lifecycle.state(), State::Failed);
    }

    #[test]
    fn rejects_map_and_handoff_shape_faults() {
        let mut lifecycle = Lifecycle::new();
        let mut invalid_map = map(1);
        invalid_map.descriptor_size = 41;
        assert_eq!(
            lifecycle.observe_map(invalid_map),
            Err(Error::DescriptorSize)
        );

        let mut lifecycle = Lifecycle::new();
        lifecycle.observe_map(map(1)).unwrap();
        let mut invalid_handoff = handoff();
        invalid_handoff.stack_top_virtual = 0;
        assert_eq!(
            lifecycle.observe_handoff(invalid_handoff),
            Err(Error::TransferState)
        );
    }

    #[test]
    fn rejects_post_exit_firmware_and_all_transfer() {
        let mut lifecycle = Lifecycle::new();
        lifecycle.observe_map(map(1)).unwrap();
        lifecycle.observe_handoff(handoff()).unwrap();
        lifecycle.observe_exit(ExitResult::Success).unwrap();
        assert_eq!(
            lifecycle.observe_firmware_call(FirmwareCall::GetMemoryMap),
            Err(Error::FirmwareAfterExit)
        );
        assert_eq!(lifecycle.firmware_calls_after_exit(), 1);
    }

    #[test]
    fn forbids_non_memory_firmware_after_first_attempt() {
        let mut lifecycle = Lifecycle::new();
        lifecycle.observe_map(map(1)).unwrap();
        lifecycle.observe_handoff(handoff()).unwrap();
        lifecycle
            .observe_exit(ExitResult::InvalidParameter)
            .unwrap();
        assert_eq!(
            lifecycle.observe_firmware_call(FirmwareCall::Other),
            Err(Error::FirmwareAfterFirstAttempt)
        );
        assert_eq!(
            lifecycle.observe_firmware_call(FirmwareCall::MemoryAllocation),
            Ok(())
        );
    }

    fn development_transfer() -> DevelopmentTransfer {
        DevelopmentTransfer {
            kernel_entry_virtual: 0xffff_ffff_8000_8000,
            handoff_virtual: 0xffff_ffff_8005_0000,
            handoff_byte_count: 5008,
            stack_top_virtual: 0xffff_ffff_8004_f000,
            page_table_root_physical: 0x0300_0000,
            transfer_cr3: 0x0300_0000,
            trap_scenario: 0,
            boot_services_exited: true,
            development_mode: true,
            emulator_only: true,
            terminal_after_revalidation: true,
            production_kernel_entry_profile_valid: false,
            signature_verifications: 0,
            authority_grants: 0,
            actions_authorized: 0,
            state_writes: 0,
            firmware_calls_after_exit: 0,
        }
    }

    fn exited() -> Lifecycle {
        let mut lifecycle = Lifecycle::new();
        lifecycle.observe_map(map(1)).unwrap();
        lifecycle.observe_handoff(handoff()).unwrap();
        lifecycle.observe_exit(ExitResult::Success).unwrap();
        lifecycle
    }

    #[test]
    fn arms_and_dispatches_one_terminal_development_transfer() {
        let mut transfer =
            DevelopmentTransferLifecycle::arm(exited(), development_transfer()).unwrap();
        assert_eq!(transfer.state(), DevelopmentTransferState::Armed);
        transfer.observe_dispatch().unwrap();
        assert_eq!(transfer.state(), DevelopmentTransferState::Dispatched);
        assert_eq!(transfer.observe_dispatch(), Err(TransferError::Replay));
    }

    #[test]
    fn rejects_transfer_before_successful_exit() {
        assert_eq!(
            DevelopmentTransferLifecycle::arm(Lifecycle::new(), development_transfer()),
            Err(TransferError::ExitBoundary)
        );
    }

    #[test]
    fn rejects_malformed_transfer_addresses() {
        let mut transfer = development_transfer();
        transfer.handoff_virtual += 1;
        assert_eq!(transfer.validate(), Err(TransferError::Address));
        transfer = development_transfer();
        transfer.transfer_cr3 += PAGE_SIZE;
        assert_eq!(transfer.validate(), Err(TransferError::Address));
        transfer = development_transfer();
        transfer.kernel_entry_virtual = 0x0000_8000_0000_0000;
        assert_eq!(transfer.validate(), Err(TransferError::Address));
    }

    #[test]
    fn rejects_production_profile_or_nonterminal_transfer() {
        let mut transfer = development_transfer();
        transfer.production_kernel_entry_profile_valid = true;
        assert_eq!(transfer.validate(), Err(TransferError::TransferState));
        transfer = development_transfer();
        transfer.terminal_after_revalidation = false;
        assert_eq!(transfer.validate(), Err(TransferError::TransferState));
        transfer = development_transfer();
        transfer.trap_scenario = 9;
        assert_eq!(transfer.validate(), Err(TransferError::TransferState));
    }

    #[test]
    fn rejects_any_transfer_effect_or_firmware_call() {
        for mutate in 0..5 {
            let mut transfer = development_transfer();
            match mutate {
                0 => transfer.signature_verifications = 1,
                1 => transfer.authority_grants = 1,
                2 => transfer.actions_authorized = 1,
                3 => transfer.state_writes = 1,
                _ => transfer.firmware_calls_after_exit = 1,
            }
            assert_eq!(transfer.validate(), Err(TransferError::Authority));
        }
    }
}
