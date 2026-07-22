use core::arch::asm;
use core::mem::size_of;
use core::ptr::{
    addr_of, addr_of_mut, read_unaligned, write_bytes, write_unaligned, write_volatile,
};
use core::sync::atomic::{Ordering, compiler_fence};

use poolekernel::{
    ByteSink, CPU_MSR_APIC_BASE, CPU_MSR_EFER, CPU_MSR_MTRR_CAP, CPU_MSR_MTRR_DEF_TYPE,
    CPU_MSR_PAT, CpuControlState, CpuDiscovery, CpuPolicySnapshot, DescriptorState, GDT_LIMIT,
    IDT_LIMIT, INSTALLED_EXCEPTION_GATE_COUNT, INSTALLED_XSTATE_EXCEPTION_GATE_COUNT,
    IST_STACK_BYTES, KERNEL_CODE_SELECTOR, KERNEL_DATA_SELECTOR, KERNEL_TSS_SELECTOR,
    privilege_msr::{
        PrivilegeMsrSnapshot, READ_CSTAR, READ_EFER, READ_FS_BASE, READ_GS_BASE,
        READ_KERNEL_GS_BASE, READ_LSTAR, READ_MCG_CAP, READ_MCG_CTL, READ_MCG_STATUS, READ_SFMASK,
        READ_STAR, READ_TSC_AUX,
    },
    xstate::{
        AREA_BYTES, INITIAL_FCW, INITIAL_MXCSR, KernelSimdPolicy, SELECTED_XCR0, SaveFormat,
        SwitchStrategy, XstatePolicy, XstateProof, effective_mxcsr_mask,
    },
};

const COM1_BASE: u16 = 0x03f8;
const DEBUGCON_PORT: u16 = 0x0402;
const TRANSMIT_READY: u8 = 1 << 5;
const MAX_READY_POLLS: usize = 4096;
const IDT_ENTRY_COUNT: usize = 256;
const BREAKPOINT_VECTOR: usize = 3;
const INVALID_OPCODE_VECTOR: usize = 6;
const DEVICE_NOT_AVAILABLE_VECTOR: usize = 7;
const DOUBLE_FAULT_VECTOR: usize = 8;
const GENERAL_PROTECTION_VECTOR: usize = 13;
const PAGE_FAULT_VECTOR: usize = 14;
const X87_FLOATING_POINT_VECTOR: usize = 16;
const SIMD_FLOATING_POINT_VECTOR: usize = 19;
const FAULT_IST_INDEX: u8 = 1;
const DOUBLE_FAULT_IST_INDEX: u8 = 2;
const INTERRUPT_GATE_PRESENT_RING0: u8 = 0x8e;
const TSS_AVAILABLE_PRESENT_RING0: u64 = 0x89;

#[derive(Clone, Copy)]
#[repr(C, packed)]
struct DescriptorPointer {
    limit: u16,
    base: u64,
}

#[derive(Clone, Copy)]
#[repr(C, packed)]
struct IdtGate {
    offset_low: u16,
    selector: u16,
    ist: u8,
    attributes: u8,
    offset_middle: u16,
    offset_high: u32,
    reserved: u32,
}

impl IdtGate {
    const fn missing() -> Self {
        Self {
            offset_low: 0,
            selector: 0,
            ist: 0,
            attributes: 0,
            offset_middle: 0,
            offset_high: 0,
            reserved: 0,
        }
    }

    fn interrupt(handler: u64, ist: u8) -> Self {
        Self {
            offset_low: handler as u16,
            selector: KERNEL_CODE_SELECTOR,
            ist,
            attributes: INTERRUPT_GATE_PRESENT_RING0,
            offset_middle: (handler >> 16) as u16,
            offset_high: (handler >> 32) as u32,
            reserved: 0,
        }
    }
}

#[derive(Clone, Copy)]
#[repr(C, packed)]
struct TaskStateSegment {
    reserved0: u32,
    rsp: [u64; 3],
    reserved1: u64,
    ist: [u64; 7],
    reserved2: u64,
    reserved3: u16,
    iomap_base: u16,
}

impl TaskStateSegment {
    fn new(rsp0: u64, ist1: u64, ist2: u64) -> Self {
        let mut rsp = [0; 3];
        rsp[0] = rsp0;
        let mut ist = [0; 7];
        ist[0] = ist1;
        ist[1] = ist2;
        Self {
            reserved0: 0,
            rsp,
            reserved1: 0,
            ist,
            reserved2: 0,
            reserved3: 0,
            iomap_base: size_of::<Self>() as u16,
        }
    }
}

#[repr(C, align(16))]
struct AlignedGdt([u64; 5]);

#[repr(C, align(16))]
struct AlignedIdt([IdtGate; IDT_ENTRY_COUNT]);

#[repr(C, align(16))]
struct AlignedTss(TaskStateSegment);

#[repr(C, align(16))]
struct TrapStack([u8; IST_STACK_BYTES as usize]);

static mut GDT: AlignedGdt = AlignedGdt([0; 5]);
static mut IDT: AlignedIdt = AlignedIdt([IdtGate::missing(); IDT_ENTRY_COUNT]);
static mut TSS: AlignedTss = AlignedTss(TaskStateSegment {
    reserved0: 0,
    rsp: [0; 3],
    reserved1: 0,
    ist: [0; 7],
    reserved2: 0,
    reserved3: 0,
    iomap_base: 0,
});
static mut FAULT_STACK: TrapStack = TrapStack([0; IST_STACK_BYTES as usize]);
static mut DOUBLE_FAULT_STACK: TrapStack = TrapStack([0; IST_STACK_BYTES as usize]);

const IA32_APIC_BASE: u32 = 0x0000_001b;
const IA32_MTRR_CAP: u32 = 0x0000_00fe;
const IA32_PAT: u32 = 0x0000_0277;
const IA32_MTRR_DEF_TYPE: u32 = 0x0000_02ff;
const IA32_EFER: u32 = 0xc000_0080;
const IA32_MCG_CAP: u32 = 0x0000_0179;
const IA32_MCG_STATUS: u32 = 0x0000_017a;
const IA32_MCG_CTL: u32 = 0x0000_017b;
const IA32_STAR: u32 = 0xc000_0081;
const IA32_LSTAR: u32 = 0xc000_0082;
const IA32_CSTAR: u32 = 0xc000_0083;
const IA32_SFMASK: u32 = 0xc000_0084;
const IA32_FS_BASE: u32 = 0xc000_0100;
const IA32_GS_BASE: u32 = 0xc000_0101;
const IA32_KERNEL_GS_BASE: u32 = 0xc000_0102;
const IA32_TSC_AUX: u32 = 0xc000_0103;
const LEAF1_EDX_MCE: u32 = 1 << 7;
const LEAF1_EDX_MCA: u32 = 1 << 14;
const EXT1_EDX_SYSCALL: u32 = 1 << 11;
const EXT1_EDX_RDTSCP: u32 = 1 << 27;
const LEAF1_EDX_APIC: u32 = 1 << 9;
const LEAF1_EDX_MTRR: u32 = 1 << 12;
const LEAF1_EDX_PAT: u32 = 1 << 16;
const LEAF1_ECX_OSXSAVE: u32 = 1 << 27;
const LEAF1_ECX_XSAVE: u32 = 1 << 26;
const CR0_MP: u64 = 1 << 1;
const CR0_EM: u64 = 1 << 2;
const CR0_TS: u64 = 1 << 3;
const CR0_NE: u64 = 1 << 5;
const CR4_OSFXSR: u64 = 1 << 9;
const CR4_OSXMMEXCPT: u64 = 1 << 10;
const CR4_OSXSAVE: u64 = 1 << 18;

