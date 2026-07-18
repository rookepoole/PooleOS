#![no_std]
#![deny(warnings)]

pub const CONTRACT_ID: &str = "PBEXIT1";
pub const MAX_EXIT_ATTEMPTS: usize = 4;
pub const RAW_MEMORY_MAP_CAPACITY: usize = 1024 * 1024;
pub const NORMALIZED_MEMORY_CAPACITY: usize = 16_384 * 40;
pub const HANDOFF_CAPACITY_BYTES: usize = 1024 * 1024;
pub const STACK_PAGE_COUNT: usize = 8;
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
}
