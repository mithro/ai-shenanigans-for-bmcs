SUMMARY = "NBD swap for the memory-tight AST2050 BMC"
DESCRIPTION = "Attaches a RAM-backed NBD export on the Pi bridge as low-priority \
swap, giving the 64 MB AST2050 (minus the 8 MB VGA reserve) headroom. Swap over \
NBD is deadlock-safe under memory pressure (SOCK_MEMALLOC/PF_MEMALLOC) and \
offloads cold pages to the Pi's RAM. Needs the kgpe-d16-swap kernel (CONFIG_SWAP)."
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = "file://nbd-swap.sh file://nbd-swap.service"
S = "${WORKDIR}"

inherit systemd
SYSTEMD_SERVICE:${PN} = "nbd-swap.service"

RDEPENDS:${PN} += "nbd-client util-linux-swapon util-linux-mkswap"

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/nbd-swap.sh ${D}${bindir}/nbd-swap.sh
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/nbd-swap.service ${D}${systemd_system_unitdir}/
}

FILES:${PN} += "${bindir}/nbd-swap.sh ${systemd_system_unitdir}/nbd-swap.service"
