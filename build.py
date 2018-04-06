from __future__ import print_function 
import os
import os.path
import shutil
import subprocess
import sys
import hashlib
import time


DIR_HERE = os.path.abspath(os.path.dirname(__file__))


def cleanup_dir(dir_name):
    if os.path.exists(dir_name):
        fsitems = os.listdir(dir_name)
        for fsitem in fsitems:
            path = os.path.join(dir_name, fsitem)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
    else:
        os.makedirs(dir_name)


def sha1_of_file(path):
    state = hashlib.sha1()
    with open(path, mode='rt') as _fh:
        for ln in [ ln.rstrip('\r\n') for ln in _fh.readlines() ]:
            payload = ln.strip()
            if payload and not payload.startswith('#'):
                state.update(payload)
    return state.hexdigest()


def build():
    docker_instance_name = 'centos7iso-{}'.format(int(time.time()))

    docker_makefile = os.path.join(DIR_HERE, 'Dockerfile')
    docker_makefile_sha1 = sha1_of_file(docker_makefile)
    docker_template_name = 'centos7iso-{}'.format(docker_makefile_sha1)

    output_dir = os.path.join(DIR_HERE, 'build')
    cleanup_dir(output_dir)
    scripts_dir_in_docker_format = os.path.join(DIR_HERE, 'scripts')
    output_dir_in_docker_format = output_dir

    install_dir_in_docker_format = os.path.join(DIR_HERE, 'install')

    if sys.platform == 'win32':
        scripts_dir_in_docker_format = scripts_dir_in_docker_format.replace('\\','/')
        install_dir_in_docker_format = install_dir_in_docker_format.replace('\\','/')
        output_dir_in_docker_format = output_dir_in_docker_format.replace('\\','/')

    docker_version = subprocess.check_output(['docker', '--version'], cwd=DIR_HERE).split('\n')[0]
    print(docker_version)
    print("Docker: instance name: '{}'".format(docker_instance_name))
    print("Docker: template name: '{}'".format(docker_template_name))
    print("Docker: scripts directory: '{}'".format(scripts_dir_in_docker_format))
    print("Docker: output directory: '{}'".format(output_dir_in_docker_format))

    build_docker_image_cmd = ['docker', 'build', '-t', docker_template_name, '.']
    print("EXEC: {}".format(' '.join(build_docker_image_cmd)))
    subprocess.check_call(build_docker_image_cmd, shell=False, cwd=DIR_HERE)

    build_in_docker_cmd = """
        docker run
        --privileged=true
        --name {docker_instance_name} --rm
        -v {scripts_dir_in_docker_format}:/root/centos7build/scripts
        -v {install_dir_in_docker_format}:/root/centos7build/install
        -v {output_dir_in_docker_format}:/root/centos7build/docker_output
        -w /root/centos7build/scripts
        {docker_template_name} bash -e build-iso.sh
    """.format(**{
        'docker_instance_name': docker_instance_name,
        'docker_template_name': docker_template_name,
        'scripts_dir_in_docker_format': scripts_dir_in_docker_format,
        'install_dir_in_docker_format': install_dir_in_docker_format,
        'output_dir_in_docker_format': output_dir_in_docker_format,
    }).split()

    print("EXEC: {}".format(' '.join(build_in_docker_cmd)))
    subprocess.check_call(build_in_docker_cmd, shell=False)


if __name__ == '__main__':
    print('Build is started ...')
    build()
    print('Build finished.')
