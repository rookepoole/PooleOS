#![no_std]
#![deny(warnings)]

pub const CONTRACT_ID: &str = "PKERR1";
pub const TARGET_CPUID_SIGNATURE: u32 = 0x00b4_0f40;
pub const WINDOWS_REPORTED_MICROCODE_REVISION: u32 = 0x0b40_4023;

pub const FEATURE_LONG_MODE: u64 = 1 << 0;
pub const FEATURE_NX: u64 = 1 << 1;
pub const FEATURE_SSE2: u64 = 1 << 2;
pub const FEATURE_XSAVE: u64 = 1 << 3;
pub const FEATURE_OSXSAVE: u64 = 1 << 4;
pub const FEATURE_FSGSBASE: u64 = 1 << 5;
pub const FEATURE_SMEP: u64 = 1 << 6;
pub const FEATURE_SMAP: u64 = 1 << 7;
pub const FEATURE_INVARIANT_TSC: u64 = 1 << 8;
pub const REQUIRED_FEATURES: u64 = FEATURE_LONG_MODE
    | FEATURE_NX
    | FEATURE_SSE2
    | FEATURE_XSAVE
    | FEATURE_OSXSAVE
    | FEATURE_FSGSBASE
    | FEATURE_SMEP
    | FEATURE_SMAP
    | FEATURE_INVARIANT_TSC;

pub const FAILURE_IDENTITY: u32 = 1 << 0;
pub const FAILURE_FEATURES: u32 = 1 << 1;
pub const FAILURE_BOARD_LINEAGE: u32 = 1 << 2;
pub const FAILURE_BIOS_FLOOR: u32 = 1 << 3;
pub const FAILURE_AGESA_FLOOR: u32 = 1 << 4;
pub const FAILURE_MICROCODE_EVIDENCE: u32 = 1 << 5;
pub const FAILURE_MICROCODE_FLOOR_SOURCE: u32 = 1 << 6;
pub const FAILURE_ERRATA_GUIDE: u32 = 1 << 7;
pub const FAILURE_RDSEED_POLICY: u32 = 1 << 8;
pub const FAILURE_SOURCE_APPLICABILITY: u32 = 1 << 9;

pub const CURRENT_EXPECTED_FAILURES: u32 = FAILURE_BOARD_LINEAGE
    | FAILURE_BIOS_FLOOR
    | FAILURE_AGESA_FLOOR
    | FAILURE_MICROCODE_EVIDENCE
    | FAILURE_MICROCODE_FLOOR_SOURCE
    | FAILURE_ERRATA_GUIDE;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum BoardLineage {
    Unknown = 0,
    Rev10To12 = 1,
    Rev13 = 2,
}

impl BoardLineage {
    pub const fn from_u8(value: u8) -> Option<Self> {
        match value {
            0 => Some(Self::Unknown),
            1 => Some(Self::Rev10To12),
            2 => Some(Self::Rev13),
            _ => None,
        }
    }

