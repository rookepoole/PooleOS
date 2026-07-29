//! Pure PKSMP2 per-CPU runtime geometry, state, and validation.

use core::mem::{offset_of, size_of};

use crate::{
    smp,
    xstate::{AREA_BYTES as XSTATE_AREA_BYTES, INITIAL_FCW, INITIAL_MXCSR, SELECTED_XCR0},
};

pub const CONTRACT_ID: &str = "PKSMP2";
pub const SELECTED_MOVE_ID: &str = "N8-SMP-PERCPU-RUNTIME-001";
pub const SELECTOR: u64 = 13;

pub const PAGE_BYTES: u64 = smp::PAGE_BYTES;
pub const LOW_BOOTSTRAP_LIMIT: u64 = smp::LOW_BOOTSTRAP_LIMIT;
pub const RESOURCE_PAGE_COUNT: u64 = 32;
pub const TRAMPOLINE_PAGE_OFFSET: u64 = 0;
pub const PML4_PAGE_OFFSET: u64 = 1;
pub const PDPT_PAGE_OFFSET: u64 = 2;
pub const PD_PAGE_OFFSET: u64 = 3;
pub const PT_PAGE_OFFSET: u64 = 4;
pub const RSP0_GUARD_LOW_OFFSET: u64 = 5;
pub const RSP0_FIRST_PAGE_OFFSET: u64 = 6;
pub const RSP0_PAGE_COUNT: u64 = 4;
pub const RSP0_GUARD_HIGH_OFFSET: u64 = 10;
pub const LOCAL_GUARD_LOW_OFFSET: u64 = 11;
pub const LOCAL_PAGE_OFFSET: u64 = 12;
pub const LOCAL_GUARD_HIGH_OFFSET: u64 = 13;
pub const DESCRIPTOR_GUARD_LOW_OFFSET: u64 = 14;
pub const DESCRIPTOR_PAGE_OFFSET: u64 = 15;
pub const DESCRIPTOR_GUARD_HIGH_OFFSET: u64 = 16;
pub const IDT_GUARD_LOW_OFFSET: u64 = 17;
pub const IDT_PAGE_OFFSET: u64 = 18;
pub const IDT_GUARD_HIGH_OFFSET: u64 = 19;
pub const IST1_GUARD_LOW_OFFSET: u64 = 20;
pub const IST1_FIRST_PAGE_OFFSET: u64 = 21;
pub const IST_PAGE_COUNT: u64 = 2;
pub const IST1_GUARD_HIGH_OFFSET: u64 = 23;
pub const IST2_GUARD_LOW_OFFSET: u64 = 24;
pub const IST2_FIRST_PAGE_OFFSET: u64 = 25;
pub const IST2_GUARD_HIGH_OFFSET: u64 = 27;
pub const XSTATE_GUARD_LOW_OFFSET: u64 = 28;
pub const XSTATE_PAGE_OFFSET: u64 = 29;
pub const XSTATE_GUARD_HIGH_OFFSET: u64 = 30;
pub const RESERVED_PAGE_OFFSET: u64 = 31;
pub const GUARD_PAGE_COUNT: u64 = 14;
pub const IDENTITY_MAPPED_PAGE_COUNT: u64 = 13;

pub const GDT_OFFSET: u64 = 0;
pub const GDT_ENTRY_COUNT: u32 = 5;
pub const GDT_LIMIT: u32 = 39;
pub const TSS_OFFSET: u64 = 64;
pub const TSS_BYTES: u32 = 104;
pub const IDT_ENTRY_COUNT: u32 = 256;
pub const IDT_BYTES: u32 = 4096;
pub const IDT_LIMIT: u32 = IDT_BYTES - 1;
pub const KERNEL_CODE_SELECTOR: u32 = 0x08;
pub const KERNEL_DATA_SELECTOR: u32 = 0x10;
pub const KERNEL_TSS_SELECTOR: u32 = 0x18;
pub const EXCEPTION_GATE_COUNT: u32 = 8;
pub const OWNED_INTERRUPT_VECTOR_COUNT: u32 = 19;
pub const INSTALLED_GATE_COUNT: u32 = EXCEPTION_GATE_COUNT + OWNED_INTERRUPT_VECTOR_COUNT;
pub const XSTATE_OWNER_TOKEN_BASE: u32 = 0x5058_0000;

pub const MAILBOX_MAGIC: u64 = 0x504b_534d_5032_4d42;
pub const MAILBOX_VERSION: u32 = 2;
pub const MAILBOX_STATE_PREPARED: u32 = 1;
pub const MAILBOX_STATE_ONLINE: u32 = 2;
pub const MAILBOX_STATE_QUIESCED: u32 = 3;
pub const MAILBOX_STATE_FAULTED: u32 = u32::MAX;
pub const MAILBOX_COMMAND_NONE: u32 = 0;
pub const MAILBOX_COMMAND_STOP: u32 = 1;
pub const RUNTIME_MAGIC: u64 = 0x504b_5254_5032_4355;
pub const RUNTIME_VERSION: u32 = 1;
pub const RUNTIME_STATE_PREPARED: u32 = 1;
pub const RUNTIME_STATE_DESCRIPTORS: u32 = 2;
pub const RUNTIME_STATE_XSTATE: u32 = 3;
pub const RUNTIME_STATE_ONLINE: u32 = 4;
pub const RUNTIME_STATE_QUIESCED: u32 = 5;

pub const CR0_MP: u64 = 1 << 1;
pub const CR0_EM: u64 = 1 << 2;
pub const CR0_TS: u64 = 1 << 3;
pub const CR0_NE: u64 = 1 << 5;
pub const CR4_OSFXSR: u64 = 1 << 9;
pub const CR4_OSXMMEXCPT: u64 = 1 << 10;
pub const CR4_OSXSAVE: u64 = 1 << 18;
pub const LEAF1_ECX_XSAVE: u32 = 1 << 26;
pub const LEAF1_ECX_OSXSAVE: u32 = 1 << 27;
pub const REQUIRED_HARDWARE_LEAF1_ECX: u32 = LEAF1_ECX_XSAVE;
pub const REQUIRED_LEAF1_ECX: u32 = LEAF1_ECX_XSAVE | LEAF1_ECX_OSXSAVE;
pub const RFLAGS_INTERRUPT_ENABLE: u64 = 1 << 9;
pub const GDT_CODE_DESCRIPTOR: u64 = 0x00af_9b00_0000_ffff;
pub const GDT_DATA_DESCRIPTOR: u64 = 0x00cf_9300_0000_ffff;
const TSS_AVAILABLE_PRESENT_RING0: u64 = 0x89;
const TSS_BUSY_PRESENT_RING0: u64 = 0x8b;
const INTERRUPT_GATE_PRESENT_RING0: u8 = 0x8e;
const FNV_OFFSET: u64 = 0xcbf2_9ce4_8422_2325;
const FNV_PRIME: u64 = 0x0000_0100_0000_01b3;

