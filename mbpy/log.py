import logging.config
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, overload


def caller(depth=1, default='__main__'):
    try:
        return sys._getframemodulename(depth + 1) or default
    except AttributeError:  # For platforms without _getframemodulename()
        pass
    try:
        return sys._getframe(depth + 1).f_globals.get('__name__', default)
    except (AttributeError, ValueError):  # For platforms without _getframe()
        pass
    return None

if TYPE_CHECKING:
    from types import ModuleType

def parentmodule() -> "ModuleType":
    return sys.modules[caller() or "__main__"]



def setup_logging() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    

def isverbose() -> bool:
    import sys
    return any(arg in sys.argv for arg in ("-v", "--verbose","-d", "--debug"))

def isvverbose() -> bool:
    import sys
    return any(arg in sys.argv for arg in ("-vv", "--vverbose","-dd", "--ddebug"))


def getlevel() -> int:
    if isvverbose():
        return logging.DEBUG
    if isverbose():
        return logging.INFO
    
    return logging.getLogger().getEffectiveLevel()

log = logging.log


# Logging configuration dictionary
LOGGING_CONFIG: Dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "detailed": {
            "format": "[%(asctime)s] %(levelname)s %(message)s (%(filename)s:%(lineno)d)",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {"format": "%(levelname)s: %(message)s"},
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": getlevel(),
            "formatter": "simple",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.FileHandler",
            "level": getlevel(),
            "formatter": "detailed",
            "filename": Path(parentmodule().__file__ or "log").with_suffix(".log"),
            "mode": "a",
        },
        "rich": {
            "class": "mbpy.helpers._logging.RichHandler",
            "level": getlevel(),
            "formatter": "simple",
        },
    },
    "loggers": {
        "": {  
            "handlers": ["console", "file"],
            "level": getlevel(),
            "propagate": True,
        },
    },
}

if TYPE_CHECKING:
    from mbpy.collect import wraps
else:
    wraps = lambda *args, **kwargs: lambda f: f

setup_logging()
# Update the existing code
if isverbose():
    LOGGING_CONFIG["loggers"][""]["level"] = "DEBUG"
if isvverbose():
    LOGGING_CONFIG["handlers"]["console"]["formatter"] = "detailed"

@overload
@wraps(logging.debug)
def debug(*args, **kwargs):...
@overload
def debug():...
def debug(*args, **kwargs) -> None:
    """Initialize or log a debug message."""
    print("DEBUGGING")
    if args is None and kwargs is None:
        logging.basicConfig(level=logging.DEBUG,force=True)
        return
    if getlevel() > logging.DEBUG:
        return
    if args or kwargs:
        logging.debug(*args, **kwargs, stack_info=True)

@wraps(logging.info)
def info(*args, **kwargs):
    if args is None and kwargs is None:
        logging.basicConfig(level=logging.INFO,force=True)
        return
    
    if getlevel() > logging.INFO:
        return
    if args or kwargs:
        logging.info(*args, **kwargs, stack_info=kwargs.get("stack_info", False) or getlevel() == logging.DEBUG)

@wraps(logging.warning)
def warning(*args, **kwargs):
    if args is None and kwargs is None and getlevel() <= logging.WARNING:
        logging.basicConfig(level=logging.WARNING,force=True)
        return
    if getlevel() > logging.WARNING:
        return
    if args or kwargs:
        logging.warning(*args, **kwargs, stack_info=kwargs.get("stack_info", False) or getlevel() == logging.DEBUG)

warn = warning

@wraps(logging.error)
def error(*args, **kwargs):
    if args is None and kwargs is None and getlevel() <= logging.ERROR:
        logging.basicConfig(level=logging.ERROR,force=True)
        return
    if getlevel() > logging.ERROR:
        return
    if args or kwargs:
        logging.error(*args, **kwargs, stack_info=kwargs.get("stack_info", False) or getlevel() == logging.DEBUG)

@wraps(logging.fatal)
def fatal(*args, **kwargs):
    if args is None and kwargs is None:
        logging.basicConfig(level=logging.FATAL,force=True)
        return
    if getlevel() > logging.FATAL:
        return
    if args or kwargs:
        logging.fatal(*args, **kwargs, stack_info=kwargs.get("stack_info", False) or getlevel() == logging.DEBUG)
