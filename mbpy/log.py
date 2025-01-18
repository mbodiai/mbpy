import logging.config
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, overload, TypeVar, Generic, Literal

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

LevelT = TypeVar("LevelT", bound=Literal["DEBUG", "INFO", "WARNING", "ERROR", "FATAL"])
class Log(Generic[LevelT]):
    level: LevelT
    @classmethod
    def set(cls):
        logging.basicConfig(level=cls.level,force=True)
        return cls
    @classmethod
    def log(cls, *args, **kwargs):
        if getlevel() > getattr(logging, cls.level.upper()):
            return cls
        if args or kwargs:
            logging.log(getattr(logging, cls.level.upper()), *args, **kwargs, stack_info=debug())
        return cls
    @classmethod
    def __class_getitem__(cls, level: LevelT):
        cls.level = level
        return cls
    
    @classmethod
    def __bool__(cls):
        print(f"is {cls.level} enabled? {getlevel()} <= {getattr(logging, cls.level.upper())}")
        return getlevel() <= getattr(logging, cls.level.upper())
    
DEBUG=Literal["DEBUG"]
INFO=Literal["INFO"]
WARNING=Literal["WARNING"]
ERROR=Literal["ERROR"]
FATAL=Literal["FATAL"]
@overload
@wraps(logging.debug)
def debug(*args, **kwargs)-> Log["DEBUG"]:...
@overload
def debug() -> Log["DEBUG"]:...
def debug(*args, **kwargs):
    """Initialize or log a debug message.

    Examples:
        >>> debug()  # Returns Log["debug"] for configuration
        >>> if debug():  # Check if debug level is enabled
        ...     print("Will only print if debug level is enabled")
        >>> debug.set()  # Set logging level to DEBUG
        >>> debug.log("Processing file")  # Log a message
        DEBUG: Processing file
    """
    if args is None and kwargs is None:
        print(f"args: {args}, kwargs: {kwargs}")
        return Log["DEBUG"]()
    if getlevel() > logging.DEBUG:
        return Log["DEBUG"]()
    if args or kwargs:
        logging.debug(*args, **kwargs, stack_info=True)
        return Log["DEBUG"]()

@overload
@wraps(logging.info)
def info(*args, **kwargs):...
@overload
def info() -> Log["info"]:...
def info(*args, **kwargs) -> None:
    """Initialize or log an info message.

    Examples:
        >>> info()  # Returns Log["info"] for configuration
        >>> if info():  # Check if info level is enabled
        ...     print("Will only print if info level is enabled")
        >>> info.set()  # Set logging level to INFO
        >>> info.log("Processing file")  # Log a message
        INFO: Processing file
    """
    if args is None and kwargs is None:
        return Log["info"]
    if getlevel() > logging.INFO:
        return Log["info"]
    if args or kwargs:
        logging.info(*args, **kwargs, stack_info=kwargs.get("stack_info", False) or getlevel() == logging.DEBUG)
        return Log["info"]
@overload
@wraps(logging.warning)
def warning(*args, **kwargs):...
def warning(*args, **kwargs) -> None:
    """Initialize or log a warning message.

    Examples:
        >>> warning()  # Returns Log["warning"] for configuration
        >>> if warning():  # Check if warning level is enabled
        ...     print("Will only print if warning level is enabled")
        >>> warning.set()  # Set logging level to WARNING
        >>> warning.log("File not found")  # Log a message
        WARNING: File not found
        >>> warning("File not found", path="/tmp/missing.txt")
        WARNING: File not found (/tmp/missing.txt)
    """
    if args is None and kwargs is None:
        return Log["warning"]
    if getlevel() > logging.WARNING:
        return Log["warning"]
    if args or kwargs:
        logging.warning(*args, **kwargs, stack_info=kwargs.get("stack_info", False) or getlevel() == logging.DEBUG)
        return Log["warning"]
    if getlevel() > logging.WARNING:
        return Log["warning"]
@overload
@wraps(logging.error)
def error(*args, **kwargs):...
@overload
def error():...
def error(*args, **kwargs) -> None:
    """Initialize or log an error message.

    Examples:
        >>> error()  # Returns Log["error"] for configuration
        >>> if error():  # Check if error level is enabled
        ...     print("Will only print if error level is enabled")
        >>> error.set()  # Set logging level to ERROR
        >>> error.log("Failed to connect")  # Log a message
        ERROR: Failed to connect
    """
    if args is None and kwargs is None:
        return Log["error"]
    if getlevel() > logging.ERROR:
        return Log["error"]
    if args or kwargs:
        logging.error(*args, **kwargs, stack_info=kwargs.get("stack_info", False) or getlevel() == logging.DEBUG)
        return Log["error"]
    

@overload
@wraps(logging.fatal)
def fatal(*args, **kwargs):...
@overload
def fatal():...
def fatal(*args, **kwargs) -> None:
    """Initialize or log a fatal message.

    Examples:
        >>> fatal()  # Returns Log["fatal"] for configuration
        >>> if fatal():  # Check if fatal level is enabled
        ...     print("Will only print if fatal level is enabled")
        >>> fatal.set()  # Set logging level to FATAL
        >>> fatal.log("Critical system failure")  # Log a message
        FATAL: Critical system failure
    """
    if args is None and kwargs is None:
        return Log["fatal"]
    if getlevel() > logging.FATAL:
        return Log["fatal"]
    if args or kwargs:
        logging.fatal(*args, **kwargs, stack_info=kwargs.get("stack_info", False) or getlevel() == logging.DEBUG)
        return Log["fatal"]
    