//! Pure PKXEXC1 floating-point exception and recovery validation.

use crate::{
    TrapDisposition, TrapExpectation, TrapObservation, validate_trap_observation,
    xstate::{INITIAL_FCW, INITIAL_MXCSR},
};

pub const CONTRACT_ID: &str = "PKXEXC1";
pub const DEVICE_NOT_AVAILABLE_VECTOR: u64 = 7;
pub const X87_FLOATING_POINT_VECTOR: u64 = 16;
pub const SIMD_FLOATING_POINT_VECTOR: u64 = 19;
pub const X87_INVALID_UNMASKED_FCW: u16 = INITIAL_FCW & !1;
pub const SIMD_INVALID_UNMASKED_MXCSR: u32 = INITIAL_MXCSR & !(1 << 7);
pub const X87_INVALID_STATUS: u16 = 1;
pub const X87_EXCEPTION_SUMMARY_STATUS: u16 = 1 << 7;
pub const SIMD_INVALID_STATUS: u32 = 1;
pub const SIMD_INVALID_MASK: u32 = 1 << 7;

const CR0_MP: u64 = 1 << 1;
const CR0_EM: u64 = 1 << 2;
const CR0_TS: u64 = 1 << 3;
const CR0_NE: u64 = 1 << 5;
const CR4_OSFXSR: u64 = 1 << 9;
const CR4_OSXMMEXCPT: u64 = 1 << 10;
const CR4_OSXSAVE: u64 = 1 << 18;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum XstateExceptionKind {
    X87Invalid,
    SimdInvalid,
    DeviceNotAvailable,
}

impl XstateExceptionKind {
    pub const fn vector(self) -> u64 {
        match self {
            Self::X87Invalid => X87_FLOATING_POINT_VECTOR,
            Self::SimdInvalid => SIMD_FLOATING_POINT_VECTOR,
            Self::DeviceNotAvailable => DEVICE_NOT_AVAILABLE_VECTOR,
        }
    }