#[repr(C, align(64))]
struct XstateArea([u8; AREA_BYTES as usize]);

#[repr(C, align(16))]
struct FxsaveArea([u8; 512]);

static mut XSTATE_CANONICAL: XstateArea = XstateArea([0; AREA_BYTES as usize]);
static mut XSTATE_CONTEXT_A: XstateArea = XstateArea([0; AREA_BYTES as usize]);
static mut XSTATE_CONTEXT_B: XstateArea = XstateArea([0; AREA_BYTES as usize]);
static mut XSTATE_FXSAVE: FxsaveArea = FxsaveArea([0; 512]);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum XstateHardwareError {
    Unsupported,
    AreaSize,
    Configuration,
    RoundTrip,
    Clear,
}

impl XstateHardwareError {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Unsupported => "unsupported",
            Self::AreaSize => "area_size",
            Self::Configuration => "configuration",
            Self::RoundTrip => "round_trip",
            Self::Clear => "clear",
        }
    }
}

#[derive(Clone, Copy)]
struct CpuidRegisters {
    eax: u32,
    ebx: u32,
    ecx: u32,
    edx: u32,
}

fn cpuid(leaf: u32, subleaf: u32) -> CpuidRegisters {
    let value = core::arch::x86_64::__cpuid_count(leaf, subleaf);
    CpuidRegisters {
        eax: value.eax,
        ebx: value.ebx,
        ecx: value.ecx,
        edx: value.edx,
    }
}

unsafe fn read_cr0() -> u64 {
    let value: u64;
    // SAFETY: PKCPU1 calls this only at CPL0 after PKXFER1; the instruction is read-only.
    unsafe { asm!("mov {}, cr0", out(reg) value, options(nomem, nostack, preserves_flags)) };
    value
}

unsafe fn read_cr4() -> u64 {
    let value: u64;
    // SAFETY: PKCPU1 calls this only at CPL0 after PKXFER1; the instruction is read-only.
    unsafe { asm!("mov {}, cr4", out(reg) value, options(nomem, nostack, preserves_flags)) };
    value
}

unsafe fn write_cr0(value: u64) {
    // SAFETY: PKXSTATE1 runs at CPL0 and writes only its frozen MP/EM/TS/NE policy.
    unsafe { asm!("mov cr0, {}", in(reg) value, options(nostack, preserves_flags)) };
}

unsafe fn write_cr4(value: u64) {
    // SAFETY: PKXSTATE1 runs at CPL0 after CPUID reports XSAVE and enables only OS-owned state.
    unsafe { asm!("mov cr4, {}", in(reg) value, options(nostack, preserves_flags)) };
}

unsafe fn read_msr(msr: u32) -> u64 {
    let low: u32;
    let high: u32;
    // SAFETY: each caller gates this privileged read through the corresponding CPUID feature.
    unsafe {
        asm!(
            "rdmsr",
            in("ecx") msr,
            out("eax") low,
            out("edx") high,
            options(nomem, nostack, preserves_flags)
        )
    };
    u64::from(low) | (u64::from(high) << 32)
}

unsafe fn read_efer() -> u64 {
    // SAFETY: long mode and the PKCPU1 baseline require IA32_EFER to exist.
    unsafe { read_msr(IA32_EFER) }
}

unsafe fn read_apic_base() -> u64 {
    // SAFETY: the caller requires CPUID.01H:EDX.APIC before this typed read.
    unsafe { read_msr(IA32_APIC_BASE) }
}

unsafe fn read_pat() -> u64 {
    // SAFETY: the caller requires CPUID.01H:EDX.PAT before this typed read.
    unsafe { read_msr(IA32_PAT) }
}

unsafe fn read_mtrr_cap() -> u64 {
    // SAFETY: the caller requires CPUID.01H:EDX.MTRR before this typed read.
    unsafe { read_msr(IA32_MTRR_CAP) }
}

unsafe fn read_mtrr_default_type() -> u64 {
    // SAFETY: the caller requires CPUID.01H:EDX.MTRR before this typed read.
    unsafe { read_msr(IA32_MTRR_DEF_TYPE) }
}

unsafe fn read_xcr0() -> u64 {
    let low: u32;
    let high: u32;
    // SAFETY: the caller requires CPUID.01H:ECX.OSXSAVE, which reflects CR4.OSXSAVE.
    unsafe {
        asm!(
            "xgetbv",
            in("ecx") 0_u32,
            out("eax") low,
            out("edx") high,
            options(nomem, nostack, preserves_flags)
        )
    };
    u64::from(low) | (u64::from(high) << 32)
}

unsafe fn write_xcr0(value: u64) {
    // SAFETY: the caller validates XCR0 against CPUID.0DH and the architectural dependencies.
    unsafe {
        asm!(
            "xsetbv",
            in("ecx") 0_u32,
            in("eax") value as u32,
            in("edx") (value >> 32) as u32,
            options(nomem, nostack, preserves_flags)
        )
    };
}

unsafe fn xsave_area(pointer: *mut u8, mask: u64) {
    // SAFETY: callers provide a writable 64-byte-aligned area sized for the selected mask.
    unsafe {
        asm!(
            "xsave64 [{}]",
            in(reg) pointer,
            in("eax") mask as u32,
            in("edx") (mask >> 32) as u32,
            options(nostack)
        )
    };
}

unsafe fn xrstor_area(pointer: *const u8, mask: u64) {
    // SAFETY: callers provide a validated standard-format area and a CPUID-supported mask.
    unsafe {
        asm!(
            "xrstor64 [{}]",
            in(reg) pointer,
            in("eax") mask as u32,
            in("edx") (mask >> 32) as u32,
            options(readonly, nostack)
        )
    };
}

unsafe fn fxsave_area(pointer: *mut u8) {
    // SAFETY: callers provide a writable 16-byte-aligned 512-byte area.
    unsafe { asm!("fxsave64 [{}]", in(reg) pointer, options(nostack)) };
}

unsafe fn load_xmm0(pointer: *const u8) {
    // SAFETY: the pointer names a readable 16-byte pattern and PKXSTATE1 owns XMM0 here.
    unsafe { asm!("movdqu xmm0, [{}]", in(reg) pointer, options(readonly, nostack)) };
}

unsafe fn store_xmm0(pointer: *mut u8) {
    // SAFETY: the pointer names a writable 16-byte observation buffer.
    unsafe { asm!("movdqu [{}], xmm0", in(reg) pointer, options(nostack)) };
}

unsafe fn read_fcw() -> u16 {
    let mut value = 0_u16;
    // SAFETY: `value` is a writable two-byte stack object.
    unsafe { asm!("fnstcw [{}]", in(reg) addr_of_mut!(value), options(nostack)) };
    value
}

unsafe fn read_mxcsr() -> u32 {
    let mut value = 0_u32;
    // SAFETY: `value` is a writable four-byte stack object.
    unsafe { asm!("stmxcsr [{}]", in(reg) addr_of_mut!(value), options(nostack)) };
    value
}

unsafe fn write_mxcsr(value: &u32) {
    // SAFETY: the caller masks unsupported bits and supplies a readable four-byte object.
    unsafe { asm!("ldmxcsr [{}]", in(reg) value, options(readonly, nostack)) };
}

