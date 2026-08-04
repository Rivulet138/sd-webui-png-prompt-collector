from __future__ import annotations

import sys
from pathlib import Path


EXTENSION_ROOT = Path(__file__).resolve().parents[1]
if str(EXTENSION_ROOT) not in sys.path:
    sys.path.insert(0, str(EXTENSION_ROOT))

from modules import script_callbacks

from png_prompt_collector.ui import create_ui


script_callbacks.on_ui_tabs(create_ui, name="png_prompt_collector")

