#! /bin/sh

set -e;

declare -r AVAILABLE_PLATFORMS="a9m2410dev a9m2440dev cc9p9360dev cc9p9360val cc9p9750dev cc9p9750val cc9cdev ccxp270stk2 unc90dev";

ubootname_a9m2410dev="a9m2410";
ubootname_a9m2440dev="a9m2440";
ubootname_cc9p9360dev="cc9p9360_dev";
ubootname_cc9p9360val="cc9p9360_val";
ubootname_cc9p9750dev="cc9p9750_dev";
ubootname_cc9p9750val="cc9p9750_val";
ubootname_cc9cdev="cc9c_nor_16";
ubootname_ccxp270stk2="ccxp";
ubootname_unc90dev="unc90";

list_available_platforms="false"
show_files_tobuild="false";

while getopts "ls" c; do
	case "${c}" in
		l)
			list_available_platforms="true";
			;;
		s)
			show_files_tobuild="true";
			;;
	esac;
done;

#######################################################
## Just show the available platforms and exit
#######################################################
if "${list_available_platforms}"; then
	set ${AVAILABLE_PLATFORMS}
	for i; do
		echo "${i}";
	done
	exit 0
fi

shift $((${OPTIND} - 1))

if test "x${#}" = "x0"; then
	set ${AVAILABLE_PLATFORMS}
fi;

if test ! -x toolchain/bin/arm-linux-gcc; then
	# build.fsforth.de has (for now) IP 192.168.40.64
	wget -q -O "-" "http://10.100.10.19/U-Boot/toolchain/toolchain-latest.tar.gz" | zcat | tar xf "-";

	if test -d "LxNETES-3/arm-linux"; then
		mv "LxNETES-3/arm-linux" "toolchain";
	fi;
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

	if "${show_files_tobuild}"; then
		echo "u-boot-${platform}.bin";
	else
		if eval "test -n \"\${ubootname_${platform}}\""; then

			# remove dependencies
			find . -type f -name ".depend" | xargs rm -rf

			# invoke prebuild script in case it exists
			if eval "test -f "prebuild_\${ubootname_${platform}}.sh""; then
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
			if eval "test -f "postbuild_\${ubootname_${platform}}.sh""; then
				eval echo "using postbuild script \"postbuild_\${ubootname_${platform}}.sh\"";
				eval "sh \"postbuild_\${ubootname_${platform}}.sh\"";
			fi

			mv "u-boot.bin" "u-boot-${platform}.bin";
		else
			echo "Don't know nothing about platform \"${platform}\"";
		fi;
	fi;
done;
