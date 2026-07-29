#![no_std]
#![deny(warnings)]

pub const CONTRACT_ID: &str = "PBC1";
pub const MAGIC: &str = "POOLEOS-BOOTCFG/1.0";
pub const END_MARKER: &str = "end=PBC1";
pub const MAX_CONFIG_BYTES: usize = 16 * 1024;
pub const MAX_LINE_BYTES: usize = 320;
pub const MAX_LINES: usize = 64;
pub const MAX_ENTRIES: usize = 8;
pub const MAX_IDENTIFIER_BYTES: usize = 31;
pub const MAX_MANIFEST_PATH_BYTES: usize = 240;
pub const MAX_MANIFEST_BYTES: u64 = 1024 * 1024;
pub const MAX_TIMEOUT_MS: u64 = 30_000;
pub const MAX_BOOT_ATTEMPTS: u64 = 8;
pub const MAX_SLOT: u64 = 4;
pub const MANIFEST_ROOT: &str = "\\EFI\\POOLEOS\\";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Empty,
    ConfigTooLarge,
    MissingFinalLf,
    Character,
    EmptyLine,
    LineTooLong,
    TooManyLines,
    Magic,
    Version,
    Syntax,
    DuplicateKey,
    UnknownKey,
    KeyOrder,
    Truncated,
    EndMarker,
    Number,
    NumberCanonical,
    NumericOverflow,
    Range,
    Identifier,
    EntryOrder,
    Mode,
    Path,
    DefaultEntry,
    OutputCapacity,
    ArtifactSize,
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::Empty => "empty",
            Self::ConfigTooLarge => "config_too_large",
            Self::MissingFinalLf => "missing_final_lf",
            Self::Character => "character",
            Self::EmptyLine => "empty_line",
            Self::LineTooLong => "line_too_long",
            Self::TooManyLines => "too_many_lines",
            Self::Magic => "magic",
            Self::Version => "version",
            Self::Syntax => "syntax",
            Self::DuplicateKey => "duplicate_key",
            Self::UnknownKey => "unknown_key",
            Self::KeyOrder => "key_order",
            Self::Truncated => "truncated",
            Self::EndMarker => "end_marker",
            Self::Number => "number",
            Self::NumberCanonical => "number_canonical",
            Self::NumericOverflow => "numeric_overflow",
            Self::Range => "range",
            Self::Identifier => "identifier",
            Self::EntryOrder => "entry_order",
            Self::Mode => "mode",
            Self::Path => "path",
            Self::DefaultEntry => "default_entry",
            Self::OutputCapacity => "output_capacity",
            Self::ArtifactSize => "artifact_size",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BootMode {
    Normal,
    Safe,
    Previous,
    Recovery,
    Diagnostic,
}

impl BootMode {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Normal => "normal",
            Self::Safe => "safe",
            Self::Previous => "previous",
            Self::Recovery => "recovery",
            Self::Diagnostic => "diagnostic",
        }
    }

    fn parse(value: &str) -> Result<Self, Error> {
        match value {
            "normal" => Ok(Self::Normal),
            "safe" => Ok(Self::Safe),
            "previous" => Ok(Self::Previous),
            "recovery" => Ok(Self::Recovery),
            "diagnostic" => Ok(Self::Diagnostic),
            _ => Err(Error::Mode),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Entry<'input> {
    pub id: &'input str,
    pub mode: BootMode,
    pub slot: u8,
    pub manifest: &'input str,
    pub manifest_max_bytes: u32,
}

impl Entry<'static> {
    pub const EMPTY: Self = Self {
        id: "",
        mode: BootMode::Normal,
        slot: 1,
        manifest: "",
        manifest_max_bytes: 1,
    };
}

#[derive(Debug, Eq, PartialEq)]
pub struct BootConfig<'input, 'entries> {
    pub default_entry: &'input str,
    pub timeout_ms: u32,
    pub boot_attempt_limit: u8,
    pub entries: &'entries [Entry<'input>],
}

#[derive(Clone, Copy)]
struct Lines<'a> {
    bytes: &'a [u8],
    offset: usize,
}

impl<'a> Lines<'a> {
    const fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, offset: 0 }
    }
}

impl<'a> Iterator for Lines<'a> {
    type Item = &'a [u8];