fn all_zero(pointer: *const u8, length: usize) -> bool {
    let mut index = 0;
    while index < length {
        // SAFETY: callers pass one of the static areas with its exact declared length.
        if unsafe { pointer.add(index).read_volatile() } != 0 {
            return false;
        }
        index += 1;
    }
    true
}

pub unsafe fn run_xstate_policy() -> Result<XstateProof, XstateHardwareError> {
    let leaf1 = cpuid(1, 0);
    if leaf1.ecx & LEAF1_ECX_XSAVE == 0 {
        return Err(XstateHardwareError::Unsupported);
    }
    let leaf_d0_before = cpuid(0x0d, 0);
    let leaf_d1 = cpuid(0x0d, 1);
    let supported_xcr0 = u64::from(leaf_d0_before.eax) | (u64::from(leaf_d0_before.edx) << 32);
    if supported_xcr0 & SELECTED_XCR0 != SELECTED_XCR0 {
        return Err(XstateHardwareError::Unsupported);
    }
    // SAFETY: support checks above establish the only architectural writes in PKXSTATE1.
    let initial_cr0 = unsafe { read_cr0() };
    // SAFETY: PKXSTATE1 executes at CPL0 after PKXFER1.
    let initial_cr4 = unsafe { read_cr4() };
    let initial_xcr0 = if leaf1.ecx & LEAF1_ECX_OSXSAVE != 0 {
        // SAFETY: CPUID reports that CR4.OSXSAVE already permits XGETBV.
        unsafe { read_xcr0() }
    } else {
        0
    };
    let configured_cr0 = (initial_cr0 | CR0_MP | CR0_NE) & !(CR0_EM | CR0_TS);
    let configured_cr4 = initial_cr4 | CR4_OSFXSR | CR4_OSXMMEXCPT | CR4_OSXSAVE;
    // SAFETY: each value is restricted to the frozen policy above.
    unsafe { write_cr0(configured_cr0) };
    // SAFETY: CPUID reports XSAVE and the selected mask has valid dependencies.
    unsafe { write_cr4(configured_cr4) };
    // SAFETY: CPUID.0DH reports x87 and SSE support.
    unsafe { write_xcr0(SELECTED_XCR0) };

    let configured_leaf1 = cpuid(1, 0);
    let leaf_d0 = cpuid(0x0d, 0);
    // SAFETY: CR4.OSXSAVE is now enabled.
    let configured_xcr0 = unsafe { read_xcr0() };
    if configured_leaf1.ecx & LEAF1_ECX_OSXSAVE == 0
        || configured_xcr0 != SELECTED_XCR0
        || !(576..=AREA_BYTES).contains(&leaf_d0.ebx)
        || leaf_d0.ecx < leaf_d0.ebx
    {
        return Err(XstateHardwareError::Configuration);
    }

    // SAFETY: selector 5 is single-BSP and owns these private statics until terminal halt.
    let canonical = unsafe { addr_of_mut!(XSTATE_CANONICAL.0).cast::<u8>() };
    // SAFETY: selector 5 is single-BSP and owns these private statics until terminal halt.
    let context_a = unsafe { addr_of_mut!(XSTATE_CONTEXT_A.0).cast::<u8>() };
    // SAFETY: selector 5 is single-BSP and owns these private statics until terminal halt.
    let context_b = unsafe { addr_of_mut!(XSTATE_CONTEXT_B.0).cast::<u8>() };
    // SAFETY: selector 5 is single-BSP and owns these private statics until terminal halt.
    let fxsave = unsafe { addr_of_mut!(XSTATE_FXSAVE.0).cast::<u8>() };
    if !(canonical as u64).is_multiple_of(64)
        || !(context_a as u64).is_multiple_of(64)
        || !(context_b as u64).is_multiple_of(64)
    {
        return Err(XstateHardwareError::AreaSize);
    }
    // SAFETY: all four pointers name private, correctly sized PKXSTATE1 statics.
    unsafe {
        write_bytes(canonical, 0, AREA_BYTES as usize);
        write_bytes(context_a, 0, AREA_BYTES as usize);
        write_bytes(context_b, 0, AREA_BYTES as usize);
        write_bytes(fxsave, 0, 512);
    }
    compiler_fence(Ordering::SeqCst);

    // SAFETY: CR0/CR4/XCR0 now satisfy the x87/SSE ownership preconditions.
    unsafe { asm!("fninit", options(nomem, nostack)) };
    let requested_mxcsr = INITIAL_MXCSR;
    // SAFETY: INITIAL_MXCSR contains no reserved bit.
    unsafe { write_mxcsr(&requested_mxcsr) };
    // SAFETY: `fxsave` is a private 16-byte-aligned 512-byte area.
    unsafe { fxsave_area(fxsave) };
    // SAFETY: offset 28 is the architectural MXCSR_MASK u32 inside the FXSAVE area.
    let raw_mxcsr_mask = unsafe { read_unaligned(fxsave.add(28).cast::<u32>()) };
    if INITIAL_MXCSR & !effective_mxcsr_mask(raw_mxcsr_mask) != 0 {
        return Err(XstateHardwareError::Configuration);
    }

    // Encode a complete standard-format initial image rather than inheriting firmware state.
    // SAFETY: each field is inside the private 4,096-byte canonical area.
    unsafe {
        write_unaligned(canonical.cast::<u16>(), INITIAL_FCW);
        write_unaligned(canonical.add(24).cast::<u32>(), INITIAL_MXCSR);
        write_unaligned(
            canonical.add(28).cast::<u32>(),
            effective_mxcsr_mask(raw_mxcsr_mask),
        );
        write_unaligned(canonical.add(512).cast::<u64>(), SELECTED_XCR0);
    }
    compiler_fence(Ordering::SeqCst);
    // SAFETY: canonical is an initialized standard-format area and the mask is supported.
    unsafe { xrstor_area(canonical, SELECTED_XCR0) };
    // SAFETY: the x87 and SSE state is live after the canonical restore.
    let initial_fcw = unsafe { read_fcw() };
    // SAFETY: the x87 and SSE state is live after the canonical restore.
    let initial_mxcsr = unsafe { read_mxcsr() };

    let pattern_a = [0x11_u8; 16];
    let pattern_b = [0xa5_u8; 16];
    let mut observed_a = [0_u8; 16];
    let mut observed_b = [0_u8; 16];
    let mut observed_zero = [0xff_u8; 16];
    // SAFETY: the patterns and state areas meet the helper contracts.
    unsafe {
        load_xmm0(pattern_a.as_ptr());
        xsave_area(context_a, SELECTED_XCR0);
        load_xmm0(pattern_b.as_ptr());
        xsave_area(context_b, SELECTED_XCR0);
        xrstor_area(context_a, SELECTED_XCR0);
        store_xmm0(observed_a.as_mut_ptr());
        xrstor_area(context_b, SELECTED_XCR0);
        store_xmm0(observed_b.as_mut_ptr());
        xrstor_area(canonical, SELECTED_XCR0);
        store_xmm0(observed_zero.as_mut_ptr());
    }
    // SAFETY: the XSTATE_BV fields are within initialized, aligned XSAVE areas.
    let context_a_xstate_bv = unsafe { read_unaligned(context_a.add(512).cast::<u64>()) };
    // SAFETY: the XSTATE_BV fields are within initialized, aligned XSAVE areas.
    let context_b_xstate_bv = unsafe { read_unaligned(context_b.add(512).cast::<u64>()) };
    let context_a_match = observed_a == pattern_a;
    let context_b_match = observed_b == pattern_b;
    let canonical_xmm0_zero = observed_zero == [0; 16];
    if !context_a_match || !context_b_match {
        return Err(XstateHardwareError::RoundTrip);
    }
    if !canonical_xmm0_zero {
        return Err(XstateHardwareError::Clear);
    }

    // SAFETY: erase both per-context images and the capability scratch before reporting.
    unsafe {
        write_bytes(context_a, 0, AREA_BYTES as usize);
        write_bytes(context_b, 0, AREA_BYTES as usize);
        write_bytes(fxsave, 0, 512);
    }
    compiler_fence(Ordering::SeqCst);
    if !all_zero(context_a, AREA_BYTES as usize) || !all_zero(context_b, AREA_BYTES as usize) {
        return Err(XstateHardwareError::Clear);
    }

    Ok(XstateProof {
        policy: XstatePolicy {
            leaf1_ecx: configured_leaf1.ecx,
            leaf1_edx: configured_leaf1.edx,
            supported_xcr0,
            selected_xcr0: configured_xcr0,
            enabled_area_bytes: leaf_d0.ebx,
            maximum_area_bytes: leaf_d0.ecx,
            leaf_d1_eax: leaf_d1.eax,
            cr0: configured_cr0,
            cr4: configured_cr4,
            xss: 0,
            mxcsr_mask: raw_mxcsr_mask,
            area_address: context_a as u64,
            area_bytes: AREA_BYTES,
            save_format: SaveFormat::StandardXsave,
            switch_strategy: SwitchStrategy::Eager,
            kernel_simd: KernelSimdPolicy::Forbidden,
        },
        cr0_before: initial_cr0,
        cr4_before: initial_cr4,
        xcr0_before: initial_xcr0,
        initial_fcw,
        initial_mxcsr,
        context_a_xstate_bv,
        context_b_xstate_bv,
        context_a_match,
        context_b_match,
        canonical_xmm0_zero,
        context_image_zero_bytes: AREA_BYTES * 2,
        save_count: 2,
        restore_count: 4,
        state_write_count: 3,
        unexpected_nm_count: 0,
    })
}

