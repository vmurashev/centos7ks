#!/bin/bash -e

ISO_NAME="$1"
if [ -z "$ISO_NAME" ]; then
    echo "[create-iso] ERROR: path to generating iso is not provided in command-line."
    exit 1
fi

DIR_HERE=$(cd $(dirname $0) && pwd)
DIR_OUTPUT=$(cd $(dirname $1) && pwd)
ISO_NAME=$(basename "$1")
ISO_NAME=$(echo "$ISO_NAME" | sed 's/\.iso$//I')
DIR_CUSTOM_INSTALL="$DIR_HERE/../install"

echo "[create-iso] output-directory: '$DIR_OUTPUT'"
echo "[create-iso] iso name: '$ISO_NAME'"

if [ ! -d "$DIR_OUTPUT" ] || [ -z "$ISO_NAME" ]; then
    echo "[create-iso] ERROR: invalid command-line."
    exit 1
fi

DIR_ISODB="${DIR_OUTPUT}/isodb"
DIR_ISOTMP="${DIR_OUTPUT}/isotmp"
LOGFILE="${DIR_OUTPUT}/iso-creation-log.txt"

mkdir -p $DIR_ISODB
mkdir -p $DIR_ISOTMP
rm -f $LOGFILE
rm -f "${DIR_OUTPUT}/${ISO_NAME}.iso"

echo "[create-iso] started ..."

(
    cd $DIR_OUTPUT

    livecd-creator --verbose --debug \
        --config 'iso-ks.cfg' \
        --cache=$DIR_ISODB \
        --fslabel=$ISO_NAME \
        --tmpdir=$DIR_ISOTMP \
        --skip-minimize \
        --logfile=$LOGFILE

    rm -rf isopack isomnt
    mkdir -p isopack isomnt
    mount -t iso9660 -o loop "${DIR_OUTPUT}/${ISO_NAME}.iso" "${DIR_OUTPUT}/isomnt"
    (cd "${DIR_OUTPUT}/isomnt" && tar -cvf - . ) | (cd "${DIR_OUTPUT}/isopack" && tar -xf - )
    umount "${DIR_OUTPUT}/isomnt"
    rm -rf "${DIR_OUTPUT}/isomnt"
    rm -f "${DIR_OUTPUT}/${ISO_NAME}.iso"

    # tune connent inside isolinux
    rm -f "${DIR_OUTPUT}/isopack/isolinux/macboot.img"

    # Put our custom scripts for installation into ISO
    if [ -d "$DIR_CUSTOM_INSTALL" ]; then
        install_files=$(cd $DIR_CUSTOM_INSTALL && ls -1)
        for f in $(cd $DIR_CUSTOM_INSTALL && ls -1)
        do
            echo "[create-iso] processing $f"
            cp -T "$DIR_CUSTOM_INSTALL/$f" "${DIR_OUTPUT}/isopack/$f"
        done
    fi

    (cd ${DIR_OUTPUT}/isopack && genisoimage -U -r -v -T -J -joliet-long -V 'centos7' -b isolinux/isolinux.bin -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table -eltorito-alt-boot -e isolinux/efiboot.img -no-emul-boot -o "${DIR_OUTPUT}/${ISO_NAME}.iso" . )

)

stat "${DIR_OUTPUT}/${ISO_NAME}.iso"
echo "[create-iso] done: '${DIR_OUTPUT}/${ISO_NAME}.iso'"
