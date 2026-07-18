#![no_std]
#![deny(warnings)]

use core::fmt;
use poole_boot_artifact::{Artifact, Role};
use sha2::{Digest, Sha256};

pub const PROOF_ID: &str = "N5-INNER-LIVE-PARSE-001";
pub const ARTIFACT_COUNT: usize = 6;
pub const PARSER_COUNT: u8 = 6;
pub const CROSS_BINDING_COUNT: u8 = 6;
pub const DEVELOPMENT_DENIAL_COUNT: u8 = 6;
pub const ARTIFACT_VERSION: u64 = 1;

const UNEXPECTED_AUTHORITY: &str = "inner_development_authority_unexpected";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Stage {
    InitialOuter,
    RecoveryOuter,
    SymbolsOuter,
    MicrocodeOuter,
    FirmwareOuter,
    PolicyOuter,
    InitialParse,
    RecoveryParse,
    SymbolsParse,
    MicrocodeParse,
    FirmwareParse,
    PolicyParse,
    PolicyInitialDigest,
    PolicyRecoveryDigest,
    PolicySymbolsDigest,
    PolicyMicrocodeDigest,
    PolicyFirmwareDigest,
    PolicyInitialRoutes,
    InitialDenial,
    RecoveryDenial,
    SymbolsDenial,
    MicrocodeDenial,
    FirmwareDenial,
    PolicyDenial,
    Summary,
}

impl Stage {
    pub const fn code(self) -> &'static str {
        match self {
            Self::InitialOuter => "inner.initial.outer",
            Self::RecoveryOuter => "inner.recovery.outer",
            Self::SymbolsOuter => "inner.symbols.outer",
            Self::MicrocodeOuter => "inner.microcode.outer",
            Self::FirmwareOuter => "inner.firmware.outer",
            Self::PolicyOuter => "inner.policy.outer",
            Self::InitialParse => "inner.initial.parse",
            Self::RecoveryParse => "inner.recovery.parse",
            Self::SymbolsParse => "inner.symbols.parse",
            Self::MicrocodeParse => "inner.microcode.parse",
            Self::FirmwareParse => "inner.firmware.parse",
            Self::PolicyParse => "inner.policy.parse",
            Self::PolicyInitialDigest => "inner.policy.initial_digest",
            Self::PolicyRecoveryDigest => "inner.policy.recovery_digest",
            Self::PolicySymbolsDigest => "inner.policy.symbols_digest",
            Self::PolicyMicrocodeDigest => "inner.policy.microcode_digest",
            Self::PolicyFirmwareDigest => "inner.policy.firmware_digest",
            Self::PolicyInitialRoutes => "inner.policy.initial_routes",
            Self::InitialDenial => "inner.initial.denial",
            Self::RecoveryDenial => "inner.recovery.denial",
            Self::SymbolsDenial => "inner.symbols.denial",
            Self::MicrocodeDenial => "inner.microcode.denial",
            Self::FirmwareDenial => "inner.firmware.denial",
            Self::PolicyDenial => "inner.policy.denial",
            Self::Summary => "inner.summary",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Failure {
    pub stage: Stage,
    pub code: &'static str,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Summary {
    pub artifact_count: u8,
    pub parser_count: u8,
    pub cross_binding_count: u8,
    pub development_denial_count: u8,
    pub file_bytes: usize,
    pub payload_bytes: usize,
    pub retained_set_sha256: [u8; 32],
    pub authority_grants: u8,
    pub actions_authorized: u8,
    pub state_writes: u8,
    pub hardware_observations: u8,
}

pub struct DigestHex<'a>(&'a [u8; 32]);

impl fmt::Display for DigestHex<'_> {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        for byte in self.0 {
            write!(formatter, "{byte:02X}")?;
        }
        Ok(())
    }
}

impl Summary {
    pub const fn digest_hex(&self) -> DigestHex<'_> {
        DigestHex(&self.retained_set_sha256)
    }
}

