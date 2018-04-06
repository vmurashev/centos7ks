from __future__ import print_function
import atexit
import base64
import fcntl
import os
import os.path
import re
import signal
import socket
import struct
import sys
import traceback
import urwid
import ConfigParser
import subprocess


AUTOMATIC_INSTALL_TIMEOUT = 15 # seconds
APP_CONFIG_FILE = '/tmp/os-config.ini'
APP_CONFIG_FILE_TMP = '/tmp/os-config.tmp'
HASHED_ROOT_PASSWORD_FILE = '/root/os-config.shadow'
HASHED_ROOT_PASSWORD_FILE_TMP = '/root/os-config.shadow.tmp'
APP_NO_TIMER_STAMP_FILE = '/tmp/os-notimer.hook'
EXIT_CODE = 1
SIG_ARG_SEPARATOR = '&'
SIG_ARG_DATA_SEPARATOR = '#'
OVERLAY_BOX_SIZE_DEFAULT = 80
OVERLAY_BOX_SIZE_REDUCED = 50
_RE_HOSTNAME = re.compile(r'^[0-9A-Za-z\-\.]+$')


# -----------------------------------------------------------------------------
# TEXT constansts

TEXT_MAIN_CAPTION = 'CentOS-7 initial setup'
TEXT_MENU_CAPTION = 'Menu'
TEXT_CURRENT_SETTINGS_CAPTION = 'Current settings'
TEXT_ACTION_ELEMENT_INSTALL = 'Install with the current settings'
TEXT_ACTION_ELEMENT_INSTALL_HINT = 'CentOS-7 will be installed with the settings shown on the right.'
TEXT_ACTION_ELEMENT_CUSTOMIZE = 'Change settings'
TEXT_ACTION_ELEMENT_CUSTOMIZE_HINT = 'Change the installation settings.'
TEXT_ACTION_ELEMENT_EXIT = 'Exit to shell'
TEXT_ACTION_ELEMENT_EXIT_HINT = 'Interrupt the initial setup.'
TEXT_AUTOMATIC_INSTALL = 'The installation will start in {} seconds. Press any key to interrupt.'
TEXT_AUTOMATIC_INSTALL_CANCELLED = 'Automatic installation has been cancelled.'
TEXT_ELEMENT_HOSTNAME = 'Host name'
TEXT_ELEMENT_ROOTPASSWORD = 'Password for user "root"'
TEXT_ELEMENT_ETH0 = 'Network settings (NIC eth0)'
TEXT_ELEMENT_ETH0_MAC = 'Network settings (NIC eth0,\nMAC {})'
TEXT_ELEMENT_TARGET_DEVICE = 'Install to: /dev/sda'
TEXT_ELEMENT_TARGET_DEVICE_WARNING = 'All data on /dev/sda will be LOST.'
TEXT_ELEMENT_VALUE_NOT_GIVEN = '<Not specified>'
TEXT_ELEMENT_VALUE_USE_DHCP = 'Use DHCP'
TEXT_ELEMENT_VALUE_STATIC_IP = 'Set static IP address'
TEXT_ELEMENT_IP_ADDRESS = 'IP address'
TEXT_ELEMENT_SUBNET_MASK = 'Subnet mask'
TEXT_ELEMENT_DEFAULT_GATEWAY = 'Default gateway'
TEXT_ELEMENT_DNS_SERVERS = 'DNS server(s)'
TEXT_ELEMENT_DNS_SERVERS_EX = 'DNS server(s)\nseparated by commas or space characters'
TEXT_ELEMENT_KEYBOARD_HINT = 'Press <Up>, <Down>, <Enter> to select the item.'
TEXT_ELEMENT_KEYBOARD_DLG_HINT = 'Press <Esc> to close the dialog.'
TEXT_HOSTNAME_DIALOG_CAPTION = 'Specify the host name'
TEXT_PASSWD_DIALOG_CAPTION = 'Change the password for user "root"'
TEXT_PASSWD_DIALOG_PASSWD1 = 'New password'
TEXT_PASSWD_DIALOG_PASSWD2 = 'Confirm password'
TEXT_ETH0_DIALOG_CAPTION = 'Change network settings for NIC eth0'
TEXT_ETH0_STATIC_DIALOG_CAPTION = 'Set a static IP address for NIC eth0'
TEXT_BUTTON_APPLY = 'Apply'
TEXT_BUTTON_CANCEL = 'Cancel'
TEXT_ELEMENT_ESC_TO_EXIT = 'Press <ESC> to exit'
TEXT_ELEMENT_ESC_TO_CONTINUE = 'Press <ESC> to continue'
TEXT_ERROR_NOT_SPECIFIED = 'Not specified.'
TEXT_ERROR_INVALID_IP = "Specified value '{}' is not a valid network address."
TEXT_ERROR_INVALID_HOSTNAME = "Specified value '{}' is not a valid host name."
TEXT_ERROR_PASSWD = "The passwords you entered do not match or are empty."
# -----------------------------------------------------------------------------

def is_valid_ip_v4(ip):
    if ip.count('.') != 3:
        return False
    bits = ip.split('.')
    count = 0
    for t in bits:
        v = t.strip()
        if v:
            num = None
            try:
                num = int(v)
            except ValueError:
                pass
            if num is not None and num >= 0 and num<256:
                count += 1
    return count == 4


def is_valid_host_name(hostname):
    if len(hostname) > 253:
        return False
    if hostname.startswith('.') or hostname.startswith('-'):
        return False
    if not _RE_HOSTNAME.match(hostname):
        return False
    bits = hostname.split('.')
    for v in bits:
        if not v or len(v) > 63:
            return False
    return True


def rootpw_describe():
    if os.path.exists(HASHED_ROOT_PASSWORD_FILE):
        return '********'
    else:
        return TEXT_ELEMENT_VALUE_NOT_GIVEN


def assign_rootpw(rootpw):
    import crypt
    rootpw_hash = crypt.crypt(rootpw, salt=crypt.METHOD_SHA512)
    with open(HASHED_ROOT_PASSWORD_FILE_TMP, 'wt') as fh:
        print(rootpw_hash, end='', file=fh)
    os.rename(HASHED_ROOT_PASSWORD_FILE_TMP, HASHED_ROOT_PASSWORD_FILE)


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


class AppInputError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)


