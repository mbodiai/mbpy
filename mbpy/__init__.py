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