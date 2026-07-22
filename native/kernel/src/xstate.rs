//! Pure PKXSTATE1 policy and ownership validation.

pub const CONTRACT_ID: &str = "PKXSTATE1";
pub const SELECTED_XCR0: u64 = 0b11;
pub const AREA_ALIGNMENT: u64 = 64;
pub const AREA_BYTES: u32 = 4096;
pub const LEGACY_AREA_BYTES: u32 = 512;
pub const HEADER_BYTES: u32 = 64;
pub const MIN_STANDARD_AREA_BYTES: u32 = LEGACY_AREA_BYTES + HEADER_BYTES;
pub const INITIAL_FCW: u16 = 0x037f;
pub const INITIAL_MXCSR: u32 = 0x0000_1f80;
pub const MXCSR_MASK_FALLBACK: u32 = 0x0000_ffbf;

const LEAF1_ECX_XSAVE: u32 = 1 << 26;
const LEAF1_ECX_OSXSAVE: u32 = 1 << 27;
const LEAF1_EDX_FPU: u32 = 1 << 0;
const LEAF1_EDX_FXSR: u32 = 1 << 24;
const LEAF1_EDX_SSE: u32 = 1 << 25;
const LEAF1_EDX_SSE2: u32 = 1 << 26;
const REQUIRED_LEAF1_EDX: u32 = LEAF1_EDX_FPU | LEAF1_EDX_FXSR | LEAF1_EDX_SSE | LEAF1_EDX_SSE2;
const LEAF_D1_KNOWN_CAPABILITIES: u32 = 0x0f;
const CR0_MP: u64 = 1 << 1;
const CR0_EM: u64 = 1 << 2;
const CR0_TS: u64 = 1 << 3;
const CR0_NE: u64 = 1 << 5;
const CR4_OSFXSR: u64 = 1 << 9;
const CR4_OSXMMEXCPT: u64 = 1 << 10;
const CR4_OSXSAVE: u64 = 1 << 18;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SaveFormat {
    StandardXsave,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SwitchStrategy {
    Eager,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum KernelSimdPolicy {
    Forbidden,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct XstatePolicy {
    pub leaf1_ecx: u32,
    pub leaf1_edx: u32,
    pub supported_xcr0: u64,
    pub selected_xcr0: u64,
    pub enabled_area_bytes: u32,
    pub maximum_area_bytes: u32,
    pub leaf_d1_eax: u32,
    pub cr0: u64,
    pub cr4: u64,
    pub xss: u64,
    pub mxcsr_mask: u32,
    pub area_address: u64,
    pub area_bytes: u32,
    pub save_format: SaveFormat,
    pub switch_strategy: SwitchStrategy,
    pub kernel_simd: KernelSimdPolicy,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum XstatePolicyError {
    Feature,
    ComponentMask,
    AreaSize,
    AreaAlignment,
    ControlState,
    SupervisorState,
    MxcsrMask,
    SaveFormat,
}

impl XstatePolicyError {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Feature => "feature",
            Self::ComponentMask => "component_mask",
            Self::AreaSize => "area_size",
            Self::AreaAlignment => "area_alignment",
            Self::ControlState => "control_state",
            Self::SupervisorState => "supervisor_state",
            Self::MxcsrMask => "mxcsr_mask",
            Self::SaveFormat => "save_format",
        }
    }
}

pub const fn effective_mxcsr_mask(raw: u32) -> u32 {
    if raw == 0 { MXCSR_MASK_FALLBACK } else { raw }
}

pub fn validate_policy(policy: &XstatePolicy) -> Result<(), XstatePolicyError> {
    if policy.leaf1_ecx & (LEAF1_ECX_XSAVE | LEAF1_ECX_OSXSAVE)
        != LEAF1_ECX_XSAVE | LEAF1_ECX_OSXSAVE
        || policy.leaf1_edx & REQUIRED_LEAF1_EDX != REQUIRED_LEAF1_EDX
    {
        return Err(XstatePolicyError::Feature);
    }
    if policy.supported_xcr0 & SELECTED_XCR0 != SELECTED_XCR0
        || policy.selected_xcr0 != SELECTED_XCR0
        || policy.selected_xcr0 & !policy.supported_xcr0 != 0
    {
        return Err(XstatePolicyError::ComponentMask);
    }
    if !(MIN_STANDARD_AREA_BYTES..=AREA_BYTES).contains(&policy.enabled_area_bytes)
        || policy.maximum_area_bytes < policy.enabled_area_bytes
        || policy.area_bytes != AREA_BYTES
    {
        return Err(XstatePolicyError::AreaSize);
    }
    if policy.area_address == 0 || !policy.area_address.is_multiple_of(AREA_ALIGNMENT) {
        return Err(XstatePolicyError::AreaAlignment);
    }
    if policy.cr0 & (CR0_MP | CR0_NE) != CR0_MP | CR0_NE
        || policy.cr0 & (CR0_EM | CR0_TS) != 0
        || policy.cr4 & (CR4_OSFXSR | CR4_OSXMMEXCPT | CR4_OSXSAVE)
            != CR4_OSFXSR | CR4_OSXMMEXCPT | CR4_OSXSAVE
    {
        return Err(XstatePolicyError::ControlState);
    }
    if policy.xss != 0 {
        return Err(XstatePolicyError::SupervisorState);
    }
    if policy.leaf_d1_eax & !LEAF_D1_KNOWN_CAPABILITIES != 0 {
        return Err(XstatePolicyError::Feature);
    }
    let mxcsr_mask = effective_mxcsr_mask(policy.mxcsr_mask);
    if INITIAL_MXCSR & !mxcsr_mask != 0 {
        return Err(XstatePolicyError::MxcsrMask);
    }
    if policy.save_format != SaveFormat::StandardXsave
        || policy.switch_strategy != SwitchStrategy::Eager
        || policy.kernel_simd != KernelSimdPolicy::Forbidden
    {
        return Err(XstatePolicyError::SaveFormat);
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ContextSwitch {
    pub outgoing_owner: u64,
    pub incoming_owner: u64,
    pub outgoing_address: u64,
    pub incoming_address: u64,
    pub image_bytes: u32,
    pub selected_xcr0: u64,
    pub incoming_initialized: bool,
    pub scheduler_lock_held: bool,
    pub interrupts_disabled: bool,
    pub kernel_simd_active: bool,
    pub same_cpu: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ContextSwitchError {
    Owner,
    Image,
    ComponentMask,
    Uninitialized,
    SchedulerLock,
    InterruptState,
    KernelSimd,
    CpuMigration,
}

pub fn validate_context_switch(value: &ContextSwitch) -> Result<(), ContextSwitchError> {
    if value.outgoing_owner == 0
        || value.incoming_owner == 0
        || value.outgoing_owner == value.incoming_owner
    {
        return Err(ContextSwitchError::Owner);
    }
    if value.image_bytes != AREA_BYTES
        || value.outgoing_address == value.incoming_address
        || !value.outgoing_address.is_multiple_of(AREA_ALIGNMENT)
        || !value.incoming_address.is_multiple_of(AREA_ALIGNMENT)
    {
        return Err(ContextSwitchError::Image);
    }
    if value.selected_xcr0 != SELECTED_XCR0 {
        return Err(ContextSwitchError::ComponentMask);
    }
    if !value.incoming_initialized {
        return Err(ContextSwitchError::Uninitialized);
    }
    if !value.scheduler_lock_held {
        return Err(ContextSwitchError::SchedulerLock);
    }
    if !value.interrupts_disabled {
        return Err(ContextSwitchError::InterruptState);
    }
    if value.kernel_simd_active {
        return Err(ContextSwitchError::KernelSimd);
    }
    if !value.same_cpu {
        return Err(ContextSwitchError::CpuMigration);
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct XstateProof {
    pub policy: XstatePolicy,
    pub cr0_before: u64,
    pub cr4_before: u64,
    pub xcr0_before: u64,
    pub initial_fcw: u16,
    pub initial_mxcsr: u32,
    pub context_a_xstate_bv: u64,
    pub context_b_xstate_bv: u64,
    pub context_a_match: bool,
    pub context_b_match: bool,
    pub canonical_xmm0_zero: bool,
    pub context_image_zero_bytes: u32,
    pub save_count: u8,
    pub restore_count: u8,
    pub state_write_count: u8,
    pub unexpected_nm_count: u8,
}

pub fn validate_proof(proof: &XstateProof) -> Result<(), XstatePolicyError> {
    validate_policy(&proof.policy)?;
    if proof.initial_fcw != INITIAL_FCW || proof.initial_mxcsr != INITIAL_MXCSR {
        return Err(XstatePolicyError::ControlState);
    }
    if proof.context_a_xstate_bv & !SELECTED_XCR0 != 0
        || proof.context_b_xstate_bv & !SELECTED_XCR0 != 0
        || proof.context_a_xstate_bv & 0b10 == 0
        || proof.context_b_xstate_bv & 0b10 == 0
        || !proof.context_a_match
        || !proof.context_b_match
        || !proof.canonical_xmm0_zero
        || proof.context_image_zero_bytes != AREA_BYTES * 2
        || proof.save_count != 2
        || proof.restore_count != 4
        || proof.state_write_count != 3
        || proof.unexpected_nm_count != 0
    {
        return Err(XstatePolicyError::SaveFormat);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn policy() -> XstatePolicy {
        XstatePolicy {
            leaf1_ecx: LEAF1_ECX_XSAVE | LEAF1_ECX_OSXSAVE,
            leaf1_edx: REQUIRED_LEAF1_EDX,
            supported_xcr0: SELECTED_XCR0,
            selected_xcr0: SELECTED_XCR0,
            enabled_area_bytes: MIN_STANDARD_AREA_BYTES,
            maximum_area_bytes: MIN_STANDARD_AREA_BYTES,
            leaf_d1_eax: 1,
            cr0: CR0_MP | CR0_NE,
            cr4: CR4_OSFXSR | CR4_OSXMMEXCPT | CR4_OSXSAVE,
            xss: 0,
            mxcsr_mask: 0xffff,
            area_address: 0x1000,
            area_bytes: AREA_BYTES,
            save_format: SaveFormat::StandardXsave,
            switch_strategy: SwitchStrategy::Eager,
            kernel_simd: KernelSimdPolicy::Forbidden,
        }
    }

    #[test]
    fn accepts_frozen_eager_standard_policy() {
        assert_eq!(validate_policy(&policy()), Ok(()));
    }

    #[test]
    fn rejects_feature_mask_and_component_conflicts() {
        let mut value = policy();
        value.leaf1_ecx &= !LEAF1_ECX_XSAVE;
        assert_eq!(validate_policy(&value), Err(XstatePolicyError::Feature));
        value = policy();
        value.selected_xcr0 = 1;
        assert_eq!(
            validate_policy(&value),
            Err(XstatePolicyError::ComponentMask)
        );
    }

    #[test]
    fn rejects_area_control_and_supervisor_conflicts() {
        let mut value = policy();
        value.area_address += 1;
        assert_eq!(
            validate_policy(&value),
            Err(XstatePolicyError::AreaAlignment)
        );
        value = policy();
        value.cr0 |= CR0_TS;
        assert_eq!(
            validate_policy(&value),
            Err(XstatePolicyError::ControlState)
        );
        value = policy();
        value.xss = 1;
        assert_eq!(
            validate_policy(&value),
            Err(XstatePolicyError::SupervisorState)
        );
        value = policy();
        value.leaf_d1_eax |= 1 << 3;
        assert_eq!(validate_policy(&value), Ok(()));
        value.leaf_d1_eax |= 1 << 4;
        assert_eq!(validate_policy(&value), Err(XstatePolicyError::Feature));
    }

    #[test]
    fn uses_architectural_mxcsr_mask_fallback() {
        let mut value = policy();
        value.mxcsr_mask = 0;
        assert_eq!(effective_mxcsr_mask(0), MXCSR_MASK_FALLBACK);
        assert_eq!(validate_policy(&value), Ok(()));
        value.mxcsr_mask = 0x0000_0080;
        assert_eq!(validate_policy(&value), Err(XstatePolicyError::MxcsrMask));
    }

    fn switch() -> ContextSwitch {
        ContextSwitch {
            outgoing_owner: 0xa,
            incoming_owner: 0xb,
            outgoing_address: 0x1000,
            incoming_address: 0x2000,
            image_bytes: AREA_BYTES,
            selected_xcr0: SELECTED_XCR0,
            incoming_initialized: true,
            scheduler_lock_held: true,
            interrupts_disabled: true,
            kernel_simd_active: false,
            same_cpu: true,
        }
    }

    #[test]
    fn accepts_frozen_context_switch_preconditions() {
        assert_eq!(validate_context_switch(&switch()), Ok(()));
    }

    #[test]
    fn rejects_cross_owner_and_execution_precondition_failures() {
        let mut value = switch();
        value.incoming_owner = value.outgoing_owner;
        assert_eq!(
            validate_context_switch(&value),
            Err(ContextSwitchError::Owner)
        );
        value = switch();
        value.kernel_simd_active = true;
        assert_eq!(
            validate_context_switch(&value),
            Err(ContextSwitchError::KernelSimd)
        );
        value = switch();
        value.same_cpu = false;
        assert_eq!(
            validate_context_switch(&value),
            Err(ContextSwitchError::CpuMigration)
        );
    }

    #[test]
    fn validates_exact_round_trip_and_clear_receipt() {
        let proof = XstateProof {
            policy: policy(),
            cr0_before: CR0_MP | CR0_NE,
            cr4_before: CR4_OSFXSR | CR4_OSXMMEXCPT | CR4_OSXSAVE,
            xcr0_before: SELECTED_XCR0,
            initial_fcw: INITIAL_FCW,
            initial_mxcsr: INITIAL_MXCSR,
            context_a_xstate_bv: 2,
            context_b_xstate_bv: 2,
            context_a_match: true,
            context_b_match: true,
            canonical_xmm0_zero: true,
            context_image_zero_bytes: AREA_BYTES * 2,
            save_count: 2,
            restore_count: 4,
            state_write_count: 3,
            unexpected_nm_count: 0,
        };
        assert_eq!(validate_proof(&proof), Ok(()));
    }
}
