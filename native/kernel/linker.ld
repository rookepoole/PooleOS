OUTPUT_FORMAT(elf64-x86-64)
OUTPUT_ARCH(i386:x86-64)
ENTRY(poole_kernel_entry)

PHDRS
{
  phdr PT_PHDR PHDRS FLAGS(4);
  ro PT_LOAD FILEHDR PHDRS FLAGS(4);
  text PT_LOAD FLAGS(5);
  data PT_LOAD FLAGS(6);
  dynamic PT_DYNAMIC FLAGS(6);
  relro PT_GNU_RELRO FLAGS(4);
  stack PT_GNU_STACK FLAGS(6);
}

SECTIONS
{
  . = SIZEOF_HEADERS;
  __poole_ro_start = 0;
  .gnu.hash : { *(.gnu.hash) } :ro
  .hash : { *(.hash) } :ro
  .dynsym : { *(.dynsym) } :ro
  .dynstr : { *(.dynstr) } :ro
  .rodata :
  {
    KEEP(*(.poole.manifest))
    *(.rodata .rodata.*)
    FILL(0)
    . = 0x9000;
  } :ro
  __poole_ro_end = .;

  . = 0x9000;
  __poole_text_start = .;
  .text :
  {
    KEEP(*(.text.poole_entry))
    *(.text .text.*)
    FILL(0)
    . = 0x3d000;
  } :text
  __poole_text_end = .;

  . = 0x3d000;
  __poole_data_start = .;
  .dynamic : { *(.dynamic) } :data :dynamic :relro
  .rela.dyn : { *(.rela.dyn) } :data :relro
  .data.rel.ro :
  {
    *(.data.rel.ro .data.rel.ro.*)
    *(.got .got.*)
  } :data :relro
  .relro.pad :
  {
    FILL(0)
    . = 0x44000;
  } :data :relro
  __poole_relro_end = .;

  . = 0x44000;
  .data : { *(.data .data.*) } :data
  .bss (NOLOAD) :
  {
    *(.bss .bss.*)
    *(COMMON)
    . = 0x4e000;
  } :data
  __poole_image_end = .;

  /DISCARD/ :
  {
    *(.comment)
    *(.eh_frame .eh_frame.*)
    *(.eh_frame_hdr)
    *(.gcc_except_table .gcc_except_table.*)
    *(.note .note.*)
  }
}

ASSERT((__poole_ro_end & 0xfff) == 0, "read-only segment must end on a page")
ASSERT((__poole_text_start & 0xfff) == 0, "text segment must start on a page")
ASSERT((__poole_text_end & 0xfff) == 0, "text segment must end on a page")
ASSERT((__poole_data_start & 0xfff) == 0, "data segment must start on a page")
ASSERT((__poole_relro_end & 0xfff) == 0, "RELRO must end on a page")
ASSERT((__poole_image_end & 0xfff) == 0, "image must end on a page")
ASSERT(__poole_ro_end == __poole_text_start, "read-only and text loads must be contiguous")
ASSERT(__poole_text_end == __poole_data_start, "text and data loads must be contiguous")
