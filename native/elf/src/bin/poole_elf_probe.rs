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

fn encode_hex(bytes: &[u8]) -> String {
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        write!(output, "{byte:02x}").expect("writing to String cannot fail");
    }
    output
}

fn parse_u64_hex(value: &str) -> Result<u64, &'static str> {
    u64::from_str_radix(value, 16).map_err(|_| "transport")
}

fn append_ranges(
    output: &mut String,
    plans: impl IntoIterator<Item = (u32, u32, poole_elf::Permissions)>,
) {
    let mut first = true;
    for (offset, size, permissions) in plans {
        if !first {
            output.push(',');
        }
        first = false;
        write!(output, "{offset:08x}+{size:08x}:{}", permissions.code())
            .expect("writing to String cannot fail");
    }
}

fn summary(plan: poole_elf::ImagePlan, loaded: &[u8]) -> String {
    let mut output = format!(
        "OK;file_size={};image_size={};entry_offset={:08x};entry_virtual={:016x};entry_physical={:016x};physical_base={:016x};virtual_base={:016x};relocations={};relro={:08x}+{:08x};segments=",
        plan.file_size,
        plan.image_size,
        plan.entry_offset,
        plan.entry_virtual,
        plan.entry_physical,
        plan.physical_base,
        plan.virtual_base,
        plan.relocation_count,
        plan.relro_offset,
        plan.relro_size,
    );
    append_ranges(
        &mut output,
        plan.segments.iter().map(|segment| {
            (
                segment.virtual_offset,
                segment.memory_size,
                segment.permissions,
            )
        }),
    );
    output.push_str(";mappings=");
    append_ranges(
        &mut output,
        plan.mappings.iter().map(|mapping| {
            (
                mapping.virtual_offset,
                mapping.memory_size,
                mapping.permissions,
            )
        }),
    );
    write!(
        output,
        ";fnv64={:016x}",
        poole_elf::fnv1a64(&loaded[..plan.image_size as usize])
    )
    .expect("writing to String cannot fail");
    output
}

fn load_request(value: &str, include_bytes: bool) -> Result<String, &'static str> {
    let mut fields = value.splitn(5, ':');
    let command = fields.next().ok_or("transport")?;
    if !matches!((command, include_bytes), ("L", false) | ("B", true)) {
        return Err("transport");
    }
    let virtual_base = parse_u64_hex(fields.next().ok_or("transport")?)?;
    let physical_base = parse_u64_hex(fields.next().ok_or("transport")?)?;
    let capacity = fields
        .next()
        .ok_or("transport")?
        .parse::<usize>()
        .map_err(|_| "transport")?;
    if capacity > poole_elf::MAX_IMAGE_BYTES as usize {
        return Err("transport");
    }
    let bytes = decode_hex(fields.next().ok_or("transport")?).map_err(|_| "transport")?;
    let mut destination = vec![0xa5; capacity];
    let plan = poole_elf::load(&bytes, physical_base, virtual_base, &mut destination)
        .map_err(|error| error.code())?;
    if include_bytes {
        Ok(format!(
            "OKBYTES:{}",
            encode_hex(&destination[..plan.image_size as usize])
        ))
    } else {
        Ok(summary(plan, &destination))
    }
}

fn mutation_request(value: &str, cached: &[u8]) -> Result<String, &'static str> {
    let mut fields = value.splitn(6, ':');
    if fields.next() != Some("M") || cached.is_empty() {
        return Err("transport");
    }
    let virtual_base = parse_u64_hex(fields.next().ok_or("transport")?)?;
    let physical_base = parse_u64_hex(fields.next().ok_or("transport")?)?;
    let capacity = fields
        .next()
        .ok_or("transport")?
        .parse::<usize>()
        .map_err(|_| "transport")?;
    let length = fields
        .next()
        .ok_or("transport")?
        .parse::<usize>()
        .map_err(|_| "transport")?;
    let patches = fields.next().ok_or("transport")?;
    if capacity > poole_elf::MAX_IMAGE_BYTES as usize || length > cached.len() {
        return Err("transport");
    }
    let mut bytes = cached[..length].to_vec();
    if patches != "-" {
        for patch in patches.split(',') {
            let (offset, value) = patch.split_once('=').ok_or("transport")?;
            let offset = usize::from_str_radix(offset, 16).map_err(|_| "transport")?;
            let value = u8::from_str_radix(value, 16).map_err(|_| "transport")?;
            let target = bytes.get_mut(offset).ok_or("transport")?;
            *target = value;
        }
    }
    let mut destination = vec![0xa5; capacity];
    let plan = poole_elf::load(&bytes, physical_base, virtual_base, &mut destination)
        .map_err(|error| error.code())?;
    Ok(summary(plan, &destination))
}

fn main() {
    let mut cached = Vec::new();
    for line in io::stdin().lock().lines() {
        let result = line.map_err(|_| "transport").and_then(|value| {
            if let Some(encoded) = value.strip_prefix("C:") {
                cached = decode_hex(encoded).map_err(|_| "transport")?;
                Ok("OKCACHE".to_owned())
            } else if value.starts_with("M:") {
                mutation_request(&value, &cached)
            } else {
                load_request(&value, value.starts_with("B:"))
            }
        });
        match result {
            Ok(value) => println!("{value}"),
            Err(code) => println!("ERR:{code}"),
        }
    }
}
