set pagination off
set confirm off
set architecture arm
target remote :11234
# Force the eth0 gate flag non-zero: break at the cmp (0xc001a5bc), set r3=1
break *0xc001a5bc
commands
  silent
  set $r3 = 1
  printf "FORCED-GATE priv=0x%08x -> register path\n", $r5
  continue
end
continue
