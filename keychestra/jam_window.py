"""Jam focus window — hold focus so keys don’t type into other apps."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from keychestra import gtk_ui

if TYPE_CHECKING:
    from keychestra.daemon import OrganDaemon

log = logging.getLogger("keychestra")


class JamWindow:
    def __init__(self, daemon: OrganDaemon) -> None:
        self.daemon = daemon
        self._window = None

    @property
    def open(self) -> bool:
        return self._window is not None

    def show(self) -> None:
        if self._window is not None:
            def _present() -> bool:
                if self._window is not None:
                    self._window.present()
                return False

            gtk_ui.idle(_present)
            return
        gtk_ui.idle(self._build)

    def close(self) -> None:
        win = self._window
        if win is not None:
            gtk_ui.idle(lambda: (win.destroy(), False)[1])

    def _build(self) -> bool:
        if self._window is not None:
            self._window.present()
            return False

        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, Gtk

        win = Gtk.Window(title="Keychestra — jam focus")
        win.set_default_size(440, 220)
        win.set_keep_above(True)
        win.set_border_width(18)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        win.add(box)

        title = Gtk.Label()
        title.set_markup('<span size="large" weight="bold">Keychestra</span>')
        title.set_xalign(0)
        box.pack_start(title, False, False, 0)

        body = Gtk.Label(
            label=(
                "Keep this window focused to jam without typing\n"
                "into Slack, the browser, or your editor.\n\n"
                "Piano: Z = Do (C) always.\n"
                "Scale rows: Z = tonica (Do if root is C).\n\n"
                "Hold Space = tremolo (volume).\n"
                "Ctrl+Shift+P = panic (all notes off).\n\n"
                "Keys still make sound either way — focus only\n"
                "controls where the characters go."
            )
        )
        body.set_xalign(0)
        body.set_line_wrap(True)
        box.pack_start(body, True, True, 0)

        status = Gtk.Label(label="● focused — play freely")
        status.set_xalign(0)
        box.pack_start(status, False, False, 0)

        def on_focus_in(_w, _e):
            status.set_text("● focused — play freely")
            return False

        def on_focus_out(_w, _e):
            status.set_text("○ unfocused — keys will type into other apps")
            return False

        def on_key(_w, _e):
            return True

        def on_destroy(_w):
            self._window = None
            gtk_ui.window_closed()

        win.connect("focus-in-event", on_focus_in)
        win.connect("focus-out-event", on_focus_out)
        win.connect("key-press-event", on_key)
        win.connect("key-release-event", on_key)
        win.connect("destroy", on_destroy)

        css = b"window { background-color: #1a1210; } label { color: #e8ddd0; }"
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self._window = win
        gtk_ui.window_opened()
        win.show_all()
        win.present()
        log.info("jam window open")
        return False
