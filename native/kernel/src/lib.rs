#![no_std]
#![deny(warnings)]
#![forbid(unsafe_op_in_unsafe_fn)]

#[cfg(test)]
extern crate std;

use core::marker::PhantomData;
use core::ptr;
use core::sync::atomic::{AtomicU8, AtomicU32, AtomicUsize, Ordering};

use poole_handoff::{
    self, BOOT_SERVICES_EXITED, CoreRecord, DEVELOPMENT_MODE, FEATURE_CORE, FEATURE_FRAMEBUFFER,
    FEATURE_LOADED_ARTIFACTS, FEATURE_MEMORY_MAP, Handoff, RECORD_FRAMEBUFFER,
    RECORD_LOADED_ARTIFACTS, validate_kernel_entry_profile,
};

pub mod active_virtual_memory;
pub mod physical_memory;
pub mod privilege_msr;
pub mod revalidation;
pub mod virtual_memory;
pub mod xstate;
pub mod xstate_exception;

pub const ENTRY_CONTRACT_ID: &str = "PKENTRY1";
pub const TRANSFER_CONTRACT_ID: &str = "PKXFER1";
pub const TRAP_CONTRACT_ID: &str = "PKTRAP1";
pub const CPU_POLICY_CONTRACT_ID: &str = "PKCPU1";
pub const PRIVILEGE_MSR_CONTRACT_ID: &str = privilege_msr::CONTRACT_ID;
pub const PHYSICAL_MEMORY_CONTRACT_ID: &str = physical_memory::CONTRACT_ID;
pub const ACTIVE_VIRTUAL_MEMORY_CONTRACT_ID: &str = active_virtual_memory::CONTRACT_ID;
pub const VIRTUAL_MEMORY_CONTRACT_ID: &str = virtual_memory::CONTRACT_ID;
pub const XSTATE_EXCEPTION_CONTRACT_ID: &str = "PKXEXC1";
#[used]
#[unsafe(link_section = ".text.pkbuild_literal")]
static BUILD_ID_BYTES: [u8; 35] = *b"PKBUILD1-CYCLE131-N9-PMM-GROWTH-001";
pub const BUILD_ID: &[u8] = &BUILD_ID_BYTES;
pub const ENTRY_OFFSET: u64 = 0x9000;
pub const EARLY_LOG_CAPACITY: usize = 4096;
pub const HANDOFF_MAGIC_U64: u64 = u64::from_le_bytes(poole_handoff::MAGIC);
pub const KERNEL_CODE_SELECTOR: u16 = 0x08;
pub const KERNEL_DATA_SELECTOR: u16 = 0x10;
pub const KERNEL_TSS_SELECTOR: u16 = 0x18;
pub const GDT_LIMIT: u16 = 39;
pub const IDT_LIMIT: u16 = 4095;
pub const IST_STACK_BYTES: u64 = 8192;
pub const BOOTSTRAP_STACK_PAGE_COUNT: u64 = 14;
pub const INSTALLED_EXCEPTION_GATE_COUNT: u16 = 5;
pub const INSTALLED_XSTATE_EXCEPTION_GATE_COUNT: u16 = 8;
const CR3_ALLOWED_LOW_BITS: u64 = (1 << 3) | (1 << 4);
const RFLAGS_INTERRUPT_ENABLE: u64 = 1 << 9;
const RFLAGS_DIRECTION: u64 = 1 << 10;
const RFLAGS_RESERVED_ONE: u64 = 1 << 1;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u32)]
pub enum PanicCode {
    RustPanic = 0x1001,
    StackContract = 0x1002,
    HandoffEnvelope = 0x1003,
    HandoffDecode = 0x1004,
    HandoffProfile = 0x1005,
    RuntimeContinuity = 0x1006,
    TrustRevalidation = 0x1007,
    TransferState = 0x1008,
    Reentry = 0x1009,
    DescriptorState = 0x100a,
    TrapContract = 0x100b,
    CpuPolicy = 0x100c,
    XstatePolicy = 0x100d,
    XstateException = 0x100e,
    PrivilegeMsrPolicy = 0x100f,
    PhysicalMemory = 0x1010,
    VirtualMemory = 0x1011,
    ActiveVirtualMemory = 0x1012,
    UnexpectedReturn = 0x10ff,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u64)]
pub enum DevelopmentTrapScenario {
    None = 0,
    Returning = 1,
    DoubleFault = 2,
    MalformedFrame = 3,
    CpuPolicy = 4,
    XstatePolicy = 5,
    XstateException = 6,
    PrivilegeMsrPolicy = 7,
    PhysicalMemory = 8,
    VirtualMemory = 9,
    ActiveVirtualMemory = 10,
}

macro_rules! scenario_label {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pkscenario_labels")]
        static $name: [u8; $value.len()] = *$value;
    };
}

scenario_label!(SCENARIO_NONE, b"none");
scenario_label!(SCENARIO_RETURNING, b"returning");
scenario_label!(SCENARIO_DOUBLE_FAULT, b"double_fault");
scenario_label!(SCENARIO_MALFORMED_FRAME, b"malformed_frame");
scenario_label!(SCENARIO_CPU_POLICY, b"cpu_policy");
scenario_label!(SCENARIO_XSTATE_POLICY, b"xstate_policy");
scenario_label!(SCENARIO_XSTATE_EXCEPTION, b"xstate_exception");
scenario_label!(SCENARIO_PRIVILEGE_MSR_POLICY, b"privilege_msr_policy");
scenario_label!(SCENARIO_PHYSICAL_MEMORY, b"physical_memory");
scenario_label!(SCENARIO_VIRTUAL_MEMORY, b"virtual_memory");
scenario_label!(SCENARIO_ACTIVE_VIRTUAL_MEMORY, b"active_virtual_memory");

const fn scenario_label_text(bytes: &'static [u8]) -> &'static str {
    // SAFETY: every caller supplies an ASCII byte string declared immediately above.
    unsafe { core::str::from_utf8_unchecked(bytes) }
}

impl DevelopmentTrapScenario {
    pub const fn from_selector(selector: u64) -> Option<Self> {
        match selector {
            0 => Some(Self::None),
            1 => Some(Self::Returning),
            2 => Some(Self::DoubleFault),
            3 => Some(Self::MalformedFrame),
            4 => Some(Self::CpuPolicy),
            5 => Some(Self::XstatePolicy),
            6 => Some(Self::XstateException),
            7 => Some(Self::PrivilegeMsrPolicy),
            8 => Some(Self::PhysicalMemory),
            9 => Some(Self::VirtualMemory),
            10 => Some(Self::ActiveVirtualMemory),
            _ => None,
        }
    }

    pub const fn label(self) -> &'static str {
        match self {
            Self::None => scenario_label_text(&SCENARIO_NONE),
            Self::Returning => scenario_label_text(&SCENARIO_RETURNING),
            Self::DoubleFault => scenario_label_text(&SCENARIO_DOUBLE_FAULT),
            Self::MalformedFrame => scenario_label_text(&SCENARIO_MALFORMED_FRAME),
            Self::CpuPolicy => scenario_label_text(&SCENARIO_CPU_POLICY),
            Self::XstatePolicy => scenario_label_text(&SCENARIO_XSTATE_POLICY),
            Self::XstateException => scenario_label_text(&SCENARIO_XSTATE_EXCEPTION),
            Self::PrivilegeMsrPolicy => scenario_label_text(&SCENARIO_PRIVILEGE_MSR_POLICY),
            Self::PhysicalMemory => scenario_label_text(&SCENARIO_PHYSICAL_MEMORY),
            Self::VirtualMemory => scenario_label_text(&SCENARIO_VIRTUAL_MEMORY),
            Self::ActiveVirtualMemory => scenario_label_text(&SCENARIO_ACTIVE_VIRTUAL_MEMORY),
        }
    }
}