class StaticNetworkConfig:
    def __init__(self):
        self.ip = None
        self.netmask = None
        self.gateway = None
        self.nameserver = None


class AppConfig:
    def __init__(self):
        self.error_text = None
        self.hostname = None
        self.hostname_overlay = None
        self.eth0_mac_address = None
        self.eth0_use_dhcp = None
        self.eth0_static = StaticNetworkConfig()
        self.eth0_static_overlay = StaticNetworkConfig()
        self.eth0_static_overlay_last_error = None
        self.iso_version = None
        self.target_version = None

    def eth0_describe(self):
        if self.eth0_use_dhcp is not None:
            details = [TEXT_ELEMENT_VALUE_USE_DHCP if self.eth0_use_dhcp else TEXT_ELEMENT_VALUE_STATIC_IP]
            if not self.eth0_use_dhcp:
                align = 2 + max([len(TEXT_ELEMENT_IP_ADDRESS), len(TEXT_ELEMENT_SUBNET_MASK), len(TEXT_ELEMENT_DEFAULT_GATEWAY), len(TEXT_ELEMENT_DNS_SERVERS)])
                # ip address
                details += [ '{}{}'.format(''.join([TEXT_ELEMENT_IP_ADDRESS, ':']).ljust(align), self.eth0_static.ip if self.eth0_static.ip is not None else TEXT_ELEMENT_VALUE_NOT_GIVEN) ]
                # netmask
                details += [ '{}{}'.format(''.join([TEXT_ELEMENT_SUBNET_MASK, ':']).ljust(align), self.eth0_static.netmask if self.eth0_static.netmask is not None else TEXT_ELEMENT_VALUE_NOT_GIVEN) ]
                # gateway
                details += [ '{}{}'.format(''.join([TEXT_ELEMENT_DEFAULT_GATEWAY, ':']).ljust(align), self.eth0_static.gateway if self.eth0_static.gateway is not None else TEXT_ELEMENT_VALUE_NOT_GIVEN) ]
                # nameservers
                details += [ '{}{}'.format(''.join([TEXT_ELEMENT_DNS_SERVERS, ':']).ljust(align), self.eth0_static.nameserver if self.eth0_static.nameserver is not None else TEXT_ELEMENT_VALUE_NOT_GIVEN) ]
        else:
            details = ['<unknown>']
        return '\n'.join(details)

    def get_eth0_static_ip_to_edit(self):
        if self.eth0_static_overlay.ip is not None:
            return self.eth0_static_overlay.ip
        if self.eth0_static.ip is not None:
            return self.eth0_static.ip
        return ''

    def get_eth0_static_netmask_to_edit(self):
        if self.eth0_static_overlay.netmask is not None:
            return self.eth0_static_overlay.netmask
        if self.eth0_static.netmask is not None:
            return self.eth0_static.netmask
        return ''

    def get_eth0_static_gateway_to_edit(self):
        if self.eth0_static_overlay.gateway is not None:
            return self.eth0_static_overlay.gateway
        if self.eth0_static.gateway is not None:
            return self.eth0_static.gateway
        return ''

    def get_eth0_static_nameserver_to_edit(self):
        if self.eth0_static_overlay.nameserver is not None:
            return self.eth0_static_overlay.nameserver
        if self.eth0_static.nameserver is not None:
            return self.eth0_static.nameserver
        return ''

    def _strip_str_value(self, value):
        s = value.encode('ascii', 'backslashreplace').decode('utf-8')
        s = s.strip()
        if not s:
            return None
        return s

    def _eth0_static_validate(self):
        ipaddr = self._strip_str_value(self.eth0_static_overlay.ip)
        if ipaddr is None:
            self.eth0_static_overlay_last_error = 'ip'
            raise AppInputError('{}:\n{}: {}'.format(TEXT_ELEMENT_ETH0, TEXT_ELEMENT_IP_ADDRESS, TEXT_ERROR_NOT_SPECIFIED))
        if not is_valid_ip_v4(ipaddr):
            self.eth0_static_overlay_last_error = 'ip'
            raise AppInputError('{}:\n{}: {}'.format(TEXT_ELEMENT_ETH0, TEXT_ELEMENT_IP_ADDRESS, TEXT_ERROR_INVALID_IP.format(ipaddr)))

        netmask = self._strip_str_value(self.eth0_static_overlay.netmask)
        if netmask is None:
            self.eth0_static_overlay_last_error = 'netmask'
            raise AppInputError('{}:\n{}: {}'.format(TEXT_ELEMENT_ETH0, TEXT_ELEMENT_SUBNET_MASK, TEXT_ERROR_NOT_SPECIFIED))
        if not is_valid_ip_v4(netmask):
            self.eth0_static_overlay_last_error = 'netmask'
            raise AppInputError('{}:\n{}: {}'.format(TEXT_ELEMENT_ETH0, TEXT_ELEMENT_SUBNET_MASK, TEXT_ERROR_INVALID_IP.format(netmask)))

        gateway = self._strip_str_value(self.eth0_static_overlay.gateway)
        if gateway is None:
            self.eth0_static_overlay_last_error = 'gateway'
            raise AppInputError('{}:\n{}: {}'.format(TEXT_ELEMENT_ETH0, TEXT_ELEMENT_DEFAULT_GATEWAY, TEXT_ERROR_NOT_SPECIFIED))
        if not is_valid_ip_v4(gateway):
            self.eth0_static_overlay_last_error = 'gateway'
            raise AppInputError('{}:\n{}: {}'.format(TEXT_ELEMENT_ETH0, TEXT_ELEMENT_DEFAULT_GATEWAY, TEXT_ERROR_INVALID_IP.format(gateway)))

        ns_list = []
        nameserver = self._strip_str_value(self.eth0_static_overlay.nameserver)
        if nameserver is not None:
            bits = nameserver.replace(',', ' ').split()
            for v in bits:
                ns_value = v.strip()
                if ns_value:
                    if not is_valid_ip_v4(ns_value):
                        self.eth0_static_overlay_last_error = 'nameserver'
                        raise AppInputError('{}:\n{}: {}'.format(TEXT_ELEMENT_ETH0, TEXT_ELEMENT_DNS_SERVERS, TEXT_ERROR_INVALID_IP.format(ns_value)))
                    else:
                        ns_list.append(ns_value)
        if ns_list:
            nameserver = ','.join(ns_list)

        new_config = StaticNetworkConfig()
        new_config.ip = ipaddr
        new_config.netmask = netmask
        new_config.gateway = gateway
        new_config.nameserver = nameserver
        return new_config

    def hostname_describe(self):
        if self.hostname is None:
            return '<unknown>'
        return self.hostname

    def get_hostname_to_edit(self):
        if self.hostname_overlay is not None:
            return self.hostname_overlay
        return self.hostname

    def _hostname_validate(self):
        valid = True
        hostname = self._strip_str_value(self.hostname_overlay)
        if not hostname:
            valid = False
        elif hostname != self.hostname_overlay.strip():
            valid = False # unicode
        else:
            valid = is_valid_host_name(hostname)
        if not valid:
            raise AppInputError(TEXT_ERROR_INVALID_HOSTNAME.format(hostname if hostname is not None else ''))
        return hostname

    def eth0_dhcp_apply(self):
        self.eth0_use_dhcp = True
        self.persist_changes()

    def eth0_static_apply(self):
        self.eth0_static = self._eth0_static_validate()
        self.eth0_use_dhcp = False
        self.eth0_static_overlay = StaticNetworkConfig()
        self.persist_changes()

    def hostname_apply(self):
        self.hostname = self._hostname_validate()
        self.hostname_overlay = None
        self.persist_changes()

    def persist_changes(self):
        config = load_ini_config(APP_CONFIG_FILE)
        if not config.has_section('main'):
            config.add_section('main')
        config.set('main', 'hostname', self.hostname)
        if not config.has_section('eth0'):
            config.add_section('eth0')
        config.set('eth0', 'bootproto', 'dhcp' if self.eth0_use_dhcp else 'static')
        if self.eth0_static.ip is not None:
            config.set('eth0', 'ip', self.eth0_static.ip)
        else:
            config.remove_option('eth0', 'ip')
        if self.eth0_static.netmask is not None:
            config.set('eth0', 'netmask', self.eth0_static.netmask)
        else:
            config.remove_option('eth0', 'netmask')
        if self.eth0_static.gateway is not None:
            config.set('eth0', 'gateway', self.eth0_static.gateway)
        else:
            config.remove_option('eth0', 'gateway')
        if self.eth0_static.nameserver is not None:
            config.set('eth0', 'nameserver', self.eth0_static.nameserver)
        else:
            config.remove_option('eth0', 'nameserver')
        with open(APP_CONFIG_FILE_TMP, 'wb') as configfile:
            config.write(configfile)
        os.rename(APP_CONFIG_FILE_TMP, APP_CONFIG_FILE)


