pub const CONTRACT_ID: &str = "PKMSR1";

pub const READ_EFER: u32 = 1 << 0;
pub const READ_STAR: u32 = 1 << 1;
pub const READ_LSTAR: u32 = 1 << 2;
pub const READ_CSTAR: u32 = 1 << 3;
pub const READ_SFMASK: u32 = 1 << 4;
pub const READ_FS_BASE: u32 = 1 << 5;
pub const READ_GS_BASE: u32 = 1 << 6;
pub const READ_KERNEL_GS_BASE: u32 = 1 << 7;
pub const READ_TSC_AUX: u32 = 1 << 8;
pub const READ_MCG_CAP: u32 = 1 << 9;
pub const READ_MCG_STATUS: u32 = 1 << 10;
pub const READ_MCG_CTL: u32 = 1 << 11;

const LEAF1_EDX_MCE: u32 = 1 << 7;
const LEAF1_EDX_MCA: u32 = 1 << 14;
const EXT1_EDX_SYSCALL: u32 = 1 << 11;
const EXT1_EDX_RDTSCP: u32 = 1 << 27;
const EXT1_EDX_LONG_MODE: u32 = 1 << 29;
const CR4_PCE: u64 = 1 << 8;
const EFER_SCE: u64 = 1 << 0;
const EFER_LME: u64 = 1 << 8;
const EFER_LMA: u64 = 1 << 10;
const EFER_NXE: u64 = 1 << 11;
const EFER_ALLOWED: u64 =
    EFER_SCE | EFER_LME | EFER_LMA | EFER_NXE | (1 << 12) | (1 << 13) | (1 << 14) | (1 << 15);
const EFER_REQUIRED: u64 = EFER_LME | EFER_LMA | EFER_NXE;
const LINKAGE_READS: u32 = READ_EFER | READ_STAR | READ_LSTAR | READ_CSTAR | READ_SFMASK;
const BASE_READS: u32 = READ_FS_BASE | READ_GS_BASE | READ_KERNEL_GS_BASE;
const MCA_GLOBAL_READS: u32 = READ_MCG_CAP | READ_MCG_STATUS;
const QEMU64_MCG_CAP_ALLOWED: u64 = 0x0100_01ff;
const QEMU64_MCG_CTL: u64 = u64::MAX;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PrivilegeMsrSnapshot {
    pub vendor: [u8; 12],
    pub max_basic_leaf: u32,
    pub max_extended_leaf: u32,
    pub leaf1_edx: u32,
    pub ext1_edx: u32,
    pub leaf_a_eax: u32,
    pub ext22_eax: u32,
    pub cr4: u64,
    pub efer: u64,
    pub star: u64,
    pub lstar: u64,
    pub cstar: u64,
    pub sfmask: u64,
    pub fs_base: u64,
    pub gs_base: u64,
    pub kernel_gs_base: u64,
    pub tsc_aux: u64,
    pub mcg_cap: u64,
    pub mcg_status: u64,
    pub mcg_ctl: u64,
    pub msr_read_mask: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PrivilegeMsrError {
    Vendor,
    LeafRange,
    Feature,
    PerformanceMonitoring,
    Efer,
    Linkage,
    CanonicalAddress,
    PerCpuBase,
    TscAux,
    MachineCheckCapability,
    MachineCheckStatus,
    MachineCheckControl,
    ReadSet,
}

impl PrivilegeMsrError {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Vendor => "vendor",
            Self::LeafRange => "leaf_range",
            Self::Feature => "feature",
            Self::PerformanceMonitoring => "performance_monitoring",
            Self::Efer => "efer",
            Self::Linkage => "linkage",
            Self::CanonicalAddress => "canonical_address",
            Self::PerCpuBase => "per_cpu_base",
            Self::TscAux => "tsc_aux",
            Self::MachineCheckCapability => "machine_check_capability",
            Self::MachineCheckStatus => "machine_check_status",
            Self::MachineCheckControl => "machine_check_control",
            Self::ReadSet => "read_set",
        }
    }
}

pub const fn is_canonical_48(value: u64) -> bool {
    let high = value >> 48;
    if value & (1 << 47) == 0 {
        high == 0
    } else {
        high == 0xffff
    }
}

pub const fn machine_check_bank_count(snapshot: &PrivilegeMsrSnapshot) -> u8 {
    (snapshot.mcg_cap & 0xff) as u8
}

pub const fn machine_check_ctl_present(snapshot: &PrivilegeMsrSnapshot) -> bool {
    snapshot.mcg_cap & (1 << 8) != 0
}