pub const GUARD_OFFSETS: [u64; GUARD_PAGE_COUNT as usize] = [
    RSP0_GUARD_LOW_OFFSET,
    RSP0_GUARD_HIGH_OFFSET,
    LOCAL_GUARD_LOW_OFFSET,
    LOCAL_GUARD_HIGH_OFFSET,
    DESCRIPTOR_GUARD_LOW_OFFSET,
    DESCRIPTOR_GUARD_HIGH_OFFSET,
    IDT_GUARD_LOW_OFFSET,
    IDT_GUARD_HIGH_OFFSET,
    IST1_GUARD_LOW_OFFSET,
    IST1_GUARD_HIGH_OFFSET,
    IST2_GUARD_LOW_OFFSET,
    IST2_GUARD_HIGH_OFFSET,
    XSTATE_GUARD_LOW_OFFSET,
    XSTATE_GUARD_HIGH_OFFSET,
];

pub const EXCEPTION_VECTORS: [u8; EXCEPTION_GATE_COUNT as usize] = [3, 6, 7, 8, 13, 14, 16, 19];
pub const INTERRUPT_VECTORS: [u8; OWNED_INTERRUPT_VECTOR_COUNT as usize] = [
    64, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 255,
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    ResourceAddress,
    ResourceCount,
    PageRole,
    MailboxShape,
    MailboxState,
    MailboxIdentity,
    FeatureMismatch,
    ControlState,
    DescriptorState,
    StackState,
    XstateState,
    InterruptState,
    TimeOrder,
    Checksum,
    ResourceImage,
    Transition,
    Rollback,
}

