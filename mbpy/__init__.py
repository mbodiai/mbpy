# SPDX-FileCopyrightText: 2024-present Sebastian Peralta <sebastian@mbodi.ai>
#
# SPDX-License-Identifier: apache-2.0
import logging

from rich.logging import RichHandler
from rich.pretty import install


logging.getLogger().addHandler(RichHandler()) 
from rich.pretty import install
from rich.traceback import install as install_traceback

install(max_length=10, max_string=80)
install_traceback(show_locals=True)