def get_mac_address(ifname):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', ifname[:15]))
        return '-'.join(['%02X' % ord(char) for char in info[18:24]])
    except IOError as exc:
        if exc.errno == 19: # no such device
            return None
        raise


def load_version_info(version_file, default=None):
    version_info = default
    if not os.path.exists(version_file) and default is not None:
        return default
    with open(version_file, mode='rt') as fh:
        for ln in [ ln.rstrip('\r\n').strip() for ln in fh.readlines() ]:
            if ln:
                version_info = ln
                break
    return version_info


def init_app_config(app_config):
    config = load_ini_config(APP_CONFIG_FILE)

    hostname = get_ini_conf_string1(config, 'main', 'hostname')
    bootproto = get_ini_conf_string1(config, 'eth0', 'bootproto')
    ip = get_ini_conf_string0(config, 'eth0', 'ip')
    netmask = get_ini_conf_string0(config, 'eth0', 'netmask')
    gateway = get_ini_conf_string0(config, 'eth0', 'gateway')
    nameserver = get_ini_conf_string0(config, 'eth0', 'nameserver')

    app_config.eth0_mac_address = get_mac_address('eth0')
    app_config.hostname = hostname
    app_config.eth0_use_dhcp = True if bootproto == 'dhcp' else False
    app_config.eth0_static.ip = ip
    app_config.eth0_static.netmask = netmask
    app_config.eth0_static.gateway = gateway
    app_config.eth0_static.nameserver = nameserver


class AppHostNameEditDisplay(urwid.WidgetWrap):
    signals = ['sig.hostname']

    def __init__(self, app_config):
        self.app_config = app_config
        self.hostname_bar = urwid.Edit(edit_text=app_config.get_hostname_to_edit())
        content = [
            urwid.Divider(),
            urwid.Text(TEXT_ELEMENT_HOSTNAME + ':'),
            urwid.AttrMap(self.hostname_bar, 'app.editbox', 'app.editfocus'),
            urwid.Divider(),
            urwid.Columns([
                urwid.Divider(),
                ('fixed', 10, urwid.AttrMap(urwid.Button(TEXT_BUTTON_APPLY, self.on_apply), 'app.button', 'app.buttonfocus')),
                ('fixed', 10, urwid.AttrMap(urwid.Button(TEXT_BUTTON_CANCEL, self.on_cancel), 'app.button', 'app.buttonfocus')),
                urwid.Divider()
            ], dividechars=8)
        ]
        walker = urwid.SimpleListWalker(content)
        self.footer = urwid.Pile([urwid.Text(TEXT_ELEMENT_KEYBOARD_DLG_HINT), urwid.Text(TEXT_ELEMENT_KEYBOARD_HINT)])
        self.view = urwid.AttrMap(urwid.LineBox(urwid.Frame(urwid.ListBox(walker), footer=self.footer), title=TEXT_HOSTNAME_DIALOG_CAPTION), 'app.dialog')
        urwid.WidgetWrap.__init__(self, self.view)

    def on_apply(self, *args):
        self.app_config.hostname_overlay = self.hostname_bar.get_edit_text()
        self._emit(self.signals[0], SIG_ARG_SEPARATOR.join(['.quit', '.apply']))

    def do_cancel(self):
        self.app_config.hostname_overlay = None
        self._emit(self.signals[0], '.quit')

    def on_cancel(self, *args):
        self.do_cancel()

    def keypress(self, size, key):
        if key == 'esc':
            self.do_cancel()
        else:
            return self.__super.keypress(size, key)