impl Error {
    pub const fn label(self) -> &'static str {
        match self {
            Self::ResourceAddress => "runtime_resource_address",
            Self::ResourceCount => "runtime_resource_count",
            Self::PageRole => "runtime_page_role",
            Self::MailboxShape => "runtime_mailbox_shape",
            Self::MailboxState => "runtime_mailbox_state",
            Self::MailboxIdentity => "runtime_mailbox_identity",
            Self::FeatureMismatch => "runtime_feature_mismatch",
            Self::ControlState => "runtime_control_state",
            Self::DescriptorState => "runtime_descriptor_state",
            Self::StackState => "runtime_stack_state",
            Self::XstateState => "runtime_xstate_state",
            Self::InterruptState => "runtime_interrupt_state",
            Self::TimeOrder => "runtime_time_order",
            Self::Checksum => "runtime_checksum",
            Self::ResourceImage => "runtime_resource_image",
            Self::Transition => "runtime_transition",
            Self::Rollback => "runtime_rollback",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ResourceLayout {
    pub start_page: u64,
    pub page_count: u64,
}

impl ResourceLayout {
    pub fn new(start_page: u64, page_count: u64) -> Result<Self, Error> {
        if page_count != RESOURCE_PAGE_COUNT {
            return Err(Error::ResourceCount);
        }
        let start = start_page
            .checked_mul(PAGE_BYTES)
            .ok_or(Error::ResourceAddress)?;
        let end = start
            .checked_add(
                page_count
                    .checked_mul(PAGE_BYTES)
                    .ok_or(Error::ResourceAddress)?,
            )
            .ok_or(Error::ResourceAddress)?;
        if start == 0 || end > LOW_BOOTSTRAP_LIMIT || start / PAGE_BYTES > u64::from(u8::MAX) {
            return Err(Error::ResourceAddress);
        }
        Ok(Self {
            start_page,
            page_count,
        })
    }

    pub const fn page_address(self, offset: u64) -> u64 {
        (self.start_page + offset) * PAGE_BYTES
    }

    pub const fn trampoline(self) -> u64 {
        self.page_address(TRAMPOLINE_PAGE_OFFSET)
    }

    pub const fn pml4(self) -> u64 {
        self.page_address(PML4_PAGE_OFFSET)
    }

    pub const fn pdpt(self) -> u64 {
        self.page_address(PDPT_PAGE_OFFSET)
    }

    pub const fn page_directory(self) -> u64 {
        self.page_address(PD_PAGE_OFFSET)
    }

    pub const fn page_table(self) -> u64 {
        self.page_address(PT_PAGE_OFFSET)
    }

    pub const fn rsp0_bottom(self) -> u64 {
        self.page_address(RSP0_FIRST_PAGE_OFFSET)
    }

    pub const fn rsp0_top(self) -> u64 {
        self.page_address(RSP0_FIRST_PAGE_OFFSET + RSP0_PAGE_COUNT)
    }

    pub const fn local(self) -> u64 {
        self.page_address(LOCAL_PAGE_OFFSET)
    }

    pub const fn gdt(self) -> u64 {
        self.page_address(DESCRIPTOR_PAGE_OFFSET) + GDT_OFFSET
    }

    pub const fn tss(self) -> u64 {
        self.page_address(DESCRIPTOR_PAGE_OFFSET) + TSS_OFFSET
    }

    pub const fn idt(self) -> u64 {
        self.page_address(IDT_PAGE_OFFSET)
    }

    pub const fn ist1_bottom(self) -> u64 {
        self.page_address(IST1_FIRST_PAGE_OFFSET)
    }

    pub const fn ist1_top(self) -> u64 {
        self.page_address(IST1_FIRST_PAGE_OFFSET + IST_PAGE_COUNT)
    }

    pub const fn ist2_bottom(self) -> u64 {
        self.page_address(IST2_FIRST_PAGE_OFFSET)
    }

    pub const fn ist2_top(self) -> u64 {
        self.page_address(IST2_FIRST_PAGE_OFFSET + IST_PAGE_COUNT)
    }

    pub const fn xstate(self) -> u64 {
        self.page_address(XSTATE_PAGE_OFFSET)
    }

    pub const fn sipi_vector(self) -> u8 {
        (self.trampoline() / PAGE_BYTES) as u8
    }

    pub const fn is_guard_offset(offset: u64) -> bool {
        matches!(
            offset,
            RSP0_GUARD_LOW_OFFSET
                | RSP0_GUARD_HIGH_OFFSET
                | LOCAL_GUARD_LOW_OFFSET
                | LOCAL_GUARD_HIGH_OFFSET
                | DESCRIPTOR_GUARD_LOW_OFFSET
                | DESCRIPTOR_GUARD_HIGH_OFFSET
                | IDT_GUARD_LOW_OFFSET
                | IDT_GUARD_HIGH_OFFSET
                | IST1_GUARD_LOW_OFFSET
                | IST1_GUARD_HIGH_OFFSET
                | IST2_GUARD_LOW_OFFSET
                | IST2_GUARD_HIGH_OFFSET
                | XSTATE_GUARD_LOW_OFFSET
                | XSTATE_GUARD_HIGH_OFFSET
        )
    }

    pub const fn is_mapped_offset(offset: u64) -> bool {
        offset == TRAMPOLINE_PAGE_OFFSET
            || (offset >= RSP0_FIRST_PAGE_OFFSET
                && offset < RSP0_FIRST_PAGE_OFFSET + RSP0_PAGE_COUNT)
            || offset == LOCAL_PAGE_OFFSET
            || offset == DESCRIPTOR_PAGE_OFFSET
            || offset == IDT_PAGE_OFFSET
            || (offset >= IST1_FIRST_PAGE_OFFSET
                && offset < IST1_FIRST_PAGE_OFFSET + IST_PAGE_COUNT)
            || (offset >= IST2_FIRST_PAGE_OFFSET
                && offset < IST2_FIRST_PAGE_OFFSET + IST_PAGE_COUNT)
            || offset == XSTATE_PAGE_OFFSET
    }

    pub fn leaf_entry(self, offset: u64) -> Result<u64, Error> {
        if offset >= self.page_count || !Self::is_mapped_offset(offset) {
            return Err(Error::PageRole);
        }
        let mut flags = smp::ENTRY_PRESENT | smp::ENTRY_NO_EXECUTE;
        if offset == TRAMPOLINE_PAGE_OFFSET {
            flags = smp::ENTRY_PRESENT;
        } else if offset != IDT_PAGE_OFFSET {
            flags |= smp::ENTRY_WRITABLE;
        }
        Ok(self.page_address(offset) | flags)
    }
}

#[derive(Clone, Copy)]
#[repr(C)]
pub struct RuntimeMailbox {
    pub magic: u64,
    pub version: u32,
    pub state: u32,
    pub command: u32,
    pub target_apic_id: u32,
    pub bsp_apic_id: u32,
    pub observed_apic_id: u32,
    pub leaf1_ecx: u32,
    pub leaf1_edx: u32,
    pub cr0: u64,
    pub cr3: u64,
    pub cr4: u64,
    pub efer: u64,
    pub tsc_online: u64,
    pub tsc_stop: u64,
    pub baseline_checksum: u64,
    pub runtime_magic: u64,
    pub runtime_version: u32,
    pub runtime_state: u32,
    pub expected_gdt_base: u64,
    pub expected_idt_base: u64,
    pub expected_tss_base: u64,
    pub rsp0: u64,
    pub ist1_bottom: u64,
    pub ist1_top: u64,
    pub ist2_bottom: u64,
    pub ist2_top: u64,
    pub xstate_base: u64,
    pub xstate_bytes: u32,
    pub xstate_owner_initial: u32,
    pub observed_gdt_base: u64,
    pub observed_idt_base: u64,
    pub observed_rsp: u64,
    pub xcr0: u64,
    pub xstate_bv: u64,
    pub rflags: u64,
    pub observed_gdt_limit: u32,
    pub observed_idt_limit: u32,
    pub task_selector: u32,
    pub code_selector: u32,
    pub data_selector: u32,
    pub installed_gate_count: u32,
    pub owned_interrupt_vector_count: u32,
    pub interrupts_enabled: u32,
    pub initial_fcw: u32,
    pub initial_mxcsr: u32,
    pub xstate_owner_final: u32,
    pub xstate_save_count: u32,
    pub xstate_restore_count: u32,
    pub fault_code: u32,
    pub supported_xcr0: u64,
    pub enabled_area_bytes: u32,
    pub maximum_area_bytes: u32,
    pub runtime_checksum: u64,
    pub scratch_gdtr: [u8; 16],
    pub scratch_idtr: [u8; 16],
}

pub const MAILBOX_BYTES: usize = size_of::<RuntimeMailbox>();
pub const MAILBOX_MAGIC_OFFSET: usize = offset_of!(RuntimeMailbox, magic);
pub const MAILBOX_VERSION_OFFSET: usize = offset_of!(RuntimeMailbox, version);
pub const MAILBOX_STATE_OFFSET: usize = offset_of!(RuntimeMailbox, state);
pub const MAILBOX_COMMAND_OFFSET: usize = offset_of!(RuntimeMailbox, command);
pub const MAILBOX_TARGET_APIC_ID_OFFSET: usize = offset_of!(RuntimeMailbox, target_apic_id);
pub const MAILBOX_BSP_APIC_ID_OFFSET: usize = offset_of!(RuntimeMailbox, bsp_apic_id);
pub const MAILBOX_OBSERVED_APIC_ID_OFFSET: usize = offset_of!(RuntimeMailbox, observed_apic_id);
pub const MAILBOX_LEAF1_ECX_OFFSET: usize = offset_of!(RuntimeMailbox, leaf1_ecx);
pub const MAILBOX_LEAF1_EDX_OFFSET: usize = offset_of!(RuntimeMailbox, leaf1_edx);
pub const MAILBOX_CR0_OFFSET: usize = offset_of!(RuntimeMailbox, cr0);
pub const MAILBOX_CR3_OFFSET: usize = offset_of!(RuntimeMailbox, cr3);
pub const MAILBOX_CR4_OFFSET: usize = offset_of!(RuntimeMailbox, cr4);
pub const MAILBOX_EFER_OFFSET: usize = offset_of!(RuntimeMailbox, efer);
pub const MAILBOX_TSC_ONLINE_OFFSET: usize = offset_of!(RuntimeMailbox, tsc_online);
pub const MAILBOX_TSC_STOP_OFFSET: usize = offset_of!(RuntimeMailbox, tsc_stop);
pub const MAILBOX_BASELINE_CHECKSUM_OFFSET: usize = offset_of!(RuntimeMailbox, baseline_checksum);
pub const MAILBOX_RUNTIME_MAGIC_OFFSET: usize = offset_of!(RuntimeMailbox, runtime_magic);
pub const MAILBOX_RUNTIME_VERSION_OFFSET: usize = offset_of!(RuntimeMailbox, runtime_version);
pub const MAILBOX_RUNTIME_STATE_OFFSET: usize = offset_of!(RuntimeMailbox, runtime_state);
pub const MAILBOX_EXPECTED_GDT_BASE_OFFSET: usize = offset_of!(RuntimeMailbox, expected_gdt_base);
pub const MAILBOX_EXPECTED_IDT_BASE_OFFSET: usize = offset_of!(RuntimeMailbox, expected_idt_base);
pub const MAILBOX_EXPECTED_TSS_BASE_OFFSET: usize = offset_of!(RuntimeMailbox, expected_tss_base);
pub const MAILBOX_RSP0_OFFSET: usize = offset_of!(RuntimeMailbox, rsp0);
pub const MAILBOX_IST1_BOTTOM_OFFSET: usize = offset_of!(RuntimeMailbox, ist1_bottom);
pub const MAILBOX_IST1_TOP_OFFSET: usize = offset_of!(RuntimeMailbox, ist1_top);
pub const MAILBOX_IST2_BOTTOM_OFFSET: usize = offset_of!(RuntimeMailbox, ist2_bottom);
pub const MAILBOX_IST2_TOP_OFFSET: usize = offset_of!(RuntimeMailbox, ist2_top);
pub const MAILBOX_XSTATE_BASE_OFFSET: usize = offset_of!(RuntimeMailbox, xstate_base);
pub const MAILBOX_XSTATE_BYTES_OFFSET: usize = offset_of!(RuntimeMailbox, xstate_bytes);
pub const MAILBOX_XSTATE_OWNER_INITIAL_OFFSET: usize =
    offset_of!(RuntimeMailbox, xstate_owner_initial);
pub const MAILBOX_OBSERVED_GDT_BASE_OFFSET: usize = offset_of!(RuntimeMailbox, observed_gdt_base);
pub const MAILBOX_OBSERVED_IDT_BASE_OFFSET: usize = offset_of!(RuntimeMailbox, observed_idt_base);
pub const MAILBOX_OBSERVED_RSP_OFFSET: usize = offset_of!(RuntimeMailbox, observed_rsp);
pub const MAILBOX_XCR0_OFFSET: usize = offset_of!(RuntimeMailbox, xcr0);
pub const MAILBOX_XSTATE_BV_OFFSET: usize = offset_of!(RuntimeMailbox, xstate_bv);
pub const MAILBOX_RFLAGS_OFFSET: usize = offset_of!(RuntimeMailbox, rflags);
pub const MAILBOX_OBSERVED_GDT_LIMIT_OFFSET: usize = offset_of!(RuntimeMailbox, observed_gdt_limit);
pub const MAILBOX_OBSERVED_IDT_LIMIT_OFFSET: usize = offset_of!(RuntimeMailbox, observed_idt_limit);
pub const MAILBOX_TASK_SELECTOR_OFFSET: usize = offset_of!(RuntimeMailbox, task_selector);
pub const MAILBOX_CODE_SELECTOR_OFFSET: usize = offset_of!(RuntimeMailbox, code_selector);
pub const MAILBOX_DATA_SELECTOR_OFFSET: usize = offset_of!(RuntimeMailbox, data_selector);
pub const MAILBOX_INSTALLED_GATE_COUNT_OFFSET: usize =
    offset_of!(RuntimeMailbox, installed_gate_count);
pub const MAILBOX_OWNED_INTERRUPT_VECTOR_COUNT_OFFSET: usize =
    offset_of!(RuntimeMailbox, owned_interrupt_vector_count);
pub const MAILBOX_INTERRUPTS_ENABLED_OFFSET: usize = offset_of!(RuntimeMailbox, interrupts_enabled);
pub const MAILBOX_INITIAL_FCW_OFFSET: usize = offset_of!(RuntimeMailbox, initial_fcw);
pub const MAILBOX_INITIAL_MXCSR_OFFSET: usize = offset_of!(RuntimeMailbox, initial_mxcsr);
pub const MAILBOX_XSTATE_OWNER_FINAL_OFFSET: usize = offset_of!(RuntimeMailbox, xstate_owner_final);
pub const MAILBOX_XSTATE_SAVE_COUNT_OFFSET: usize = offset_of!(RuntimeMailbox, xstate_save_count);
pub const MAILBOX_XSTATE_RESTORE_COUNT_OFFSET: usize =
    offset_of!(RuntimeMailbox, xstate_restore_count);
pub const MAILBOX_FAULT_CODE_OFFSET: usize = offset_of!(RuntimeMailbox, fault_code);
pub const MAILBOX_SUPPORTED_XCR0_OFFSET: usize = offset_of!(RuntimeMailbox, supported_xcr0);
pub const MAILBOX_ENABLED_AREA_BYTES_OFFSET: usize = offset_of!(RuntimeMailbox, enabled_area_bytes);
pub const MAILBOX_MAXIMUM_AREA_BYTES_OFFSET: usize = offset_of!(RuntimeMailbox, maximum_area_bytes);
pub const MAILBOX_RUNTIME_CHECKSUM_OFFSET: usize = offset_of!(RuntimeMailbox, runtime_checksum);
pub const MAILBOX_SCRATCH_GDTR_OFFSET: usize = offset_of!(RuntimeMailbox, scratch_gdtr);
pub const MAILBOX_SCRATCH_IDTR_OFFSET: usize = offset_of!(RuntimeMailbox, scratch_idtr);

const _: () = assert!(MAILBOX_BYTES == 352);
const _: () = assert!(MAILBOX_MAGIC_OFFSET == 0);
const _: () = assert!(MAILBOX_RUNTIME_MAGIC_OFFSET == 96);
const _: () = assert!(MAILBOX_OBSERVED_GDT_BASE_OFFSET == 192);
const _: () = assert!(MAILBOX_RUNTIME_CHECKSUM_OFFSET == 312);
const _: () = assert!(MAILBOX_SCRATCH_GDTR_OFFSET == 320);
const _: () = assert!(MAILBOX_SCRATCH_IDTR_OFFSET == 336);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MailboxSnapshot {
    pub magic: u64,
    pub version: u32,
    pub state: u32,
    pub command: u32,
    pub target_apic_id: u32,
    pub bsp_apic_id: u32,
    pub observed_apic_id: u32,
    pub leaf1_ecx: u32,
    pub leaf1_edx: u32,
    pub cr0: u64,
    pub cr3: u64,
    pub cr4: u64,
    pub efer: u64,
    pub tsc_online: u64,
    pub tsc_stop: u64,
    pub baseline_checksum: u64,
    pub runtime_magic: u64,
    pub runtime_version: u32,
    pub runtime_state: u32,
    pub expected_gdt_base: u64,
    pub expected_idt_base: u64,
    pub expected_tss_base: u64,
    pub rsp0: u64,
    pub ist1_bottom: u64,
    pub ist1_top: u64,
    pub ist2_bottom: u64,
    pub ist2_top: u64,
    pub xstate_base: u64,
    pub xstate_bytes: u32,
    pub xstate_owner_initial: u32,
    pub observed_gdt_base: u64,
    pub observed_idt_base: u64,
    pub observed_rsp: u64,
    pub xcr0: u64,
    pub xstate_bv: u64,
    pub rflags: u64,
    pub observed_gdt_limit: u32,
    pub observed_idt_limit: u32,
    pub task_selector: u32,
    pub code_selector: u32,
    pub data_selector: u32,
    pub installed_gate_count: u32,
    pub owned_interrupt_vector_count: u32,
    pub interrupts_enabled: u32,
    pub initial_fcw: u32,
    pub initial_mxcsr: u32,
    pub xstate_owner_final: u32,
    pub xstate_save_count: u32,
    pub xstate_restore_count: u32,
    pub fault_code: u32,
    pub supported_xcr0: u64,
    pub enabled_area_bytes: u32,
    pub maximum_area_bytes: u32,
    pub runtime_checksum: u64,
}

fn fnv_u64(mut state: u64, value: u64) -> u64 {
    for byte in value.to_le_bytes() {
        state ^= u64::from(byte);
        state = state.wrapping_mul(FNV_PRIME);
    }
    state
}

pub fn baseline_checksum(mailbox: &MailboxSnapshot) -> u64 {
    [
        mailbox.magic,
        u64::from(mailbox.version),
        u64::from(mailbox.state),
        u64::from(mailbox.command),
        u64::from(mailbox.target_apic_id),
        u64::from(mailbox.bsp_apic_id),
        u64::from(mailbox.observed_apic_id),
        u64::from(mailbox.leaf1_ecx),
        u64::from(mailbox.leaf1_edx),
        mailbox.cr0,
        mailbox.cr3,
        mailbox.cr4,
        mailbox.efer,
        mailbox.tsc_online,
        mailbox.tsc_stop,
    ]
    .into_iter()
    .fold(FNV_OFFSET, fnv_u64)
}

pub fn runtime_checksum(mailbox: &MailboxSnapshot) -> u64 {
    [
        mailbox.baseline_checksum,
        mailbox.runtime_magic,
        u64::from(mailbox.runtime_version),
        u64::from(mailbox.runtime_state),
        mailbox.expected_gdt_base,
        mailbox.expected_idt_base,
        mailbox.expected_tss_base,
        mailbox.rsp0,
        mailbox.ist1_bottom,
        mailbox.ist1_top,
        mailbox.ist2_bottom,
        mailbox.ist2_top,
        mailbox.xstate_base,
        u64::from(mailbox.xstate_bytes),
        u64::from(mailbox.xstate_owner_initial),
        mailbox.observed_gdt_base,
        mailbox.observed_idt_base,
        mailbox.observed_rsp,
        mailbox.xcr0,
        mailbox.xstate_bv,
        mailbox.rflags,
        u64::from(mailbox.observed_gdt_limit),
        u64::from(mailbox.observed_idt_limit),
        u64::from(mailbox.task_selector),
        u64::from(mailbox.code_selector),
        u64::from(mailbox.data_selector),
        u64::from(mailbox.installed_gate_count),
        u64::from(mailbox.owned_interrupt_vector_count),
        u64::from(mailbox.interrupts_enabled),
        u64::from(mailbox.initial_fcw),
        u64::from(mailbox.initial_mxcsr),
        u64::from(mailbox.xstate_owner_final),
        u64::from(mailbox.xstate_save_count),
        u64::from(mailbox.xstate_restore_count),
        u64::from(mailbox.fault_code),
        mailbox.supported_xcr0,
        u64::from(mailbox.enabled_area_bytes),
        u64::from(mailbox.maximum_area_bytes),
    ]
    .into_iter()
    .fold(FNV_OFFSET, fnv_u64)
}

pub const fn owner_token(apic_id: u32) -> u32 {
    XSTATE_OWNER_TOKEN_BASE | apic_id
}

pub fn validate_mailbox(
    mailbox: &MailboxSnapshot,
    layout: ResourceLayout,
    bsp_leaf1_ecx: u32,
    bsp_leaf1_edx: u32,
    bsp_tsc_before: u64,
    bsp_tsc_after: u64,
) -> Result<(), Error> {
    if mailbox.magic != MAILBOX_MAGIC
        || mailbox.version != MAILBOX_VERSION
        || mailbox.runtime_magic != RUNTIME_MAGIC
        || mailbox.runtime_version != RUNTIME_VERSION
    {
        return Err(Error::MailboxShape);
    }
    if mailbox.state != MAILBOX_STATE_QUIESCED
        || mailbox.command != MAILBOX_COMMAND_STOP
        || mailbox.runtime_state != RUNTIME_STATE_QUIESCED
        || mailbox.fault_code != 0
    {
        return Err(Error::MailboxState);
    }
    if mailbox.target_apic_id == mailbox.bsp_apic_id
        || mailbox.observed_apic_id != mailbox.target_apic_id
    {
        return Err(Error::MailboxIdentity);
    }
    if mailbox.leaf1_ecx & !LEAF1_ECX_OSXSAVE != bsp_leaf1_ecx & !LEAF1_ECX_OSXSAVE
        || mailbox.leaf1_edx != bsp_leaf1_edx
        || bsp_leaf1_ecx & REQUIRED_HARDWARE_LEAF1_ECX != REQUIRED_HARDWARE_LEAF1_ECX
        || mailbox.leaf1_ecx & REQUIRED_LEAF1_ECX != REQUIRED_LEAF1_ECX
        || mailbox.leaf1_edx & smp::REQUIRED_LEAF1_EDX != smp::REQUIRED_LEAF1_EDX
        || mailbox.supported_xcr0 & SELECTED_XCR0 != SELECTED_XCR0
        || mailbox.enabled_area_bytes < 576
        || mailbox.enabled_area_bytes > XSTATE_AREA_BYTES
        || mailbox.maximum_area_bytes < mailbox.enabled_area_bytes
        || mailbox.maximum_area_bytes > XSTATE_AREA_BYTES
    {
        return Err(Error::FeatureMismatch);
    }
    if mailbox.cr0 & (smp::CR0_PE | smp::CR0_PG | smp::CR0_WP | CR0_MP | CR0_NE)
        != smp::CR0_PE | smp::CR0_PG | smp::CR0_WP | CR0_MP | CR0_NE
        || mailbox.cr0 & (CR0_EM | CR0_TS) != 0
        || mailbox.cr3 != layout.pml4()
        || mailbox.cr4 & (smp::CR4_PAE | CR4_OSFXSR | CR4_OSXMMEXCPT | CR4_OSXSAVE)
            != smp::CR4_PAE | CR4_OSFXSR | CR4_OSXMMEXCPT | CR4_OSXSAVE
        || mailbox.efer & (smp::EFER_LME | smp::EFER_LMA | smp::EFER_NXE)
            != smp::EFER_LME | smp::EFER_LMA | smp::EFER_NXE
    {
        return Err(Error::ControlState);
    }
    if mailbox.expected_gdt_base != layout.gdt()
        || mailbox.expected_idt_base != layout.idt()
        || mailbox.expected_tss_base != layout.tss()
        || mailbox.observed_gdt_base != layout.gdt()
        || mailbox.observed_idt_base != layout.idt()
        || mailbox.observed_gdt_limit != GDT_LIMIT
        || mailbox.observed_idt_limit != IDT_LIMIT
        || mailbox.task_selector != KERNEL_TSS_SELECTOR
        || mailbox.code_selector != KERNEL_CODE_SELECTOR
        || mailbox.data_selector != KERNEL_DATA_SELECTOR
    {
        return Err(Error::DescriptorState);
    }
    if mailbox.rsp0 != layout.rsp0_top()
        || mailbox.observed_rsp != layout.rsp0_top()
        || mailbox.ist1_bottom != layout.ist1_bottom()
        || mailbox.ist1_top != layout.ist1_top()
        || mailbox.ist2_bottom != layout.ist2_bottom()
        || mailbox.ist2_top != layout.ist2_top()
        || !mailbox.rsp0.is_multiple_of(16)
    {
        return Err(Error::StackState);
    }
    if mailbox.xstate_base != layout.xstate()
        || mailbox.xstate_bytes != XSTATE_AREA_BYTES
        || mailbox.xstate_owner_initial != owner_token(mailbox.target_apic_id)
        || mailbox.xstate_owner_final != 0
        || mailbox.xstate_save_count != 1
        || mailbox.xstate_restore_count != 1
        || mailbox.xcr0 != SELECTED_XCR0
        || mailbox.xstate_bv & !SELECTED_XCR0 != 0
        || mailbox.initial_fcw != u32::from(INITIAL_FCW)
        || mailbox.initial_mxcsr != INITIAL_MXCSR
    {
        return Err(Error::XstateState);
    }
    if mailbox.installed_gate_count != INSTALLED_GATE_COUNT
        || mailbox.owned_interrupt_vector_count != OWNED_INTERRUPT_VECTOR_COUNT
        || mailbox.interrupts_enabled != 0
        || mailbox.rflags & RFLAGS_INTERRUPT_ENABLE != 0
    {
        return Err(Error::InterruptState);
    }
    if bsp_tsc_before == 0
        || mailbox.tsc_online < bsp_tsc_before
        || mailbox.tsc_online > bsp_tsc_after
        || mailbox.tsc_stop < mailbox.tsc_online
    {
        return Err(Error::TimeOrder);
    }
    if mailbox.baseline_checksum != baseline_checksum(mailbox)
        || mailbox.runtime_checksum != runtime_checksum(mailbox)
    {
        return Err(Error::Checksum);
    }
    Ok(())
}

fn put_u16(page: &mut [u8; PAGE_BYTES as usize], offset: usize, value: u16) {
    page[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
}

fn put_u32(page: &mut [u8; PAGE_BYTES as usize], offset: usize, value: u32) {
    page[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
}

fn put_u64(page: &mut [u8; PAGE_BYTES as usize], offset: usize, value: u64) {
    page[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
}

fn get_u16(page: &[u8; PAGE_BYTES as usize], offset: usize) -> u16 {
    u16::from_le_bytes(page[offset..offset + 2].try_into().expect("bounded u16"))
}

fn get_u32(page: &[u8; PAGE_BYTES as usize], offset: usize) -> u32 {
    u32::from_le_bytes(page[offset..offset + 4].try_into().expect("bounded u32"))
}

fn get_u64(page: &[u8; PAGE_BYTES as usize], offset: usize) -> u64 {
    u64::from_le_bytes(page[offset..offset + 8].try_into().expect("bounded u64"))
}

fn tss_descriptor(base: u64, kind: u64) -> (u64, u64) {
    let limit = u64::from(TSS_BYTES - 1);
    let low = (limit & 0xffff)
        | ((base & 0x00ff_ffff) << 16)
        | (kind << 40)
        | (((limit >> 16) & 0x0f) << 48)
        | (((base >> 24) & 0xff) << 56);
    (low, base >> 32)
}

pub fn build_descriptor_page(layout: ResourceLayout) -> [u8; PAGE_BYTES as usize] {
    let mut page = [0u8; PAGE_BYTES as usize];
    put_u64(&mut page, 8, GDT_CODE_DESCRIPTOR);
    put_u64(&mut page, 16, GDT_DATA_DESCRIPTOR);
    let (tss_low, tss_high) = tss_descriptor(layout.tss(), TSS_AVAILABLE_PRESENT_RING0);
    put_u64(&mut page, 24, tss_low);
    put_u64(&mut page, 32, tss_high);
    let tss = TSS_OFFSET as usize;
    put_u64(&mut page, tss + 4, layout.rsp0_top());
    put_u64(&mut page, tss + 36, layout.ist1_top());
    put_u64(&mut page, tss + 44, layout.ist2_top());
    put_u16(&mut page, tss + 102, TSS_BYTES as u16);
    page
}

fn write_idt_gate(page: &mut [u8; PAGE_BYTES as usize], vector: u8, handler: u64, ist: u8) {
    let offset = usize::from(vector) * 16;
    put_u16(page, offset, handler as u16);
    put_u16(page, offset + 2, KERNEL_CODE_SELECTOR as u16);
    page[offset + 4] = ist;
    page[offset + 5] = INTERRUPT_GATE_PRESENT_RING0;
    put_u16(page, offset + 6, (handler >> 16) as u16);
    put_u32(page, offset + 8, (handler >> 32) as u32);
}

pub fn build_idt_page(
    layout: ResourceLayout,
    fault_handler: u64,
) -> Result<[u8; PAGE_BYTES as usize], Error> {
    if fault_handler < layout.trampoline() || fault_handler >= layout.trampoline() + PAGE_BYTES {
        return Err(Error::ResourceAddress);
    }
    let mut page = [0u8; PAGE_BYTES as usize];
    for vector in EXCEPTION_VECTORS {
        write_idt_gate(
            &mut page,
            vector,
            fault_handler,
            if vector == 8 { 2 } else { 1 },
        );
    }
    for vector in INTERRUPT_VECTORS {
        write_idt_gate(&mut page, vector, fault_handler, 1);
    }
    Ok(page)
}

pub fn validate_post_ap_resources(
    layout: ResourceLayout,
    descriptor_page: &[u8; PAGE_BYTES as usize],
    idt_page: &[u8; PAGE_BYTES as usize],
    xstate_page: &[u8; PAGE_BYTES as usize],
    fault_handler: u64,
    mailbox: &MailboxSnapshot,
) -> Result<(), Error> {
    if get_u64(descriptor_page, 8) != GDT_CODE_DESCRIPTOR
        || get_u64(descriptor_page, 16) != GDT_DATA_DESCRIPTOR
    {
        return Err(Error::ResourceImage);
    }
    let (busy_low, busy_high) = tss_descriptor(layout.tss(), TSS_BUSY_PRESENT_RING0);
    if get_u64(descriptor_page, 24) != busy_low
        || get_u64(descriptor_page, 32) != busy_high
        || get_u64(descriptor_page, TSS_OFFSET as usize + 4) != layout.rsp0_top()
        || get_u64(descriptor_page, TSS_OFFSET as usize + 36) != layout.ist1_top()
        || get_u64(descriptor_page, TSS_OFFSET as usize + 44) != layout.ist2_top()
        || get_u16(descriptor_page, TSS_OFFSET as usize + 102) != TSS_BYTES as u16
    {
        return Err(Error::ResourceImage);
    }
    if idt_page != &build_idt_page(layout, fault_handler)? {
        return Err(Error::ResourceImage);
    }
    if get_u16(xstate_page, 0) != INITIAL_FCW
        || get_u32(xstate_page, 24) != INITIAL_MXCSR
        || get_u64(xstate_page, 512) != mailbox.xstate_bv
        || xstate_page[mailbox.enabled_area_bytes as usize..]
            .iter()
            .any(|byte| *byte != 0)
    {
        return Err(Error::ResourceImage);
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
    Quiesced,
    Parked,
    Validated,
    Released,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RollbackReceipt {
    pub failed_at: TransactionStage,
    pub ap_parked: bool,
    pub runtime_revoked: bool,
    pub resources_zeroed: bool,
    pub resources_released: bool,
}

pub struct PerCpuRuntimeTransaction {
    stage: TransactionStage,
    ap_started: bool,
}

impl PerCpuRuntimeTransaction {
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

    pub fn quiesced(&mut self) -> Result<(), Error> {
        self.advance(TransactionStage::Online, TransactionStage::Quiesced)
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
            runtime_revoked: true,
            resources_zeroed: true,
            resources_released: true,
        })
    }
}

impl Default for PerCpuRuntimeTransaction {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_mailbox(layout: ResourceLayout) -> MailboxSnapshot {
        let mut value = MailboxSnapshot {
            magic: MAILBOX_MAGIC,
            version: MAILBOX_VERSION,
            state: MAILBOX_STATE_QUIESCED,
            command: MAILBOX_COMMAND_STOP,
            target_apic_id: 1,
            bsp_apic_id: 0,
            observed_apic_id: 1,
            leaf1_ecx: REQUIRED_LEAF1_ECX,
            leaf1_edx: smp::REQUIRED_LEAF1_EDX,
            cr0: smp::CR0_PE | smp::CR0_PG | smp::CR0_WP | CR0_MP | CR0_NE,
            cr3: layout.pml4(),
            cr4: smp::CR4_PAE | CR4_OSFXSR | CR4_OSXMMEXCPT | CR4_OSXSAVE,
            efer: smp::EFER_LME | smp::EFER_LMA | smp::EFER_NXE,
            tsc_online: 20,
            tsc_stop: 30,
            baseline_checksum: 0,
            runtime_magic: RUNTIME_MAGIC,
            runtime_version: RUNTIME_VERSION,
            runtime_state: RUNTIME_STATE_QUIESCED,
            expected_gdt_base: layout.gdt(),
            expected_idt_base: layout.idt(),
            expected_tss_base: layout.tss(),
            rsp0: layout.rsp0_top(),
            ist1_bottom: layout.ist1_bottom(),
            ist1_top: layout.ist1_top(),
            ist2_bottom: layout.ist2_bottom(),
            ist2_top: layout.ist2_top(),
            xstate_base: layout.xstate(),
            xstate_bytes: XSTATE_AREA_BYTES,
            xstate_owner_initial: owner_token(1),
            observed_gdt_base: layout.gdt(),
            observed_idt_base: layout.idt(),
            observed_rsp: layout.rsp0_top(),
            xcr0: SELECTED_XCR0,
            xstate_bv: 0,
            rflags: 2,
            observed_gdt_limit: GDT_LIMIT,
            observed_idt_limit: IDT_LIMIT,
            task_selector: KERNEL_TSS_SELECTOR,
            code_selector: KERNEL_CODE_SELECTOR,
            data_selector: KERNEL_DATA_SELECTOR,
            installed_gate_count: INSTALLED_GATE_COUNT,
            owned_interrupt_vector_count: OWNED_INTERRUPT_VECTOR_COUNT,
            interrupts_enabled: 0,
            initial_fcw: u32::from(INITIAL_FCW),
            initial_mxcsr: INITIAL_MXCSR,
            xstate_owner_final: 0,
            xstate_save_count: 1,
            xstate_restore_count: 1,
            fault_code: 0,
            supported_xcr0: SELECTED_XCR0,
            enabled_area_bytes: 576,
            maximum_area_bytes: 576,
            runtime_checksum: 0,
        };
        value.baseline_checksum = baseline_checksum(&value);
        value.runtime_checksum = runtime_checksum(&value);
        value
    }

    #[test]
    fn freezes_guarded_runtime_geometry_below_one_megabyte() {
        let layout = ResourceLayout::new(1, RESOURCE_PAGE_COUNT).unwrap();
        assert_eq!(0x1000, layout.trampoline());
        assert_eq!(0xb000, layout.rsp0_top());
        assert_eq!(0x10_040, layout.tss());
        assert_eq!(0x13000, layout.idt());
        assert_eq!(0x1e000, layout.xstate());
        assert_eq!(1, layout.sipi_vector());
    }

    #[test]
    fn rejects_zero_high_and_wrong_size_resources() {
        assert_eq!(Err(Error::ResourceAddress), ResourceLayout::new(0, 32));
        assert_eq!(Err(Error::ResourceCount), ResourceLayout::new(1, 31));
        assert_eq!(Err(Error::ResourceAddress), ResourceLayout::new(225, 32));
    }

    #[test]
    fn maps_exact_runtime_pages_with_wx_and_guard_policy() {
        let layout = ResourceLayout::new(1, RESOURCE_PAGE_COUNT).unwrap();
        let mut mapped = 0;
        for offset in 0..RESOURCE_PAGE_COUNT {
            if ResourceLayout::is_mapped_offset(offset) {
                mapped += 1;
                let entry = layout.leaf_entry(offset).unwrap();
                assert_ne!(0, entry & smp::ENTRY_PRESENT);
                if offset == TRAMPOLINE_PAGE_OFFSET {
                    assert_eq!(0, entry & (smp::ENTRY_WRITABLE | smp::ENTRY_NO_EXECUTE));
                } else if offset == IDT_PAGE_OFFSET {
                    assert_eq!(
                        smp::ENTRY_NO_EXECUTE,
                        entry & (smp::ENTRY_WRITABLE | smp::ENTRY_NO_EXECUTE)
                    );
                } else {
                    assert_eq!(
                        smp::ENTRY_WRITABLE | smp::ENTRY_NO_EXECUTE,
                        entry & (smp::ENTRY_WRITABLE | smp::ENTRY_NO_EXECUTE)
                    );
                }
            } else {
                assert_eq!(Err(Error::PageRole), layout.leaf_entry(offset));
            }
        }
        assert_eq!(IDENTITY_MAPPED_PAGE_COUNT, mapped);
        assert!(
            GUARD_OFFSETS
                .into_iter()
                .all(ResourceLayout::is_guard_offset)
        );
    }

    #[test]
    fn generated_mailbox_offsets_match_assembly_contract() {
        assert_eq!(352, MAILBOX_BYTES);
        assert_eq!(96, MAILBOX_RUNTIME_MAGIC_OFFSET);
        assert_eq!(192, MAILBOX_OBSERVED_GDT_BASE_OFFSET);
        assert_eq!(312, MAILBOX_RUNTIME_CHECKSUM_OFFSET);
        assert_eq!(320, MAILBOX_SCRATCH_GDTR_OFFSET);
        assert_eq!(336, MAILBOX_SCRATCH_IDTR_OFFSET);
    }

    #[test]
    fn descriptor_page_freezes_available_tss_and_guarded_stacks() {
        let layout = ResourceLayout::new(1, RESOURCE_PAGE_COUNT).unwrap();
        let page = build_descriptor_page(layout);
        let (low, high) = tss_descriptor(layout.tss(), TSS_AVAILABLE_PRESENT_RING0);
        assert_eq!(GDT_CODE_DESCRIPTOR, get_u64(&page, 8));
        assert_eq!(GDT_DATA_DESCRIPTOR, get_u64(&page, 16));
        assert_eq!(low, get_u64(&page, 24));
        assert_eq!(high, get_u64(&page, 32));
        assert_eq!(layout.rsp0_top(), get_u64(&page, TSS_OFFSET as usize + 4));
        assert_eq!(layout.ist1_top(), get_u64(&page, TSS_OFFSET as usize + 36));
        assert_eq!(layout.ist2_top(), get_u64(&page, TSS_OFFSET as usize + 44));
    }

    #[test]
    fn idt_installs_exact_exception_and_owned_interrupt_gates() {
        let layout = ResourceLayout::new(1, RESOURCE_PAGE_COUNT).unwrap();
        let handler = layout.trampoline() + 0x300;
        let page = build_idt_page(layout, handler).unwrap();
        let present = (0..IDT_ENTRY_COUNT as usize)
            .filter(|vector| page[vector * 16 + 5] == INTERRUPT_GATE_PRESENT_RING0)
            .count();
        assert_eq!(INSTALLED_GATE_COUNT as usize, present);
        assert_eq!(2, page[usize::from(8u8) * 16 + 4]);
        assert_eq!(1, page[usize::from(64u8) * 16 + 4]);
        assert_eq!(0, page[65 * 16 + 5]);
    }

    #[test]
    fn validates_complete_quiesced_runtime_mailbox() {
        let layout = ResourceLayout::new(1, RESOURCE_PAGE_COUNT).unwrap();
        let value = valid_mailbox(layout);
        assert_eq!(
            Ok(()),
            validate_mailbox(
                &value,
                layout,
                value.leaf1_ecx & !LEAF1_ECX_OSXSAVE,
                value.leaf1_edx,
                10,
                25,
            )
        );
    }

    #[test]
    fn rejects_descriptor_xstate_interrupt_and_checksum_drift() {
        let layout = ResourceLayout::new(1, RESOURCE_PAGE_COUNT).unwrap();
        let original = valid_mailbox(layout);
        for mutation in 0..5 {
            let mut value = original;
            match mutation {
                0 => value.observed_gdt_base += PAGE_BYTES,
                1 => value.xcr0 = 1,
                2 => value.interrupts_enabled = 1,
                3 => value.fault_code = 1,
                _ => value.runtime_checksum ^= 1,
            }
            assert!(
                validate_mailbox(
                    &value,
                    layout,
                    original.leaf1_ecx,
                    original.leaf1_edx,
                    10,
                    25
                )
                .is_err()
            );
        }
    }

    #[test]
    fn post_ap_resource_validation_requires_hardware_busy_tss() {
        let layout = ResourceLayout::new(1, RESOURCE_PAGE_COUNT).unwrap();
        let handler = layout.trampoline() + 0x300;
        let mut descriptor = build_descriptor_page(layout);
        let idt = build_idt_page(layout, handler).unwrap();
        let mailbox = valid_mailbox(layout);
        let mut xstate = [0u8; PAGE_BYTES as usize];
        put_u16(&mut xstate, 0, INITIAL_FCW);
        put_u32(&mut xstate, 24, INITIAL_MXCSR);
        put_u64(&mut xstate, 512, mailbox.xstate_bv);
        assert_eq!(
            Err(Error::ResourceImage),
            validate_post_ap_resources(layout, &descriptor, &idt, &xstate, handler, &mailbox)
        );
        let (low, high) = tss_descriptor(layout.tss(), TSS_BUSY_PRESENT_RING0);
        put_u64(&mut descriptor, 24, low);
        put_u64(&mut descriptor, 32, high);
        assert_eq!(
            Ok(()),
            validate_post_ap_resources(layout, &descriptor, &idt, &xstate, handler, &mailbox)
        );
    }

    #[test]
    fn transaction_requires_park_and_post_ap_validation_before_release() {
        let mut transaction = PerCpuRuntimeTransaction::new();
        assert_eq!(Err(Error::Transition), transaction.online());
        transaction.reserve().unwrap();
        transaction.prepare().unwrap();
        transaction.startup_sent().unwrap();
        transaction.online().unwrap();
        transaction.quiesced().unwrap();
        assert_eq!(Err(Error::Transition), transaction.released());
        transaction.parked().unwrap();
        transaction.validated().unwrap();
        transaction.released().unwrap();
        assert_eq!(TransactionStage::Released, transaction.stage());
    }

    #[test]
    fn rollback_refuses_started_ap_without_confirmed_park() {
        let mut transaction = PerCpuRuntimeTransaction::new();
        transaction.reserve().unwrap();
        transaction.prepare().unwrap();
        transaction.startup_sent().unwrap();
        assert_eq!(Err(Error::Rollback), transaction.rollback(false));
        let receipt = transaction.rollback(true).unwrap();
        assert!(
            receipt.ap_parked
                && receipt.runtime_revoked
                && receipt.resources_zeroed
                && receipt.resources_released
        );
    }
}
