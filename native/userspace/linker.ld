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
ASSERT(SIZEOF(.text) > 0 && SIZEOF(.text) <= 16384, "program exceeds four code pages")
ASSERT(SIZEOF(.forbidden) == 0, "program needs unsupported data or relocation")
ASSERT(SIZEOF(.rela.forbidden) == 0 && SIZEOF(.rel.forbidden) == 0, "program needs relocations")
