#![no_std]
#![deny(warnings)]

use sha2::{Digest, Sha256};

pub const CONTRACT_ID: &str = "PSM1";
pub const MAGIC: &str = "POOLEOS-SYSTEM-MANIFEST/1.0";
pub const END_MARKER: &str = "end=PSM1";
pub const MANIFEST_ROOT: &str = "\\EFI\\POOLEOS\\";
pub const MAX_MANIFEST_BYTES: usize = 64 * 1024;
pub const MAX_LINE_BYTES: usize = 384;
pub const MAX_LINES: usize = 192;
pub const MAX_ARTIFACTS: usize = 16;
pub const MAX_IDENTIFIER_BYTES: usize = 31;
pub const MAX_MANIFEST_ID_BYTES: usize = 63;
pub const MAX_PATH_BYTES: usize = 240;
pub const MAX_FORMAT_BYTES: usize = 16;
pub const MAX_ENTRY_CONTRACT_BYTES: usize = 16;
pub const MAX_FILE_BYTES: u64 = 64 * 1024 * 1024;
pub const MAX_IMAGE_BYTES: u64 = 512 * 1024 * 1024;
pub const MAX_SLOT: u64 = 4;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Empty,
    ManifestTooLarge,
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
    ArtifactOrder,
    ArtifactType,
    Format,
    Path,
    Digest,
    EntryContract,
    OutputCapacity,
    DuplicatePath,
    KernelCount,
    VersionFloor,
    Size,
    Binding,
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::Empty => "manifest_empty",
            Self::ManifestTooLarge => "manifest_too_large",
            Self::MissingFinalLf => "manifest_missing_final_lf",
            Self::Character => "manifest_character",
            Self::EmptyLine => "manifest_empty_line",
            Self::LineTooLong => "manifest_line_too_long",
            Self::TooManyLines => "manifest_too_many_lines",
            Self::Magic => "manifest_magic",
            Self::Version => "manifest_version",
            Self::Syntax => "manifest_syntax",
            Self::DuplicateKey => "manifest_duplicate_key",
            Self::UnknownKey => "manifest_unknown_key",
            Self::KeyOrder => "manifest_key_order",
            Self::Truncated => "manifest_truncated",
            Self::EndMarker => "manifest_end_marker",
            Self::Number => "manifest_number",
            Self::NumberCanonical => "manifest_number_canonical",
            Self::NumericOverflow => "manifest_numeric_overflow",
            Self::Range => "manifest_range",
            Self::Identifier => "manifest_identifier",
            Self::ArtifactOrder => "manifest_artifact_order",
            Self::ArtifactType => "manifest_artifact_type",
            Self::Format => "manifest_format",
            Self::Path => "manifest_path",
            Self::Digest => "manifest_digest",
            Self::EntryContract => "manifest_entry_contract",
            Self::OutputCapacity => "manifest_output_capacity",
            Self::DuplicatePath => "manifest_duplicate_path",
            Self::KernelCount => "manifest_kernel_count",
            Self::VersionFloor => "manifest_version_floor",
            Self::Size => "manifest_size",
            Self::Binding => "manifest_binding",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ArtifactKind {
    Kernel,
    InitialSystem,
    Recovery,
    Symbols,
    Microcode,
    Firmware,
    Policy,
    PooleGlyph,
}