    pub const fn minimum_stable_bios_number(self) -> Option<u16> {
        match self {
            Self::Unknown => None,
            Self::Rev10To12 => Some(39),
            Self::Rev13 => Some(7),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum RdseedPolicy {
    Unknown = 0,
    Masked = 1,
    Use64BitOnly = 2,
    PatchedFirmware = 3,
}

impl RdseedPolicy {
    pub const fn from_u8(value: u8) -> Option<Self> {
        match value {
            0 => Some(Self::Unknown),
            1 => Some(Self::Masked),
            2 => Some(Self::Use64BitOnly),
            3 => Some(Self::PatchedFirmware),
            _ => None,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct AgesaVersion {
    pub major: u8,
    pub minor: u8,
    pub patch: u8,
    pub build: u8,
    pub suffix_rank: u8,
}

impl AgesaVersion {
    pub const fn new(major: u8, minor: u8, patch: u8, build: u8, suffix_rank: u8) -> Self {
        Self {
            major,
            minor,
            patch,
            build,
            suffix_rank,
        }
    }

    pub const fn at_least(self, floor: Self) -> bool {
        if self.major != floor.major {
            return self.major > floor.major;
        }
        if self.minor != floor.minor {
            return self.minor > floor.minor;
        }
        if self.patch != floor.patch {
            return self.patch > floor.patch;
        }
        if self.build != floor.build {
            return self.build > floor.build;
        }
        self.suffix_rank >= floor.suffix_rank
    }
}

pub const COMBINED_SECURITY_AGESA_FLOOR: AgesaVersion = AgesaVersion::new(1, 2, 0, 3, 9);
pub const CURRENT_AGESA: AgesaVersion = AgesaVersion::new(1, 2, 0, 2, 2);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Evidence {
    pub cpuid_signature: u32,
    pub feature_mask: u64,
    pub board_lineage: BoardLineage,
    pub bios_number: u16,
    pub bios_is_stable: bool,
    pub agesa: AgesaVersion,
    pub microcode_revision: u32,
    pub all_processors_same_revision: bool,
    pub native_revision_evidence_trusted: bool,
    pub vendor_numeric_microcode_floor_available: bool,
    pub model44_revision_guide_available: bool,
    pub model44_revision_guide_applicable: bool,
    pub rdseed_capability_exposed: bool,
    pub rdseed_policy: RdseedPolicy,
    pub direct_product_sources_only: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Decision {
    pub failures: u32,
    pub authority_grants: u8,
    pub actions_authorized: u8,
    pub state_writes: u8,
}

impl Decision {
    pub const fn policy_satisfied(self) -> bool {
        self.failures == 0
    }
}

pub const fn evaluate(evidence: Evidence) -> Decision {
    let mut failures = 0;
    if evidence.cpuid_signature != TARGET_CPUID_SIGNATURE {
        failures |= FAILURE_IDENTITY;
    }
    if evidence.feature_mask & REQUIRED_FEATURES != REQUIRED_FEATURES {
        failures |= FAILURE_FEATURES;
    }
    let minimum_bios = evidence.board_lineage.minimum_stable_bios_number();
    if minimum_bios.is_none() {
        failures |= FAILURE_BOARD_LINEAGE;
    }
    if !evidence.bios_is_stable
        || match minimum_bios {
            Some(minimum) => evidence.bios_number < minimum,
            None => true,
        }
    {
        failures |= FAILURE_BIOS_FLOOR;
    }
    if !evidence.agesa.at_least(COMBINED_SECURITY_AGESA_FLOOR) {
        failures |= FAILURE_AGESA_FLOOR;
    }
    if evidence.microcode_revision == 0
        || !evidence.all_processors_same_revision
        || !evidence.native_revision_evidence_trusted
    {
        failures |= FAILURE_MICROCODE_EVIDENCE;
    }
    if !evidence.vendor_numeric_microcode_floor_available {
        failures |= FAILURE_MICROCODE_FLOOR_SOURCE;
    }
    if !evidence.model44_revision_guide_available || !evidence.model44_revision_guide_applicable {
        failures |= FAILURE_ERRATA_GUIDE;
    }
    if evidence.rdseed_capability_exposed {
        let rdseed_safe = match evidence.rdseed_policy {
            RdseedPolicy::Masked | RdseedPolicy::Use64BitOnly => true,
            RdseedPolicy::PatchedFirmware => evidence.agesa.at_least(COMBINED_SECURITY_AGESA_FLOOR),
            RdseedPolicy::Unknown => false,
        };
        if !rdseed_safe {
            failures |= FAILURE_RDSEED_POLICY;
        }
    }
    if !evidence.direct_product_sources_only {
        failures |= FAILURE_SOURCE_APPLICABILITY;
    }
    Decision {
        failures,
        authority_grants: 0,
        actions_authorized: 0,
        state_writes: 0,
    }
}

pub const fn current_observation() -> Evidence {
    Evidence {
        cpuid_signature: TARGET_CPUID_SIGNATURE,
        feature_mask: REQUIRED_FEATURES,
        board_lineage: BoardLineage::Unknown,
        bios_number: 32,
        bios_is_stable: true,
        agesa: CURRENT_AGESA,
        microcode_revision: WINDOWS_REPORTED_MICROCODE_REVISION,
        all_processors_same_revision: true,
        native_revision_evidence_trusted: false,
        vendor_numeric_microcode_floor_available: false,
        model44_revision_guide_available: false,
        model44_revision_guide_applicable: false,
        rdseed_capability_exposed: true,
        rdseed_policy: RdseedPolicy::Masked,
        direct_product_sources_only: true,
    }
}

pub const fn synthetic_qualification_fixture() -> Evidence {
    Evidence {
        cpuid_signature: TARGET_CPUID_SIGNATURE,
        feature_mask: REQUIRED_FEATURES,
        board_lineage: BoardLineage::Rev10To12,
        bios_number: 39,
        bios_is_stable: true,
        agesa: AgesaVersion::new(1, 2, 8, 0, 0),
        microcode_revision: WINDOWS_REPORTED_MICROCODE_REVISION,
        all_processors_same_revision: true,
        native_revision_evidence_trusted: true,
        vendor_numeric_microcode_floor_available: true,
        model44_revision_guide_available: true,
        model44_revision_guide_applicable: true,
        rdseed_capability_exposed: true,
        rdseed_policy: RdseedPolicy::PatchedFirmware,
        direct_product_sources_only: true,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn current_observation_denies_exactly_declared_gaps() {
        let decision = evaluate(current_observation());
        assert_eq!(decision.failures, CURRENT_EXPECTED_FAILURES);
        assert!(!decision.policy_satisfied());
        assert_eq!(decision.authority_grants, 0);
        assert_eq!(decision.actions_authorized, 0);
        assert_eq!(decision.state_writes, 0);
    }

    #[test]
    fn synthetic_all_true_fixture_is_policy_only() {
        let decision = evaluate(synthetic_qualification_fixture());
        assert!(decision.policy_satisfied());
        assert_eq!(decision.authority_grants, 0);
        assert_eq!(decision.actions_authorized, 0);
        assert_eq!(decision.state_writes, 0);
    }

    #[test]
    fn target_identity_is_exact() {
        let mut evidence = synthetic_qualification_fixture();
        evidence.cpuid_signature ^= 1;
        assert_eq!(evaluate(evidence).failures, FAILURE_IDENTITY);
    }

    #[test]
    fn missing_mandatory_feature_is_rejected() {
        let mut evidence = synthetic_qualification_fixture();
        evidence.feature_mask &= !FEATURE_SMAP;
        assert_eq!(evaluate(evidence).failures, FAILURE_FEATURES);
    }

    #[test]
    fn wrong_model_revision_guide_is_rejected() {
        let mut evidence = synthetic_qualification_fixture();
        evidence.model44_revision_guide_applicable = false;
        assert_eq!(evaluate(evidence).failures, FAILURE_ERRATA_GUIDE);
    }

    #[test]
    fn rdseed_requires_a_declared_safe_path() {
        let mut evidence = synthetic_qualification_fixture();
        evidence.rdseed_policy = RdseedPolicy::Unknown;
        assert_eq!(evaluate(evidence).failures, FAILURE_RDSEED_POLICY);
    }
}