class AppRootPasswordEditDisplay(urwid.WidgetWrap):
    signals = ['sig.rootpw']

    def __init__(self):
        self.rootpw1_bar = urwid.Edit(mask='*')
        self.rootpw2_bar = urwid.Edit(mask='*')
        content = [
            urwid.Divider(),
            urwid.Text(TEXT_PASSWD_DIALOG_PASSWD1 + ':'),
            urwid.AttrMap(self.rootpw1_bar, 'app.editbox', 'app.editfocus'),
            urwid.Text(TEXT_PASSWD_DIALOG_PASSWD2 + ':'),
            urwid.AttrMap(self.rootpw2_bar, 'app.editbox', 'app.editfocus'),
            urwid.Divider(),
            urwid.Columns([
                urwid.Divider(),
                ('fixed', 10, urwid.AttrMap(urwid.Button(TEXT_BUTTON_APPLY, self.on_apply), 'app.button', 'app.buttonfocus')),
                ('fixed', 10, urwid.AttrMap(urwid.Button(TEXT_BUTTON_CANCEL, self.on_cancel), 'app.button', 'app.buttonfocus')),
                urwid.Divider()
            ], dividechars=8)
        ]
        walker = urwid.SimpleListWalker(content)
        self.footer = urwid.Pile([urwid.Text(TEXT_ELEMENT_KEYBOARD_DLG_HINT), urwid.Text(TEXT_ELEMENT_KEYBOARD_HINT)])
        self.view = urwid.AttrMap(urwid.LineBox(urwid.Frame(urwid.ListBox(walker), footer=self.footer), title=TEXT_PASSWD_DIALOG_CAPTION), 'app.dialog')
        urwid.WidgetWrap.__init__(self, self.view)

    def on_apply(self, *args):
        pw1 = self.rootpw1_bar.get_edit_text()
        pw2 = self.rootpw2_bar.get_edit_text()
        subject = ''
        if pw1 and pw2 and (pw1 == pw2):
            subject = pw1
        self._emit(self.signals[0], SIG_ARG_SEPARATOR.join(['.quit', SIG_ARG_DATA_SEPARATOR.join(['.apply', base64.b64encode(subject)])]))

    def do_cancel(self):
        self._emit(self.signals[0], '.quit')

    def on_cancel(self, *args):
        self.do_cancel()

    def keypress(self, size, key):
        if key == 'esc':
            self.do_cancel()
        else:
            return self.__super.keypress(size, key)


class AppStaticNeworkDisplay(urwid.WidgetWrap):
    signals = ['sig.eth0.static']

    def __init__(self, app_config):
        self.app_config = app_config
        self.ipaddr_bar = urwid.Edit(edit_text=app_config.get_eth0_static_ip_to_edit())
        self.netmask_bar = urwid.Edit(edit_text=app_config.get_eth0_static_netmask_to_edit())
        self.gateway_bar = urwid.Edit(edit_text=app_config.get_eth0_static_gateway_to_edit())
        self.nameserver_bar = urwid.Edit(edit_text=app_config.get_eth0_static_nameserver_to_edit())
        focus_map = {'ip': 1, 'netmask': 3, 'gateway': 5, 'nameserver': 7}
        content = [
            urwid.Text(TEXT_ELEMENT_IP_ADDRESS + ':'),
            urwid.AttrMap(self.ipaddr_bar, 'app.editbox', 'app.editfocus'),
            urwid.Text(TEXT_ELEMENT_SUBNET_MASK + ':'),
            urwid.AttrMap(self.netmask_bar, 'app.editbox', 'app.editfocus'),
            urwid.Text(TEXT_ELEMENT_DEFAULT_GATEWAY + ':'),
            urwid.AttrMap(self.gateway_bar, 'app.editbox', 'app.editfocus'),
            urwid.Text(TEXT_ELEMENT_DNS_SERVERS_EX + ':'),
            urwid.AttrMap(self.nameserver_bar, 'app.editbox', 'app.editfocus'),
            urwid.Divider(),
            urwid.Columns([
                urwid.Divider(),
                ('fixed', 10, urwid.AttrMap(urwid.Button(TEXT_BUTTON_APPLY, self.on_apply), 'app.button', 'app.buttonfocus')),
                ('fixed', 10, urwid.AttrMap(urwid.Button(TEXT_BUTTON_CANCEL, self.on_cancel), 'app.button', 'app.buttonfocus')),
                urwid.Divider()
            ], dividechars=8)
        ]
        walker = urwid.SimpleListWalker(content)
        focus_idx = None
        if app_config.eth0_static_overlay_last_error is not None:
            focus_idx = focus_map.get(app_config.eth0_static_overlay_last_error)
            app_config.eth0_static_overlay_last_error = None
        if focus_idx is not None:
            walker.set_focus(focus_idx)
        self.footer = urwid.Pile([urwid.Text(TEXT_ELEMENT_KEYBOARD_DLG_HINT), urwid.Text(TEXT_ELEMENT_KEYBOARD_HINT)])
        self.view = urwid.AttrMap(urwid.LineBox(urwid.Frame(urwid.ListBox(walker), footer=self.footer), title=TEXT_ETH0_STATIC_DIALOG_CAPTION), 'app.dialog')
        urwid.WidgetWrap.__init__(self, self.view)

    def on_apply(self, *args):
        self.app_config.eth0_static_overlay.ip = self.ipaddr_bar.get_edit_text()
        self.app_config.eth0_static_overlay.netmask = self.netmask_bar.get_edit_text()
        self.app_config.eth0_static_overlay.gateway = self.gateway_bar.get_edit_text()
        self.app_config.eth0_static_overlay.nameserver = self.nameserver_bar.get_edit_text()
        self._emit(self.signals[0], SIG_ARG_SEPARATOR.join(['.quit', '.apply']))

    def do_cancel(self):
        self.app_config.eth0_static_overlay = StaticNetworkConfig()
        self._emit(self.signals[0], '.quit')

    def on_cancel(self, *args):
        self.do_cancel()

    def keypress(self, size, key):
        if key == 'esc':
            self.do_cancel()
        else:
            return self.__super.keypress(size, key)


