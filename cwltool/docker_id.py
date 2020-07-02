"""Helper functions for docker."""

import subprocess  # nosec
from typing import List, Optional, Tuple


def docker_vm_id() -> Tuple[Optional[int], Optional[int]]:
    """
    Return the User ID and Group ID of the default docker user inside the VM.

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


def check_output_and_strip(cmd: List[str]) -> Optional[str]:
    """
    Pass a command list to subprocess.check_output.

    Returning None if an expected exception is raised
    :param cmd: The command to execute
    :return: Stripped string output of the command, or None if error
    """
    try:
        result = subprocess.check_output(  # nosec
            cmd, stderr=subprocess.STDOUT, universal_newlines=True
        )
        return result.strip()
    except (OSError, subprocess.CalledProcessError, TypeError, AttributeError):
        # OSError is raised if command doesn't exist
        # CalledProcessError is raised if command returns nonzero
        # AttributeError is raised if result cannot be strip()ped
        return None


def docker_machine_name() -> Optional[str]:
    """
    Get the machine name of the active docker-machine machine.

    :return: Name of the active machine or None if error
    """
    return check_output_and_strip(["docker-machine", "active"])


def cmd_output_matches(check_cmd: List[str], expected_status: str) -> bool:
    """
    Run a command and compares output to expected.

    :param check_cmd: Command list to execute
    :param expected_status: Expected output, e.g. "Running" or "poweroff"
    :return: Boolean value, indicating whether or not command result matched
    """
    return check_output_and_strip(check_cmd) == expected_status


def boot2docker_running() -> bool:
    """
    Check if boot2docker CLI reports that boot2docker vm is running.

    :return: True if vm is running, False otherwise
    """
    return cmd_output_matches(["boot2docker", "status"], "running")


def docker_machine_running() -> bool:
    """
    Ask docker-machine for the active machine and checks if its VM is running.

    :return: True if vm is running, False otherwise
    """
    machine_name = docker_machine_name()
    if not machine_name:
        return False
    return cmd_output_matches(["docker-machine", "status", machine_name], "Running")


def cmd_output_to_int(cmd: List[str]) -> Optional[int]:
    """
    Run the provided command and returns the integer value of the result.

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


def boot2docker_id() -> Tuple[Optional[int], Optional[int]]:
    """
    Get the UID and GID of the docker user inside a running boot2docker vm.

    :return: Tuple (UID, GID), or (None, None) if error (e.g. boot2docker not present or stopped)
    """
    uid = cmd_output_to_int(["boot2docker", "ssh", "id", "-"])
    gid = cmd_output_to_int(["boot2docker", "ssh", "id", "-g"])
    return (uid, gid)


def docker_machine_id() -> Tuple[Optional[int], Optional[int]]:
    """
    Ask docker-machine for active machine and gets the UID of the docker user.

    inside the vm
    :return: tuple (UID, GID), or (None, None) if error (e.g. docker-machine not present or stopped)
    """
    machine_name = docker_machine_name()
    if not machine_name:
        return (None, None)
    uid = cmd_output_to_int(["docker-machine", "ssh", machine_name, "id -"])
    gid = cmd_output_to_int(["docker-machine", "ssh", machine_name, "id -g"])
    return (uid, gid)


if __name__ == "__main__":
    print(docker_vm_id())
