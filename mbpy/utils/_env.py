from __future__ import annotations

import logging
import os
import platform
import sys
from typing import Callable, Literal

from rich.prompt import Prompt

from mbpy.utils.collect import PathLike as Path


def detect_active_interpreter() -> set[str]:
    """Attempt to detect a venv, virtualenv, poetry, or conda environment by looking for certain markers.

    If it fails to find any, it will fail with a message.
    """
    detection_funcs: list[Callable[[], str | None]] = [
        detect_venv_or_virtualenv_interpreter,
        detect_conda_env_interpreter,
    ]
    active = set()
    for detect in detection_funcs:
        path = detect()
        if not path:
            continue
        if Path(path).exists():
            active.add(str(path))
    return active

def get_env_interpreter(env: str | None):
    if env == "conda":
        return detect_conda_env_interpreter()
    return detect_venv_or_virtualenv_interpreter()

def get_executable(env: str | None, multiple: Literal["auto", "ask","fail"] = "auto"):
    """Get the specified or detected python interpreter."""
    if env:
        return get_env_interpreter(env) or "python3"
    
    pythons = detect_active_interpreter()
    if len(pythons) == 0:
        logging.warning("No active python environment detected. Using the default python interpreter.")
        return sys.executable
    if len(pythons) > 1:
        if multiple == "fail":
            logging.error(f"Multiple active python environments detected: {pythons} and multiple is set to fail. You can change the behavior by setting multiple to 'auto' or 'ask'. See mb env --help for more information.")
            sys.exit(1)
        if multiple == "ask":
            return Prompt.ask(" Multiple python versions detected please Select the python interpreter to use", choices=pythons)
    return pythons.pop()
    

def detect_venv_or_virtualenv_interpreter() -> str | None:
    # Both virtualenv and venv set this environment variable.
    env_var = os.environ.get("VIRTUAL_ENV")
    logging.debug(env_var)
    if not env_var:
        return None

    path = Path(env_var)
    path /= determine_bin_dir()

    file_name = determine_interpreter_file_name()
    logging.debug(file_name)
    return str(path / file_name) if file_name else None


def determine_bin_dir() -> str:
    return "Scripts" if os.name == "nt" else "bin"


def detect_conda_env_interpreter() -> str | None:
    # Env var mentioned in https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#saving-environment-variables.
    env_var = os.environ.get("CONDA_PREFIX")
    if not env_var:
        return None
    

    path = Path(env_var)

    # On POSIX systems, conda adds the python executable to the /bin directory. On Windows, it resides in the parent
    # directory of /bin (i.e. the root directory).
    # See https://docs.anaconda.com/free/working-with-conda/configurations/python-path/#examples.
    if os.name == "posix":  # pragma: posix cover
        path /= "bin"

    file_name = determine_interpreter_file_name()

    return str(path / file_name) if file_name else None



def determine_interpreter_file_name() -> str | None:
    impl_name_to_file_name_dict = {"CPython": "python", "PyPy": "pypy"}
    name = impl_name_to_file_name_dict.get(platform.python_implementation())
    if not name:
        return None
    if os.name == "nt":  # pragma: nt cover
        return name + ".exe"
    return name



if __name__ == "__main__":
    pass
