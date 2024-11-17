# SPDX-FileCopyrightText: 2024-present Sebastian Peralta <sebastian@mbodi.ai>
#
# SPDX-License-Identifier: apache-2.0
import logging
import sys
from typing import TYPE_CHECKING

from rich.logging import RichHandler
from rich.pretty import install
from rich.traceback import install as install_traceback
from .utils import collections, import_utils
from .utils.import_utils import smart_import
from . import cli, commands, context, mpip





def isverbose(args):
    return any(arg in {"-v", "--verbose","debug","-d","--debug"} for arg in args)

def isvverbose(args):
    return any(arg in {"-vv", "--DEBUG","-vvv","DEBUG"} for arg in args)

logging.getLogger().addHandler(RichHandler())
if isvverbose(sys.argv):
    logging.getLogger().setLevel(logging.DEBUG)
install(max_length=10, max_string=80)
install_traceback(show_locals=isverbose(sys.argv))



DataModel = smart_import("pydantic.BaseModel")\
    or smart_import("typing_extension.TypedDict") \
    or smart_import(name="mbodi.SampleDict")

if TYPE_CHECKING:
    from pydantic import BaseModel
    DataModel = BaseModel
    
__all__ = ["context", "mpip","DataModel", "context", "mpip",
           "cli", "commands", "collections", "import_utils"]

