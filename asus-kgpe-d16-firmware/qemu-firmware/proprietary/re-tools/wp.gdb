set pagination off
set confirm off
set architecture arm
target remote :11234
watch *(unsigned int *)0xc03523a4
commands
  silent
  printf "FC-WRITE value=0x%08x  pc=0x%08x  lr=0x%08x\n", *(unsigned int *)0xc03523a4, $pc, $lr
  continue
end
continue
