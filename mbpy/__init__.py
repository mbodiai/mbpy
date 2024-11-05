# SPDX-FileCopyrightText: 2024-present Sebastian Peralta <sebastian@mbodi.ai>
#
# SPDX-License-Identifier: apache-2.0
import logging
import sys

from rich.logging import RichHandler
from rich.pretty import install
from rich.traceback import install as install_traceback

from . import context, file_assistant

logging.getLogger().addHandler(RichHandler())
install(max_length=10, max_string=80)
install_traceback(show_locals=sys.argv and any(arg in {"-v", "--verbose","debug","-d","--debug"} for arg in sys.argv))

__all__ = ["context", "mpip",  "file_assistant"]