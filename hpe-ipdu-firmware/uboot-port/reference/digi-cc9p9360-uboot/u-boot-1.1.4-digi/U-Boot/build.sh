#!/bin/sh

set -e;

declare -r AVAILABLE_PLATFORMS="a9m2410dev a9m2440dev cc9p9360dev cc9p9360val cc9p9750dev cc9p9750val cc9cjsnor cc9cjsnand ccw9cjsnor ccw9cjsnand ccxp270stk2 unc90dev";

ubootname_a9m2410dev="a9m2410";
ubootname_a9m2440dev="a9m2440";
ubootname_cc9p9360dev="cc9p9360dev";
ubootname_cc9p9360val="cc9p9360_val";
ubootname_cc9p9750dev="cc9p9750dev";
ubootname_cc9p9750val="cc9p9750_val";
ubootname_cc9cjsnor="cc9cjsnor";
ubootname_cc9cjsnand="cc9cjsnand";
ubootname_ccw9cjsnor="ccw9cjsnor";
ubootname_ccw9cjsnand="ccw9cjsnand";
ubootname_ccxp270stk2="ccxp";
ubootname_unc90dev="unc90dev";

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

# toolchain="latest" is reserved for LxNETES-3.2
toolchain="newest";

if test -f "CVS/Tag"; then
	toolchain="`cat CVS/Tag`";
	VERSION_TAG="${toolchain:1}";
fi;

# keep a copy of the last valid toolchain if available
lasttoolchain=toolchain.$$
if test -e toolchain; then
	mv toolchain ${lasttoolchain}
fi;

# get appropriate toolchain from build server 10.100.10.19
# note some tar.gz don't contain the toplevel toolchain/ dir, so work around this:
# echo "$0: trying to use toolchain-${toolchain}.tar.gz"
mkdir toolchain
(cd toolchain;wget -q -O "-" "http://bre-sln-lxnetes1.digi.com/U-Boot/toolchain/toolchain-${toolchain}.tar.gz" | zcat | tar xf "-")
if test -d toolchain/toolchain; then
	tmp=tmp.$$
	mv toolchain $tmp
	mv $tmp/toolchain .
	rmdir $tmp
fi;

if test -e toolchain;then
#	echo "$0: new toolchain downloaded"
	rm -rf ${lasttoolchain}
else
	if test -e ${lasttoolchain}; then
		mv ${lasttoolchain} toolchain
		echo "$0: Warning: using old toolchain"
	else
		echo "$0: ERROR: no valid toolchain found"
	fi
fi

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

			# quick'n'dirty hack to prevent make clean from
			# deleting files in the toolchain directory.
			chmod u-x "toolchain";

			make clean;

			# 2nd part of the dirty hack
			chmod u+x "toolchain";

			# standard build of U-Boot for the selected platform
			eval "make "VERSION_TAG=${VERSION_TAG:=HEAD}" \"\${ubootname_${platform}}_config\"";
			make;
		else
			echo "Don't know nothing about platform \"${platform}\"";
			exit 1
		fi;
	fi;
done;