pub unsafe fn observe_cpu_policy() -> CpuPolicySnapshot {
    let basic = cpuid(0, 0);
    let extended = cpuid(0x8000_0000, 0);
    let leaf1 = cpuid(1, 0);
    let leaf4 = cpuid(4, 0);
    let leaf6 = if basic.eax >= 6 {
        cpuid(6, 0)
    } else {
        cpuid(0, 0)
    };
    let leaf7 = cpuid(7, 0);
    let leaf_a = if basic.eax >= 0x0a {
        cpuid(0x0a, 0)
    } else {
        cpuid(0, 0)
    };
    let leaf_b0 = if basic.eax >= 0x0b {
        cpuid(0x0b, 0)
    } else {
        CpuidRegisters {
            eax: 0,
            ebx: 0,
            ecx: 0,
            edx: 0,
        }
    };
    let leaf_d0 = if basic.eax >= 0x0d && leaf1.ecx & (1 << 26) != 0 {
        cpuid(0x0d, 0)
    } else {
        CpuidRegisters {
            eax: 0,
            ebx: 0,
            ecx: 0,
            edx: 0,
        }
    };
    let ext1 = cpuid(0x8000_0001, 0);
    let ext6 = cpuid(0x8000_0006, 0);
    let ext7 = cpuid(0x8000_0007, 0);
    let ext8 = cpuid(0x8000_0008, 0);
    let ext1f = if extended.eax >= 0x8000_001f {
        cpuid(0x8000_001f, 0)
    } else {
        CpuidRegisters {
            eax: 0,
            ebx: 0,
            ecx: 0,
            edx: 0,
        }
    };
    let mut brand = [0_u8; 48];
    let mut brand_offset = 0;
    for leaf in 0x8000_0002..=0x8000_0004 {
        let value = cpuid(leaf, 0);
        for register in [value.eax, value.ebx, value.ecx, value.edx] {
            brand[brand_offset..brand_offset + 4].copy_from_slice(&register.to_le_bytes());
            brand_offset += 4;
        }
    }
    let mut vendor = [0_u8; 12];
    vendor[0..4].copy_from_slice(&basic.ebx.to_le_bytes());
    vendor[4..8].copy_from_slice(&basic.edx.to_le_bytes());
    vendor[8..12].copy_from_slice(&basic.ecx.to_le_bytes());

    let mut msr_read_mask = CPU_MSR_EFER;
    // SAFETY: the running x86-64 environment necessarily implements IA32_EFER.
    let efer = unsafe { read_efer() };
    let (apic_base, pat, mtrr_cap, mtrr_def_type) = (
        if leaf1.edx & LEAF1_EDX_APIC != 0 {
            msr_read_mask |= CPU_MSR_APIC_BASE;
            // SAFETY: CPUID reports the APIC MSR facility.
            unsafe { read_apic_base() }
        } else {
            0
        },
        if leaf1.edx & LEAF1_EDX_PAT != 0 {
            msr_read_mask |= CPU_MSR_PAT;
            // SAFETY: CPUID reports the PAT MSR facility.
            unsafe { read_pat() }
        } else {
            0
        },
        if leaf1.edx & LEAF1_EDX_MTRR != 0 {
            msr_read_mask |= CPU_MSR_MTRR_CAP;
            // SAFETY: CPUID reports the MTRR MSR facility.
            unsafe { read_mtrr_cap() }
        } else {
            0
        },
        if leaf1.edx & LEAF1_EDX_MTRR != 0 {
            msr_read_mask |= CPU_MSR_MTRR_DEF_TYPE;
            // SAFETY: CPUID reports the MTRR MSR facility.
            unsafe { read_mtrr_default_type() }
        } else {
            0
        },
    );
    let xcr0 = if leaf1.ecx & LEAF1_ECX_OSXSAVE != 0 {
        // SAFETY: OSXSAVE reports that XGETBV is enabled by CR4.OSXSAVE.
        unsafe { read_xcr0() }
    } else {
        0
    };
    CpuPolicySnapshot {
        discovery: CpuDiscovery {
            vendor,
            brand,
            max_basic_leaf: basic.eax,
            max_extended_leaf: extended.eax,
            leaf1_eax: leaf1.eax,
            leaf1_ebx: leaf1.ebx,
            leaf1_ecx: leaf1.ecx,
            leaf1_edx: leaf1.edx,
            leaf4_eax: leaf4.eax,
            leaf4_ebx: leaf4.ebx,
            leaf4_ecx: leaf4.ecx,
            leaf4_edx: leaf4.edx,
            leaf6_eax: leaf6.eax,
            leaf7_ebx: leaf7.ebx,
            leaf7_ecx: leaf7.ecx,
            leaf7_edx: leaf7.edx,
            leaf_a_eax: leaf_a.eax,
            leaf_b0_eax: leaf_b0.eax,
            leaf_b0_ebx: leaf_b0.ebx,
            leaf_b0_ecx: leaf_b0.ecx,
            leaf_b0_edx: leaf_b0.edx,
            leaf_d0_eax: leaf_d0.eax,
            leaf_d0_ebx: leaf_d0.ebx,
            leaf_d0_ecx: leaf_d0.ecx,
            leaf_d0_edx: leaf_d0.edx,
            ext1_ecx: ext1.ecx,
            ext1_edx: ext1.edx,
            ext6_ecx: ext6.ecx,
            ext7_edx: ext7.edx,
            ext8_eax: ext8.eax,
            ext1f_eax: ext1f.eax,
        },
        control: CpuControlState {
            // SAFETY: PKCPU1 runs at CPL0; these reads do not modify control state.
            cr0: unsafe { read_cr0() },
            // SAFETY: PKCPU1 runs at CPL0; these reads do not modify control state.
            cr4: unsafe { read_cr4() },
            efer,
            xcr0,
            apic_base,
            pat,
            mtrr_cap,
            mtrr_def_type,
            msr_read_mask,
        },
    }
}

