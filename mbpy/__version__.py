from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from typing import Tuple
    VERSION_TUPLE = Tuple[int | str, ...]
else:
    VERSION_TUPLE = object


def get_version() -> str:
    from .mpip import get_latest_version
    major, minor, patch = get_latest_version(__package__)
    return f"{major}.{minor}.{int(patch)+1}"

__version__ = get_version()
