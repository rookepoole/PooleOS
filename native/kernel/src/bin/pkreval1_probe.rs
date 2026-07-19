use std::env;
use std::fs;
use std::process::ExitCode;

use poolekernel::revalidation::{self, RETAINED_FILE_COUNT};

fn hex(bytes: &[u8; 32]) -> String {
    bytes.iter().map(|byte| format!("{byte:02X}")).collect()
}

fn xorshift64(mut value: u64) -> u64 {
    value ^= value << 13;
    value ^= value >> 7;
    value ^ (value << 17)
}

fn fnv_extend(mut value: u64, bytes: &[u8]) -> u64 {
    for byte in bytes {
        value ^= u64::from(*byte);
        value = value.wrapping_mul(0x0000_0100_0000_01b3);
    }
    value
}

fn retained_files(storage: &[Vec<u8>]) -> [&[u8]; RETAINED_FILE_COUNT] {
    storage
        .iter()
        .map(Vec::as_slice)
        .collect::<Vec<_>>()
        .try_into()
        .expect("fixed retained-file count")
}

fn main() -> ExitCode {
    let mut arguments: Vec<_> = env::args_os().skip(1).collect();
    let mutation_cases =
        if arguments.first().and_then(|value| value.to_str()) == Some("--mutations") {
            if arguments.len() < 2 {
                return ExitCode::from(64);
            }
            let count = match arguments[1]
                .to_str()
                .and_then(|value| value.parse::<usize>().ok())
            {
                Some(value) if (1..=65_536).contains(&value) => value,
                _ => return ExitCode::from(64),
            };
            arguments.drain(..2);
            count
        } else {
            0
        };
    let locator_control = if arguments.first().and_then(|value| value.to_str()) == Some("--locator")
    {
        if arguments.len() < 2 {
            return ExitCode::from(64);
        }
        let index = match arguments[1]
            .to_str()
            .and_then(|value| value.parse::<usize>().ok())
        {
            Some(value) if value < RETAINED_FILE_COUNT => value,
            _ => return ExitCode::from(64),
        };
        arguments.drain(..2);
        Some(index)
    } else {
        None
    };
    let paths = arguments;
    if paths.len() != RETAINED_FILE_COUNT + 1 {
        eprintln!(
            "usage: pkreval1-probe HANDOFF INITIAL RECOVERY SYMBOLS MICROCODE FIRMWARE POLICY MANIFEST TRUST_POLICY TRUST_STATE"
        );
        return ExitCode::from(64);
    }
    let handoff = match fs::read(&paths[0]) {
        Ok(value) => value,
        Err(error) => {
            eprintln!("PKREVAL1 IO_ERROR {error}");
            return ExitCode::from(66);
        }
    };
    let mut storage = Vec::with_capacity(RETAINED_FILE_COUNT);
    for path in &paths[1..] {
        match fs::read(path) {
            Ok(value) => storage.push(value),
            Err(error) => {
                eprintln!("PKREVAL1 IO_ERROR {error}");
                return ExitCode::from(66);
            }
        }
    }
    match revalidation::revalidate_development_files(&handoff, retained_files(&storage)) {
        Ok(summary) => {
            println!(
                "PKREVAL1 PASS retained_files={} artifacts={} parsers={} manifest_bytes={} file_bytes={} retained_sha256={} policy_sha256={} state_sha256={} denial={} authority_grants={} actions={} state_writes={}",
                summary.retained_file_count,
                summary.artifact_count,
                summary.parser_count,
                summary.manifest_bytes,
                summary.retained_file_bytes,
                hex(&summary.retained_set_sha256),
                hex(&summary.policy_sha256),
                hex(&summary.state_sha256),
                summary.denial,
                summary.authority_grants,
                summary.actions_authorized,
                summary.state_writes,
            );
            if mutation_cases != 0 {
                let mut state = 0x504B_5245_5641_4C31u64;
                let mut outcome = 0xcbf2_9ce4_8422_2325u64;
                let mut rejects = 0usize;
                let mut expected = 0usize;
                let mut coverage = 0u16;
                for case_index in 0..mutation_cases {
                    state = xorshift64(state);
                    let target = state as usize % RETAINED_FILE_COUNT;
                    state = xorshift64(state);
                    let offset = state as usize % storage[target].len();
                    state = xorshift64(state);
                    let mask = ((state >> 56) as u8) | 1;
                    storage[target][offset] ^= mask;
                    let mutated = retained_files(&storage);
                    let code = match revalidation::revalidate_development_files(&handoff, mutated) {
                        Ok(_) => "pass",
                        Err(error) => {
                            rejects += 1;
                            if error == revalidation::Error::FileDigest {
                                expected += 1;
                            }
                            error.code()
                        }
                    };
                    storage[target][offset] ^= mask;
                    coverage |= 1 << target;
                    outcome = fnv_extend(outcome, &(case_index as u64).to_le_bytes());
                    outcome = fnv_extend(outcome, &(target as u64).to_le_bytes());
                    outcome = fnv_extend(outcome, &(offset as u64).to_le_bytes());
                    outcome = fnv_extend(outcome, &[mask]);
                    outcome = fnv_extend(outcome, code.as_bytes());
                }
                println!(
                    "PKREVAL1 MUTATION PASS cases={} rejects={} expected_file_digest={} role_coverage={} outcome_fnv1a64={:016X}",
                    mutation_cases,
                    rejects,
                    expected,
                    coverage.count_ones(),
                    outcome,
                );
                if rejects != mutation_cases
                    || expected != mutation_cases
                    || coverage.count_ones() as usize != RETAINED_FILE_COUNT
                {
                    return ExitCode::from(3);
                }
            }
            if let Some(index) = locator_control {
                let files = retained_files(&storage);
                let mut locators = match revalidation::retained_locators(&handoff) {
                    Ok(value) => value,
                    Err(error) => {
                        println!("PKREVAL1 LOCATOR REJECT code={}", error.code());
                        return ExitCode::from(2);
                    }
                };
                locators[index] = locators[index].wrapping_add(4096);
                let retained = core::array::from_fn(|file_index| revalidation::RetainedFile {
                    role: revalidation::RETAINED_ROLES[file_index],
                    physical_base: locators[file_index],
                    bytes: files[file_index],
                });
                match revalidation::revalidate_development(&handoff, retained) {
                    Err(revalidation::Error::FileLocator) => {
                        println!("PKREVAL1 LOCATOR REJECT code=pkreval_file_locator");
                    }
                    Err(error) => {
                        println!("PKREVAL1 LOCATOR REJECT code={}", error.code());
                        return ExitCode::from(3);
                    }
                    Ok(_) => return ExitCode::from(3),
                }
            }
            ExitCode::SUCCESS
        }
        Err(error) => {
            println!("PKREVAL1 REJECT code={}", error.code());
            ExitCode::from(2)
        }
    }
}
