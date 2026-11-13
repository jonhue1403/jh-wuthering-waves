"""Compatibility launcher for the removed OK Script web frontend.

OK Script 3 no longer ships its browser UI. Keep this legacy entry point
usable by warning and starting the supported desktop Qt application instead.
"""

import warnings

from config import config
from ok import OK


def main():
    warnings.warn(
        "OK Script 3 removed the web frontend; launching the desktop UI. "
        "Use main.py instead.",
        FutureWarning,
        stacklevel=2,
    )
    OK(config).start()


if __name__ == "__main__":
    main()