pub unsafe fn observe_privilege_msr_policy() -> PrivilegeMsrSnapshot {
    let basic = cpuid(0, 0);
    let extended = cpuid(0x8000_0000, 0);
    let leaf1 = cpuid(1, 0);
    let ext1 = cpuid(0x8000_0001, 0);
    let leaf_a = if basic.eax >= 0x0a {
        cpuid(0x0a, 0)
    } else {
        CpuidRegisters {
            eax: 0,
            ebx: 0,
            ecx: 0,
            edx: 0,
        }
    };
    let ext22 = if extended.eax >= 0x8000_0022 {
        cpuid(0x8000_0022, 0)
    } else {
        CpuidRegisters {
            eax: 0,
            ebx: 0,
            ecx: 0,
            edx: 0,
        }
    };
    let mut vendor = [0_u8; 12];
    vendor[0..4].copy_from_slice(&basic.ebx.to_le_bytes());
    vendor[4..8].copy_from_slice(&basic.edx.to_le_bytes());
    vendor[8..12].copy_from_slice(&basic.ecx.to_le_bytes());

    let syscall = ext1.edx & EXT1_EDX_SYSCALL != 0;
    let rdtscp = ext1.edx & EXT1_EDX_RDTSCP != 0;
    let machine_check =
        leaf1.edx & (LEAF1_EDX_MCE | LEAF1_EDX_MCA) == LEAF1_EDX_MCE | LEAF1_EDX_MCA;
    let mut msr_read_mask = READ_EFER;
    // SAFETY: long mode requires EFER and this is a read-only observation.
    let efer = unsafe { read_msr(IA32_EFER) };
    let (star, lstar, cstar, sfmask) = if syscall {
        msr_read_mask |= READ_STAR | READ_LSTAR | READ_CSTAR | READ_SFMASK;
        // SAFETY: CPUID reports SYSCALL/SYSRET and therefore these linkage MSRs.
        unsafe {
            (
                read_msr(IA32_STAR),
                read_msr(IA32_LSTAR),
                read_msr(IA32_CSTAR),
                read_msr(IA32_SFMASK),
            )
        }
    } else {
        (0, 0, 0, 0)
    };
    msr_read_mask |= READ_FS_BASE | READ_GS_BASE | READ_KERNEL_GS_BASE;
    // SAFETY: these system-software MSRs are defined in 64-bit mode.
    let (fs_base, gs_base, kernel_gs_base) = unsafe {
        (
            read_msr(IA32_FS_BASE),
            read_msr(IA32_GS_BASE),
            read_msr(IA32_KERNEL_GS_BASE),
        )
    };
    let tsc_aux = if rdtscp {
        msr_read_mask |= READ_TSC_AUX;
        // SAFETY: CPUID reports RDTSCP and therefore TSC_AUX.
        unsafe { read_msr(IA32_TSC_AUX) }
    } else {
        0
    };
    let (mcg_cap, mcg_status, mcg_ctl) = if machine_check {
        msr_read_mask |= READ_MCG_CAP | READ_MCG_STATUS;
        // SAFETY: CPUID reports MCE and MCA; MCG_CAP and MCG_STATUS are present.
        let cap = unsafe { read_msr(IA32_MCG_CAP) };
        // SAFETY: CPUID reports the global MCA MSR set.
        let status = unsafe { read_msr(IA32_MCG_STATUS) };
        let control = if cap & (1 << 8) != 0 {
            msr_read_mask |= READ_MCG_CTL;
            // SAFETY: MCG_CAP.CTLP reports MCG_CTL as present.
            unsafe { read_msr(IA32_MCG_CTL) }
        } else {
            0
        };
        (cap, status, control)
    } else {
        (0, 0, 0)
    };

    PrivilegeMsrSnapshot {
        vendor,
        max_basic_leaf: basic.eax,
        max_extended_leaf: extended.eax,
        leaf1_edx: leaf1.edx,
        ext1_edx: ext1.edx,
        leaf_a_eax: leaf_a.eax,
        ext22_eax: ext22.eax,
        // SAFETY: the profile runs at CPL0 and this read does not modify CR4.
        cr4: unsafe { read_cr4() },
        efer,
        star,
        lstar,
        cstar,
        sfmask,
        fs_base,
        gs_base,
        kernel_gs_base,
        tsc_aux,
        mcg_cap,
        mcg_status,
        mcg_ctl,
        msr_read_mask,
    }
}

