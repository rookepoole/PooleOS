use crate::{
    acpi::AcpiError,
    interrupt_time::{MadtTopology, Processor},
};

pub const CONTRACT_ID: &str = "PKSMP1";
pub const SELECTED_MOVE_ID: &str = "N8-SMP-FIRST-AP-001";
pub const SELECTOR: u64 = 12;

pub const PAGE_BYTES: u64 = 4096;
pub const LOW_BOOTSTRAP_LIMIT: u64 = 0x0010_0000;
pub const RESOURCE_PAGE_COUNT: u64 = 14;
pub const TRAMPOLINE_PAGE_OFFSET: u64 = 0;
pub const PML4_PAGE_OFFSET: u64 = 1;
pub const PDPT_PAGE_OFFSET: u64 = 2;
pub const PD_PAGE_OFFSET: u64 = 3;
pub const PT_PAGE_OFFSET: u64 = 4;
pub const STACK_GUARD_LOW_OFFSET: u64 = 5;
pub const STACK_FIRST_PAGE_OFFSET: u64 = 6;
pub const STACK_PAGE_COUNT: u64 = 4;
pub const STACK_GUARD_HIGH_OFFSET: u64 = 10;
pub const PER_CPU_GUARD_LOW_OFFSET: u64 = 11;
pub const PER_CPU_PAGE_OFFSET: u64 = 12;
pub const PER_CPU_GUARD_HIGH_OFFSET: u64 = 13;
pub const GUARD_PAGE_COUNT: u64 = 4;

pub const MAILBOX_MAGIC: u64 = 0x504b_534d_5031_4d42;
pub const MAILBOX_VERSION: u32 = 1;
pub const MAILBOX_BYTES: usize = 96;
pub const MAILBOX_MAGIC_OFFSET: usize = 0;
pub const MAILBOX_VERSION_OFFSET: usize = 8;
pub const MAILBOX_STATE_OFFSET: usize = 12;
pub const MAILBOX_COMMAND_OFFSET: usize = 16;
pub const MAILBOX_TARGET_APIC_ID_OFFSET: usize = 20;
pub const MAILBOX_BSP_APIC_ID_OFFSET: usize = 24;
pub const MAILBOX_OBSERVED_APIC_ID_OFFSET: usize = 28;
pub const MAILBOX_LEAF1_ECX_OFFSET: usize = 32;
pub const MAILBOX_LEAF1_EDX_OFFSET: usize = 36;
pub const MAILBOX_CR0_OFFSET: usize = 40;
pub const MAILBOX_CR3_OFFSET: usize = 48;
pub const MAILBOX_CR4_OFFSET: usize = 56;
pub const MAILBOX_EFER_OFFSET: usize = 64;
pub const MAILBOX_TSC_ONLINE_OFFSET: usize = 72;
pub const MAILBOX_TSC_STOP_OFFSET: usize = 80;
pub const MAILBOX_CHECKSUM_OFFSET: usize = 88;

pub const MAILBOX_STATE_EMPTY: u32 = 0;
pub const MAILBOX_STATE_PREPARED: u32 = 1;
pub const MAILBOX_STATE_ONLINE: u32 = 2;
pub const MAILBOX_STATE_QUIESCED: u32 = 3;
pub const MAILBOX_COMMAND_NONE: u32 = 0;
pub const MAILBOX_COMMAND_STOP: u32 = 1;

pub const ENTRY_PRESENT: u64 = 1 << 0;
pub const ENTRY_WRITABLE: u64 = 1 << 1;
pub const ENTRY_NO_EXECUTE: u64 = 1 << 63;
pub const CR0_PE: u64 = 1 << 0;
pub const CR0_PG: u64 = 1 << 31;
pub const CR0_WP: u64 = 1 << 16;
pub const CR4_PAE: u64 = 1 << 5;
pub const EFER_LME: u64 = 1 << 8;
pub const EFER_LMA: u64 = 1 << 10;
pub const EFER_NXE: u64 = 1 << 11;
pub const LEAF1_EDX_APIC: u32 = 1 << 9;
pub const LEAF1_EDX_FXSR: u32 = 1 << 24;
pub const LEAF1_EDX_SSE: u32 = 1 << 25;
pub const LEAF1_EDX_SSE2: u32 = 1 << 26;
pub const REQUIRED_LEAF1_EDX: u32 =
    LEAF1_EDX_APIC | LEAF1_EDX_FXSR | LEAF1_EDX_SSE | LEAF1_EDX_SSE2;

