from __future__ import print_function
import ConfigParser
import os.path
import sys


HASHED_ROOT_PASSWORD_FILE = '/root/os-config.shadow'


def load_ini_config(fname):
    with open(fname, mode='rb') as _:
        pass
    config = ConfigParser.RawConfigParser()
    config.optionxform=str
    config.read(fname)
    return config


def get_ini_conf_string1(config, section, option):
    return config.get(section, option).strip()


def get_ini_conf_string0(config, section, option, default=None):
    if not config.has_option(section, option):
        return default
    return get_ini_conf_string1(config, section, option)


def eval_network_config(config):
    bootproto = get_ini_conf_string1(config, 'eth0', 'bootproto')
    if bootproto == 'dhcp':
        return 'network --device=eth0 --bootproto=dhcp'

    static_ip = get_ini_conf_string0(config, 'eth0', 'ip')
    static_netmask = get_ini_conf_string1(config, 'eth0', 'netmask')
    static_gateway = get_ini_conf_string1(config, 'eth0', 'gateway')
    static_nameserver = get_ini_conf_string0(config, 'eth0', 'nameserver')
    value = 'network --device=eth0 --bootproto=static --ip={} --netmask={} --gateway={}'.format(static_ip, static_netmask, static_gateway)
    if static_nameserver is not None:
        value = value + ' --nameserver={}'.format(static_nameserver)
    return value


def eval_rootpw_config():
    rootpw_hash = ''
    if os.path.exists(HASHED_ROOT_PASSWORD_FILE):
        with open(HASHED_ROOT_PASSWORD_FILE, mode='rt') as fh:
            for ln in [ ln.rstrip('\r\n').strip() for ln in fh.readlines() ]:
                if ln:
                    rootpw_hash = ln
                    break
        if not rootpw_hash:
            raise Exception("os-getconf.py - got broken password hash.")
        rootpw_hash = rootpw_hash.replace('\\','\\\\').replace('/','\\/') # escaping for sed
        return 'rootpw --iscrypted {}'.format(rootpw_hash)
    else:
        return 'rootpw --lock'


if __name__ == '__main__':
    if sys.argv[1] == '@rootpw':
        value = eval_rootpw_config()
    else:
        config = load_ini_config(sys.argv[1])
        if sys.argv[2] == '@network':
            value = eval_network_config(config)
        else:
            section, option = sys.argv[2], sys.argv[3]
            value = get_ini_conf_string1(config, section, option)
    print(value)