#[derive(Clone, Copy, Debug)]
#[repr(C)]
pub struct TrapFrame {
    pub r15: u64,
    pub r14: u64,
    pub r13: u64,
    pub r12: u64,
    pub r11: u64,
    pub r10: u64,
    pub r9: u64,
    pub r8: u64,
    pub rsi: u64,
    pub rdi: u64,
    pub rbp: u64,
    pub rdx: u64,
    pub rcx: u64,
    pub rbx: u64,
    pub rax: u64,
    pub vector: u64,
    pub error_code: u64,
    pub rip: u64,
    pub code_selector: u64,
    pub rflags: u64,
    pub rsp: u64,
    pub data_selector: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct XstateExceptionTransition {
    pub cr0: u64,
    pub cr4: u64,
    pub fcw_before: u16,
    pub fsw_before: u16,
    pub mxcsr_before: u32,
    pub fcw_after: u16,
    pub fsw_after: u16,
    pub mxcsr_after: u32,
}

pub unsafe fn install_descriptor_tables(rsp0: u64) -> DescriptorState {
    // SAFETY: the caller owns the single-BSP PKTRAP1 descriptor installation.
    unsafe { install_descriptor_tables_for_profile(rsp0, false) }
}

pub unsafe fn install_xstate_exception_descriptor_tables(rsp0: u64) -> DescriptorState {
    // SAFETY: the caller owns the single-BSP PKXEXC1 descriptor installation.
    unsafe { install_descriptor_tables_for_profile(rsp0, true) }
}

unsafe fn install_descriptor_tables_for_profile(
    rsp0: u64,
    include_xstate_exceptions: bool,
) -> DescriptorState {
    // SAFETY: single-entry BSP initialization is the sole accessor to these statics.
    let (gdt_base, idt_base, tss_base, ist1_bottom, ist2_bottom) = unsafe {
        (
            addr_of_mut!(GDT.0).cast::<u64>() as u64,
            addr_of_mut!(IDT.0).cast::<IdtGate>() as u64,
            addr_of_mut!(TSS.0) as u64,
            addr_of_mut!(FAULT_STACK.0).cast::<u8>() as u64,
            addr_of_mut!(DOUBLE_FAULT_STACK.0).cast::<u8>() as u64,
        )
    };
    let ist1_top = ist1_bottom + IST_STACK_BYTES;
    let ist2_top = ist2_bottom + IST_STACK_BYTES;

    let tss = TaskStateSegment::new(rsp0, ist1_top, ist2_top);
    // SAFETY: single-entry BSP initialization owns the writable static descriptor storage.
    unsafe { write_volatile(addr_of_mut!(TSS.0), tss) };

    let mut gdt = [0u64; 5];
    gdt[1] = 0x00af_9a00_0000_ffff;
    gdt[2] = 0x00cf_9200_0000_ffff;
    let tss_limit = (size_of::<TaskStateSegment>() - 1) as u64;
    gdt[3] = (tss_limit & 0xffff)
        | ((tss_base & 0x00ff_ffff) << 16)
        | (TSS_AVAILABLE_PRESENT_RING0 << 40)
        | (((tss_limit >> 16) & 0x0f) << 48)
        | (((tss_base >> 24) & 0xff) << 56);
    gdt[4] = tss_base >> 32;
    // SAFETY: the BSP has exclusive initialization ownership before LGDT/LTR.
    unsafe { write_volatile(addr_of_mut!(GDT.0), gdt) };

    // SAFETY: the zeroed table is not live until the final LIDT below.
    unsafe { write_bytes(addr_of_mut!(IDT.0).cast::<IdtGate>(), 0, IDT_ENTRY_COUNT) };
    for (vector, handler, ist) in [
        (
            BREAKPOINT_VECTOR,
            poole_trap_breakpoint as *const () as usize as u64,
            FAULT_IST_INDEX,
        ),
        (
            INVALID_OPCODE_VECTOR,
            poole_trap_invalid_opcode as *const () as usize as u64,
            FAULT_IST_INDEX,
        ),
        (
            DOUBLE_FAULT_VECTOR,
            poole_trap_double_fault as *const () as usize as u64,
            DOUBLE_FAULT_IST_INDEX,
        ),
        (
            GENERAL_PROTECTION_VECTOR,
            poole_trap_general_protection as *const () as usize as u64,
            FAULT_IST_INDEX,
        ),
        (
            PAGE_FAULT_VECTOR,
            poole_trap_page_fault as *const () as usize as u64,
            FAULT_IST_INDEX,
        ),
    ] {
        // SAFETY: each constant vector is unique and within the 256-entry table.
        unsafe {
            write_volatile(
                addr_of_mut!(IDT.0).cast::<IdtGate>().add(vector),
                IdtGate::interrupt(handler, ist),
            )
        };
    }
    if include_xstate_exceptions {
        for (vector, handler) in [
            (
                DEVICE_NOT_AVAILABLE_VECTOR,
                poole_trap_device_not_available as *const () as usize as u64,
            ),
            (
                X87_FLOATING_POINT_VECTOR,
                poole_trap_x87_floating_point as *const () as usize as u64,
            ),
            (
                SIMD_FLOATING_POINT_VECTOR,
                poole_trap_simd_floating_point as *const () as usize as u64,
            ),
        ] {
            // SAFETY: each extra PKXEXC1 vector is unique and within the live IDT.
            unsafe {
                write_volatile(
                    addr_of_mut!(IDT.0).cast::<IdtGate>().add(vector),
                    IdtGate::interrupt(handler, FAULT_IST_INDEX),
                )
            };
        }
    }

    let gdtr = DescriptorPointer {
        limit: GDT_LIMIT,
        base: gdt_base,
    };
    let idtr = DescriptorPointer {
        limit: IDT_LIMIT,
        base: idt_base,
    };
    // SAFETY: descriptors and dedicated stacks are fully initialized and mapped writable.
    unsafe { load_gdt_and_tss(addr_of!(gdtr)) };
    // SAFETY: the IDT contains valid ring-0 gates for the bounded exception set.
    unsafe {
        asm!(
            "lidt [{}]",
            in(reg) addr_of!(idtr),
            options(readonly, nostack, preserves_flags),
        )
    };

    let mut observed_gdtr = DescriptorPointer { limit: 0, base: 0 };
    let mut observed_idtr = DescriptorPointer { limit: 0, base: 0 };
    // SAFETY: outputs point to complete writable ten-byte pseudo-descriptors.
    unsafe {
        asm!(
            "sgdt [{}]",
            in(reg) addr_of_mut!(observed_gdtr),
            options(nostack, preserves_flags),
        );
        asm!(
            "sidt [{}]",
            in(reg) addr_of_mut!(observed_idtr),
            options(nostack, preserves_flags),
        );
    }
    let code_selector: u16;
    let data_selector: u16;
    let task_selector: u16;
    let rflags: u64;
    // SAFETY: these are read-only architectural state observations after table load.
    unsafe {
        asm!("mov {:x}, cs", out(reg) code_selector, options(nomem, nostack, preserves_flags));
        asm!("mov {:x}, ss", out(reg) data_selector, options(nomem, nostack, preserves_flags));
        asm!("str {:x}", out(reg) task_selector, options(nomem, nostack, preserves_flags));
        asm!("pushfq", "pop {}", out(reg) rflags, options(nomem, preserves_flags));
    }
    // SAFETY: packed fields are copied with explicit unaligned reads.
    let observed_gdt_base = unsafe { read_unaligned(addr_of!(observed_gdtr.base)) };
    // SAFETY: packed fields are copied with explicit unaligned reads.
    let observed_gdt_limit = unsafe { read_unaligned(addr_of!(observed_gdtr.limit)) };
    // SAFETY: packed fields are copied with explicit unaligned reads.
    let observed_idt_base = unsafe { read_unaligned(addr_of!(observed_idtr.base)) };
    // SAFETY: packed fields are copied with explicit unaligned reads.
    let observed_idt_limit = unsafe { read_unaligned(addr_of!(observed_idtr.limit)) };
    DescriptorState {
        gdt_base: observed_gdt_base,
        gdt_limit: observed_gdt_limit,
        idt_base: observed_idt_base,
        idt_limit: observed_idt_limit,
        tss_base,
        rsp0,
        ist1_bottom,
        ist1_top,
        ist2_bottom,
        ist2_top,
        code_selector,
        data_selector,
        task_selector,
        installed_gate_count: if include_xstate_exceptions {
            INSTALLED_XSTATE_EXCEPTION_GATE_COUNT
        } else {
            INSTALLED_EXCEPTION_GATE_COUNT
        },
        interrupts_enabled: rflags & (1 << 9) != 0,
    }
}

unsafe fn load_gdt_and_tss(gdtr: *const DescriptorPointer) {
    // SAFETY: the caller supplies a complete live GDT with code, data, and available TSS entries.
    unsafe {
        asm!(
            "lgdt [{gdtr}]",
            "mov ax, {data_selector}",
            "mov ds, ax",
            "mov es, ax",
            "mov ss, ax",
            "xor eax, eax",
            "mov fs, ax",
            "mov gs, ax",
            "push {code_selector}",
            "lea rax, [rip + 2f]",
            "push rax",
            "retfq",
            "2:",
            "mov ax, {tss_selector}",
            "ltr ax",
            gdtr = in(reg) gdtr,
            data_selector = const KERNEL_DATA_SELECTOR,
            code_selector = const KERNEL_CODE_SELECTOR,
            tss_selector = const KERNEL_TSS_SELECTOR,
            lateout("rax") _,
            options(preserves_flags),
        )
    };
}

pub unsafe fn arm_double_fault_delivery_failure() {
    // SAFETY: this terminal development scenario deliberately removes only the #GP gate.
    unsafe {
        write_volatile(
            addr_of_mut!(IDT.0)
                .cast::<IdtGate>()
                .add(GENERAL_PROTECTION_VECTOR),
            IdtGate::missing(),
        )
    };
    compiler_fence(Ordering::SeqCst);
}

pub fn read_cr2() -> u64 {
    let value: u64;
    // SAFETY: ring-0 exception dispatch owns this read-only CR2 observation.
    unsafe { asm!("mov {}, cr2", out(reg) value, options(nomem, nostack, preserves_flags)) };
    value
}

pub fn breakpoint_resume_address() -> u64 {
    poole_breakpoint_resume as *const () as usize as u64
}

pub fn invalid_opcode_fault_address() -> u64 {
    poole_invalid_opcode_fault as *const () as usize as u64
}

pub fn invalid_opcode_resume_address() -> u64 {
    poole_invalid_opcode_resume as *const () as usize as u64
}

pub fn page_fault_fault_address() -> u64 {
    poole_page_fault_origin as *const () as usize as u64
}

pub fn page_fault_resume_address() -> u64 {
    poole_page_fault_resume as *const () as usize as u64
}

pub fn double_fault_origin_address() -> u64 {
    poole_double_fault_origin as *const () as usize as u64
}

pub fn x87_exception_fault_address() -> u64 {
    poole_x87_exception_fault as *const () as usize as u64
}

pub fn x87_exception_resume_address() -> u64 {
    poole_x87_exception_resume as *const () as usize as u64
}

pub fn simd_exception_fault_address() -> u64 {
    poole_simd_exception_fault as *const () as usize as u64
}

pub fn simd_exception_resume_address() -> u64 {
    poole_simd_exception_resume as *const () as usize as u64
}

pub fn device_not_available_fault_address() -> u64 {
    poole_device_not_available_fault as *const () as usize as u64
}

unsafe fn read_fsw() -> u16 {
    let value: u16;
    // SAFETY: FNSTSW is the non-waiting status observation required in a #MF handler.
    unsafe { asm!("fnstsw ax", out("ax") value, options(nomem, nostack)) };
    value
}

pub fn observe_xstate_control_state() -> (u64, u64) {
    // SAFETY: PKXEXC1 invokes this only at CPL0 inside its installed handlers.
    unsafe { (read_cr0(), read_cr4()) }
}

pub fn observe_simd_exception_diagnostic() -> (u32, u64) {
    // SAFETY: the panic-only diagnostic runs at CPL0 with the parent eager policy live.
    unsafe { (read_mxcsr(), read_cr4()) }
}

pub unsafe fn recover_x87_exception() -> XstateExceptionTransition {
    // SAFETY: #MF dispatch runs at CPL0 with TS clear and owns the x87 state.
    let cr0 = unsafe { read_cr0() };
    // SAFETY: #MF dispatch runs at CPL0 after PKXSTATE1 configuration.
    let cr4 = unsafe { read_cr4() };
    // SAFETY: all three observations are non-mutating and valid with TS clear.
    let (fcw_before, fsw_before, mxcsr_before) = unsafe { (read_fcw(), read_fsw(), read_mxcsr()) };
    // SAFETY: FNINIT is the bounded non-waiting recovery action for the owned x87 state.
    unsafe { asm!("fninit", options(nomem, nostack)) };
    // SAFETY: the recovered state is live and readable after FNINIT.
    let (fcw_after, fsw_after, mxcsr_after) = unsafe { (read_fcw(), read_fsw(), read_mxcsr()) };
    XstateExceptionTransition {
        cr0,
        cr4,
        fcw_before,
        fsw_before,
        mxcsr_before,
        fcw_after,
        fsw_after,
        mxcsr_after,
    }
}

pub unsafe fn recover_simd_exception() -> XstateExceptionTransition {
    // SAFETY: #XM dispatch runs at CPL0 with TS clear and owns the SSE state.
    let cr0 = unsafe { read_cr0() };
    // SAFETY: #XM dispatch runs at CPL0 after PKXSTATE1 configuration.
    let cr4 = unsafe { read_cr4() };
    // SAFETY: all three observations are non-mutating and valid with TS clear.
    let (fcw_before, fsw_before, mxcsr_before) = unsafe { (read_fcw(), read_fsw(), read_mxcsr()) };
    let canonical = INITIAL_MXCSR;
    // SAFETY: the canonical MXCSR contains no reserved bits and masks every exception.
    unsafe { write_mxcsr(&canonical) };
    // SAFETY: the recovered state is live and readable after LDMXCSR.
    let (fcw_after, fsw_after, mxcsr_after) = unsafe { (read_fcw(), read_fsw(), read_mxcsr()) };
    XstateExceptionTransition {
        cr0,
        cr4,
        fcw_before,
        fsw_before,
        mxcsr_before,
        fcw_after,
        fsw_after,
        mxcsr_after,
    }
}

pub unsafe fn trigger_breakpoint() {
    // SAFETY: PKTRAP1 installs and validates the corresponding IDT gate before this call.
    unsafe { poole_trigger_breakpoint() };
}

pub unsafe fn trigger_invalid_opcode() {
    // SAFETY: PKTRAP1 installs and validates the corresponding IDT gate before this call.
    unsafe { poole_trigger_invalid_opcode() };
}

pub unsafe fn trigger_page_fault(address: u64) {
    // SAFETY: PKTRAP1 supplies a deliberate known-unmapped guard address.
    unsafe { poole_trigger_page_fault(address) };
}

pub unsafe fn trigger_double_fault() -> ! {
    // SAFETY: this is the terminal QEMU-only #GP-delivery-failure scenario.
    unsafe { poole_trigger_double_fault() }
}

pub unsafe fn trigger_x87_exception() {
    // SAFETY: PKXEXC1 installed vector 16 and owns the live x87 state.
    unsafe { poole_trigger_x87_exception() };
}

pub unsafe fn trigger_simd_exception() {
    // SAFETY: PKXEXC1 installed vector 19 and owns the live SSE state.
    unsafe { poole_trigger_simd_exception() };
}

pub unsafe fn trigger_device_not_available_rejection() -> ! {
    // SAFETY: this terminal test-only path arms TS and immediately executes FNOP.
    unsafe { poole_trigger_device_not_available_rejection() }
}

unsafe extern "C" {
    fn poole_trap_breakpoint();
    fn poole_trap_invalid_opcode();
    fn poole_trap_device_not_available();
    fn poole_trap_double_fault();
    fn poole_trap_general_protection();
    fn poole_trap_page_fault();
    fn poole_trap_x87_floating_point();
    fn poole_trap_simd_floating_point();
    fn poole_trigger_breakpoint();
    fn poole_breakpoint_resume();
    fn poole_trigger_invalid_opcode();
    fn poole_invalid_opcode_fault();
    fn poole_invalid_opcode_resume();
    fn poole_trigger_page_fault(address: u64);
    fn poole_page_fault_origin();
    fn poole_page_fault_resume();
    fn poole_trigger_double_fault() -> !;
    fn poole_double_fault_origin();
    fn poole_trigger_x87_exception();
    fn poole_x87_exception_fault();
    fn poole_x87_exception_resume();
    fn poole_trigger_simd_exception();
    fn poole_simd_exception_fault();
    fn poole_simd_exception_resume();
    fn poole_trigger_device_not_available_rejection() -> !;
    fn poole_device_not_available_fault();
}

core::arch::global_asm!(
    r#"
    .section .text.poole_traps,"ax",@progbits

    .macro POOLE_TRAP_NO_ERROR name, vector
    .global \name
    .type \name,@function
\name:
    push 0
    push \vector
    jmp poole_trap_common
    .size \name, .-\name
    .endm

    .macro POOLE_TRAP_ERROR name, vector
    .global \name
    .type \name,@function
\name:
    push \vector
    jmp poole_trap_common
    .size \name, .-\name
    .endm

    POOLE_TRAP_NO_ERROR poole_trap_breakpoint, 3
    POOLE_TRAP_NO_ERROR poole_trap_invalid_opcode, 6
    POOLE_TRAP_NO_ERROR poole_trap_device_not_available, 7
    POOLE_TRAP_ERROR poole_trap_double_fault, 8
    POOLE_TRAP_ERROR poole_trap_general_protection, 13
    POOLE_TRAP_ERROR poole_trap_page_fault, 14
    POOLE_TRAP_NO_ERROR poole_trap_x87_floating_point, 16
    POOLE_TRAP_NO_ERROR poole_trap_simd_floating_point, 19

    .global poole_trap_common
    .type poole_trap_common,@function
poole_trap_common:
    push rax
    push rbx
    push rcx
    push rdx
    push rbp
    push rdi
    push rsi
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push r14
    push r15
    cld
    mov rdi, rsp
    call poole_kernel_trap_dispatch
    pop r15
    pop r14
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    pop rsi
    pop rdi
    pop rbp
    pop rdx
    pop rcx
    pop rbx
    pop rax
    add rsp, 16
    iretq
    .size poole_trap_common, .-poole_trap_common

    .global poole_trigger_breakpoint
    .type poole_trigger_breakpoint,@function
poole_trigger_breakpoint:
    int3
    .global poole_breakpoint_resume
poole_breakpoint_resume:
    ret
    .size poole_trigger_breakpoint, .-poole_trigger_breakpoint

    .global poole_trigger_invalid_opcode
    .type poole_trigger_invalid_opcode,@function
poole_trigger_invalid_opcode:
    .global poole_invalid_opcode_fault
poole_invalid_opcode_fault:
    ud2
    .global poole_invalid_opcode_resume
poole_invalid_opcode_resume:
    ret
    .size poole_trigger_invalid_opcode, .-poole_trigger_invalid_opcode

    .global poole_trigger_page_fault
    .type poole_trigger_page_fault,@function
poole_trigger_page_fault:
    .global poole_page_fault_origin
poole_page_fault_origin:
    mov rax, qword ptr [rdi]
    .global poole_page_fault_resume
poole_page_fault_resume:
    ret
    .size poole_trigger_page_fault, .-poole_trigger_page_fault

    .global poole_trigger_double_fault
    .type poole_trigger_double_fault,@function
poole_trigger_double_fault:
    mov ax, 0x28
    .global poole_double_fault_origin
poole_double_fault_origin:
    mov ds, ax
    ud2
    .size poole_trigger_double_fault, .-poole_trigger_double_fault

    .global poole_trigger_x87_exception
    .type poole_trigger_x87_exception,@function
poole_trigger_x87_exception:
    sub rsp, 16
    mov word ptr [rsp], 0x037e
    fninit
    fldcw word ptr [rsp]
    fldz
    fldz
    fdivp st(1), st(0)
    .global poole_x87_exception_fault
poole_x87_exception_fault:
    fwait
    .global poole_x87_exception_resume
poole_x87_exception_resume:
    add rsp, 16
    ret
    .size poole_trigger_x87_exception, .-poole_trigger_x87_exception

    .global poole_trigger_simd_exception
    .type poole_trigger_simd_exception,@function
poole_trigger_simd_exception:
    sub rsp, 16
    mov dword ptr [rsp], 0x00001f00
    ldmxcsr dword ptr [rsp]
    pxor xmm0, xmm0
    pxor xmm1, xmm1
    .global poole_simd_exception_fault
poole_simd_exception_fault:
    divss xmm0, xmm1
    .global poole_simd_exception_resume
poole_simd_exception_resume:
    add rsp, 16
    ret
    .size poole_trigger_simd_exception, .-poole_trigger_simd_exception

    .global poole_trigger_device_not_available_rejection
    .type poole_trigger_device_not_available_rejection,@function
poole_trigger_device_not_available_rejection:
    mov rax, cr0
    or rax, 8
    mov cr0, rax
    .global poole_device_not_available_fault
poole_device_not_available_fault:
    fnop
    ud2
    .size poole_trigger_device_not_available_rejection, .-poole_trigger_device_not_available_rejection
"#
);

const _: () = assert!(size_of::<DescriptorPointer>() == 10);
const _: () = assert!(size_of::<IdtGate>() == 16);
const _: () = assert!(size_of::<TaskStateSegment>() == 104);
const _: () = assert!(size_of::<TrapFrame>() == 176);

pub struct Com1 {
    available: bool,
}

impl Com1 {
    /// Initializes the fixed legacy COM1 candidate with a bounded loopback test.
    ///
    /// # Safety
    ///
    /// The caller must execute at a privilege level permitted to access x86 I/O ports.
    pub unsafe fn initialize() -> Self {
        // SAFETY: the caller owns the privileged fixed-port probe for this early boundary.
        unsafe {
            outb(COM1_BASE + 1, 0x00);
            outb(COM1_BASE + 3, 0x80);
            outb(COM1_BASE, 0x03);
            outb(COM1_BASE + 1, 0x00);
            outb(COM1_BASE + 3, 0x03);
            outb(COM1_BASE + 2, 0xc7);
            outb(COM1_BASE + 4, 0x1e);
            outb(COM1_BASE, 0xae);
        }
        // SAFETY: this reads only the fixed loopback register configured above.
        let available = unsafe { inb(COM1_BASE) == 0xae };
        if available {
            // SAFETY: restore normal modem-control output for the same fixed UART.
            unsafe { outb(COM1_BASE + 4, 0x0f) };
        }
        Self { available }
    }