    fn next(&mut self) -> Option<Self::Item> {
        if self.offset >= self.bytes.len() {
            return None;
        }
        let start = self.offset;
        while self.offset < self.bytes.len() && self.bytes[self.offset] != b'\n' {
            self.offset += 1;
        }
        let end = self.offset;
        if self.offset < self.bytes.len() {
            self.offset += 1;
        }
        Some(&self.bytes[start..end])
    }
}

fn line_at(bytes: &[u8], index: usize) -> Result<&str, Error> {
    let line = Lines::new(bytes).nth(index).ok_or(Error::Truncated)?;
    core::str::from_utf8(line).map_err(|_| Error::Character)
}

fn split_key_value(line: &str) -> Result<(&str, &str), Error> {
    let (key, value) = line.split_once('=').ok_or(Error::Syntax)?;
    if key.is_empty() || value.is_empty() || value.contains('=') {
        return Err(Error::Syntax);
    }
    Ok((key, value))
}

fn parse_number(value: &str) -> Result<u64, Error> {
    if value.is_empty() || !value.as_bytes().iter().all(u8::is_ascii_digit) {
        return Err(Error::Number);
    }
    if value.len() > 1 && value.starts_with('0') {
        return Err(Error::NumberCanonical);
    }
    let mut result = 0u64;
    for byte in value.bytes() {
        result = result
            .checked_mul(10)
            .and_then(|number| number.checked_add(u64::from(byte - b'0')))
            .ok_or(Error::NumericOverflow)?;
    }
    Ok(result)
}

fn parse_range(value: &str, minimum: u64, maximum: u64) -> Result<u64, Error> {
    let number = parse_number(value)?;
    if !(minimum..=maximum).contains(&number) {
        return Err(Error::Range);
    }
    Ok(number)
}

fn valid_identifier(value: &str) -> bool {
    let bytes = value.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= MAX_IDENTIFIER_BYTES
        && bytes[0].is_ascii_lowercase()
        && bytes[1..]
            .iter()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || *byte == b'_')
}

fn validate_manifest_path(value: &str) -> Result<(), Error> {
    if value.len() > MAX_MANIFEST_PATH_BYTES || !value.starts_with(MANIFEST_ROOT) {
        return Err(Error::Path);
    }
    let relative = &value[MANIFEST_ROOT.len()..];
    if relative.is_empty() || relative.contains('/') || !relative.ends_with(".PBM") {
        return Err(Error::Path);
    }
    let mut components = relative.split('\\').peekable();
    while let Some(component) = components.next() {
        if component.is_empty() || component == "." || component == ".." || component.len() > 64 {
            return Err(Error::Path);
        }
        let body = if components.peek().is_none() {
            component.strip_suffix(".PBM").ok_or(Error::Path)?
        } else {
            component
        };
        if body.is_empty()
            || !body.as_bytes()[0].is_ascii_uppercase()
            || !body.as_bytes().iter().all(|byte| {
                byte.is_ascii_uppercase() || byte.is_ascii_digit() || *byte == b'_' || *byte == b'-'
            })
        {
            return Err(Error::Path);
        }
    }
    Ok(())
}

enum KeyClass {
    Known,
    InvalidIdentifier,
    Unknown,
}

fn classify_key(key: &str) -> KeyClass {
    if matches!(
        key,
        "entry_count" | "default_entry" | "timeout_ms" | "boot_attempt_limit"
    ) {
        return KeyClass::Known;
    }
    let Some(rest) = key.strip_prefix("entry.") else {
        return KeyClass::Unknown;
    };
    let Some((identifier, field)) = rest.split_once('.') else {
        return KeyClass::Unknown;
    };
    if !valid_identifier(identifier) {
        return KeyClass::InvalidIdentifier;
    }
    if matches!(field, "mode" | "slot" | "manifest" | "manifest_max_bytes") {
        KeyClass::Known
    } else {
        KeyClass::Unknown
    }
}

fn expect_value<'a>(bytes: &'a [u8], index: usize, expected_key: &str) -> Result<&'a str, Error> {
    let (key, value) = split_key_value(line_at(bytes, index)?)?;
    if key == expected_key {
        return Ok(value);
    }
    match classify_key(key) {
        KeyClass::Known => Err(Error::KeyOrder),
        KeyClass::InvalidIdentifier => Err(Error::Identifier),
        KeyClass::Unknown => Err(Error::UnknownKey),
    }
}

