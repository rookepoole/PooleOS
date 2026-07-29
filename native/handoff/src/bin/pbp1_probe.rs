use std::io::{self, BufRead};

fn decode_hex(line: &str) -> Result<Vec<u8>, ()> {
    let value = line.trim();
    if !value.len().is_multiple_of(2) {
        return Err(());
    }
    let mut bytes = Vec::with_capacity(value.len() / 2);
    for pair in value.as_bytes().chunks_exact(2) {
        let text = std::str::from_utf8(pair).map_err(|_| ())?;
        bytes.push(u8::from_str_radix(text, 16).map_err(|_| ())?);
    }
    Ok(bytes)
}

fn main() {
    for line in io::stdin().lock().lines() {
        match line.map_err(|_| ()).and_then(|value| {
            let (kernel_profile, encoded) = value
                .strip_prefix("K:")
                .map_or((false, value.as_str()), |rest| (true, rest));
            let bytes = decode_hex(encoded)?;
            let handoff = poole_handoff::decode(&bytes).map_err(|_| ())?;
            if kernel_profile {
                poole_handoff::validate_kernel_entry_profile(&handoff).map_err(|_| ())?;
            }
            Ok(())
        }) {
            Ok(()) => println!("OK"),
            Err(()) => println!("ERR"),
        }
    }
}
