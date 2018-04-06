#!/bin/bash
set -e
DIR_HERE=$(cd $(dirname $0) && pwd)
python "${DIR_HERE}/test_build_env.py"

make --directory ${DIR_HERE}

if [ -f "/.dockerenv" -a -d "${DIR_HERE}/../docker_output" ]; then
    DIR_DOCKER_OUTPUT=$(cd "${DIR_HERE}/../docker_output" && pwd)
    DIR_OUTPUT=$(cd "${DIR_HERE}/../output" && pwd)
    echo "Emerge build results out from docker ..."
    cp "$DIR_OUTPUT/centos7.iso" "$DIR_DOCKER_OUTPUT"
fi
