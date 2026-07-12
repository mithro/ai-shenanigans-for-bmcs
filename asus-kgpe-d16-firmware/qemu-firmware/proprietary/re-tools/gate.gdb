set pagination off
set confirm off
set architecture arm
target remote :11234
# eth0 gate: at 0xc001a5b8, r3 = config base ([priv+0x19c]); flag = [config+0x225]
break *0xc001a5b8
commands
  silent
  set $cfg = $r3
  set $flag = *(unsigned char *)($cfg + 0x225)
  printf "GATE priv=0x%08x cfg=0x%08x flag[+0x225]=0x%02x\n", $r5, $cfg, $flag
  printf "  cfg bytes +0x220..+0x230: "
  set $i = 0x220
  while $i <= 0x230
    printf "%02x ", *(unsigned char *)($cfg + $i)
    set $i = $i + 1
  end
  printf "\n"
  continue
end
continue
