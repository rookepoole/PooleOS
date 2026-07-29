use core::cmp::min;

pub const CONTRACT_ID: &str = "PKIRQ1";
pub const MAX_PROCESSORS: usize = 32;
pub const MAX_IO_APICS: usize = 8;
pub const MAX_OVERRIDES: usize = 24;
pub const MAX_NMI_SOURCES: usize = 16;
pub const MAX_LOCAL_NMIS: usize = 32;
pub const TIMER_VECTOR: u8 = 0x40;
pub const IPI_VECTOR_FIRST: u8 = 0xe0;
pub const IPI_VECTOR_LAST: u8 = 0xef;
pub const APIC_ERROR_VECTOR: u8 = 0xf0;
pub const SPURIOUS_VECTOR: u8 = 0xff;
pub const APIC_BASE_ENABLE: u64 = 1 << 11;
pub const APIC_BASE_X2APIC: u64 = 1 << 10;
pub const APIC_BASE_BSP: u64 = 1 << 8;
pub const APIC_BASE_ADDRESS_MASK: u64 = 0x000f_ffff_ffff_f000;
const MADT_HEADER_BYTES: u64 = 44;
const HPET_TABLE_BYTES: u64 = 56;
const FEMTOSECONDS_PER_SECOND: u128 = 1_000_000_000_000_000;
const FEMTOSECONDS_PER_NANOSECOND: u128 = 1_000_000;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    PhysicalAccess,
    TableAddress,
    TableLength,
    TableShape,
    TableCapacity,
    ReservedBits,
    DuplicateProcessor,
    DuplicateIoApic,
    DuplicateOverride,
    DuplicateAddressOverride,
    ProcessorMissing,
    ApicUnsupported,
    X2ApicActive,
    ApicBase,
    ApicVersion,
    HpetAddressSpace,
    HpetRegisterShape,
    HpetPeriod,
    VectorRange,
    VectorOwned,
    CounterWidth,
    CounterRegression,
    CounterDelta,
    TimeOverflow,
    CalibrationSample,
    CalibrationRange,
    TimerCount,
}

impl Error {
    pub const fn label(self) -> &'static str {
        match self {
            Self::PhysicalAccess => "physical_access",
            Self::TableAddress => "table_address",
            Self::TableLength => "table_length",
            Self::TableShape => "table_shape",
            Self::TableCapacity => "table_capacity",
            Self::ReservedBits => "reserved_bits",
            Self::DuplicateProcessor => "duplicate_processor",
            Self::DuplicateIoApic => "duplicate_io_apic",
            Self::DuplicateOverride => "duplicate_override",
            Self::DuplicateAddressOverride => "duplicate_address_override",
            Self::ProcessorMissing => "processor_missing",
            Self::ApicUnsupported => "apic_unsupported",
            Self::X2ApicActive => "x2apic_active",
            Self::ApicBase => "apic_base",
            Self::ApicVersion => "apic_version",
            Self::HpetAddressSpace => "hpet_address_space",
            Self::HpetRegisterShape => "hpet_register_shape",
            Self::HpetPeriod => "hpet_period",
            Self::VectorRange => "vector_range",
            Self::VectorOwned => "vector_owned",
            Self::CounterWidth => "counter_width",
            Self::CounterRegression => "counter_regression",
            Self::CounterDelta => "counter_delta",
            Self::TimeOverflow => "time_overflow",
            Self::CalibrationSample => "calibration_sample",
            Self::CalibrationRange => "calibration_range",
            Self::TimerCount => "timer_count",
        }
    }
}

pub trait PhysicalRead {
    fn read_word(&mut self, page_address: u64, word_index: usize) -> Result<u64, Error>;
}

fn byte<A: PhysicalRead>(access: &mut A, address: u64) -> Result<u8, Error> {
    let page = address & !0xfff;
    let page_offset = usize::try_from(address & 0xfff).map_err(|_| Error::TableAddress)?;
    let word = access.read_word(page, page_offset / 8)?;
    Ok(((word >> ((page_offset % 8) * 8)) & 0xff) as u8)
}

fn u16_at<A: PhysicalRead>(access: &mut A, address: u64) -> Result<u16, Error> {
    Ok(u16::from_le_bytes([
        byte(access, address)?,
        byte(access, address + 1)?,
    ]))
}

fn u32_at<A: PhysicalRead>(access: &mut A, address: u64) -> Result<u32, Error> {
    Ok(u32::from_le_bytes([
        byte(access, address)?,
        byte(access, address + 1)?,
        byte(access, address + 2)?,
        byte(access, address + 3)?,
    ]))
}