fn failure(stage: Stage, code: &'static str) -> Failure {
    Failure { stage, code }
}

fn parse_outer<'a>(bytes: &'a [u8], role: Role, stage: Stage) -> Result<Artifact<'a>, Failure> {
    poole_boot_artifact::parse_bound(bytes, role, ARTIFACT_VERSION)
        .map_err(|error| failure(stage, error.code()))
}

fn verify_digest(actual: &[u8], expected: [u8; 32], stage: Stage) -> Result<(), Failure> {
    if poole_boot_artifact::sha256(actual) == expected {
        Ok(())
    } else {
        Err(failure(stage, "inner_policy_payload_digest"))
    }
}

fn retained_set_sha256(files: [&[u8]; ARTIFACT_COUNT]) -> [u8; 32] {
    let mut digest = Sha256::new();
    digest.update(b"POOLEOS/INNER-LIVE-SET/V1\0");
    for (index, bytes) in files.iter().enumerate() {
        digest.update(Role::ALL[index].code().to_le_bytes());
        digest.update((bytes.len() as u64).to_le_bytes());
        digest.update(bytes);
    }
    let value = digest.finalize();
    let mut output = [0u8; 32];
    output.copy_from_slice(&value);
    output
}

pub fn validate_development_set(files: [&[u8]; ARTIFACT_COUNT]) -> Result<Summary, Failure> {
    let initial_outer = parse_outer(files[0], Role::InitialSystem, Stage::InitialOuter)?;
    let recovery_outer = parse_outer(files[1], Role::Recovery, Stage::RecoveryOuter)?;
    let symbols_outer = parse_outer(files[2], Role::Symbols, Stage::SymbolsOuter)?;
    let microcode_outer = parse_outer(files[3], Role::Microcode, Stage::MicrocodeOuter)?;
    let firmware_outer = parse_outer(files[4], Role::FirmwareManifest, Stage::FirmwareOuter)?;
    let policy_outer = parse_outer(files[5], Role::PolicyBundle, Stage::PolicyOuter)?;

    let initial = poole_initial_system::parse(initial_outer.payload)
        .map_err(|error| failure(Stage::InitialParse, error.code()))?;
    let recovery = poole_recovery::parse(recovery_outer.payload)
        .map_err(|error| failure(Stage::RecoveryParse, error.code()))?;
    let symbols = poole_symbols::parse(symbols_outer.payload)
        .map_err(|error| failure(Stage::SymbolsParse, error.code()))?;
    let microcode = poole_microcode::parse(microcode_outer.payload)
        .map_err(|error| failure(Stage::MicrocodeParse, error.code()))?;
    let firmware = poole_firmware::parse(firmware_outer.payload)
        .map_err(|error| failure(Stage::FirmwareParse, error.code()))?;
    let policy = poole_policy::parse(policy_outer.payload)
        .map_err(|error| failure(Stage::PolicyParse, error.code()))?;

    verify_digest(
        initial_outer.payload,
        policy.initial_system_sha256,
        Stage::PolicyInitialDigest,
    )?;
    verify_digest(
        recovery_outer.payload,
        policy.recovery_sha256,
        Stage::PolicyRecoveryDigest,
    )?;
    verify_digest(
        symbols_outer.payload,
        policy.symbols_sha256,
        Stage::PolicySymbolsDigest,
    )?;
    verify_digest(
        microcode_outer.payload,
        policy.microcode_sha256,
        Stage::PolicyMicrocodeDigest,
    )?;
    verify_digest(
        firmware_outer.payload,
        policy.firmware_sha256,
        Stage::PolicyFirmwareDigest,
    )?;
    poole_policy::validate_initial_system(&policy, initial_outer.payload)
        .map_err(|error| failure(Stage::PolicyInitialRoutes, error.code()))?;

    match poole_initial_system::authorize_activation(
        &initial,
        &poole_initial_system::ActivationContext::development(),
    ) {
        Err(poole_initial_system::Error::ActivationOuterSignature) => {}
        Err(error) => return Err(failure(Stage::InitialDenial, error.code())),
        Ok(()) => return Err(failure(Stage::InitialDenial, UNEXPECTED_AUTHORITY)),
    }
    match poole_recovery::authorize_activation(
        &recovery,
        &poole_recovery::ActivationContext::development(),
    ) {
        Err(poole_recovery::Error::ActivationOuterSignature) => {}
        Err(error) => return Err(failure(Stage::RecoveryDenial, error.code())),
        Ok(()) => return Err(failure(Stage::RecoveryDenial, UNEXPECTED_AUTHORITY)),
    }
    match poole_symbols::authorize_consumption(
        &symbols,
        &poole_symbols::ConsumptionContext::development(&symbols),
    ) {
        Err(poole_symbols::Error::ActivationOuterSignature) => {}
        Err(error) => return Err(failure(Stage::SymbolsDenial, error.code())),
        Ok(()) => return Err(failure(Stage::SymbolsDenial, UNEXPECTED_AUTHORITY)),
    }
    let microcode_context = poole_microcode::ApplyContext::development(&microcode, &[]);
    match poole_microcode::authorize_apply_plan(&microcode, &microcode_context, &[]) {
        Err(poole_microcode::Error::ActivationOuterSignature) => {}
        Err(error) => return Err(failure(Stage::MicrocodeDenial, error.code())),
        Ok(_) => return Err(failure(Stage::MicrocodeDenial, UNEXPECTED_AUTHORITY)),
    }
    let firmware_context = poole_firmware::ActivationContext::development(&firmware, &[]);
    match poole_firmware::authorize_dry_run_plan(&firmware, &firmware_context) {
        Err(poole_firmware::Error::ActivationOuterSignature) => {}
        Err(error) => return Err(failure(Stage::FirmwareDenial, error.code())),
        Ok(_) => return Err(failure(Stage::FirmwareDenial, UNEXPECTED_AUTHORITY)),
    }
    let policy_context = poole_policy::ActivationContext::development(&policy)
        .map_err(|error| failure(Stage::PolicyDenial, error.code()))?;
    match poole_policy::authorize_dry_run_decision(&policy, &policy_context) {
        Err(poole_policy::Error::ActivationOuterSignature) => {}
        Err(error) => return Err(failure(Stage::PolicyDenial, error.code())),
        Ok(_) => return Err(failure(Stage::PolicyDenial, UNEXPECTED_AUTHORITY)),
    }

    let file_bytes = files.iter().try_fold(0usize, |total, bytes| {
        total
            .checked_add(bytes.len())
            .ok_or(failure(Stage::Summary, "inner_file_bytes_overflow"))
    })?;
    let payload_bytes = [
        initial_outer.payload,
        recovery_outer.payload,
        symbols_outer.payload,
        microcode_outer.payload,
        firmware_outer.payload,
        policy_outer.payload,
    ]
    .iter()
    .try_fold(0usize, |total, bytes| {
        total
            .checked_add(bytes.len())
            .ok_or(failure(Stage::Summary, "inner_payload_bytes_overflow"))
    })?;

    Ok(Summary {
        artifact_count: ARTIFACT_COUNT as u8,
        parser_count: PARSER_COUNT,
        cross_binding_count: CROSS_BINDING_COUNT,
        development_denial_count: DEVELOPMENT_DENIAL_COUNT,
        file_bytes,
        payload_bytes,
        retained_set_sha256: retained_set_sha256(files),
        authority_grants: 0,
        actions_authorized: 0,
        state_writes: 0,
        hardware_observations: 0,
    })
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;
    use std::vec;
    use std::vec::Vec;

    const INITIAL: &[u8] = include_bytes!("../../../specs/fixtures/ppol1-canonical-pinit.bin");
    const RECOVERY: &[u8] = include_bytes!("../../../specs/fixtures/prec1-canonical.bin");
    const SYMBOLS: &[u8] = include_bytes!("../../../specs/fixtures/psym1-canonical.bin");
    const MICROCODE: &[u8] = include_bytes!("../../../specs/fixtures/pmcu1-canonical.bin");
    const FIRMWARE: &[u8] = include_bytes!("../../../specs/fixtures/pfwm1-canonical.bin");
    const POLICY: &[u8] = include_bytes!("../../../specs/fixtures/ppol1-canonical.bin");

    fn envelope(role: Role, payload: &[u8]) -> Vec<u8> {
        let mut output = vec![0u8; poole_boot_artifact::HEADER_BYTES + payload.len()];
        poole_boot_artifact::encode(role, ARTIFACT_VERSION, payload, &mut output).unwrap();
        output
    }

    fn canonical_files() -> [Vec<u8>; ARTIFACT_COUNT] {
        [
            envelope(Role::InitialSystem, INITIAL),
            envelope(Role::Recovery, RECOVERY),
            envelope(Role::Symbols, SYMBOLS),
            envelope(Role::Microcode, MICROCODE),
            envelope(Role::FirmwareManifest, FIRMWARE),
            envelope(Role::PolicyBundle, POLICY),
        ]
    }

    fn slices(files: &[Vec<u8>; ARTIFACT_COUNT]) -> [&[u8]; ARTIFACT_COUNT] {
        [
            &files[0], &files[1], &files[2], &files[3], &files[4], &files[5],
        ]
    }

    #[test]
    fn canonical_retained_set_parses_cross_binds_and_denies() {
        let files = canonical_files();
        let summary = validate_development_set(slices(&files)).unwrap();
        assert_eq!(summary.artifact_count, 6);
        assert_eq!(summary.parser_count, 6);
        assert_eq!(summary.cross_binding_count, 6);
        assert_eq!(summary.development_denial_count, 6);
        assert_eq!(summary.authority_grants, 0);
        assert_eq!(summary.actions_authorized, 0);
        assert_eq!(summary.state_writes, 0);
        assert_eq!(summary.hardware_observations, 0);
        assert!(summary.retained_set_sha256.iter().any(|byte| *byte != 0));
    }

    #[test]
    fn reordered_outer_roles_fail_closed() {
        let mut files = canonical_files();
        files.swap(0, 1);
        let failure = validate_development_set(slices(&files)).unwrap_err();
        assert_eq!(failure.stage, Stage::InitialOuter);
        assert_eq!(failure.code, "artifact_role_binding");
    }

    #[test]
    fn exact_outer_byte_mutation_fails_before_inner_parse() {
        let mut files = canonical_files();
        let last = files[2].len() - 1;
        files[2][last] ^= 1;
        let failure = validate_development_set(slices(&files)).unwrap_err();
        assert_eq!(failure.stage, Stage::SymbolsOuter);
        assert_eq!(failure.code, "artifact_digest");
    }

    #[test]
    fn recomputed_envelope_cannot_hide_invalid_inner_bytes() {
        let mut files = canonical_files();
        let mut payload = INITIAL.to_vec();
        let last = payload.len() - 1;
        payload[last] ^= 1;
        files[0] = envelope(Role::InitialSystem, &payload);
        let failure = validate_development_set(slices(&files)).unwrap_err();
        assert_eq!(failure.stage, Stage::InitialParse);
        assert_eq!(failure.code, "pinit_body_digest");
    }

    #[test]
    fn valid_policy_with_substituted_role_digest_fails_cross_binding() {
        let mut files = canonical_files();
        let mut policy = POLICY.to_vec();
        policy[160] ^= 1;
        files[5] = envelope(Role::PolicyBundle, &policy);
        let failure = validate_development_set(slices(&files)).unwrap_err();
        assert_eq!(failure.stage, Stage::PolicyRecoveryDigest);
        assert_eq!(failure.code, "inner_policy_payload_digest");
    }
}
