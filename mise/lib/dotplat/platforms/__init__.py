"""One module per platform. Each module exposes `steps() -> list[Step]`.

To add a platform: add its id to detect.PLATFORMS (and ALIASES), then add a
module here with the same name.
"""

from __future__ import annotations

import importlib

from ..runner import Step


def steps_for(platform: str) -> list[Step]:
    module = importlib.import_module(f"{__name__}.{platform}")
    return module.steps()