impl ArtifactKind {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Kernel => "kernel",
            Self::InitialSystem => "initial_system",
            Self::Recovery => "recovery",
            Self::Symbols => "symbols",
            Self::Microcode => "microcode",
            Self::Firmware => "firmware",
            Self::Policy => "policy",
            Self::PooleGlyph => "pooleglyph",
        }
    }

    fn parse(value: &str) -> Result<Self, Error> {
        match value {
            "kernel" => Ok(Self::Kernel),
            "initial_system" => Ok(Self::InitialSystem),
            "recovery" => Ok(Self::Recovery),
            "symbols" => Ok(Self::Symbols),
            "microcode" => Ok(Self::Microcode),
            "firmware" => Ok(Self::Firmware),
            "policy" => Ok(Self::Policy),
            "pooleglyph" => Ok(Self::PooleGlyph),
            _ => Err(Error::ArtifactType),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Artifact<'input> {
    pub id: &'input str,
    pub kind: ArtifactKind,
    pub format: &'input str,
    pub version: u64,
    pub path: &'input str,
    pub file_bytes: u64,
    pub image_bytes: u64,
    pub sha256: [u8; 32],
    pub entry_contract: &'input str,
}

impl Artifact<'static> {
    pub const EMPTY: Self = Self {
        id: "",
        kind: ArtifactKind::Kernel,
        format: "",
        version: 1,
        path: "",
        file_bytes: 1,
        image_bytes: 1,
        sha256: [0; 32],
        entry_contract: "",
    };
}

#[derive(Debug, Eq, PartialEq)]
pub struct SystemManifest<'input, 'artifacts> {
    pub manifest_id: &'input str,
    pub slot: u8,
    pub manifest_version: u64,
    pub minimum_secure_version: u64,
    pub artifacts: &'artifacts [Artifact<'input>],
}

impl<'input, 'artifacts> SystemManifest<'input, 'artifacts> {
    pub fn kernel(&self) -> Result<&Artifact<'input>, Error> {
        let mut result = None;
        for artifact in self.artifacts {
            if artifact.kind == ArtifactKind::Kernel {
                if result.is_some() {
                    return Err(Error::KernelCount);
                }
                result = Some(artifact);
            }
        }
        result.ok_or(Error::KernelCount)
    }
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

fn valid_lower_identifier(value: &str) -> bool {
    let bytes = value.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= MAX_IDENTIFIER_BYTES
        && bytes[0].is_ascii_lowercase()
        && bytes[1..]
            .iter()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || *byte == b'_')
}

fn valid_upper_identifier(value: &str, maximum: usize) -> bool {
    let bytes = value.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= maximum
        && bytes[0].is_ascii_uppercase()
        && bytes[1..].iter().all(|byte| {
            byte.is_ascii_uppercase() || byte.is_ascii_digit() || *byte == b'_' || *byte == b'-'
        })
}

fn validate_path(value: &str) -> Result<(), Error> {
    if value.len() > MAX_PATH_BYTES || !value.starts_with(MANIFEST_ROOT) {
        return Err(Error::Path);
    }
    let relative = &value[MANIFEST_ROOT.len()..];
    if relative.is_empty() || relative.contains('/') {
        return Err(Error::Path);
    }
    let mut components = relative.split('\\').peekable();
    while let Some(component) = components.next() {
        if component.is_empty() || component == "." || component == ".." || component.len() > 64 {
            return Err(Error::Path);
        }
        let last = components.peek().is_none();
        let mut dot_count = 0usize;
        for (index, byte) in component.bytes().enumerate() {
            if byte == b'.' {
                dot_count += 1;
                if !last || index == 0 || index + 1 == component.len() {
                    return Err(Error::Path);
                }
            } else if !(byte.is_ascii_uppercase()
                || byte.is_ascii_digit()
                || byte == b'_'
                || byte == b'-')
            {
                return Err(Error::Path);
            }
        }
        if last && dot_count != 1 {
            return Err(Error::Path);
        }
        if !last && dot_count != 0 {
            return Err(Error::Path);
        }
    }
    Ok(())
}

fn parse_digest(value: &str) -> Result<[u8; 32], Error> {
    if value.len() != 64 {
        return Err(Error::Digest);
    }
    let bytes = value.as_bytes();
    let mut digest = [0u8; 32];
    let mut index = 0usize;
    while index < digest.len() {
        let high = hex_nibble(bytes[index * 2])?;
        let low = hex_nibble(bytes[index * 2 + 1])?;
        digest[index] = high << 4 | low;
        index += 1;
    }
    Ok(digest)
}

