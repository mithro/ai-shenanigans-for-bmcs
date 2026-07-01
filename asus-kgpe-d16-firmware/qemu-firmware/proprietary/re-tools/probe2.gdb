set pagination off
set confirm off
set architecture arm
target remote :11234
# -ENODEV bail #1 (0xc001a4a0)
break *0xc001a4a0
commands
  silent
  printf "BAIL -ENODEV @0xc001a4a0 (r3-based dispatch), lr=0x%08x\n", $lr
  continue
end
# "Fail to create %s file" bail (0xc001a828)
break *0xc001a828
commands
  silent
  printf "BAIL fail-create-file @0xc001a828\n"
  continue
end
# probe function return (0xc001a830) - read return value r0
break *0xc001a830
commands
  silent
  printf "PROBE-RETURN r0=0x%08x (0=success)\n", $r0
  continue
end
continue
