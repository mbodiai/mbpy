# SPDX-FileCopyrightText: 2024-present Sebastian Peralta <sebastian@mbodi.ai>
#
# SPDX-License-Identifier: apache-2.0
# Define the variable '__version__':

import asyncio
import sys
from typing import TYPE_CHECKING

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except:
    pass


LIGHT_CYAN_BOLD = "#87d7ff"
CYAN_BOLD = "#00ffff"
PINK_BOLD = "#ffafd7"
LIGHT_BLUE = "#afd7ff"
LIGHT_BLUE_BOLD = "#afd7ff"
RESET = ""  # Resetting the color, no hex value
PINK = "#ffafd7"

THEME = {
    "info": f"{LIGHT_CYAN_BOLD}",
    "success": f"{LIGHT_BLUE}",
    "light_blue": f"{LIGHT_BLUE_BOLD}",
    "reset": RESET,
    "pink": f"{PINK}",
}


from mbpy.log import setup_logging
setup_logging()