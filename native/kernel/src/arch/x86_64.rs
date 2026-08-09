use core::arch::asm;
use core::mem::size_of;
use core::ptr::{
    addr_of, addr_of_mut, read_unaligned, read_volatile, write_bytes, write_unaligned,
    write_volatile,
};
use core::sync::atomic::{AtomicU64, Ordering, compiler_fence};

use poolekernel::{
    ByteSink, CPU_MSR_APIC_BASE, CPU_MSR_EFER, CPU_MSR_MTRR_CAP, CPU_MSR_MTRR_DEF_TYPE,
    CPU_MSR_PAT, CpuControlState, CpuDiscovery, CpuPolicySnapshot, DescriptorState, GDT_LIMIT,
    IDT_LIMIT, INSTALLED_EXCEPTION_GATE_COUNT, INSTALLED_INTERRUPT_GATE_COUNT,
    INSTALLED_XSTATE_EXCEPTION_GATE_COUNT, IST_STACK_BYTES, KERNEL_CODE_SELECTOR,
    KERNEL_DATA_SELECTOR, KERNEL_TSS_SELECTOR,
    interrupt_time::{APIC_ERROR_VECTOR, CpuApicObservation, SPURIOUS_VECTOR, TIMER_VECTOR},
    privilege_msr::{
        PrivilegeMsrSnapshot, READ_CSTAR, READ_EFER, READ_FS_BASE, READ_GS_BASE,
        READ_KERNEL_GS_BASE, READ_LSTAR, READ_MCG_CAP, READ_MCG_CTL, READ_MCG_STATUS, READ_SFMASK,
        READ_STAR, READ_TSC_AUX,
    },
    smp::{self, ResourceLayout},
    smp_ipi::{self, HandlerLayout as IpiHandlerLayout},
    smp_runtime::{self, ResourceLayout as RuntimeResourceLayout},
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
const TIMER_INTERRUPT_VECTOR: usize = TIMER_VECTOR as usize;
const APIC_ERROR_INTERRUPT_VECTOR: usize = APIC_ERROR_VECTOR as usize;
const SPURIOUS_INTERRUPT_VECTOR: usize = SPURIOUS_VECTOR as usize;
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

pub const SCHEDULER_STACK_BYTES: usize = 16 * 1024;
pub const SCHEDULER_STACK_ALIGNMENT: usize = 16;
const SCHEDULER_CONTEXT_WORDS: usize = 8;
const SCHEDULER_CONTEXT_BYTES: usize = SCHEDULER_CONTEXT_WORDS * size_of::<u64>();
const SCHEDULER_HIGH_CANARY_OFFSET: usize =
    SCHEDULER_STACK_BYTES - SCHEDULER_CONTEXT_BYTES - size_of::<u64>();
const SCHEDULER_STACK_CANARY: u64 = 0x504b_5343_4845_4431;
const SCHEDULER_STACK_FILL: u8 = 0xa5;
const SCHEDULER_TASK_A_REGISTERS: [u64; 6] = [
    0xa0a0_b0b0_c0c0_d0d0,
    0xa1a1_b1b1_c1c1_d1d1,
    0xa2a2_b2b2_c2c2_d2d2,
    0xa3a3_b3b3_c3c3_d3d3,
    0xa4a4_b4b4_c4c4_d4d4,
    0xa5a5_b5b5_c5c5_d5d5,
];
const SCHEDULER_TASK_B_REGISTERS: [u64; 6] = [
    0xb0b0_c0c0_d0d0_e0e0,
    0xb1b1_c1c1_d1d1_e1e1,
    0xb2b2_c2c2_d2d2_e2e2,
    0xb3b3_c3c3_d3d3_e3e3,
    0xb4b4_c4c4_d4d4_e4e4,
    0xb5b5_c5c5_d5d5_e5e5,
];

#[repr(C, align(16))]
struct SchedulerStack([u8; SCHEDULER_STACK_BYTES]);

static mut SCHEDULER_STACK_A: SchedulerStack = SchedulerStack([0; SCHEDULER_STACK_BYTES]);
static mut SCHEDULER_STACK_B: SchedulerStack = SchedulerStack([0; SCHEDULER_STACK_BYTES]);

pub const SCHEDULER_PREEMPT_TASK_COUNT: usize = 4;
pub const SCHEDULER_PREEMPT_STACK_BYTES: usize = SCHEDULER_STACK_BYTES;
const SCHEDULER_PREEMPT_INITIAL_RSP_RESERVE: usize = 128;
const SCHEDULER_PREEMPT_TASK_REGISTERS: [[u64; 6]; SCHEDULER_PREEMPT_TASK_COUNT] = [
    SCHEDULER_TASK_A_REGISTERS,
    SCHEDULER_TASK_B_REGISTERS,
    [
        0xc0c0_d0d0_e0e0_f0f0,
        0xc1c1_d1d1_e1e1_f1f1,
        0xc2c2_d2d2_e2e2_f2f2,
        0xc3c3_d3d3_e3e3_f3f3,
        0xc4c4_d4d4_e4e4_f4f4,
        0xc5c5_d5d5_e5e5_f5f5,
    ],
    [
        0xd0d0_e0e0_f0f0_a0a0,
        0xd1d1_e1e1_f1f1_a1a1,
        0xd2d2_e2e2_f2f2_a2a2,
        0xd3d3_e3e3_f3f3_a3a3,
        0xd4d4_e4e4_f4f4_a4a4,
        0xd5d5_e5e5_f5f5_a5a5,
    ],
];

const RETAINED_KERNEL_STACK_BYTES: usize =
    poole_kmap::STACK_PAGE_COUNT * poole_kmap::PAGE_SIZE as usize;
const SCHEDULER_DEFERRED_REGION_BYTES: usize = 2 * SCHEDULER_STACK_BYTES;
static SCHEDULER_DEFERRED_STACK_BASE: AtomicU64 = AtomicU64::new(0);
const SCHEDULER_PREEMPT_REGION_BYTES: usize =
    SCHEDULER_PREEMPT_TASK_COUNT * SCHEDULER_PREEMPT_STACK_BYTES;
static SCHEDULER_PREEMPT_STACK_BASE: AtomicU64 = AtomicU64::new(0);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SchedulerSwitchHardwareError {
    Trace,
    InterruptState,
    StackGeometry,
    RegisterState,
    TransitionCount,
    ControlState,
    Clear,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SchedulerSwitchProof {
    pub dispatch_count: u32,
    pub machine_transition_count: u32,
    pub task_a_runs: u32,
    pub task_b_runs: u32,
    pub callee_saved_register_count: u8,
    pub rflags_preserved: bool,
    pub same_cr3: bool,
    pub fs_gs_unchanged: bool,
    pub xstate_unused: bool,
    pub debug_state_unused: bool,
    pub pmu_state_unused: bool,
    pub stacks_distinct: bool,
    pub stack_bytes_each: u32,
    pub stack_alignment: u8,
    pub stack_bytes_cleared: u32,
    pub register_error_count: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SchedulerPreemptionHardwareError {
    InterruptState,
    StackGeometry,
    ContextGeometry,
    EntryCount,
    TransitionCount,
    ControlState,
    Clear,
}

impl SchedulerPreemptionHardwareError {
    pub const fn label(self) -> &'static str {
        match self {
            Self::InterruptState => "launcher_interrupt_state",
            Self::StackGeometry => "launcher_stack_geometry",
            Self::ContextGeometry => "launcher_context_geometry",
            Self::EntryCount => "launcher_entry_count",
            Self::TransitionCount => "launcher_transition_count",
            Self::ControlState => "launcher_control_state",
            Self::Clear => "launcher_clear",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SchedulerPreemptionHardwareProof {
    pub task_entry_count: [u32; SCHEDULER_PREEMPT_TASK_COUNT],
    pub launcher_transition_count: u32,
    pub stack_count: u8,
    pub stack_bytes_each: u32,
    pub stack_alignment: u8,
    pub stack_bytes_cleared: u32,
    pub same_cr3: bool,
    pub fs_gs_unchanged: bool,
    pub returned_with_interrupts_disabled: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SchedulerDeferredHardwareError {
    InterruptState,
    Worker,
    StackGeometry,
    StackCanary,
    StackRange,
    StackAlignment,
    Step,
    TransitionCount,
    ControlState,
    Clear,
}

impl SchedulerDeferredHardwareError {
    pub const fn label(self) -> &'static str {
        match self {
            Self::InterruptState => "worker_interrupt_state",
            Self::Worker => "worker_identity",
            Self::StackGeometry => "worker_stack_geometry",
            Self::StackCanary => "worker_stack_canary",
            Self::StackRange => "worker_stack_range",
            Self::StackAlignment => "worker_stack_alignment",
            Self::Step => "worker_step",
            Self::TransitionCount => "worker_transition_count",
            Self::ControlState => "worker_control_state",
            Self::Clear => "worker_stack_clear",
        }
    }
}

pub struct SchedulerDeferredHardwareContext {
    cr3: u64,
    bases: (u64, u64, u64),
    dispatches: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SchedulerDeferredHardwareProof {
    pub worker_entry_count: [u32; 2],
    pub dispatch_count: u32,
    pub machine_transition_count: u32,
    pub stack_count: u8,
    pub stack_bytes_each: u32,
    pub stack_alignment: u8,
    pub stack_bytes_cleared: u32,
    pub same_cr3: bool,
    pub fs_gs_unchanged: bool,
    pub returned_with_interrupts_disabled: bool,
    pub worker_error_count: u32,
}

unsafe extern "C" {
    fn poole_scheduler_context_switch(outgoing: *mut u64, incoming: *const u64);
    fn poole_scheduler_task_a_entry();
    fn poole_scheduler_task_b_entry();
    static mut poole_scheduler_kernel_rsp: u64;
    static mut poole_scheduler_task_a_rsp: u64;
    static mut poole_scheduler_task_b_rsp: u64;
    static mut poole_scheduler_task_a_runs: u64;
    static mut poole_scheduler_task_b_runs: u64;
    static mut poole_scheduler_last_task: u64;
    static mut poole_scheduler_transition_count: u64;
    static mut poole_scheduler_register_errors: u64;
    fn poole_scheduler_preempt_task_a_entry();
    fn poole_scheduler_preempt_task_a_end();
    fn poole_scheduler_preempt_task_b_entry();
    fn poole_scheduler_preempt_task_b_end();
    fn poole_scheduler_preempt_task_c_entry();
    fn poole_scheduler_preempt_task_c_end();
    fn poole_scheduler_preempt_task_d_entry();
    fn poole_scheduler_preempt_task_d_end();
    fn poole_scheduler_preempt_launch(outgoing: *mut u64, incoming: *const u64);
    static mut poole_scheduler_preempt_kernel_rsp: u64;
    static mut poole_scheduler_preempt_task_a_rsp: u64;
    static mut poole_scheduler_preempt_task_b_rsp: u64;
    static mut poole_scheduler_preempt_task_c_rsp: u64;
    static mut poole_scheduler_preempt_task_d_rsp: u64;
    static mut poole_scheduler_preempt_task_a_entries: u64;
    static mut poole_scheduler_preempt_task_b_entries: u64;
    static mut poole_scheduler_preempt_task_c_entries: u64;
    static mut poole_scheduler_preempt_task_d_entries: u64;
    static mut poole_scheduler_preempt_flags_before: u64;
    static mut poole_scheduler_preempt_flags_after: u64;
    fn poole_scheduler_deferred_worker_a_entry();
    fn poole_scheduler_deferred_worker_b_entry();
    static mut poole_scheduler_deferred_kernel_rsp: u64;
    static mut poole_scheduler_deferred_worker_a_rsp: u64;
    static mut poole_scheduler_deferred_worker_b_rsp: u64;
    static mut poole_scheduler_deferred_worker_a_entries: u64;
    static mut poole_scheduler_deferred_worker_b_entries: u64;
    static mut poole_scheduler_deferred_transition_count: u64;
    static mut poole_scheduler_deferred_errors: u64;
}

core::arch::global_asm!(
    r#"
    .section .text.poole_scheduler_switch,"ax",@progbits
    .balign 16
    .global poole_scheduler_context_switch
    .type poole_scheduler_context_switch,@function
poole_scheduler_context_switch:
    pushfq
    push rbp
    push rbx
    push r12
    push r13
    push r14
    push r15
    mov qword ptr [rdi], rsp
    inc qword ptr [rip + poole_scheduler_transition_count]
    mov rsp, qword ptr [rsi]
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    pop rbp
    popfq
    ret
    .global poole_scheduler_context_switch_end
poole_scheduler_context_switch_end:
    .size poole_scheduler_context_switch, .-poole_scheduler_context_switch

    .global poole_scheduler_task_a_entry
    .type poole_scheduler_task_a_entry,@function
poole_scheduler_task_a_entry:
    mov rax, 0xa0a0b0b0c0c0d0d0
    cmp rbx, rax
    jne .Lpoole_scheduler_task_a_error
    mov rax, 0xa1a1b1b1c1c1d1d1
    cmp rbp, rax
    jne .Lpoole_scheduler_task_a_error
    mov rax, 0xa2a2b2b2c2c2d2d2
    cmp r12, rax
    jne .Lpoole_scheduler_task_a_error
    mov rax, 0xa3a3b3b3c3c3d3d3
    cmp r13, rax
    jne .Lpoole_scheduler_task_a_error
    mov rax, 0xa4a4b4b4c4c4d4d4
    cmp r14, rax
    jne .Lpoole_scheduler_task_a_error
    mov rax, 0xa5a5b5b5c5c5d5d5
    cmp r15, rax
    jne .Lpoole_scheduler_task_a_error
    jmp .Lpoole_scheduler_task_a_run
.Lpoole_scheduler_task_a_error:
    inc qword ptr [rip + poole_scheduler_register_errors]
.Lpoole_scheduler_task_a_run:
    inc qword ptr [rip + poole_scheduler_task_a_runs]
    mov qword ptr [rip + poole_scheduler_last_task], 1
    lea rdi, [rip + poole_scheduler_task_a_rsp]
    lea rsi, [rip + poole_scheduler_kernel_rsp]
    call poole_scheduler_context_switch
    jmp poole_scheduler_task_a_entry
    .size poole_scheduler_task_a_entry, .-poole_scheduler_task_a_entry

    .global poole_scheduler_task_b_entry
    .type poole_scheduler_task_b_entry,@function
poole_scheduler_task_b_entry:
    mov rax, 0xb0b0c0c0d0d0e0e0
    cmp rbx, rax
    jne .Lpoole_scheduler_task_b_error
    mov rax, 0xb1b1c1c1d1d1e1e1
    cmp rbp, rax
    jne .Lpoole_scheduler_task_b_error
    mov rax, 0xb2b2c2c2d2d2e2e2
    cmp r12, rax
    jne .Lpoole_scheduler_task_b_error
    mov rax, 0xb3b3c3c3d3d3e3e3
    cmp r13, rax
    jne .Lpoole_scheduler_task_b_error
    mov rax, 0xb4b4c4c4d4d4e4e4
    cmp r14, rax
    jne .Lpoole_scheduler_task_b_error
    mov rax, 0xb5b5c5c5d5d5e5e5
    cmp r15, rax
    jne .Lpoole_scheduler_task_b_error
    jmp .Lpoole_scheduler_task_b_run
.Lpoole_scheduler_task_b_error:
    inc qword ptr [rip + poole_scheduler_register_errors]
.Lpoole_scheduler_task_b_run:
    inc qword ptr [rip + poole_scheduler_task_b_runs]
    mov qword ptr [rip + poole_scheduler_last_task], 2
    lea rdi, [rip + poole_scheduler_task_b_rsp]
    lea rsi, [rip + poole_scheduler_kernel_rsp]
    call poole_scheduler_context_switch
    jmp poole_scheduler_task_b_entry
    .size poole_scheduler_task_b_entry, .-poole_scheduler_task_b_entry

    .section .bss.poole_scheduler_context,"aw",@nobits
    .balign 8
    .global poole_scheduler_kernel_rsp
poole_scheduler_kernel_rsp:
    .quad 0
    .global poole_scheduler_task_a_rsp
poole_scheduler_task_a_rsp:
    .quad 0
    .global poole_scheduler_task_b_rsp
poole_scheduler_task_b_rsp:
    .quad 0
    .global poole_scheduler_task_a_runs
poole_scheduler_task_a_runs:
    .quad 0
    .global poole_scheduler_task_b_runs
poole_scheduler_task_b_runs:
    .quad 0
    .global poole_scheduler_last_task
poole_scheduler_last_task:
    .quad 0
    .global poole_scheduler_transition_count
poole_scheduler_transition_count:
    .quad 0
    .global poole_scheduler_register_errors
poole_scheduler_register_errors:
    .quad 0
"#
);

core::arch::global_asm!(
    r#"
    .section .text.poole_scheduler_deferred_workers,"ax",@progbits
    .balign 16

    .macro POOLE_SCHEDULER_DEFERRED_WORKER name, worker_id, entries, saved_rsp
    .global \name
    .type \name,@function
\name:
.L\name\()_loop:
    mov edi, \worker_id
    call poole_deferred_worker_step
    cmp eax, 1
    je .L\name\()_step_ok
    inc qword ptr [rip + poole_scheduler_deferred_errors]
.L\name\()_step_ok:
    inc qword ptr [rip + \entries]
    lea rdi, [rip + \saved_rsp]
    lea rsi, [rip + poole_scheduler_deferred_kernel_rsp]
    inc qword ptr [rip + poole_scheduler_deferred_transition_count]
    call poole_scheduler_context_switch
    jmp .L\name\()_loop
    .size \name, .-\name
    .endm

    POOLE_SCHEDULER_DEFERRED_WORKER poole_scheduler_deferred_worker_a_entry, 0, poole_scheduler_deferred_worker_a_entries, poole_scheduler_deferred_worker_a_rsp
    POOLE_SCHEDULER_DEFERRED_WORKER poole_scheduler_deferred_worker_b_entry, 1, poole_scheduler_deferred_worker_b_entries, poole_scheduler_deferred_worker_b_rsp

    .section .bss.poole_scheduler_deferred_context,"aw",@nobits
    .balign 8
    .global poole_scheduler_deferred_kernel_rsp
poole_scheduler_deferred_kernel_rsp:
    .quad 0
    .global poole_scheduler_deferred_worker_a_rsp
poole_scheduler_deferred_worker_a_rsp:
    .quad 0
    .global poole_scheduler_deferred_worker_b_rsp
poole_scheduler_deferred_worker_b_rsp:
    .quad 0
    .global poole_scheduler_deferred_worker_a_entries
poole_scheduler_deferred_worker_a_entries:
    .quad 0
    .global poole_scheduler_deferred_worker_b_entries
poole_scheduler_deferred_worker_b_entries:
    .quad 0
    .global poole_scheduler_deferred_transition_count
poole_scheduler_deferred_transition_count:
    .quad 0
    .global poole_scheduler_deferred_errors
poole_scheduler_deferred_errors:
    .quad 0
"#
);

core::arch::global_asm!(
    r#"
    .section .text.poole_scheduler_preempt_tasks,"ax",@progbits
    .balign 16

    .global poole_scheduler_preempt_launch
    .type poole_scheduler_preempt_launch,@function
poole_scheduler_preempt_launch:
    pushfq
    pop rax
    mov qword ptr [rip + poole_scheduler_preempt_flags_before], rax
    call poole_scheduler_context_switch
    pushfq
    pop rax
    mov qword ptr [rip + poole_scheduler_preempt_flags_after], rax
    ret
    .size poole_scheduler_preempt_launch, .-poole_scheduler_preempt_launch

    .macro POOLE_SCHEDULER_PREEMPT_TASK name, end_name, entries, saved_rsp
    .global \name
    .type \name,@function
\name:
    inc qword ptr [rip + \entries]
.L\name\()_loop:
    cmp dword ptr [rip + poole_scheduler_preempt_done], 0
    jne .L\name\()_return
    pause
    jmp .L\name\()_loop
.L\name\()_return:
    lea rdi, [rip + \saved_rsp]
    lea rsi, [rip + poole_scheduler_preempt_kernel_rsp]
    call poole_scheduler_context_switch
    ud2
    .global \end_name
\end_name:
    .size \name, .-\name
    .endm

    POOLE_SCHEDULER_PREEMPT_TASK poole_scheduler_preempt_task_a_entry, poole_scheduler_preempt_task_a_end, poole_scheduler_preempt_task_a_entries, poole_scheduler_preempt_task_a_rsp
    POOLE_SCHEDULER_PREEMPT_TASK poole_scheduler_preempt_task_b_entry, poole_scheduler_preempt_task_b_end, poole_scheduler_preempt_task_b_entries, poole_scheduler_preempt_task_b_rsp
    POOLE_SCHEDULER_PREEMPT_TASK poole_scheduler_preempt_task_c_entry, poole_scheduler_preempt_task_c_end, poole_scheduler_preempt_task_c_entries, poole_scheduler_preempt_task_c_rsp
    POOLE_SCHEDULER_PREEMPT_TASK poole_scheduler_preempt_task_d_entry, poole_scheduler_preempt_task_d_end, poole_scheduler_preempt_task_d_entries, poole_scheduler_preempt_task_d_rsp

    .section .bss.poole_scheduler_preempt_context,"aw",@nobits
    .balign 8
    .global poole_scheduler_preempt_kernel_rsp
poole_scheduler_preempt_kernel_rsp:
    .quad 0
    .global poole_scheduler_preempt_task_a_rsp
poole_scheduler_preempt_task_a_rsp:
    .quad 0
    .global poole_scheduler_preempt_task_b_rsp
poole_scheduler_preempt_task_b_rsp:
    .quad 0
    .global poole_scheduler_preempt_task_c_rsp
poole_scheduler_preempt_task_c_rsp:
    .quad 0
    .global poole_scheduler_preempt_task_d_rsp
poole_scheduler_preempt_task_d_rsp:
    .quad 0
    .global poole_scheduler_preempt_task_a_entries
poole_scheduler_preempt_task_a_entries:
    .quad 0
    .global poole_scheduler_preempt_task_b_entries
poole_scheduler_preempt_task_b_entries:
    .quad 0
    .global poole_scheduler_preempt_task_c_entries
poole_scheduler_preempt_task_c_entries:
    .quad 0
    .global poole_scheduler_preempt_task_d_entries
poole_scheduler_preempt_task_d_entries:
    .quad 0
    .global poole_scheduler_preempt_flags_before
poole_scheduler_preempt_flags_before:
    .quad 0
    .global poole_scheduler_preempt_flags_after
poole_scheduler_preempt_flags_after:
    .quad 0
"#
);

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

pub fn observe_leaf1_features() -> (u32, u32) {
    let value = cpuid(1, 0);
    (value.ecx, value.edx)
}

pub fn read_tsc_ordered() -> u64 {
    let low: u32;
    let high: u32;
    // SAFETY: LFENCE orders prior loads and RDTSC is a read-only architectural observation.
    unsafe {
        asm!(
            "lfence",
            "rdtsc",
            out("eax") low,
            out("edx") high,
            options(nomem, nostack)
        )
    };
    u64::from(low) | (u64::from(high) << 32)
}

pub fn memory_fence() {
    // SAFETY: MFENCE orders the shared first-AP mailbox without changing privilege state.
    unsafe { asm!("mfence", options(nostack, preserves_flags)) };
}

pub fn physical_address_bits() -> Option<u8> {
    const EXTENDED_MAXIMUM: u32 = 0x8000_0000;
    const ADDRESS_WIDTHS: u32 = 0x8000_0008;

    if cpuid(EXTENDED_MAXIMUM, 0).eax < ADDRESS_WIDTHS {
        return None;
    }
    let bits = (cpuid(ADDRESS_WIDTHS, 0).eax & 0xff) as u8;
    (36..=52).contains(&bits).then_some(bits)
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

unsafe fn write_msr(msr: u32, value: u64) {
    // SAFETY: each caller supplies a typed, support-gated MSR and a constrained value.
    unsafe {
        asm!(
            "wrmsr",
            in("ecx") msr,
            in("eax") value as u32,
            in("edx") (value >> 32) as u32,
            options(nomem, nostack, preserves_flags)
        )
    };
}

unsafe fn read_efer() -> u64 {
    // SAFETY: long mode and the PKCPU1 baseline require IA32_EFER to exist.
    unsafe { read_msr(IA32_EFER) }
}

unsafe fn read_apic_base() -> u64 {
    // SAFETY: the caller requires CPUID.01H:EDX.APIC before this typed read.
    unsafe { read_msr(IA32_APIC_BASE) }
}

pub fn observe_apic_cpu() -> CpuApicObservation {
    let leaf1 = cpuid(1, 0);
    CpuApicObservation {
        apic_supported: leaf1.edx & (1 << 9) != 0,
        x2apic_supported: leaf1.ecx & (1 << 21) != 0,
        initial_apic_id: leaf1.ebx >> 24,
        physical_address_bits: physical_address_bits().unwrap_or(0),
    }
}

pub unsafe fn read_local_apic_base() -> u64 {
    // SAFETY: the PKIRQ1 caller first requires CPUID.01H:EDX.APIC.
    unsafe { read_apic_base() }
}

pub unsafe fn write_local_apic_base(value: u64) {
    // SAFETY: PKIRQ1 permits only an exact read-modify-write of IA32_APIC_BASE.EN.
    unsafe { write_msr(IA32_APIC_BASE, value) }
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
    unsafe { install_descriptor_tables_for_profile(rsp0, false, false) }
}

pub unsafe fn install_xstate_exception_descriptor_tables(rsp0: u64) -> DescriptorState {
    // SAFETY: the caller owns the single-BSP PKXEXC1 descriptor installation.
    unsafe { install_descriptor_tables_for_profile(rsp0, true, false) }
}

pub unsafe fn install_interrupt_descriptor_tables(rsp0: u64) -> DescriptorState {
    // SAFETY: the caller owns the one-BSP PKIRQ1 descriptor installation with IF clear.
    unsafe { install_descriptor_tables_for_profile(rsp0, false, true) }
}

unsafe fn install_descriptor_tables_for_profile(
    rsp0: u64,
    include_xstate_exceptions: bool,
    include_interrupts: bool,
) -> DescriptorState {
    assert!(!(include_xstate_exceptions && include_interrupts));
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
    if include_interrupts {
        for (vector, handler) in [
            (
                TIMER_INTERRUPT_VECTOR,
                poole_interrupt_timer as *const () as usize as u64,
            ),
            (
                APIC_ERROR_INTERRUPT_VECTOR,
                poole_interrupt_apic_error as *const () as usize as u64,
            ),
            (
                SPURIOUS_INTERRUPT_VECTOR,
                poole_interrupt_spurious as *const () as usize as u64,
            ),
        ] {
            // SAFETY: each PKIRQ1 vector is uniquely owned and uses the bounded IST1 stack.
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
        } else if include_interrupts {
            INSTALLED_INTERRUPT_GATE_COUNT
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
    fn poole_interrupt_timer();
    fn poole_interrupt_apic_error();
    fn poole_interrupt_spurious();
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
    POOLE_TRAP_NO_ERROR poole_interrupt_timer, 64
    POOLE_TRAP_NO_ERROR poole_interrupt_apic_error, 240
    POOLE_TRAP_NO_ERROR poole_interrupt_spurious, 255

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

core::arch::global_asm!(
    r#"
    .section .rodata.poole_ap_runtime_trampoline,"a",@progbits
    .balign 16
    .global poole_ap_runtime_trampoline_start
    .global poole_ap_runtime_trampoline_end
    .global poole_ap_runtime_trampoline_protected_entry
    .global poole_ap_runtime_trampoline_long_entry
    .global poole_ap_runtime_trampoline_fault
    .global poole_ap_runtime_trampoline_gdt
    .global poole_ap_runtime_patch_protected_offset
    .global poole_ap_runtime_patch_long_offset
    .global poole_ap_runtime_patch_gdt_base
    .global poole_ap_runtime_patch_cr3
    .global poole_ap_runtime_patch_stack_top
    .global poole_ap_runtime_patch_mailbox
    .global poole_ap_runtime_patch_gdtr_base
    .global poole_ap_runtime_patch_idtr_base
    .global poole_ap_runtime_patch_xstate

    .set poole_ap_runtime_gdt_pointer_offset, .Lpoole_ap_runtime_gdt_pointer - poole_ap_runtime_trampoline_start
    .set poole_ap_runtime_config_cr3_offset, .Lpoole_ap_runtime_config_cr3 - poole_ap_runtime_trampoline_start
    .set poole_ap_runtime_config_stack_top_offset, .Lpoole_ap_runtime_config_stack_top - poole_ap_runtime_trampoline_start
    .set poole_ap_runtime_config_mailbox_offset, .Lpoole_ap_runtime_config_mailbox - poole_ap_runtime_trampoline_start
    .set poole_ap_runtime_config_gdtr_offset, .Lpoole_ap_runtime_config_gdtr - poole_ap_runtime_trampoline_start
    .set poole_ap_runtime_config_idtr_offset, .Lpoole_ap_runtime_config_idtr - poole_ap_runtime_trampoline_start
    .set poole_ap_runtime_config_xstate_offset, .Lpoole_ap_runtime_config_xstate - poole_ap_runtime_trampoline_start

poole_ap_runtime_trampoline_start:
    .code16
    cli
    cld
    xor eax, eax
    mov ax, cs
    shl eax, 4
    mov esi, eax
    .byte 0xbb
    .word poole_ap_runtime_gdt_pointer_offset
    lgdt cs:[bx]
    mov eax, cr0
    or eax, 1
    mov cr0, eax
    .byte 0x66, 0xea
poole_ap_runtime_patch_protected_offset:
    .long 0
    .word 0x0008

    .code32
poole_ap_runtime_trampoline_protected_entry:
    mov ax, 0x0010
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov eax, cr4
    or eax, 0x20
    mov cr4, eax
    mov eax, dword ptr [esi + poole_ap_runtime_config_cr3_offset]
    mov cr3, eax
    mov ecx, 0xc0000080
    rdmsr
    or eax, 0x00000900
    wrmsr
    mov eax, cr0
    or eax, 0x80010001
    mov cr0, eax
    .byte 0xea
poole_ap_runtime_patch_long_offset:
    .long 0
    .word 0x0018

    .code64
poole_ap_runtime_trampoline_long_entry:
    mov ax, 0x0020
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov esi, esi
    mov rsp, qword ptr [rsi + poole_ap_runtime_config_stack_top_offset]
    xor rbp, rbp
    mov rdi, qword ptr [rsi + poole_ap_runtime_config_mailbox_offset]
    lgdt [rsi + poole_ap_runtime_config_gdtr_offset]
    push 0x0008
    lea rax, [rip + .Lpoole_ap_runtime_gdt_live]
    push rax
    retfq
.Lpoole_ap_runtime_gdt_live:
    mov ax, 0x0010
    mov ds, ax
    mov es, ax
    mov ss, ax
    xor eax, eax
    mov fs, ax
    mov gs, ax
    mov ax, 0x0018
    ltr ax
    lidt [rsi + poole_ap_runtime_config_idtr_offset]
    mov dword ptr [rdi + 108], 2

    mov rax, cr0
    or rax, 0x22
    and rax, -13
    mov cr0, rax
    mov rax, cr4
    or rax, 0x00040620
    mov cr4, rax
    xor ecx, ecx
    mov eax, 3
    xor edx, edx
    xsetbv
    fninit
    fldcw word ptr [rip + .Lpoole_ap_runtime_initial_fcw]
    ldmxcsr dword ptr [rip + .Lpoole_ap_runtime_initial_mxcsr]
    mov rbx, qword ptr [rsi + poole_ap_runtime_config_xstate_offset]
    mov eax, 3
    xor edx, edx
    xsave64 [rbx]
    mov dword ptr [rdi + 108], 3

    mov eax, 1
    cpuid
    mov r8d, ebx
    shr r8d, 24
    mov dword ptr [rdi + 28], r8d
    mov dword ptr [rdi + 32], ecx
    mov dword ptr [rdi + 36], edx
    mov eax, 0x0d
    xor ecx, ecx
    cpuid
    mov dword ptr [rdi + 296], eax
    mov dword ptr [rdi + 300], 0
    mov dword ptr [rdi + 304], ebx
    mov dword ptr [rdi + 308], ecx

    mov rax, cr0
    mov qword ptr [rdi + 40], rax
    mov rax, cr3
    mov qword ptr [rdi + 48], rax
    mov rax, cr4
    mov qword ptr [rdi + 56], rax
    mov ecx, 0xc0000080
    rdmsr
    shl rdx, 32
    or rax, rdx
    mov qword ptr [rdi + 64], rax
    xor ecx, ecx
    xgetbv
    shl rdx, 32
    or rax, rdx
    mov qword ptr [rdi + 216], rax

    sgdt [rdi + 320]
    movzx eax, word ptr [rdi + 320]
    mov dword ptr [rdi + 240], eax
    mov rax, qword ptr [rdi + 322]
    mov qword ptr [rdi + 192], rax
    sidt [rdi + 336]
    movzx eax, word ptr [rdi + 336]
    mov dword ptr [rdi + 244], eax
    mov rax, qword ptr [rdi + 338]
    mov qword ptr [rdi + 200], rax
    str ax
    movzx eax, ax
    mov dword ptr [rdi + 248], eax
    mov ax, cs
    movzx eax, ax
    mov dword ptr [rdi + 252], eax
    mov ax, ss
    movzx eax, ax
    mov dword ptr [rdi + 256], eax
    mov qword ptr [rdi + 208], rsp
    pushfq
    pop rax
    mov qword ptr [rdi + 232], rax
    shr rax, 9
    and eax, 1
    mov dword ptr [rdi + 268], eax
    fnstcw word ptr [rdi + 272]
    stmxcsr dword ptr [rdi + 276]
    mov rbx, qword ptr [rsi + poole_ap_runtime_config_xstate_offset]
    mov rax, qword ptr [rbx + 512]
    mov qword ptr [rdi + 224], rax

    lfence
    rdtsc
    shl rdx, 32
    or rax, rdx
    mov qword ptr [rdi + 72], rax
    mov dword ptr [rdi + 108], 4
    mfence
    mov dword ptr [rdi + 12], 2
.Lpoole_ap_runtime_wait_stop:
    pause
    cmp dword ptr [rdi + 16], 1
    jne .Lpoole_ap_runtime_wait_stop
    lfence
    rdtsc
    shl rdx, 32
    or rax, rdx
    mov qword ptr [rdi + 80], rax
    mov rbx, qword ptr [rsi + poole_ap_runtime_config_xstate_offset]
    mov eax, 3
    xor edx, edx
    xrstor64 [rbx]
    mov dword ptr [rdi + 280], 0
    mov dword ptr [rdi + 284], 1
    mov dword ptr [rdi + 288], 1
    mov dword ptr [rdi + 108], 5
    mfence
    mov dword ptr [rdi + 12], 3
.Lpoole_ap_runtime_parked:
    cli
    hlt
    jmp .Lpoole_ap_runtime_parked

poole_ap_runtime_trampoline_fault:
    cli
    mov rax, qword ptr [rip + .Lpoole_ap_runtime_config_mailbox]
    mov dword ptr [rax + 292], 1
    mov dword ptr [rax + 108], 0xffffffff
    mfence
    mov dword ptr [rax + 12], 0xffffffff
.Lpoole_ap_runtime_fault_halt:
    hlt
    jmp .Lpoole_ap_runtime_fault_halt

    .balign 8
.Lpoole_ap_runtime_initial_fcw:
    .word 0x037f
    .balign 4
.Lpoole_ap_runtime_initial_mxcsr:
    .long 0x00001f80
    .balign 8
.Lpoole_ap_runtime_gdt_pointer:
    .word .Lpoole_ap_runtime_gdt_end - poole_ap_runtime_trampoline_gdt - 1
poole_ap_runtime_patch_gdt_base:
    .long 0
    .balign 8
poole_ap_runtime_trampoline_gdt:
    .quad 0x0000000000000000
    .quad 0x00cf9b000000ffff
    .quad 0x00cf93000000ffff
    .quad 0x00af9b000000ffff
    .quad 0x00cf93000000ffff
.Lpoole_ap_runtime_gdt_end:
    .balign 8
.Lpoole_ap_runtime_config_cr3:
poole_ap_runtime_patch_cr3:
    .long 0
    .long 0
.Lpoole_ap_runtime_config_stack_top:
poole_ap_runtime_patch_stack_top:
    .quad 0
.Lpoole_ap_runtime_config_mailbox:
poole_ap_runtime_patch_mailbox:
    .quad 0
.Lpoole_ap_runtime_config_gdtr:
    .word 39
poole_ap_runtime_patch_gdtr_base:
    .quad 0
.Lpoole_ap_runtime_config_idtr:
    .word 4095
poole_ap_runtime_patch_idtr_base:
    .quad 0
.Lpoole_ap_runtime_config_xstate:
poole_ap_runtime_patch_xstate:
    .quad 0
poole_ap_runtime_trampoline_end:
    .code64
"#
);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct ApRuntimeTrampolineOffsets {
    protected_patch: usize,
    long_patch: usize,
    gdt_base_patch: usize,
    cr3_patch: usize,
    stack_top_patch: usize,
    mailbox_patch: usize,
    gdtr_base_patch: usize,
    idtr_base_patch: usize,
    xstate_patch: usize,
    protected_entry: usize,
    long_entry: usize,
    fault_entry: usize,
    gdt: usize,
}

unsafe extern "C" {
    static poole_ap_runtime_trampoline_start: u8;
    static poole_ap_runtime_trampoline_end: u8;
    static poole_ap_runtime_trampoline_protected_entry: u8;
    static poole_ap_runtime_trampoline_long_entry: u8;
    static poole_ap_runtime_trampoline_fault: u8;
    static poole_ap_runtime_trampoline_gdt: u8;
    static poole_ap_runtime_patch_protected_offset: u8;
    static poole_ap_runtime_patch_long_offset: u8;
    static poole_ap_runtime_patch_gdt_base: u8;
    static poole_ap_runtime_patch_cr3: u8;
    static poole_ap_runtime_patch_stack_top: u8;
    static poole_ap_runtime_patch_mailbox: u8;
    static poole_ap_runtime_patch_gdtr_base: u8;
    static poole_ap_runtime_patch_idtr_base: u8;
    static poole_ap_runtime_patch_xstate: u8;
}

fn ap_runtime_trampoline_offsets(start: *const u8) -> Option<ApRuntimeTrampolineOffsets> {
    Some(ApRuntimeTrampolineOffsets {
        protected_patch: ap_symbol_offset(
            &raw const poole_ap_runtime_patch_protected_offset,
            start,
        )?,
        long_patch: ap_symbol_offset(&raw const poole_ap_runtime_patch_long_offset, start)?,
        gdt_base_patch: ap_symbol_offset(&raw const poole_ap_runtime_patch_gdt_base, start)?,
        cr3_patch: ap_symbol_offset(&raw const poole_ap_runtime_patch_cr3, start)?,
        stack_top_patch: ap_symbol_offset(&raw const poole_ap_runtime_patch_stack_top, start)?,
        mailbox_patch: ap_symbol_offset(&raw const poole_ap_runtime_patch_mailbox, start)?,
        gdtr_base_patch: ap_symbol_offset(&raw const poole_ap_runtime_patch_gdtr_base, start)?,
        idtr_base_patch: ap_symbol_offset(&raw const poole_ap_runtime_patch_idtr_base, start)?,
        xstate_patch: ap_symbol_offset(&raw const poole_ap_runtime_patch_xstate, start)?,
        protected_entry: ap_symbol_offset(
            &raw const poole_ap_runtime_trampoline_protected_entry,
            start,
        )?,
        long_entry: ap_symbol_offset(&raw const poole_ap_runtime_trampoline_long_entry, start)?,
        fault_entry: ap_symbol_offset(&raw const poole_ap_runtime_trampoline_fault, start)?,
        gdt: ap_symbol_offset(&raw const poole_ap_runtime_trampoline_gdt, start)?,
    })
}

core::arch::global_asm!(
    r#"
    .section .text.poole_ap_ipi_trampoline,"ax",@progbits
    .balign 16
    .global poole_ap_ipi_trampoline_start
    .global poole_ap_ipi_trampoline_end
    .global poole_ap_ipi_trampoline_protected_entry
    .global poole_ap_ipi_trampoline_long_entry
    .global poole_ap_ipi_trampoline_fault
    .global poole_ap_ipi_reschedule
    .global poole_ap_ipi_shootdown
    .global poole_ap_ipi_call_function
    .global poole_ap_ipi_diagnostic
    .global poole_ap_ipi_panic
    .global poole_ap_ipi_stop
    .global poole_ap_ipi_apic_error
    .global poole_ap_ipi_spurious
    .global poole_ap_ipi_trampoline_gdt
    .global poole_ap_ipi_patch_protected_offset
    .global poole_ap_ipi_patch_long_offset
    .global poole_ap_ipi_patch_gdt_base
    .global poole_ap_ipi_patch_cr3
    .global poole_ap_ipi_patch_stack_top
    .global poole_ap_ipi_patch_mailbox
    .global poole_ap_ipi_patch_gdtr_base
    .global poole_ap_ipi_patch_idtr_base
    .global poole_ap_ipi_patch_xstate

    .set poole_ap_ipi_gdt_pointer_offset, .Lpoole_ap_ipi_gdt_pointer - poole_ap_ipi_trampoline_start
    .set poole_ap_ipi_config_cr3_offset, .Lpoole_ap_ipi_config_cr3 - poole_ap_ipi_trampoline_start
    .set poole_ap_ipi_config_stack_top_offset, .Lpoole_ap_ipi_config_stack_top - poole_ap_ipi_trampoline_start
    .set poole_ap_ipi_config_mailbox_offset, .Lpoole_ap_ipi_config_mailbox - poole_ap_ipi_trampoline_start
    .set poole_ap_ipi_config_gdtr_offset, .Lpoole_ap_ipi_config_gdtr - poole_ap_ipi_trampoline_start
    .set poole_ap_ipi_config_idtr_offset, .Lpoole_ap_ipi_config_idtr - poole_ap_ipi_trampoline_start
    .set poole_ap_ipi_config_xstate_offset, .Lpoole_ap_ipi_config_xstate - poole_ap_ipi_trampoline_start

poole_ap_ipi_trampoline_start:
    .code16
    cli
    cld
    xor eax, eax
    mov ax, cs
    shl eax, 4
    mov esi, eax
    .byte 0xbb
    .word poole_ap_ipi_gdt_pointer_offset
    lgdt cs:[bx]
    mov eax, cr0
    or eax, 1
    mov cr0, eax
    .byte 0x66, 0xea
poole_ap_ipi_patch_protected_offset:
    .long 0
    .word 0x0008

    .code32
poole_ap_ipi_trampoline_protected_entry:
    mov ax, 0x0010
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov eax, cr4
    or eax, 0x20
    mov cr4, eax
    mov eax, dword ptr [esi + poole_ap_ipi_config_cr3_offset]
    mov cr3, eax
    mov ecx, 0xc0000080
    rdmsr
    or eax, 0x00000900
    wrmsr
    mov eax, cr0
    or eax, 0x80010001
    mov cr0, eax
    .byte 0xea
poole_ap_ipi_patch_long_offset:
    .long 0
    .word 0x0018

    .code64
poole_ap_ipi_trampoline_long_entry:
    mov ax, 0x0020
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov esi, esi
    mov rsp, qword ptr [rsi + poole_ap_ipi_config_stack_top_offset]
    xor rbp, rbp
    mov rdi, qword ptr [rsi + poole_ap_ipi_config_mailbox_offset]
    lgdt [rsi + poole_ap_ipi_config_gdtr_offset]
    push 0x0008
    lea rax, [rip + .Lpoole_ap_ipi_gdt_live]
    push rax
    retfq
.Lpoole_ap_ipi_gdt_live:
    mov ax, 0x0010
    mov ds, ax
    mov es, ax
    mov ss, ax
    xor eax, eax
    mov fs, ax
    mov gs, ax
    mov ax, 0x0018
    ltr ax
    lidt [rsi + poole_ap_ipi_config_idtr_offset]
    mov dword ptr [rdi + 108], 2

    mov rax, cr0
    or rax, 0x22
    and rax, -13
    mov cr0, rax
    mov rax, cr4
    or rax, 0x00040620
    mov cr4, rax
    xor ecx, ecx
    mov eax, 3
    xor edx, edx
    xsetbv
    fninit
    fldcw word ptr [rip + .Lpoole_ap_ipi_initial_fcw]
    ldmxcsr dword ptr [rip + .Lpoole_ap_ipi_initial_mxcsr]
    mov rbx, qword ptr [rsi + poole_ap_ipi_config_xstate_offset]
    mov eax, 3
    xor edx, edx
    xsave64 [rbx]
    mov dword ptr [rdi + 108], 3

    mov eax, 1
    cpuid
    mov r8d, ebx
    shr r8d, 24
    mov dword ptr [rdi + 28], r8d
    mov dword ptr [rdi + 32], ecx
    mov dword ptr [rdi + 36], edx
    mov eax, 0x0d
    xor ecx, ecx
    cpuid
    mov dword ptr [rdi + 296], eax
    mov dword ptr [rdi + 300], 0
    mov dword ptr [rdi + 304], ebx
    mov dword ptr [rdi + 308], ecx

    mov rax, cr0
    mov qword ptr [rdi + 40], rax
    mov rax, cr3
    mov qword ptr [rdi + 48], rax
    mov rax, cr4
    mov qword ptr [rdi + 56], rax
    mov ecx, 0xc0000080
    rdmsr
    shl rdx, 32
    or rax, rdx
    mov qword ptr [rdi + 64], rax
    xor ecx, ecx
    xgetbv
    shl rdx, 32
    or rax, rdx
    mov qword ptr [rdi + 216], rax

    sgdt [rdi + 320]
    movzx eax, word ptr [rdi + 320]
    mov dword ptr [rdi + 240], eax
    mov rax, qword ptr [rdi + 322]
    mov qword ptr [rdi + 192], rax
    sidt [rdi + 336]
    movzx eax, word ptr [rdi + 336]
    mov dword ptr [rdi + 244], eax
    mov rax, qword ptr [rdi + 338]
    mov qword ptr [rdi + 200], rax
    str ax
    movzx eax, ax
    mov dword ptr [rdi + 248], eax
    mov ax, cs
    movzx eax, ax
    mov dword ptr [rdi + 252], eax
    mov ax, ss
    movzx eax, ax
    mov dword ptr [rdi + 256], eax
    mov qword ptr [rdi + 208], rsp
    fnstcw word ptr [rdi + 272]
    stmxcsr dword ptr [rdi + 276]
    mov rbx, qword ptr [rsi + poole_ap_ipi_config_xstate_offset]
    mov rax, qword ptr [rbx + 512]
    mov qword ptr [rdi + 224], rax

    mov rbx, {apic_physical}
    mov eax, dword ptr [rbx + {apic_spurious_offset}]
    and eax, 0xffffff00
    or eax, 0x000001ff
    mov dword ptr [rbx + {apic_spurious_offset}], eax
    mov rax, qword ptr [rdi + {ipi_magic_offset}]
    mov rbx, {ipi_magic}
    cmp rax, rbx
    jne poole_ap_ipi_trampoline_fault
    cmp dword ptr [rdi + {ipi_version_offset}], {ipi_version}
    jne poole_ap_ipi_trampoline_fault
    mov rax, qword ptr [rdi + {shootdown_magic_offset}]
    mov rbx, {shootdown_magic}
    cmp rax, rbx
    jne poole_ap_ipi_trampoline_fault
    cmp dword ptr [rdi + {shootdown_version_offset}], {shootdown_version}
    jne poole_ap_ipi_trampoline_fault
    mov rax, qword ptr [rdi + {shootdown_virtual_offset}]
    mov rbx, {shootdown_probe_virtual}
    cmp rax, rbx
    jne poole_ap_ipi_trampoline_fault
    mov rbx, qword ptr [rax]
    mov qword ptr [rdi + {shootdown_observed_before_offset}], rbx

    lfence
    rdtsc
    shl rdx, 32
    or rax, rdx
    mov qword ptr [rdi + 72], rax
    mov dword ptr [rdi + 108], 4
    mov dword ptr [rdi + {ipi_service_offset}], {service_online}
    mfence
    mov dword ptr [rdi + 12], 2
    sti
    pushfq
    pop rax
    mov qword ptr [rdi + 232], rax
    mov dword ptr [rdi + 268], 1
.Lpoole_ap_ipi_wait:
    hlt
    jmp .Lpoole_ap_ipi_wait

poole_ap_ipi_reschedule:
    push rax
    mov eax, 1
    jmp .Lpoole_ap_ipi_common
poole_ap_ipi_shootdown:
    push rax
    mov eax, 2
    jmp .Lpoole_ap_ipi_common
poole_ap_ipi_call_function:
    push rax
    mov eax, 3
    jmp .Lpoole_ap_ipi_common
poole_ap_ipi_diagnostic:
    push rax
    mov eax, 4
    jmp .Lpoole_ap_ipi_common
poole_ap_ipi_panic:
    push rax
    mov eax, 5
    jmp .Lpoole_ap_ipi_common
poole_ap_ipi_stop:
    push rax
    mov eax, 6

.Lpoole_ap_ipi_common:
    push rbx
    push rcx
    push rdx
    push rsi
    push rdi
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push r14
    push r15
    mov r15d, eax
    mov rdi, qword ptr [rip + .Lpoole_ap_ipi_config_mailbox]
    inc dword ptr [rdi + {delivery_offset}]
    xor r14d, r14d

    cmp dword ptr [rdi + {request_status_offset}], {request_armed}
    jne .Lpoole_ap_ipi_deny_state
    mov rax, qword ptr [rdi + {request_cap_high_offset}]
    mov rbx, {capability_high}
    cmp rax, rbx
    jne .Lpoole_ap_ipi_deny_capability
    mov rax, qword ptr [rdi + {request_cap_low_offset}]
    mov rbx, {capability_low}
    cmp rax, rbx
    jne .Lpoole_ap_ipi_deny_capability
    mov rax, qword ptr [rdi + {request_attempt_offset}]
    mov rbx, qword ptr [rdi + {ack_attempt_offset}]
    inc rbx
    cmp rax, rbx
    jne .Lpoole_ap_ipi_deny_attempt
    cmp dword ptr [rdi + {request_operation_offset}], r15d
    jne .Lpoole_ap_ipi_deny_operation
    lea ebx, [r15d + 0xdf]
    cmp dword ptr [rdi + {request_vector_offset}], ebx
    jne .Lpoole_ap_ipi_deny_vector
    mov ebx, dword ptr [rdi + 28]
    cmp dword ptr [rdi + {request_target_offset}], ebx
    jne .Lpoole_ap_ipi_deny_target

    mov rax, {request_checksum_seed}
    xor rax, qword ptr [rdi + {request_cap_high_offset}]
    xor rax, qword ptr [rdi + {request_cap_low_offset}]
    xor rax, qword ptr [rdi + {request_attempt_offset}]
    xor rax, qword ptr [rdi + {request_sequence_offset}]
    xor rax, qword ptr [rdi + {payload_offset}]
    mov ebx, dword ptr [rdi + {request_operation_offset}]
    xor rax, rbx
    mov ebx, dword ptr [rdi + {request_vector_offset}]
    xor rax, rbx
    mov ebx, dword ptr [rdi + {request_target_offset}]
    xor rax, rbx
    cmp rax, qword ptr [rdi + {request_checksum_offset}]
    jne .Lpoole_ap_ipi_deny_checksum

    mov rax, qword ptr [rdi + {request_sequence_offset}]
    mov rbx, qword ptr [rdi + {last_sequence_offset}]
    cmp rax, rbx
    je .Lpoole_ap_ipi_deny_duplicate
    jb .Lpoole_ap_ipi_deny_stale
    inc rbx
    cmp rax, rbx
    jne .Lpoole_ap_ipi_deny_stale

    cmp r15d, 1
    je .Lpoole_ap_ipi_payload_reschedule
    cmp r15d, 2
    je .Lpoole_ap_ipi_payload_shootdown
    cmp r15d, 3
    je .Lpoole_ap_ipi_payload_call
    cmp r15d, 4
    je .Lpoole_ap_ipi_payload_diagnostic
    cmp r15d, 5
    je .Lpoole_ap_ipi_payload_panic
    mov rbx, {stop_token}
    jmp .Lpoole_ap_ipi_payload_compare
.Lpoole_ap_ipi_payload_reschedule:
    xor ebx, ebx
    jmp .Lpoole_ap_ipi_payload_compare
.Lpoole_ap_ipi_payload_shootdown:
    mov ebx, {shootdown_active_generation}
    jmp .Lpoole_ap_ipi_payload_compare
.Lpoole_ap_ipi_payload_call:
    mov rbx, {call_token}
    jmp .Lpoole_ap_ipi_payload_compare
.Lpoole_ap_ipi_payload_diagnostic:
    mov rbx, {diagnostic_token}
    jmp .Lpoole_ap_ipi_payload_compare
.Lpoole_ap_ipi_payload_panic:
    mov rbx, {panic_token}
.Lpoole_ap_ipi_payload_compare:
    cmp qword ptr [rdi + {payload_offset}], rbx
    jne .Lpoole_ap_ipi_deny_payload
    cmp r15d, 2
    jne .Lpoole_ap_ipi_payload_valid
    cmp dword ptr [rdi + {shootdown_state_offset}], {shootdown_state_armed}
    jne .Lpoole_ap_ipi_deny_shootdown_state
    mov rax, cr3
    mov rbx, {shootdown_root_mask}
    and rax, rbx
    cmp rax, qword ptr [rdi + {shootdown_root_offset}]
    jne .Lpoole_ap_ipi_deny_shootdown_root
    mov rax, qword ptr [rdi + {shootdown_virtual_offset}]
    mov rbx, {shootdown_probe_virtual}
    cmp rax, rbx
    jne .Lpoole_ap_ipi_deny_shootdown_address
    mov rax, qword ptr [rdi + {shootdown_retired_generation_offset}]
    cmp rax, {shootdown_retired_generation}
    jne .Lpoole_ap_ipi_deny_shootdown_generation
    mov rbx, qword ptr [rdi + {shootdown_active_generation_offset}]
    cmp rbx, {shootdown_active_generation}
    jne .Lpoole_ap_ipi_deny_shootdown_generation
    inc rax
    cmp rax, rbx
    jne .Lpoole_ap_ipi_deny_shootdown_generation
    cmp rbx, qword ptr [rdi + {shootdown_last_ack_generation_offset}]
    jbe .Lpoole_ap_ipi_deny_shootdown_generation
    mov rax, qword ptr [rdi + {shootdown_target_mask_offset}]
    mov ecx, dword ptr [rdi + 28]
    cmp ecx, 64
    jae .Lpoole_ap_ipi_deny_shootdown_target
    mov rbx, 1
    shl rbx, cl
    cmp rax, rbx
    jne .Lpoole_ap_ipi_deny_shootdown_target
    mov rax, qword ptr [rdi + {shootdown_old_frame_offset}]
    test rax, rax
    jz .Lpoole_ap_ipi_deny_shootdown_address
    test rax, 0xfff
    jnz .Lpoole_ap_ipi_deny_shootdown_address
    mov rbx, qword ptr [rdi + {shootdown_new_frame_offset}]
    test rbx, rbx
    jz .Lpoole_ap_ipi_deny_shootdown_address
    test rbx, 0xfff
    jnz .Lpoole_ap_ipi_deny_shootdown_address
    cmp rax, rbx
    je .Lpoole_ap_ipi_deny_shootdown_address
    mov rax, {shootdown_request_checksum_seed}
    xor rax, qword ptr [rdi + {shootdown_root_offset}]
    xor rax, qword ptr [rdi + {shootdown_virtual_offset}]
    xor rax, qword ptr [rdi + {shootdown_retired_generation_offset}]
    xor rax, qword ptr [rdi + {shootdown_active_generation_offset}]
    xor rax, qword ptr [rdi + {shootdown_target_mask_offset}]
    xor rax, qword ptr [rdi + {shootdown_old_frame_offset}]
    xor rax, qword ptr [rdi + {shootdown_new_frame_offset}]
    cmp rax, qword ptr [rdi + {shootdown_request_checksum_offset}]
    jne .Lpoole_ap_ipi_deny_shootdown_checksum
.Lpoole_ap_ipi_payload_valid:
    cmp dword ptr [rdi + {panic_latched_offset}], 0
    je .Lpoole_ap_ipi_accept
    cmp r15d, 4
    je .Lpoole_ap_ipi_accept
    cmp r15d, 6
    jne .Lpoole_ap_ipi_deny_panic

.Lpoole_ap_ipi_accept:
    mov r13d, {ack_accepted}
    inc dword ptr [rdi + {accepted_offset}]
    mov rax, qword ptr [rdi + {request_sequence_offset}]
    mov qword ptr [rdi + {last_sequence_offset}], rax
    cmp r15d, 5
    je .Lpoole_ap_ipi_count_panic
    cmp r15d, 6
    je .Lpoole_ap_ipi_count_stop
    lea rbx, [rdi + {operation_count_base}]
    inc dword ptr [rbx + r15*4]
    jmp .Lpoole_ap_ipi_counted
.Lpoole_ap_ipi_count_panic:
    inc dword ptr [rdi + {panic_count_offset}]
    jmp .Lpoole_ap_ipi_counted
.Lpoole_ap_ipi_count_stop:
    inc dword ptr [rdi + {stop_count_offset}]
.Lpoole_ap_ipi_counted:
    cmp r15d, 1
    je .Lpoole_ap_ipi_result_reschedule
    cmp r15d, 2
    je .Lpoole_ap_ipi_result_shootdown
    cmp r15d, 3
    je .Lpoole_ap_ipi_result_call
    cmp r15d, 4
    je .Lpoole_ap_ipi_result_diagnostic
    cmp r15d, 5
    je .Lpoole_ap_ipi_result_panic
    mov r12, {result_stop}
    jmp .Lpoole_ap_ipi_respond
.Lpoole_ap_ipi_result_reschedule:
    mov r12, {result_reschedule}
    jmp .Lpoole_ap_ipi_respond
.Lpoole_ap_ipi_result_shootdown:
    mov rax, qword ptr [rdi + {shootdown_virtual_offset}]
    invlpg [rax]
    mfence
    mov rbx, qword ptr [rax]
    mov qword ptr [rdi + {shootdown_observed_after_offset}], rbx
    inc qword ptr [rdi + {shootdown_invalidation_count_offset}]
    mov rax, qword ptr [rdi + {shootdown_active_generation_offset}]
    mov qword ptr [rdi + {shootdown_last_ack_generation_offset}], rax
    mov rax, qword ptr [rdi + {shootdown_target_mask_offset}]
    mov qword ptr [rdi + {shootdown_ack_mask_offset}], rax
    mov dword ptr [rdi + {shootdown_error_offset}], 0
    mov dword ptr [rdi + {shootdown_state_offset}], {shootdown_state_acked}
    mov rax, {shootdown_response_checksum_seed}
    xor rax, qword ptr [rdi + {shootdown_root_offset}]
    xor rax, qword ptr [rdi + {shootdown_virtual_offset}]
    xor rax, qword ptr [rdi + {shootdown_active_generation_offset}]
    xor rax, qword ptr [rdi + {shootdown_target_mask_offset}]
    xor rax, qword ptr [rdi + {shootdown_ack_mask_offset}]
    xor rax, qword ptr [rdi + {shootdown_observed_before_offset}]
    xor rax, qword ptr [rdi + {shootdown_observed_after_offset}]
    xor rax, qword ptr [rdi + {shootdown_invalidation_count_offset}]
    xor rax, qword ptr [rdi + {shootdown_last_ack_generation_offset}]
    mov ebx, dword ptr [rdi + {shootdown_state_offset}]
    xor rax, rbx
    mov ebx, dword ptr [rdi + {shootdown_error_offset}]
    xor rax, rbx
    mov qword ptr [rdi + {shootdown_response_checksum_offset}], rax
    mov r12, {result_shootdown}
    jmp .Lpoole_ap_ipi_respond
.Lpoole_ap_ipi_result_call:
    mov r12, {result_call}
    jmp .Lpoole_ap_ipi_respond
.Lpoole_ap_ipi_result_diagnostic:
    mov r12, {result_diagnostic}
    jmp .Lpoole_ap_ipi_respond
.Lpoole_ap_ipi_result_panic:
    mov r12, {result_panic}
    mov dword ptr [rdi + {panic_latched_offset}], 1
    mov dword ptr [rdi + {ipi_service_offset}], {service_panic}
    jmp .Lpoole_ap_ipi_respond

.Lpoole_ap_ipi_deny_state:
    mov r14d, {error_state}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_capability:
    mov r14d, {error_capability}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_attempt:
    mov r14d, {error_attempt}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_operation:
    mov r14d, {error_operation}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_vector:
    mov r14d, {error_vector}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_target:
    mov r14d, {error_target}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_checksum:
    mov r14d, {error_checksum}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_stale:
    mov r14d, {error_stale}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_duplicate:
    mov r14d, {error_duplicate}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_payload:
    mov r14d, {error_payload}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_panic:
    mov r14d, {error_panic}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_shootdown_state:
    mov r14d, {error_shootdown_state}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_shootdown_root:
    mov r14d, {error_shootdown_root}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_shootdown_generation:
    mov r14d, {error_shootdown_generation}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_shootdown_target:
    mov r14d, {error_shootdown_target}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_shootdown_address:
    mov r14d, {error_shootdown_address}
    jmp .Lpoole_ap_ipi_deny
.Lpoole_ap_ipi_deny_shootdown_checksum:
    mov r14d, {error_shootdown_checksum}
.Lpoole_ap_ipi_deny:
    mov r13d, {ack_denied}
    xor r12d, r12d
    inc dword ptr [rdi + {denied_offset}]

.Lpoole_ap_ipi_respond:
    mov dword ptr [rdi + {request_status_offset}], 0
    mov dword ptr [rdi + {ack_operation_offset}], r15d
    mov dword ptr [rdi + {ack_status_offset}], r13d
    mov dword ptr [rdi + {ack_error_offset}], r14d
    mov rax, qword ptr [rdi + {request_sequence_offset}]
    mov qword ptr [rdi + {ack_sequence_offset}], rax
    mov qword ptr [rdi + {result_offset}], r12
    mov rax, {response_checksum_seed}
    xor rax, qword ptr [rdi + {request_attempt_offset}]
    xor rax, qword ptr [rdi + {request_sequence_offset}]
    xor rax, r12
    xor rax, qword ptr [rdi + {last_sequence_offset}]
    xor rax, r15
    xor rax, r13
    xor rax, r14
    mov ebx, dword ptr [rdi + {delivery_offset}]
    xor rax, rbx
    mov ebx, dword ptr [rdi + {accepted_offset}]
    xor rax, rbx
    mov ebx, dword ptr [rdi + {denied_offset}]
    xor rax, rbx
    mov qword ptr [rdi + {response_checksum_offset}], rax
    inc dword ptr [rdi + {eoi_offset}]
    mov ebx, {apic_physical}
    mov dword ptr [rbx + {apic_eoi_offset}], 0
    mfence
    mov rax, qword ptr [rdi + {request_attempt_offset}]
    mov qword ptr [rdi + {ack_attempt_offset}], rax
    cmp r15d, 6
    jne .Lpoole_ap_ipi_return
    cmp r13d, {ack_accepted}
    je .Lpoole_ap_ipi_terminal_stop

.Lpoole_ap_ipi_return:
    pop r15
    pop r14
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rbx
    pop rax
    iretq

.Lpoole_ap_ipi_terminal_stop:
    cli
    lfence
    rdtsc
    shl rdx, 32
    or rax, rdx
    mov qword ptr [rdi + 80], rax
    mov rbx, qword ptr [rip + .Lpoole_ap_ipi_config_xstate]
    mov eax, 3
    xor edx, edx
    xrstor64 [rbx]
    mov dword ptr [rdi + 280], 0
    mov dword ptr [rdi + 284], 1
    mov dword ptr [rdi + 288], 1
    pushfq
    pop rax
    mov qword ptr [rdi + 232], rax
    mov dword ptr [rdi + 268], 0
    mov dword ptr [rdi + 16], 1
    mov dword ptr [rdi + 108], 5
    mov dword ptr [rdi + {ipi_service_offset}], {service_quiesced}
    mfence
    mov dword ptr [rdi + 12], 3
.Lpoole_ap_ipi_parked:
    hlt
    jmp .Lpoole_ap_ipi_parked

poole_ap_ipi_apic_error:
    push rax
    push rbx
    mov rax, qword ptr [rip + .Lpoole_ap_ipi_config_mailbox]
    inc dword ptr [rax + {apic_error_count_offset}]
    inc dword ptr [rax + {eoi_offset}]
    mov ebx, {apic_physical}
    mov dword ptr [rbx + {apic_eoi_offset}], 0
    pop rbx
    pop rax
    iretq

poole_ap_ipi_spurious:
    push rax
    mov rax, qword ptr [rip + .Lpoole_ap_ipi_config_mailbox]
    inc dword ptr [rax + {spurious_count_offset}]
    pop rax
    iretq

poole_ap_ipi_trampoline_fault:
    cli
    mov rax, qword ptr [rip + .Lpoole_ap_ipi_config_mailbox]
    mov dword ptr [rax + 292], 1
    mov dword ptr [rax + 108], 0xffffffff
    mov dword ptr [rax + {ipi_service_offset}], 0xffffffff
    mfence
    mov dword ptr [rax + 12], 0xffffffff
.Lpoole_ap_ipi_fault_halt:
    hlt
    jmp .Lpoole_ap_ipi_fault_halt

    .balign 8
.Lpoole_ap_ipi_initial_fcw:
    .word 0x037f
    .balign 4
.Lpoole_ap_ipi_initial_mxcsr:
    .long 0x00001f80
    .balign 8
.Lpoole_ap_ipi_gdt_pointer:
    .word .Lpoole_ap_ipi_gdt_end - poole_ap_ipi_trampoline_gdt - 1
poole_ap_ipi_patch_gdt_base:
    .long 0
    .balign 8
poole_ap_ipi_trampoline_gdt:
    .quad 0x0000000000000000
    .quad 0x00cf9b000000ffff
    .quad 0x00cf93000000ffff
    .quad 0x00af9b000000ffff
    .quad 0x00cf93000000ffff
.Lpoole_ap_ipi_gdt_end:
    .balign 8
.Lpoole_ap_ipi_config_cr3:
poole_ap_ipi_patch_cr3:
    .long 0
    .long 0
.Lpoole_ap_ipi_config_stack_top:
poole_ap_ipi_patch_stack_top:
    .quad 0
.Lpoole_ap_ipi_config_mailbox:
poole_ap_ipi_patch_mailbox:
    .quad 0
.Lpoole_ap_ipi_config_gdtr:
    .word 39
poole_ap_ipi_patch_gdtr_base:
    .quad 0
.Lpoole_ap_ipi_config_idtr:
    .word 4095
poole_ap_ipi_patch_idtr_base:
    .quad 0
.Lpoole_ap_ipi_config_xstate:
poole_ap_ipi_patch_xstate:
    .quad 0
poole_ap_ipi_trampoline_end:
    .code64
"#,
    apic_physical = const smp_ipi::APIC_PHYSICAL_ADDRESS,
    apic_eoi_offset = const smp_ipi::APIC_EOI_OFFSET,
    apic_spurious_offset = const smp_ipi::APIC_SPURIOUS_OFFSET,
    ipi_magic_offset = const smp_ipi::MAGIC_OFFSET,
    ipi_version_offset = const smp_ipi::VERSION_OFFSET,
    ipi_service_offset = const smp_ipi::SERVICE_STATE_OFFSET,
    request_cap_high_offset = const smp_ipi::REQUEST_CAPABILITY_HIGH_OFFSET,
    request_cap_low_offset = const smp_ipi::REQUEST_CAPABILITY_LOW_OFFSET,
    request_attempt_offset = const smp_ipi::REQUEST_ATTEMPT_OFFSET,
    request_sequence_offset = const smp_ipi::REQUEST_SEQUENCE_OFFSET,
    payload_offset = const smp_ipi::PAYLOAD_OFFSET,
    request_checksum_offset = const smp_ipi::REQUEST_CHECKSUM_OFFSET,
    ack_attempt_offset = const smp_ipi::ACK_ATTEMPT_OFFSET,
    ack_sequence_offset = const smp_ipi::ACK_SEQUENCE_OFFSET,
    result_offset = const smp_ipi::RESULT_OFFSET,
    response_checksum_offset = const smp_ipi::RESPONSE_CHECKSUM_OFFSET,
    last_sequence_offset = const smp_ipi::LAST_ACCEPTED_SEQUENCE_OFFSET,
    request_operation_offset = const smp_ipi::REQUEST_OPERATION_OFFSET,
    request_vector_offset = const smp_ipi::REQUEST_VECTOR_OFFSET,
    request_target_offset = const smp_ipi::REQUEST_TARGET_APIC_ID_OFFSET,
    request_status_offset = const smp_ipi::REQUEST_STATUS_OFFSET,
    ack_operation_offset = const smp_ipi::ACK_OPERATION_OFFSET,
    ack_status_offset = const smp_ipi::ACK_STATUS_OFFSET,
    ack_error_offset = const smp_ipi::ACK_ERROR_OFFSET,
    delivery_offset = const smp_ipi::DELIVERY_COUNT_OFFSET,
    eoi_offset = const smp_ipi::EOI_COUNT_OFFSET,
    accepted_offset = const smp_ipi::ACCEPTED_COUNT_OFFSET,
    denied_offset = const smp_ipi::DENIED_COUNT_OFFSET,
    operation_count_base = const (smp_ipi::RESCHEDULE_COUNT_OFFSET - 4),
    stop_count_offset = const smp_ipi::STOP_COUNT_OFFSET,
    panic_count_offset = const smp_ipi::PANIC_COUNT_OFFSET,
    panic_latched_offset = const smp_ipi::PANIC_LATCHED_OFFSET,
    spurious_count_offset = const smp_ipi::SPURIOUS_COUNT_OFFSET,
    apic_error_count_offset = const smp_ipi::APIC_ERROR_COUNT_OFFSET,
    shootdown_magic_offset = const smp_ipi::SHOOTDOWN_MAGIC_OFFSET,
    shootdown_version_offset = const smp_ipi::SHOOTDOWN_VERSION_OFFSET,
    shootdown_state_offset = const smp_ipi::SHOOTDOWN_STATE_OFFSET,
    shootdown_error_offset = const smp_ipi::SHOOTDOWN_ERROR_OFFSET,
    shootdown_root_offset = const smp_ipi::SHOOTDOWN_ROOT_PHYSICAL_OFFSET,
    shootdown_virtual_offset = const smp_ipi::SHOOTDOWN_VIRTUAL_ADDRESS_OFFSET,
    shootdown_retired_generation_offset = const smp_ipi::SHOOTDOWN_RETIRED_GENERATION_OFFSET,
    shootdown_active_generation_offset = const smp_ipi::SHOOTDOWN_ACTIVE_GENERATION_OFFSET,
    shootdown_target_mask_offset = const smp_ipi::SHOOTDOWN_TARGET_MASK_OFFSET,
    shootdown_ack_mask_offset = const smp_ipi::SHOOTDOWN_ACK_MASK_OFFSET,
    shootdown_old_frame_offset = const smp_ipi::SHOOTDOWN_OLD_FRAME_PHYSICAL_OFFSET,
    shootdown_new_frame_offset = const smp_ipi::SHOOTDOWN_NEW_FRAME_PHYSICAL_OFFSET,
    shootdown_observed_before_offset = const smp_ipi::SHOOTDOWN_OBSERVED_BEFORE_OFFSET,
    shootdown_observed_after_offset = const smp_ipi::SHOOTDOWN_OBSERVED_AFTER_OFFSET,
    shootdown_invalidation_count_offset = const smp_ipi::SHOOTDOWN_INVALIDATION_COUNT_OFFSET,
    shootdown_request_checksum_offset = const smp_ipi::SHOOTDOWN_REQUEST_CHECKSUM_OFFSET,
    shootdown_response_checksum_offset = const smp_ipi::SHOOTDOWN_RESPONSE_CHECKSUM_OFFSET,
    shootdown_last_ack_generation_offset = const smp_ipi::SHOOTDOWN_LAST_ACK_GENERATION_OFFSET,
    ipi_magic = const smp_ipi::EXTENSION_MAGIC,
    ipi_version = const smp_ipi::EXTENSION_VERSION,
    service_online = const smp_ipi::SERVICE_STATE_ONLINE,
    service_panic = const smp_ipi::SERVICE_STATE_PANIC,
    service_quiesced = const smp_ipi::SERVICE_STATE_QUIESCED,
    request_armed = const smp_ipi::REQUEST_ARMED,
    ack_accepted = const smp_ipi::ACK_ACCEPTED,
    ack_denied = const smp_ipi::ACK_DENIED,
    error_state = const smp_ipi::ERROR_REQUEST_STATE,
    error_capability = const smp_ipi::ERROR_CAPABILITY,
    error_attempt = const smp_ipi::ERROR_ATTEMPT,
    error_operation = const smp_ipi::ERROR_OPERATION,
    error_vector = const smp_ipi::ERROR_VECTOR,
    error_target = const smp_ipi::ERROR_TARGET,
    error_checksum = const smp_ipi::ERROR_CHECKSUM,
    error_stale = const smp_ipi::ERROR_STALE_SEQUENCE,
    error_duplicate = const smp_ipi::ERROR_DUPLICATE_SEQUENCE,
    error_payload = const smp_ipi::ERROR_PAYLOAD,
    error_panic = const smp_ipi::ERROR_PANIC_LATCHED,
    error_shootdown_state = const smp_ipi::ERROR_SHOOTDOWN_STATE,
    error_shootdown_root = const smp_ipi::ERROR_SHOOTDOWN_ROOT,
    error_shootdown_generation = const smp_ipi::ERROR_SHOOTDOWN_GENERATION,
    error_shootdown_target = const smp_ipi::ERROR_SHOOTDOWN_TARGET,
    error_shootdown_address = const smp_ipi::ERROR_SHOOTDOWN_ADDRESS,
    error_shootdown_checksum = const smp_ipi::ERROR_SHOOTDOWN_CHECKSUM,
    capability_high = const smp_ipi::CAPABILITY_HIGH,
    capability_low = const smp_ipi::CAPABILITY_LOW,
    request_checksum_seed = const smp_ipi::REQUEST_CHECKSUM_SEED,
    response_checksum_seed = const smp_ipi::RESPONSE_CHECKSUM_SEED,
    call_token = const smp_ipi::CALL_NOOP_TOKEN,
    diagnostic_token = const smp_ipi::DIAGNOSTIC_TOKEN,
    panic_token = const smp_ipi::PANIC_NOTICE_TOKEN,
    stop_token = const smp_ipi::STOP_TOKEN,
    result_reschedule = const smp_ipi::RESULT_RESCHEDULE_OBSERVED,
    result_shootdown = const smp_ipi::RESULT_SHOOTDOWN_INVALIDATED,
    result_call = const smp_ipi::RESULT_CALL_ALLOWLIST_NOOP,
    result_diagnostic = const smp_ipi::RESULT_DIAGNOSTIC_OBSERVED,
    result_panic = const smp_ipi::RESULT_PANIC_LATCHED,
    result_stop = const smp_ipi::RESULT_STOP_QUIESCED,
    shootdown_magic = const smp_ipi::SHOOTDOWN_MAGIC,
    shootdown_version = const smp_ipi::SHOOTDOWN_VERSION,
    shootdown_state_armed = const smp_ipi::SHOOTDOWN_STATE_ARMED,
    shootdown_state_acked = const smp_ipi::SHOOTDOWN_STATE_ACKED,
    shootdown_root_mask = const 0x000f_ffff_ffff_f000u64,
    shootdown_probe_virtual = const smp_ipi::PROBE_VIRTUAL_ADDRESS,
    shootdown_retired_generation = const smp_ipi::RETIRED_GENERATION,
    shootdown_active_generation = const smp_ipi::ACTIVE_GENERATION,
    shootdown_request_checksum_seed = const smp_ipi::SHOOTDOWN_REQUEST_CHECKSUM_SEED,
    shootdown_response_checksum_seed = const smp_ipi::SHOOTDOWN_RESPONSE_CHECKSUM_SEED,
);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct ApIpiTrampolineOffsets {
    protected_patch: usize,
    long_patch: usize,
    gdt_base_patch: usize,
    cr3_patch: usize,
    stack_top_patch: usize,
    mailbox_patch: usize,
    gdtr_base_patch: usize,
    idtr_base_patch: usize,
    xstate_patch: usize,
    protected_entry: usize,
    long_entry: usize,
    handlers: IpiHandlerLayout,
    gdt: usize,
}

unsafe extern "C" {
    static poole_ap_ipi_trampoline_start: u8;
    static poole_ap_ipi_trampoline_end: u8;
    static poole_ap_ipi_trampoline_protected_entry: u8;
    static poole_ap_ipi_trampoline_long_entry: u8;
    static poole_ap_ipi_trampoline_fault: u8;
    static poole_ap_ipi_reschedule: u8;
    static poole_ap_ipi_shootdown: u8;
    static poole_ap_ipi_call_function: u8;
    static poole_ap_ipi_diagnostic: u8;
    static poole_ap_ipi_panic: u8;
    static poole_ap_ipi_stop: u8;
    static poole_ap_ipi_apic_error: u8;
    static poole_ap_ipi_spurious: u8;
    static poole_ap_ipi_trampoline_gdt: u8;
    static poole_ap_ipi_patch_protected_offset: u8;
    static poole_ap_ipi_patch_long_offset: u8;
    static poole_ap_ipi_patch_gdt_base: u8;
    static poole_ap_ipi_patch_cr3: u8;
    static poole_ap_ipi_patch_stack_top: u8;
    static poole_ap_ipi_patch_mailbox: u8;
    static poole_ap_ipi_patch_gdtr_base: u8;
    static poole_ap_ipi_patch_idtr_base: u8;
    static poole_ap_ipi_patch_xstate: u8;
}

fn ap_ipi_trampoline_offsets(start: *const u8) -> Option<ApIpiTrampolineOffsets> {
    Some(ApIpiTrampolineOffsets {
        protected_patch: ap_symbol_offset(&raw const poole_ap_ipi_patch_protected_offset, start)?,
        long_patch: ap_symbol_offset(&raw const poole_ap_ipi_patch_long_offset, start)?,
        gdt_base_patch: ap_symbol_offset(&raw const poole_ap_ipi_patch_gdt_base, start)?,
        cr3_patch: ap_symbol_offset(&raw const poole_ap_ipi_patch_cr3, start)?,
        stack_top_patch: ap_symbol_offset(&raw const poole_ap_ipi_patch_stack_top, start)?,
        mailbox_patch: ap_symbol_offset(&raw const poole_ap_ipi_patch_mailbox, start)?,
        gdtr_base_patch: ap_symbol_offset(&raw const poole_ap_ipi_patch_gdtr_base, start)?,
        idtr_base_patch: ap_symbol_offset(&raw const poole_ap_ipi_patch_idtr_base, start)?,
        xstate_patch: ap_symbol_offset(&raw const poole_ap_ipi_patch_xstate, start)?,
        protected_entry: ap_symbol_offset(
            &raw const poole_ap_ipi_trampoline_protected_entry,
            start,
        )?,
        long_entry: ap_symbol_offset(&raw const poole_ap_ipi_trampoline_long_entry, start)?,
        handlers: IpiHandlerLayout {
            fault: ap_symbol_offset(&raw const poole_ap_ipi_trampoline_fault, start)? as u64,
            reschedule: ap_symbol_offset(&raw const poole_ap_ipi_reschedule, start)? as u64,
            shootdown: ap_symbol_offset(&raw const poole_ap_ipi_shootdown, start)? as u64,
            call_function: ap_symbol_offset(&raw const poole_ap_ipi_call_function, start)? as u64,
            diagnostic: ap_symbol_offset(&raw const poole_ap_ipi_diagnostic, start)? as u64,
            panic: ap_symbol_offset(&raw const poole_ap_ipi_panic, start)? as u64,
            stop: ap_symbol_offset(&raw const poole_ap_ipi_stop, start)? as u64,
            apic_error: ap_symbol_offset(&raw const poole_ap_ipi_apic_error, start)? as u64,
            spurious: ap_symbol_offset(&raw const poole_ap_ipi_spurious, start)? as u64,
        },
        gdt: ap_symbol_offset(&raw const poole_ap_ipi_trampoline_gdt, start)?,
    })
}

core::arch::global_asm!(
    r#"
    .section .rodata.poole_ap_trampoline,"a",@progbits
    .balign 16
    .global poole_ap_trampoline_start
    .global poole_ap_trampoline_end
    .global poole_ap_trampoline_protected_entry
    .global poole_ap_trampoline_long_entry
    .global poole_ap_trampoline_gdt
    .global poole_ap_patch_protected_offset
    .global poole_ap_patch_long_offset
    .global poole_ap_patch_gdt_base
    .global poole_ap_patch_cr3
    .global poole_ap_patch_stack_top
    .global poole_ap_patch_mailbox

    .set poole_ap_gdt_pointer_offset, .Lpoole_ap_gdt_pointer - poole_ap_trampoline_start
    .set poole_ap_config_cr3_offset, .Lpoole_ap_config_cr3 - poole_ap_trampoline_start
    .set poole_ap_config_stack_top_offset, .Lpoole_ap_config_stack_top - poole_ap_trampoline_start
    .set poole_ap_config_mailbox_offset, .Lpoole_ap_config_mailbox - poole_ap_trampoline_start

poole_ap_trampoline_start:
    .code16
    cli
    cld
    xor eax, eax
    mov ax, cs
    shl eax, 4
    mov esi, eax
    .byte 0xbb
    .word poole_ap_gdt_pointer_offset
    lgdt cs:[bx]
    mov eax, cr0
    or eax, 1
    mov cr0, eax
    .byte 0x66, 0xea
poole_ap_patch_protected_offset:
    .long 0
    .word 0x0008

    .code32
poole_ap_trampoline_protected_entry:
    mov ax, 0x0010
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov eax, cr4
    or eax, 0x20
    mov cr4, eax
    mov eax, dword ptr [esi + poole_ap_config_cr3_offset]
    mov cr3, eax
    mov ecx, 0xc0000080
    rdmsr
    or eax, 0x00000900
    wrmsr
    mov eax, cr0
    or eax, 0x80010001
    mov cr0, eax
    .byte 0xea
poole_ap_patch_long_offset:
    .long 0
    .word 0x0018

    .code64
poole_ap_trampoline_long_entry:
    mov ax, 0x0020
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov esi, esi
    mov rsp, qword ptr [rsi + poole_ap_config_stack_top_offset]
    xor rbp, rbp
    mov rdi, qword ptr [rsi + poole_ap_config_mailbox_offset]
    mov eax, 1
    cpuid
    mov r8d, ebx
    shr r8d, 24
    mov dword ptr [rdi + 28], r8d
    mov dword ptr [rdi + 32], ecx
    mov dword ptr [rdi + 36], edx
    mov rax, cr0
    mov qword ptr [rdi + 40], rax
    mov rax, cr3
    mov qword ptr [rdi + 48], rax
    mov rax, cr4
    mov qword ptr [rdi + 56], rax
    mov ecx, 0xc0000080
    rdmsr
    shl rdx, 32
    or rax, rdx
    mov qword ptr [rdi + 64], rax
    lfence
    rdtsc
    shl rdx, 32
    or rax, rdx
    mov qword ptr [rdi + 72], rax
    mfence
    mov dword ptr [rdi + 12], 2
.Lpoole_ap_wait_stop:
    pause
    cmp dword ptr [rdi + 16], 1
    jne .Lpoole_ap_wait_stop
    lfence
    rdtsc
    shl rdx, 32
    or rax, rdx
    mov qword ptr [rdi + 80], rax
    mfence
    mov dword ptr [rdi + 12], 3
.Lpoole_ap_parked:
    cli
    hlt
    jmp .Lpoole_ap_parked

    .balign 8
.Lpoole_ap_gdt_pointer:
    .word .Lpoole_ap_gdt_end - poole_ap_trampoline_gdt - 1
poole_ap_patch_gdt_base:
    .long 0
    .balign 8
poole_ap_trampoline_gdt:
    .quad 0x0000000000000000
    .quad 0x00cf9b000000ffff
    .quad 0x00cf93000000ffff
    .quad 0x00af9b000000ffff
    .quad 0x00cf93000000ffff
.Lpoole_ap_gdt_end:
    .balign 8
.Lpoole_ap_config_cr3:
poole_ap_patch_cr3:
    .long 0
    .long 0
.Lpoole_ap_config_stack_top:
poole_ap_patch_stack_top:
    .quad 0
.Lpoole_ap_config_mailbox:
poole_ap_patch_mailbox:
    .quad 0
poole_ap_trampoline_end:
    .code64
"#
);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct ApTrampolineOffsets {
    protected_patch: usize,
    long_patch: usize,
    gdt_base_patch: usize,
    cr3_patch: usize,
    stack_top_patch: usize,
    mailbox_patch: usize,
    protected_entry: usize,
    long_entry: usize,
    gdt: usize,
}

unsafe extern "C" {
    static poole_ap_trampoline_start: u8;
    static poole_ap_trampoline_end: u8;
    static poole_ap_trampoline_protected_entry: u8;
    static poole_ap_trampoline_long_entry: u8;
    static poole_ap_trampoline_gdt: u8;
    static poole_ap_patch_protected_offset: u8;
    static poole_ap_patch_long_offset: u8;
    static poole_ap_patch_gdt_base: u8;
    static poole_ap_patch_cr3: u8;
    static poole_ap_patch_stack_top: u8;
    static poole_ap_patch_mailbox: u8;
}

fn ap_symbol_offset(symbol: *const u8, start: *const u8) -> Option<usize> {
    (symbol as usize).checked_sub(start as usize)
}

fn ap_trampoline_offsets(start: *const u8) -> Option<ApTrampolineOffsets> {
    Some(ApTrampolineOffsets {
        protected_patch: ap_symbol_offset(&raw const poole_ap_patch_protected_offset, start)?,
        long_patch: ap_symbol_offset(&raw const poole_ap_patch_long_offset, start)?,
        gdt_base_patch: ap_symbol_offset(&raw const poole_ap_patch_gdt_base, start)?,
        cr3_patch: ap_symbol_offset(&raw const poole_ap_patch_cr3, start)?,
        stack_top_patch: ap_symbol_offset(&raw const poole_ap_patch_stack_top, start)?,
        mailbox_patch: ap_symbol_offset(&raw const poole_ap_patch_mailbox, start)?,
        protected_entry: ap_symbol_offset(&raw const poole_ap_trampoline_protected_entry, start)?,
        long_entry: ap_symbol_offset(&raw const poole_ap_trampoline_long_entry, start)?,
        gdt: ap_symbol_offset(&raw const poole_ap_trampoline_gdt, start)?,
    })
}

fn patch_bytes<const N: usize>(
    page: &mut [u8; smp::PAGE_BYTES as usize],
    offset: usize,
    bytes: [u8; N],
) -> Result<(), ()> {
    let target = page
        .get_mut(offset..offset.checked_add(N).ok_or(())?)
        .ok_or(())?;
    target.copy_from_slice(&bytes);
    Ok(())
}

pub fn build_ap_trampoline_page(
    layout: ResourceLayout,
) -> Result<([u8; smp::PAGE_BYTES as usize], usize), ()> {
    let start = &raw const poole_ap_trampoline_start;
    let end = &raw const poole_ap_trampoline_end;
    let length = (end as usize).checked_sub(start as usize).ok_or(())?;
    if length == 0 || length > smp::PAGE_BYTES as usize {
        return Err(());
    }
    let offsets = ap_trampoline_offsets(start).ok_or(())?;
    let mut page = [0u8; smp::PAGE_BYTES as usize];
    // SAFETY: the linker symbols bound one immutable template wholly inside this image.
    let template = unsafe { core::slice::from_raw_parts(start, length) };
    page[..length].copy_from_slice(template);

    let protected = layout
        .trampoline()
        .checked_add(offsets.protected_entry as u64)
        .and_then(|value| u32::try_from(value).ok())
        .ok_or(())?;
    let long = layout
        .trampoline()
        .checked_add(offsets.long_entry as u64)
        .and_then(|value| u32::try_from(value).ok())
        .ok_or(())?;
    let gdt = layout
        .trampoline()
        .checked_add(offsets.gdt as u64)
        .and_then(|value| u32::try_from(value).ok())
        .ok_or(())?;
    patch_bytes(&mut page, offsets.protected_patch, protected.to_le_bytes())?;
    patch_bytes(&mut page, offsets.long_patch, long.to_le_bytes())?;
    patch_bytes(&mut page, offsets.gdt_base_patch, gdt.to_le_bytes())?;
    patch_bytes(
        &mut page,
        offsets.cr3_patch,
        u32::try_from(layout.pml4()).map_err(|_| ())?.to_le_bytes(),
    )?;
    patch_bytes(
        &mut page,
        offsets.stack_top_patch,
        layout.stack_top().to_le_bytes(),
    )?;
    patch_bytes(
        &mut page,
        offsets.mailbox_patch,
        layout.per_cpu().to_le_bytes(),
    )?;
    Ok((page, length))
}

pub fn build_ap_runtime_trampoline_page(
    layout: RuntimeResourceLayout,
) -> Result<([u8; smp_runtime::PAGE_BYTES as usize], usize, u64), ()> {
    let start = &raw const poole_ap_runtime_trampoline_start;
    let end = &raw const poole_ap_runtime_trampoline_end;
    let length = (end as usize).checked_sub(start as usize).ok_or(())?;
    if length == 0 || length > smp_runtime::PAGE_BYTES as usize {
        return Err(());
    }
    let offsets = ap_runtime_trampoline_offsets(start).ok_or(())?;
    let mut page = [0u8; smp_runtime::PAGE_BYTES as usize];
    // SAFETY: the linker symbols bound one immutable template wholly inside this image.
    let template = unsafe { core::slice::from_raw_parts(start, length) };
    page[..length].copy_from_slice(template);

    let protected = layout
        .trampoline()
        .checked_add(offsets.protected_entry as u64)
        .and_then(|value| u32::try_from(value).ok())
        .ok_or(())?;
    let long = layout
        .trampoline()
        .checked_add(offsets.long_entry as u64)
        .and_then(|value| u32::try_from(value).ok())
        .ok_or(())?;
    let gdt = layout
        .trampoline()
        .checked_add(offsets.gdt as u64)
        .and_then(|value| u32::try_from(value).ok())
        .ok_or(())?;
    let fault = layout
        .trampoline()
        .checked_add(offsets.fault_entry as u64)
        .ok_or(())?;
    patch_bytes(&mut page, offsets.protected_patch, protected.to_le_bytes())?;
    patch_bytes(&mut page, offsets.long_patch, long.to_le_bytes())?;
    patch_bytes(&mut page, offsets.gdt_base_patch, gdt.to_le_bytes())?;
    patch_bytes(
        &mut page,
        offsets.cr3_patch,
        u32::try_from(layout.pml4()).map_err(|_| ())?.to_le_bytes(),
    )?;
    patch_bytes(
        &mut page,
        offsets.stack_top_patch,
        layout.rsp0_top().to_le_bytes(),
    )?;
    patch_bytes(
        &mut page,
        offsets.mailbox_patch,
        layout.local().to_le_bytes(),
    )?;
    patch_bytes(
        &mut page,
        offsets.gdtr_base_patch,
        layout.gdt().to_le_bytes(),
    )?;
    patch_bytes(
        &mut page,
        offsets.idtr_base_patch,
        layout.idt().to_le_bytes(),
    )?;
    patch_bytes(
        &mut page,
        offsets.xstate_patch,
        layout.xstate().to_le_bytes(),
    )?;
    Ok((page, length, fault))
}

pub fn build_ap_ipi_trampoline_page(
    layout: RuntimeResourceLayout,
) -> Result<([u8; smp_ipi::PAGE_BYTES as usize], usize, IpiHandlerLayout), ()> {
    let start = &raw const poole_ap_ipi_trampoline_start;
    let end = &raw const poole_ap_ipi_trampoline_end;
    let length = (end as usize).checked_sub(start as usize).ok_or(())?;
    if length == 0 || length > smp_ipi::PAGE_BYTES as usize {
        return Err(());
    }
    let offsets = ap_ipi_trampoline_offsets(start).ok_or(())?;
    let mut page = [0u8; smp_ipi::PAGE_BYTES as usize];
    // SAFETY: the linker symbols bound one immutable template wholly inside this image.
    let template = unsafe { core::slice::from_raw_parts(start, length) };
    page[..length].copy_from_slice(template);

    let physical = |offset: usize| layout.trampoline().checked_add(offset as u64).ok_or(());
    let protected = u32::try_from(physical(offsets.protected_entry)?).map_err(|_| ())?;
    let long = u32::try_from(physical(offsets.long_entry)?).map_err(|_| ())?;
    let gdt = u32::try_from(physical(offsets.gdt)?).map_err(|_| ())?;
    let handlers = IpiHandlerLayout {
        fault: physical(offsets.handlers.fault as usize)?,
        reschedule: physical(offsets.handlers.reschedule as usize)?,
        shootdown: physical(offsets.handlers.shootdown as usize)?,
        call_function: physical(offsets.handlers.call_function as usize)?,
        diagnostic: physical(offsets.handlers.diagnostic as usize)?,
        panic: physical(offsets.handlers.panic as usize)?,
        stop: physical(offsets.handlers.stop as usize)?,
        apic_error: physical(offsets.handlers.apic_error as usize)?,
        spurious: physical(offsets.handlers.spurious as usize)?,
    };
    patch_bytes(&mut page, offsets.protected_patch, protected.to_le_bytes())?;
    patch_bytes(&mut page, offsets.long_patch, long.to_le_bytes())?;
    patch_bytes(&mut page, offsets.gdt_base_patch, gdt.to_le_bytes())?;
    patch_bytes(
        &mut page,
        offsets.cr3_patch,
        u32::try_from(layout.pml4()).map_err(|_| ())?.to_le_bytes(),
    )?;
    patch_bytes(
        &mut page,
        offsets.stack_top_patch,
        layout.rsp0_top().to_le_bytes(),
    )?;
    patch_bytes(
        &mut page,
        offsets.mailbox_patch,
        layout.local().to_le_bytes(),
    )?;
    patch_bytes(
        &mut page,
        offsets.gdtr_base_patch,
        layout.gdt().to_le_bytes(),
    )?;
    patch_bytes(
        &mut page,
        offsets.idtr_base_patch,
        layout.idt().to_le_bytes(),
    )?;
    patch_bytes(
        &mut page,
        offsets.xstate_patch,
        layout.xstate().to_le_bytes(),
    )?;
    Ok((page, length, handlers))
}

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

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PicMasks {
    pub master: u8,
    pub slave: u8,
}

pub unsafe fn mask_legacy_pic() -> Result<PicMasks, ()> {
    // SAFETY: PKIRQ1 owns the fixed dual-8259 data ports while IF is clear.
    let original = unsafe {
        PicMasks {
            master: inb(0x21),
            slave: inb(0xa1),
        }
    };
    // SAFETY: writing all ones masks every legacy PIC input without remapping vectors.
    unsafe {
        outb(0x21, 0xff);
        outb(0xa1, 0xff);
    }
    // SAFETY: readback is limited to the two mask registers just written.
    if unsafe { inb(0x21) } != 0xff || unsafe { inb(0xa1) } != 0xff {
        // SAFETY: restore the exact observed masks after failed readback.
        unsafe {
            outb(0x21, original.master);
            outb(0xa1, original.slave);
        }
        return Err(());
    }
    Ok(original)
}

pub unsafe fn restore_legacy_pic(masks: PicMasks) -> Result<(), ()> {
    // SAFETY: PKIRQ1 still owns the fixed dual-8259 data ports with IF clear.
    unsafe {
        outb(0x21, masks.master);
        outb(0xa1, masks.slave);
    }
    // SAFETY: readback verifies the exact rollback state.
    if unsafe { inb(0x21) } != masks.master || unsafe { inb(0xa1) } != masks.slave {
        return Err(());
    }
    Ok(())
}

pub unsafe fn enable_interrupts_halt_disable() {
    // SAFETY: PKIRQ1 calls this only after a complete IDT/APIC/timer transaction;
    // STI's interrupt shadow keeps HLT adjacent and CLI closes the delivery window.
    unsafe { asm!("sti", "hlt", "cli", options(nomem, nostack)) };
}

pub fn halt_forever() -> ! {
    loop {
        // SAFETY: the terminal kernel state intentionally disables interrupts and halts.
        unsafe { core::arch::asm!("cli", "hlt", options(nomem, nostack)) };
    }
}

/// Reads the complete current CR3 value.
///
/// # Safety
///
/// The caller must execute at CPL0 on x86-64.
pub unsafe fn read_cr3() -> u64 {
    let value: u64;
    // SAFETY: the caller owns this privileged control-register observation.
    unsafe { asm!("mov {}, cr3", out(reg) value, options(nomem, nostack, preserves_flags)) };
    value
}

/// Installs one prevalidated page-table root and performs the architectural CR3 flush.
///
/// # Safety
///
/// The caller must execute at CPL0 and prove that `value` preserves the executing code,
/// current stack, and every operand needed until a later CR3 transition.
pub unsafe fn write_cr3(value: u64) {
    // SAFETY: the caller proves that this exact root is activation eligible.
    unsafe { asm!("mov cr3, {}", in(reg) value, options(nostack, preserves_flags)) };
}

/// Invalidates one canonical virtual address in the current address space.
///
/// # Safety
///
/// The caller must execute at CPL0 and own the page-table transition for `address`.
pub unsafe fn invalidate_page(address: u64) {
    // SAFETY: the caller owns the local invalidation protocol for this address.
    unsafe { asm!("invlpg [{}]", in(reg) address, options(nostack, preserves_flags)) };
}

/// Reads RFLAGS without changing interrupt state.
pub fn read_rflags() -> u64 {
    let value: u64;
    // SAFETY: PUSHFQ/POP to a general register is unprivileged and preserves the flags.
    unsafe { asm!("pushfq", "pop {}", out(reg) value, options(nomem, preserves_flags)) };
    value
}

fn scheduler_stack_pointer(task: u8) -> *mut u64 {
    match task {
        0 => addr_of_mut!(poole_scheduler_task_a_rsp),
        _ => addr_of_mut!(poole_scheduler_task_b_rsp),
    }
}

fn scheduler_stack_base(task: u8) -> *mut u8 {
    // SAFETY: this creates raw addresses only; ownership is enforced by the one-BSP caller.
    unsafe {
        match task {
            0 => addr_of_mut!(SCHEDULER_STACK_A.0).cast::<u8>(),
            _ => addr_of_mut!(SCHEDULER_STACK_B.0).cast::<u8>(),
        }
    }
}

unsafe fn initialize_scheduler_stack(
    stack: *mut u8,
    saved_rsp: *mut u64,
    entry: unsafe extern "C" fn(),
    registers: [u64; 6],
) {
    // SAFETY: the caller exclusively owns the fixed static stack and context slot.
    unsafe {
        write_bytes(stack, SCHEDULER_STACK_FILL, SCHEDULER_STACK_BYTES);
        write_volatile(stack.cast::<u64>(), SCHEDULER_STACK_CANARY);
        write_volatile(
            stack.add(SCHEDULER_HIGH_CANARY_OFFSET).cast::<u64>(),
            SCHEDULER_STACK_CANARY,
        );
        let frame = stack
            .add(SCHEDULER_STACK_BYTES - SCHEDULER_CONTEXT_BYTES)
            .cast::<u64>();
        write_volatile(frame, registers[5]);
        write_volatile(frame.add(1), registers[4]);
        write_volatile(frame.add(2), registers[3]);
        write_volatile(frame.add(3), registers[2]);
        write_volatile(frame.add(4), registers[0]);
        write_volatile(frame.add(5), registers[1]);
        write_volatile(frame.add(6), 1 << 1);
        write_volatile(frame.add(7), entry as usize as u64);
        write_volatile(saved_rsp, frame as u64);
    }
}

fn scheduler_stack_valid(task: u8) -> bool {
    let base = scheduler_stack_base(task);
    let saved = unsafe { read_volatile(scheduler_stack_pointer(task)) };
    let low = base as u64;
    let high = low + SCHEDULER_STACK_BYTES as u64;
    let canaries = unsafe {
        read_volatile(base.cast::<u64>()) == SCHEDULER_STACK_CANARY
            && read_volatile(base.add(SCHEDULER_HIGH_CANARY_OFFSET).cast::<u64>())
                == SCHEDULER_STACK_CANARY
    };
    canaries
        && saved >= low + size_of::<u64>() as u64
        && saved
            .checked_add(SCHEDULER_CONTEXT_BYTES as u64)
            .is_some_and(|end| end <= high)
        && saved.is_multiple_of(SCHEDULER_STACK_ALIGNMENT as u64)
}

fn clear_scheduler_stacks() -> bool {
    for task in 0..2 {
        let base = scheduler_stack_base(task);
        // SAFETY: the task contexts are retired and no switch can resume either stack.
        unsafe { write_bytes(base, 0, SCHEDULER_STACK_BYTES) };
    }
    let mut cleared = true;
    for task in 0..2 {
        let base = scheduler_stack_base(task);
        for offset in 0..SCHEDULER_STACK_BYTES {
            // SAFETY: the fixed stack range remains exclusively owned by this proof.
            cleared &= unsafe { read_volatile(base.add(offset)) } == 0;
        }
        // SAFETY: the retired context slot cannot be consumed after this point.
        unsafe { write_volatile(scheduler_stack_pointer(task), 0) };
    }
    cleared
}

fn run_scheduler_context_switch_inner(
    trace: &[u8; 8],
) -> Result<SchedulerSwitchProof, SchedulerSwitchHardwareError> {
    if trace != &[0, 1, 0, 1, 0, 1, 0, 1] {
        return Err(SchedulerSwitchHardwareError::Trace);
    }
    let rflags_before = read_rflags();
    if rflags_before & (1 << 9) != 0 {
        return Err(SchedulerSwitchHardwareError::InterruptState);
    }
    // SAFETY: selector 15 executes at CPL0 and reads only the current architectural state.
    let cr3_before = unsafe { read_cr3() };
    // SAFETY: long mode defines these three base MSRs; selector 15 does not write them.
    let bases_before = unsafe {
        (
            read_msr(IA32_FS_BASE),
            read_msr(IA32_GS_BASE),
            read_msr(IA32_KERNEL_GS_BASE),
        )
    };

    // SAFETY: this profile is single-entry, one-BSP, and exclusively owns both static stacks.
    unsafe {
        write_volatile(addr_of_mut!(poole_scheduler_kernel_rsp), 0);
        write_volatile(addr_of_mut!(poole_scheduler_task_a_runs), 0);
        write_volatile(addr_of_mut!(poole_scheduler_task_b_runs), 0);
        write_volatile(addr_of_mut!(poole_scheduler_last_task), 0);
        write_volatile(addr_of_mut!(poole_scheduler_transition_count), 0);
        write_volatile(addr_of_mut!(poole_scheduler_register_errors), 0);
        initialize_scheduler_stack(
            scheduler_stack_base(0),
            scheduler_stack_pointer(0),
            poole_scheduler_task_a_entry,
            SCHEDULER_TASK_A_REGISTERS,
        );
        initialize_scheduler_stack(
            scheduler_stack_base(1),
            scheduler_stack_pointer(1),
            poole_scheduler_task_b_entry,
            SCHEDULER_TASK_B_REGISTERS,
        );
    }

    let stack_a = scheduler_stack_base(0) as u64;
    let stack_b = scheduler_stack_base(1) as u64;
    let stack_a_end = stack_a
        .checked_add(SCHEDULER_STACK_BYTES as u64)
        .ok_or(SchedulerSwitchHardwareError::StackGeometry)?;
    let stack_b_end = stack_b
        .checked_add(SCHEDULER_STACK_BYTES as u64)
        .ok_or(SchedulerSwitchHardwareError::StackGeometry)?;
    if !stack_a.is_multiple_of(SCHEDULER_STACK_ALIGNMENT as u64)
        || !stack_b.is_multiple_of(SCHEDULER_STACK_ALIGNMENT as u64)
        || !(stack_a_end <= stack_b || stack_b_end <= stack_a)
    {
        return Err(SchedulerSwitchHardwareError::StackGeometry);
    }

    for (index, task) in trace.iter().copied().enumerate() {
        let runs_before = unsafe {
            if task == 0 {
                read_volatile(addr_of!(poole_scheduler_task_a_runs))
            } else {
                read_volatile(addr_of!(poole_scheduler_task_b_runs))
            }
        };
        // SAFETY: each incoming RSP names a validated frame on a private live stack.
        unsafe {
            write_volatile(addr_of_mut!(poole_scheduler_last_task), 0);
            poole_scheduler_context_switch(
                addr_of_mut!(poole_scheduler_kernel_rsp),
                scheduler_stack_pointer(task),
            );
        }
        let (runs_after, observed_task, transitions, register_errors) = unsafe {
            (
                if task == 0 {
                    read_volatile(addr_of!(poole_scheduler_task_a_runs))
                } else {
                    read_volatile(addr_of!(poole_scheduler_task_b_runs))
                },
                read_volatile(addr_of!(poole_scheduler_last_task)),
                read_volatile(addr_of!(poole_scheduler_transition_count)),
                read_volatile(addr_of!(poole_scheduler_register_errors)),
            )
        };
        if runs_after != runs_before + 1 || observed_task != u64::from(task) + 1 {
            return Err(SchedulerSwitchHardwareError::Trace);
        }
        if transitions != (index as u64 + 1) * 2 {
            return Err(SchedulerSwitchHardwareError::TransitionCount);
        }
        if register_errors != 0 {
            return Err(SchedulerSwitchHardwareError::RegisterState);
        }
        if !scheduler_stack_valid(task) {
            return Err(SchedulerSwitchHardwareError::StackGeometry);
        }
    }

    let rflags_after = read_rflags();
    // SAFETY: these are the same read-only CPL0 observations sampled before the proof.
    let (cr3_after, bases_after) = unsafe {
        (
            read_cr3(),
            (
                read_msr(IA32_FS_BASE),
                read_msr(IA32_GS_BASE),
                read_msr(IA32_KERNEL_GS_BASE),
            ),
        )
    };
    let (task_a_runs, task_b_runs, transitions, register_errors, kernel_rsp) = unsafe {
        (
            read_volatile(addr_of!(poole_scheduler_task_a_runs)),
            read_volatile(addr_of!(poole_scheduler_task_b_runs)),
            read_volatile(addr_of!(poole_scheduler_transition_count)),
            read_volatile(addr_of!(poole_scheduler_register_errors)),
            read_volatile(addr_of!(poole_scheduler_kernel_rsp)),
        )
    };
    if task_a_runs != 4 || task_b_runs != 4 || transitions != 16 || register_errors != 0 {
        return Err(SchedulerSwitchHardwareError::TransitionCount);
    }
    if kernel_rsp == 0 || !kernel_rsp.is_multiple_of(SCHEDULER_STACK_ALIGNMENT as u64) {
        return Err(SchedulerSwitchHardwareError::StackGeometry);
    }
    if rflags_after != rflags_before || cr3_after != cr3_before || bases_after != bases_before {
        return Err(SchedulerSwitchHardwareError::ControlState);
    }
    if !scheduler_stack_valid(0) || !scheduler_stack_valid(1) {
        return Err(SchedulerSwitchHardwareError::StackGeometry);
    }

    Ok(SchedulerSwitchProof {
        dispatch_count: trace.len() as u32,
        machine_transition_count: transitions as u32,
        task_a_runs: task_a_runs as u32,
        task_b_runs: task_b_runs as u32,
        callee_saved_register_count: 6,
        rflags_preserved: true,
        same_cr3: true,
        fs_gs_unchanged: true,
        xstate_unused: true,
        debug_state_unused: true,
        pmu_state_unused: true,
        stacks_distinct: true,
        stack_bytes_each: SCHEDULER_STACK_BYTES as u32,
        stack_alignment: SCHEDULER_STACK_ALIGNMENT as u8,
        stack_bytes_cleared: 0,
        register_error_count: register_errors as u32,
    })
}

pub fn run_scheduler_context_switch_probe(
    trace: &[u8; 8],
) -> Result<SchedulerSwitchProof, SchedulerSwitchHardwareError> {
    let result = run_scheduler_context_switch_inner(trace);
    if !clear_scheduler_stacks() {
        return Err(SchedulerSwitchHardwareError::Clear);
    }
    result.map(|mut proof| {
        proof.stack_bytes_cleared = (2 * SCHEDULER_STACK_BYTES) as u32;
        proof
    })
}

fn scheduler_deferred_stack_base(worker: u8) -> *mut u8 {
    let base = SCHEDULER_DEFERRED_STACK_BASE.load(Ordering::Acquire);
    (base as usize + usize::from(worker) * SCHEDULER_STACK_BYTES) as *mut u8
}

fn scheduler_deferred_stack_pointer(worker: u8) -> *mut u64 {
    match worker {
        0 => addr_of_mut!(poole_scheduler_deferred_worker_a_rsp),
        _ => addr_of_mut!(poole_scheduler_deferred_worker_b_rsp),
    }
}

fn scheduler_deferred_stack_error(worker: u8) -> Option<SchedulerDeferredHardwareError> {
    let base = scheduler_deferred_stack_base(worker);
    let saved = unsafe { read_volatile(scheduler_deferred_stack_pointer(worker)) };
    let low = base as u64;
    let high = low + SCHEDULER_STACK_BYTES as u64;
    if unsafe { read_volatile(base.cast::<u64>()) } != SCHEDULER_STACK_CANARY {
        return Some(SchedulerDeferredHardwareError::StackCanary);
    }
    if saved < low + size_of::<u64>() as u64
        || saved
            .checked_add(SCHEDULER_CONTEXT_BYTES as u64)
            .is_none_or(|end| end > high)
    {
        return Some(SchedulerDeferredHardwareError::StackRange);
    }
    if !saved.is_multiple_of(SCHEDULER_STACK_ALIGNMENT as u64) {
        return Some(SchedulerDeferredHardwareError::StackAlignment);
    }
    None
}

pub fn prepare_scheduler_deferred_workers(
    kernel_stack_top: u64,
) -> Result<SchedulerDeferredHardwareContext, SchedulerDeferredHardwareError> {
    if read_rflags() & (1 << 9) != 0 {
        return Err(SchedulerDeferredHardwareError::InterruptState);
    }
    let kernel_stack_bottom = kernel_stack_top
        .checked_sub(RETAINED_KERNEL_STACK_BYTES as u64)
        .ok_or(SchedulerDeferredHardwareError::StackGeometry)?;
    let worker_region_top = kernel_stack_bottom
        .checked_add(SCHEDULER_DEFERRED_REGION_BYTES as u64)
        .ok_or(SchedulerDeferredHardwareError::StackGeometry)?;
    let current_rsp: u64;
    // SAFETY: this observes only the current kernel stack pointer.
    unsafe {
        asm!("mov {}, rsp", out(reg) current_rsp, options(nomem, nostack, preserves_flags));
    }
    if kernel_stack_top == 0
        || !kernel_stack_top.is_multiple_of(poole_kmap::PAGE_SIZE)
        || !kernel_stack_bottom.is_multiple_of(poole_kmap::PAGE_SIZE)
        || worker_region_top > kernel_stack_top
        || current_rsp < worker_region_top
        || current_rsp >= kernel_stack_top
        || SCHEDULER_DEFERRED_STACK_BASE
            .compare_exchange(0, kernel_stack_bottom, Ordering::AcqRel, Ordering::Acquire)
            .is_err()
    {
        return Err(SchedulerDeferredHardwareError::StackGeometry);
    }
    let stack_a = scheduler_deferred_stack_base(0) as u64;
    let stack_b = scheduler_deferred_stack_base(1) as u64;
    let stack_a_end = stack_a
        .checked_add(SCHEDULER_STACK_BYTES as u64)
        .ok_or(SchedulerDeferredHardwareError::StackGeometry)?;
    let stack_b_end = stack_b
        .checked_add(SCHEDULER_STACK_BYTES as u64)
        .ok_or(SchedulerDeferredHardwareError::StackGeometry)?;
    if !stack_a.is_multiple_of(SCHEDULER_STACK_ALIGNMENT as u64)
        || !stack_b.is_multiple_of(SCHEDULER_STACK_ALIGNMENT as u64)
        || !(stack_a_end <= stack_b || stack_b_end <= stack_a)
    {
        return Err(SchedulerDeferredHardwareError::StackGeometry);
    }
    // SAFETY: selector 17 is single-entry BSP-only and exclusively owns these statics.
    unsafe {
        write_volatile(addr_of_mut!(poole_scheduler_deferred_kernel_rsp), 0);
        write_volatile(addr_of_mut!(poole_scheduler_deferred_worker_a_entries), 0);
        write_volatile(addr_of_mut!(poole_scheduler_deferred_worker_b_entries), 0);
        write_volatile(addr_of_mut!(poole_scheduler_deferred_transition_count), 0);
        write_volatile(addr_of_mut!(poole_scheduler_deferred_errors), 0);
        initialize_scheduler_stack(
            scheduler_deferred_stack_base(0),
            scheduler_deferred_stack_pointer(0),
            poole_scheduler_deferred_worker_a_entry,
            SCHEDULER_TASK_A_REGISTERS,
        );
        initialize_scheduler_stack(
            scheduler_deferred_stack_base(1),
            scheduler_deferred_stack_pointer(1),
            poole_scheduler_deferred_worker_b_entry,
            SCHEDULER_TASK_B_REGISTERS,
        );
    }
    if let Some(error) =
        scheduler_deferred_stack_error(0).or_else(|| scheduler_deferred_stack_error(1))
    {
        return Err(error);
    }
    // SAFETY: selector 17 executes at CPL0 and only observes current control state.
    let (cr3, bases) = unsafe {
        (
            read_cr3(),
            (
                read_msr(IA32_FS_BASE),
                read_msr(IA32_GS_BASE),
                read_msr(IA32_KERNEL_GS_BASE),
            ),
        )
    };
    Ok(SchedulerDeferredHardwareContext {
        cr3,
        bases,
        dispatches: 0,
    })
}

pub fn dispatch_scheduler_deferred_worker(
    context: &mut SchedulerDeferredHardwareContext,
    worker: u8,
) -> Result<(), SchedulerDeferredHardwareError> {
    if worker >= 2 {
        return Err(SchedulerDeferredHardwareError::Worker);
    }
    if read_rflags() & (1 << 9) != 0 {
        return Err(SchedulerDeferredHardwareError::InterruptState);
    }
    if let Some(error) = scheduler_deferred_stack_error(worker) {
        return Err(error);
    }
    let entries_before = unsafe {
        if worker == 0 {
            read_volatile(addr_of!(poole_scheduler_deferred_worker_a_entries))
        } else {
            read_volatile(addr_of!(poole_scheduler_deferred_worker_b_entries))
        }
    };
    let transitions_before =
        unsafe { read_volatile(addr_of!(poole_scheduler_deferred_transition_count)) };
    // SAFETY: the incoming RSP names a validated frame on the selected private stack.
    unsafe {
        write_volatile(
            addr_of_mut!(poole_scheduler_deferred_transition_count),
            transitions_before + 1,
        );
        poole_scheduler_context_switch(
            addr_of_mut!(poole_scheduler_deferred_kernel_rsp),
            scheduler_deferred_stack_pointer(worker),
        );
    }
    let (entries_after, transitions_after, errors) = unsafe {
        (
            if worker == 0 {
                read_volatile(addr_of!(poole_scheduler_deferred_worker_a_entries))
            } else {
                read_volatile(addr_of!(poole_scheduler_deferred_worker_b_entries))
            },
            read_volatile(addr_of!(poole_scheduler_deferred_transition_count)),
            read_volatile(addr_of!(poole_scheduler_deferred_errors)),
        )
    };
    if entries_after != entries_before + 1 || errors != 0 {
        return Err(SchedulerDeferredHardwareError::Step);
    }
    if transitions_after != transitions_before + 2 {
        return Err(SchedulerDeferredHardwareError::TransitionCount);
    }
    if let Some(error) = scheduler_deferred_stack_error(worker) {
        return Err(error);
    }
    context.dispatches = context
        .dispatches
        .checked_add(1)
        .ok_or(SchedulerDeferredHardwareError::TransitionCount)?;
    Ok(())
}

pub fn clear_scheduler_deferred_workers(
    context: SchedulerDeferredHardwareContext,
) -> Result<SchedulerDeferredHardwareProof, SchedulerDeferredHardwareError> {
    if read_rflags() & (1 << 9) != 0 {
        return Err(SchedulerDeferredHardwareError::InterruptState);
    }
    // SAFETY: all work is terminal and these are read-only CPL0 observations.
    let (cr3, bases) = unsafe {
        (
            read_cr3(),
            (
                read_msr(IA32_FS_BASE),
                read_msr(IA32_GS_BASE),
                read_msr(IA32_KERNEL_GS_BASE),
            ),
        )
    };
    if cr3 != context.cr3 || bases != context.bases {
        return Err(SchedulerDeferredHardwareError::ControlState);
    }
    let (entry_a, entry_b, transitions, errors) = unsafe {
        (
            read_volatile(addr_of!(poole_scheduler_deferred_worker_a_entries)),
            read_volatile(addr_of!(poole_scheduler_deferred_worker_b_entries)),
            read_volatile(addr_of!(poole_scheduler_deferred_transition_count)),
            read_volatile(addr_of!(poole_scheduler_deferred_errors)),
        )
    };
    if entry_a + entry_b != u64::from(context.dispatches)
        || transitions != u64::from(context.dispatches) * 2
        || errors != 0
    {
        return Err(SchedulerDeferredHardwareError::TransitionCount);
    }
    for worker in 0..2 {
        let base = scheduler_deferred_stack_base(worker);
        // SAFETY: no worker can resume after the controller reaches terminal state.
        unsafe { write_bytes(base, 0, SCHEDULER_STACK_BYTES) };
    }
    for worker in 0..2 {
        let base = scheduler_deferred_stack_base(worker);
        for offset in 0..SCHEDULER_STACK_BYTES {
            if unsafe { read_volatile(base.add(offset)) } != 0 {
                return Err(SchedulerDeferredHardwareError::Clear);
            }
        }
        // SAFETY: the cleared and retired worker context cannot be consumed again.
        unsafe { write_volatile(scheduler_deferred_stack_pointer(worker), 0) };
    }
    // SAFETY: all selector-17 context metadata is retired after proof capture.
    unsafe {
        write_volatile(addr_of_mut!(poole_scheduler_deferred_kernel_rsp), 0);
        write_volatile(addr_of_mut!(poole_scheduler_deferred_worker_a_entries), 0);
        write_volatile(addr_of_mut!(poole_scheduler_deferred_worker_b_entries), 0);
        write_volatile(addr_of_mut!(poole_scheduler_deferred_transition_count), 0);
        write_volatile(addr_of_mut!(poole_scheduler_deferred_errors), 0);
    }
    SCHEDULER_DEFERRED_STACK_BASE.store(0, Ordering::Release);
    Ok(SchedulerDeferredHardwareProof {
        worker_entry_count: [entry_a as u32, entry_b as u32],
        dispatch_count: context.dispatches,
        machine_transition_count: transitions as u32,
        stack_count: 2,
        stack_bytes_each: SCHEDULER_STACK_BYTES as u32,
        stack_alignment: SCHEDULER_STACK_ALIGNMENT as u8,
        stack_bytes_cleared: (2 * SCHEDULER_STACK_BYTES) as u32,
        same_cr3: true,
        fs_gs_unchanged: true,
        returned_with_interrupts_disabled: true,
        worker_error_count: errors as u32,
    })
}

fn scheduler_preemption_stack_base(task: usize) -> *mut u8 {
    let base = SCHEDULER_PREEMPT_STACK_BASE.load(Ordering::Acquire);
    (base as usize + task * SCHEDULER_PREEMPT_STACK_BYTES) as *mut u8
}

fn scheduler_preemption_saved_rsp(task: usize) -> *mut u64 {
    match task {
        0 => addr_of_mut!(poole_scheduler_preempt_task_a_rsp),
        1 => addr_of_mut!(poole_scheduler_preempt_task_b_rsp),
        2 => addr_of_mut!(poole_scheduler_preempt_task_c_rsp),
        _ => addr_of_mut!(poole_scheduler_preempt_task_d_rsp),
    }
}

fn scheduler_preemption_entry_counter(task: usize) -> *mut u64 {
    match task {
        0 => addr_of_mut!(poole_scheduler_preempt_task_a_entries),
        1 => addr_of_mut!(poole_scheduler_preempt_task_b_entries),
        2 => addr_of_mut!(poole_scheduler_preempt_task_c_entries),
        _ => addr_of_mut!(poole_scheduler_preempt_task_d_entries),
    }
}

fn scheduler_preemption_entry_bounds(task: usize) -> (u64, u64) {
    match task {
        0 => (
            poole_scheduler_preempt_task_a_entry as *const () as usize as u64,
            poole_scheduler_preempt_task_a_end as *const () as usize as u64,
        ),
        1 => (
            poole_scheduler_preempt_task_b_entry as *const () as usize as u64,
            poole_scheduler_preempt_task_b_end as *const () as usize as u64,
        ),
        2 => (
            poole_scheduler_preempt_task_c_entry as *const () as usize as u64,
            poole_scheduler_preempt_task_c_end as *const () as usize as u64,
        ),
        _ => (
            poole_scheduler_preempt_task_d_entry as *const () as usize as u64,
            poole_scheduler_preempt_task_d_end as *const () as usize as u64,
        ),
    }
}

pub fn scheduler_preemption_stack_bounds(task: usize) -> Option<(u64, u64)> {
    if task >= SCHEDULER_PREEMPT_TASK_COUNT {
        return None;
    }
    let bottom = scheduler_preemption_stack_base(task) as u64;
    if bottom == task as u64 * SCHEDULER_PREEMPT_STACK_BYTES as u64 {
        return None;
    }
    Some((bottom, bottom + SCHEDULER_PREEMPT_STACK_BYTES as u64))
}

fn scheduler_preemption_stack_valid(task: usize) -> bool {
    let Some((bottom, top)) = scheduler_preemption_stack_bounds(task) else {
        return false;
    };
    let base = bottom as usize as *const u8;
    let canaries = unsafe {
        read_volatile(base.cast::<u64>()) == SCHEDULER_STACK_CANARY
            && read_volatile(base.add(SCHEDULER_HIGH_CANARY_OFFSET).cast::<u64>())
                == SCHEDULER_STACK_CANARY
    };
    canaries
        && bottom.is_multiple_of(SCHEDULER_STACK_ALIGNMENT as u64)
        && top.is_multiple_of(SCHEDULER_STACK_ALIGNMENT as u64)
}

pub fn scheduler_preemption_context_valid(task: usize, frame: &TrapFrame) -> bool {
    let Some((bottom, top)) = scheduler_preemption_stack_bounds(task) else {
        return false;
    };
    let (entry, end) = scheduler_preemption_entry_bounds(task);
    scheduler_preemption_stack_valid(task)
        && frame.rip >= entry
        && frame.rip < end
        && frame.rsp >= bottom
        && frame.rsp <= top
        && frame.rsp.is_multiple_of(8)
        && frame.code_selector == u64::from(KERNEL_CODE_SELECTOR)
        && frame.data_selector == u64::from(KERNEL_DATA_SELECTOR)
        && frame.rflags & ((1 << 1) | (1 << 9)) == (1 << 1) | (1 << 9)
        && frame.rflags & ((1 << 14) | (1 << 17)) == 0
}

pub fn prepare_scheduler_preemption_contexts(
    kernel_stack_top: u64,
) -> Result<[TrapFrame; SCHEDULER_PREEMPT_TASK_COUNT], SchedulerPreemptionHardwareError> {
    if read_rflags() & (1 << 9) != 0 {
        return Err(SchedulerPreemptionHardwareError::InterruptState);
    }
    let kernel_stack_bottom = kernel_stack_top
        .checked_sub(RETAINED_KERNEL_STACK_BYTES as u64)
        .ok_or(SchedulerPreemptionHardwareError::StackGeometry)?;
    let task_region_top = kernel_stack_bottom
        .checked_add(SCHEDULER_PREEMPT_REGION_BYTES as u64)
        .ok_or(SchedulerPreemptionHardwareError::StackGeometry)?;
    let current_rsp: u64;
    // SAFETY: this is a read-only observation of the current kernel stack pointer.
    unsafe {
        core::arch::asm!(
            "mov {}, rsp",
            out(reg) current_rsp,
            options(nomem, nostack, preserves_flags)
        );
    }
    if kernel_stack_top == 0
        || !kernel_stack_top.is_multiple_of(poole_kmap::PAGE_SIZE)
        || !kernel_stack_bottom.is_multiple_of(poole_kmap::PAGE_SIZE)
        || task_region_top > kernel_stack_top
        || current_rsp < task_region_top
        || current_rsp >= kernel_stack_top
        || SCHEDULER_PREEMPT_STACK_BASE
            .compare_exchange(0, kernel_stack_bottom, Ordering::AcqRel, Ordering::Acquire)
            .is_err()
    {
        return Err(SchedulerPreemptionHardwareError::StackGeometry);
    }
    for task in 0..SCHEDULER_PREEMPT_TASK_COUNT {
        let base = scheduler_preemption_stack_base(task);
        // SAFETY: selector 16 exclusively owns each fixed stack before interrupt enablement.
        unsafe {
            write_bytes(base, SCHEDULER_STACK_FILL, SCHEDULER_PREEMPT_STACK_BYTES);
            write_volatile(base.cast::<u64>(), SCHEDULER_STACK_CANARY);
            write_volatile(
                base.add(SCHEDULER_HIGH_CANARY_OFFSET).cast::<u64>(),
                SCHEDULER_STACK_CANARY,
            );
            write_volatile(scheduler_preemption_saved_rsp(task), 0);
            write_volatile(scheduler_preemption_entry_counter(task), 0);
        }
    }
    // SAFETY: task A is the sole cooperative launch context and owns stack A.
    unsafe {
        initialize_scheduler_stack(
            scheduler_preemption_stack_base(0),
            scheduler_preemption_saved_rsp(0),
            poole_scheduler_preempt_task_a_entry,
            SCHEDULER_PREEMPT_TASK_REGISTERS[0],
        );
        let launch_frame = read_volatile(scheduler_preemption_saved_rsp(0));
        write_volatile(
            (launch_frame as usize as *mut u64).add(6),
            (1 << 1) | (1 << 9),
        );
        write_volatile(addr_of_mut!(poole_scheduler_preempt_kernel_rsp), 0);
        write_volatile(addr_of_mut!(poole_scheduler_transition_count), 0);
    }

    let mut contexts = [TrapFrame {
        r15: 0,
        r14: 0,
        r13: 0,
        r12: 0,
        r11: 0,
        r10: 0,
        r9: 0,
        r8: 0,
        rsi: 0,
        rdi: 0,
        rbp: 0,
        rdx: 0,
        rcx: 0,
        rbx: 0,
        rax: 0,
        vector: u64::from(TIMER_VECTOR),
        error_code: 0,
        rip: 0,
        code_selector: u64::from(KERNEL_CODE_SELECTOR),
        rflags: (1 << 1) | (1 << 9),
        rsp: 0,
        data_selector: u64::from(KERNEL_DATA_SELECTOR),
    }; SCHEDULER_PREEMPT_TASK_COUNT];
    for task in 0..SCHEDULER_PREEMPT_TASK_COUNT {
        let (entry, _) = scheduler_preemption_entry_bounds(task);
        let (_, top) = scheduler_preemption_stack_bounds(task)
            .ok_or(SchedulerPreemptionHardwareError::StackGeometry)?;
        let registers = SCHEDULER_PREEMPT_TASK_REGISTERS[task];
        contexts[task] = TrapFrame {
            r15: registers[5],
            r14: registers[4],
            r13: registers[3],
            r12: registers[2],
            r11: 0x1100_0000_0000_0000 | task as u64,
            r10: 0x1000_0000_0000_0000 | task as u64,
            r9: 0x0900_0000_0000_0000 | task as u64,
            r8: 0x0800_0000_0000_0000 | task as u64,
            rsi: 0x0600_0000_0000_0000 | task as u64,
            rdi: 0x0700_0000_0000_0000 | task as u64,
            rbp: registers[1],
            rdx: 0x0200_0000_0000_0000 | task as u64,
            rcx: 0x0100_0000_0000_0000 | task as u64,
            rbx: registers[0],
            rax: 0x0a00_0000_0000_0000 | task as u64,
            vector: u64::from(TIMER_VECTOR),
            error_code: 0,
            rip: entry,
            code_selector: u64::from(KERNEL_CODE_SELECTOR),
            rflags: (1 << 1) | (1 << 9),
            rsp: top - SCHEDULER_PREEMPT_INITIAL_RSP_RESERVE as u64,
            data_selector: u64::from(KERNEL_DATA_SELECTOR),
        };
        if !scheduler_preemption_context_valid(task, &contexts[task]) {
            return Err(SchedulerPreemptionHardwareError::ContextGeometry);
        }
    }
    Ok(contexts)
}

pub fn run_scheduler_preemption_launcher()
-> Result<SchedulerPreemptionHardwareProof, SchedulerPreemptionHardwareError> {
    if read_rflags() & (1 << 9) != 0 {
        return Err(SchedulerPreemptionHardwareError::InterruptState);
    }
    for task in 0..SCHEDULER_PREEMPT_TASK_COUNT {
        if !scheduler_preemption_stack_valid(task) {
            return Err(SchedulerPreemptionHardwareError::StackGeometry);
        }
    }
    // SAFETY: selector 16 executes at CPL0 and these are read-only control-state observations.
    let (cr3_before, bases_before) = unsafe {
        (
            read_cr3(),
            (
                read_msr(IA32_FS_BASE),
                read_msr(IA32_GS_BASE),
                read_msr(IA32_KERNEL_GS_BASE),
            ),
        )
    };
    unsafe {
        write_volatile(addr_of_mut!(poole_scheduler_preempt_flags_before), 0);
        write_volatile(addr_of_mut!(poole_scheduler_preempt_flags_after), 0);
    }
    // SAFETY: task A has a validated private launch frame and returns only after the terminal tick.
    unsafe {
        poole_scheduler_preempt_launch(
            addr_of_mut!(poole_scheduler_preempt_kernel_rsp),
            scheduler_preemption_saved_rsp(0),
        );
    }
    let current_rflags = read_rflags();
    // SAFETY: these repeat the same read-only CPL0 observations after bounded return.
    let (cr3_after, bases_after) = unsafe {
        (
            read_cr3(),
            (
                read_msr(IA32_FS_BASE),
                read_msr(IA32_GS_BASE),
                read_msr(IA32_KERNEL_GS_BASE),
            ),
        )
    };
    let mut entries = [0u32; SCHEDULER_PREEMPT_TASK_COUNT];
    for (task, entry) in entries.iter_mut().enumerate() {
        let observed = unsafe { read_volatile(scheduler_preemption_entry_counter(task)) };
        *entry = observed
            .try_into()
            .map_err(|_| SchedulerPreemptionHardwareError::EntryCount)?;
    }
    let transitions = unsafe { read_volatile(addr_of!(poole_scheduler_transition_count)) };
    let (switch_flags_before, switch_flags_after) = unsafe {
        (
            read_volatile(addr_of!(poole_scheduler_preempt_flags_before)),
            read_volatile(addr_of!(poole_scheduler_preempt_flags_after)),
        )
    };
    if entries != [1; SCHEDULER_PREEMPT_TASK_COUNT] {
        return Err(SchedulerPreemptionHardwareError::EntryCount);
    }
    if transitions != 2 {
        return Err(SchedulerPreemptionHardwareError::TransitionCount);
    }
    if switch_flags_before == 0
        || switch_flags_after != switch_flags_before
        || switch_flags_after & (1 << 9) != 0
        || current_rflags & (1 << 9) != 0
        || cr3_after != cr3_before
        || bases_after != bases_before
    {
        return Err(SchedulerPreemptionHardwareError::ControlState);
    }
    Ok(SchedulerPreemptionHardwareProof {
        task_entry_count: entries,
        launcher_transition_count: transitions as u32,
        stack_count: SCHEDULER_PREEMPT_TASK_COUNT as u8,
        stack_bytes_each: SCHEDULER_PREEMPT_STACK_BYTES as u32,
        stack_alignment: SCHEDULER_STACK_ALIGNMENT as u8,
        stack_bytes_cleared: 0,
        same_cr3: true,
        fs_gs_unchanged: true,
        returned_with_interrupts_disabled: true,
    })
}

pub fn clear_scheduler_preemption_stacks(
    mut proof: SchedulerPreemptionHardwareProof,
) -> Result<SchedulerPreemptionHardwareProof, SchedulerPreemptionHardwareError> {
    for task in 0..SCHEDULER_PREEMPT_TASK_COUNT {
        let base = scheduler_preemption_stack_base(task);
        // SAFETY: all four contexts are retired and timer delivery is masked with IF clear.
        unsafe { write_bytes(base, 0, SCHEDULER_PREEMPT_STACK_BYTES) };
    }
    for task in 0..SCHEDULER_PREEMPT_TASK_COUNT {
        let base = scheduler_preemption_stack_base(task);
        for offset in 0..SCHEDULER_PREEMPT_STACK_BYTES {
            if unsafe { read_volatile(base.add(offset)) } != 0 {
                return Err(SchedulerPreemptionHardwareError::Clear);
            }
        }
        unsafe {
            write_volatile(scheduler_preemption_saved_rsp(task), 0);
            write_volatile(scheduler_preemption_entry_counter(task), 0);
        }
    }
    unsafe {
        write_volatile(addr_of_mut!(poole_scheduler_preempt_kernel_rsp), 0);
        write_volatile(addr_of_mut!(poole_scheduler_transition_count), 0);
        write_volatile(addr_of_mut!(poole_scheduler_preempt_flags_before), 0);
        write_volatile(addr_of_mut!(poole_scheduler_preempt_flags_after), 0);
    }
    SCHEDULER_PREEMPT_STACK_BASE.store(0, Ordering::Release);
    proof.stack_bytes_cleared =
        (SCHEDULER_PREEMPT_TASK_COUNT * SCHEDULER_PREEMPT_STACK_BYTES) as u32;
    Ok(proof)
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