class AppNeworkCustomizeDisplay(urwid.WidgetWrap):
    signals = ['sig.eth0']

    def __init__(self, app_config):
        h1 = '*' if app_config.eth0_use_dhcp else ' '
        h2 = '*' if not app_config.eth0_use_dhcp else ' '
        focus_idx = 0 if app_config.eth0_use_dhcp else 1
        self.actions = [(' '.join([h1, TEXT_ELEMENT_VALUE_USE_DHCP]), '.dhcp'), (' '.join([h2, TEXT_ELEMENT_VALUE_STATIC_IP]), '.static')]
        walker = urwid.SimpleListWalker([urwid.AttrMap(urwid.Text(a[0]), None, 'app.focus') for a in self.actions])
        walker.set_focus(focus_idx)
        self.listbox = urwid.ListBox(walker)
        self.footer = urwid.Pile([urwid.Text(TEXT_ELEMENT_KEYBOARD_DLG_HINT), urwid.Text(TEXT_ELEMENT_KEYBOARD_HINT)])
        self.view = urwid.AttrMap(urwid.LineBox(urwid.Frame(self.listbox, footer=self.footer), title=TEXT_ETH0_DIALOG_CAPTION), 'app.dialog')
        urwid.WidgetWrap.__init__(self, self.view)

    def keypress(self, size, key):
        if key == 'up':
            _, idx = self.listbox.get_focus()
            if idx > 0:
                idx -= 1
                self.listbox.set_focus(idx)
        elif key == 'down':
            _, idx = self.listbox.get_focus()
            if idx + 1 < len(self.actions):
                idx += 1
                self.listbox.set_focus(idx)
        elif key == 'enter':
            _, idx = self.listbox.get_focus()
            self._emit(self.signals[0], SIG_ARG_SEPARATOR.join(['.quit', self.actions[idx][1]]))
        elif key == 'esc':
            self._emit(self.signals[0], '.quit')


class AppCustomizeDisplay(urwid.WidgetWrap):
    signals = ['sig.customize']

    def __init__(self, app_config):
        self.actions = [
            ('.hostname', TEXT_ELEMENT_HOSTNAME),
            ('.rootpw', TEXT_ELEMENT_ROOTPASSWORD),
            ('.network', TEXT_ELEMENT_ETH0.format(app_config.eth0_mac_address))]

        self.listbox = urwid.ListBox(urwid.SimpleListWalker([urwid.AttrMap(urwid.Text(a[1]), None, 'app.focus') for a in self.actions]))
        self.footer = urwid.Pile([urwid.Text(TEXT_ELEMENT_KEYBOARD_DLG_HINT), urwid.Text(TEXT_ELEMENT_KEYBOARD_HINT)])
        self.view = urwid.AttrMap(urwid.LineBox(urwid.Frame(self.listbox, footer=self.footer), title=TEXT_ACTION_ELEMENT_CUSTOMIZE), 'app.dialog')
        urwid.WidgetWrap.__init__(self, self.view)

    def keypress(self, size, key):
        if key == 'up':
            _, idx = self.listbox.get_focus()
            if idx > 0:
                idx -= 1
                self.listbox.set_focus(idx)
        elif key == 'down':
            _, idx = self.listbox.get_focus()
            if idx + 1 < len(self.actions):
                idx += 1
                self.listbox.set_focus(idx)
        elif key == 'enter':
            _, idx = self.listbox.get_focus()
            self._emit(self.signals[0], SIG_ARG_SEPARATOR.join(['.quit', self.actions[idx][0]]))
        elif key == 'esc':
            self._emit(self.signals[0], '.quit')


class AppErrorDisplay(urwid.WidgetWrap):
    signals = ['sig.error']

    def __init__(self, error_text, title='', topmost=False, post_call=None):
        self.topmost = topmost
        self.post_call = post_call
        self.err_text_bar = urwid.Text(error_text)
        text_panel = urwid.Pile([urwid.AttrMap(urwid.Text("Initial setup error:"), 'app.err.title'), self.err_text_bar])
        if topmost:
            self.status_bar = urwid.Text(TEXT_ELEMENT_ESC_TO_EXIT)
        else:
            self.status_bar = urwid.Text(TEXT_ELEMENT_ESC_TO_CONTINUE)
        self.view = urwid.AttrMap(urwid.LineBox(urwid.AttrMap(urwid.Frame(urwid.Filler(text_panel, valign='top'), footer=self.status_bar), 'app.err.default'), title=title), 'app.err.title')

        urwid.WidgetWrap.__init__(self, self.view)

    def keypress(self, size, key):
        if key == 'esc':
            if self.topmost:
                self._emit(self.signals[0], '.main.exit')
            else:
                if self.post_call is None:
                    self._emit(self.signals[0], '.quit')
                else:
                    self._emit(self.signals[0], SIG_ARG_SEPARATOR.join(['.quit', self.post_call]))


def format_automatic_install_message(elapsed_time):
    remaining_time = int(AUTOMATIC_INSTALL_TIMEOUT) - int(elapsed_time)
    return TEXT_AUTOMATIC_INSTALL.format(remaining_time)


class TimerState:
    def __init__(self):
        self._is_timer_in_progress = not os.path.exists(APP_NO_TIMER_STAMP_FILE)
        self._last_external_status = None
        self._seen_keypress = False

    def on_keypress(self):
        self._seen_keypress = True

    def on_timer_start(self):
        self._is_timer_in_progress = True

    def on_timer_cancel(self):
        self._is_timer_in_progress = False

    def is_timer_in_progress(self):
        return self._is_timer_in_progress

    def on_idle(self):
        need_timer_restart = False
        need_timer_cancel = False
        status_changed = False
        current_external_status = not os.path.exists(APP_NO_TIMER_STAMP_FILE)
        if self._last_external_status is None:
            status_changed = True
        elif self._last_external_status != current_external_status:
            status_changed = True
        if status_changed:
            self._seen_keypress = False
            self._last_external_status = current_external_status
        if status_changed and self._last_external_status and not self._is_timer_in_progress and not self._seen_keypress:
            need_timer_restart = True
        else:
            if status_changed and self._is_timer_in_progress:
                if not self._last_external_status:
                    need_timer_cancel = True
        return need_timer_restart, need_timer_cancel


