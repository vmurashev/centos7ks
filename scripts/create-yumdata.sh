#!/bin/bash -e

set -e

DIR_HERE=$(cd $(dirname $0) && pwd)

DIR_OUTPUT="$1"

if [ -z "$DIR_OUTPUT" ]; then
    echo "[create-yumdata] ERROR: path to output directory is not provided in command-line."
    exit 1
fi

set +e
DIR_OUTPUT=$(cd "$1" && pwd)
set -e

if [ ! -d "$DIR_OUTPUT" ]; then
    echo "[create-yumdata] ERROR: invalid command-line, directory not found: '$DIR_OUTPUT'"
    exit 1
fi

DIR_YUM_DATA="$DIR_OUTPUT/yumdata"

rm -rf "$DIR_YUM_DATA"

mkdir -p "$DIR_YUM_DATA/config"
mkdir -p "$DIR_YUM_DATA/log"
mkdir -p "$DIR_YUM_DATA/cache"
mkdir -p "$DIR_YUM_DATA/tmp"

YUM_CONFIG_FILE="$DIR_YUM_DATA/config/yum.conf"
YUM_LOG_FILE="$DIR_YUM_DATA/log/yum.log"

REPO_BASE_URL='http://mirror.centos.org/centos/7/os/x86_64/'
REPO_UPDATES_URL='http://mirror.centos.org/centos/7/updates/x86_64/'
REPO_EXTRAS_URL='http://mirror.centos.org/centos/7/extras/x86_64/'

cat > "$YUM_CONFIG_FILE" << EOF
[main]
keepcache=0
exactarch=1
cachedir=$DIR_YUM_DATA/cache
debuglevel=1
logfile=$YUM_LOG_FILE
reposdir=/dev/null
retries=20
obsoletes=1
gpgcheck=0
assumeyes=1
plugins=1
group_package_types=default,mandatory

[base]
name=base
baseurl=$REPO_BASE_URL
enabled=1
gpgcheck=0


#released updates
[updates]
name=updates
baseurl=$REPO_UPDATES_URL
enabled=1
gpgcheck=0

[extras]
name=extras
baseurl=$REPO_EXTRAS_URL
enabled=1
gpgcheck=0

EOF

# step-1

echo "[create-yumdata][step-1] Evaluating url of file with repo groups ..."
echo "Downloading '$REPO_BASE_URL/repodata/repomd.xml' as '$DIR_YUM_DATA/tmp/repomd.xml' ..."
curl "$REPO_BASE_URL/repodata/repomd.xml" -o "$DIR_YUM_DATA/tmp/repomd.xml"
echo "Parsing $DIR_YUM_DATA/tmp/repomd.xml ..."

group_tag=0
location=''
ln_stripped=''
while read ln; do
    ln_stripped=$(echo "$ln" | sed 's/^\s*\(.*\)$/\1/')
    if [ "$ln_stripped" = '<data type="group">' ]; then
        group_tag=1
    elif [ "$ln_stripped" = '<data type="group_gz">' ]; then
        group_tag=2
    elif [ "$ln_stripped" = '</data>' ]; then
        group_tag=0
    elif [ "$group_tag" != '0' -a "${ln_stripped:0:9}" = '<location' ]; then
        location=$(echo "$ln_stripped" | sed 's/<location href="\(.*\)"\/>/\1/')
        break
    fi
done < "$DIR_YUM_DATA/tmp/repomd.xml"
if [ -z "$location" ]; then
    echo "ERROR: Can't eval repo group location."
    exit 1
fi
echo "Evaluated url: '$REPO_BASE_URL/$location'"
echo "[create-yumdata][step-1] Done."


# step-2

echo "[create-yumdata][step-2] Generating stripped groups info ..."
echo "Downloading '$REPO_BASE_URL/$location' as '$DIR_YUM_DATA/tmp/groups.xml' ..."
curl "$REPO_BASE_URL/$location" -o "$DIR_YUM_DATA/tmp/groups.xml"
if [ "$group_tag" = "2" ]; then
    mv "$DIR_YUM_DATA/tmp/groups.xml" "$DIR_YUM_DATA/tmp/groups.xml.gz"
    if ! gzip -d "$DIR_YUM_DATA/tmp/groups.xml.gz"; then
        echo "ERROR: Can't unpack groups XML file."
        exit 1
    fi
fi

echo "Parsing $DIR_YUM_DATA/tmp/groups.xml ..."
python "$DIR_HERE/strip-groups-info.py" --input "$DIR_YUM_DATA/tmp/groups.xml" --output "$DIR_YUM_DATA/comps.xml"
echo "Generated file '$DIR_YUM_DATA/comps.xml'"
echo "[create-yumdata][step-2] Done."

# step-3

echo "[create-yumdata][step-3] Downloading repo packages ..."

cat "$DIR_HERE/packages-live.lst" | xargs yum install \
    -c "$YUM_CONFIG_FILE" \
    --downloadonly \
    --downloaddir="$DIR_YUM_DATA/packages" \
    --installroot="$DIR_YUM_DATA/tmp" \
    --releasever=/

echo "[create-yumdata][step-3] Done."

echo "[create-yumdata][step-4] Generating repo metadata ..."
createrepo -g "$DIR_YUM_DATA/comps.xml" "$DIR_YUM_DATA/packages" --verbose --simple-md-filenames

cat > $DIR_YUM_DATA/packages/.treeinfo << EOF
[general]
name = CentOS Linux-7
family = CentOS Linux
timestamp = $(date +%s)
version = 7
arch = x86_64
EOF

cat > $DIR_YUM_DATA/.buildstamp << EOF
[Main]
Product=CentOS Linux
Version=7
IsFinal=True
UUID=$(date +%Y%m%d%H%M).x86_64
EOF

echo "[create-yumdata][step-4] Done."
