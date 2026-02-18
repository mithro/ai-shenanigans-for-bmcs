#! /bin/sh

set -e;

pwd_dir=`pwd`
tmp_images_dir=${pwd_dir}/images
boot_bin_dir=${pwd_dir}/AT91RM9200-Boot
uboot_dir=${pwd_dir}
boot_bin_size=64
uboot_size=192
uboot_final_image=u-boot.bin

if [ -d ${tmp_images_dir} ]; then
	rm -rf ${tmp_images_dir}
fi

# Create a temp images directorie
mkdir ${tmp_images_dir}

# Check that all the needed files exist...
if [ ! -f ${boot_bin_dir}/boot.bin ]; then
	echo "Error: missing boot.bin file, needed to create final image"
	exit 1
fi

if [ ! -f ${uboot_dir}/u-boot.bin ]; then
	echo "Error: missing u-boot.bin file, needed to create final image"
	exit 1
fi

# Create binary images

# Create boot.bin holder
dd if=/dev/zero of=${tmp_images_dir}/bootloader.img bs=1024 count=${boot_bin_size}

# @TODO check if file fits into the reserved space
dd if=${boot_bin_dir}/boot.bin of=${tmp_images_dir}/bootloader.img conv=notrunc

# Create u-boot.bin holder.
# @TODO Use 0xffs to optimize flash programming if possible.
dd if=/dev/zero of=${tmp_images_dir}/uboot.img bs=1024 count=${uboot_size}

# @TODO check if file fits into the reserved space
dd if=${uboot_dir}/u-boot.bin of=${tmp_images_dir}/uboot.img conv=notrunc

# Join both images to create the final file
cat ${tmp_images_dir}/uboot.img >>${tmp_images_dir}/bootloader.img

# Rename to get the final image
cp ${tmp_images_dir}/bootloader.img ${uboot_dir}/${uboot_final_image}

# Clean all temp files...
if [ -d ${tmp_images_dir} ]; then
	rm -rf ${tmp_images_dir}/*
fi

exit 0