    pub const fn available(&self) -> bool {
        self.available
    }
}

impl ByteSink for Com1 {
    fn write_byte(&mut self, byte: u8) {
        if !self.available {
            return;
        }
        for _ in 0..MAX_READY_POLLS {
            // SAFETY: availability was established by the bounded fixed-port probe.
            if unsafe { inb(COM1_BASE + 5) } & TRANSMIT_READY != 0 {
                // SAFETY: the UART reports that its transmit register is ready.
                unsafe { outb(COM1_BASE, byte) };
                return;
            }
            core::hint::spin_loop();
        }
        self.available = false;
    }
}

pub struct DebugCon;

impl DebugCon {
    pub const fn new() -> Self {
        Self
    }
}

impl ByteSink for DebugCon {
    fn write_byte(&mut self, byte: u8) {
        // SAFETY: PKXFER1's QEMU-only profile reserves this fixed debugcon port.
        unsafe { outb(DEBUGCON_PORT, byte) };
    }
}

pub fn halt_forever() -> ! {
    loop {
        // SAFETY: the terminal kernel state intentionally disables interrupts and halts.
        unsafe { core::arch::asm!("cli", "hlt", options(nomem, nostack)) };
    }
}

unsafe fn outb(port: u16, value: u8) {
    // SAFETY: the caller supplies a port for which it owns the privileged I/O operation.
    unsafe {
        core::arch::asm!(
            "out dx, al",
            in("dx") port,
            in("al") value,
            options(nomem, nostack, preserves_flags),
        )
    };
}

unsafe fn inb(port: u16) -> u8 {
    let value: u8;
    // SAFETY: the caller supplies a port for which it owns the privileged I/O operation.
    unsafe {
        core::arch::asm!(
            "in al, dx",
            in("dx") port,
            lateout("al") value,
            options(nomem, nostack, preserves_flags),
        )
    };
    value
}
