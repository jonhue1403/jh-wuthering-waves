"""Standalone read-only Farming Assistant browser launcher.

Unlike main_web.py, this does not start OK Script or the game executor.
"""
from src.automation.farming_web_server import main


if __name__ == "__main__":
    raise SystemExit(main())
