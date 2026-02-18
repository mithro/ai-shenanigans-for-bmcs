#! /bin/sh

set -e;

ubootname_a9m2410dev="a9m2410";
ubootname_a9m2440dev="a9m2440";
ubootname_cc9p9360dev="cc9p9360_dev";
ubootname_cc9p9360val="cc9p9360_val";
ubootname_cc9p9750dev="cc9p9750_dev";
ubootname_cc9p9750val="cc9p9750_val";
ubootname_cc9cdev="cc9c_nor_16";
ubootname_ccxp270stk2="ccxp";
ubootname_unc90dev="unc90";

if test "x${#}" = "x0"; then
	echo "Usage: $0 <platform>" >&2;
	exit 1;
fi;

if test ! -x toolchain/bin/arm-linux-gcc; then
	echo "The toolchain is missing in the toolchain/ directory" >&2;
	echo "Please check README.U-Boot for build instructions." >&2;
	exit 1;
fi;

PATH="`pwd`/toolchain/bin:${PATH}";
export PATH;

for platform; do
	# check that "ubootname_${platform}" is a valid variable name.
	# What is a valid name? probably all that matches "[_a-zA-Z][_a-zA-Z0-9]*"
	if expr "x${platform}" : "x.*[^a-zA-Z0-9_]" >/dev/null; then
		echo "Warning: skip malformed argument \"${platform}\"" >&2;
		continue;
	fi;

	if eval "test -n \"\${ubootname_${platform}}\""; then

		# remove dependencies
		find . -type f -name ".depend" | xargs rm -rf

		# invoke prebuild script in case it exists
		if eval "test -f \"prebuild_\${ubootname_${platform}}.sh\""; then
			eval echo "using prebuild script \"prebuild_\${ubootname_${platform}}.sh\"";
			eval "sh \"prebuild_\${ubootname_${platform}}.sh\"";
		fi


		# quick'n'dirty hack to prevent make clean from
		# deleting files in the toolchain directory.
		chmod u-x "toolchain";

		make clean;

		# 2nd part of the dirty hack
		chmod u+x "toolchain";

		# standard build of U-Boot for the selected platform
		eval "make \"\${ubootname_${platform}}_config\"";
		make;

		# invoke postbuild script in case it exists
		if eval "test -f \"postbuild_\${ubootname_${platform}}.sh\""; then
			eval echo "using postbuild script \"postbuild_\${ubootname_${platform}}.sh\"";
			eval "sh \"postbuild_\${ubootname_${platform}}.sh\"";
		fi

		mv "u-boot.bin" "u-boot-${platform}.bin";
	else
		echo "Don't know nothing about platform \"${platform}\"";
	fi;
done;
