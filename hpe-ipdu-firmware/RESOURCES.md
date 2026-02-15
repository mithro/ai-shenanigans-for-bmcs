# HPE Intelligent Modular PDU -- Resources

## Overview

The HPE Intelligent Modular PDU (iPDU) is an intelligent power distribution unit for
data centre rack power management. The AF531A model is a 4.9 kVA unit with L6
connectors. The Core Unit contains the main controller board with a Digi NS9360
ARM926EJ-S processor running Linux.

The chassis includes:
- 6x C19 outlets per Core Unit (grouped into load segments)
- RJ-45 Ethernet management port
- RS-232 serial console (via Display Unit)
- Per-outlet current/power monitoring via MAXQ3180 3-phase measurement AFE
- Web interface, SNMP, Telnet, FTP, SSH management protocols
- Daisy-chain capability to additional iPDU units
- Extension bar support

## Firmware Downloads

All HPE firmware downloads require an HPE Passport account.

### HPE Support Pages
- **Product Support:** https://www.dell.com/support/home/en-us/product-support/product/poweredge-c410x/overview
  (Note: This is the wrong link -- HPE iPDU support pages require authentication)
- **HPE MyEnterpriseLicense:** https://myenterpriselicense.hpe.com/cwp-ui/product-details/Z7550-63180/-/sw_free
- **HPE Support Center (AF531A):** https://support.hpe.com/connect/s/product?language=en_US&is498702_tab=t5&kmpmoid=ish_3765193

### Known Firmware Versions (Codename "Henning")

| Version | Filename Pattern | Notes |
|---------|-----------------|-------|
| 2.0.51.12 | Henning_2.0.51.12_Z7550-09130.zip | Latest known (2019) |
| 2.0.51 | Henning_2.0.51_*.zip | |
| 2.0.3 | Henning_2.0.3_*.zip | |
| 2.0.2 | Henning_2.0.2_*.zip | |
| 2.0.1 | Henning_2.0.1_*.zip | |
| 2.0.0 | Henning_2.0.0_*.zip | Major version bump |
| 1.4 | Henning_1.4_*.zip | |
| 1.3 | Henning_1.3_*.zip | |
| 1.2 | Henning_1.2_*.zip | |
| 1.1 | Henning_1.1_*.zip | Initial release (~2010) |

### HP Power Device Flash Utility
Used for flashing firmware via serial or FTP. Several versions known:
- HPPowerDeviceFlashUtility_3.2.1_Z7550-09218.zip
- HPPowerDeviceFlashUtility_2.0.x_*.zip

### Alternative Sources (Eaton)
The HPE iPDUs may be OEM rebrands of Eaton ePDU products. Eaton firmware may be
compatible:
- **Eaton Firmware Downloads:** https://www.eaton.com/us/en-us/products/backup-power-ups-surge-it-power-distribution/firmware-downloads.html

## Documentation

### Official HP/HPE Documentation
- **HP iPDU User Guide (ManualsLib):** https://www.manualslib.com/manual/1252706/Hp-Intelligent-Pdu.html
  (104 pages, covers hardware setup, web interface, serial console, firmware update)

### Key Manual Sections
- Serial settings: 115200/8/N/1/None
- Firmware files: `image.bin` (firmware) + `config.bin` (configuration)
- Flash modes: Serial Flash (single unit) and FTP Flash (single/multiple units)
- Core Unit connections: serial to Display Unit, serial to additional iPDU, RJ-45 Ethernet, reset button

## Datasheets

### Main CPU: Digi NS9360
- **NS9360 Datasheet (Rev D, 09/2007):**
  https://ftp1.digi.com/support/documentation/91001326_D.pdf
  (80 pages, 721 KB -- pinout, GPIO MUX table, address map, electrical specs)
- **NS9360 Hardware Reference Manual (Rev J, 03/2011):**
  https://ftp1.digi.com/support/documentation/90000675_J.pdf
  (2.7 MB -- full register-level documentation: GPIO config registers, serial ports,
  memory controller, Ethernet, DMA, interrupt controller, all peripherals)
- **ConnectCore 9P 9360 HW Reference:**
  https://ftp1.digi.com/support/documentation/90000769_C.pdf
  (Hardware reference for the ConnectCore 9P 9360 system-on-module)
- **NET+Works HW Reference Guide:**
  https://ftp1.digi.com/support/documentation/userguide_hwreferenceguide.pdf
  (General hardware reference for the NET+ARM processor family)

### Ethernet PHY: ICS 1893AFLF
- **ICS1893 Datasheet (Renesas):**
  https://www.renesas.com/en/document/dst/1893y-10-datasheet
  (10Base-T/100Base-TX Integrated PHYceiver, 3.3V)
