OUTPUT_FORMAT(elf64-x86-64)
OUTPUT_ARCH(i386:x86-64)
ENTRY(_start)
PHDRS { code PT_LOAD FLAGS(5); }
SECTIONS
{
  . = 0;
  .text : {
    KEEP(*(.text.start))
    *(.text .text.*)
    *(.rodata .rodata.*)
    . = DEFINED(__poole_window_capacity) ? MAX(., 24576) : .;
    __poole_capacity_start = .;
    KEEP(*(.window_capacity))
    __poole_capacity_end = .;
  } :code
  .forbidden : {
    *(.data .data.* .bss .bss.* COMMON)
    *(.got .got.* .plt .plt.*)
    *(.dynamic .dynsym .dynstr .hash .gnu.hash)
  } :code
  .rela.forbidden : { *(.rela.*) } :code
  .rel.forbidden : { *(.rel.*) } :code
  /DISCARD/ : {
    *(.comment .note.* .eh_frame .eh_frame.* .eh_frame_hdr)
    *(.gcc_except_table .gcc_except_table.*)
  }
}
ASSERT(_start == 0, "startup must be the first byte")
ASSERT(SIZEOF(.text) > 0, "program is empty")
ASSERT(DEFINED(__poole_window_capacity) ? SIZEOF(.text) <= 28672 : SIZEOF(.text) <= 16384, "program exceeds its explicit code profile")
ASSERT(DEFINED(__poole_window_capacity) ? (__poole_capacity_start == 24576 && __poole_capacity_end > 24576) : (__poole_capacity_start == __poole_capacity_end), "capacity probe must execute on page seven only in PWCODE1")
ASSERT(SIZEOF(.forbidden) == 0, "program needs unsupported data or relocation")
ASSERT(SIZEOF(.rela.forbidden) == 0 && SIZEOF(.rel.forbidden) == 0, "program needs relocations")
