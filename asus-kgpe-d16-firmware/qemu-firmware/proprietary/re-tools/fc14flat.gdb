set pagination off
set confirm off
set architecture arm
target remote :11234
# fc is deterministic at 0xc5793220; watch fc+0x14 = 0xc5793234 directly (flat, no nesting)
watch *(unsigned int *)0xc5793234
commands
  silent
  printf "FC14 val=0x%08x pc=0x%08x lr=0x%08x\n", *(unsigned int *)0xc5793234, $pc, $lr
  continue
end
continue
