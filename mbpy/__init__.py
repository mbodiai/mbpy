# SPDX-FileCopyrightText: 2024-present Sebastian Peralta <sebastian@mbodi.ai>
#
# SPDX-License-Identifier: apache-2.0
import logging

from rich.logging import RichHandler
from rich.pretty import install
from rich.traceback import install as rich_install

install(max_length=10, max_string=50)


rich_install(locals_hide_dunder=False, locals_hide_sunder=False, show_locals=True)


logging.getLogger().addHandler(RichHandler()) 
# Path: __init__.py
# This file is automatically created by mbpy.
from rich.pretty import install
from rich.traceback import install as install_traceback

install(max_length=10, max_string=80)
install_traceback(show_locals=True)
# Path: __init__.py
# This file is automatically created by mbpy.
from rich.pretty import install
from rich.traceback import install as install_traceback

install(max_length=10, max_string=80)
install_traceback(show_locals=True)