pub const fn expected_read_mask(snapshot: &PrivilegeMsrSnapshot) -> u32 {
    let mut expected = LINKAGE_READS | BASE_READS;
    if snapshot.ext1_edx & EXT1_EDX_RDTSCP != 0 {
        expected |= READ_TSC_AUX;
    }
    if snapshot.leaf1_edx & (LEAF1_EDX_MCE | LEAF1_EDX_MCA) == LEAF1_EDX_MCE | LEAF1_EDX_MCA {
        expected |= MCA_GLOBAL_READS;
        if machine_check_ctl_present(snapshot) {
            expected |= READ_MCG_CTL;
        }
    }
    expected
}

pub fn validate_snapshot(snapshot: &PrivilegeMsrSnapshot) -> Result<(), PrivilegeMsrError> {
    if snapshot.vendor != *b"AuthenticAMD" {
        return Err(PrivilegeMsrError::Vendor);
    }
    if snapshot.max_basic_leaf < 0x0a || snapshot.max_extended_leaf < 0x8000_0008 {
        return Err(PrivilegeMsrError::LeafRange);
    }
    let required_leaf1 = LEAF1_EDX_MCE | LEAF1_EDX_MCA;
    let required_ext1 = EXT1_EDX_SYSCALL | EXT1_EDX_LONG_MODE;
    if snapshot.leaf1_edx & required_leaf1 != required_leaf1
        || snapshot.ext1_edx & required_ext1 != required_ext1
    {
        return Err(PrivilegeMsrError::Feature);
    }
    let architectural_pmu_version = snapshot.leaf_a_eax & 0xff;
    let amd_perfmon_v2_version = if snapshot.max_extended_leaf >= 0x8000_0022 {
        snapshot.ext22_eax & 0xff
    } else {
        if snapshot.ext22_eax != 0 {
            return Err(PrivilegeMsrError::PerformanceMonitoring);
        }
        0
    };
    if architectural_pmu_version != 0 || amd_perfmon_v2_version != 0 || snapshot.cr4 & CR4_PCE != 0
    {
        return Err(PrivilegeMsrError::PerformanceMonitoring);
    }
    if snapshot.efer & EFER_REQUIRED != EFER_REQUIRED
        || snapshot.efer & !EFER_ALLOWED != 0
        || snapshot.efer & (EFER_SCE | (1 << 12)) != 0
    {
        return Err(PrivilegeMsrError::Efer);
    }
    if !is_canonical_48(snapshot.lstar) || !is_canonical_48(snapshot.cstar) {
        return Err(PrivilegeMsrError::CanonicalAddress);
    }
    if snapshot.star != 0 || snapshot.lstar != 0 || snapshot.cstar != 0 || snapshot.sfmask != 0 {
        return Err(PrivilegeMsrError::Linkage);
    }
    if !is_canonical_48(snapshot.fs_base)
        || !is_canonical_48(snapshot.gs_base)
        || !is_canonical_48(snapshot.kernel_gs_base)
    {
        return Err(PrivilegeMsrError::CanonicalAddress);
    }
    if snapshot.fs_base != 0 || snapshot.gs_base != 0 || snapshot.kernel_gs_base != 0 {
        return Err(PrivilegeMsrError::PerCpuBase);
    }
    if snapshot.tsc_aux >> 32 != 0 || snapshot.tsc_aux != 0 {
        return Err(PrivilegeMsrError::TscAux);
    }
    let banks = machine_check_bank_count(snapshot);
    if snapshot.mcg_cap & !QEMU64_MCG_CAP_ALLOWED != 0
        || snapshot.mcg_cap & (1 << 24) == 0
        || !(1..=32).contains(&banks)
    {
        return Err(PrivilegeMsrError::MachineCheckCapability);
    }
    if snapshot.mcg_status & !0x7 != 0 || snapshot.mcg_status != 0 {
        return Err(PrivilegeMsrError::MachineCheckStatus);
    }
    if machine_check_ctl_present(snapshot) {
        if snapshot.mcg_ctl != QEMU64_MCG_CTL {
            return Err(PrivilegeMsrError::MachineCheckControl);
        }
    } else if snapshot.mcg_ctl != 0 {
        return Err(PrivilegeMsrError::MachineCheckControl);
    }
    if snapshot.msr_read_mask != expected_read_mask(snapshot) {
        return Err(PrivilegeMsrError::ReadSet);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snapshot() -> PrivilegeMsrSnapshot {
        PrivilegeMsrSnapshot {
            vendor: *b"AuthenticAMD",
            max_basic_leaf: 0x0d,
            max_extended_leaf: 0x8000_000a,
            leaf1_edx: LEAF1_EDX_MCE | LEAF1_EDX_MCA,
            ext1_edx: EXT1_EDX_SYSCALL | EXT1_EDX_LONG_MODE,
            leaf_a_eax: 0,
            ext22_eax: 0,
            cr4: 0x668,
            efer: EFER_REQUIRED,
            star: 0,
            lstar: 0,
            cstar: 0,
            sfmask: 0,
            fs_base: 0,
            gs_base: 0,
            kernel_gs_base: 0,
            tsc_aux: 0,
            mcg_cap: 0x0100_010a,
            mcg_status: 0,
            mcg_ctl: u64::MAX,
            msr_read_mask: 0xeff,
        }
    }

    #[test]
    fn accepts_frozen_qemu64_observation() {
        assert_eq!(validate_snapshot(&snapshot()), Ok(()));
    }

    #[test]
    fn rejects_promoted_support_without_read_set() {
        let mut value = snapshot();
        value.ext1_edx |= EXT1_EDX_RDTSCP;
        assert_eq!(validate_snapshot(&value), Err(PrivilegeMsrError::ReadSet));
    }

    #[test]
    fn rejects_enabled_pmu_or_user_rdpmc() {
        let mut value = snapshot();
        value.leaf_a_eax = 1;
        assert_eq!(
            validate_snapshot(&value),
            Err(PrivilegeMsrError::PerformanceMonitoring)
        );
        value = snapshot();
        value.cr4 |= CR4_PCE;
        assert_eq!(
            validate_snapshot(&value),
            Err(PrivilegeMsrError::PerformanceMonitoring)
        );
    }

    #[test]
    fn rejects_syscall_activation() {
        let mut value = snapshot();
        value.efer |= EFER_SCE;
        assert_eq!(validate_snapshot(&value), Err(PrivilegeMsrError::Efer));
    }

    #[test]
    fn rejects_noncanonical_or_active_linkage() {
        let mut value = snapshot();
        value.lstar = 0x0000_8000_0000_0000;
        assert_eq!(
            validate_snapshot(&value),
            Err(PrivilegeMsrError::CanonicalAddress)
        );
        value = snapshot();
        value.star = 1;
        assert_eq!(validate_snapshot(&value), Err(PrivilegeMsrError::Linkage));
    }

    #[test]
    fn rejects_nonzero_early_per_cpu_state() {
        let mut value = snapshot();
        value.kernel_gs_base = 0xffff_8000_0000_0000;
        assert_eq!(
            validate_snapshot(&value),
            Err(PrivilegeMsrError::PerCpuBase)
        );
        value = snapshot();
        value.tsc_aux = 1;
        assert_eq!(validate_snapshot(&value), Err(PrivilegeMsrError::TscAux));
    }

    #[test]
    fn rejects_reserved_machine_check_bits_and_active_status() {
        let mut value = snapshot();
        value.mcg_cap |= 1 << 9;
        assert_eq!(
            validate_snapshot(&value),
            Err(PrivilegeMsrError::MachineCheckCapability)
        );
        value = snapshot();
        value.mcg_status = 1;
        assert_eq!(
            validate_snapshot(&value),
            Err(PrivilegeMsrError::MachineCheckStatus)
        );
    }

    #[test]
    fn rejects_machine_check_control_profile_drift() {
        let mut value = snapshot();
        value.mcg_ctl &= !1;
        assert_eq!(
            validate_snapshot(&value),
            Err(PrivilegeMsrError::MachineCheckControl)
        );
    }

    #[test]
    fn rejects_unadvertised_mcg_ctl_read() {
        let mut value = snapshot();
        value.mcg_cap &= !(1 << 8);
        value.msr_read_mask &= !READ_MCG_CTL;
        value.mcg_ctl = 1;
        assert_eq!(
            validate_snapshot(&value),
            Err(PrivilegeMsrError::MachineCheckControl)
        );
    }

    #[test]
    fn rejects_read_set_drift() {
        let mut value = snapshot();
        value.msr_read_mask &= !READ_EFER;
        assert_eq!(validate_snapshot(&value), Err(PrivilegeMsrError::ReadSet));
    }

    #[test]
    fn canonical_check_accepts_both_halves() {
        assert!(is_canonical_48(0x0000_7fff_ffff_ffff));
        assert!(is_canonical_48(0xffff_8000_0000_0000));
        assert!(!is_canonical_48(0x0000_8000_0000_0000));
    }
}
