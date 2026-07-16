#![no_std]
#![deny(warnings)]

use core::cmp::min;

pub const EFI_ERROR_BIT: usize = 1usize << (usize::BITS - 1);
pub const EFI_BUFFER_TOO_SMALL: usize = EFI_ERROR_BIT | 5;
pub const TABLE_HEADER_BYTES: usize = 24;
pub const MAX_FIRMWARE_TABLE_BYTES: usize = 4096;
pub const MAX_CONFIGURATION_TABLES: usize = 256;
pub const MIN_MEMORY_DESCRIPTOR_BYTES: usize = 40;
pub const MAX_MEMORY_DESCRIPTOR_BYTES: usize = 256;
pub const MAX_MEMORY_MAP_BYTES: usize = 1024 * 1024;
pub const MEMORY_MAP_GROWTH_DESCRIPTORS: usize = 8;
pub const MAX_FRAMEBUFFER_BYTES: usize = 512 * 1024 * 1024;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ContractError {
    BufferTooSmall,
    Signature,
    HeaderSize,
    Reserved,
    Crc,
    PointerCount,
    InitialMemoryMapStatus,
    MemoryMapSize,
    DescriptorSize,
    ArithmeticOverflow,
    FinalMemoryMapStatus,
    MemoryMapShape,
    FramebufferDimensions,
    FramebufferStride,
    FramebufferFormat,
    FramebufferBase,
    FramebufferAddressRange,
    FramebufferSize,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TableHeaderSummary {
    pub signature: u64,
    pub revision: u32,
    pub header_size: usize,
    pub crc32: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MemoryMapPlan {
    pub allocation_size: usize,
    pub descriptor_size: usize,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MemoryMapSummary {
    pub map_size: usize,
    pub descriptor_size: usize,
    pub descriptor_count: usize,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PixelFormat {
    Rgb,
    Bgr,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FramebufferLayout {
    pub width: usize,
    pub height: usize,
    pub stride: usize,
    pub pixel_count_with_stride: usize,
    pub required_bytes: usize,
    pub format: PixelFormat,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Rgb {
    pub red: u8,
    pub green: u8,
    pub blue: u8,
}

fn read_u32(bytes: &[u8], offset: usize) -> Result<u32, ContractError> {
    let source = bytes
        .get(offset..offset + 4)
        .ok_or(ContractError::BufferTooSmall)?;
    Ok(u32::from_le_bytes([source[0], source[1], source[2], source[3]]))
}

fn read_u64(bytes: &[u8], offset: usize) -> Result<u64, ContractError> {
    let source = bytes
        .get(offset..offset + 8)
        .ok_or(ContractError::BufferTooSmall)?;
    Ok(u64::from_le_bytes([
        source[0], source[1], source[2], source[3], source[4], source[5], source[6], source[7],
    ]))
}

pub fn crc32(bytes: &[u8]) -> u32 {
    let mut crc = u32::MAX;
    for byte in bytes {
        crc ^= u32::from(*byte);
        for _ in 0..8 {
            let mask = 0u32.wrapping_sub(crc & 1);
            crc = (crc >> 1) ^ (0xedb8_8320 & mask);
        }
    }
    !crc
}

pub fn table_crc32(bytes: &[u8], header_size: usize) -> Result<u32, ContractError> {
    if header_size < TABLE_HEADER_BYTES || header_size > bytes.len() {
        return Err(ContractError::HeaderSize);
    }
    let mut crc = u32::MAX;
    for (index, byte) in bytes[..header_size].iter().enumerate() {
        let value = if (16..20).contains(&index) { 0 } else { *byte };
        crc ^= u32::from(value);
        for _ in 0..8 {
            let mask = 0u32.wrapping_sub(crc & 1);
            crc = (crc >> 1) ^ (0xedb8_8320 & mask);
        }
    }
    Ok(!crc)
}

pub fn validate_table_header(
    bytes: &[u8],
    expected_signature: u64,
    minimum_size: usize,
) -> Result<TableHeaderSummary, ContractError> {
    if bytes.len() < TABLE_HEADER_BYTES {
        return Err(ContractError::BufferTooSmall);
    }
    let signature = read_u64(bytes, 0)?;
    if signature != expected_signature {
        return Err(ContractError::Signature);
    }
    let revision = read_u32(bytes, 8)?;
    let header_size = read_u32(bytes, 12)? as usize;
    if header_size < minimum_size
        || header_size > MAX_FIRMWARE_TABLE_BYTES
        || header_size > bytes.len()
    {
        return Err(ContractError::HeaderSize);
    }
    let stored_crc = read_u32(bytes, 16)?;
    if read_u32(bytes, 20)? != 0 {
        return Err(ContractError::Reserved);
    }
    if table_crc32(bytes, header_size)? != stored_crc {
        return Err(ContractError::Crc);
    }
    Ok(TableHeaderSummary {
        signature,
        revision,
        header_size,
        crc32: stored_crc,
    })
}

pub fn validate_configuration_tables(
    count: usize,
    pointer_present: bool,
) -> Result<usize, ContractError> {
    if count > MAX_CONFIGURATION_TABLES || (count != 0 && !pointer_present) {
        return Err(ContractError::PointerCount);
    }
    Ok(count)
}

pub fn plan_memory_map(
    status: usize,
    required_size: usize,
    descriptor_size: usize,
) -> Result<MemoryMapPlan, ContractError> {
    if status != EFI_BUFFER_TOO_SMALL {
        return Err(ContractError::InitialMemoryMapStatus);
    }
    if required_size == 0 || required_size > MAX_MEMORY_MAP_BYTES {
        return Err(ContractError::MemoryMapSize);
    }
    if !(MIN_MEMORY_DESCRIPTOR_BYTES..=MAX_MEMORY_DESCRIPTOR_BYTES)
        .contains(&descriptor_size)
        || descriptor_size % 8 != 0
    {
        return Err(ContractError::DescriptorSize);
    }
    let margin = descriptor_size
        .checked_mul(MEMORY_MAP_GROWTH_DESCRIPTORS)
        .ok_or(ContractError::ArithmeticOverflow)?;
    let allocation_size = required_size
        .checked_add(margin)
        .ok_or(ContractError::ArithmeticOverflow)?;
    if allocation_size > MAX_MEMORY_MAP_BYTES {
        return Err(ContractError::MemoryMapSize);
    }
    Ok(MemoryMapPlan {
        allocation_size,
        descriptor_size,
    })
}

pub fn validate_memory_map_result(
    status: usize,
    map_size: usize,
    allocation_size: usize,
    descriptor_size: usize,
) -> Result<MemoryMapSummary, ContractError> {
    if status != 0 {
        return Err(ContractError::FinalMemoryMapStatus);
    }
    if map_size == 0 || map_size > allocation_size || map_size > MAX_MEMORY_MAP_BYTES {
        return Err(ContractError::MemoryMapSize);
    }
    if !(MIN_MEMORY_DESCRIPTOR_BYTES..=MAX_MEMORY_DESCRIPTOR_BYTES)
        .contains(&descriptor_size)
        || descriptor_size % 8 != 0
    {
        return Err(ContractError::DescriptorSize);
    }
    if map_size % descriptor_size != 0 {
        return Err(ContractError::MemoryMapShape);
    }
    Ok(MemoryMapSummary {
        map_size,
        descriptor_size,
        descriptor_count: map_size / descriptor_size,
    })
}

pub fn validate_framebuffer(
    width: usize,
    height: usize,
    stride: usize,
    pixel_format: u32,
    framebuffer_base: u64,
    framebuffer_size: usize,
) -> Result<FramebufferLayout, ContractError> {
    if width < 320 || height < 200 || width > 16_384 || height > 16_384 {
        return Err(ContractError::FramebufferDimensions);
    }
    if stride < width || stride > 16_384 {
        return Err(ContractError::FramebufferStride);
    }
    let format = match pixel_format {
        0 => PixelFormat::Rgb,
        1 => PixelFormat::Bgr,
        _ => return Err(ContractError::FramebufferFormat),
    };
    if framebuffer_base == 0 || framebuffer_base & 3 != 0 {
        return Err(ContractError::FramebufferBase);
    }
    let pixel_count_with_stride = stride
        .checked_mul(height)
        .ok_or(ContractError::ArithmeticOverflow)?;
    let required_bytes = pixel_count_with_stride
        .checked_mul(4)
        .ok_or(ContractError::ArithmeticOverflow)?;
    if required_bytes > framebuffer_size || required_bytes > MAX_FRAMEBUFFER_BYTES {
        return Err(ContractError::FramebufferSize);
    }
    let required_bytes_u64 = u64::try_from(required_bytes)
        .map_err(|_| ContractError::FramebufferAddressRange)?;
    if framebuffer_base > usize::MAX as u64
        || framebuffer_base.checked_add(required_bytes_u64).is_none()
    {
        return Err(ContractError::FramebufferAddressRange);
    }
    Ok(FramebufferLayout {
        width,
        height,
        stride,
        pixel_count_with_stride,
        required_bytes,
        format,
    })
}

fn squared_distance(x: usize, y: usize, center_x: usize, center_y: usize) -> u64 {
    let dx = x.abs_diff(center_x) as u64;
    let dy = y.abs_diff(center_y) as u64;
    dx * dx + dy * dy
}

pub fn identity_rgb(x: usize, y: usize, width: usize, height: usize) -> Rgb {
    let scale = min(width, height).max(1);
    let center_x = width / 2;
    let center_y = height.saturating_mul(9) / 20;
    let outer = (scale / 5).max(24);
    let inner = outer.saturating_mul(3) / 4;
    let distance = squared_distance(x, y, center_x, center_y);
    let outer_squared = (outer as u64) * (outer as u64);
    let inner_squared = (inner as u64) * (inner as u64);

    let mut color = Rgb {
        red: 7,
        green: 14,
        blue: 18,
    };
    if y < height / 3 {
        color = Rgb {
            red: 10,
            green: 20,
            blue: 25,
        };
    }
    if distance <= outer_squared && distance >= inner_squared {
        color = if x + y < center_x + center_y {
            Rgb {
                red: 150,
                green: 248,
                blue: 255,
            }
        } else {
            Rgb {
                red: 25,
                green: 177,
                blue: 194,
            }
        };
    }

    let stem_left = center_x.saturating_sub(outer / 3);
    let stem_right = stem_left + (outer / 5).max(8);
    let stem_top = center_y.saturating_sub(outer / 2);
    let stem_bottom = center_y + outer / 2;
    if (stem_left..=stem_right).contains(&x) && (stem_top..=stem_bottom).contains(&y) {
        color = Rgb {
            red: 238,
            green: 252,
            blue: 252,
        };
    }

    let bowl_center_x = stem_right;
    let bowl_center_y = center_y.saturating_sub(outer / 5);
    let bowl_outer = (outer * 7 / 20).max(12);
    let bowl_inner = bowl_outer * 3 / 5;
    let bowl_distance = squared_distance(x, y, bowl_center_x, bowl_center_y);
    if x >= stem_right
        && bowl_distance <= (bowl_outer as u64) * (bowl_outer as u64)
        && bowl_distance >= (bowl_inner as u64) * (bowl_inner as u64)
    {
        color = Rgb {
            red: 238,
            green: 252,
            blue: 252,
        };
    }

    let bar_y = height.saturating_mul(4) / 5;
    let bar_half = width / 10;
    if y >= bar_y
        && y < bar_y + (scale / 160).max(2)
        && x >= center_x.saturating_sub(bar_half)
        && x <= center_x + bar_half
    {
        color = Rgb {
            red: 56,
            green: 213,
            blue: 216,
        };
    }
    color
}

pub fn pack_pixel(color: Rgb, format: PixelFormat) -> u32 {
    match format {
        PixelFormat::Rgb => {
            u32::from(color.red) | (u32::from(color.green) << 8) | (u32::from(color.blue) << 16)
        }
        PixelFormat::Bgr => {
            u32::from(color.blue) | (u32::from(color.green) << 8) | (u32::from(color.red) << 16)
        }
    }
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;
    use std::vec;

    fn table(signature: u64, size: usize) -> std::vec::Vec<u8> {
        let mut bytes = vec![0u8; size];
        bytes[0..8].copy_from_slice(&signature.to_le_bytes());
        bytes[8..12].copy_from_slice(&0x0002_0064u32.to_le_bytes());
        bytes[12..16].copy_from_slice(&(size as u32).to_le_bytes());
        let crc = table_crc32(&bytes, size).unwrap();
        bytes[16..20].copy_from_slice(&crc.to_le_bytes());
        bytes
    }

    #[test]
    fn standard_crc_vector_matches() {
        assert_eq!(crc32(b"123456789"), 0xcbf4_3926);
    }

    #[test]
    fn table_header_accepts_exact_crc_and_rejects_mutations() {
        let signature = 0x5453_5953_2049_4249;
        let bytes = table(signature, 120);
        assert_eq!(
            validate_table_header(&bytes, signature, 120).unwrap().header_size,
            120
        );
        let mut wrong_signature = bytes.clone();
        wrong_signature[0] ^= 1;
        assert_eq!(
            validate_table_header(&wrong_signature, signature, 120),
            Err(ContractError::Signature)
        );
        let mut wrong_crc = bytes.clone();
        wrong_crc[119] ^= 1;
        assert_eq!(
            validate_table_header(&wrong_crc, signature, 120),
            Err(ContractError::Crc)
        );
        let mut reserved = bytes.clone();
        reserved[20] = 1;
        assert_eq!(
            validate_table_header(&reserved, signature, 120),
            Err(ContractError::Reserved)
        );
    }

    #[test]
    fn table_header_rejects_short_and_oversized_claims() {
        let signature = 7;
        assert_eq!(
            validate_table_header(&[0; 8], signature, 120),
            Err(ContractError::BufferTooSmall)
        );
        let mut bytes = table(signature, 120);
        bytes[12..16].copy_from_slice(&4097u32.to_le_bytes());
        assert_eq!(
            validate_table_header(&bytes, signature, 120),
            Err(ContractError::HeaderSize)
        );
    }

    #[test]
    fn configuration_table_count_is_bounded() {
        assert_eq!(validate_configuration_tables(0, false), Ok(0));
        assert_eq!(validate_configuration_tables(12, true), Ok(12));
        assert_eq!(
            validate_configuration_tables(1, false),
            Err(ContractError::PointerCount)
        );
        assert_eq!(
            validate_configuration_tables(MAX_CONFIGURATION_TABLES + 1, true),
            Err(ContractError::PointerCount)
        );
    }

    #[test]
    fn memory_map_plan_requires_expected_probe_and_margin() {
        let plan = plan_memory_map(EFI_BUFFER_TOO_SMALL, 4096, 48).unwrap();
        assert_eq!(plan.allocation_size, 4480);
        assert_eq!(
            plan_memory_map(0, 4096, 48),
            Err(ContractError::InitialMemoryMapStatus)
        );
        assert_eq!(
            plan_memory_map(EFI_BUFFER_TOO_SMALL, 4096, 41),
            Err(ContractError::DescriptorSize)
        );
        assert_eq!(
            plan_memory_map(EFI_BUFFER_TOO_SMALL, MAX_MEMORY_MAP_BYTES, 48),
            Err(ContractError::MemoryMapSize)
        );
    }

    #[test]
    fn memory_map_result_rejects_partial_descriptors() {
        let summary = validate_memory_map_result(0, 4800, 8192, 48).unwrap();
        assert_eq!(summary.descriptor_count, 100);
        assert_eq!(
            validate_memory_map_result(0, 4801, 8192, 48),
            Err(ContractError::MemoryMapShape)
        );
        assert_eq!(
            validate_memory_map_result(EFI_BUFFER_TOO_SMALL, 4800, 8192, 48),
            Err(ContractError::FinalMemoryMapStatus)
        );
    }

    #[test]
    fn framebuffer_contract_rejects_blt_only_and_short_storage() {
        let layout = validate_framebuffer(1024, 768, 1024, 1, 0x8000_0000, 1024 * 768 * 4)
            .unwrap();
        assert_eq!(layout.format, PixelFormat::Bgr);
        assert_eq!(
            validate_framebuffer(1024, 768, 1024, 3, 0x8000_0000, 1024 * 768 * 4),
            Err(ContractError::FramebufferFormat)
        );
        assert_eq!(
            validate_framebuffer(1024, 768, 1000, 1, 0x8000_0000, 1024 * 768 * 4),
            Err(ContractError::FramebufferStride)
        );
        assert_eq!(
            validate_framebuffer(1024, 768, 1024, 1, 0x8000_0000, 4096),
            Err(ContractError::FramebufferSize)
        );
        assert_eq!(
            validate_framebuffer(320, 200, 320, 1, u64::MAX - 3, 320 * 200 * 4),
            Err(ContractError::FramebufferAddressRange)
        );
    }

    #[test]
    fn boot_identity_is_high_contrast_and_format_stable() {
        let background = identity_rgb(0, 479, 640, 480);
        let ring = identity_rgb(320, 120, 640, 480);
        assert_ne!(background, ring);
        assert!(u16::from(ring.green) + u16::from(ring.blue) > 300);
        let color = Rgb {
            red: 1,
            green: 2,
            blue: 3,
        };
        assert_eq!(pack_pixel(color, PixelFormat::Rgb), 0x0003_0201);
        assert_eq!(pack_pixel(color, PixelFormat::Bgr), 0x0001_0203);
    }
}
