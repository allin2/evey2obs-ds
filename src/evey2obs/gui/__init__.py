"""Desktop GUI using tkinter (standard library, zero extra dependencies)."""

from __future__ import annotations

from evey2obs.config_file import load_settings
from evey2obs.settings import AppSettings


def launch_gui(settings: AppSettings | None = None) -> None:
    """Create and run the main evey2obs application window.

    Args:
        settings: Pre-loaded settings. If None, loads from config file
                  (with env var overrides).
    """
    from evey2obs.gui.app import App

    app = App(settings or load_settings())
    app.mainloop()
