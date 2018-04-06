#!/bin/bash
set -e
export PYTHONUNBUFFERED=1


DIR_ISO_ROOT='/run/initramfs/live'
DIR_SYSROOT='/mnt/sysimage'
KICKSTART_TEMPLATE_FILE="$DIR_ISO_ROOT/os-template.cfg"
KICKSTART_CONFIG_FILE='/tmp/os-install.cfg'

INI_CONFIG_INSTALL="/tmp/os-config.ini"
HASHED_ROOT_PASSWORD_FILE='/root/os-config.shadow'


safe_copy_file() {
    local SRC_FILE="$1"
    local DST_FILE="$2"
    rm -f "${DST_FILE}.bak"
    if [ -f "${DST_FILE}" ]; then
        mv -T "${DST_FILE}" "${DST_FILE}.bak"
    fi
    echo -n "Copying file '$SRC_FILE' as '$DST_FILE' ... "
    cp -T "$SRC_FILE" "$DST_FILE"
    chmod 0644 "$DST_FILE"
    rm -f "${DST_FILE}.bak"
    echo "done"
}

safe_copy_file_in_dir() {
    local SRC_FILE="$1"
    local DST_DIR="$2"
    local SRC_FILE_NAME="$(basename "$SRC_FILE")"
    local DST_FILE="${DST_DIR}/${SRC_FILE_NAME}"
    safe_copy_file "$SRC_FILE" "$DST_FILE"
}


if [ ! -f "$INI_CONFIG_INSTALL" ]; then
   echo "ERROR: File not found: '$INI_CONFIG_INSTALL'"
   exit 1
fi

if [ ! -f "$KICKSTART_TEMPLATE_FILE" ]; then
   echo "ERROR: File not found: '$KICKSTART_TEMPLATE_FILE'"
   exit 1
fi

set +e
HOST_NAME=$(python "$DIR_ISO_ROOT/os-getconf.py" '/tmp/os-config.ini' 'main' 'hostname')
set -e
if [ -n "$HOST_NAME" ]; then
    echo "Host name to be used: '$HOST_NAME'"
else
    echo "ERROR: Got empty host name for target."
    exit 1
fi

HAVE_ROOT_PASSWORD_HASH_FILE='n'
if [ -f "$HASHED_ROOT_PASSWORD_FILE" ]; then
    chattr +i "$HASHED_ROOT_PASSWORD_FILE"
    HAVE_ROOT_PASSWORD_HASH_FILE='y'
fi
set +e
ROOTPW_CONFIG=$(python "$DIR_ISO_ROOT/os-getconf.py" @rootpw)
set -e
if [ -z "$ROOTPW_CONFIG" ]; then
    echo "ERROR: Got a broken 'rootpw' configuration."
    exit 1
fi

set +e
NETWORK_CONFIG=$(python "$DIR_ISO_ROOT/os-getconf.py" $INI_CONFIG_INSTALL @network)
set -e
if [ -n "$NETWORK_CONFIG" ]; then
    echo "Network configuration to be used: '$NETWORK_CONFIG'"
else
    echo "ERROR: Got an empty network configuration for the target."
    exit 1
fi

safe_copy_file "$KICKSTART_TEMPLATE_FILE" "$KICKSTART_CONFIG_FILE"
sed -i "s/@NETWORK@/$NETWORK_CONFIG/" "$KICKSTART_CONFIG_FILE"
sed -i "s/@ROOTPASSWORD@/$ROOTPW_CONFIG/" "$KICKSTART_CONFIG_FILE"

if [ ! -f "$KICKSTART_CONFIG_FILE" ]; then
   echo "ERROR: File not found: '$KICKSTART_CONFIG_FILE'"
   exit 1
fi
echo "Anaconda initial setup ..."
anaconda -C --kickstart "$KICKSTART_CONFIG_FILE"
if [ ! -f "$DIR_SYSROOT/root/anaconda-ks.cfg" ]; then
   echo "Operating system installation has failed. Please examine logs."
   exit 1
fi
if [ "$HAVE_ROOT_PASSWORD_HASH_FILE" != 'y' ]; then
    safe_copy_file_in_dir "$DIR_ISO_ROOT/os-unseal-tty1.sh" "$DIR_SYSROOT/tmp"
    chroot "$DIR_SYSROOT" '/bin/bash' '/tmp/os-unseal-tty1.sh'
    rm -f "$DIR_SYSROOT/tmp/os-unseal-tty1.sh"
fi

echo -n "$HOST_NAME" > "$DIR_SYSROOT/etc/hostname"

touch '/tmp/os-install.ok'