const LEAF1_EDX_FPU: u32 = 1 << 0;
const LEAF1_EDX_TSC: u32 = 1 << 4;
const LEAF1_EDX_MSR: u32 = 1 << 5;
const LEAF1_EDX_PAE: u32 = 1 << 6;
const LEAF1_EDX_CX8: u32 = 1 << 8;
const LEAF1_EDX_APIC: u32 = 1 << 9;
const LEAF1_EDX_MTRR: u32 = 1 << 12;
const LEAF1_EDX_PGE: u32 = 1 << 13;
const LEAF1_EDX_CMOV: u32 = 1 << 15;
const LEAF1_EDX_PAT: u32 = 1 << 16;
const LEAF1_EDX_FXSR: u32 = 1 << 24;
const LEAF1_EDX_SSE: u32 = 1 << 25;
const LEAF1_EDX_SSE2: u32 = 1 << 26;
const LEAF1_EDX_HTT: u32 = 1 << 28;
pub const CPU_REQUIRED_LEAF1_EDX: u32 = LEAF1_EDX_FPU
    | LEAF1_EDX_TSC
    | LEAF1_EDX_MSR
    | LEAF1_EDX_PAE
    | LEAF1_EDX_CX8
    | LEAF1_EDX_APIC
    | LEAF1_EDX_MTRR
    | LEAF1_EDX_PGE
    | LEAF1_EDX_CMOV
    | LEAF1_EDX_PAT
    | LEAF1_EDX_FXSR
    | LEAF1_EDX_SSE
    | LEAF1_EDX_SSE2;

const LEAF1_ECX_PCID: u32 = 1 << 17;
const LEAF1_ECX_X2APIC: u32 = 1 << 21;
const LEAF1_ECX_XSAVE: u32 = 1 << 26;
const LEAF1_ECX_OSXSAVE: u32 = 1 << 27;
const LEAF7_EBX_FSGSBASE: u32 = 1 << 0;
const LEAF7_EBX_SMEP: u32 = 1 << 7;
const LEAF7_EBX_SMAP: u32 = 1 << 20;
const LEAF7_ECX_UMIP: u32 = 1 << 2;
const EXT1_EDX_SYSCALL: u32 = 1 << 11;
const EXT1_EDX_NX: u32 = 1 << 20;
const EXT1_EDX_LONG_MODE: u32 = 1 << 29;
pub const CPU_REQUIRED_EXT1_EDX: u32 = EXT1_EDX_SYSCALL | EXT1_EDX_NX | EXT1_EDX_LONG_MODE;

const CR0_PE: u64 = 1 << 0;
const CR0_MP: u64 = 1 << 1;
const CR0_EM: u64 = 1 << 2;
const CR0_TS: u64 = 1 << 3;
const CR0_ET: u64 = 1 << 4;
const CR0_NE: u64 = 1 << 5;
const CR0_WP: u64 = 1 << 16;
const CR0_NW: u64 = 1 << 29;
const CR0_CD: u64 = 1 << 30;
const CR0_PG: u64 = 1 << 31;
pub const CPU_REQUIRED_CR0: u64 = CR0_PE | CR0_MP | CR0_ET | CR0_NE | CR0_WP | CR0_PG;
pub const CPU_FORBIDDEN_CR0: u64 = CR0_EM | CR0_TS | CR0_NW | CR0_CD;

const CR4_PAE: u64 = 1 << 5;
const CR4_OSFXSR: u64 = 1 << 9;
const CR4_OSXMMEXCPT: u64 = 1 << 10;
const CR4_UMIP: u64 = 1 << 11;
const CR4_VMXE: u64 = 1 << 13;
const CR4_SMXE: u64 = 1 << 14;
const CR4_FSGSBASE: u64 = 1 << 16;
const CR4_PCIDE: u64 = 1 << 17;
const CR4_OSXSAVE: u64 = 1 << 18;
const CR4_SMEP: u64 = 1 << 20;
const CR4_SMAP: u64 = 1 << 21;
const CR4_PKE: u64 = 1 << 22;
const CR4_CET: u64 = 1 << 23;
const CR4_PKS: u64 = 1 << 24;
const CR4_LA57: u64 = 1 << 12;
pub const CPU_REQUIRED_CR4: u64 = CR4_PAE | CR4_OSFXSR | CR4_OSXMMEXCPT;
pub const CPU_FORBIDDEN_CR4: u64 = CR4_LA57 | CR4_VMXE | CR4_SMXE | CR4_PKE | CR4_CET | CR4_PKS;

const EFER_SCE: u64 = 1 << 0;
const EFER_LME: u64 = 1 << 8;
const EFER_LMA: u64 = 1 << 10;
const EFER_NXE: u64 = 1 << 11;
const EFER_SVME: u64 = 1 << 12;
const EFER_LMSLE: u64 = 1 << 13;
const EFER_FFXSR: u64 = 1 << 14;
const EFER_TCE: u64 = 1 << 15;
const EFER_ALLOWED: u64 =
    EFER_SCE | EFER_LME | EFER_LMA | EFER_NXE | EFER_SVME | EFER_LMSLE | EFER_FFXSR | EFER_TCE;
pub const CPU_REQUIRED_EFER: u64 = EFER_LME | EFER_LMA | EFER_NXE;

