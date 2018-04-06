from __future__ import print_function
import os
import os.path
import signal
import subprocess
import time


DIR_HERE = os.path.normpath(os.path.abspath(os.path.dirname(__file__)))
INSTALL_SCRIPT = os.path.join(DIR_HERE, 'os-install.sh')

def preexec(): # Don't forward signals.
    os.setpgrp()


def main():
    ret_code = None
    output_file = '/tmp/os-install.log'
    with open(os.devnull, 'rw') as dev_null:
        with open(output_file, mode='wt') as ofh:
            with open(output_file, mode='rt') as ifh:
                p = subprocess.Popen(['/bin/bash', INSTALL_SCRIPT],
                    stdin=dev_null, stdout=ofh, stderr=subprocess.STDOUT, preexec_fn = preexec)
                while True:
                    line = ifh.readline()
                    if not line:
                        ret_code = p.poll()
                        if ret_code is not None:
                            p.wait()
                            break
                        time.sleep(0.1)
                        continue
                    print(line, end='')
    return ret_code


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    exit(main())
