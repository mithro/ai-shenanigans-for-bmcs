#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Re-boot the F-IMG2 image and (1) cleanly capture SOL info/activate after an
IPMI warmup (netipmid socket-activation races on ARM926, per F5), and (2)
diagnose the FRU inventory population over SSH."""
import argparse, os, subprocess, sys, time

SSH_OPTS = ["-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
            "-o","ConnectTimeout=10","-o","LogLevel=ERROR"]

def tail(path, markers, deadline):
    seen=b""; pos=0
    while time.time()<deadline:
        if os.path.exists(path):
            with open(path,"rb") as f:
                f.seek(pos); c=f.read(); pos=f.tell()
            seen+=c
            for m in markers:
                if m.encode() in seen: return m
        time.sleep(1.0)
    return None

def ipmi(port,args,pw,timeout=30):
    cmd=["ipmitool","-I","lanplus","-H","127.0.0.1","-p",str(port),"-U","root",
         "-P",pw,"-C","17"]+args
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
        return p.returncode,p.stdout.decode("utf-8","replace")
    except subprocess.TimeoutExpired as e:
        return 124,(e.stdout or b"").decode("utf-8","replace")+f"\n[timeout {timeout}s]"

def ipmi_retry(port,args,pw,tries=6,timeout=25):
    last=(1,"")
    for i in range(tries):
        rc,out=ipmi(port,args,pw,timeout)
        # strip RAKP retry noise; success = rc 0 or a real IPMI body
        if rc==0 and "Error: " not in out.splitlines()[-1] if out.splitlines() else rc==0:
            return rc,out
        if rc==0:
            return rc,out
        last=(rc,out); time.sleep(4)
    return last

def ssh(port,pw,cmd,timeout=45):
    c=["sshpass","-p",pw,"ssh"]+SSH_OPTS+["-p",str(port),"root@127.0.0.1",cmd]
    try:
        p=subprocess.run(c,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
        return p.returncode,p.stdout.decode("utf-8","replace")
    except subprocess.TimeoutExpired as e:
        return 124,(e.stdout or b"").decode("utf-8","replace")

def save(evd,slug,hdr,body):
    os.makedirs(evd,exist_ok=True)
    with open(os.path.join(evd,f"{slug}.txt"),"w") as f: f.write(hdr+"\n\n"+body)
    print(f"[evidence] {slug}.txt ({len(body)}b)")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--qemu",required=True); ap.add_argument("--kernel",required=True)
    ap.add_argument("--dtb",required=True); ap.add_argument("--nfsroot",required=True)
    ap.add_argument("--mem",type=int,default=256)
    ap.add_argument("--ssh-port",type=int,default=2372); ap.add_argument("--ipmi-port",type=int,default=16773)
    ap.add_argument("--password",default="0penBmc"); ap.add_argument("--boot-timeout",type=int,default=1500)
    ap.add_argument("--evidence-dir",default="evidence/img2"); ap.add_argument("--serial-log",required=True)
    a=ap.parse_args()
    lp=a.serial_log
    if os.path.exists(lp): os.remove(lp)
    append=(f"console=ttyS4,115200n8 mem={a.mem}M root=/dev/nfs rw ip=dhcp "
            f"nfsroot={a.nfsroot},vers=3,tcp,nolock")
    hostfwd=(f"user,model=ftgmac100,hostfwd=tcp::{a.ssh_port}-:22,"
             f"hostfwd=udp::{a.ipmi_port}-:623")
    cmd=[a.qemu,"-M","kgpe-d16-bmc","-m",str(a.mem),"-nographic","-monitor","none",
         "-serial",f"file:{lp}","-nic",hostfwd,"-kernel",a.kernel,"-dtb",a.dtb,"-append",append]
    print("boot:"," ".join(cmd))
    q=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
    dl=time.time()+a.boot_timeout
    try:
        tail(lp,["VFS: Mounted root","Mounted root (nfs"],dl)
        print("[nfs] mounted; waiting for login/services")
        tail(lp,["login:","Startup finished","Started Network IPMI"],min(time.time()+240,dl))
        # SSH warmup
        while time.time()<dl:
            rc,out=ssh(a.ssh_port,a.password,"echo READY")
            if rc==0 and "READY" in out: print("[ssh] up"); break
            time.sleep(6)
        # IPMI warmup (netipmid socket-activation race)
        print("[ipmi] warming up netipmid ...")
        for _ in range(15):
            rc,out=ipmi(a.ipmi_port,["mc","info"],a.password,15)
            if rc==0 and "Device ID" in out: print("[ipmi] netipmid ready"); break
            time.sleep(5)

        # --- (a) SOL clean capture (retried) ---
        rc,out=ipmi_retry(a.ipmi_port,["sol","info","1"],a.password)
        save(a.evidence_dir,"a-sol-info","$ ipmitool -I lanplus sol info 1  (retried)\n# rc=%d"%rc,out)
        rc,out=ipmi_retry(a.ipmi_port,["sol","payload","status","1","1"],a.password)
        save(a.evidence_dir,"a-sol-payload-status","$ ipmitool -I lanplus sol payload status 1 1\n# rc=%d"%rc,out)
        rc,out=ipmi(a.ipmi_port,["sol","activate"],a.password,timeout=16)
        save(a.evidence_dir,"a-sol-activate","$ ipmitool -I lanplus sol activate  (blocks if opens)\n# rc=%d"%rc,out)

        # --- (d) FRU diagnosis over SSH ---
        rc,out=ssh(a.ssh_port,a.password,
            "echo '## fru-populate service'; systemctl --no-pager status kgpe-d16-fru-populate.service | head -20; "
            "echo; echo '## journal'; journalctl -u kgpe-d16-fru-populate.service --no-pager | tail -25; "
            "echo; echo '## motherboard inventory'; busctl introspect xyz.openbmc_project.Inventory.Manager "
            "/xyz/openbmc_project/inventory/system/chassis/motherboard 2>&1 | grep -Ei 'Asset|Manufacturer|Serial|Part|Model|PrettyName|Item' | head; "
            "echo; echo '## blob present'; ls -l /usr/share/kgpe-d16/motherboard-fru.bin; "
            "echo; echo '## manual re-run fruid 86'; phosphor-read-eeprom --eeprom /usr/share/kgpe-d16/motherboard-fru.bin --fruid 86; echo rc=$?; "
            "echo '## motherboard inventory AFTER'; busctl introspect xyz.openbmc_project.Inventory.Manager "
            "/xyz/openbmc_project/inventory/system/chassis/motherboard 2>&1 | grep -Ei 'Manufacturer|Serial|Part|PrettyName' | head")
        save(a.evidence_dir,"d-fru-diagnostics","# FRU population diagnostics (SSH)\n# rc=%d"%rc,out)

        # give inventory a moment, then re-read fru print + device 0
        time.sleep(5)
        rc,out=ipmi_retry(a.ipmi_port,["fru","print"],a.password,timeout=45)
        save(a.evidence_dir,"d-fru-print","$ ipmitool -I lanplus fru print  (after populate)\n# rc=%d"%rc,out)
        rc,out=ipmi_retry(a.ipmi_port,["fru","print","0"],a.password,timeout=30)
        save(a.evidence_dir,"d-fru-print-0","$ ipmitool -I lanplus fru print 0\n# rc=%d"%rc,out)
        print("\n[done] fixup captures written")
        return 0
    finally:
        q.terminate()
        try: q.wait(timeout=10)
        except subprocess.TimeoutExpired: q.kill()

if __name__=="__main__":
    raise SystemExit(main())