pub const CPU_MSR_EFER: u32 = 1 << 0;
pub const CPU_MSR_APIC_BASE: u32 = 1 << 1;
pub const CPU_MSR_PAT: u32 = 1 << 2;
pub const CPU_MSR_MTRR_CAP: u32 = 1 << 3;
pub const CPU_MSR_MTRR_DEF_TYPE: u32 = 1 << 4;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CpuIdentity {
    pub family: u16,
    pub model: u16,
    pub stepping: u8,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CpuDiscovery {
    pub vendor: [u8; 12],
    pub brand: [u8; 48],
    pub max_basic_leaf: u32,
    pub max_extended_leaf: u32,
    pub leaf1_eax: u32,
    pub leaf1_ebx: u32,
    pub leaf1_ecx: u32,
    pub leaf1_edx: u32,
    pub leaf4_eax: u32,
    pub leaf4_ebx: u32,
    pub leaf4_ecx: u32,
    pub leaf4_edx: u32,
    pub leaf6_eax: u32,
    pub leaf7_ebx: u32,
    pub leaf7_ecx: u32,
    pub leaf7_edx: u32,
    pub leaf_a_eax: u32,
    pub leaf_b0_eax: u32,
    pub leaf_b0_ebx: u32,
    pub leaf_b0_ecx: u32,
    pub leaf_b0_edx: u32,
    pub leaf_d0_eax: u32,
    pub leaf_d0_ebx: u32,
    pub leaf_d0_ecx: u32,
    pub leaf_d0_edx: u32,
    pub ext1_ecx: u32,
    pub ext1_edx: u32,
    pub ext6_ecx: u32,
    pub ext7_edx: u32,
    pub ext8_eax: u32,
    pub ext1f_eax: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CpuControlState {
    pub cr0: u64,
    pub cr4: u64,
    pub efer: u64,
    pub xcr0: u64,
    pub apic_base: u64,
    pub pat: u64,
    pub mtrr_cap: u64,
    pub mtrr_def_type: u64,
    pub msr_read_mask: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CpuPolicySnapshot {
    pub discovery: CpuDiscovery,
    pub control: CpuControlState,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CpuPolicyError {
    Vendor,
    LeafRange,
    Identity,
    Brand,
    Feature,
    AddressWidth,
    Topology,
    ControlRegister,
    FeatureState,
    Xsave,
    Efer,
    MsrReadSet,
    ApicBase,
    Pat,
    Mtrr,
}

impl CpuPolicyError {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Vendor => "vendor",
            Self::LeafRange => "leaf_range",
            Self::Identity => "identity",
            Self::Brand => "brand",
            Self::Feature => "feature",
            Self::AddressWidth => "address_width",
            Self::Topology => "topology",
            Self::ControlRegister => "control_register",
            Self::FeatureState => "feature_state",
            Self::Xsave => "xsave",
            Self::Efer => "efer",
            Self::MsrReadSet => "msr_read_set",
            Self::ApicBase => "apic_base",
            Self::Pat => "pat",
            Self::Mtrr => "mtrr",
        }
    }
}

pub const fn decode_cpu_identity(signature: u32) -> CpuIdentity {
    let stepping = (signature & 0x0f) as u8;
    let base_model = ((signature >> 4) & 0x0f) as u16;
    let base_family = ((signature >> 8) & 0x0f) as u16;
    let extended_model = ((signature >> 16) & 0x0f) as u16;
    let extended_family = ((signature >> 20) & 0xff) as u16;
    let family = if base_family == 0x0f {
        base_family + extended_family
    } else {
        base_family
    };
    let model = if base_family == 0x06 || base_family == 0x0f {
        base_model | (extended_model << 4)
    } else {
        base_model
    };
    CpuIdentity {
        family,
        model,
        stepping,
    }
}

fn valid_brand(brand: &[u8; 48]) -> bool {
    let mut saw_printable = false;
    let mut saw_nul = false;
    for byte in brand {
        if *byte == 0 {
            saw_nul = true;
        } else if saw_nul || !(b' '..=b'~').contains(byte) {
            return false;
        } else if *byte != b' ' {
            saw_printable = true;
        }
    }
    saw_printable
}

fn valid_pat(pat: u64) -> bool {
    let mut index = 0;
    while index < 8 {
        let value = ((pat >> (index * 8)) & 0xff) as u8;
        if !matches!(value, 0 | 1 | 4 | 5 | 6 | 7) {
            return false;
        }
        index += 1;
    }
    true
}

pub fn validate_cpu_policy_snapshot(
    snapshot: &CpuPolicySnapshot,
) -> Result<CpuIdentity, CpuPolicyError> {
    let discovery = &snapshot.discovery;
    let control = &snapshot.control;
    if discovery.vendor != *b"AuthenticAMD" && discovery.vendor != *b"GenuineIntel" {
        return Err(CpuPolicyError::Vendor);
    }
    if discovery.max_basic_leaf < 7 || discovery.max_extended_leaf < 0x8000_0008 {
        return Err(CpuPolicyError::LeafRange);
    }
    let identity = decode_cpu_identity(discovery.leaf1_eax);
    if identity.family == 0 || identity.family > 0x10e || identity.model > 0xff {
        return Err(CpuPolicyError::Identity);
    }
    if !valid_brand(&discovery.brand) {
        return Err(CpuPolicyError::Brand);
    }
    if discovery.leaf1_edx & CPU_REQUIRED_LEAF1_EDX != CPU_REQUIRED_LEAF1_EDX
        || discovery.ext1_edx & CPU_REQUIRED_EXT1_EDX != CPU_REQUIRED_EXT1_EDX
    {
        return Err(CpuPolicyError::Feature);
    }
    let physical_width = discovery.ext8_eax & 0xff;
    let linear_width = (discovery.ext8_eax >> 8) & 0xff;
    if !(36..=52).contains(&physical_width) || linear_width != 48 {
        return Err(CpuPolicyError::AddressWidth);
    }
    let logical_processors = (discovery.leaf1_ebx >> 16) & 0xff;
    let leaf_b_logical = discovery.leaf_b0_ebx & 0xffff;
    if leaf_b_logical != 0 && discovery.leaf_b0_edx != discovery.leaf1_ebx >> 24
        || leaf_b_logical == 0
            && discovery.leaf1_edx & LEAF1_EDX_HTT != 0
            && logical_processors == 0
    {
        return Err(CpuPolicyError::Topology);
    }
    if control.cr0 & CPU_REQUIRED_CR0 != CPU_REQUIRED_CR0
        || control.cr0 & CPU_FORBIDDEN_CR0 != 0
        || control.cr4 & CPU_REQUIRED_CR4 != CPU_REQUIRED_CR4
        || control.cr4 & CPU_FORBIDDEN_CR4 != 0
    {
        return Err(CpuPolicyError::ControlRegister);
    }
    let support_gated = [
        (CR4_UMIP, discovery.leaf7_ecx & LEAF7_ECX_UMIP != 0),
        (CR4_FSGSBASE, discovery.leaf7_ebx & LEAF7_EBX_FSGSBASE != 0),
        (CR4_PCIDE, discovery.leaf1_ecx & LEAF1_ECX_PCID != 0),
        (CR4_SMEP, discovery.leaf7_ebx & LEAF7_EBX_SMEP != 0),
        (CR4_SMAP, discovery.leaf7_ebx & LEAF7_EBX_SMAP != 0),
    ];
    for (mask, supported) in support_gated {
        if control.cr4 & mask != 0 && !supported {
            return Err(CpuPolicyError::FeatureState);
        }
    }
    let xsave = discovery.leaf1_ecx & LEAF1_ECX_XSAVE != 0;
    let osxsave = discovery.leaf1_ecx & LEAF1_ECX_OSXSAVE != 0;
    let cr4_osxsave = control.cr4 & CR4_OSXSAVE != 0;
    if osxsave != cr4_osxsave || osxsave && !xsave {
        return Err(CpuPolicyError::FeatureState);
    }
    if xsave {
        let supported_xcr0 =
            u64::from(discovery.leaf_d0_eax) | (u64::from(discovery.leaf_d0_edx) << 32);
        if supported_xcr0 & 0b11 != 0b11
            || osxsave && (control.xcr0 & 0b11 != 0b11 || control.xcr0 & !supported_xcr0 != 0)
            || !osxsave && control.xcr0 != 0
        {
            return Err(CpuPolicyError::Xsave);
        }
    } else if discovery.leaf_d0_eax != 0
        || discovery.leaf_d0_ebx != 0
        || discovery.leaf_d0_ecx != 0
        || discovery.leaf_d0_edx != 0
        || control.xcr0 != 0
        || cr4_osxsave
    {
        return Err(CpuPolicyError::Xsave);
    }
    if control.efer & CPU_REQUIRED_EFER != CPU_REQUIRED_EFER
        || control.efer & !EFER_ALLOWED != 0
        || control.efer & EFER_SVME != 0
    {
        return Err(CpuPolicyError::Efer);
    }
    let expected_msr_mask =
        CPU_MSR_EFER | CPU_MSR_APIC_BASE | CPU_MSR_PAT | CPU_MSR_MTRR_CAP | CPU_MSR_MTRR_DEF_TYPE;
    if control.msr_read_mask != expected_msr_mask {
        return Err(CpuPolicyError::MsrReadSet);
    }
    let physical_mask = if physical_width == 64 {
        u64::MAX
    } else {
        (1_u64 << physical_width) - 1
    };
    let apic_address = control.apic_base & 0x000f_ffff_ffff_f000;
    if control.apic_base & !(0x000f_ffff_ffff_f000 | 0x0d00) != 0
        || control.apic_base & 0x02ff != 0
        || control.apic_base & (1 << 11) == 0
        || control.apic_base & (1 << 10) != 0 && discovery.leaf1_ecx & LEAF1_ECX_X2APIC == 0
        || apic_address == 0
        || apic_address & !physical_mask != 0
    {
        return Err(CpuPolicyError::ApicBase);
    }
    if !valid_pat(control.pat) {
        return Err(CpuPolicyError::Pat);
    }
    const MTRR_CAP_ALLOWED: u64 = 0xff | (1 << 8) | (1 << 10) | (1 << 11);
    const MTRR_DEF_ALLOWED: u64 = 0xff | (1 << 10) | (1 << 11);
    let variable_ranges = control.mtrr_cap & 0xff;
    let default_type = control.mtrr_def_type & 0xff;
    if control.mtrr_cap & !MTRR_CAP_ALLOWED != 0
        || variable_ranges == 0
        || variable_ranges > 32
        || control.mtrr_def_type & !MTRR_DEF_ALLOWED != 0
        || !matches!(default_type, 0 | 1 | 4 | 5 | 6 | 7)
        || control.mtrr_def_type & (1 << 11) == 0
        || control.mtrr_def_type & (1 << 10) != 0 && control.mtrr_cap & (1 << 8) == 0
    {
        return Err(CpuPolicyError::Mtrr);
    }
    Ok(identity)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DescriptorState {
    pub gdt_base: u64,
    pub gdt_limit: u16,
    pub idt_base: u64,
    pub idt_limit: u16,
    pub tss_base: u64,
    pub rsp0: u64,
    pub ist1_bottom: u64,
    pub ist1_top: u64,
    pub ist2_bottom: u64,
    pub ist2_top: u64,
    pub code_selector: u16,
    pub data_selector: u16,
    pub task_selector: u16,
    pub installed_gate_count: u16,
    pub interrupts_enabled: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DescriptorError {
    Table,
    Selector,
    Stack,
    InterruptState,
}

fn validate_descriptor_state_with_gate_count(
    state: &DescriptorState,
    expected_gate_count: u16,
) -> Result<(), DescriptorError> {
    if state.gdt_base == 0
        || state.idt_base == 0
        || state.tss_base == 0
        || !is_canonical_x86_64(state.gdt_base)
        || !is_canonical_x86_64(state.idt_base)
        || !is_canonical_x86_64(state.tss_base)
        || state.gdt_limit != GDT_LIMIT
        || state.idt_limit != IDT_LIMIT
        || state.installed_gate_count != expected_gate_count
    {
        return Err(DescriptorError::Table);
    }
    if state.code_selector != KERNEL_CODE_SELECTOR
        || state.data_selector != KERNEL_DATA_SELECTOR
        || state.task_selector != KERNEL_TSS_SELECTOR
    {
        return Err(DescriptorError::Selector);
    }
    let valid_stack = |bottom: u64, top: u64| {
        bottom != 0
            && top.checked_sub(bottom) == Some(IST_STACK_BYTES)
            && bottom.is_multiple_of(16)
            && top.is_multiple_of(16)
            && is_canonical_x86_64(bottom)
            && is_canonical_x86_64(top - 1)
    };
    if state.rsp0 == 0
        || !state.rsp0.is_multiple_of(16)
        || !is_canonical_x86_64(state.rsp0)
        || !valid_stack(state.ist1_bottom, state.ist1_top)
        || !valid_stack(state.ist2_bottom, state.ist2_top)
        || state.ist1_top > state.ist2_bottom && state.ist2_top > state.ist1_bottom
        || state.rsp0 == state.ist1_top
        || state.rsp0 == state.ist2_top
    {
        return Err(DescriptorError::Stack);
    }
    if state.interrupts_enabled {
        return Err(DescriptorError::InterruptState);
    }
    Ok(())
}

pub fn validate_descriptor_state(state: &DescriptorState) -> Result<(), DescriptorError> {
    validate_descriptor_state_with_gate_count(state, INSTALLED_EXCEPTION_GATE_COUNT)
}

pub fn validate_xstate_exception_descriptor_state(
    state: &DescriptorState,
) -> Result<(), DescriptorError> {
    validate_descriptor_state_with_gate_count(state, INSTALLED_XSTATE_EXCEPTION_GATE_COUNT)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TrapObservation {
    pub vector: u64,
    pub error_code: u64,
    pub rip: u64,
    pub code_selector: u64,
    pub rflags: u64,
    pub saved_rsp: u64,
    pub data_selector: u64,
    pub cr2: u64,
    pub handler_rsp: u64,
    pub depth: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TrapExpectation {
    pub vector: u64,
    pub error_code: u64,
    pub fault_rip: u64,
    pub resume_rip: u64,
    pub expected_cr2: Option<u64>,
    pub ist_bottom: u64,
    pub ist_top: u64,
    pub terminal: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TrapDisposition {
    ResumeAt(u64),
    Halt,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TrapError {
    Vector,
    ErrorCode,
    InstructionPointer,
    CodeSelector,
    DataSelector,
    Flags,
    SavedStack,
    HandlerStack,
    FaultAddress,
    Depth,
    Expectation,
}

pub fn validate_trap_observation(
    observation: &TrapObservation,
    expectation: &TrapExpectation,
) -> Result<TrapDisposition, TrapError> {
    if !matches!(expectation.vector, 3 | 6 | 7 | 8 | 14 | 16 | 19)
        || !is_canonical_x86_64(expectation.fault_rip)
        || !is_canonical_x86_64(expectation.resume_rip)
        || expectation.ist_top <= expectation.ist_bottom
        || expectation.ist_top - expectation.ist_bottom != IST_STACK_BYTES
        || expectation.terminal != matches!(expectation.vector, 7 | 8)
    {
        return Err(TrapError::Expectation);
    }
    if observation.vector != expectation.vector {
        return Err(TrapError::Vector);
    }
    if observation.error_code != expectation.error_code {
        return Err(TrapError::ErrorCode);
    }
    if observation.rip != expectation.fault_rip || !is_canonical_x86_64(observation.rip) {
        return Err(TrapError::InstructionPointer);
    }
    if observation.code_selector != u64::from(KERNEL_CODE_SELECTOR) {
        return Err(TrapError::CodeSelector);
    }
    if observation.data_selector != u64::from(KERNEL_DATA_SELECTOR) {
        return Err(TrapError::DataSelector);
    }
    if observation.rflags & RFLAGS_RESERVED_ONE == 0
        || observation.rflags & (RFLAGS_INTERRUPT_ENABLE | RFLAGS_DIRECTION) != 0
    {
        return Err(TrapError::Flags);
    }
    if observation.saved_rsp == 0 || !is_canonical_x86_64(observation.saved_rsp) {
        return Err(TrapError::SavedStack);
    }
    if observation.handler_rsp < expectation.ist_bottom
        || observation.handler_rsp >= expectation.ist_top
        || !is_canonical_x86_64(observation.handler_rsp)
    {
        return Err(TrapError::HandlerStack);
    }
    if expectation
        .expected_cr2
        .is_some_and(|value| observation.cr2 != value)
    {
        return Err(TrapError::FaultAddress);
    }
    if observation.depth != 1 {
        return Err(TrapError::Depth);
    }
    if expectation.terminal {
        Ok(TrapDisposition::Halt)
    } else {
        Ok(TrapDisposition::ResumeAt(expectation.resume_rip))
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PanicDisposition {
    Primary,
    Nested,
}

pub struct PanicState {
    depth: AtomicU32,
    last_code: AtomicU32,
}

impl PanicState {
    pub const fn new() -> Self {
        Self {
            depth: AtomicU32::new(0),
            last_code: AtomicU32::new(0),
        }
    }

    pub fn begin(&self, code: PanicCode) -> PanicDisposition {
        self.last_code.store(code as u32, Ordering::Release);
        if self.depth.fetch_add(1, Ordering::AcqRel) == 0 {
            PanicDisposition::Primary
        } else {
            PanicDisposition::Nested
        }
    }

    pub fn depth(&self) -> u32 {
        self.depth.load(Ordering::Acquire)
    }

    pub fn last_code(&self) -> u32 {
        self.last_code.load(Ordering::Acquire)
    }
}

impl Default for PanicState {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EntryError {
    NullHandoff,
    HandoffAlignment,
    HandoffLength,
    HandoffRange,
    NoncanonicalHandoff,
    Magic,
    NullStack,
    StackAlignment,
    NoncanonicalStack,
    Decode,
    KernelProfile,
    EntryMismatch,
    EntryOffset,
    StackMismatch,
    HandoffAddressMismatch,
    PageTableMismatch,
    FlagState,
}

impl EntryError {
    pub const fn panic_code(self) -> PanicCode {
        match self {
            Self::NullStack | Self::StackAlignment | Self::NoncanonicalStack => {
                PanicCode::StackContract
            }
            Self::Decode => PanicCode::HandoffDecode,
            Self::KernelProfile => PanicCode::HandoffProfile,
            Self::EntryMismatch
            | Self::EntryOffset
            | Self::StackMismatch
            | Self::HandoffAddressMismatch
            | Self::PageTableMismatch
            | Self::FlagState => PanicCode::RuntimeContinuity,
            _ => PanicCode::HandoffEnvelope,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FramebufferSpec {
    pub physical_base: u64,
    pub byte_count: u64,
    pub width: u32,
    pub height: u32,
    pub stride: u32,
    pub pixel_format: u32,
    pub foreground: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ValidatedEntry {
    pub core: CoreRecord,
    pub framebuffer: Option<FramebufferSpec>,
}

pub const fn is_canonical_x86_64(address: u64) -> bool {
    let sign = (address >> 47) & 1;
    let upper = address >> 48;
    (sign == 0 && upper == 0) || (sign == 1 && upper == 0xffff)
}

pub fn validate_entry_envelope(
    handoff_address: usize,
    handoff_length: usize,
    magic: u64,
    stack_top: usize,
) -> Result<(), EntryError> {
    if handoff_address == 0 {
        return Err(EntryError::NullHandoff);
    }
    if !handoff_address.is_multiple_of(8) {
        return Err(EntryError::HandoffAlignment);
    }
    if !(poole_handoff::HEADER_BYTES..=poole_handoff::MAX_TOTAL_BYTES).contains(&handoff_length) {
        return Err(EntryError::HandoffLength);
    }
    let handoff_end = handoff_address
        .checked_add(handoff_length - 1)
        .ok_or(EntryError::HandoffRange)?;
    if !is_canonical_x86_64(handoff_address as u64) || !is_canonical_x86_64(handoff_end as u64) {
        return Err(EntryError::NoncanonicalHandoff);
    }
    if magic != HANDOFF_MAGIC_U64 {
        return Err(EntryError::Magic);
    }
    if stack_top == 0 {
        return Err(EntryError::NullStack);
    }
    if !stack_top.is_multiple_of(16) {
        return Err(EntryError::StackAlignment);
    }
    if !is_canonical_x86_64(stack_top as u64) {
        return Err(EntryError::NoncanonicalStack);
    }
    Ok(())
}

pub fn validate_handoff(
    bytes: &[u8],
    runtime_entry: u64,
    stack_top: u64,
) -> Result<ValidatedEntry, EntryError> {
    let handoff = poole_handoff::decode(bytes).map_err(|_| EntryError::Decode)?;
    validate_kernel_entry_profile(&handoff).map_err(|_| EntryError::KernelProfile)?;
    validate_handoff_continuity(&handoff, runtime_entry, stack_top)
}

pub fn validate_development_handoff(
    bytes: &[u8],
    runtime_entry: u64,
    stack_top: u64,
) -> Result<ValidatedEntry, EntryError> {
    let handoff = poole_handoff::decode(bytes).map_err(|_| EntryError::Decode)?;
    validate_development_transfer_profile(&handoff)?;
    validate_handoff_continuity(&handoff, runtime_entry, stack_top)
}

fn validate_handoff_continuity(
    handoff: &Handoff<'_>,
    runtime_entry: u64,
    stack_top: u64,
) -> Result<ValidatedEntry, EntryError> {
    let core = handoff.core().map_err(|_| EntryError::Decode)?;
    if core.kernel_entry_virtual != runtime_entry {
        return Err(EntryError::EntryMismatch);
    }
    if runtime_entry.checked_sub(core.kernel_virtual_base) != Some(ENTRY_OFFSET) {
        return Err(EntryError::EntryOffset);
    }
    if core.initial_stack_top_virtual != stack_top {
        return Err(EntryError::StackMismatch);
    }
    Ok(ValidatedEntry {
        core,
        framebuffer: framebuffer_spec(handoff),
    })
}

fn validate_development_transfer_profile(handoff: &Handoff<'_>) -> Result<(), EntryError> {
    let has_framebuffer = handoff.record(RECORD_FRAMEBUFFER).is_some();
    let expected_features = FEATURE_CORE
        | FEATURE_MEMORY_MAP
        | FEATURE_LOADED_ARTIFACTS
        | if has_framebuffer {
            FEATURE_FRAMEBUFFER
        } else {
            0
        };
    let expected_required = FEATURE_CORE | FEATURE_MEMORY_MAP | FEATURE_LOADED_ARTIFACTS;
    let expected_record_count = if has_framebuffer { 4 } else { 3 };
    let header = handoff.header();
    let core = handoff.core().map_err(|_| EntryError::Decode)?;
    let artifacts = handoff
        .record(RECORD_LOADED_ARTIFACTS)
        .ok_or(EntryError::KernelProfile)?;
    if header.features != expected_features
        || header.required_features != expected_required
        || header.record_count != expected_record_count
        || core.boot_flags != DEVELOPMENT_MODE | BOOT_SERVICES_EXITED
        || core.uefi_system_table_physical != 0
        || core.uefi_runtime_services_physical != 0
        || artifacts.descriptor.element_count != revalidation::PROFILE_ROLE_COUNT
        || validate_kernel_entry_profile(handoff).is_ok()
    {
        return Err(EntryError::KernelProfile);
    }
    Ok(())
}

pub fn validate_runtime_state(
    entry: &ValidatedEntry,
    handoff_address: u64,
    handoff_length: usize,
    observed_stack_top: u64,
    observed_cr3: u64,
    observed_rflags: u64,
) -> Result<(), EntryError> {
    if entry.core.handoff_virtual_base != handoff_address
        || entry.core.handoff_byte_count != handoff_length as u64
    {
        return Err(EntryError::HandoffAddressMismatch);
    }
    if entry.core.initial_stack_top_virtual != observed_stack_top {
        return Err(EntryError::StackMismatch);
    }
    if observed_cr3 & (poole_handoff::PAGE_BYTES - 1) & !CR3_ALLOWED_LOW_BITS != 0
        || observed_cr3 & !(poole_handoff::PAGE_BYTES - 1) != entry.core.page_table_root_physical
    {
        return Err(EntryError::PageTableMismatch);
    }
    if observed_rflags & (RFLAGS_INTERRUPT_ENABLE | RFLAGS_DIRECTION) != 0 {
        return Err(EntryError::FlagState);
    }
    Ok(())
}

fn read_u32(bytes: &[u8], offset: usize) -> u32 {
    u32::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
    ])
}

fn read_u64(bytes: &[u8], offset: usize) -> u64 {
    u64::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
        bytes[offset + 4],
        bytes[offset + 5],
        bytes[offset + 6],
        bytes[offset + 7],
    ])
}

fn framebuffer_spec(handoff: &Handoff<'_>) -> Option<FramebufferSpec> {
    let record = handoff.record(RECORD_FRAMEBUFFER)?;
    let payload = record.payload;
    if payload.len() != poole_handoff::FRAMEBUFFER_BYTES {
        return None;
    }
    let physical_base = read_u64(payload, 0);
    let byte_count = read_u64(payload, 8);
    if !framebuffer_identity_range_is_safe(physical_base, byte_count) {
        return None;
    }
    Some(FramebufferSpec {
        physical_base,
        byte_count,
        width: read_u32(payload, 16),
        height: read_u32(payload, 20),
        stride: read_u32(payload, 24),
        pixel_format: read_u32(payload, 28),
        foreground: read_u32(payload, 32) | read_u32(payload, 36) | read_u32(payload, 40),
    })
}

pub fn framebuffer_identity_range_is_safe(physical_base: u64, byte_count: u64) -> bool {
    if physical_base == 0
        || !physical_base.is_multiple_of(4)
        || byte_count == 0
        || !byte_count.is_multiple_of(4)
    {
        return false;
    }
    let Some(last_byte) = physical_base.checked_add(byte_count - 1) else {
        return false;
    };
    is_canonical_x86_64(physical_base) && is_canonical_x86_64(last_byte)
}

pub trait ByteSink {
    fn write_byte(&mut self, byte: u8);
}

pub struct EarlyRing {
    bytes: [AtomicU8; EARLY_LOG_CAPACITY],
    writes: AtomicUsize,
}

impl EarlyRing {
    pub const fn new() -> Self {
        Self {
            bytes: [const { AtomicU8::new(0) }; EARLY_LOG_CAPACITY],
            writes: AtomicUsize::new(0),
        }
    }

    pub fn push(&self, byte: u8) {
        let sequence = self.writes.fetch_add(1, Ordering::AcqRel);
        self.bytes[sequence % EARLY_LOG_CAPACITY].store(byte, Ordering::Release);
    }

    pub fn write(&self, bytes: &[u8]) {
        for byte in bytes {
            self.push(*byte);
        }
    }

    pub fn total_writes(&self) -> usize {
        self.writes.load(Ordering::Acquire)
    }

    pub fn snapshot(&self, output: &mut [u8]) -> usize {
        let total = self.total_writes();
        let count = total.min(EARLY_LOG_CAPACITY).min(output.len());
        let start = total.saturating_sub(count);
        for (index, target) in output[..count].iter_mut().enumerate() {
            *target = self.bytes[(start + index) % EARLY_LOG_CAPACITY].load(Ordering::Acquire);
        }
        count
    }
}

impl Default for EarlyRing {
    fn default() -> Self {
        Self::new()
    }
}

pub struct RingSink<'a>(pub &'a EarlyRing);

impl ByteSink for RingSink<'_> {
    fn write_byte(&mut self, byte: u8) {
        self.0.push(byte);
    }
}

pub struct EarlyLogger<S> {
    sink: S,
}

impl<S: ByteSink> EarlyLogger<S> {
    pub const fn new(sink: S) -> Self {
        Self { sink }
    }

    pub fn write_bytes(&mut self, bytes: &[u8]) {
        for byte in bytes {
            self.sink.write_byte(*byte);
        }
    }

    pub fn write_str(&mut self, text: &str) {
        self.write_bytes(text.as_bytes());
    }

    pub fn write_hex_u64(&mut self, value: u64) {
        const HEX: &[u8; 16] = b"0123456789ABCDEF";
        self.write_str("0x");
        for shift in (0..16).rev() {
            self.sink
                .write_byte(HEX[((value >> (shift * 4)) & 0xf) as usize]);
        }
    }

    pub fn write_hex_bytes(&mut self, bytes: &[u8]) {
        const HEX: &[u8; 16] = b"0123456789ABCDEF";
        for byte in bytes {
            self.sink.write_byte(HEX[(byte >> 4) as usize]);
            self.sink.write_byte(HEX[(byte & 0x0f) as usize]);
        }
    }

    pub fn write_decimal_u64(&mut self, mut value: u64) {
        let mut digits = [0u8; 20];
        let mut used = 0usize;
        loop {
            digits[used] = b'0' + (value % 10) as u8;
            used += 1;
            value /= 10;
            if value == 0 {
                break;
            }
        }
        while used != 0 {
            used -= 1;
            self.sink.write_byte(digits[used]);
        }
    }

    pub fn into_inner(self) -> S {
        self.sink
    }
}

pub struct Framebuffer<'a> {
    pixels: *mut u32,
    pixel_count: usize,
    width: usize,
    height: usize,
    stride: usize,
    foreground: u32,
    background: u32,
    cursor_x: usize,
    cursor_y: usize,
    _borrow: PhantomData<&'a mut [u32]>,
}

impl<'a> Framebuffer<'a> {
    pub fn from_slice(
        pixels: &'a mut [u32],
        width: usize,
        height: usize,
        stride: usize,
        foreground: u32,
        background: u32,
    ) -> Option<Self> {
        let pointer = pixels.as_mut_ptr();
        let count = pixels.len();
        // SAFETY: the pointer and length originate from the uniquely borrowed slice.
        unsafe {
            Self::from_raw_parts(
                pointer, count, width, height, stride, foreground, background,
            )
        }
    }

    /// Creates a volatile framebuffer sink over an already mapped writable range.
    ///
    /// # Safety
    ///
    /// `pixels..pixels + pixel_count` must remain mapped, writable, and exclusively
    /// borrowed for `'a`. The mapping must not be revoked while the sink exists.
    pub unsafe fn from_raw_parts(
        pixels: *mut u32,
        pixel_count: usize,
        width: usize,
        height: usize,
        stride: usize,
        foreground: u32,
        background: u32,
    ) -> Option<Self> {
        let required = stride.checked_mul(height)?;
        if pixels.is_null() || width < 6 || height < 8 || stride < width || required > pixel_count {
            return None;
        }
        Some(Self {
            pixels,
            pixel_count,
            width,
            height,
            stride,
            foreground,
            background,
            cursor_x: 0,
            cursor_y: 0,
            _borrow: PhantomData,
        })
    }

    fn write_pixel(&mut self, x: usize, y: usize, color: u32) {
        let Some(index) = y
            .checked_mul(self.stride)
            .and_then(|row| row.checked_add(x))
        else {
            return;
        };
        if x >= self.width || y >= self.height || index >= self.pixel_count {
            return;
        }
        // SAFETY: construction validated the complete stride-by-height range.
        unsafe { ptr::write_volatile(self.pixels.add(index), color) };
    }

    fn newline(&mut self) {
        self.cursor_x = 0;
        self.cursor_y += 8;
        if self.cursor_y + 7 >= self.height {
            self.cursor_y = 0;
        }
    }

    fn draw_glyph(&mut self, byte: u8) {
        if self.cursor_x + 5 >= self.width {
            self.newline();
        }
        let rows = glyph_rows(byte);
        for (row, bits) in rows.iter().enumerate() {
            for column in 0..5 {
                let color = if bits & (1 << (4 - column)) != 0 {
                    self.foreground
                } else {
                    self.background
                };
                self.write_pixel(self.cursor_x + column, self.cursor_y + row, color);
            }
        }
        self.cursor_x += 6;
    }
}

impl ByteSink for Framebuffer<'_> {
    fn write_byte(&mut self, byte: u8) {
        match byte {
            b'\n' => self.newline(),
            b'\r' => self.cursor_x = 0,
            value => self.draw_glyph(value.to_ascii_uppercase()),
        }
    }
}

fn glyph_rows(byte: u8) -> [u8; 7] {
    match byte {
        b' ' => [0, 0, 0, 0, 0, 0, 0],
        b'-' => [0, 0, 0, 0b11111, 0, 0, 0],
        b'.' => [0, 0, 0, 0, 0, 0b00110, 0b00110],
        b':' => [0, 0b00110, 0b00110, 0, 0b00110, 0b00110, 0],
        b'/' => [0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0, 0],
        b'0' => [
            0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110,
        ],
        b'1' => [
            0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110,
        ],
        b'2' => [
            0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111,
        ],
        b'3' => [
            0b11110, 0b00001, 0b00001, 0b01110, 0b00001, 0b00001, 0b11110,
        ],
        b'4' => [
            0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010,
        ],
        b'5' => [
            0b11111, 0b10000, 0b10000, 0b11110, 0b00001, 0b00001, 0b11110,
        ],
        b'6' => [
            0b01110, 0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110,
        ],
        b'7' => [
            0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000,
        ],
        b'8' => [
            0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110,
        ],
        b'9' => [
            0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00001, 0b01110,
        ],
        b'A' => [
            0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001,
        ],
        b'B' => [
            0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110,
        ],
        b'C' => [
            0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110,
        ],
        b'D' => [
            0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110,
        ],
        b'E' => [
            0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111,
        ],
        b'F' => [
            0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000,
        ],
        b'G' => [
            0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110,
        ],
        b'H' => [
            0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001,
        ],
        b'I' => [
            0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110,
        ],
        b'J' => [
            0b00111, 0b00010, 0b00010, 0b00010, 0b10010, 0b10010, 0b01100,
        ],
        b'K' => [
            0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001,
        ],
        b'L' => [
            0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111,
        ],
        b'M' => [
            0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001,
        ],
        b'N' => [
            0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001,
        ],
        b'O' => [
            0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110,
        ],
        b'P' => [
            0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000,
        ],
        b'Q' => [
            0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101,
        ],
        b'R' => [
            0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001,
        ],
        b'S' => [
            0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110,
        ],
        b'T' => [
            0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100,
        ],
        b'U' => [
            0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110,
        ],
        b'V' => [
            0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100,
        ],
        b'W' => [
            0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b10101, 0b01010,
        ],
        b'X' => [
            0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001,
        ],
        b'Y' => [
            0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100,
        ],
        b'Z' => [
            0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111,
        ],
        _ => [
            0b11111, 0b10001, 0b10101, 0b10101, 0b10001, 0b10001, 0b11111,
        ],
    }
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;
    use std::vec::Vec;

    #[derive(Default)]
    struct TestSink(Vec<u8>);

    impl ByteSink for TestSink {
        fn write_byte(&mut self, byte: u8) {
            self.0.push(byte);
        }
    }

    #[test]
    fn canonical_address_rules_cover_both_halves() {
        assert!(is_canonical_x86_64(0x0000_7fff_ffff_ffff));
        assert!(is_canonical_x86_64(0xffff_8000_0000_0000));
        assert!(!is_canonical_x86_64(0x0000_8000_0000_0000));
        assert!(!is_canonical_x86_64(0xffff_7fff_ffff_ffff));
        assert!(!is_canonical_x86_64(0x0001_0000_0000_0000));
    }

    fn descriptor_state() -> DescriptorState {
        DescriptorState {
            gdt_base: 0xffff_ffff_8003_0000,
            gdt_limit: GDT_LIMIT,
            idt_base: 0xffff_ffff_8003_1000,
            idt_limit: IDT_LIMIT,
            tss_base: 0xffff_ffff_8003_2000,
            rsp0: 0xffff_ffff_8004_9000,
            ist1_bottom: 0xffff_ffff_8003_4000,
            ist1_top: 0xffff_ffff_8003_6000,
            ist2_bottom: 0xffff_ffff_8003_6000,
            ist2_top: 0xffff_ffff_8003_8000,
            code_selector: KERNEL_CODE_SELECTOR,
            data_selector: KERNEL_DATA_SELECTOR,
            task_selector: KERNEL_TSS_SELECTOR,
            installed_gate_count: INSTALLED_EXCEPTION_GATE_COUNT,
            interrupts_enabled: false,
        }
    }

    fn cpu_policy_snapshot() -> CpuPolicySnapshot {
        let mut brand = [b' '; 48];
        brand[..29].copy_from_slice(b"QEMU Virtual CPU version 2.5+");
        CpuPolicySnapshot {
            discovery: CpuDiscovery {
                vendor: *b"AuthenticAMD",
                brand,
                max_basic_leaf: 0x0d,
                max_extended_leaf: 0x8000_0008,
                leaf1_eax: 0x0000_0f61,
                leaf1_ebx: 1 << 16,
                leaf1_ecx: 0,
                leaf1_edx: CPU_REQUIRED_LEAF1_EDX,
                leaf4_eax: 0,
                leaf4_ebx: 0,
                leaf4_ecx: 0,
                leaf4_edx: 0,
                leaf6_eax: 0,
                leaf7_ebx: 0,
                leaf7_ecx: 0,
                leaf7_edx: 0,
                leaf_a_eax: 0,
                leaf_b0_eax: 0,
                leaf_b0_ebx: 0,
                leaf_b0_ecx: 0,
                leaf_b0_edx: 0,
                leaf_d0_eax: 0,
                leaf_d0_ebx: 0,
                leaf_d0_ecx: 0,
                leaf_d0_edx: 0,
                ext1_ecx: 0,
                ext1_edx: CPU_REQUIRED_EXT1_EDX,
                ext6_ecx: 0,
                ext7_edx: 0,
                ext8_eax: 0x0000_3030,
                ext1f_eax: 0,
            },
            control: CpuControlState {
                cr0: CPU_REQUIRED_CR0,
                cr4: CPU_REQUIRED_CR4,
                efer: CPU_REQUIRED_EFER,
                xcr0: 0,
                apic_base: 0xfee0_0900,
                pat: 0x0007_0406_0007_0406,
                mtrr_cap: 0x508,
                mtrr_def_type: 0xc06,
                msr_read_mask: CPU_MSR_EFER
                    | CPU_MSR_APIC_BASE
                    | CPU_MSR_PAT
                    | CPU_MSR_MTRR_CAP
                    | CPU_MSR_MTRR_DEF_TYPE,
            },
        }
    }

    #[test]
    fn decodes_base_and_extended_cpu_identity_fields() {
        assert_eq!(
            decode_cpu_identity(0x00b4_0f40),
            CpuIdentity {
                family: 0x1a,
                model: 0x44,
                stepping: 0,
            }
        );
        assert_eq!(
            decode_cpu_identity(0x0003_06a9),
            CpuIdentity {
                family: 6,
                model: 0x3a,
                stepping: 9,
            }
        );
    }

    #[test]
    fn accepts_bounded_read_only_cpu_policy_snapshot() {
        assert_eq!(
            validate_cpu_policy_snapshot(&cpu_policy_snapshot()),
            Ok(CpuIdentity {
                family: 0x0f,
                model: 6,
                stepping: 1,
            })
        );
    }

    #[test]
    fn cpu_policy_rejects_missing_baseline_and_bad_widths() {
        let mut snapshot = cpu_policy_snapshot();
        snapshot.discovery.leaf1_edx &= !LEAF1_EDX_SSE2;
        assert_eq!(
            validate_cpu_policy_snapshot(&snapshot),
            Err(CpuPolicyError::Feature)
        );
        snapshot = cpu_policy_snapshot();
        snapshot.discovery.ext8_eax = 0x0000_3930;
        assert_eq!(
            validate_cpu_policy_snapshot(&snapshot),
            Err(CpuPolicyError::AddressWidth)
        );
    }

    #[test]
    fn cpu_policy_rejects_unsupported_control_features_and_xsave_conflicts() {
        let mut snapshot = cpu_policy_snapshot();
        snapshot.control.cr4 |= CR4_SMEP;
        assert_eq!(
            validate_cpu_policy_snapshot(&snapshot),
            Err(CpuPolicyError::FeatureState)
        );
        snapshot = cpu_policy_snapshot();
        snapshot.discovery.leaf1_ecx = LEAF1_ECX_XSAVE | LEAF1_ECX_OSXSAVE;
        snapshot.discovery.leaf_d0_eax = 0b111;
        snapshot.control.cr4 |= CR4_OSXSAVE;
        snapshot.control.xcr0 = 0b101;
        assert_eq!(
            validate_cpu_policy_snapshot(&snapshot),
            Err(CpuPolicyError::Xsave)
        );
    }

    #[test]
    fn cpu_policy_rejects_msr_read_set_and_register_payload_faults() {
        let mut snapshot = cpu_policy_snapshot();
        snapshot.control.msr_read_mask &= !CPU_MSR_PAT;
        assert_eq!(
            validate_cpu_policy_snapshot(&snapshot),
            Err(CpuPolicyError::MsrReadSet)
        );
        snapshot = cpu_policy_snapshot();
        snapshot.control.apic_base &= !(1 << 11);
        assert_eq!(
            validate_cpu_policy_snapshot(&snapshot),
            Err(CpuPolicyError::ApicBase)
        );
        snapshot = cpu_policy_snapshot();
        snapshot.control.pat = 0x0007_0406_0007_0306;
        assert_eq!(
            validate_cpu_policy_snapshot(&snapshot),
            Err(CpuPolicyError::Pat)
        );
        snapshot = cpu_policy_snapshot();
        snapshot.control.mtrr_def_type &= !(1 << 11);
        assert_eq!(
            validate_cpu_policy_snapshot(&snapshot),
            Err(CpuPolicyError::Mtrr)
        );
    }

    #[test]
    fn accepts_bounded_bsp_descriptor_state() {
        assert_eq!(validate_descriptor_state(&descriptor_state()), Ok(()));
    }

    #[test]
    fn descriptor_state_rejects_selector_stack_and_interrupt_faults() {
        let mut state = descriptor_state();
        state.task_selector = 0x20;
        assert_eq!(
            validate_descriptor_state(&state),
            Err(DescriptorError::Selector)
        );
        state = descriptor_state();
        state.ist2_bottom = state.ist1_bottom;
        assert_eq!(
            validate_descriptor_state(&state),
            Err(DescriptorError::Stack)
        );
        state = descriptor_state();
        state.interrupts_enabled = true;
        assert_eq!(
            validate_descriptor_state(&state),
            Err(DescriptorError::InterruptState)
        );
    }

    fn trap_observation() -> TrapObservation {
        TrapObservation {
            vector: 6,
            error_code: 0,
            rip: 0xffff_ffff_8000_a000,
            code_selector: u64::from(KERNEL_CODE_SELECTOR),
            rflags: RFLAGS_RESERVED_ONE,
            saved_rsp: 0xffff_ffff_8004_8ff8,
            data_selector: u64::from(KERNEL_DATA_SELECTOR),
            cr2: 0,
            handler_rsp: 0xffff_ffff_8003_5f00,
            depth: 1,
        }
    }

    fn trap_expectation() -> TrapExpectation {
        TrapExpectation {
            vector: 6,
            error_code: 0,
            fault_rip: 0xffff_ffff_8000_a000,
            resume_rip: 0xffff_ffff_8000_a002,
            expected_cr2: None,
            ist_bottom: 0xffff_ffff_8003_4000,
            ist_top: 0xffff_ffff_8003_6000,
            terminal: false,
        }
    }

    #[test]
    fn accepts_uniform_returning_trap_frame() {
        assert_eq!(
            validate_trap_observation(&trap_observation(), &trap_expectation()),
            Ok(TrapDisposition::ResumeAt(0xffff_ffff_8000_a002))
        );
    }

    #[test]
    fn trap_frame_rejects_corrupt_selectors_flags_stack_and_cr2() {
        let expectation = trap_expectation();
        let mut observation = trap_observation();
        observation.code_selector = 0x10;
        assert_eq!(
            validate_trap_observation(&observation, &expectation),
            Err(TrapError::CodeSelector)
        );
        observation = trap_observation();
        observation.rflags |= RFLAGS_INTERRUPT_ENABLE;
        assert_eq!(
            validate_trap_observation(&observation, &expectation),
            Err(TrapError::Flags)
        );
        observation = trap_observation();
        observation.handler_rsp = expectation.ist_top;
        assert_eq!(
            validate_trap_observation(&observation, &expectation),
            Err(TrapError::HandlerStack)
        );
        observation = trap_observation();
        observation.vector = 14;
        observation.cr2 = 0xffff_ffff_8004_0000;
        let page_fault = TrapExpectation {
            vector: 14,
            expected_cr2: Some(0xffff_ffff_8004_1000),
            ..expectation
        };
        assert_eq!(
            validate_trap_observation(&observation, &page_fault),
            Err(TrapError::FaultAddress)
        );
    }

    #[test]
    fn parses_only_frozen_development_scenario_selectors() {
        assert_eq!(
            DevelopmentTrapScenario::from_selector(1),
            Some(DevelopmentTrapScenario::Returning)
        );
        assert_eq!(
            DevelopmentTrapScenario::from_selector(4),
            Some(DevelopmentTrapScenario::CpuPolicy)
        );
        assert_eq!(
            DevelopmentTrapScenario::from_selector(5),
            Some(DevelopmentTrapScenario::XstatePolicy)
        );
        assert_eq!(
            DevelopmentTrapScenario::from_selector(6),
            Some(DevelopmentTrapScenario::XstateException)
        );
        assert_eq!(
            DevelopmentTrapScenario::from_selector(7),
            Some(DevelopmentTrapScenario::PrivilegeMsrPolicy)
        );
        assert_eq!(
            DevelopmentTrapScenario::from_selector(8),
            Some(DevelopmentTrapScenario::PhysicalMemory)
        );
        assert_eq!(
            DevelopmentTrapScenario::from_selector(9),
            Some(DevelopmentTrapScenario::VirtualMemory)
        );
        assert_eq!(
            DevelopmentTrapScenario::from_selector(10),
            Some(DevelopmentTrapScenario::ActiveVirtualMemory)
        );
        assert_eq!(DevelopmentTrapScenario::from_selector(11), None);
    }

    #[test]
    fn accepts_valid_entry_envelope() {
        assert_eq!(
            validate_entry_envelope(
                0xffff_9000_0000_0000,
                4096,
                HANDOFF_MAGIC_U64,
                0xffff_9000_0010_0000
            ),
            Ok(())
        );
    }

    #[test]
    fn rejects_null_and_misaligned_handoff() {
        assert_eq!(
            validate_entry_envelope(0, 4096, HANDOFF_MAGIC_U64, 0x1000),
            Err(EntryError::NullHandoff)
        );
        assert_eq!(
            validate_entry_envelope(0x1001, 4096, HANDOFF_MAGIC_U64, 0x2000),
            Err(EntryError::HandoffAlignment)
        );
    }

    #[test]
    fn rejects_bad_handoff_length_and_range() {
        assert_eq!(
            validate_entry_envelope(0x1000, 1, HANDOFF_MAGIC_U64, 0x2000),
            Err(EntryError::HandoffLength)
        );
        assert_eq!(
            validate_entry_envelope(usize::MAX - 255, 512, HANDOFF_MAGIC_U64, 0x2000,),
            Err(EntryError::HandoffRange)
        );
    }

    #[test]
    fn rejects_wrong_magic() {
        assert_eq!(
            validate_entry_envelope(0x1000, 4096, 0, 0x2000),
            Err(EntryError::Magic)
        );
    }

    #[test]
    fn rejects_bad_stack_contract() {
        assert_eq!(
            validate_entry_envelope(0x1000, 4096, HANDOFF_MAGIC_U64, 0),
            Err(EntryError::NullStack)
        );
        assert_eq!(
            validate_entry_envelope(0x1000, 4096, HANDOFF_MAGIC_U64, 0x2008),
            Err(EntryError::StackAlignment)
        );
    }

    #[test]
    fn ring_preserves_written_order() {
        let ring = EarlyRing::new();
        ring.write(b"POOLE");
        let mut output = [0u8; 8];
        assert_eq!(ring.snapshot(&mut output), 5);
        assert_eq!(&output[..5], b"POOLE");
    }

    #[test]
    fn ring_wraps_to_latest_bytes() {
        let ring = EarlyRing::new();
        for index in 0..EARLY_LOG_CAPACITY + 7 {
            ring.push((index & 0xff) as u8);
        }
        let mut output = [0u8; 7];
        assert_eq!(ring.snapshot(&mut output), 7);
        for (index, value) in output.iter().enumerate() {
            assert_eq!(*value, ((EARLY_LOG_CAPACITY + index) & 0xff) as u8);
        }
    }

    #[test]
    fn bounded_logger_formats_hex_and_decimal() {
        let mut logger = EarlyLogger::new(TestSink::default());
        logger.write_hex_u64(0x1234);
        logger.write_str("/");
        logger.write_decimal_u64(18_446_744_073_709_551_615);
        logger.write_str("/");
        logger.write_hex_bytes(&[0xab, 0xcd, 0xef]);
        let output = logger.into_inner().0;
        assert_eq!(output, b"0x0000000000001234/18446744073709551615/ABCDEF");
    }

    #[test]
    fn runtime_state_binds_handoff_stack_cr3_and_flags() {
        let entry = ValidatedEntry {
            core: CoreRecord {
                boot_flags: DEVELOPMENT_MODE | BOOT_SERVICES_EXITED,
                kernel_physical_base: 0x0100_0000,
                kernel_physical_size: 0x40000,
                kernel_virtual_base: 0xffff_ffff_8000_0000,
                kernel_virtual_size: 0x40000,
                kernel_entry_virtual: 0xffff_ffff_8000_8000,
                initial_stack_top_virtual: 0xffff_ffff_8004_9000,
                page_table_root_physical: 0x0200_0000,
                handoff_physical_base: 0x0300_0000,
                handoff_virtual_base: 0xffff_ffff_8005_0000,
                handoff_byte_count: 5008,
                uefi_system_table_physical: 0,
                uefi_runtime_services_physical: 0,
                boot_attempt: 0,
                boot_attempt_limit: 3,
                boot_slot: 1,
                selected_entry: 1,
                uefi_revision: 0x0002_0046,
            },
            framebuffer: None,
        };
        assert_eq!(
            validate_runtime_state(
                &entry,
                0xffff_ffff_8005_0000,
                5008,
                0xffff_ffff_8004_9000,
                0x0200_0018,
                0x2,
            ),
            Ok(())
        );
        assert_eq!(
            validate_runtime_state(
                &entry,
                0xffff_ffff_8005_0000,
                5008,
                0xffff_ffff_8004_9000,
                0x0200_1000,
                0x2,
            ),
            Err(EntryError::PageTableMismatch)
        );
        assert_eq!(
            validate_runtime_state(
                &entry,
                0xffff_ffff_8005_0000,
                5008,
                0xffff_ffff_8004_9000,
                0x0200_0000,
                RFLAGS_INTERRUPT_ENABLE,
            ),
            Err(EntryError::FlagState)
        );
    }

    #[test]
    fn panic_state_distinguishes_nested_entry() {
        let state = PanicState::new();
        assert_eq!(state.begin(PanicCode::RustPanic), PanicDisposition::Primary);
        assert_eq!(
            state.begin(PanicCode::UnexpectedReturn),
            PanicDisposition::Nested
        );
        assert_eq!(state.depth(), 2);
        assert_eq!(state.last_code(), PanicCode::UnexpectedReturn as u32);
    }

    #[test]
    fn framebuffer_rejects_invalid_geometry() {
        let mut pixels = [0u32; 64];
        assert!(Framebuffer::from_slice(&mut pixels, 8, 8, 7, 1, 0).is_none());
    }

    #[test]
    fn framebuffer_identity_range_rejects_unsafe_addresses() {
        assert!(framebuffer_identity_range_is_safe(0x8000_0000, 4096));
        assert!(!framebuffer_identity_range_is_safe(0, 4096));
        assert!(!framebuffer_identity_range_is_safe(0x8000_0002, 4096));
        assert!(!framebuffer_identity_range_is_safe(0x8000_0000, 4095));
        assert!(!framebuffer_identity_range_is_safe(
            0x0000_ffff_ffff_f000,
            8192
        ));
        assert!(!framebuffer_identity_range_is_safe(u64::MAX - 3, 8));
    }

    #[test]
    fn framebuffer_draws_inside_declared_bounds() {
        let mut pixels = [0u32; 16 * 16];
        {
            let mut framebuffer = Framebuffer::from_slice(&mut pixels, 16, 16, 16, 0x00ff_ffff, 0)
                .expect("valid framebuffer");
            framebuffer.write_byte(b'A');
            framebuffer.write_byte(b'\n');
            framebuffer.write_byte(b'?');
        }
        assert!(pixels.iter().any(|pixel| *pixel == 0x00ff_ffff));
        assert_eq!(pixels.len(), 256);
    }
}
