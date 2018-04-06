from __future__ import print_function
import ConfigParser
import os
import os.path
import struct
import sys


APP_CONFIG_FILE = '/tmp/os-config.ini'


def generate_app_config():
    if os.path.exists(APP_CONFIG_FILE):
        return

    hostname = "host-{:05x}".format(struct.unpack('I', os.urandom(4))[0] & 0xFFFFF)

    config = ConfigParser.RawConfigParser()

    config.add_section('main')
    config.set('main', 'hostname', hostname)

    config.add_section('eth0')
    config.set('eth0', 'bootproto', 'dhcp')

    with open(APP_CONFIG_FILE, 'wb') as configfile:
        config.write(configfile)


def main():
    install = True if '--install' in sys.argv else None
    if install:
        generate_app_config()
    else:
        print('os-bootstrap.py - invalid call')
        exit(1)


if __name__ == '__main__':
    main()
