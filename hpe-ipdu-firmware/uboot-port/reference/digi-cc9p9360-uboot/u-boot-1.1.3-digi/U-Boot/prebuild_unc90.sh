#! /bin/sh

set -e;

#PATH="`pwd`/toolchain/arm-linux/bin:${PATH}";
#export PATH

if ! test -d "AT91RM9200-Boot"; then
	echo "Error: Missing AT91RM9200-Boot directory"
	echo "Needed to build U-Boot for unc90"
	exit 1
else
	if test -f "AT91RM9200-Boot/CVS/Tag"; then
		cat "AT91RM9200-Boot/CVS/Tag";
	fi

	make -C "AT91RM9200-Boot";
	exit 0
fi
