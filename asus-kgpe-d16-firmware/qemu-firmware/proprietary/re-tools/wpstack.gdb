set pagination off
set confirm off
set architecture arm
target remote :11234
watch *(unsigned int *)0xc03523a4
commands
  silent
  if *(unsigned int *)0xc03523a4 != 0
    printf "FC-CREATE value=0x%08x pc=0x%08x sp=0x%08x\n", *(unsigned int *)0xc03523a4, $pc, $sp
    x/24xw $sp
    detach
    quit
  end
  continue
end
continue