const FNV_OFFSET: u64 = 0xcbf2_9ce4_8422_2325;
const FNV_PRIME: u64 = 0x0000_0100_0000_01b3;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    PhysicalAccess,
    Acpi(AcpiError),
    AcpiAddress,
    Madt,
    Apic,
    Hpet,
    Memory,
    Timeout,
    Trampoline,
    ResourceAddress,
    ResourceCount,
    SipiVector,
    ProcessorCount,
    BspMissing,
    TargetMissing,
    TargetApicId,
    X2ApicUnsupported,
    PageRole,
    MailboxShape,
    MailboxState,
    MailboxIdentity,
    FeatureMismatch,
    ControlState,
    TimeOrder,
    Checksum,
    Transition,
    Rollback,
}

impl Error {
    pub const fn label(self) -> &'static str {
        match self {
            Self::PhysicalAccess => "physical_access",
            Self::Acpi(error) => error.label(),
            Self::AcpiAddress => "acpi_snapshot_address",
            Self::Madt => "madt",
            Self::Apic => "apic",
            Self::Hpet => "hpet",
            Self::Memory => "memory",
            Self::Timeout => "timeout",
            Self::Trampoline => "trampoline",
            Self::ResourceAddress => "resource_address",
            Self::ResourceCount => "resource_count",
            Self::SipiVector => "sipi_vector",
            Self::ProcessorCount => "processor_count",
            Self::BspMissing => "bsp_missing",
            Self::TargetMissing => "target_missing",
            Self::TargetApicId => "target_apic_id",
            Self::X2ApicUnsupported => "x2apic_unsupported",
            Self::PageRole => "page_role",
            Self::MailboxShape => "mailbox_shape",
            Self::MailboxState => "mailbox_state",
            Self::MailboxIdentity => "mailbox_identity",
            Self::FeatureMismatch => "feature_mismatch",
            Self::ControlState => "control_state",
            Self::TimeOrder => "time_order",
            Self::Checksum => "checksum",
            Self::Transition => "transition",
            Self::Rollback => "rollback",
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
        if start == 0 || end > LOW_BOOTSTRAP_LIMIT {
            return Err(Error::ResourceAddress);
        }
        let vector = start / PAGE_BYTES;
        if vector == 0 || vector > u64::from(u8::MAX) {
            return Err(Error::SipiVector);
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

    pub const fn stack_top(self) -> u64 {
        self.page_address(STACK_FIRST_PAGE_OFFSET + STACK_PAGE_COUNT)
    }

    pub const fn per_cpu(self) -> u64 {
        self.page_address(PER_CPU_PAGE_OFFSET)
    }

    pub const fn sipi_vector(self) -> u8 {
        (self.trampoline() / PAGE_BYTES) as u8
    }

    pub const fn is_guard_offset(offset: u64) -> bool {
        matches!(
            offset,
            STACK_GUARD_LOW_OFFSET
                | STACK_GUARD_HIGH_OFFSET
                | PER_CPU_GUARD_LOW_OFFSET
                | PER_CPU_GUARD_HIGH_OFFSET
        )
    }

    pub const fn is_mapped_offset(offset: u64) -> bool {
        offset == TRAMPOLINE_PAGE_OFFSET
            || (offset >= STACK_FIRST_PAGE_OFFSET
                && offset < STACK_FIRST_PAGE_OFFSET + STACK_PAGE_COUNT)
            || offset == PER_CPU_PAGE_OFFSET
    }

    pub fn leaf_entry(self, offset: u64) -> Result<u64, Error> {
        if offset >= self.page_count || !Self::is_mapped_offset(offset) {
            return Err(Error::PageRole);
        }
        let mut flags = ENTRY_PRESENT;
        if offset != TRAMPOLINE_PAGE_OFFSET {
            flags |= ENTRY_WRITABLE | ENTRY_NO_EXECUTE;
        }
        Ok(self.page_address(offset) | flags)
    }
}

pub fn select_first_ap(topology: &MadtTopology, bsp_apic_id: u32) -> Result<Processor, Error> {
    if topology.enabled_processor_count < 2 {
        return Err(Error::ProcessorCount);
    }
    let bsp = topology
        .processors
        .iter()
        .take(topology.processor_count)
        .copied()
        .find(|item| item.enabled && item.apic_id == bsp_apic_id)
        .ok_or(Error::BspMissing)?;
    if bsp.x2apic || bsp.apic_id > u32::from(u8::MAX) {
        return Err(Error::X2ApicUnsupported);
    }
    let target = topology
        .processors
        .iter()
        .take(topology.processor_count)
        .copied()
        .filter(|item| item.enabled && item.apic_id != bsp_apic_id)
        .min_by_key(|item| item.apic_id)
        .ok_or(Error::TargetMissing)?;
    if target.x2apic {
        return Err(Error::X2ApicUnsupported);
    }
    if target.apic_id > u32::from(u8::MAX) {
        return Err(Error::TargetApicId);
    }
    Ok(target)
}

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
    pub checksum: u64,
}

fn fnv_u64(mut state: u64, value: u64) -> u64 {
    for byte in value.to_le_bytes() {
        state ^= u64::from(byte);
        state = state.wrapping_mul(FNV_PRIME);
    }
    state
}

pub fn mailbox_checksum(mailbox: &MailboxSnapshot) -> u64 {
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

pub fn validate_mailbox(
    mailbox: &MailboxSnapshot,
    layout: ResourceLayout,
    bsp_leaf1_ecx: u32,
    bsp_leaf1_edx: u32,
    bsp_tsc_before: u64,
    bsp_tsc_after: u64,
) -> Result<(), Error> {
    if mailbox.magic != MAILBOX_MAGIC || mailbox.version != MAILBOX_VERSION {
        return Err(Error::MailboxShape);
    }
    if mailbox.state != MAILBOX_STATE_QUIESCED || mailbox.command != MAILBOX_COMMAND_STOP {
        return Err(Error::MailboxState);
    }
    if mailbox.target_apic_id == mailbox.bsp_apic_id
        || mailbox.observed_apic_id != mailbox.target_apic_id
    {
        return Err(Error::MailboxIdentity);
    }
    if mailbox.leaf1_ecx != bsp_leaf1_ecx
        || mailbox.leaf1_edx != bsp_leaf1_edx
        || mailbox.leaf1_edx & REQUIRED_LEAF1_EDX != REQUIRED_LEAF1_EDX
    {
        return Err(Error::FeatureMismatch);
    }
    if mailbox.cr0 & (CR0_PE | CR0_PG | CR0_WP) != CR0_PE | CR0_PG | CR0_WP
        || mailbox.cr3 != layout.pml4()
        || mailbox.cr4 & CR4_PAE == 0
        || mailbox.efer & (EFER_LME | EFER_LMA | EFER_NXE) != EFER_LME | EFER_LMA | EFER_NXE
    {
        return Err(Error::ControlState);
    }
    if bsp_tsc_before == 0
        || mailbox.tsc_online < bsp_tsc_before
        || mailbox.tsc_online > bsp_tsc_after
        || mailbox.tsc_stop < mailbox.tsc_online
    {
        return Err(Error::TimeOrder);
    }
    if mailbox.checksum != mailbox_checksum(mailbox) {
        return Err(Error::Checksum);
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TransactionStage {
    Empty,
    Reserved,
    Prepared,
    InitSent,
    StartupSent,
    Online,
    Quiesced,
    Parked,
    Released,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RollbackReceipt {
    pub stage: TransactionStage,
    pub ap_parked: bool,
    pub mailbox_revoked: bool,
    pub resources_zeroed: bool,
    pub resources_released: bool,
}

pub struct FirstApTransaction {
    stage: TransactionStage,
    ap_started: bool,
}

impl FirstApTransaction {
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

    pub fn init_sent(&mut self) -> Result<(), Error> {
        self.advance(TransactionStage::Prepared, TransactionStage::InitSent)
    }

    pub fn startup_sent(&mut self) -> Result<(), Error> {
        self.advance(TransactionStage::InitSent, TransactionStage::StartupSent)
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

    pub fn released(&mut self) -> Result<(), Error> {
        self.advance(TransactionStage::Parked, TransactionStage::Released)
    }

    pub fn rollback(&mut self, park_succeeded: bool) -> Result<RollbackReceipt, Error> {
        let failed_at = self.stage;
        if self.ap_started && !park_succeeded {
            return Err(Error::Rollback);
        }
        self.stage = TransactionStage::Released;
        Ok(RollbackReceipt {
            stage: failed_at,
            ap_parked: !self.ap_started || park_succeeded,
            mailbox_revoked: true,
            resources_zeroed: true,
            resources_released: true,
        })
    }
}

impl Default for FirstApTransaction {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;
    use crate::interrupt_time::MadtTopology;

    fn topology() -> MadtTopology {
        let mut value = MadtTopology {
            local_apic_address: 0xfee0_0000,
            pcat_compatible: true,
            processor_count: 2,
            enabled_processor_count: 2,
            io_apic_count: 0,
            override_count: 0,
            nmi_source_count: 0,
            local_nmi_count: 0,
            unknown_structure_count: 0,
            address_override_count: 0,
            processors: [Processor {
                firmware_uid: 0,
                apic_id: 0,
                enabled: false,
                online_capable: false,
                x2apic: false,
            }; crate::interrupt_time::MAX_PROCESSORS],
            io_apics: [crate::interrupt_time::IoApic {
                id: 0,
                physical_address: 0,
                global_interrupt_base: 0,
            }; crate::interrupt_time::MAX_IO_APICS],
            overrides: [crate::interrupt_time::InterruptOverride {
                bus: 0,
                source: 0,
                global_interrupt: 0,
                flags: 0,
            }; crate::interrupt_time::MAX_OVERRIDES],
            nmi_sources: [crate::interrupt_time::NmiSource {
                flags: 0,
                global_interrupt: 0,
            }; crate::interrupt_time::MAX_NMI_SOURCES],
            local_nmis: [crate::interrupt_time::LocalNmi {
                firmware_uid: 0,
                lint: 0,
                flags: 0,
                x2apic: false,
            }; crate::interrupt_time::MAX_LOCAL_NMIS],
        };
        value.processors[0] = Processor {
            firmware_uid: 0,
            apic_id: 0,
            enabled: true,
            online_capable: false,
            x2apic: false,
        };
        value.processors[1] = Processor {
            firmware_uid: 1,
            apic_id: 1,
            enabled: true,
            online_capable: false,
            x2apic: false,
        };
        value
    }

    #[test]
    fn freezes_resource_geometry_below_one_megabyte() {
        let layout = ResourceLayout::new(1, RESOURCE_PAGE_COUNT).unwrap();
        assert_eq!(0x1000, layout.trampoline());
        assert_eq!(0xd000, layout.per_cpu());
        assert_eq!(1, layout.sipi_vector());
        assert_eq!(0xb000, layout.stack_top());
    }

    #[test]
    fn rejects_zero_high_and_wrong_size_resources() {
        assert_eq!(Err(Error::ResourceAddress), ResourceLayout::new(0, 14));
        assert_eq!(Err(Error::ResourceCount), ResourceLayout::new(1, 13));
        assert_eq!(Err(Error::ResourceAddress), ResourceLayout::new(250, 14));
    }

    #[test]
    fn maps_only_trampoline_stack_and_per_cpu_pages() {
        let layout = ResourceLayout::new(1, RESOURCE_PAGE_COUNT).unwrap();
        for offset in 0..RESOURCE_PAGE_COUNT {
            if ResourceLayout::is_mapped_offset(offset) {
                let entry = layout.leaf_entry(offset).unwrap();
                assert_ne!(0, entry & ENTRY_PRESENT);
                if offset == TRAMPOLINE_PAGE_OFFSET {
                    assert_eq!(0, entry & (ENTRY_WRITABLE | ENTRY_NO_EXECUTE));
                } else {
                    assert_eq!(
                        ENTRY_WRITABLE | ENTRY_NO_EXECUTE,
                        entry & (ENTRY_WRITABLE | ENTRY_NO_EXECUTE)
                    );
                }
            } else {
                assert_eq!(Err(Error::PageRole), layout.leaf_entry(offset));
            }
        }
    }

    #[test]
    fn keeps_all_four_guard_pages_absent() {
        let guards = [
            STACK_GUARD_LOW_OFFSET,
            STACK_GUARD_HIGH_OFFSET,
            PER_CPU_GUARD_LOW_OFFSET,
            PER_CPU_GUARD_HIGH_OFFSET,
        ];
        assert_eq!(GUARD_PAGE_COUNT as usize, guards.len());
        assert!(guards.into_iter().all(ResourceLayout::is_guard_offset));
    }

    #[test]
    fn selects_the_lowest_enabled_non_bsp_ap() {
        assert_eq!(1, select_first_ap(&topology(), 0).unwrap().apic_id);
    }

    #[test]
    fn rejects_missing_or_x2apic_targets() {
        let mut value = topology();
        value.processors[1].enabled = false;
        value.enabled_processor_count = 1;
        assert_eq!(Err(Error::ProcessorCount), select_first_ap(&value, 0));
        let mut value = topology();
        value.processors[1].x2apic = true;
        assert_eq!(Err(Error::X2ApicUnsupported), select_first_ap(&value, 0));
    }

    fn mailbox(layout: ResourceLayout) -> MailboxSnapshot {
        let mut value = MailboxSnapshot {
            magic: MAILBOX_MAGIC,
            version: MAILBOX_VERSION,
            state: MAILBOX_STATE_QUIESCED,
            command: MAILBOX_COMMAND_STOP,
            target_apic_id: 1,
            bsp_apic_id: 0,
            observed_apic_id: 1,
            leaf1_ecx: 0x8000_0000,
            leaf1_edx: REQUIRED_LEAF1_EDX,
            cr0: CR0_PE | CR0_PG | CR0_WP,
            cr3: layout.pml4(),
            cr4: CR4_PAE,
            efer: EFER_LME | EFER_LMA | EFER_NXE,
            tsc_online: 20,
            tsc_stop: 30,
            checksum: 0,
        };
        value.checksum = mailbox_checksum(&value);
        value
    }

    #[test]
    fn validates_exact_quiesced_mailbox() {
        let layout = ResourceLayout::new(1, RESOURCE_PAGE_COUNT).unwrap();
        let value = mailbox(layout);
        assert_eq!(
            Ok(()),
            validate_mailbox(&value, layout, value.leaf1_ecx, value.leaf1_edx, 10, 25)
        );
    }

    #[test]
    fn rejects_identity_control_time_and_checksum_drift() {
        let layout = ResourceLayout::new(1, RESOURCE_PAGE_COUNT).unwrap();
        let mut value = mailbox(layout);
        value.observed_apic_id = 2;
        assert_eq!(
            Err(Error::MailboxIdentity),
            validate_mailbox(&value, layout, value.leaf1_ecx, value.leaf1_edx, 10, 25)
        );
        let mut value = mailbox(layout);
        value.cr3 += PAGE_BYTES;
        value.checksum = mailbox_checksum(&value);
        assert_eq!(
            Err(Error::ControlState),
            validate_mailbox(&value, layout, value.leaf1_ecx, value.leaf1_edx, 10, 25)
        );
        let mut value = mailbox(layout);
        value.tsc_online = 9;
        value.checksum = mailbox_checksum(&value);
        assert_eq!(
            Err(Error::TimeOrder),
            validate_mailbox(&value, layout, value.leaf1_ecx, value.leaf1_edx, 10, 25)
        );
        let mut value = mailbox(layout);
        value.checksum ^= 1;
        assert_eq!(
            Err(Error::Checksum),
            validate_mailbox(&value, layout, value.leaf1_ecx, value.leaf1_edx, 10, 25)
        );
    }

    #[test]
    fn completes_exact_lifecycle() {
        let mut transaction = FirstApTransaction::new();
        transaction.reserve().unwrap();
        transaction.prepare().unwrap();
        transaction.init_sent().unwrap();
        transaction.startup_sent().unwrap();
        transaction.online().unwrap();
        transaction.quiesced().unwrap();
        transaction.parked().unwrap();
        transaction.released().unwrap();
        assert_eq!(TransactionStage::Released, transaction.stage());
    }

    #[test]
    fn rolls_back_every_pre_start_stage_without_ap_park() {
        for stop_after in 0..3 {
            let mut transaction = FirstApTransaction::new();
            transaction.reserve().unwrap();
            if stop_after >= 1 {
                transaction.prepare().unwrap();
            }
            if stop_after >= 2 {
                transaction.init_sent().unwrap();
            }
            let receipt = transaction.rollback(false).unwrap();
            assert!(
                receipt.ap_parked
                    && receipt.mailbox_revoked
                    && receipt.resources_zeroed
                    && receipt.resources_released
            );
        }
    }

    #[test]
    fn requires_ap_park_after_startup_on_rollback() {
        let mut transaction = FirstApTransaction::new();
        transaction.reserve().unwrap();
        transaction.prepare().unwrap();
        transaction.init_sent().unwrap();
        transaction.startup_sent().unwrap();
        assert_eq!(Err(Error::Rollback), transaction.rollback(false));
        let receipt = transaction.rollback(true).unwrap();
        assert!(receipt.ap_parked && receipt.resources_released);
    }

    #[test]
    fn rejects_out_of_order_lifecycle_transitions() {
        let mut transaction = FirstApTransaction::new();
        assert_eq!(Err(Error::Transition), transaction.prepare());
        transaction.reserve().unwrap();
        assert_eq!(Err(Error::Transition), transaction.online());
    }
}
