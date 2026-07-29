use poole_kmap::{Mapping, Permissions, Request, TABLE_ENTRIES, TableAddresses, populate};

const PHYSICAL: u64 = 0x0200_0000;
const VIRTUAL: u64 = poole_kmap::MIN_VIRTUAL_BASE;

fn main() {
    let mut mappings = [Mapping::EMPTY; poole_kmap::MAX_MAPPINGS];
    mappings[0] = Mapping {
        virtual_offset: 0,
        byte_count: 0x8000,
        permissions: Permissions::READ,
    };
    mappings[1] = Mapping {
        virtual_offset: 0x8000,
        byte_count: 0x2a000,
        permissions: Permissions::READ_EXECUTE,
    };
    mappings[2] = Mapping {
        virtual_offset: 0x32000,
        byte_count: 0x6000,
        permissions: Permissions::READ,
    };
    mappings[3] = Mapping {
        virtual_offset: 0x38000,
        byte_count: 0xa000,
        permissions: Permissions::READ_WRITE,
    };
    let request = Request {
        physical_base: PHYSICAL,
        virtual_base: VIRTUAL,
        image_bytes: 0x42000,
        page_count: 66,
        entry_virtual: VIRTUAL + 0x8000,
        mapping_count: 4,
        mappings,
        physical_address_bits: 48,
    };
    let addresses = TableAddresses::contiguous(0x0010_0000, 0x0300_0000)
        .expect("canonical PKMAP1 table addresses");
    let original = [0u64; TABLE_ENTRIES];
    let mut root = [0u64; TABLE_ENTRIES];
    let mut pdpt = [0u64; TABLE_ENTRIES];
    let mut directory = [0u64; TABLE_ENTRIES];
    let mut table = [0u64; TABLE_ENTRIES];
    let summary = populate(
        &request,
        addresses,
        &original,
        &mut root,
        &mut pdpt,
        &mut directory,
        &mut table,
    )
    .expect("canonical PKMAP1 request");
    println!(
        "{} PASS mappings={} pages={} ro={} rx={} rw={} wx={} pml4={} pdpt={} pd={} pt={} leaf_fnv1a64={:016X}",
        poole_kmap::CONTRACT_ID,
        request.mapping_count,
        summary.mapped_page_count,
        summary.read_only_page_count,
        summary.read_execute_page_count,
        summary.read_write_page_count,
        summary.writable_executable_page_count,
        summary.pml4_index,
        summary.pdpt_index,
        summary.page_directory_index,
        summary.first_page_table_index,
        summary.leaf_fingerprint
    );
}