fn entry_key<'a>(key: &'a str, expected_field: &str) -> Result<&'a str, Error> {
    let rest = key
        .strip_prefix("entry.")
        .ok_or_else(|| match classify_key(key) {
            KeyClass::Known => Error::KeyOrder,
            KeyClass::InvalidIdentifier => Error::Identifier,
            KeyClass::Unknown => Error::UnknownKey,
        })?;
    let (identifier, field) = rest.split_once('.').ok_or(Error::UnknownKey)?;
    if !valid_identifier(identifier) {
        return Err(Error::Identifier);
    }
    if !matches!(field, "mode" | "slot" | "manifest" | "manifest_max_bytes") {
        return Err(Error::UnknownKey);
    }
    if field != expected_field {
        return Err(Error::KeyOrder);
    }
    Ok(identifier)
}

fn validate_lexical(bytes: &[u8]) -> Result<usize, Error> {
    if bytes.is_empty() {
        return Err(Error::Empty);
    }
    if bytes.len() > MAX_CONFIG_BYTES {
        return Err(Error::ConfigTooLarge);
    }
    if !bytes.ends_with(b"\n") {
        return Err(Error::MissingFinalLf);
    }
    for byte in bytes {
        if *byte != b'\n' && !(b'!'..=b'~').contains(byte) {
            return Err(Error::Character);
        }
    }
    let mut count = 0usize;
    for line in Lines::new(bytes) {
        if line.is_empty() {
            return Err(Error::EmptyLine);
        }
        if line.len() > MAX_LINE_BYTES {
            return Err(Error::LineTooLong);
        }
        count = count.checked_add(1).ok_or(Error::TooManyLines)?;
        if count > MAX_LINES {
            return Err(Error::TooManyLines);
        }
    }
    Ok(count)
}

fn validate_duplicate_keys(bytes: &[u8], line_count: usize) -> Result<(), Error> {
    if line_count < 2 {
        return Err(Error::Truncated);
    }
    for left_index in 1..line_count - 1 {
        let (left, _) = split_key_value(line_at(bytes, left_index)?)?;
        for right_index in left_index + 1..line_count - 1 {
            let (right, _) = split_key_value(line_at(bytes, right_index)?)?;
            if left == right {
                return Err(Error::DuplicateKey);
            }
        }
    }
    Ok(())
}

