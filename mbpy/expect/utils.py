from __future__ import annotations

import errno
import os
import re
import select
import shutil
import stat
import subprocess
import sys
import traceback
from pathlib import Path
from time import time
from typing import Any


def get_shell_aliases(home_dir="~"):
    try:
        # Determine the shell and the appropriate initialization file
        shell = os.environ.get("SHELL", "")
        mbdir = Path(os.getenv("MB_WS", Path.home()))
        home_dirs = {Path.home(), Path(home_dir).expanduser(), mbdir}
        results = []

        for home_dir in home_dirs:
            if "bash" in shell:
                init_file = home_dir / ".bashrc"
            elif "zsh" in shell:
                init_file = home_dir / ".zshrc"
            else:
                raise ValueError(f"Unsupported shell: {shell}")

            # Check if the initialization file exists
            if not init_file.exists():
                continue  # Skip if the file doesn't exist

            # Source the shell configuration file and list aliases
            command = f"source {init_file}; alias"
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                executable=shell,
                check=False,
            )

            if result.returncode == 0:
                results.append(result.stdout.strip())
            else:
                raise ValueError(f"{result.stderr.strip()}")

        # Resolve aliases and dependencies
        return resolve_aliases_and_dependencies("\n".join(results).splitlines())
    except Exception as e:
        traceback.print_exc()
        return f"Error: {e}"


def resolve_aliases_and_dependencies(aliases, shell="bash"):
    """Resolves shell aliases, expands environment variables, and checks dependencies."""
    try:
        out = {}
        missing_dependencies = []
        for line in aliases:
            match = re.match(r"(\w+)=['\"]?(.+?)['\"]?$", line)
            if match:
                alias_name, alias_command = match.groups()
                resolved_command = os.path.expandvars(
                    alias_command
                )  # Expand env variables

                # Check for missing dependencies
                command_parts = re.split(
                    r"[;|& ]+", resolved_command
                )  # Robust splitting
                md = [
                    part
                    for part in command_parts
                    if not shutil.which(part)
                    and not part.startswith("$")
                    and not part.startswith("(")
                ]
                missing_dependencies.extend(md)
                out[alias_name] = resolved_command

        return out, missing_dependencies
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


aliases, md = get_shell_aliases()

def is_executable_file(path):
    """Checks that path is an executable regular file, or a symlink towards one.

    This is roughly ``os.path isfile(path) and os.access(path, os.X_OK)``.
    """
    fpath = os.path.realpath(path)

    if not Path(fpath).exists():
        return False

    mode = Path.stat(fpath).st_mode

    if sys.platform.startswith("sunos") and os.getuid() == 0:
        return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))

    return os.access(fpath, os.X_OK)

def which(filename, env=None):
    """Find a file in PATH.

    This takes a given filename; tries to find it in the environment path;
    then checks if it is executable. This returns the full path to the filename
    if found and executable. Otherwise this returns None.
    """
    if excu := os.path.expandvars(f"${filename}"):
        print(excu)
        return excu
    print(f"not found {filename}")
    cmd = Path(filename)
    if cmd.exists() and is_executable_file(cmd):
        return filename
    if filename in aliases:
        return filename
    if env is None:
        env = os.environ
    p = env.get("PATH")
    if p is not None:
        p = os.defpath
    pathlist = p.split(os.pathsep)
    for path in pathlist:
        ff = path / cmd
        if is_executable_file(ff):
            return str(ff)
    if filename in os.environ:
        return filename
    
    return aliases.get(filename)

def split_command_line(command_line) -> list[Any]:
    """Split command line into a list of arguments.
    
    This splits a command line into a list of arguments. It splits arguments
    on spaces, but handles embedded quotes, doublequotes, and escaped
    characters. It's impossible to do this with a regular expression, so I
    wrote a little state machine to parse the command line.
    """
    arg_list = []
    arg = ""

    state_basic = 0
    state_esc = 1
    state_singlequote = 2
    state_doublequote = 3
    state_whitespace = 4
    state = state_basic

    for c in command_line:
        if state in (state_basic, state_whitespace):
            if c == "\\":
                state = state_esc
            elif c == r"'":
                state = state_singlequote
            elif c == r'"':
                state = state_doublequote
            elif c.isspace():
                if state == state_whitespace:
                    None
                else:
                    arg_list.append(arg)
                    arg = ""
                    state = state_whitespace
            else:
                arg = arg + c
                state = state_basic
        elif state == state_esc:
            arg = arg + c
            state = state_basic
        elif state == state_singlequote:
            if c == r"'":
                state = state_basic
            else:
                arg = arg + c
        elif state == state_doublequote:
            if c == r'"':
                state = state_basic
            else:
                arg = arg + c

    if arg != "":
        arg_list.append(arg)
    return arg_list

def select_ignore_interrupts(iwtd, owtd, ewtd, timeout=None):
    """This is a wrapper around select.select() that ignores signals.
    
    If select.select raises a select.error exception and errno is an EINTR
    error then it is ignored. Mainly this is used to ignore sigwinch
    (terminal resize).
    """
    if timeout is not None:
        end_time = time() + timeout
    while True:
        try:
            return select.select(iwtd, owtd, ewtd, timeout)
        except InterruptedError:
            err = sys.exc_info()[1]
            if err.args[0] == errno.EINTR:
                if timeout is not None:
                    timeout = end_time - time()
                    if timeout < 0:
                        return ([], [], [])
            else:
                raise

def poll_ignore_interrupts(fds, timeout=None):
    """Simple wrapper around poll to register file descriptors and ignore signals."""
    if timeout is not None:
        end_time = time() + timeout

    poller = select.poll()
    for fd in fds:
        poller.register(fd, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR)

    while True:
        try:
            timeout_ms = None if timeout is None else timeout * 1000
            results = poller.poll(timeout_ms)
            return [afd for afd, _ in results]
        except InterruptedError:
            err = sys.exc_info()[1]
            if err.args[0] == errno.EINTR:
                if timeout is not None:
                    timeout = end_time - time()
                    if timeout < 0:
                        return []
            else:
                raise