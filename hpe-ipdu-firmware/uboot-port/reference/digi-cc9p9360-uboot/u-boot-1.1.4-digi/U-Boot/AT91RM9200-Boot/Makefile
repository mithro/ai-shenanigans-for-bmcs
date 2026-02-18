
CFLAGS = -Os -fno-builtin -fomit-frame-pointer  -fno-strict-aliasing  -fno-common -msoft-float -D__arm__ -D__FLASHED__ -I.
LDFLAGS = -nostdlib -Tld.script

CROSS_COMPILE=arm-linux-
#CROSS_COMPILE = /usr/local/arm/2.95.3/bin/arm-linux-
CC=$(CROSS_COMPILE)gcc

OBJ =  entry.o div0.o _udivsi3.o initboot.o crt0.o misc.o main.o

all:	boot.bin boot.srec boot.hex

boot.bin:	boot.text boot.data
	cat boot.text boot.data > $@

boot.text:	boot
	$(CROSS_COMPILE)objcopy -O binary -j .text $< $@

boot.data:	boot
	$(CROSS_COMPILE)objcopy -O binary -j .data $< $@

boot.srec:	boot
	$(CROSS_COMPILE)objcopy -O srec $< $@

boot.hex:	boot
	$(CROSS_COMPILE)objcopy -O ihex $< $@

boot:	$(OBJ)
	$(CC) $(LDFLAGS) -o $@ $(OBJ)

crt0.o:	crt0.S
	$(CC) $(CFLAGS) -c $<

entry.o:	entry.S
	$(CC) $(CFLAGS) -c $<

_udivsi3.o:	_udivsi3.S
	$(CC) $(CFLAGS) -c $<

div0.o:	div0.c
	$(CC) $(CFLAGS) -c $<

misc.o:	misc.c
	$(CC) $(CFLAGS) -c $<

initboot.o:	initboot.c
	$(CC) $(CFLAGS) -c $<

main.o:	main.c
	$(CC) $(CFLAGS) -c $<

clean:
	rm -f boot boot.text boot.data *.o *~
