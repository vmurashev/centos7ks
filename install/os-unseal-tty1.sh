#!/bin/bash
set -e
rm /etc/systemd/system/getty.target.wants/getty@tty1.service
cp /lib/systemd/system/getty@.service /etc/systemd/system/getty@tty1.service
sed -i 's/\(^.*ExecStart=.*$\)/\1 --autologin root/' /etc/systemd/system/getty@tty1.service
echo ';Alias=getty@tty1.service' >> /etc/systemd/system/getty@tty1.service
ln -s /etc/systemd/system/getty@tty1.service /etc/systemd/system/getty.target.wants/getty@tty1.service

{
    echo '#!/bin/bash'
    echo 'set -e'
    echo 'if [ "$(tty)" != "/dev/tty1" ]; then'
    echo '    exit 0'
    echo 'fi'
    echo 'function at_exit {'
    echo '    systemctl restart getty@tty1'
    echo '}'
    echo 'trap at_exit EXIT'
    echo 'echo -e "To proceed, you need to specify a password for user \033[0;31mroot\033[0m."'
    echo 'echo -e "Press any key to start changing it by \033[0;31mpasswd\033[0m command ..."'
    echo 'stty -echo'
    echo 'read -n 1'
    echo 'stty echo'
    echo 'passwd root'
    echo 'rm /etc/systemd/system/getty.target.wants/getty@tty1.service'
    echo 'cp /lib/systemd/system/getty@.service /etc/systemd/system/getty@tty1.service'
    echo 'ln -s /etc/systemd/system/getty@tty1.service /etc/systemd/system/getty.target.wants/getty@tty1.service'
    echo 'systemctl daemon-reload'
    echo 'mv /root/force_passwd_on_tty1.sh /root/force_passwd_on_tty1.bak'
} > "/root/force_passwd_on_tty1.sh"

{
    cat '/etc/skel/.bash_profile'
    echo ''
    echo 'if [ "$(tty)" = "/dev/tty1" ]; then'
    echo '  if [ -f "/root/force_passwd_on_tty1.sh" ]; then'
    echo '    /bin/bash /root/force_passwd_on_tty1.sh'
    echo '  fi'
    echo 'fi'
} > '/root/.bash_profile'