fn u64_at<A: PhysicalRead>(access: &mut A, address: u64) -> Result<u64, Error> {
    Ok(u64::from_le_bytes([
        byte(access, address)?,
        byte(access, address + 1)?,
        byte(access, address + 2)?,
        byte(access, address + 3)?,
        byte(access, address + 4)?,
        byte(access, address + 5)?,
        byte(access, address + 6)?,
        byte(access, address + 7)?,
    ]))
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Processor {
    pub firmware_uid: u32,
    pub apic_id: u32,
    pub enabled: bool,
    pub online_capable: bool,
    pub x2apic: bool,
}

const EMPTY_PROCESSOR: Processor = Processor {
    firmware_uid: 0,
    apic_id: 0,
    enabled: false,
    online_capable: false,
    x2apic: false,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct IoApic {
    pub id: u8,
    pub physical_address: u32,
    pub global_interrupt_base: u32,
}

const EMPTY_IO_APIC: IoApic = IoApic {
    id: 0,
    physical_address: 0,
    global_interrupt_base: 0,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InterruptOverride {
    pub bus: u8,
    pub source: u8,
    pub global_interrupt: u32,
    pub flags: u16,
}

const EMPTY_OVERRIDE: InterruptOverride = InterruptOverride {
    bus: 0,
    source: 0,
    global_interrupt: 0,
    flags: 0,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct NmiSource {
    pub flags: u16,
    pub global_interrupt: u32,
}

const EMPTY_NMI_SOURCE: NmiSource = NmiSource {
    flags: 0,
    global_interrupt: 0,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LocalNmi {
    pub firmware_uid: u32,
    pub lint: u8,
    pub flags: u16,
    pub x2apic: bool,
}

const EMPTY_LOCAL_NMI: LocalNmi = LocalNmi {
    firmware_uid: 0,
    lint: 0,
    flags: 0,
    x2apic: false,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MadtTopology {
    pub local_apic_address: u64,
    pub pcat_compatible: bool,
    pub processor_count: usize,
    pub enabled_processor_count: usize,
    pub io_apic_count: usize,
    pub override_count: usize,
    pub nmi_source_count: usize,
    pub local_nmi_count: usize,
    pub unknown_structure_count: usize,
    pub address_override_count: usize,
    pub processors: [Processor; MAX_PROCESSORS],
    pub io_apics: [IoApic; MAX_IO_APICS],
    pub overrides: [InterruptOverride; MAX_OVERRIDES],
    pub nmi_sources: [NmiSource; MAX_NMI_SOURCES],
    pub local_nmis: [LocalNmi; MAX_LOCAL_NMIS],
}

impl MadtTopology {
    const fn empty() -> Self {
        Self {
            local_apic_address: 0,
            pcat_compatible: false,
            processor_count: 0,
            enabled_processor_count: 0,
            io_apic_count: 0,
            override_count: 0,
            nmi_source_count: 0,
            local_nmi_count: 0,
            unknown_structure_count: 0,
            address_override_count: 0,
            processors: [EMPTY_PROCESSOR; MAX_PROCESSORS],
            io_apics: [EMPTY_IO_APIC; MAX_IO_APICS],
            overrides: [EMPTY_OVERRIDE; MAX_OVERRIDES],
            nmi_sources: [EMPTY_NMI_SOURCE; MAX_NMI_SOURCES],
            local_nmis: [EMPTY_LOCAL_NMI; MAX_LOCAL_NMIS],
        }
    }

    pub fn processor(&self, apic_id: u32) -> Option<Processor> {
        self.processors[..self.processor_count]
            .iter()
            .copied()
            .find(|processor| processor.apic_id == apic_id)
    }
}

fn validate_mps_flags(flags: u16) -> Result<(), Error> {
    if flags & !0x000f != 0 || flags & 0x0003 == 0x0002 || flags & 0x000c == 0x0008 {
        return Err(Error::ReservedBits);
    }
    Ok(())
}

fn add_processor(topology: &mut MadtTopology, processor: Processor) -> Result<(), Error> {
    if topology.processors[..topology.processor_count]
        .iter()
        .any(|item| {
            item.apic_id == processor.apic_id || item.firmware_uid == processor.firmware_uid
        })
    {
        return Err(Error::DuplicateProcessor);
    }
    if topology.processor_count == MAX_PROCESSORS {
        return Err(Error::TableCapacity);
    }
    if processor.enabled {
        topology.enabled_processor_count += 1;
    }
    topology.processors[topology.processor_count] = processor;
    topology.processor_count += 1;
    Ok(())
}

pub fn parse_madt<A: PhysicalRead>(
    access: &mut A,
    physical_address: u64,
    byte_count: u64,
) -> Result<MadtTopology, Error> {
    if physical_address == 0 {
        return Err(Error::TableAddress);
    }
    if byte_count < MADT_HEADER_BYTES {
        return Err(Error::TableLength);
    }
    if [
        byte(access, physical_address)?,
        byte(access, physical_address + 1)?,
        byte(access, physical_address + 2)?,
        byte(access, physical_address + 3)?,
    ] != *b"APIC"
        || u64::from(u32_at(access, physical_address + 4)?) != byte_count
    {
        return Err(Error::TableShape);
    }
    let flags = u32_at(access, physical_address + 40)?;
    if flags & !1 != 0 {
        return Err(Error::ReservedBits);
    }
    let mut topology = MadtTopology::empty();
    topology.local_apic_address = u64::from(u32_at(access, physical_address + 36)?);
    topology.pcat_compatible = flags & 1 != 0;
    let mut cursor = MADT_HEADER_BYTES;
    while cursor < byte_count {
        if byte_count - cursor < 2 {
            return Err(Error::TableShape);
        }
        let structure = physical_address
            .checked_add(cursor)
            .ok_or(Error::TableAddress)?;
        let kind = byte(access, structure)?;
        let length = u64::from(byte(access, structure + 1)?);
        if length < 2 || length > byte_count - cursor {
            return Err(Error::TableShape);
        }
        match kind {
            0 if length == 8 => {
                let local_flags = u32_at(access, structure + 4)?;
                if local_flags & !3 != 0 {
                    return Err(Error::ReservedBits);
                }
                add_processor(
                    &mut topology,
                    Processor {
                        firmware_uid: u32::from(byte(access, structure + 2)?),
                        apic_id: u32::from(byte(access, structure + 3)?),
                        enabled: local_flags & 1 != 0,
                        online_capable: local_flags & 2 != 0,
                        x2apic: false,
                    },
                )?;
            }
            1 if length == 12 => {
                if byte(access, structure + 3)? != 0 {
                    return Err(Error::ReservedBits);
                }
                let item = IoApic {
                    id: byte(access, structure + 2)?,
                    physical_address: u32_at(access, structure + 4)?,
                    global_interrupt_base: u32_at(access, structure + 8)?,
                };
                if item.physical_address == 0 || item.physical_address & 0xfff != 0 {
                    return Err(Error::TableAddress);
                }
                if topology.io_apics[..topology.io_apic_count]
                    .iter()
                    .any(|existing| existing.id == item.id)
                {
                    return Err(Error::DuplicateIoApic);
                }
                if topology.io_apic_count == MAX_IO_APICS {
                    return Err(Error::TableCapacity);
                }
                topology.io_apics[topology.io_apic_count] = item;
                topology.io_apic_count += 1;
            }
            2 if length == 10 => {
                let item = InterruptOverride {
                    bus: byte(access, structure + 2)?,
                    source: byte(access, structure + 3)?,
                    global_interrupt: u32_at(access, structure + 4)?,
                    flags: u16_at(access, structure + 8)?,
                };
                validate_mps_flags(item.flags)?;
                if topology.overrides[..topology.override_count]
                    .iter()
                    .any(|existing| existing.bus == item.bus && existing.source == item.source)
                {
                    return Err(Error::DuplicateOverride);
                }
                if topology.override_count == MAX_OVERRIDES {
                    return Err(Error::TableCapacity);
                }
                topology.overrides[topology.override_count] = item;
                topology.override_count += 1;
            }
            3 if length == 8 => {
                let item = NmiSource {
                    flags: u16_at(access, structure + 2)?,
                    global_interrupt: u32_at(access, structure + 4)?,
                };
                validate_mps_flags(item.flags)?;
                if topology.nmi_source_count == MAX_NMI_SOURCES {
                    return Err(Error::TableCapacity);
                }
                topology.nmi_sources[topology.nmi_source_count] = item;
                topology.nmi_source_count += 1;
            }
            4 if length == 6 => {
                let flags = u16_at(access, structure + 3)?;
                validate_mps_flags(flags)?;
                let lint = byte(access, structure + 5)?;
                if lint > 1 {
                    return Err(Error::TableShape);
                }
                if topology.local_nmi_count == MAX_LOCAL_NMIS {
                    return Err(Error::TableCapacity);
                }
                topology.local_nmis[topology.local_nmi_count] = LocalNmi {
                    firmware_uid: u32::from(byte(access, structure + 2)?),
                    lint,
                    flags,
                    x2apic: false,
                };
                topology.local_nmi_count += 1;
            }
            5 if length == 12 => {
                if topology.address_override_count != 0 || u16_at(access, structure + 2)? != 0 {
                    return Err(if topology.address_override_count != 0 {
                        Error::DuplicateAddressOverride
                    } else {
                        Error::ReservedBits
                    });
                }
                let address = u64_at(access, structure + 4)?;
                if address == 0 || address & 0xfff != 0 {
                    return Err(Error::TableAddress);
                }
                topology.local_apic_address = address;
                topology.address_override_count = 1;
            }
            9 if length == 16 => {
                if u16_at(access, structure + 2)? != 0 {
                    return Err(Error::ReservedBits);
                }
                let local_flags = u32_at(access, structure + 8)?;
                if local_flags & !3 != 0 {
                    return Err(Error::ReservedBits);
                }
                add_processor(
                    &mut topology,
                    Processor {
                        firmware_uid: u32_at(access, structure + 12)?,
                        apic_id: u32_at(access, structure + 4)?,
                        enabled: local_flags & 1 != 0,
                        online_capable: local_flags & 2 != 0,
                        x2apic: true,
                    },
                )?;
            }
            10 if length == 12 => {
                if u16_at(access, structure + 2)? != 0 {
                    return Err(Error::ReservedBits);
                }
                let flags = u16_at(access, structure + 8)?;
                validate_mps_flags(flags)?;
                let lint = byte(access, structure + 10)?;
                if lint > 1 || byte(access, structure + 11)? != 0 {
                    return Err(Error::TableShape);
                }
                if topology.local_nmi_count == MAX_LOCAL_NMIS {
                    return Err(Error::TableCapacity);
                }
                topology.local_nmis[topology.local_nmi_count] = LocalNmi {
                    firmware_uid: u32_at(access, structure + 4)?,
                    lint,
                    flags,
                    x2apic: true,
                };
                topology.local_nmi_count += 1;
            }
            0 | 1 | 2 | 3 | 4 | 5 | 9 | 10 => return Err(Error::TableShape),
            _ => topology.unknown_structure_count += 1,
        }
        cursor = cursor.checked_add(length).ok_or(Error::TableLength)?;
    }
    if topology.local_apic_address == 0
        || topology.local_apic_address & 0xfff != 0
        || topology.processor_count == 0
        || topology.enabled_processor_count == 0
    {
        return Err(Error::TableShape);
    }
    Ok(topology)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct HpetDescription {
    pub hardware_revision: u8,
    pub comparator_count: u8,
    pub counter_64_bit_capable: bool,
    pub legacy_replacement_capable: bool,
    pub vendor_id: u16,
    pub physical_address: u64,
    pub sequence: u8,
    pub minimum_tick: u16,
    pub page_protection: u8,
}

pub fn parse_hpet<A: PhysicalRead>(
    access: &mut A,
    physical_address: u64,
    byte_count: u64,
) -> Result<HpetDescription, Error> {
    if physical_address == 0 {
        return Err(Error::TableAddress);
    }
    if byte_count < HPET_TABLE_BYTES {
        return Err(Error::TableLength);
    }
    if [
        byte(access, physical_address)?,
        byte(access, physical_address + 1)?,
        byte(access, physical_address + 2)?,
        byte(access, physical_address + 3)?,
    ] != *b"HPET"
        || u64::from(u32_at(access, physical_address + 4)?) != byte_count
    {
        return Err(Error::TableShape);
    }
    let block = u32_at(access, physical_address + 36)?;
    let address_space = byte(access, physical_address + 40)?;
    let register_width = byte(access, physical_address + 41)?;
    let register_offset = byte(access, physical_address + 42)?;
    let access_size = byte(access, physical_address + 43)?;
    let register_address = u64_at(access, physical_address + 44)?;
    if address_space != 0 {
        return Err(Error::HpetAddressSpace);
    }
    if !matches!(register_width, 0 | 64)
        || register_offset != 0
        || !matches!(access_size, 0 | 4)
        || register_address == 0
        || register_address & 7 != 0
        || register_address & 0xfff > 0xf08
    {
        return Err(Error::HpetRegisterShape);
    }
    let page_protection = byte(access, physical_address + 55)?;
    if page_protection > 2 {
        return Err(Error::ReservedBits);
    }
    Ok(HpetDescription {
        hardware_revision: block as u8,
        comparator_count: ((block >> 8) & 0x1f) as u8 + 1,
        counter_64_bit_capable: block & (1 << 13) != 0,
        legacy_replacement_capable: block & (1 << 15) != 0,
        vendor_id: (block >> 16) as u16,
        physical_address: register_address,
        sequence: byte(access, physical_address + 52)?,
        minimum_tick: u16_at(access, physical_address + 53)?,
        page_protection,
    })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CpuApicObservation {
    pub apic_supported: bool,
    pub x2apic_supported: bool,
    pub initial_apic_id: u32,
    pub physical_address_bits: u8,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ApicDiscovery {
    pub physical_address: u64,
    pub apic_id: u32,
    pub bsp: bool,
    pub globally_enabled: bool,
    pub version: u8,
    pub max_lvt_entry: u8,
}

pub fn validate_apic_discovery(
    topology: &MadtTopology,
    cpu: CpuApicObservation,
    apic_base_msr: u64,
    id_register: u32,
    version_register: u32,
) -> Result<ApicDiscovery, Error> {
    if !cpu.apic_supported {
        return Err(Error::ApicUnsupported);
    }
    if !(36..=52).contains(&cpu.physical_address_bits) {
        return Err(Error::ApicBase);
    }
    if apic_base_msr & APIC_BASE_X2APIC != 0 {
        return Err(Error::X2ApicActive);
    }
    let address = apic_base_msr & APIC_BASE_ADDRESS_MASK;
    let width_mask = (1u64 << cpu.physical_address_bits) - 1;
    if address == 0 || address & !width_mask != 0 || address != topology.local_apic_address {
        return Err(Error::ApicBase);
    }
    let apic_id = id_register >> 24;
    if apic_id != cpu.initial_apic_id
        || !topology
            .processor(apic_id)
            .is_some_and(|processor| processor.enabled && !processor.x2apic)
    {
        return Err(Error::ProcessorMissing);
    }
    let version = version_register as u8;
    let max_lvt_entry = ((version_register >> 16) & 0xff) as u8;
    if version < 0x10 || max_lvt_entry < 3 || version_register & 0xff00_e000 != 0 {
        return Err(Error::ApicVersion);
    }
    Ok(ApicDiscovery {
        physical_address: address,
        apic_id,
        bsp: apic_base_msr & APIC_BASE_BSP != 0,
        globally_enabled: apic_base_msr & APIC_BASE_ENABLE != 0,
        version,
        max_lvt_entry,
    })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum VectorOwner {
    Free,
    Exception,
    Timer,
    FutureIpi,
    ApicError,
    Spurious,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct VectorLedger {
    owners: [VectorOwner; 256],
    owned_count: u16,
}

impl VectorLedger {
    pub fn new() -> Result<Self, Error> {
        let mut value = Self {
            owners: [VectorOwner::Free; 256],
            owned_count: 0,
        };
        for vector in 0..=31u8 {
            value.reserve(vector, VectorOwner::Exception)?;
        }
        value.reserve(TIMER_VECTOR, VectorOwner::Timer)?;
        for vector in IPI_VECTOR_FIRST..=IPI_VECTOR_LAST {
            value.reserve(vector, VectorOwner::FutureIpi)?;
        }
        value.reserve(APIC_ERROR_VECTOR, VectorOwner::ApicError)?;
        value.reserve(SPURIOUS_VECTOR, VectorOwner::Spurious)?;
        Ok(value)
    }

    pub fn reserve(&mut self, vector: u8, owner: VectorOwner) -> Result<(), Error> {
        if owner == VectorOwner::Free {
            return Err(Error::VectorRange);
        }
        let slot = &mut self.owners[usize::from(vector)];
        if *slot != VectorOwner::Free {
            return Err(Error::VectorOwned);
        }
        *slot = owner;
        self.owned_count = self.owned_count.checked_add(1).ok_or(Error::VectorRange)?;
        Ok(())
    }

    pub const fn owner(&self, vector: u8) -> VectorOwner {
        self.owners[vector as usize]
    }

    pub const fn owned_count(&self) -> u16 {
        self.owned_count
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct HpetClock {
    counter_bits: u8,
    period_femtoseconds: u64,
    mask: u64,
    last_raw: u64,
    elapsed_ticks: u128,
    max_sample_delta: u64,
}

impl HpetClock {
    pub fn new(
        counter_bits: u8,
        period_femtoseconds: u64,
        initial_raw: u64,
        max_sample_delta: u64,
    ) -> Result<Self, Error> {
        if !matches!(counter_bits, 32 | 64) {
            return Err(Error::CounterWidth);
        }
        if !(100_000..=100_000_000).contains(&period_femtoseconds) {
            return Err(Error::HpetPeriod);
        }
        let mask = if counter_bits == 64 {
            u64::MAX
        } else {
            u64::from(u32::MAX)
        };
        if initial_raw & !mask != 0 || max_sample_delta == 0 || max_sample_delta > mask / 2 {
            return Err(Error::CounterDelta);
        }
        Ok(Self {
            counter_bits,
            period_femtoseconds,
            mask,
            last_raw: initial_raw,
            elapsed_ticks: 0,
            max_sample_delta,
        })
    }

    pub fn sample(&mut self, raw: u64) -> Result<u64, Error> {
        if raw & !self.mask != 0 {
            return Err(Error::CounterWidth);
        }
        let delta = raw.wrapping_sub(self.last_raw) & self.mask;
        if delta == 0 || delta > self.max_sample_delta {
            return Err(if raw < self.last_raw && self.counter_bits == 64 {
                Error::CounterRegression
            } else {
                Error::CounterDelta
            });
        }
        self.elapsed_ticks = self
            .elapsed_ticks
            .checked_add(u128::from(delta))
            .ok_or(Error::TimeOverflow)?;
        self.last_raw = raw;
        let nanos = self
            .elapsed_ticks
            .checked_mul(u128::from(self.period_femtoseconds))
            .ok_or(Error::TimeOverflow)?
            / FEMTOSECONDS_PER_NANOSECOND;
        u64::try_from(nanos).map_err(|_| Error::TimeOverflow)
    }

    pub const fn elapsed_ticks(&self) -> u128 {
        self.elapsed_ticks
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ApicTimerCalibration {
    pub hpet_ticks: u64,
    pub elapsed_apic_ticks: u64,
    pub sample_nanoseconds: u64,
    pub apic_ticks_per_second: u64,
}

pub fn calibrate_apic_timer(
    initial_count: u32,
    current_count: u32,
    hpet_ticks: u64,
    hpet_period_femtoseconds: u64,
) -> Result<ApicTimerCalibration, Error> {
    if current_count >= initial_count || hpet_ticks == 0 {
        return Err(Error::CalibrationSample);
    }
    if !(100_000..=100_000_000).contains(&hpet_period_femtoseconds) {
        return Err(Error::HpetPeriod);
    }
    let elapsed_apic_ticks = u64::from(initial_count - current_count);
    let sample_femtoseconds = u128::from(hpet_ticks)
        .checked_mul(u128::from(hpet_period_femtoseconds))
        .ok_or(Error::TimeOverflow)?;
    let sample_nanoseconds = sample_femtoseconds / FEMTOSECONDS_PER_NANOSECOND;
    if !(1_000_000..=1_000_000_000).contains(&sample_nanoseconds) {
        return Err(Error::CalibrationRange);
    }
    let frequency = u128::from(elapsed_apic_ticks)
        .checked_mul(FEMTOSECONDS_PER_SECOND)
        .ok_or(Error::TimeOverflow)?
        / sample_femtoseconds;
    if !(100_000..=10_000_000_000).contains(&frequency) {
        return Err(Error::CalibrationRange);
    }
    Ok(ApicTimerCalibration {
        hpet_ticks,
        elapsed_apic_ticks,
        sample_nanoseconds: u64::try_from(sample_nanoseconds).map_err(|_| Error::TimeOverflow)?,
        apic_ticks_per_second: u64::try_from(frequency).map_err(|_| Error::TimeOverflow)?,
    })
}

pub fn timer_initial_count(frequency: u64, interval_nanoseconds: u64) -> Result<u32, Error> {
    if frequency == 0 || interval_nanoseconds == 0 {
        return Err(Error::TimerCount);
    }
    let count = u128::from(frequency)
        .checked_mul(u128::from(interval_nanoseconds))
        .ok_or(Error::TimeOverflow)?
        / 1_000_000_000;
    u32::try_from(min(count.max(1), u128::from(u32::MAX))).map_err(|_| Error::TimerCount)
}

#[cfg(test)]
mod tests {
    extern crate std;

    use std::vec;
    use std::vec::Vec;

    use super::*;

    struct Bytes {
        base: u64,
        data: Vec<u8>,
    }

    impl PhysicalRead for Bytes {
        fn read_word(&mut self, page_address: u64, word_index: usize) -> Result<u64, Error> {
            let address = page_address
                .checked_add((word_index * 8) as u64)
                .ok_or(Error::PhysicalAccess)?;
            let offset = usize::try_from(
                address
                    .checked_sub(self.base)
                    .ok_or(Error::PhysicalAccess)?,
            )
            .map_err(|_| Error::PhysicalAccess)?;
            let mut value = [0u8; 8];
            value.copy_from_slice(
                self.data
                    .get(offset..offset + 8)
                    .ok_or(Error::PhysicalAccess)?,
            );
            Ok(u64::from_le_bytes(value))
        }
    }

    fn table(signature: &[u8; 4], length: usize) -> Bytes {
        let mut data = vec![0u8; (length + 7) & !7];
        data[..4].copy_from_slice(signature);
        data[4..8].copy_from_slice(&(length as u32).to_le_bytes());
        Bytes { base: 0x1000, data }
    }

    fn push_entry(bytes: &mut Bytes, entry: &[u8]) {
        let old_length = u32::from_le_bytes(bytes.data[4..8].try_into().unwrap()) as usize;
        let new_length = old_length + entry.len();
        bytes.data.resize((new_length + 7) & !7, 0);
        bytes.data[old_length..new_length].copy_from_slice(entry);
        bytes.data[4..8].copy_from_slice(&(new_length as u32).to_le_bytes());
    }

    #[test]
    fn parses_complete_madt_topology_and_override() {
        let mut bytes = table(b"APIC", 44);
        bytes.data[36..40].copy_from_slice(&0xfee0_0000u32.to_le_bytes());
        bytes.data[40..44].copy_from_slice(&1u32.to_le_bytes());
        push_entry(&mut bytes, &[0, 8, 0, 2, 1, 0, 0, 0]);
        push_entry(&mut bytes, &[1, 12, 3, 0, 0, 0, 192, 254, 0, 0, 0, 0]);
        push_entry(&mut bytes, &[2, 10, 0, 0, 2, 0, 0, 0, 0, 0]);
        push_entry(&mut bytes, &[4, 6, 0xff, 0, 0, 1]);
        push_entry(&mut bytes, &[0x7f, 4, 0, 0]);
        let length = u64::from(u32::from_le_bytes(bytes.data[4..8].try_into().unwrap()));
        let topology = parse_madt(&mut bytes, 0x1000, length).unwrap();
        assert_eq!(1, topology.processor_count);
        assert_eq!(1, topology.enabled_processor_count);
        assert_eq!(1, topology.io_apic_count);
        assert_eq!(1, topology.override_count);
        assert_eq!(1, topology.local_nmi_count);
        assert_eq!(1, topology.unknown_structure_count);
        assert_eq!(
            Some(Processor {
                firmware_uid: 0,
                apic_id: 2,
                enabled: true,
                online_capable: false,
                x2apic: false
            }),
            topology.processor(2)
        );
    }

    #[test]
    fn parses_x2apic_and_address_override() {
        let mut bytes = table(b"APIC", 44);
        bytes.data[36..40].copy_from_slice(&0xfee0_0000u32.to_le_bytes());
        push_entry(&mut bytes, &[5, 12, 0, 0, 0, 0, 0xe0, 0xfe, 0, 0, 0, 0]);
        push_entry(
            &mut bytes,
            &[9, 16, 0, 0, 4, 3, 2, 1, 1, 0, 0, 0, 9, 0, 0, 0],
        );
        let length = u64::from(u32::from_le_bytes(bytes.data[4..8].try_into().unwrap()));
        let topology = parse_madt(&mut bytes, 0x1000, length).unwrap();
        assert_eq!(1, topology.address_override_count);
        assert_eq!(0xfee0_0000, topology.local_apic_address);
        assert!(topology.processors[0].x2apic);
        assert_eq!(0x0102_0304, topology.processors[0].apic_id);
    }

    #[test]
    fn rejects_malformed_duplicate_and_reserved_madt_entries() {
        let mut short = table(b"APIC", 44);
        short.data[36..40].copy_from_slice(&0xfee0_0000u32.to_le_bytes());
        push_entry(&mut short, &[0, 7, 0, 0, 1, 0, 0]);
        let length = u64::from(u32::from_le_bytes(short.data[4..8].try_into().unwrap()));
        assert_eq!(
            Err(Error::TableShape),
            parse_madt(&mut short, 0x1000, length)
        );

        let mut duplicate = table(b"APIC", 44);
        duplicate.data[36..40].copy_from_slice(&0xfee0_0000u32.to_le_bytes());
        push_entry(&mut duplicate, &[0, 8, 0, 0, 1, 0, 0, 0]);
        push_entry(&mut duplicate, &[0, 8, 1, 0, 1, 0, 0, 0]);
        let length = u64::from(u32::from_le_bytes(duplicate.data[4..8].try_into().unwrap()));
        assert_eq!(
            Err(Error::DuplicateProcessor),
            parse_madt(&mut duplicate, 0x1000, length)
        );

        let mut reserved = table(b"APIC", 44);
        reserved.data[36..40].copy_from_slice(&0xfee0_0000u32.to_le_bytes());
        reserved.data[40..44].copy_from_slice(&2u32.to_le_bytes());
        assert_eq!(
            Err(Error::ReservedBits),
            parse_madt(&mut reserved, 0x1000, 44)
        );
    }

    #[test]
    fn parses_hpet_gas_and_rejects_io_space() {
        let mut bytes = table(b"HPET", 56);
        let block = 1u32 | (2 << 8) | (1 << 13) | (0x8086 << 16);
        bytes.data[36..40].copy_from_slice(&block.to_le_bytes());
        bytes.data[41] = 64;
        bytes.data[43] = 4;
        bytes.data[44..52].copy_from_slice(&0xfed0_0000u64.to_le_bytes());
        bytes.data[53..55].copy_from_slice(&128u16.to_le_bytes());
        let parsed = parse_hpet(&mut bytes, 0x1000, 56).unwrap();
        assert_eq!(3, parsed.comparator_count);
        assert!(parsed.counter_64_bit_capable);
        assert_eq!(0x8086, parsed.vendor_id);
        bytes.data[40] = 1;
        assert_eq!(
            Err(Error::HpetAddressSpace),
            parse_hpet(&mut bytes, 0x1000, 56)
        );
    }

    #[test]
    fn validates_apic_identity_version_and_madt_membership() {
        let mut topology = MadtTopology::empty();
        topology.local_apic_address = 0xfee0_0000;
        topology.processors[0] = Processor {
            firmware_uid: 0,
            apic_id: 7,
            enabled: true,
            online_capable: false,
            x2apic: false,
        };
        topology.processor_count = 1;
        topology.enabled_processor_count = 1;
        let cpu = CpuApicObservation {
            apic_supported: true,
            x2apic_supported: true,
            initial_apic_id: 7,
            physical_address_bits: 48,
        };
        let discovery =
            validate_apic_discovery(&topology, cpu, 0xfee0_0900, 7 << 24, 0x0005_0014).unwrap();
        assert!(discovery.bsp);
        assert!(discovery.globally_enabled);
        assert_eq!(5, discovery.max_lvt_entry);
        assert_eq!(
            Err(Error::X2ApicActive),
            validate_apic_discovery(&topology, cpu, 0xfee0_0d00, 7 << 24, 0x0005_0014)
        );
        assert_eq!(
            Err(Error::ProcessorMissing),
            validate_apic_discovery(&topology, cpu, 0xfee0_0900, 8 << 24, 0x0005_0014)
        );
    }

    #[test]
    fn vector_ledger_rejects_collisions_and_tracks_future_ipis() {
        let mut ledger = VectorLedger::new().unwrap();
        assert_eq!(VectorOwner::Timer, ledger.owner(TIMER_VECTOR));
        assert_eq!(VectorOwner::FutureIpi, ledger.owner(IPI_VECTOR_FIRST));
        assert_eq!(VectorOwner::ApicError, ledger.owner(APIC_ERROR_VECTOR));
        assert_eq!(51, ledger.owned_count());
        assert_eq!(
            Err(Error::VectorOwned),
            ledger.reserve(TIMER_VECTOR, VectorOwner::Timer)
        );
        assert_eq!(
            Err(Error::VectorRange),
            ledger.reserve(0x70, VectorOwner::Free)
        );
        ledger.reserve(0x70, VectorOwner::Timer).unwrap();
        assert_eq!(52, ledger.owned_count());
    }

    #[test]
    fn hpet_clock_handles_one_32_bit_wrap_and_rejects_ambiguous_delta() {
        let mut clock = HpetClock::new(32, 100_000_000, 0xffff_fff0, 1_000).unwrap();
        assert_eq!(3_200, clock.sample(0x10).unwrap());
        assert_eq!(32, clock.elapsed_ticks());
        assert_eq!(Err(Error::CounterDelta), clock.sample(0x1000));
        let mut wide = HpetClock::new(64, 100_000_000, 100, 1_000).unwrap();
        assert_eq!(Err(Error::CounterRegression), wide.sample(99));
    }

    #[test]
    fn apic_calibration_and_timer_count_are_checked() {
        let calibration =
            calibrate_apic_timer(0xffff_ffff, 0xffff_0000, 100_000, 100_000_000).unwrap();
        assert_eq!(10_000_000, calibration.sample_nanoseconds);
        assert_eq!(6_553_500, calibration.apic_ticks_per_second);
        assert_eq!(
            65_535,
            timer_initial_count(calibration.apic_ticks_per_second, 10_000_000).unwrap()
        );
        assert_eq!(
            Err(Error::CalibrationSample),
            calibrate_apic_timer(10, 10, 1, 100_000_000)
        );
    }
}
