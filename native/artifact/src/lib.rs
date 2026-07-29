#![no_std]
#![deny(warnings)]

use sha2::{Digest, Sha256};

pub const CONTRACT_ID: &str = "PBART1";
pub const MAGIC: [u8; 8] = *b"PBART1\0\0";
pub const MAJOR_VERSION: u16 = 1;
pub const MINOR_VERSION: u16 = 0;
pub const HEADER_BYTES: usize = 96;
pub const MAX_FILE_BYTES: usize = 1024 * 1024;
pub const MAX_PAYLOAD_BYTES: usize = MAX_FILE_BYTES - HEADER_BYTES;

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
#[repr(u32)]
pub enum Role {
    InitialSystem = 2,
    Recovery = 3,
    Symbols = 4,
    Microcode = 5,
    FirmwareManifest = 6,
    PolicyBundle = 7,
}

impl Role {
    pub const ALL: [Self; 6] = [
        Self::InitialSystem,
        Self::Recovery,
        Self::Symbols,
        Self::Microcode,
        Self::FirmwareManifest,
        Self::PolicyBundle,
    ];

    pub const fn code(self) -> u32 {
        self as u32
    }

    pub const fn as_str(self) -> &'static str {
        match self {
            Self::InitialSystem => "initial_system",
            Self::Recovery => "recovery",
            Self::Symbols => "symbols",
            Self::Microcode => "microcode",
            Self::FirmwareManifest => "firmware",
            Self::PolicyBundle => "policy",
        }
    }

    pub const fn from_code(value: u32) -> Result<Self, Error> {
        match value {
            2 => Ok(Self::InitialSystem),
            3 => Ok(Self::Recovery),
            4 => Ok(Self::Symbols),
            5 => Ok(Self::Microcode),
            6 => Ok(Self::FirmwareManifest),
            7 => Ok(Self::PolicyBundle),
            _ => Err(Error::Role),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Truncated,
    Oversized,
    Magic,
    Version,
    HeaderSize,
    Reserved,
    Role,
    Flags,
    ArtifactVersion,
    PayloadSize,
    ImageSize,
    TrailingBytes,
    Digest,
    RoleBinding,
    VersionBinding,
    OutputCapacity,
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::Truncated => "artifact_truncated",
            Self::Oversized => "artifact_oversized",
            Self::Magic => "artifact_magic",
            Self::Version => "artifact_version",
            Self::HeaderSize => "artifact_header_size",
            Self::Reserved => "artifact_reserved",
            Self::Role => "artifact_role",
            Self::Flags => "artifact_flags",
            Self::ArtifactVersion => "artifact_payload_version",
            Self::PayloadSize => "artifact_payload_size",
            Self::ImageSize => "artifact_image_size",
            Self::TrailingBytes => "artifact_trailing_bytes",
            Self::Digest => "artifact_digest",
            Self::RoleBinding => "artifact_role_binding",
            Self::VersionBinding => "artifact_version_binding",
            Self::OutputCapacity => "artifact_output_capacity",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Artifact<'a> {
    pub role: Role,
    pub version: u64,
    pub payload: &'a [u8],
    pub payload_sha256: [u8; 32],
}

fn read_u16(bytes: &[u8], offset: usize) -> Result<u16, Error> {
    let value = bytes.get(offset..offset + 2).ok_or(Error::Truncated)?;
    Ok(u16::from_le_bytes([value[0], value[1]]))
}

fn read_u32(bytes: &[u8], offset: usize) -> Result<u32, Error> {
    let value = bytes.get(offset..offset + 4).ok_or(Error::Truncated)?;
    Ok(u32::from_le_bytes([value[0], value[1], value[2], value[3]]))
}

fn read_u64(bytes: &[u8], offset: usize) -> Result<u64, Error> {
    let value = bytes.get(offset..offset + 8).ok_or(Error::Truncated)?;
    Ok(u64::from_le_bytes([
        value[0], value[1], value[2], value[3], value[4], value[5], value[6], value[7],
    ]))
}

fn write_u16(bytes: &mut [u8], offset: usize, value: u16) {
    bytes[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
}

fn write_u32(bytes: &mut [u8], offset: usize, value: u32) {
    bytes[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
}

fn write_u64(bytes: &mut [u8], offset: usize, value: u64) {
    bytes[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
}

pub fn sha256(bytes: &[u8]) -> [u8; 32] {
    let result = Sha256::digest(bytes);
    let mut digest = [0u8; 32];
    digest.copy_from_slice(&result);
    digest
}

pub fn parse(bytes: &[u8]) -> Result<Artifact<'_>, Error> {
    if bytes.len() < HEADER_BYTES {
        return Err(Error::Truncated);
    }
    if bytes.len() > MAX_FILE_BYTES {
        return Err(Error::Oversized);
    }
    if bytes[..MAGIC.len()] != MAGIC {
        return Err(Error::Magic);
    }
    if read_u16(bytes, 8)? != MAJOR_VERSION || read_u16(bytes, 10)? != MINOR_VERSION {
        return Err(Error::Version);
    }
    if usize::from(read_u16(bytes, 12)?) != HEADER_BYTES {
        return Err(Error::HeaderSize);
    }
    if read_u16(bytes, 14)? != 0 || bytes[80..HEADER_BYTES].iter().any(|byte| *byte != 0) {
        return Err(Error::Reserved);
    }
    let role = Role::from_code(read_u32(bytes, 16)?)?;
    if read_u32(bytes, 20)? != 0 {
        return Err(Error::Flags);
    }
    let version = read_u64(bytes, 24)?;
    if version == 0 {
        return Err(Error::ArtifactVersion);
    }
    let payload_bytes = usize::try_from(read_u64(bytes, 32)?).map_err(|_| Error::PayloadSize)?;
    if payload_bytes == 0 || payload_bytes > MAX_PAYLOAD_BYTES {
        return Err(Error::PayloadSize);
    }
    if read_u64(bytes, 40)? != 0 {
        return Err(Error::ImageSize);
    }
    let expected_bytes = HEADER_BYTES
        .checked_add(payload_bytes)
        .ok_or(Error::PayloadSize)?;
    if bytes.len() < expected_bytes {
        return Err(Error::Truncated);
    }
    if bytes.len() > expected_bytes {
        return Err(Error::TrailingBytes);
    }
    let payload = &bytes[HEADER_BYTES..expected_bytes];
    let mut expected_digest = [0u8; 32];
    expected_digest.copy_from_slice(&bytes[48..80]);
    if sha256(payload) != expected_digest {
        return Err(Error::Digest);
    }
    Ok(Artifact {
        role,
        version,
        payload,
        payload_sha256: expected_digest,
    })
}

pub fn parse_bound(bytes: &[u8], role: Role, version: u64) -> Result<Artifact<'_>, Error> {
    let artifact = parse(bytes)?;
    if artifact.role != role {
        return Err(Error::RoleBinding);
    }
    if artifact.version != version {
        return Err(Error::VersionBinding);
    }
    Ok(artifact)
}

pub fn encode<'a>(
    role: Role,
    version: u64,
    payload: &[u8],
    output: &'a mut [u8],
) -> Result<&'a [u8], Error> {
    if version == 0 {
        return Err(Error::ArtifactVersion);
    }
    if payload.is_empty() || payload.len() > MAX_PAYLOAD_BYTES {
        return Err(Error::PayloadSize);
    }
    let total = HEADER_BYTES
        .checked_add(payload.len())
        .ok_or(Error::PayloadSize)?;
    if output.len() < total {
        return Err(Error::OutputCapacity);
    }
    let output = &mut output[..total];
    output.fill(0);
    output[..MAGIC.len()].copy_from_slice(&MAGIC);
    write_u16(output, 8, MAJOR_VERSION);
    write_u16(output, 10, MINOR_VERSION);
    write_u16(output, 12, HEADER_BYTES as u16);
    write_u32(output, 16, role.code());
    write_u64(output, 24, version);
    write_u64(output, 32, payload.len() as u64);
    output[48..80].copy_from_slice(&sha256(payload));
    output[HEADER_BYTES..].copy_from_slice(payload);
    parse_bound(output, role, version)?;
    Ok(output)
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;

    fn fixture(role: Role) -> std::vec::Vec<u8> {
        let payload = b"PooleOS PBART1 development payload";
        let mut output = std::vec![0u8; HEADER_BYTES + payload.len()];
        let bytes = encode(role, 7, payload, &mut output).unwrap();
        bytes.to_vec()
    }

    #[test]
    fn canonical_envelope_round_trips_all_roles() {
        for role in Role::ALL {
            let bytes = fixture(role);
            let artifact = parse_bound(&bytes, role, 7).unwrap();
            assert_eq!(artifact.role, role);
            assert_eq!(artifact.version, 7);
            assert_eq!(artifact.payload, b"PooleOS PBART1 development payload");
            assert_eq!(artifact.payload_sha256, sha256(artifact.payload));
        }
    }

    #[test]
    fn rejects_header_role_version_and_digest_substitution() {
        let bytes = fixture(Role::InitialSystem);
        assert_eq!(
            parse_bound(&bytes, Role::Recovery, 7),
            Err(Error::RoleBinding)
        );
        assert_eq!(
            parse_bound(&bytes, Role::InitialSystem, 8),
            Err(Error::VersionBinding)
        );
        let mut changed = bytes.clone();
        changed[HEADER_BYTES] ^= 1;
        assert_eq!(parse(&changed), Err(Error::Digest));
        let mut flags = bytes.clone();
        flags[20] = 1;
        assert_eq!(parse(&flags), Err(Error::Flags));
        let mut reserved = bytes.clone();
        reserved[95] = 1;
        assert_eq!(parse(&reserved), Err(Error::Reserved));
    }

    #[test]
    fn rejects_truncation_trailing_bytes_and_declared_size_drift() {
        let bytes = fixture(Role::PolicyBundle);
        assert_eq!(parse(&bytes[..HEADER_BYTES - 1]), Err(Error::Truncated));
        assert_eq!(parse(&bytes[..bytes.len() - 1]), Err(Error::Truncated));
        let mut trailing = bytes.clone();
        trailing.push(0);
        assert_eq!(parse(&trailing), Err(Error::TrailingBytes));
        let mut empty = bytes.clone();
        empty[32..40].copy_from_slice(&0u64.to_le_bytes());
        assert_eq!(parse(&empty), Err(Error::PayloadSize));
        let mut image = bytes.clone();
        image[40] = 1;
        assert_eq!(parse(&image), Err(Error::ImageSize));
    }

    #[test]
    fn encoder_rejects_zero_version_empty_payload_and_short_output() {
        let mut output = [0u8; HEADER_BYTES + 1];
        assert_eq!(
            encode(Role::Symbols, 0, b"x", &mut output),
            Err(Error::ArtifactVersion)
        );
        assert_eq!(
            encode(Role::Symbols, 1, b"", &mut output),
            Err(Error::PayloadSize)
        );
        assert_eq!(
            encode(Role::Symbols, 1, b"xy", &mut output),
            Err(Error::OutputCapacity)
        );
    }
}
