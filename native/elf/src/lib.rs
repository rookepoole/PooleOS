#![no_std]
#![deny(warnings)]

pub const CONTRACT_ID: &str = "PKELF1";
pub const PAGE_SIZE: u64 = 4096;
pub const VIRTUAL_BASE_ALIGNMENT: u64 = 2 * 1024 * 1024;
pub const MAX_FILE_BYTES: usize = 1024 * 1024;
pub const MAX_IMAGE_BYTES: u64 = 64 * 1024 * 1024;
pub const MIN_PHYSICAL_BASE: u64 = 0x0010_0000;
pub const MAX_PHYSICAL_EXCLUSIVE: u64 = 1u64 << 52;
pub const MIN_VIRTUAL_BASE: u64 = 0xffff_ffff_8000_0000;
pub const MAX_VIRTUAL_EXCLUSIVE: u64 = 0xffff_ffff_c000_0000;
pub const PROGRAM_HEADER_COUNT: usize = 7;
pub const LOAD_SEGMENT_COUNT: usize = 3;
pub const MAPPING_COUNT: usize = 4;
pub const MAX_RELOCATIONS: usize = 4096;

const ELF_HEADER_BYTES: u64 = 64;
const PROGRAM_HEADER_BYTES: u64 = 56;
const DYNAMIC_ENTRY_BYTES: u64 = 16;
const DYNAMIC_ENTRY_COUNT: u64 = 4;
const DYNAMIC_BYTES: u64 = DYNAMIC_ENTRY_BYTES * DYNAMIC_ENTRY_COUNT;
const RELA_ENTRY_BYTES: u64 = 24;

const PT_LOAD: u32 = 1;
const PT_DYNAMIC: u32 = 2;
const PT_PHDR: u32 = 6;
const PT_GNU_STACK: u32 = 0x6474_e551;
const PT_GNU_RELRO: u32 = 0x6474_e552;

const PF_X: u32 = 1;
const PF_W: u32 = 2;
const PF_R: u32 = 4;

const DT_NULL: i64 = 0;
const DT_RELA: i64 = 7;
const DT_RELASZ: i64 = 8;
const DT_RELAENT: i64 = 9;
const R_X86_64_RELATIVE: u32 = 8;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Empty,
    HeaderTruncated,
    FileTooLarge,
    Magic,
    Class,
    Encoding,
    IdentVersion,
    OsAbi,
    AbiVersion,
    IdentPadding,
    FileType,
    Machine,
    Version,
    HeaderFlags,
    HeaderSize,
    ProgramHeaderOffset,
    ProgramHeaderSize,
    ProgramHeaderCount,
    ProgramHeaderBounds,
    SectionTable,
    UnsupportedSegment,
    ProgramHeaderOrder,
    PhdrSegment,
    LoadCount,
    LoadFlags,
    LoadAlignment,
    LoadAddress,
    SegmentSize,
    SegmentBounds,
    SegmentLayout,
    FileCoverage,
    EntryPoint,
    DynamicSegment,
    DynamicOrder,
    DynamicEntry,
    RelocationTable,
    RelocationCount,
    RelocationEntrySize,
    RelocationType,
    RelocationSymbol,
    RelocationOrder,
    RelocationTarget,
    RelocationAddend,
    RelocationValue,
    RelroSegment,
    StackSegment,
    PhysicalBase,
    VirtualBase,
    OutputCapacity,
    ArithmeticOverflow,
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::Empty => "empty",
            Self::HeaderTruncated => "header_truncated",
            Self::FileTooLarge => "file_too_large",
            Self::Magic => "magic",
            Self::Class => "class",
            Self::Encoding => "encoding",
            Self::IdentVersion => "ident_version",
            Self::OsAbi => "osabi",
            Self::AbiVersion => "abi_version",
            Self::IdentPadding => "ident_padding",
            Self::FileType => "file_type",
            Self::Machine => "machine",
            Self::Version => "version",
            Self::HeaderFlags => "header_flags",
            Self::HeaderSize => "header_size",
            Self::ProgramHeaderOffset => "program_header_offset",
            Self::ProgramHeaderSize => "program_header_size",
            Self::ProgramHeaderCount => "program_header_count",
            Self::ProgramHeaderBounds => "program_header_bounds",
            Self::SectionTable => "section_table",
            Self::UnsupportedSegment => "unsupported_segment",
            Self::ProgramHeaderOrder => "program_header_order",
            Self::PhdrSegment => "phdr_segment",
            Self::LoadCount => "load_count",
            Self::LoadFlags => "load_flags",
            Self::LoadAlignment => "load_alignment",
            Self::LoadAddress => "load_address",
            Self::SegmentSize => "segment_size",
            Self::SegmentBounds => "segment_bounds",
            Self::SegmentLayout => "segment_layout",
            Self::FileCoverage => "file_coverage",
            Self::EntryPoint => "entry_point",
            Self::DynamicSegment => "dynamic_segment",
            Self::DynamicOrder => "dynamic_order",
            Self::DynamicEntry => "dynamic_entry",
            Self::RelocationTable => "relocation_table",
            Self::RelocationCount => "relocation_count",
            Self::RelocationEntrySize => "relocation_entry_size",
            Self::RelocationType => "relocation_type",
            Self::RelocationSymbol => "relocation_symbol",
            Self::RelocationOrder => "relocation_order",
            Self::RelocationTarget => "relocation_target",
            Self::RelocationAddend => "relocation_addend",
            Self::RelocationValue => "relocation_value",
            Self::RelroSegment => "relro_segment",
            Self::StackSegment => "stack_segment",
            Self::PhysicalBase => "physical_base",
            Self::VirtualBase => "virtual_base",
            Self::OutputCapacity => "output_capacity",
            Self::ArithmeticOverflow => "arithmetic_overflow",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Permissions {
    pub read: bool,
    pub write: bool,
    pub execute: bool,
}

