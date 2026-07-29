use std::env;
use std::process::ExitCode;

use poole_cpu_policy::{AgesaVersion, BoardLineage, Evidence, RdseedPolicy, evaluate};

fn parse_u64(value: &str) -> Option<u64> {
    let value = value.strip_prefix("0x").unwrap_or(value);
    u64::from_str_radix(value, 16).ok()
}

fn parse_u32(value: &str) -> Option<u32> {
    parse_u64(value).and_then(|parsed| parsed.try_into().ok())
}

fn parse_u16(value: &str) -> Option<u16> {
    value.parse().ok()
}

fn parse_u8(value: &str) -> Option<u8> {
    value.parse().ok()
}

fn parse_bool(value: &str) -> Option<bool> {
    match value {
        "0" => Some(false),
        "1" => Some(true),
        _ => None,
    }
}

fn main() -> ExitCode {
    let arguments: Vec<String> = env::args().skip(1).collect();
    if arguments.len() != 19 {
        eprintln!(
            "usage: pkerr1-probe SIGNATURE FEATURES LINEAGE BIOS STABLE AGESA_MAJOR AGESA_MINOR AGESA_PATCH AGESA_BUILD AGESA_SUFFIX MICROCODE HOMOGENEOUS NATIVE FLOOR GUIDE_AVAILABLE GUIDE_APPLICABLE RDSEED_EXPOSED RDSEED_POLICY DIRECT_SOURCES"
        );
        return ExitCode::from(64);
    }
    let evidence = match (
        parse_u32(&arguments[0]),
        parse_u64(&arguments[1]),
        parse_u8(&arguments[2]).and_then(BoardLineage::from_u8),
        parse_u16(&arguments[3]),
        parse_bool(&arguments[4]),
        parse_u8(&arguments[5]),
        parse_u8(&arguments[6]),
        parse_u8(&arguments[7]),
        parse_u8(&arguments[8]),
        parse_u8(&arguments[9]),
        parse_u32(&arguments[10]),
        parse_bool(&arguments[11]),
        parse_bool(&arguments[12]),
        parse_bool(&arguments[13]),
        parse_bool(&arguments[14]),
        parse_bool(&arguments[15]),
        parse_bool(&arguments[16]),
        parse_u8(&arguments[17]).and_then(RdseedPolicy::from_u8),
        parse_bool(&arguments[18]),
    ) {
        (
            Some(cpuid_signature),
            Some(feature_mask),
            Some(board_lineage),
            Some(bios_number),
            Some(bios_is_stable),
            Some(agesa_major),
            Some(agesa_minor),
            Some(agesa_patch),
            Some(agesa_build),
            Some(agesa_suffix),
            Some(microcode_revision),
            Some(all_processors_same_revision),
            Some(native_revision_evidence_trusted),
            Some(vendor_numeric_microcode_floor_available),
            Some(model44_revision_guide_available),
            Some(model44_revision_guide_applicable),
            Some(rdseed_capability_exposed),
            Some(rdseed_policy),
            Some(direct_product_sources_only),
        ) => Evidence {
            cpuid_signature,
            feature_mask,
            board_lineage,
            bios_number,
            bios_is_stable,
            agesa: AgesaVersion::new(
                agesa_major,
                agesa_minor,
                agesa_patch,
                agesa_build,
                agesa_suffix,
            ),
            microcode_revision,
            all_processors_same_revision,
            native_revision_evidence_trusted,
            vendor_numeric_microcode_floor_available,
            model44_revision_guide_available,
            model44_revision_guide_applicable,
            rdseed_capability_exposed,
            rdseed_policy,
            direct_product_sources_only,
        },
        _ => return ExitCode::from(64),
    };
    let decision = evaluate(evidence);
    println!(
        "PKERR1 DECISION failures=0x{:08X} satisfied={} authority={} actions={} writes={}",
        decision.failures,
        u8::from(decision.policy_satisfied()),
        decision.authority_grants,
        decision.actions_authorized,
        decision.state_writes,
    );
    ExitCode::SUCCESS
}
