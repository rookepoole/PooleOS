use poole_kmap::{
    HANDOFF_CAPACITY_BYTES, Mapping, Permissions, Request, RetainedRequest, STACK_PAGE_COUNT,
    TABLE_ENTRIES, TableAddresses, populate_retained,
};

const PHYSICAL: u64 = 0x0200_0000;
const VIRTUAL: u64 = poole_kmap::MIN_VIRTUAL_BASE;

fn main() {
    let mut mappings = [Mapping::EMPTY; poole_kmap::MAX_MAPPINGS];
    mappings[0] = Mapping {
        virtual_offset: 0,
        byte_count: 0x9000,
        permissions: Permissions::READ,
    };
    mappings[1] = Mapping {
        virtual_offset: 0x9000,
        byte_count: 0x34000,
        permissions: Permissions::READ_EXECUTE,
    };
    mappings[2] = Mapping {
        virtual_offset: 0x3d000,
        byte_count: 0x7000,
        permissions: Permissions::READ,
    };
    mappings[3] = Mapping {
        virtual_offset: 0x44000,
        byte_count: 0xa000,
        permissions: Permissions::READ_WRITE,
    };
    let request = Request {
        physical_base: PHYSICAL,
        virtual_base: VIRTUAL,
        image_bytes: 0x4e000,
        page_count: 78,
        entry_virtual: VIRTUAL + 0x9000,
        mapping_count: 4,
        mappings,
        physical_address_bits: 48,
    };
    let retained = RetainedRequest {
        stack_physical_base: 0x0400_0000,
        stack_page_count: STACK_PAGE_COUNT as u32,
        handoff_physical_base: 0x0500_0000,
        handoff_capacity_bytes: HANDOFF_CAPACITY_BYTES as u32,
    };
    let addresses = TableAddresses::contiguous(0x0010_0000, 0x0300_0000)
        .expect("canonical PKMAP2 table addresses");
    let original = [0u64; TABLE_ENTRIES];
    let mut root = [0u64; TABLE_ENTRIES];
    let mut pdpt = [0u64; TABLE_ENTRIES];
    let mut directory = [0u64; TABLE_ENTRIES];
    let mut table = [0u64; TABLE_ENTRIES];
    let summary = populate_retained(
        &request,
        retained,
        addresses,
        &original,
        &mut root,
        &mut pdpt,
        &mut directory,
        &mut table,
    )
    .expect("canonical PKMAP2 request");
    println!(
        "{} PASS kernel_pages={} stack_pages={} handoff_pages={} guards={} total_pages={} stack_pt={} handoff_pt={} retained_fnv1a64={:016X}",
        poole_kmap::RETAINED_CONTRACT_ID,
        summary.kernel.mapped_page_count,
        summary.stack_page_count,
        summary.handoff_page_count,
        summary.guard_page_count,
        summary.total_mapped_page_count,
        summary.stack_first_page_table_index,
        summary.handoff_first_page_table_index,
        summary.retained_leaf_fingerprint,
    );
}