- **ICS1893AF Datasheet (AllDatasheet):**
  https://www.alldatasheet.com/datasheet-pdf/pdf/112036/ICST/ICS1893AF.html
  (170 KB / 12 pages)
- **ICS1893 User Design Guide:**
  https://www.renesas.com/en/document/apn/1893-user-design-guide

Note: The ICS1893AFLF (U10, marked "P47932M / 1893AFLF") was initially
misidentified as a clock generator. It is actually the Ethernet PHY transceiver
that pairs with the NS9360's on-chip Ethernet MAC.

### Power Measurement AFE: Maxim MAXQ3180
- **MAXQ3180 Datasheet (DigiKey):**
  https://media.digikey.com/pdf/Data%20Sheets/Maxim%20PDFs/MAXQ3180.pdf
  (1.2 MB / 48 pages -- SPI protocol, register map, power calculation algorithms)
- **MAXQ3180 Product Page (Analog Devices):**
  https://www.analog.com/en/products/maxq3180.html
- **Application Note AN4663:**
  https://pdfserv.maximintegrated.com/en/an/AN4663.pdf

### Sub-MCU: Toshiba TMP89FM42LUG
- **TMP89FM42LUG Datasheet (Toshiba):**
  https://toshiba.semicon-storage.com/info/TMP89FM42LUG_datasheet_en_20090721.pdf?did=11183&prodName=TMP89FM42LUG
  (~5 MB / ~408 pages -- TLCS-870/C1 8-bit MCU, 238 ns instruction execution)
- **TMP89FM42LUG Product Page:**
  https://toshiba.semicon-storage.com/ap-en/semiconductor/product/microcontrollers/tlcs-870-c1-series-and-tlcs-870-c1e-series/detail.TMP89FM42LUG.html
- **TLCS-870/C1 Series Programming Manual:**
  https://www.manualslib.com/manual/1737789/Toshiba-Tlcs-870-C1-Series.html

### Memory
- **ISSI IS42S32800D (SDRAM):**
  https://www.alldatasheet.com/datasheet-pdf/pdf/310977/ISSI/IS42S32800D.html
  (894 KB / 60 pages -- 256 Mbit, 8M x 32 x 4 banks, 3.3V)
- **Macronix MX29LV640E (NOR Flash):**
  https://www.macronix.com/Lists/Datasheet/Attachments/8514/MX29LV640E%20T-B,%203V,%2064Mb,%20v1.7.pdf
  (728 KB / 61 pages -- 64 Mbit, bottom boot sector, 3V, 70 ns access)
- **MX29LV640E Migration App Note:**
  https://www.macronix.com/Lists/ApplicationNote/Attachments/1865/AN071-Migration_to_MX29LV640E.pdf

### RS-232 Level Shifter: TI MAX3243EI
- **MAX3243E Datasheet:**
  https://www.ti.com/lit/ds/symlink/max3243e.pdf
  (3V to 5.5V RS-232 transceiver with AutoShutdown)

## Board Photos

Physical board teardown photos:
- **Google Photos Album ("HP PDU AF520A Core Parts"):**
  https://photos.google.com/share/AF1QipOlajnfRlw4bCdkUFzp4Ti6VZBmPwLn1eyXQCJaOMjkgSEMFuxiXs21xtg1u3QJMA?key=TjdOQno3d2FLbzJYSFhBM3RoZ2RfU2xxclJaT05n

## Key Technical Details

### iPDU Features
- Per-outlet power monitoring (V, A, W, VA, PF, kWh)
- Environmental monitoring support
- Web interface (HTTP/HTTPS)
- SNMP v1/v2c/v3
- Telnet/SSH CLI
- FTP/TFTP firmware update
- Email and SNMP trap alerting
- Daisy-chain up to 8 units
- Extension bar support (up to 4 per Core Unit)

### Hardware Specifications
| Component | Details |
|-----------|---------|
| CPU | Digi NS9360B-0-C177 (ARM926EJ-S, ~177 MHz) |
| SDRAM | 32 MB (ISSI IS42S32800D) |
| NOR Flash | 16 MB (2x Macronix MX29LV640EB) |
| Power Measurement | Maxim MAXQ3180-RAN (3-phase AFE) |
| Sub-MCU | Toshiba TMP89FM42LUG (TLCS-870/C, display/LED) |
| Serial Ports | 4x UART/SPI (NS9360) + RS-232 via MAX3243EI |
| Ethernet | 10/100 Mbps (NS9360 MAC + ICS1893AFLF PHY) |
| I2C | 1x bus (on-chip) |
| RTC | On-chip (NS9360) with coin cell backup |
| System Crystal | 29.4912 MHz |
| Ethernet Crystal | 25.000 MHz |
