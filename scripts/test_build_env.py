from __future__ import print_function
import os.path
import inspect
import sys


class BuildSystemException(Exception):
    def __init__(self, text, frame=1):
        frame_info = inspect.stack()[frame]
        msg = '[{}({})] {}'.format(os.path.basename(frame_info[1]), frame_info[2], text)
        Exception.__init__(self, msg)


def main():
    SYS_PLATFORM = sys.platform
    SYS_MACHINE = None
    SYS_LINUX_RELEASE_ID = None
    SYS_LINUX_RELEASE_VERSION_ID = None

    if hasattr(os, 'uname'):
        SYS_MACHINE = os.uname()[4]

    print("PLATFORM: '{}'".format(SYS_PLATFORM))
    if SYS_MACHINE is not None:
        print("MACHINE: '{}'".format(SYS_MACHINE))

    if not SYS_PLATFORM.startswith('linux') or (SYS_MACHINE != 'x86_64'):
        raise BuildSystemException("Build cannot proceed, it is started on unsupported platform.")

    if not os.path.isfile('/etc/os-release'):
        if os.path.isfile('/etc/centos-release'):
            with open('/etc/centos-release', mode='rt') as _fh:
                for ln in [ ln.rstrip('\r\n') for ln in _fh.readlines() ]:
                    if ln.strip():
                        print(ln.strip())
        raise BuildSystemException("Build cannot proceed, expected file '{0}' not found.".format(os.path.basename(__file__), '/etc/os-release'))

    with open('/etc/os-release', mode='rt') as _fh:
        for ln in [ ln.rstrip('\r\n') for ln in _fh.readlines() ]:
            release_match = ln.split('=')
            release_key = None
            release_value = None
            if len(release_match) == 2:
                release_key = release_match[0]
                release_value = release_match[1].strip('"')
            if release_key == 'ID':
                SYS_LINUX_RELEASE_ID = release_value
            if release_key == 'VERSION_ID':
                SYS_LINUX_RELEASE_VERSION_ID = release_value


    print("LINUX_RELEASE_ID: '{}'".format(SYS_LINUX_RELEASE_ID))
    print("LINUX_RELEASE_VERSION_ID: '{}'".format(SYS_LINUX_RELEASE_VERSION_ID))

    if SYS_LINUX_RELEASE_ID != 'centos' or SYS_LINUX_RELEASE_VERSION_ID != '7':
        raise BuildSystemException("Build cannot proceed, it is started on unsupported version of Linux.")

    if os.path.isfile('/etc/centos-release'):
        with open('/etc/centos-release', mode='rt') as _fh:
            for ln in [ ln.rstrip('\r\n') for ln in _fh.readlines() ]:
                if ln.strip():
                    print(ln.strip())

if __name__ == '__main__':
    try:
        main()
    except BuildSystemException as exc:
        print("ERROR: {}".format(exc))
        exit(2)