class AppMainDisplay(urwid.WidgetWrap):
    signals = ['sig.main']

    def __init__(self, app_config, timer_config):
        self.app_config = app_config
        self.timer_config = timer_config
        self.hostname_text_bar = urwid.Text(app_config.hostname_describe())
        self.eth0_text_bar = urwid.Text(app_config.eth0_describe())
        self.rootpw_text_bar = None

        self.actions = [
            ('.install', TEXT_ACTION_ELEMENT_INSTALL, TEXT_ACTION_ELEMENT_INSTALL_HINT),
            ('.customize', TEXT_ACTION_ELEMENT_CUSTOMIZE, TEXT_ACTION_ELEMENT_CUSTOMIZE_HINT),
            ('.exit', TEXT_ACTION_ELEMENT_EXIT, TEXT_ACTION_ELEMENT_EXIT_HINT)]

        self.listbox = urwid.ListBox(urwid.SimpleListWalker([urwid.AttrMap(urwid.Text(a[1]), None, 'app.focus') for a in self.actions]))

        self.menu_bar = urwid.Pile([
            urwid.AttrMap(urwid.Text(TEXT_MENU_CAPTION, align='center'), 'app.title'),
            urwid.Divider('-'),
            urwid.BoxAdapter(self.listbox, 2*len(self.actions))
        ])

        network_caption = TEXT_ELEMENT_ETH0 if app_config.eth0_mac_address is None else TEXT_ELEMENT_ETH0_MAC.format(app_config.eth0_mac_address)

        self.rootpw_text_bar = urwid.Text(rootpw_describe())

        self.current_settings_bar = urwid.Pile([
            urwid.AttrMap(urwid.Text(TEXT_CURRENT_SETTINGS_CAPTION, align='center'), 'app.title'),
            urwid.Divider('-'),
            urwid.AttrMap(urwid.Text(TEXT_ELEMENT_TARGET_DEVICE), 'app.title'),
            urwid.Text(TEXT_ELEMENT_TARGET_DEVICE_WARNING),
            urwid.Divider(),
            urwid.AttrMap(urwid.Text(TEXT_ELEMENT_HOSTNAME + ':'), 'app.title'),
            self.hostname_text_bar,
            urwid.Divider(),
            urwid.AttrMap(urwid.Text(TEXT_ELEMENT_ROOTPASSWORD + ':'), 'app.title'),
            self.rootpw_text_bar,
            urwid.Divider(),
            urwid.AttrMap(urwid.Text(network_caption + ':'), 'app.title'),
            self.eth0_text_bar
        ])

        status_text = TEXT_ACTION_ELEMENT_INSTALL_HINT if not self.timer_config.is_timer_in_progress() else format_automatic_install_message(0)
        self.status_bar = urwid.Text(status_text)
        self.columns = urwid.Columns([('weight', 1, urwid.Filler(self.menu_bar, valign='top')), ('fixed', 1, urwid.SolidFill(u'\u2502')), ('weight', 1, urwid.Filler(self.current_settings_bar, valign='top'))])
        self.footer = urwid.Pile([urwid.AttrMap(urwid.Text(TEXT_ELEMENT_KEYBOARD_HINT), 'app.default'), urwid.AttrMap(self.status_bar, 'app.alarm')])
        self.view = urwid.AttrMap(urwid.LineBox(urwid.AttrMap(urwid.Frame(urwid.LineBox(self.columns), footer=self.footer), 'app.default'), title=TEXT_MAIN_CAPTION), 'app.title')

        urwid.WidgetWrap.__init__(self, self.view)

    def on_app_reconf(self):
        self.hostname_text_bar.set_text(self.app_config.hostname_describe())
        self.eth0_text_bar.set_text(self.app_config.eth0_describe())
        if self.rootpw_text_bar is not None:
            self.rootpw_text_bar.set_text(rootpw_describe())

    def keypress(self, size, key):
        if self.timer_config is not None:
            self.timer_config.on_keypress()
            if self.timer_config.is_timer_in_progress():
                self._emit(self.signals[0], '.cancel.timer')
        if key == 'up':
            _, idx = self.listbox.get_focus()
            if idx > 0:
                idx -= 1
                self.listbox.set_focus(idx)
                self._emit(self.signals[0], SIG_ARG_DATA_SEPARATOR.join(['sig.main.hint', base64.b64encode(self.actions[idx][2])]))
        elif key == 'down':
            _, idx = self.listbox.get_focus()
            if idx + 1 < len(self.actions):
                idx += 1
                self.listbox.set_focus(idx)
                self._emit(self.signals[0], SIG_ARG_DATA_SEPARATOR.join(['sig.main.hint', base64.b64encode(self.actions[idx][2])]))
        elif key == 'enter':
            _, idx = self.listbox.get_focus()
            self._emit(self.signals[0], self.actions[idx][0])
        else:
            if key != 'esc':
                _, idx = self.listbox.get_focus()
                self._emit(self.signals[0], SIG_ARG_DATA_SEPARATOR.join(['sig.main.hint', base64.b64encode(self.actions[idx][2])]))


def extract_exception_line():
    tb = sys.exc_info()[-1]
    stk = traceback.extract_tb(tb)
    stk_idx = 0
    i = 0
    for frame in stk:
        frame_file = frame[0]
        if frame_file == __file__:
            stk_idx = i
        i += 1
    linenum = stk[stk_idx][1]
    return linenum


def format_exception_one_line(e):
    exc_line = extract_exception_line()
    exc_class = e.__class__.__name__
    return "line=%s: %s : %s" % (exc_line, exc_class, e)


