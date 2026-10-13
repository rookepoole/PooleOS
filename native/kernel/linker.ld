OUTPUT_FORMAT(elf64-x86-64)
OUTPUT_ARCH(i386:x86-64)
ENTRY(poole_kernel_entry)

/* Only the reviewed file-session build supplies this absolute selector. */
__poole_ro_capacity = DEFINED(__poole_files_profile) ? 0xE000 : 0xD000;

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
    __poole_ro_used_end = .;
    FILL(0)
    . = __poole_ro_capacity;
  } :ro
  __poole_ro_end = .;

  . = __poole_ro_capacity;
  __poole_text_start = .;
  .text :
  {
    KEEP(*(.text.poole_entry))
    *(.text .text.*)
    __poole_text_used_end = .;
    FILL(0)
    . = ALIGN(0x1000);
  } :text
  __poole_text_end = .;

  . = __poole_text_end;
  __poole_data_start = .;
  .dynamic : { *(.dynamic) } :data :dynamic :relro
  .rela.dyn : { *(.rela.dyn) } :data :relro
  .data.rel.ro :
  {
    *(.data.rel.ro .data.rel.ro.*)
    *(.got .got.*)
    __poole_relro_used_end = .;
  } :data :relro
  .relro.pad :
  {
    FILL(0)
    . = ALIGN(0x1000);
  } :data :relro
  __poole_relro_end = .;

  . = __poole_relro_end;
  .data : { *(.data .data.*) __poole_data_used_end = .; } :data
  .bss (NOLOAD) :
  {
    *(.bss .bss.*)
    *(COMMON)
    __poole_bss_used_end = .;
    . = ALIGN(0x1000);
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
ASSERT(__poole_image_end <= 0xD0000, "image must fit the 208-page bootstrap kernel capacity")