pub fn parse<'input, 'entries>(
    bytes: &'input [u8],
    storage: &'entries mut [Entry<'input>],
) -> Result<BootConfig<'input, 'entries>, Error> {
    let line_count = validate_lexical(bytes)?;
    let first = line_at(bytes, 0)?;
    if first != MAGIC {
        return if first.starts_with("POOLEOS-BOOTCFG/") {
            Err(Error::Version)
        } else {
            Err(Error::Magic)
        };
    }
    if line_count < 6 {
        return Err(Error::Truncated);
    }
    if line_at(bytes, line_count - 1)? != END_MARKER {
        return Err(Error::EndMarker);
    }
    validate_duplicate_keys(bytes, line_count)?;

    let entry_count = parse_range(
        expect_value(bytes, 1, "entry_count")?,
        1,
        MAX_ENTRIES as u64,
    )? as usize;
    let expected_lines = 6usize
        .checked_add(entry_count.checked_mul(4).ok_or(Error::NumericOverflow)?)
        .ok_or(Error::NumericOverflow)?;
    if line_count < expected_lines {
        return Err(Error::Truncated);
    }
    if line_count > expected_lines {
        let (key, _) = split_key_value(line_at(bytes, expected_lines - 1)?)?;
        return match classify_key(key) {
            KeyClass::Known => Err(Error::KeyOrder),
            KeyClass::InvalidIdentifier => Err(Error::Identifier),
            KeyClass::Unknown => Err(Error::UnknownKey),
        };
    }
    if storage.len() < entry_count {
        return Err(Error::OutputCapacity);
    }

    let default_entry = expect_value(bytes, 2, "default_entry")?;
    if !valid_identifier(default_entry) {
        return Err(Error::Identifier);
    }
    let timeout_ms = parse_range(expect_value(bytes, 3, "timeout_ms")?, 0, MAX_TIMEOUT_MS)? as u32;
    let boot_attempt_limit = parse_range(
        expect_value(bytes, 4, "boot_attempt_limit")?,
        1,
        MAX_BOOT_ATTEMPTS,
    )? as u8;

    let mut previous_id = "";
    let mut default_found = false;
    for (entry_index, slot) in storage[..entry_count].iter_mut().enumerate() {
        let base = 5 + entry_index * 4;
        let (mode_key, mode_value) = split_key_value(line_at(bytes, base)?)?;
        let id = entry_key(mode_key, "mode")?;
        if !previous_id.is_empty() && id <= previous_id {
            return Err(Error::EntryOrder);
        }
        previous_id = id;

        let (slot_key, slot_value) = split_key_value(line_at(bytes, base + 1)?)?;
        let (manifest_key, manifest_value) = split_key_value(line_at(bytes, base + 2)?)?;
        let (limit_key, limit_value) = split_key_value(line_at(bytes, base + 3)?)?;
        if entry_key(slot_key, "slot")? != id
            || entry_key(manifest_key, "manifest")? != id
            || entry_key(limit_key, "manifest_max_bytes")? != id
        {
            return Err(Error::KeyOrder);
        }
        validate_manifest_path(manifest_value)?;
        let manifest_max_bytes = parse_range(limit_value, 1, MAX_MANIFEST_BYTES)? as u32;
        *slot = Entry {
            id,
            mode: BootMode::parse(mode_value)?,
            slot: parse_range(slot_value, 1, MAX_SLOT)? as u8,
            manifest: manifest_value,
            manifest_max_bytes,
        };
        default_found |= id == default_entry;
    }
    if !default_found {
        return Err(Error::DefaultEntry);
    }
    Ok(BootConfig {
        default_entry,
        timeout_ms,
        boot_attempt_limit,
        entries: &storage[..entry_count],
    })
}

