"""Shared GTK main loop so jam + controls windows can coexist."""

from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger("keychestra")

_lock = threading.Lock()
_loop_ready = threading.Event()
_loop_thread: threading.Thread | None = None
_open_windows = 0


def ensure_gtk_loop() -> None:
    global _loop_thread
    with _lock:
        if _loop_thread is not None and _loop_thread.is_alive():
            return

        def _run() -> None:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk

            _loop_ready.set()
            Gtk.main()

        _loop_ready.clear()
        _loop_thread = threading.Thread(target=_run, name="keychestra-gtk", daemon=True)
        _loop_thread.start()
    if not _loop_ready.wait(timeout=3.0):
        raise RuntimeError("GTK main loop failed to start")


def idle(callback) -> None:
    """Schedule callback on the GTK thread."""
    ensure_gtk_loop()
    from gi.repository import GLib

    GLib.idle_add(callback)


def window_opened() -> None:
    global _open_windows
    with _lock:
        _open_windows += 1


def window_closed() -> None:
    """Quit GTK main only when the last Keychestra window is gone."""
    global _open_windows, _loop_thread
    with _lock:
        _open_windows = max(0, _open_windows - 1)
        if _open_windows > 0:
            return
    try:
        from gi.repository import GLib, Gtk

        def _quit() -> bool:
            if Gtk.main_level() > 0:
                Gtk.main_quit()
            return False

        GLib.idle_add(_quit)
    except Exception:
        pass
    with _lock:
        _loop_thread = None
        _loop_ready.clear()
    # tiny pause so a quick re-open starts a fresh loop cleanly
    time.sleep(0.05)
