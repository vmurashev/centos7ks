#!/bin/bash
set -e

DIR_HERE=$(cd $(dirname $0) && pwd)

python "$DIR_HERE/os-bootstrap.py" --install
python "$DIR_HERE/os-config-tui.py"
python "$DIR_HERE/os-install-tui.py" "$DIR_HERE/os-logwrap.py"

if [ -f '/tmp/os-install.ok' ]; then
    echo "Installation has been completed successfully."
else
    echo "Installation has been failed. Please study logs."
    if [ -f '/tmp/os-install.log' ]; then
        echo "You may start with '/tmp/os-install.log'"
    fi
fi