pub fn validate_manifest_size(configured_limit: u64, observed_size: u64) -> Result<(), Error> {
    if configured_limit == 0
        || configured_limit > MAX_MANIFEST_BYTES
        || observed_size == 0
        || observed_size > configured_limit
        || observed_size > MAX_MANIFEST_BYTES
    {
        return Err(Error::ArtifactSize);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;
    use std::vec;

    const MINIMAL: &[u8] = b"POOLEOS-BOOTCFG/1.0\nentry_count=1\ndefault_entry=normal\ntimeout_ms=0\nboot_attempt_limit=3\nentry.normal.mode=normal\nentry.normal.slot=1\nentry.normal.manifest=\\EFI\\POOLEOS\\MANIFEST_A.PBM\nentry.normal.manifest_max_bytes=65536\nend=PBC1\n";

    fn parse_with_capacity(bytes: &[u8], capacity: usize) -> Result<(), Error> {
        let mut storage = vec![Entry::EMPTY; capacity];
        parse(bytes, &mut storage).map(|_| ())
    }

    #[test]
    fn minimal_contract_parses_without_allocation() {
        let mut storage = [Entry::EMPTY; MAX_ENTRIES];
        let config = parse(MINIMAL, &mut storage).unwrap();
        assert_eq!(config.default_entry, "normal");
        assert_eq!(config.timeout_ms, 0);
        assert_eq!(config.boot_attempt_limit, 3);
        assert_eq!(config.entries.len(), 1);
        assert_eq!(config.entries[0].mode, BootMode::Normal);
        assert_eq!(config.entries[0].manifest_max_bytes, 65_536);
    }

    #[test]
    fn final_lf_and_ascii_are_mandatory() {
        assert_eq!(
            parse_with_capacity(&MINIMAL[..MINIMAL.len() - 1], 8),
            Err(Error::MissingFinalLf)
        );
        let mut changed = MINIMAL.to_vec();
        changed[0] = 0;
        assert_eq!(parse_with_capacity(&changed, 8), Err(Error::Character));
    }

    #[test]
    fn incompatible_version_fails_closed() {
        let changed = MINIMAL.replacen(b"/1.0", b"/2.0", 1);
        assert_eq!(parse_with_capacity(&changed, 8), Err(Error::Version));
    }

    #[test]
    fn duplicate_and_unknown_keys_are_distinct() {
        let duplicate = MINIMAL.replacen(b"timeout_ms=0", b"entry_count=0", 1);
        assert_eq!(parse_with_capacity(&duplicate, 8), Err(Error::DuplicateKey));
        let unknown = MINIMAL.replacen(b"timeout_ms=0", b"delay_ms=0", 1);
        assert_eq!(parse_with_capacity(&unknown, 8), Err(Error::UnknownKey));
    }

    #[test]
    fn noncanonical_and_overflowing_numbers_fail() {
        let leading = MINIMAL.replacen(b"timeout_ms=0", b"timeout_ms=00", 1);
        assert_eq!(
            parse_with_capacity(&leading, 8),
            Err(Error::NumberCanonical)
        );
        let overflow = MINIMAL.replacen(b"timeout_ms=0", b"timeout_ms=18446744073709551616", 1);
        assert_eq!(
            parse_with_capacity(&overflow, 8),
            Err(Error::NumericOverflow)
        );
    }

    #[test]
    fn ranges_are_bounded() {
        let timeout = MINIMAL.replacen(b"timeout_ms=0", b"timeout_ms=30001", 1);
        assert_eq!(parse_with_capacity(&timeout, 8), Err(Error::Range));
        let slot = MINIMAL.replacen(b"slot=1", b"slot=5", 1);
        assert_eq!(parse_with_capacity(&slot, 8), Err(Error::Range));
    }

    #[test]
    fn path_traversal_and_wrong_root_are_rejected() {
        let traversal = MINIMAL.replacen(b"MANIFEST_A.PBM", b"..\\MANIFEST_A.PBM", 1);
        assert_eq!(parse_with_capacity(&traversal, 8), Err(Error::Path));
        let root = MINIMAL.replacen(b"\\EFI\\POOLEOS", b"\\EFI\\OTHER", 1);
        assert_eq!(parse_with_capacity(&root, 8), Err(Error::Path));
    }

    #[test]
    fn output_capacity_is_explicit() {
        assert_eq!(parse_with_capacity(MINIMAL, 0), Err(Error::OutputCapacity));
    }

    #[test]
    fn missing_default_entry_is_rejected() {
        let changed = MINIMAL.replacen(b"default_entry=normal", b"default_entry=recovery", 1);
        assert_eq!(parse_with_capacity(&changed, 8), Err(Error::DefaultEntry));
    }

    #[test]
    fn entry_mode_is_closed() {
        let changed = MINIMAL.replacen(b"mode=normal", b"mode=fast", 1);
        assert_eq!(parse_with_capacity(&changed, 8), Err(Error::Mode));
    }

    #[test]
    fn artifact_size_is_nonzero_and_bounded() {
        assert_eq!(validate_manifest_size(1024, 1024), Ok(()));
        assert_eq!(validate_manifest_size(1024, 1025), Err(Error::ArtifactSize));
        assert_eq!(validate_manifest_size(0, 1), Err(Error::ArtifactSize));
        assert_eq!(validate_manifest_size(1024, 0), Err(Error::ArtifactSize));
    }

    #[test]
    fn error_codes_are_stable_ascii() {
        assert_eq!(Error::DuplicateKey.code(), "duplicate_key");
        assert_eq!(Error::ArtifactSize.code(), "artifact_size");
    }

    trait ReplaceBytes {
        fn replacen(&self, from: &[u8], to: &[u8], count: usize) -> std::vec::Vec<u8>;
    }

    impl ReplaceBytes for [u8] {
        fn replacen(&self, from: &[u8], to: &[u8], count: usize) -> std::vec::Vec<u8> {
            let mut output = std::vec::Vec::new();
            let mut remainder = self;
            let mut replaced = 0;
            while replaced < count {
                let Some(position) = remainder
                    .windows(from.len())
                    .position(|window| window == from)
                else {
                    break;
                };
                output.extend_from_slice(&remainder[..position]);
                output.extend_from_slice(to);
                remainder = &remainder[position + from.len()..];
                replaced += 1;
            }
            output.extend_from_slice(remainder);
            output
        }
    }
}
