#!/bin/sh
#####################################################################################
# @File: userbuild_cygwin.sh
# @Desc: File to build U-Boot under cygwin environment. Performs some sanity checks
#        and builds U-Boot, for the selected platforms.
# @Ver:  Version 1.1 (13/Oct/2006).
#        Version 1.0 (25/Oct/2005).
#
# Copyright (c) 2005,2006 Digi International
#####################################################################################

set -e;

ubootname_a9m2410dev="a9m2410";
ubootname_a9m2440dev="a9m2440";
ubootname_cc9p9360dev="cc9p9360dev";
ubootname_cc9p9360val="cc9p9360_val";
ubootname_cc9p9750dev="cc9p9750dev";
ubootname_cc9p9750val="cc9p9750_val";
ubootname_cc9cdev="cc9c_nor_16";
ubootname_ccxp270stk2="ccxp";
ubootname_unc90dev="unc90";

hostenv=`uname -s | tr '[:upper:]' '[:lower:]' | sed -e 's/\(cygwin\).*/cygwin/'`
 
# Sanity checks
if test "x${#}" = "x0"; then
	echo "Usage: $0 <platform>" >&2;
	exit 1;
fi;

if [ "$hostenv" = "linux" ]; then
	echo "This script is prepared to build U-Boot under cygwin environment" >&2;
	echo "Please use userbuild.sh script for linux builds." >&2;
	exit 1;
elif [ "$hostenv" = "cygwin" ]; then
	cross_gcc=arm-elf-gcc;
	toolchain_bin_path=/bin;
else
	echo "Unkown host build environment" >&2;
	exit 1;
fi

if test ! -x ${toolchain_bin_path}/${cross_gcc}; then
	echo "The toolchain is missing in ${toolchain_bin_path} directory" >&2;
	echo "Please check README.U-Boot for build instructions." >&2;
	exit 1;
fi;

PATH="${toolchain_bin_path}:${PATH}";
export PATH;

for platform; do
	# check that "ubootname_${platform}" is a valid variable name.
	# What is a valid name? probably all that matches "[_a-zA-Z][_a-zA-Z0-9]*"
	if expr "x${platform}" : "x.*[^a-zA-Z0-9_]" >/dev/null; then
		echo "Warning: skip malformed argument \"${platform}\"" >&2;
		continue;
	fi;

	if eval "test -n \"\${ubootname_${platform}}\""; then

		# remove dependencies and clean
		find . -type f -name ".depend" | xargs rm -rf
		make clean;

		# standard build of U-Boot for the selected platform
		eval "make \"\${ubootname_${platform}}_config\"";
		make;

		# per platform rename
		mv "u-boot.bin" "u-boot-${platform}.bin";
	else
		echo "Don't know nothing about platform \"${platform}\"";
		exit 1
	fi;
done;