impl Permissions {
    pub const READ: Self = Self {
        read: true,
        write: false,
        execute: false,
    };
    pub const READ_EXECUTE: Self = Self {
        read: true,
        write: false,
        execute: true,
    };
    pub const READ_WRITE: Self = Self {
        read: true,
        write: true,
        execute: false,
    };

    pub const fn code(self) -> &'static str {
        if self.execute {
            "rx"
        } else if self.write {
            "rw"
        } else {
            "r"
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SegmentPlan {
    pub file_offset: u32,
    pub virtual_offset: u32,
    pub file_size: u32,
    pub memory_size: u32,
    pub permissions: Permissions,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MappingPlan {
    pub virtual_offset: u32,
    pub memory_size: u32,
    pub permissions: Permissions,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ImagePlan {
    pub file_size: u32,
    pub image_size: u32,
    pub entry_offset: u32,
    pub entry_virtual: u64,
    pub entry_physical: u64,
    pub physical_base: u64,
    pub virtual_base: u64,
    pub relocation_count: u32,
    pub relro_offset: u32,
    pub relro_size: u32,
    pub segments: [SegmentPlan; LOAD_SEGMENT_COUNT],
    pub mappings: [MappingPlan; MAPPING_COUNT],
}

#[derive(Clone, Copy)]
struct ProgramHeader {
    segment_type: u32,
    flags: u32,
    offset: u64,
    virtual_address: u64,
    physical_address: u64,
    file_size: u64,
    memory_size: u64,
    alignment: u64,
}

impl ProgramHeader {
    const EMPTY: Self = Self {
        segment_type: 0,
        flags: 0,
        offset: 0,
        virtual_address: 0,
        physical_address: 0,
        file_size: 0,
        memory_size: 0,
        alignment: 0,
    };
}

struct RelocationContext<'a> {
    bytes: &'a [u8],
    relocation_address: u64,
    relocation_size: u64,
    relocation_count: u64,
    dynamic: ProgramHeader,
    relro: ProgramHeader,
    loads: &'a [ProgramHeader; LOAD_SEGMENT_COUNT],
    image_size: u64,
    virtual_base: u64,
}

fn read_u16(bytes: &[u8], offset: usize, error: Error) -> Result<u16, Error> {
    let source = bytes.get(offset..offset + 2).ok_or(error)?;
    Ok(u16::from_le_bytes([source[0], source[1]]))
}

fn read_u32(bytes: &[u8], offset: usize, error: Error) -> Result<u32, Error> {
    let source = bytes.get(offset..offset + 4).ok_or(error)?;
    Ok(u32::from_le_bytes([
        source[0], source[1], source[2], source[3],
    ]))
}

fn read_u64(bytes: &[u8], offset: usize, error: Error) -> Result<u64, Error> {
    let source = bytes.get(offset..offset + 8).ok_or(error)?;
    Ok(u64::from_le_bytes([
        source[0], source[1], source[2], source[3], source[4], source[5], source[6], source[7],
    ]))
}

fn read_i64(bytes: &[u8], offset: usize, error: Error) -> Result<i64, Error> {
    Ok(i64::from_le_bytes(
        read_u64(bytes, offset, error)?.to_le_bytes(),
    ))
}

fn to_usize(value: u64, error: Error) -> Result<usize, Error> {
    usize::try_from(value).map_err(|_| error)
}

fn to_u32(value: u64) -> Result<u32, Error> {
    u32::try_from(value).map_err(|_| Error::ArithmeticOverflow)
}

fn add(left: u64, right: u64, error: Error) -> Result<u64, Error> {
    left.checked_add(right).ok_or(error)
}

fn range_contains(start: u64, size: u64, inner_start: u64, inner_size: u64) -> bool {
    match (start.checked_add(size), inner_start.checked_add(inner_size)) {
        (Some(end), Some(inner_end)) => inner_start >= start && inner_end <= end,
        _ => false,
    }
}

fn ranges_overlap(left_start: u64, left_size: u64, right_start: u64, right_size: u64) -> bool {
    match (
        left_start.checked_add(left_size),
        right_start.checked_add(right_size),
    ) {
        (Some(left_end), Some(right_end)) => left_start < right_end && right_start < left_end,
        _ => true,
    }
}

fn parse_program_header(bytes: &[u8], index: usize) -> Result<ProgramHeader, Error> {
    let base = to_usize(
        ELF_HEADER_BYTES
            .checked_add(
                PROGRAM_HEADER_BYTES
                    .checked_mul(index as u64)
                    .ok_or(Error::ProgramHeaderBounds)?,
            )
            .ok_or(Error::ProgramHeaderBounds)?,
        Error::ProgramHeaderBounds,
    )?;
    Ok(ProgramHeader {
        segment_type: read_u32(bytes, base, Error::ProgramHeaderBounds)?,
        flags: read_u32(bytes, base + 4, Error::ProgramHeaderBounds)?,
        offset: read_u64(bytes, base + 8, Error::ProgramHeaderBounds)?,
        virtual_address: read_u64(bytes, base + 16, Error::ProgramHeaderBounds)?,
        physical_address: read_u64(bytes, base + 24, Error::ProgramHeaderBounds)?,
        file_size: read_u64(bytes, base + 32, Error::ProgramHeaderBounds)?,
        memory_size: read_u64(bytes, base + 40, Error::ProgramHeaderBounds)?,
        alignment: read_u64(bytes, base + 48, Error::ProgramHeaderBounds)?,
    })
}

fn supported_type(segment_type: u32) -> bool {
    matches!(
        segment_type,
        PT_LOAD | PT_DYNAMIC | PT_PHDR | PT_GNU_STACK | PT_GNU_RELRO
    )
}

fn validate_base_addresses(
    physical_base: u64,
    virtual_base: u64,
    image_size: u64,
) -> Result<(), Error> {
    if physical_base < MIN_PHYSICAL_BASE
        || !physical_base.is_multiple_of(PAGE_SIZE)
        || add(physical_base, image_size, Error::PhysicalBase)? > MAX_PHYSICAL_EXCLUSIVE
    {
        return Err(Error::PhysicalBase);
    }
    if !(MIN_VIRTUAL_BASE..MAX_VIRTUAL_EXCLUSIVE).contains(&virtual_base)
        || !virtual_base.is_multiple_of(VIRTUAL_BASE_ALIGNMENT)
        || add(virtual_base, image_size, Error::VirtualBase)? > MAX_VIRTUAL_EXCLUSIVE
    {
        return Err(Error::VirtualBase);
    }
    Ok(())
}

fn validate_header(bytes: &[u8]) -> Result<(u64, [ProgramHeader; PROGRAM_HEADER_COUNT]), Error> {
    if bytes.is_empty() {
        return Err(Error::Empty);
    }
    if bytes.len() < ELF_HEADER_BYTES as usize {
        return Err(Error::HeaderTruncated);
    }
    if bytes.len() > MAX_FILE_BYTES {
        return Err(Error::FileTooLarge);
    }
    if bytes[0..4] != [0x7f, b'E', b'L', b'F'] {
        return Err(Error::Magic);
    }
    if bytes[4] != 2 {
        return Err(Error::Class);
    }
    if bytes[5] != 1 {
        return Err(Error::Encoding);
    }
    if bytes[6] != 1 {
        return Err(Error::IdentVersion);
    }
    if bytes[7] != 0 {
        return Err(Error::OsAbi);
    }
    if bytes[8] != 0 {
        return Err(Error::AbiVersion);
    }
    if bytes[9..16].iter().any(|byte| *byte != 0) {
        return Err(Error::IdentPadding);
    }
    if read_u16(bytes, 16, Error::HeaderTruncated)? != 3 {
        return Err(Error::FileType);
    }
    if read_u16(bytes, 18, Error::HeaderTruncated)? != 62 {
        return Err(Error::Machine);
    }
    if read_u32(bytes, 20, Error::HeaderTruncated)? != 1 {
        return Err(Error::Version);
    }
    let entry = read_u64(bytes, 24, Error::HeaderTruncated)?;
    if read_u64(bytes, 32, Error::HeaderTruncated)? != ELF_HEADER_BYTES {
        return Err(Error::ProgramHeaderOffset);
    }
    let section_offset = read_u64(bytes, 40, Error::HeaderTruncated)?;
    if read_u32(bytes, 48, Error::HeaderTruncated)? != 0 {
        return Err(Error::HeaderFlags);
    }
    if u64::from(read_u16(bytes, 52, Error::HeaderTruncated)?) != ELF_HEADER_BYTES {
        return Err(Error::HeaderSize);
    }
    if u64::from(read_u16(bytes, 54, Error::HeaderTruncated)?) != PROGRAM_HEADER_BYTES {
        return Err(Error::ProgramHeaderSize);
    }
    if usize::from(read_u16(bytes, 56, Error::HeaderTruncated)?) != PROGRAM_HEADER_COUNT {
        return Err(Error::ProgramHeaderCount);
    }
    let section_entry_size = read_u16(bytes, 58, Error::HeaderTruncated)?;
    let section_count = read_u16(bytes, 60, Error::HeaderTruncated)?;
    let section_name_index = read_u16(bytes, 62, Error::HeaderTruncated)?;
    if section_offset != 0
        || section_count != 0
        || section_name_index != 0
        || !matches!(section_entry_size, 0 | 64)
    {
        return Err(Error::SectionTable);
    }
    let program_table_end = ELF_HEADER_BYTES
        .checked_add(
            PROGRAM_HEADER_BYTES
                .checked_mul(PROGRAM_HEADER_COUNT as u64)
                .ok_or(Error::ProgramHeaderBounds)?,
        )
        .ok_or(Error::ProgramHeaderBounds)?;
    if program_table_end > bytes.len() as u64 {
        return Err(Error::ProgramHeaderBounds);
    }

    let mut headers = [ProgramHeader::EMPTY; PROGRAM_HEADER_COUNT];
    for (index, header) in headers.iter_mut().enumerate() {
        *header = parse_program_header(bytes, index)?;
        if !supported_type(header.segment_type) {
            return Err(Error::UnsupportedSegment);
        }
    }
    let expected = [
        PT_PHDR,
        PT_LOAD,
        PT_LOAD,
        PT_LOAD,
        PT_DYNAMIC,
        PT_GNU_RELRO,
        PT_GNU_STACK,
    ];
    for (header, expected_type) in headers.iter().zip(expected) {
        if header.segment_type != expected_type {
            return Err(Error::ProgramHeaderOrder);
        }
    }
    Ok((entry, headers))
}

fn validate_phdr(header: ProgramHeader) -> Result<(), Error> {
    let table_size = PROGRAM_HEADER_BYTES
        .checked_mul(PROGRAM_HEADER_COUNT as u64)
        .ok_or(Error::ArithmeticOverflow)?;
    if header.flags != PF_R
        || header.offset != ELF_HEADER_BYTES
        || header.virtual_address != ELF_HEADER_BYTES
        || header.physical_address != 0
        || header.file_size != table_size
        || header.memory_size != table_size
        || header.alignment != 8
    {
        return Err(Error::PhdrSegment);
    }
    Ok(())
}

fn validate_loads(
    bytes: &[u8],
    headers: &[ProgramHeader; PROGRAM_HEADER_COUNT],
) -> Result<([ProgramHeader; LOAD_SEGMENT_COUNT], u64), Error> {
    let loads = [headers[1], headers[2], headers[3]];
    let expected_flags = [PF_R, PF_R | PF_X, PF_R | PF_W];
    for (load, flags) in loads.iter().zip(expected_flags) {
        if load.flags != flags || load.flags & (PF_W | PF_X) == (PF_W | PF_X) {
            return Err(Error::LoadFlags);
        }
        if load.alignment != PAGE_SIZE
            || !load.offset.is_multiple_of(PAGE_SIZE)
            || !load.virtual_address.is_multiple_of(PAGE_SIZE)
            || load.offset != load.virtual_address
        {
            return Err(Error::LoadAlignment);
        }
        if load.physical_address != 0 {
            return Err(Error::LoadAddress);
        }
        if load.file_size == 0
            || load.memory_size == 0
            || load.file_size > load.memory_size
            || !load.memory_size.is_multiple_of(PAGE_SIZE)
        {
            return Err(Error::SegmentSize);
        }
        let file_end = add(load.offset, load.file_size, Error::SegmentBounds)?;
        let memory_end = add(load.virtual_address, load.memory_size, Error::SegmentBounds)?;
        if file_end > bytes.len() as u64 || memory_end > MAX_IMAGE_BYTES {
            return Err(Error::SegmentBounds);
        }
    }
    if loads[0].virtual_address != 0 || loads[0].offset != 0 {
        return Err(Error::SegmentLayout);
    }
    if loads[0].file_size != loads[0].memory_size
        || loads[1].file_size != loads[1].memory_size
        || add(
            loads[0].virtual_address,
            loads[0].memory_size,
            Error::SegmentLayout,
        )? != loads[1].virtual_address
        || add(
            loads[1].virtual_address,
            loads[1].memory_size,
            Error::SegmentLayout,
        )? != loads[2].virtual_address
        || loads[0].file_size != loads[1].offset
        || add(loads[1].offset, loads[1].file_size, Error::SegmentLayout)? != loads[2].offset
    {
        return Err(Error::SegmentLayout);
    }
    let program_table_end = ELF_HEADER_BYTES
        .checked_add(PROGRAM_HEADER_BYTES * PROGRAM_HEADER_COUNT as u64)
        .ok_or(Error::ArithmeticOverflow)?;
    if loads[0].file_size < program_table_end {
        return Err(Error::FileCoverage);
    }
    if add(loads[2].offset, loads[2].file_size, Error::FileCoverage)? != bytes.len() as u64 {
        return Err(Error::FileCoverage);
    }
    let image_size = add(
        loads[2].virtual_address,
        loads[2].memory_size,
        Error::SegmentBounds,
    )?;
    if loads[2].memory_size < PAGE_SIZE * 2 || image_size > MAX_IMAGE_BYTES {
        return Err(Error::SegmentSize);
    }
    Ok((loads, image_size))
}

fn validate_dynamic_and_relro(
    bytes: &[u8],
    dynamic: ProgramHeader,
    relro: ProgramHeader,
    stack: ProgramHeader,
    writable: ProgramHeader,
) -> Result<(u64, u64, u64), Error> {
    if relro.flags != PF_R
        || relro.offset != writable.offset
        || relro.virtual_address != writable.virtual_address
        || relro.physical_address != 0
        || relro.file_size != relro.memory_size
        || relro.memory_size < PAGE_SIZE
        || !relro.memory_size.is_multiple_of(PAGE_SIZE)
        || relro.alignment != PAGE_SIZE
        || relro.memory_size >= writable.memory_size
        || relro.memory_size > writable.file_size
    {
        return Err(Error::RelroSegment);
    }
    if stack.flags != PF_R | PF_W
        || stack.offset != 0
        || stack.virtual_address != 0
        || stack.physical_address != 0
        || stack.file_size != 0
        || stack.memory_size != 0
        || stack.alignment != 16
    {
        return Err(Error::StackSegment);
    }
    if dynamic.flags != PF_R | PF_W
        || dynamic.offset != writable.offset
        || dynamic.virtual_address != writable.virtual_address
        || dynamic.physical_address != 0
        || dynamic.file_size != DYNAMIC_BYTES
        || dynamic.memory_size != DYNAMIC_BYTES
        || dynamic.alignment != 8
        || !range_contains(
            relro.virtual_address,
            relro.memory_size,
            dynamic.virtual_address,
            dynamic.memory_size,
        )
    {
        return Err(Error::DynamicSegment);
    }
    let dynamic_offset = to_usize(dynamic.offset, Error::DynamicSegment)?;
    let expected_tags = [DT_RELA, DT_RELASZ, DT_RELAENT, DT_NULL];
    let mut values = [0u64; DYNAMIC_ENTRY_COUNT as usize];
    for (index, expected_tag) in expected_tags.iter().enumerate() {
        let offset = dynamic_offset + index * DYNAMIC_ENTRY_BYTES as usize;
        if read_i64(bytes, offset, Error::DynamicSegment)? != *expected_tag {
            return Err(Error::DynamicOrder);
        }
        values[index] = read_u64(bytes, offset + 8, Error::DynamicSegment)?;
    }
    if values[3] != 0 {
        return Err(Error::DynamicEntry);
    }
    let relocation_address = values[0];
    let relocation_size = values[1];
    if values[2] != RELA_ENTRY_BYTES {
        return Err(Error::RelocationEntrySize);
    }
    if relocation_size == 0 || !relocation_size.is_multiple_of(RELA_ENTRY_BYTES) {
        return Err(Error::RelocationTable);
    }
    let relocation_count = relocation_size / RELA_ENTRY_BYTES;
    if relocation_count == 0 || relocation_count > MAX_RELOCATIONS as u64 {
        return Err(Error::RelocationCount);
    }
    if !relocation_address.is_multiple_of(8)
        || ranges_overlap(
            dynamic.virtual_address,
            dynamic.memory_size,
            relocation_address,
            relocation_size,
        )
        || !range_contains(
            relro.virtual_address,
            relro.memory_size,
            relocation_address,
            relocation_size,
        )
        || !range_contains(
            writable.virtual_address,
            writable.file_size,
            relocation_address,
            relocation_size,
        )
    {
        return Err(Error::RelocationTable);
    }
    Ok((relocation_address, relocation_size, relocation_count))
}

fn validate_relocations(context: RelocationContext<'_>) -> Result<(), Error> {
    let mut previous_target = None;
    for index in 0..context.relocation_count {
        let record_address = context
            .relocation_address
            .checked_add(
                index
                    .checked_mul(RELA_ENTRY_BYTES)
                    .ok_or(Error::RelocationTable)?,
            )
            .ok_or(Error::RelocationTable)?;
        let record_offset = to_usize(record_address, Error::RelocationTable)?;
        let target = read_u64(context.bytes, record_offset, Error::RelocationTable)?;
        let info = read_u64(context.bytes, record_offset + 8, Error::RelocationTable)?;
        let addend = read_i64(context.bytes, record_offset + 16, Error::RelocationTable)?;
        let relocation_type = info as u32;
        let symbol = info >> 32;
        if relocation_type != R_X86_64_RELATIVE {
            return Err(Error::RelocationType);
        }
        if symbol != 0 {
            return Err(Error::RelocationSymbol);
        }
        if previous_target.is_some_and(|previous| target <= previous) {
            return Err(Error::RelocationOrder);
        }
        previous_target = Some(target);
        if !target.is_multiple_of(8)
            || !range_contains(
                context.relro.virtual_address,
                context.relro.memory_size,
                target,
                8,
            )
            || ranges_overlap(
                context.dynamic.virtual_address,
                context.dynamic.memory_size,
                target,
                8,
            )
            || ranges_overlap(
                context.relocation_address,
                context.relocation_size,
                target,
                8,
            )
        {
            return Err(Error::RelocationTarget);
        }
        let target_offset = to_usize(target, Error::RelocationTarget)?;
        if context
            .bytes
            .get(target_offset..target_offset + 8)
            .ok_or(Error::RelocationTarget)?
            .iter()
            .any(|byte| *byte != 0)
        {
            return Err(Error::RelocationTarget);
        }
        let addend = u64::try_from(addend).map_err(|_| Error::RelocationAddend)?;
        if addend >= context.image_size
            || !context
                .loads
                .iter()
                .any(|load| range_contains(load.virtual_address, load.memory_size, addend, 1))
        {
            return Err(Error::RelocationAddend);
        }
        let value = add(context.virtual_base, addend, Error::RelocationValue)?;
        if value < context.virtual_base
            || value
                >= add(
                    context.virtual_base,
                    context.image_size,
                    Error::RelocationValue,
                )?
        {
            return Err(Error::RelocationValue);
        }
    }
    Ok(())
}

pub fn inspect(bytes: &[u8], physical_base: u64, virtual_base: u64) -> Result<ImagePlan, Error> {
    let (entry, headers) = validate_header(bytes)?;
    validate_phdr(headers[0])?;
    let (loads, image_size) = validate_loads(bytes, &headers)?;
    validate_base_addresses(physical_base, virtual_base, image_size)?;
    if !range_contains(loads[1].virtual_address, loads[1].file_size, entry, 1) {
        return Err(Error::EntryPoint);
    }
    let (relocation_address, relocation_size, relocation_count) =
        validate_dynamic_and_relro(bytes, headers[4], headers[5], headers[6], loads[2])?;
    validate_relocations(RelocationContext {
        bytes,
        relocation_address,
        relocation_size,
        relocation_count,
        dynamic: headers[4],
        relro: headers[5],
        loads: &loads,
        image_size,
        virtual_base,
    })?;

    let segments = [
        SegmentPlan {
            file_offset: to_u32(loads[0].offset)?,
            virtual_offset: to_u32(loads[0].virtual_address)?,
            file_size: to_u32(loads[0].file_size)?,
            memory_size: to_u32(loads[0].memory_size)?,
            permissions: Permissions::READ,
        },
        SegmentPlan {
            file_offset: to_u32(loads[1].offset)?,
            virtual_offset: to_u32(loads[1].virtual_address)?,
            file_size: to_u32(loads[1].file_size)?,
            memory_size: to_u32(loads[1].memory_size)?,
            permissions: Permissions::READ_EXECUTE,
        },
        SegmentPlan {
            file_offset: to_u32(loads[2].offset)?,
            virtual_offset: to_u32(loads[2].virtual_address)?,
            file_size: to_u32(loads[2].file_size)?,
            memory_size: to_u32(loads[2].memory_size)?,
            permissions: Permissions::READ_WRITE,
        },
    ];
    let relro_end = add(
        headers[5].virtual_address,
        headers[5].memory_size,
        Error::RelroSegment,
    )?;
    let writable_end = add(
        loads[2].virtual_address,
        loads[2].memory_size,
        Error::SegmentBounds,
    )?;
    let mappings = [
        MappingPlan {
            virtual_offset: to_u32(loads[0].virtual_address)?,
            memory_size: to_u32(loads[0].memory_size)?,
            permissions: Permissions::READ,
        },
        MappingPlan {
            virtual_offset: to_u32(loads[1].virtual_address)?,
            memory_size: to_u32(loads[1].memory_size)?,
            permissions: Permissions::READ_EXECUTE,
        },
        MappingPlan {
            virtual_offset: to_u32(headers[5].virtual_address)?,
            memory_size: to_u32(headers[5].memory_size)?,
            permissions: Permissions::READ,
        },
        MappingPlan {
            virtual_offset: to_u32(relro_end)?,
            memory_size: to_u32(writable_end - relro_end)?,
            permissions: Permissions::READ_WRITE,
        },
    ];
    Ok(ImagePlan {
        file_size: u32::try_from(bytes.len()).map_err(|_| Error::ArithmeticOverflow)?,
        image_size: to_u32(image_size)?,
        entry_offset: to_u32(entry)?,
        entry_virtual: add(virtual_base, entry, Error::EntryPoint)?,
        entry_physical: add(physical_base, entry, Error::EntryPoint)?,
        physical_base,
        virtual_base,
        relocation_count: to_u32(relocation_count)?,
        relro_offset: to_u32(headers[5].virtual_address)?,
        relro_size: to_u32(headers[5].memory_size)?,
        segments,
        mappings,
    })
}

pub fn load(
    bytes: &[u8],
    physical_base: u64,
    virtual_base: u64,
    destination: &mut [u8],
) -> Result<ImagePlan, Error> {
    let plan = inspect(bytes, physical_base, virtual_base)?;
    let image_size = plan.image_size as usize;
    if destination.len() < image_size {
        return Err(Error::OutputCapacity);
    }

    destination[..image_size].fill(0);
    for segment in plan.segments {
        let source_start = segment.file_offset as usize;
        let source_end = source_start + segment.file_size as usize;
        let target_start = segment.virtual_offset as usize;
        let target_end = target_start + segment.file_size as usize;
        destination[target_start..target_end].copy_from_slice(&bytes[source_start..source_end]);
    }

    let dynamic_offset = plan.segments[2].file_offset as usize;
    let relocation_address = read_u64(bytes, dynamic_offset + 8, Error::DynamicSegment)?;
    for index in 0..plan.relocation_count as u64 {
        let record_offset = (relocation_address + index * RELA_ENTRY_BYTES) as usize;
        let target = read_u64(bytes, record_offset, Error::RelocationTable)? as usize;
        let addend = read_i64(bytes, record_offset + 16, Error::RelocationTable)? as u64;
        let value = virtual_base + addend;
        destination[target..target + 8].copy_from_slice(&value.to_le_bytes());
    }
    Ok(plan)
}

pub fn fnv1a64(bytes: &[u8]) -> u64 {
    let mut value = 0xcbf2_9ce4_8422_2325u64;
    for byte in bytes {
        value ^= u64::from(*byte);
        value = value.wrapping_mul(0x0000_0100_0000_01b3);
    }
    value
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;
    use std::vec;

    fn write_u16(bytes: &mut [u8], offset: usize, value: u16) {
        bytes[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
    }

    fn write_u32(bytes: &mut [u8], offset: usize, value: u32) {
        bytes[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
    }

    fn write_u64(bytes: &mut [u8], offset: usize, value: u64) {
        bytes[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
    }

    fn phdr(bytes: &mut [u8], index: usize, values: [u64; 8]) {
        let base = ELF_HEADER_BYTES as usize + index * PROGRAM_HEADER_BYTES as usize;
        write_u32(bytes, base, values[0] as u32);
        write_u32(bytes, base + 4, values[1] as u32);
        for (field, value) in values[2..].iter().enumerate() {
            write_u64(bytes, base + 8 + field * 8, *value);
        }
    }

    fn fixture() -> std::vec::Vec<u8> {
        let mut bytes = vec![0u8; 0x3000];
        bytes[0..4].copy_from_slice(&[0x7f, b'E', b'L', b'F']);
        bytes[4] = 2;
        bytes[5] = 1;
        bytes[6] = 1;
        write_u16(&mut bytes, 16, 3);
        write_u16(&mut bytes, 18, 62);
        write_u32(&mut bytes, 20, 1);
        write_u64(&mut bytes, 24, 0x1000);
        write_u64(&mut bytes, 32, 64);
        write_u32(&mut bytes, 48, 0);
        write_u16(&mut bytes, 52, 64);
        write_u16(&mut bytes, 54, 56);
        write_u16(&mut bytes, 56, 7);
        phdr(&mut bytes, 0, [6, 4, 64, 64, 0, 392, 392, 8]);
        phdr(&mut bytes, 1, [1, 4, 0, 0, 0, 0x1000, 0x1000, 0x1000]);
        phdr(
            &mut bytes,
            2,
            [1, 5, 0x1000, 0x1000, 0, 0x1000, 0x1000, 0x1000],
        );
        phdr(
            &mut bytes,
            3,
            [1, 6, 0x2000, 0x2000, 0, 0x1000, 0x2000, 0x1000],
        );
        phdr(&mut bytes, 4, [2, 6, 0x2000, 0x2000, 0, 64, 64, 8]);
        phdr(
            &mut bytes,
            5,
            [0x6474_e552, 4, 0x2000, 0x2000, 0, 0x1000, 0x1000, 0x1000],
        );
        phdr(&mut bytes, 6, [0x6474_e551, 6, 0, 0, 0, 0, 0, 16]);
        bytes[0x1000..0x1008].copy_from_slice(&[0xfa, 0xf4, 0xeb, 0xfd, 0x50, 0x4b, 0x45, 0x4c]);
        write_u64(&mut bytes, 0x2000, DT_RELA as u64);
        write_u64(&mut bytes, 0x2008, 0x2040);
        write_u64(&mut bytes, 0x2010, DT_RELASZ as u64);
        write_u64(&mut bytes, 0x2018, 48);
        write_u64(&mut bytes, 0x2020, DT_RELAENT as u64);
        write_u64(&mut bytes, 0x2028, 24);
        write_u64(&mut bytes, 0x2030, DT_NULL as u64);
        write_u64(&mut bytes, 0x2038, 0);
        write_u64(&mut bytes, 0x2040, 0x2080);
        write_u64(&mut bytes, 0x2048, R_X86_64_RELATIVE as u64);
        write_u64(&mut bytes, 0x2050, 0x1000);
        write_u64(&mut bytes, 0x2058, 0x2088);
        write_u64(&mut bytes, 0x2060, R_X86_64_RELATIVE as u64);
        write_u64(&mut bytes, 0x2068, 0x3000);
        bytes
    }

    const PHYSICAL: u64 = 0x0200_0000;
    const VIRTUAL: u64 = MIN_VIRTUAL_BASE;

    #[test]
    fn exact_fixture_loads_and_relocates() {
        let bytes = fixture();
        let mut output = vec![0xa5; 0x4000];
        let plan = load(&bytes, PHYSICAL, VIRTUAL, &mut output).unwrap();
        assert_eq!(plan.file_size, 0x3000);
        assert_eq!(plan.image_size, 0x4000);
        assert_eq!(plan.entry_virtual, VIRTUAL + 0x1000);
        assert_eq!(plan.relocation_count, 2);
        assert_eq!(
            read_u64(&output, 0x2080, Error::RelocationTarget),
            Ok(VIRTUAL + 0x1000)
        );
        assert_eq!(
            read_u64(&output, 0x2088, Error::RelocationTarget),
            Ok(VIRTUAL + 0x3000)
        );
        assert!(output[0x3000..0x4000].iter().all(|byte| *byte == 0));
    }

    #[test]
    fn mapping_plan_is_page_exact_and_wx_free() {
        let plan = inspect(&fixture(), PHYSICAL, VIRTUAL).unwrap();
        assert_eq!(plan.mappings[0].permissions, Permissions::READ);
        assert_eq!(plan.mappings[1].permissions, Permissions::READ_EXECUTE);
        assert_eq!(plan.mappings[2].permissions, Permissions::READ);
        assert_eq!(plan.mappings[3].permissions, Permissions::READ_WRITE);
        assert!(plan.mappings.iter().all(|mapping| {
            !(mapping.permissions.write && mapping.permissions.execute)
                && u64::from(mapping.virtual_offset).is_multiple_of(PAGE_SIZE)
                && u64::from(mapping.memory_size).is_multiple_of(PAGE_SIZE)
        }));
    }

    #[test]
    fn invalid_input_never_mutates_destination() {
        let mut bytes = fixture();
        bytes[0] = 0;
        let mut output = vec![0xa5; 0x4000];
        assert_eq!(
            load(&bytes, PHYSICAL, VIRTUAL, &mut output),
            Err(Error::Magic)
        );
        assert!(output.iter().all(|byte| *byte == 0xa5));
    }

    #[test]
    fn short_capacity_never_mutates_destination() {
        let bytes = fixture();
        let mut output = vec![0xa5; 0x3fff];
        assert_eq!(
            load(&bytes, PHYSICAL, VIRTUAL, &mut output),
            Err(Error::OutputCapacity)
        );
        assert!(output.iter().all(|byte| *byte == 0xa5));
    }

    #[test]
    fn rejects_wrong_class_and_machine() {
        let mut bytes = fixture();
        bytes[4] = 1;
        assert_eq!(inspect(&bytes, PHYSICAL, VIRTUAL), Err(Error::Class));
        let mut bytes = fixture();
        write_u16(&mut bytes, 18, 3);
        assert_eq!(inspect(&bytes, PHYSICAL, VIRTUAL), Err(Error::Machine));
    }

    #[test]
    fn rejects_writable_executable_load() {
        let mut bytes = fixture();
        write_u32(&mut bytes, 64 + 2 * 56 + 4, 7);
        assert_eq!(inspect(&bytes, PHYSICAL, VIRTUAL), Err(Error::LoadFlags));
    }

    #[test]
    fn rejects_executable_stack() {
        let mut bytes = fixture();
        write_u32(&mut bytes, 64 + 6 * 56 + 4, 7);
        assert_eq!(inspect(&bytes, PHYSICAL, VIRTUAL), Err(Error::StackSegment));
    }

    #[test]
    fn rejects_import_style_relocation() {
        let mut bytes = fixture();
        write_u64(&mut bytes, 0x2048, (1u64 << 32) | R_X86_64_RELATIVE as u64);
        assert_eq!(
            inspect(&bytes, PHYSICAL, VIRTUAL),
            Err(Error::RelocationSymbol)
        );
    }

    #[test]
    fn rejects_text_relocation() {
        let mut bytes = fixture();
        write_u64(&mut bytes, 0x2040, 0x1080);
        assert_eq!(
            inspect(&bytes, PHYSICAL, VIRTUAL),
            Err(Error::RelocationTarget)
        );
    }

    #[test]
    fn rejects_negative_and_external_addends() {
        let mut bytes = fixture();
        write_u64(&mut bytes, 0x2050, u64::MAX);
        assert_eq!(
            inspect(&bytes, PHYSICAL, VIRTUAL),
            Err(Error::RelocationAddend)
        );
        let mut bytes = fixture();
        write_u64(&mut bytes, 0x2050, 0x4000);
        assert_eq!(
            inspect(&bytes, PHYSICAL, VIRTUAL),
            Err(Error::RelocationAddend)
        );
    }

    #[test]
    fn rejects_bad_physical_and_virtual_ranges() {
        assert_eq!(
            inspect(&fixture(), PHYSICAL + 1, VIRTUAL),
            Err(Error::PhysicalBase)
        );
        assert_eq!(
            inspect(&fixture(), PHYSICAL, VIRTUAL + PAGE_SIZE),
            Err(Error::VirtualBase)
        );
    }

    #[test]
    fn fnv_transport_fingerprint_is_stable() {
        assert_eq!(fnv1a64(b""), 0xcbf2_9ce4_8422_2325);
        assert_eq!(fnv1a64(b"hello"), 0xa430_d846_80aa_bd0b);
    }
}
