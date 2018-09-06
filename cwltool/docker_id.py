"""Helper functions for docker."""
from __future__ import absolute_import, print_function

from typing import List, Optional, Tuple  # pylint: disable=unused-import

from typing_extensions import Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .utils import subprocess


def docker_vm_id():  # type: () -> Tuple[Optional[int], Optional[int]]
    """
    Returns the User ID and Group ID of the default docker user inside the VM

    When a host is using boot2docker or docker-machine to run docker with
    boot2docker.iso (As on Mac OS X), the UID that mounts the shared filesystem
    inside the VirtualBox VM is likely different than the user's UID on the host.
    :return: A tuple containing numeric User ID and Group ID of the docker account inside
    the boot2docker VM
    """
    if boot2docker_running():
        return boot2docker_id()
    if docker_machine_running():
        return docker_machine_id()
    return (None, None)


def check_output_and_strip(cmd):  # type: (List[Text]) -> Optional[Text]
    """
    Passes a command list to subprocess.check_output, returning None
    if an expected exception is raised
    :param cmd: The command to execute
    :return: Stripped string output of the command, or None if error
    """
    try:
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return result.strip()
    except (OSError, subprocess.CalledProcessError, TypeError, AttributeError):
        # OSError is raised if command doesn't exist
        # CalledProcessError is raised if command returns nonzero
        # AttributeError is raised if result cannot be strip()ped
        return None


def docker_machine_name():  # type: () -> Optional[Text]
    """
    Get the machine name of the active docker-machine machine
    :return: Name of the active machine or None if error
    """
    return check_output_and_strip(['docker-machine', 'active'])


def cmd_output_matches(check_cmd, expected_status):
    # type: (List[Text], Text) -> bool
    """
    Runs a command and compares output to expected
    :param check_cmd: Command list to execute
    :param expected_status: Expected output, e.g. "Running" or "poweroff"
    :return: Boolean value, indicating whether or not command result matched
    """
    return check_output_and_strip(check_cmd) == expected_status


def boot2docker_running():  # type: () -> bool
    """
    Checks if boot2docker CLI reports that boot2docker vm is running
    :return: True if vm is running, False otherwise
    """
    return cmd_output_matches(['boot2docker', 'status'], 'running')


def docker_machine_running():  # type: () -> bool
    """
    Asks docker-machine for active machine and checks if its VM is running
    :return: True if vm is running, False otherwise
    """
    machine_name = docker_machine_name()
    if not machine_name:
        return False
    return cmd_output_matches(['docker-machine', 'status', machine_name], 'Running')


def cmd_output_to_int(cmd):  # type: (List[Text]) -> Optional[int]
    """
    Runs the provided command and returns the integer value of the result
    :param cmd: The command to run
    :return: Integer value of result, or None if an error occurred
    """
    result = check_output_and_strip(cmd)  # may return None
    if result is not None:
        try:
            return int(result)
        except ValueError:
            # ValueError is raised if int conversion fails
            return None
    return None


def boot2docker_id():  # type: () -> Tuple[Optional[int], Optional[int]]
    """
    Gets the UID and GID of the docker user inside a running boot2docker vm
    :return: Tuple (UID, GID), or (None, None) if error (e.g. boot2docker not present or stopped)
    """
    uid = cmd_output_to_int(['boot2docker', 'ssh', 'id', '-u'])
    gid = cmd_output_to_int(['boot2docker', 'ssh', 'id', '-g'])
    return (uid, gid)

def docker_machine_id():  # type: () -> Tuple[Optional[int], Optional[int]]
    """
    Asks docker-machine for active machine and gets the UID of the docker user
    inside the vm
    :return: tuple (UID, GID), or (None, None) if error (e.g. docker-machine not present or stopped)
    """
    machine_name = docker_machine_name()
    if not machine_name:
        return (None, None)
    uid = cmd_output_to_int(['docker-machine', 'ssh', machine_name, "id -u"])
    gid = cmd_output_to_int(['docker-machine', 'ssh', machine_name, "id -g"])
    return (uid, gid)


if __name__ == '__main__':
    print(docker_vm_id())
