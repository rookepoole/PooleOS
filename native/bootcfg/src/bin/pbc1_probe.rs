use std::fmt::Write as _;
use std::io::{self, BufRead};

fn decode_hex(value: &str) -> Result<Vec<u8>, ()> {
    if !value.len().is_multiple_of(2) {
        return Err(());
    }
    value
        .as_bytes()
        .chunks_exact(2)
        .map(|pair| {
            let text = std::str::from_utf8(pair).map_err(|_| ())?;
            u8::from_str_radix(text, 16).map_err(|_| ())
        })
        .collect()
}

fn parse_request(value: &str) -> Result<String, &'static str> {
    let (capacity_text, encoded) = value
        .strip_prefix("P:")
        .and_then(|rest| rest.split_once(':'))
        .ok_or("transport")?;
    let capacity = capacity_text.parse::<usize>().map_err(|_| "transport")?;
    if capacity > poole_boot_config::MAX_ENTRIES {
        return Err("transport");
    }
    let bytes = decode_hex(encoded).map_err(|_| "transport")?;
    let mut storage = [poole_boot_config::Entry::EMPTY; poole_boot_config::MAX_ENTRIES];
    let config =
        poole_boot_config::parse(&bytes, &mut storage[..capacity]).map_err(|error| error.code())?;
    let mut summary = format!(
        "OK;entry_count={};default_entry={};timeout_ms={};boot_attempt_limit={}",
        config.entries.len(),
        config.default_entry,
        config.timeout_ms,
        config.boot_attempt_limit
    );
    for entry in config.entries {
        write!(
            summary,
            ";entry={},{},{},{},{}",
            entry.id,
            entry.mode.as_str(),
            entry.slot,
            entry.manifest,
            entry.manifest_max_bytes
        )
        .map_err(|_| "transport")?;
    }
    Ok(summary)
}

fn size_request(value: &str) -> Result<String, &'static str> {
    let (configured, observed) = value
        .strip_prefix("S:")
        .and_then(|rest| rest.split_once(':'))
        .ok_or("transport")?;
    let configured = configured.parse::<u64>().map_err(|_| "transport")?;
    let observed = observed.parse::<u64>().map_err(|_| "transport")?;
    poole_boot_config::validate_manifest_size(configured, observed)
        .map_err(|error| error.code())?;
    Ok("OK".to_owned())
}

fn main() {
    for line in io::stdin().lock().lines() {
        let result = line.map_err(|_| "transport").and_then(|value| {
            if value.starts_with("P:") {
                parse_request(&value)
            } else if value.starts_with("S:") {
                size_request(&value)
            } else {
                Err("transport")
            }
        });
        match result {
            Ok(summary) => println!("{summary}"),
            Err(code) => println!("ERR:{code}"),
        }
    }
}