    pub const fn label(self) -> &'static str {
        match self {
            Self::X87Invalid => "x87_invalid",
            Self::SimdInvalid => "simd_invalid",
            Self::DeviceNotAvailable => "device_not_available",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct XstateExceptionState {
    pub kind: XstateExceptionKind,
    pub trap: TrapObservation,
    pub expected_fault_rip: u64,
    pub expected_resume_rip: u64,
    pub ist_bottom: u64,
    pub ist_top: u64,
    pub cr0: u64,
    pub cr4: u64,
    pub fcw_before: u16,
    pub fsw_before: u16,
    pub mxcsr_before: u32,
    pub fcw_after: u16,
    pub fsw_after: u16,
    pub mxcsr_after: u32,
    pub state_sampled: bool,
    pub test_only_ts_injected: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum XstateExceptionError {
    Kind,
    Frame,
    ControlState,
    X87State,
    SimdState,
    DeviceNotAvailableState,
    Recovery,
}

impl XstateExceptionError {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Kind => "kind",
            Self::Frame => "frame",
            Self::ControlState => "control_state",
            Self::X87State => "x87_state",
            Self::SimdState => "simd_state",
            Self::DeviceNotAvailableState => "device_not_available_state",
            Self::Recovery => "recovery",
        }
    }
}

pub fn validate_exception_state(
    state: &XstateExceptionState,
) -> Result<TrapDisposition, XstateExceptionError> {
    if state.trap.vector != state.kind.vector() {
        return Err(XstateExceptionError::Kind);
    }
    let terminal = state.kind == XstateExceptionKind::DeviceNotAvailable;
    let expectation = TrapExpectation {
        vector: state.kind.vector(),
        error_code: 0,
        fault_rip: state.expected_fault_rip,
        resume_rip: state.expected_resume_rip,
        expected_cr2: None,
        ist_bottom: state.ist_bottom,
        ist_top: state.ist_top,
        terminal,
    };
    let disposition = validate_trap_observation(&state.trap, &expectation)
        .map_err(|_| XstateExceptionError::Frame)?;
    if state.cr0 & (CR0_MP | CR0_NE) != CR0_MP | CR0_NE
        || state.cr0 & CR0_EM != 0
        || state.cr4 & (CR4_OSFXSR | CR4_OSXMMEXCPT | CR4_OSXSAVE)
            != CR4_OSFXSR | CR4_OSXMMEXCPT | CR4_OSXSAVE
    {
        return Err(XstateExceptionError::ControlState);
    }

    match state.kind {
        XstateExceptionKind::X87Invalid => {
            if state.cr0 & CR0_TS != 0
                || !state.state_sampled
                || state.test_only_ts_injected
                || state.fcw_before != X87_INVALID_UNMASKED_FCW
                || state.fsw_before & (X87_INVALID_STATUS | X87_EXCEPTION_SUMMARY_STATUS)
                    != X87_INVALID_STATUS | X87_EXCEPTION_SUMMARY_STATUS
                || state.mxcsr_before != INITIAL_MXCSR
            {
                return Err(XstateExceptionError::X87State);
            }
            if state.fcw_after != INITIAL_FCW
                || state.fsw_after & 0x80ff != 0
                || state.mxcsr_after != INITIAL_MXCSR
                || disposition != TrapDisposition::ResumeAt(state.expected_resume_rip)
            {
                return Err(XstateExceptionError::Recovery);
            }
        }
        XstateExceptionKind::SimdInvalid => {
            if state.cr0 & CR0_TS != 0
                || !state.state_sampled
                || state.test_only_ts_injected
                || state.fcw_before != INITIAL_FCW
                || state.fsw_before & 0x80ff != 0
                || state.mxcsr_before != SIMD_INVALID_UNMASKED_MXCSR | SIMD_INVALID_STATUS
                || state.mxcsr_before & SIMD_INVALID_MASK != 0
            {
                return Err(XstateExceptionError::SimdState);
            }
            if state.fcw_after != INITIAL_FCW
                || state.fsw_after & 0x80ff != 0
                || state.mxcsr_after != INITIAL_MXCSR
                || disposition != TrapDisposition::ResumeAt(state.expected_resume_rip)
            {
                return Err(XstateExceptionError::Recovery);
            }
        }
        XstateExceptionKind::DeviceNotAvailable => {
            if state.cr0 & CR0_TS == 0
                || state.state_sampled
                || !state.test_only_ts_injected
                || state.fcw_before != 0
                || state.fsw_before != 0
                || state.mxcsr_before != 0
                || state.fcw_after != 0
                || state.fsw_after != 0
                || state.mxcsr_after != 0
                || disposition != TrapDisposition::Halt
            {
                return Err(XstateExceptionError::DeviceNotAvailableState);
            }
        }
    }
    Ok(disposition)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct XstateExceptionProof {
    pub x87_delivery_count: u8,
    pub simd_delivery_count: u8,
    pub device_not_available_rejection_count: u8,
    pub recovered_return_count: u8,
    pub privileged_configuration_writes: u8,
    pub recovery_state_writes: u8,
    pub unexpected_vector_count: u8,
    pub machine_code_audit_passed: bool,
    pub signature_verifications: u8,
    pub authority_grants: u8,
    pub actions_authorized: u8,
}

pub fn validate_exception_proof(proof: &XstateExceptionProof) -> Result<(), XstateExceptionError> {
    if proof.x87_delivery_count != 1
        || proof.simd_delivery_count != 1
        || proof.device_not_available_rejection_count != 1
        || proof.recovered_return_count != 2
        || proof.privileged_configuration_writes != 4
        || proof.recovery_state_writes != 2
        || proof.unexpected_vector_count != 0
        || !proof.machine_code_audit_passed
        || proof.signature_verifications != 0
        || proof.authority_grants != 0
        || proof.actions_authorized != 0
    {
        return Err(XstateExceptionError::Recovery);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn trap(vector: u64) -> TrapObservation {
        TrapObservation {
            vector,
            error_code: 0,
            rip: 0x2000,
            code_selector: 0x08,
            rflags: 0x02,
            saved_rsp: 0x4000,
            data_selector: 0x10,
            cr2: 0,
            handler_rsp: 0x1800,
            depth: 1,
        }
    }

    fn state(kind: XstateExceptionKind) -> XstateExceptionState {
        let (fcw_before, fsw_before, mxcsr_before, sampled, injected) = match kind {
            XstateExceptionKind::X87Invalid => (
                X87_INVALID_UNMASKED_FCW,
                X87_INVALID_STATUS | X87_EXCEPTION_SUMMARY_STATUS,
                INITIAL_MXCSR,
                true,
                false,
            ),
            XstateExceptionKind::SimdInvalid => (
                INITIAL_FCW,
                0,
                SIMD_INVALID_UNMASKED_MXCSR | SIMD_INVALID_STATUS,
                true,
                false,
            ),
            XstateExceptionKind::DeviceNotAvailable => (0, 0, 0, false, true),
        };
        XstateExceptionState {
            kind,
            trap: trap(kind.vector()),
            expected_fault_rip: 0x2000,
            expected_resume_rip: if kind == XstateExceptionKind::DeviceNotAvailable {
                0x2000
            } else {
                0x2004
            },
            ist_bottom: 0x1000,
            ist_top: 0x3000,
            cr0: (1 << 1)
                | (1 << 5)
                | if kind == XstateExceptionKind::DeviceNotAvailable {
                    1 << 3
                } else {
                    0
                },
            cr4: (1 << 9) | (1 << 10) | (1 << 18),
            fcw_before,
            fsw_before,
            mxcsr_before,
            fcw_after: if sampled { INITIAL_FCW } else { 0 },
            fsw_after: 0,
            mxcsr_after: if sampled { INITIAL_MXCSR } else { 0 },
            state_sampled: sampled,
            test_only_ts_injected: injected,
        }
    }

    #[test]
    fn accepts_exact_x87_and_simd_recovery() {
        for kind in [
            XstateExceptionKind::X87Invalid,
            XstateExceptionKind::SimdInvalid,
        ] {
            assert_eq!(
                validate_exception_state(&state(kind)),
                Ok(TrapDisposition::ResumeAt(0x2004))
            );
        }
    }

    #[test]
    fn accepts_terminal_device_not_available_rejection() {
        assert_eq!(
            validate_exception_state(&state(XstateExceptionKind::DeviceNotAvailable)),
            Ok(TrapDisposition::Halt)
        );
    }

    #[test]
    fn rejects_wrong_vector_and_frame() {
        let mut value = state(XstateExceptionKind::X87Invalid);
        value.trap.vector = SIMD_FLOATING_POINT_VECTOR;
        assert_eq!(
            validate_exception_state(&value),
            Err(XstateExceptionError::Kind)
        );
        value = state(XstateExceptionKind::X87Invalid);
        value.trap.code_selector = 0x10;
        assert_eq!(
            validate_exception_state(&value),
            Err(XstateExceptionError::Frame)
        );
    }

    #[test]
    fn rejects_masked_or_missing_x87_status() {
        let mut value = state(XstateExceptionKind::X87Invalid);
        value.fcw_before = INITIAL_FCW;
        assert_eq!(
            validate_exception_state(&value),
            Err(XstateExceptionError::X87State)
        );
        value = state(XstateExceptionKind::X87Invalid);
        value.fsw_before = 0;
        assert_eq!(
            validate_exception_state(&value),
            Err(XstateExceptionError::X87State)
        );
    }

    #[test]
    fn rejects_masked_or_uncleared_simd_status() {
        let mut value = state(XstateExceptionKind::SimdInvalid);
        value.mxcsr_before |= SIMD_INVALID_MASK;
        assert_eq!(
            validate_exception_state(&value),
            Err(XstateExceptionError::SimdState)
        );
        value = state(XstateExceptionKind::SimdInvalid);
        value.mxcsr_after = SIMD_INVALID_STATUS;
        assert_eq!(
            validate_exception_state(&value),
            Err(XstateExceptionError::Recovery)
        );
    }

    #[test]
    fn rejects_recoverable_or_unsampled_nm_claims() {
        let mut value = state(XstateExceptionKind::DeviceNotAvailable);
        value.test_only_ts_injected = false;
        assert_eq!(
            validate_exception_state(&value),
            Err(XstateExceptionError::DeviceNotAvailableState)
        );
        value = state(XstateExceptionKind::DeviceNotAvailable);
        value.state_sampled = true;
        assert_eq!(
            validate_exception_state(&value),
            Err(XstateExceptionError::DeviceNotAvailableState)
        );
    }

    #[test]
    fn validates_exact_proof_counts_and_authority_boundary() {
        let proof = XstateExceptionProof {
            x87_delivery_count: 1,
            simd_delivery_count: 1,
            device_not_available_rejection_count: 1,
            recovered_return_count: 2,
            privileged_configuration_writes: 4,
            recovery_state_writes: 2,
            unexpected_vector_count: 0,
            machine_code_audit_passed: true,
            signature_verifications: 0,
            authority_grants: 0,
            actions_authorized: 0,
        };
        assert_eq!(validate_exception_proof(&proof), Ok(()));
        let mut invalid = proof;
        invalid.authority_grants = 1;
        assert_eq!(
            validate_exception_proof(&invalid),
            Err(XstateExceptionError::Recovery)
        );
    }
}