class MainApp(urwid.WidgetPlaceholder):
    def __init__(self, app_config, debug):
        self.app_config = app_config
        self.debug = debug
        self.timer_config = None
        self.elapsed_time = 0
        if app_config.error_text is None:
            self.timer_config = TimerState()
            self.view = AppMainDisplay(app_config, self.timer_config)
            self.error_mode = False
        else:
            self.view = AppErrorDisplay(app_config.error_text, title=TEXT_MAIN_CAPTION, topmost=True)
            self.error_mode = True
        self.sig_subscribe(self.view)
        urwid.WidgetPlaceholder.__init__(self, self.view)

    def sig_subscribe(self, w):
        w_sig = None
        w_signals = getattr(w, 'signals', None)
        if isinstance(w_signals, list):
            w_sig = w_signals[0]
        if w_sig is not None:
            urwid.connect_signal(w, w_sig, lambda _, arg: self.on_event(w_sig, arg))

    def sig_unsubscribe(self, w):
        w_sig = None
        w_signals = getattr(w, 'signals', None)
        if isinstance(w_signals, list):
            w_sig = w_signals[0]
        if w_sig is not None:
            urwid.disconnect_signal(w, w_sig, lambda _, arg: self.on_event(w_sig, arg))

    def _decode_signal(self, sig_id, sig_arg_encoded):
        sig_name = None
        sig_arg = None
        sig_name_post = None
        sig_arg_post = None
        sig_bits = sig_arg_encoded.split(SIG_ARG_SEPARATOR, 1)
        if sig_bits[0].startswith('sig.'):
            sig_name = sig_bits[0]
        else:
            sig_name = sig_id + sig_bits[0]
        if len(sig_bits) > 1:
            if sig_bits[1].startswith('sig.'):
                sig_name_post = sig_bits[1]
            else:
                sig_name_post = sig_id + sig_bits[1]
        data1 = sig_name.split(SIG_ARG_DATA_SEPARATOR, 1)
        if len(data1) > 1:
            sig_name = data1[0]
            sig_arg = base64.b64decode(data1[1])
        if sig_name_post is not None:
            data2 = sig_name_post.split(SIG_ARG_DATA_SEPARATOR, 1)
            if len(data2) > 1:
                sig_name_post = data2[0]
                sig_arg_post = base64.b64decode(data2[1])
        return sig_name, sig_arg, sig_name_post, sig_arg_post

    def on_event(self, sig_id, sig_arg_encoded):
        debug_status = None
        handler = None
        handler_post = None
        aborted = False
        sig_name = None
        sig_arg = None
        sig_name_post = None
        sig_arg_post = None
        try:
            sig_name, sig_arg, sig_name_post, sig_arg_post = self._decode_signal(sig_id, sig_arg_encoded)
            if sig_name.endswith('.quit'):
                handler = self.on_dialog_quit
            else:
                handler = getattr(self, 'on_'+ sig_name.replace('.', '_'), None)

            if sig_name_post is not None:
                handler_post = getattr(self, 'on_'+ sig_name_post.replace('.', '_'), None)

            if self.debug:
                h1 = ':' if handler else '!'
                debug_status = h1 + sig_name
                if sig_name_post is not None:
                    h2 = ':' if handler_post else '!'
                    debug_status = debug_status + h2 + sig_name_post
            else:
                if handler is None:
                    debug_status = '!' + sig_name
                if sig_name_post is not None and handler_post is None:
                    if debug_status is None:
                        debug_status = ':' + sig_name + '!' + sig_name_post
                    else:
                        debug_status = '!' + sig_name_post
        except Exception as ex:
            debug_status = format_exception_one_line(ex)
            aborted = True

        if debug_status is not None:
            self.view.status_bar.set_text(debug_status)
        if aborted:
            return

        main_exit = None

        debug_status = None
        if handler is not None:
            try:
                handler(sig_arg)
            except urwid.ExitMainLoop as ex:
                main_exit = True
            except Exception as ex:
                debug_status = format_exception_one_line(ex)
        if debug_status is not None:
            self.view.status_bar.set_text(debug_status)
            return

        if handler_post is not None:
            try:
                handler_post(sig_arg_post)
            except urwid.ExitMainLoop as ex:
                main_exit = True
            except Exception as ex:
                debug_status = format_exception_one_line(ex)
        if debug_status is not None:
            self.view.status_bar.set_text(debug_status)

        if debug_status is None and main_exit:
            raise urwid.ExitMainLoop()

    def on_sig_main_hint(self, hint, *args):
        self.view.status_bar.set_text(hint)

    def on_sig_main_install(self, *args):
        global EXIT_CODE
        EXIT_CODE = 0
        raise urwid.ExitMainLoop()

    def on_sig_main_customize(self, *args):
        overlay_box_size = OVERLAY_BOX_SIZE_REDUCED
        w = AppCustomizeDisplay(self.app_config)
        self.sig_subscribe(w)
        self.original_widget = urwid.Overlay(w,
            self.view,
            align='center', width=('relative', overlay_box_size),
            valign='middle', height=('relative', overlay_box_size))

    def on_dialog_quit(self, *args):
        self.sig_unsubscribe(self.original_widget)
        self.original_widget = self.view

    def on_sig_customize_hostname(self, *args):
        overlay_box_size = OVERLAY_BOX_SIZE_REDUCED
        w = AppHostNameEditDisplay(self.app_config)
        self.sig_subscribe(w)
        self.original_widget = urwid.Overlay(w,
            self.view,
            align='center', width=('relative', overlay_box_size),
            valign='middle', height=('relative', overlay_box_size))

    def on_sig_customize_rootpw(self, *args):
        overlay_box_size = OVERLAY_BOX_SIZE_REDUCED
        w = AppRootPasswordEditDisplay()
        self.sig_subscribe(w)
        self.original_widget = urwid.Overlay(w,
            self.view,
            align='center', width=('relative', overlay_box_size),
            valign='middle', height=('relative', overlay_box_size))

    def on_sig_eth0_dhcp(self, *args):
        overlay_box_size = OVERLAY_BOX_SIZE_DEFAULT
        error_text = None
        try:
            self.app_config.eth0_dhcp_apply()
        except AppInputError as ex:
            overlay_box_size = OVERLAY_BOX_SIZE_REDUCED
            error_text = str(ex)
        except Exception:
            etype, evalue, tb = sys.exc_info()
            error_text = ''.join(traceback.format_tb(tb) + traceback.format_exception_only(etype, evalue))
        if error_text is not None:
            w = AppErrorDisplay(error_text=error_text)
            self.sig_subscribe(w)
            self.original_widget = urwid.Overlay(w,
                self.view,
                align='center', width=('relative', overlay_box_size),
                valign='middle', height=('relative', overlay_box_size))
        else:
            self.view.on_app_reconf()

    def on_sig_eth0_static(self, *args):
        overlay_box_size = OVERLAY_BOX_SIZE_REDUCED
        w = AppStaticNeworkDisplay(self.app_config)
        self.sig_subscribe(w)
        self.original_widget = urwid.Overlay(w,
            self.view,
            align='center', width=('relative', overlay_box_size),
            valign='middle', height=('relative', overlay_box_size))

    def on_sig_eth0_static_apply(self, *args):
        overlay_box_size = OVERLAY_BOX_SIZE_DEFAULT
        error_text = None
        try:
            self.app_config.eth0_static_apply()
        except AppInputError as ex:
            overlay_box_size = OVERLAY_BOX_SIZE_REDUCED
            error_text = str(ex)
        except Exception:
            etype, evalue, tb = sys.exc_info()
            error_text = ''.join(traceback.format_tb(tb) + traceback.format_exception_only(etype, evalue))
        if error_text is not None:
            w = AppErrorDisplay(error_text=error_text, post_call='sig.eth0.static')
            self.sig_subscribe(w)
            self.original_widget = urwid.Overlay(w,
                self.view,
                align='center', width=('relative', overlay_box_size),
                valign='middle', height=('relative', overlay_box_size))
        else:
            self.view.on_app_reconf()

    def on_sig_hostname_apply(self, *args):
        overlay_box_size = OVERLAY_BOX_SIZE_DEFAULT
        error_text = None
        try:
            self.app_config.hostname_apply()
        except AppInputError as ex:
            overlay_box_size = OVERLAY_BOX_SIZE_REDUCED
            error_text = str(ex)
        except Exception:
            etype, evalue, tb = sys.exc_info()
            error_text = ''.join(traceback.format_tb(tb) + traceback.format_exception_only(etype, evalue))
        if error_text is not None:
            w = AppErrorDisplay(error_text=error_text, post_call='sig.customize.hostname')
            self.sig_subscribe(w)
            self.original_widget = urwid.Overlay(w,
                self.view,
                align='center', width=('relative', overlay_box_size),
                valign='middle', height=('relative', overlay_box_size))
        else:
            self.view.on_app_reconf()

    def on_sig_rootpw_apply(self, rootpw, *args):
        overlay_box_size = OVERLAY_BOX_SIZE_DEFAULT
        error_text = None
        try:
            if rootpw:
                assign_rootpw(rootpw)
            else:
                error_text = TEXT_ERROR_PASSWD
        except AppInputError as ex:
            overlay_box_size = OVERLAY_BOX_SIZE_REDUCED
            error_text = str(ex)
        except Exception:
            etype, evalue, tb = sys.exc_info()
            error_text = ''.join(traceback.format_tb(tb) + traceback.format_exception_only(etype, evalue))
        if error_text is not None:
            w = AppErrorDisplay(error_text=error_text, post_call='sig.customize.rootpw')
            self.sig_subscribe(w)
            self.original_widget = urwid.Overlay(w,
                self.view,
                align='center', width=('relative', overlay_box_size),
                valign='middle', height=('relative', overlay_box_size))
        else:
            self.view.on_app_reconf()

    def on_sig_customize_network(self, *args):
        overlay_box_size = OVERLAY_BOX_SIZE_REDUCED
        w = AppNeworkCustomizeDisplay(self.app_config)
        self.sig_subscribe(w)
        self.original_widget = urwid.Overlay(w,
            self.view,
            align='center', width=('relative', overlay_box_size),
            valign='middle', height=('relative', overlay_box_size))

    def on_sig_error_main_exit(self, *args):
        raise urwid.ExitMainLoop()

    def on_sig_main_exit(self, *args):
        if not self.debug:
            global EXIT_CODE
            EXIT_CODE = 2
        raise urwid.ExitMainLoop()

    def on_sig_main_cancel_timer(self, *args):
        self.do_cancel_timer()

    def do_cancel_timer(self):
        self.elapsed_time = 0
        self.timer_config.on_timer_cancel()
        self.view.status_bar.set_text(TEXT_AUTOMATIC_INSTALL_CANCELLED)

    def on_app_timeout(self, loop, user_data):
        if not self.timer_config.is_timer_in_progress():
            return
        self.elapsed_time += 1
        if self.elapsed_time < AUTOMATIC_INSTALL_TIMEOUT:
            self.view.status_bar.set_text(format_automatic_install_message(self.elapsed_time))
            loop.set_alarm_in(1, self.on_app_timeout)
        else:
            self.on_sig_main_install()

    def on_app_idle(self, loop, user_data):
        need_timer_restart, need_timer_cancel = self.timer_config.on_idle()
        if need_timer_restart:
            self.timer_config.on_timer_start()
            self.view.status_bar.set_text(format_automatic_install_message(self.elapsed_time))
            loop.set_alarm_in(1, self.on_app_timeout)
        elif need_timer_cancel:
            self.do_cancel_timer()
        self.view.on_app_reconf()
        loop.set_alarm_in(1, self.on_app_idle)

    def main(self):
        text_color = 'light gray'
        text_color_title = 'white'
        text_color_focus = 'black'
        text_color_dialog = 'black'
        text_color_err = 'light gray'
        text_color_err_title = 'white'
        text_color_err_focus = 'black'
        background_color = 'dark blue'
        background_color_dialog = 'light gray'
        background_color_focus = 'dark cyan'
        background_color_err = 'dark red'
        background_color_err_focus = 'dark cyan'

        palette = [
            ('app.relax', 'light green', background_color),
            ('app.alarm', 'yellow', background_color),
            ('app.focus', text_color_focus, background_color_focus),
            ('app.default', text_color, background_color),
            ('app.title', text_color_title, background_color),
            ('app.dialog', text_color_dialog, background_color_dialog),
            ('app.err.focus', text_color_err_focus, background_color_err_focus),
            ('app.err.default', text_color_err, background_color_err),
            ('app.err.title', text_color_err_title, background_color_err),
            ('app.button', 'black', 'dark cyan'),
            ('app.buttonfocus', 'white', 'dark cyan'),
            ('app.editbox', 'light gray', 'dark blue'),
            ('app.editfocus', 'white', 'dark blue'),
        ]

        loop = urwid.MainLoop(self, palette)
        if not self.error_mode:
            loop.set_alarm_in(1, self.on_app_idle)
            if self.timer_config.is_timer_in_progress():
                loop.set_alarm_in(1, self.on_app_timeout)
        loop.run()


def clear_screen():
    print('\x1b\x5b\x33\x4a\x1b\x5b\x48\x1b\x5b\x32\x4a')


def main():
    global EXIT_CODE
    debug = True if '--debug' in sys.argv else False
    if not debug:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        atexit.register(clear_screen)
    app_config = AppConfig()
    try:
        init_app_config(app_config)
    except Exception:
        etype, evalue, tb = sys.exc_info()
        app_config.error_text = ''.join(traceback.format_tb(tb) + traceback.format_exception_only(etype, evalue))
    try:
        MainApp(app_config, debug).main()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
    exit(EXIT_CODE)
