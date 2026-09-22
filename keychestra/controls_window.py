"""GTK panel with real sliders for volume, tremolo intensity, and attack."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from keychestra import gtk_ui

if TYPE_CHECKING:
    from keychestra.daemon import OrganDaemon

log = logging.getLogger("keychestra")


class ControlsWindow:
    """Continuous sliders (tray menus only support stepped items)."""

    def __init__(self, daemon: OrganDaemon) -> None:
        self.daemon = daemon
        self._window = None
        self._vol_scale = None
        self._trem_scale = None
        self._ramp_scale = None

    def show(self) -> None:
        if self._window is not None:
            def _present() -> bool:
                if self._window is not None:
                    self._window.present()
                    self._sync_sliders()
                return False

            gtk_ui.idle(_present)
            return
        gtk_ui.idle(self._build)

    def close(self) -> None:
        win = self._window
        if win is not None:
            gtk_ui.idle(lambda: (win.destroy(), False)[1])

    def _sync_sliders(self) -> None:
        if self._vol_scale is not None:
            self._vol_scale.set_value(self.daemon.engine.cfg.volume * 100.0)
        if self._trem_scale is not None:
            self._trem_scale.set_value(self.daemon.engine.tremolo_intensity * 100.0)
        if self._ramp_scale is not None:
            self._ramp_scale.set_value(self.daemon.engine.tremolo_ramp_s)

    def _build(self) -> bool:
        if self._window is not None:
            self._window.present()
            self._sync_sliders()
            return False

        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, Gtk

        win = Gtk.Window(title="Keychestra — controls")
        win.set_default_size(420, 210)
        win.set_keep_above(True)
        win.set_border_width(16)

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        win.add(grid)

        def row(r: int, title: str, scale: Gtk.Scale, value_lbl: Gtk.Label) -> None:
            lab = Gtk.Label(label=title)
            lab.set_xalign(0)
            grid.attach(lab, 0, r, 1, 1)
            grid.attach(scale, 1, r, 1, 1)
            grid.attach(value_lbl, 2, r, 1, 1)

        vol_value = Gtk.Label(width_chars=5)
        vol = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        vol.set_draw_value(False)
        vol.set_hexpand(True)
        vol.set_value(self.daemon.engine.cfg.volume * 100.0)
        vol_value.set_text(f"{int(vol.get_value())}%")

        trem_value = Gtk.Label(width_chars=5)
        trem = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        trem.set_draw_value(False)
        trem.set_hexpand(True)
        trem.set_value(self.daemon.engine.tremolo_intensity * 100.0)
        trem_value.set_text(f"{int(trem.get_value())}%")

        ramp_value = Gtk.Label(width_chars=5)
        ramp = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 3.0, 0.05)
        ramp.set_draw_value(False)
        ramp.set_hexpand(True)
        ramp.set_value(self.daemon.engine.tremolo_ramp_s)

        def _ramp_text(secs: float) -> str:
            if secs <= 0.02:
                return "now"
            return f"{secs:.1f}s"

        ramp_value.set_text(_ramp_text(ramp.get_value()))

        def on_vol(scale: Gtk.Scale) -> None:
            vol_value.set_text(f"{int(scale.get_value())}%")
            self.daemon.set_volume(scale.get_value() / 100.0)

        def on_trem(scale: Gtk.Scale) -> None:
            trem_value.set_text(f"{int(scale.get_value())}%")
            self.daemon.set_tremolo_intensity(scale.get_value() / 100.0)

        def on_ramp(scale: Gtk.Scale) -> None:
            ramp_value.set_text(_ramp_text(scale.get_value()))
            self.daemon.set_tremolo_ramp(scale.get_value())

        vol.connect("value-changed", on_vol)
        trem.connect("value-changed", on_trem)
        ramp.connect("value-changed", on_ramp)

        row(0, "Volume", vol, vol_value)
        row(1, "Tremolo max", trem, trem_value)
        row(2, "Tremolo attack", ramp, ramp_value)

        hint = Gtk.Label(
            label="Attack 0 = full tremolo as soon as you hold Space.\n"
            "Higher = fades in the longer you hold. (Volume only — no pitch.)"
        )
        hint.set_xalign(0)
        hint.set_opacity(0.75)
        grid.attach(hint, 0, 3, 3, 1)

        css = b"window { background-color: #1a1210; } label { color: #e8ddd0; }"
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        def on_destroy(_w):
            self._window = None
            self._vol_scale = None
            self._trem_scale = None
            self._ramp_scale = None
            gtk_ui.window_closed()

        win.connect("destroy", on_destroy)

        self._window = win
        self._vol_scale = vol
        self._trem_scale = trem
        self._ramp_scale = ramp
        gtk_ui.window_opened()
        win.show_all()
        win.present()
        log.info("controls window open")
        return False