fn hex_nibble(byte: u8) -> Result<u8, Error> {
    match byte {
        b'0'..=b'9' => Ok(byte - b'0'),
        b'A'..=b'F' => Ok(byte - b'A' + 10),
        _ => Err(Error::Digest),
    }
}

enum KeyClass {
    Known,
    InvalidIdentifier,
    Unknown,
}

fn classify_key(key: &str) -> KeyClass {
    if matches!(
        key,
        "manifest_id" | "slot" | "manifest_version" | "minimum_secure_version" | "artifact_count"
    ) {
        return KeyClass::Known;
    }
    let Some(rest) = key.strip_prefix("artifact.") else {
        return KeyClass::Unknown;
    };
    let Some((identifier, field)) = rest.split_once('.') else {
        return KeyClass::Unknown;
    };
    if !valid_lower_identifier(identifier) {
        return KeyClass::InvalidIdentifier;
    }
    if matches!(
        field,
        "type"
            | "format"
            | "version"
            | "path"
            | "file_bytes"
            | "image_bytes"
            | "sha256"
            | "entry_contract"
    ) {
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

fn artifact_key<'a>(key: &'a str, expected_field: &str) -> Result<&'a str, Error> {
    let rest = key
        .strip_prefix("artifact.")
        .ok_or_else(|| match classify_key(key) {
            KeyClass::Known => Error::KeyOrder,
            KeyClass::InvalidIdentifier => Error::Identifier,
            KeyClass::Unknown => Error::UnknownKey,
        })?;
    let (identifier, field) = rest.split_once('.').ok_or(Error::UnknownKey)?;
    if !valid_lower_identifier(identifier) {
        return Err(Error::Identifier);
    }
    if !matches!(
        field,
        "type"
            | "format"
            | "version"
            | "path"
            | "file_bytes"
            | "image_bytes"
            | "sha256"
            | "entry_contract"
    ) {
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
    if bytes.len() > MAX_MANIFEST_BYTES {
        return Err(Error::ManifestTooLarge);
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

pub fn parse<'input, 'artifacts>(
    bytes: &'input [u8],
    storage: &'artifacts mut [Artifact<'input>],
) -> Result<SystemManifest<'input, 'artifacts>, Error> {
    let line_count = validate_lexical(bytes)?;
    let first = line_at(bytes, 0)?;
    if first != MAGIC {
        return if first.starts_with("POOLEOS-SYSTEM-MANIFEST/") {
            Err(Error::Version)
        } else {
            Err(Error::Magic)
        };
    }
    if line_count < 15 {
        return Err(Error::Truncated);
    }
    if line_at(bytes, line_count - 1)? != END_MARKER {
        return Err(Error::EndMarker);
    }
    validate_duplicate_keys(bytes, line_count)?;

    let manifest_id = expect_value(bytes, 1, "manifest_id")?;
    if !valid_upper_identifier(manifest_id, MAX_MANIFEST_ID_BYTES) {
        return Err(Error::Identifier);
    }
    let slot = parse_range(expect_value(bytes, 2, "slot")?, 1, MAX_SLOT)? as u8;
    let manifest_version = parse_range(expect_value(bytes, 3, "manifest_version")?, 1, u64::MAX)?;
    let minimum_secure_version = parse_range(
        expect_value(bytes, 4, "minimum_secure_version")?,
        0,
        u64::MAX,
    )?;
    if minimum_secure_version > manifest_version {
        return Err(Error::VersionFloor);
    }
    let artifact_count = parse_range(
        expect_value(bytes, 5, "artifact_count")?,
        1,
        MAX_ARTIFACTS as u64,
    )? as usize;
    let expected_lines = 7usize
        .checked_add(
            artifact_count
                .checked_mul(8)
                .ok_or(Error::NumericOverflow)?,
        )
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
    if storage.len() < artifact_count {
        return Err(Error::OutputCapacity);
    }

    let mut previous_id = "";
    let mut kernel_count = 0usize;
    for artifact_index in 0..artifact_count {
        let base = 6 + artifact_index * 8;
        let (type_key, type_value) = split_key_value(line_at(bytes, base)?)?;
        let id = artifact_key(type_key, "type")?;
        if !previous_id.is_empty() && id <= previous_id {
            return Err(Error::ArtifactOrder);
        }
        previous_id = id;

        let (format_key, format_value) = split_key_value(line_at(bytes, base + 1)?)?;
        let (version_key, version_value) = split_key_value(line_at(bytes, base + 2)?)?;
        let (path_key, path_value) = split_key_value(line_at(bytes, base + 3)?)?;
        let (file_key, file_value) = split_key_value(line_at(bytes, base + 4)?)?;
        let (image_key, image_value) = split_key_value(line_at(bytes, base + 5)?)?;
        let (digest_key, digest_value) = split_key_value(line_at(bytes, base + 6)?)?;
        let (entry_key, entry_value) = split_key_value(line_at(bytes, base + 7)?)?;
        for (key, field) in [
            (format_key, "format"),
            (version_key, "version"),
            (path_key, "path"),
            (file_key, "file_bytes"),
            (image_key, "image_bytes"),
            (digest_key, "sha256"),
            (entry_key, "entry_contract"),
        ] {
            if artifact_key(key, field)? != id {
                return Err(Error::KeyOrder);
            }
        }

        let kind = ArtifactKind::parse(type_value)?;
        if !valid_upper_identifier(format_value, MAX_FORMAT_BYTES) {
            return Err(Error::Format);
        }
        let version = parse_range(version_value, 1, u64::MAX)?;
        if version < minimum_secure_version {
            return Err(Error::VersionFloor);
        }
        validate_path(path_value)?;
        for previous in &storage[..artifact_index] {
            if previous.path == path_value {
                return Err(Error::DuplicatePath);
            }
        }
        let file_bytes = parse_range(file_value, 1, MAX_FILE_BYTES)?;
        let image_bytes = parse_range(image_value, 0, MAX_IMAGE_BYTES)?;
        let digest = parse_digest(digest_value)?;
        if entry_value != "none" && !valid_upper_identifier(entry_value, MAX_ENTRY_CONTRACT_BYTES) {
            return Err(Error::EntryContract);
        }
        match kind {
            ArtifactKind::Kernel => {
                kernel_count += 1;
                if format_value != "PKELF1" || entry_value != "PKENTRY1" || image_bytes == 0 {
                    return Err(Error::Binding);
                }
            }
            _ => {
                if entry_value != "none" {
                    return Err(Error::EntryContract);
                }
            }
        }
        storage[artifact_index] = Artifact {
            id,
            kind,
            format: format_value,
            version,
            path: path_value,
            file_bytes,
            image_bytes,
            sha256: digest,
            entry_contract: entry_value,
        };
    }
    if kernel_count != 1 {
        return Err(Error::KernelCount);
    }
    Ok(SystemManifest {
        manifest_id,
        slot,
        manifest_version,
        minimum_secure_version,
        artifacts: &storage[..artifact_count],
    })
}

pub fn sha256(bytes: &[u8]) -> [u8; 32] {
    let result = Sha256::digest(bytes);
    let mut digest = [0u8; 32];
    digest.copy_from_slice(&result);
    digest
}

pub fn verify_file(artifact: &Artifact<'_>, bytes: &[u8]) -> Result<[u8; 32], Error> {
    if u64::try_from(bytes.len()).map_err(|_| Error::Size)? != artifact.file_bytes {
        return Err(Error::Size);
    }
    let observed = sha256(bytes);
    if observed != artifact.sha256 {
        return Err(Error::Digest);
    }
    Ok(observed)
}

pub const fn digest_prefix(digest: &[u8; 32]) -> u64 {
    u64::from_be_bytes([
        digest[0], digest[1], digest[2], digest[3], digest[4], digest[5], digest[6], digest[7],
    ])
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;

    const ZERO_SHA: &str = "0000000000000000000000000000000000000000000000000000000000000000";
    const VALID: &[u8] = b"POOLEOS-SYSTEM-MANIFEST/1.0\nmanifest_id=PSM-CYCLE103-SLOT1\nslot=1\nmanifest_version=1\nminimum_secure_version=1\nartifact_count=1\nartifact.kernel.type=kernel\nartifact.kernel.format=PKELF1\nartifact.kernel.version=1\nartifact.kernel.path=\\EFI\\POOLEOS\\KERNEL.ELF\nartifact.kernel.file_bytes=3\nartifact.kernel.image_bytes=4096\nartifact.kernel.sha256=BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD\nartifact.kernel.entry_contract=PKENTRY1\nend=PSM1\n";

    fn parsed(bytes: &[u8]) -> Result<SystemManifest<'_, '_>, Error> {
        let storage = std::boxed::Box::leak(std::boxed::Box::new([Artifact::EMPTY; MAX_ARTIFACTS]));
        parse(bytes, storage)
    }

    fn replace_once(input: &[u8], from: &str, to: &str) -> std::vec::Vec<u8> {
        let text = core::str::from_utf8(input).unwrap();
        text.replacen(from, to, 1).into_bytes()
    }

    #[test]
    fn parses_and_verifies_canonical_kernel_manifest() {
        let manifest = parsed(VALID).unwrap();
        assert_eq!(manifest.manifest_id, "PSM-CYCLE103-SLOT1");
        assert_eq!(manifest.slot, 1);
        assert_eq!(manifest.manifest_version, 1);
        assert_eq!(manifest.minimum_secure_version, 1);
        assert_eq!(manifest.artifacts.len(), 1);
        let kernel = manifest.kernel().unwrap();
        assert_eq!(kernel.path, "\\EFI\\POOLEOS\\KERNEL.ELF");
        assert_eq!(verify_file(kernel, b"abc").unwrap(), sha256(b"abc"));
        assert_eq!(digest_prefix(&kernel.sha256), 0xBA78_16BF_8F01_CFEA);
    }

    #[test]
    fn sha256_matches_standard_vectors() {
        assert_eq!(
            sha256(b""),
            parse_digest("E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855")
                .unwrap()
        );
        assert_eq!(
            sha256(b"abc"),
            parse_digest("BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD")
                .unwrap()
        );
        assert_eq!(
            sha256(b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
            parse_digest("248D6A61D20638B8E5C026930C3E6039A33CE45964FF2167F6ECEDD419DB06C1")
                .unwrap()
        );
    }

    #[test]
    fn accepts_sorted_multi_artifact_manifest() {
        let data = b"POOLEOS-SYSTEM-MANIFEST/1.0\nmanifest_id=PSM-MULTI-SLOT1\nslot=1\nmanifest_version=2\nminimum_secure_version=1\nartifact_count=2\nartifact.kernel.type=kernel\nartifact.kernel.format=PKELF1\nartifact.kernel.version=2\nartifact.kernel.path=\\EFI\\POOLEOS\\KERNEL.ELF\nartifact.kernel.file_bytes=3\nartifact.kernel.image_bytes=4096\nartifact.kernel.sha256=BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD\nartifact.kernel.entry_contract=PKENTRY1\nartifact.policy.type=policy\nartifact.policy.format=PPOL1\nartifact.policy.version=1\nartifact.policy.path=\\EFI\\POOLEOS\\POLICY.POL\nartifact.policy.file_bytes=1\nartifact.policy.image_bytes=0\nartifact.policy.sha256=0000000000000000000000000000000000000000000000000000000000000000\nartifact.policy.entry_contract=none\nend=PSM1\n";
        let manifest = parsed(data).unwrap();
        assert_eq!(manifest.artifacts.len(), 2);
        assert_eq!(manifest.artifacts[1].kind, ArtifactKind::Policy);
    }

    #[test]
    fn rejects_lexical_and_shape_drift() {
        assert_eq!(parsed(b"").unwrap_err(), Error::Empty);
        assert_eq!(
            parsed(&VALID[..VALID.len() - 1]).unwrap_err(),
            Error::MissingFinalLf
        );
        assert_eq!(
            parsed(&replace_once(
                VALID,
                "POOLEOS-SYSTEM-MANIFEST/1.0",
                "OTHER-MANIFEST/1.0"
            ))
            .unwrap_err(),
            Error::Magic
        );
        assert_eq!(
            parsed(&replace_once(VALID, "MANIFEST/1.0", "MANIFEST/2.0")).unwrap_err(),
            Error::Version
        );
        assert_eq!(
            parsed(&replace_once(VALID, "manifest_id=", "unknown=")).unwrap_err(),
            Error::UnknownKey
        );
        assert_eq!(
            parsed(&replace_once(VALID, "slot=1", "slot=01")).unwrap_err(),
            Error::NumberCanonical
        );
    }

    #[test]
    fn rejects_slot_version_and_capacity_drift() {
        assert_eq!(
            parsed(&replace_once(VALID, "slot=1", "slot=5")).unwrap_err(),
            Error::Range
        );
        assert_eq!(
            parsed(&replace_once(
                VALID,
                "minimum_secure_version=1",
                "minimum_secure_version=2"
            ))
            .unwrap_err(),
            Error::VersionFloor
        );
        let mut none = [];
        assert_eq!(parse(VALID, &mut none).unwrap_err(), Error::OutputCapacity);
    }

    #[test]
    fn rejects_artifact_identity_and_order_drift() {
        assert_eq!(
            parsed(&replace_once(
                VALID,
                "artifact.kernel.type",
                "artifact.Kernel.type"
            ))
            .unwrap_err(),
            Error::Identifier
        );
        assert_eq!(
            parsed(&replace_once(VALID, "type=kernel", "type=unknown")).unwrap_err(),
            Error::ArtifactType
        );
        assert_eq!(
            parsed(&replace_once(VALID, "format=PKELF1", "format=pkelf1")).unwrap_err(),
            Error::Format
        );
        assert_eq!(
            parsed(&replace_once(VALID, "path=\\EFI", "path=\\efi")).unwrap_err(),
            Error::Path
        );
    }

    #[test]
    fn rejects_digest_and_kernel_binding_drift() {
        assert_eq!(
            parsed(&replace_once(
                VALID,
                "BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD",
                ZERO_SHA
            ))
            .unwrap()
            .kernel()
            .and_then(|artifact| verify_file(artifact, b"abc"))
            .unwrap_err(),
            Error::Digest
        );
        assert_eq!(
            parsed(&replace_once(VALID, "format=PKELF1", "format=PXABI1")).unwrap_err(),
            Error::Binding
        );
        assert_eq!(
            parsed(&replace_once(
                VALID,
                "entry_contract=PKENTRY1",
                "entry_contract=none"
            ))
            .unwrap_err(),
            Error::Binding
        );
        assert_eq!(
            parsed(&replace_once(VALID, "image_bytes=4096", "image_bytes=0")).unwrap_err(),
            Error::Binding
        );
    }

    #[test]
    fn rejects_file_size_and_content_drift() {
        let manifest = parsed(VALID).unwrap();
        let kernel = manifest.kernel().unwrap();
        assert_eq!(verify_file(kernel, b"ab").unwrap_err(), Error::Size);
        assert_eq!(verify_file(kernel, b"abd").unwrap_err(), Error::Digest);
    }
}
