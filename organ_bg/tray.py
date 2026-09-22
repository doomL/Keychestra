"""System tray icon (GNOME AppIndicator / StatusNotifier)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from organ_bg.daemon import OrganDaemon

from organ_bg.instruments import INSTRUMENT_ORDER, INSTRUMENTS
from organ_bg.keymap import LAYOUT_LABELS, LAYOUT_ORDER
from organ_bg.scales import ROOT_NAMES, SCALE_LABELS, SCALE_ORDER

log = logging.getLogger("organ_bg")

ASSETS = Path(__file__).resolve().parent / "assets"


def _draw_pipe_icon(size: int, muted: bool) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    body = (46, 28, 28, 255) if not muted else (90, 90, 90, 255)
    accent = (210, 175, 90, 255) if not muted else (150, 150, 150, 255)
    margin = size // 10
    d.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=size // 8,
        fill=body,
    )
    pipe_w = max(2, size // 10)
    gap = size // 7
    base_y = size - margin - size // 8
    top_ys = (margin + size // 5, margin + size // 10, margin + size // 4)
    xs = (size // 2 - gap - pipe_w // 2, size // 2 - pipe_w // 2, size // 2 + gap - pipe_w // 2)
    for x, top in zip(xs, top_ys):
        d.rectangle((x, top, x + pipe_w, base_y), fill=accent)
        d.ellipse((x - 1, top - pipe_w // 2, x + pipe_w + 1, top + pipe_w // 2), fill=accent)
    if muted:
        d.line(
            (margin + 2, size - margin - 2, size - margin - 2, margin + 2),
            fill=(230, 230, 230, 230),
            width=max(2, size // 16),
        )
    return img


def load_icons() -> tuple[Image.Image, Image.Image]:
    ASSETS.mkdir(parents=True, exist_ok=True)
    on_path = ASSETS / "organ.png"
    mute_path = ASSETS / "organ-mute.png"
    if not on_path.exists():
        _draw_pipe_icon(128, muted=False).save(on_path)
    if not mute_path.exists():
        _draw_pipe_icon(128, muted=True).save(mute_path)
    return Image.open(on_path), Image.open(mute_path)


class TrayController:
    """Runs pystray in its own thread; updates icon / menus live."""

    def __init__(self, daemon: OrganDaemon) -> None:
        self.daemon = daemon
        self._icon_on, self._icon_mute = load_icons()
        self._icon = None
        self._thread: threading.Thread | None = None

    def _title(self) -> str:
        inst = INSTRUMENTS[self.daemon.engine.cfg.instrument].label
        scale = self.daemon.scale_settings.label
        layout = LAYOUT_LABELS.get(self.daemon.layout, self.daemon.layout)
        state = "muted" if self.daemon.engine.muted else "on"
        short = "piano" if self.daemon.layout == "piano" else "rows"
        return f"Organ — {inst} · {scale} · {short} ({state})"

    def _current_image(self) -> Image.Image:
        return self._icon_mute if self.daemon.engine.muted else self._icon_on

    def _refresh(self) -> None:
        if self._icon is None:
            return
        self._icon.icon = self._current_image()
        self._icon.title = self._title()
        try:
            self._icon.update_menu()
        except Exception:
            pass

    def _toggle_mute(self, _icon=None, _item=None) -> None:
        self.daemon._toggle_mute()
        self._refresh()

    def _quit(self, _icon=None, _item=None) -> None:
        self.daemon.request_stop()
        if self._icon is not None:
            self._icon.stop()

    def _volume_delta(self, delta: float) -> Callable:
        def _cb(_icon=None, _item=None) -> None:
            vol = max(0.0, min(1.0, self.daemon.engine.cfg.volume + delta))
            self.daemon.engine.set_volume(vol)
            log.info("volume %.2f", vol)
            self._refresh()

        return _cb

    def _mute_label(self, _item=None) -> str:
        return "Unmute" if self.daemon.engine.muted else "Mute"

    def _set_instrument(self, instrument_id: str) -> Callable:
        def _cb(_icon=None, _item=None) -> None:
            self.daemon.set_instrument(instrument_id)
            self._refresh()

        return _cb

    def _instrument_checked(self, instrument_id: str) -> Callable:
        def _checked(_item=None) -> bool:
            return self.daemon.engine.cfg.instrument == instrument_id

        return _checked

    def _set_layout(self, layout_id: str) -> Callable:
        def _cb(_icon=None, _item=None) -> None:
            self.daemon.set_layout(layout_id)
            self._refresh()

        return _cb

    def _layout_checked(self, layout_id: str) -> Callable:
        def _checked(_item=None) -> bool:
            return self.daemon.layout == layout_id

        return _checked

    def _set_scale(self, scale_id: str) -> Callable:
        def _cb(_icon=None, _item=None) -> None:
            self.daemon.set_scale(scale_id)
            self._refresh()

        return _cb

    def _scale_checked(self, scale_id: str) -> Callable:
        def _checked(_item=None) -> bool:
            return self.daemon.scale_settings.scale == scale_id

        return _checked

    def _set_root(self, root: str) -> Callable:
        def _cb(_icon=None, _item=None) -> None:
            self.daemon.set_root(root)
            self._refresh()

        return _cb

    def _root_checked(self, root: str) -> Callable:
        def _checked(_item=None) -> bool:
            return self.daemon.scale_settings.root == root

        return _checked

    def _octave_delta(self, delta: int) -> Callable:
        def _cb(_icon=None, _item=None) -> None:
            self.daemon.set_octave(self.daemon.scale_settings.octave + delta)
            self._refresh()

        return _cb

    def _octave_label(self, _item=None) -> str:
        return f"Octave: {self.daemon.scale_settings.octave}"

    def _build_menu(self):
        from pystray import Menu, MenuItem

        instrument_menu = Menu(
            *[
                MenuItem(
                    INSTRUMENTS[iid].label,
                    self._set_instrument(iid),
                    checked=self._instrument_checked(iid),
                    radio=True,
                )
                for iid in INSTRUMENT_ORDER
            ]
        )
        layout_menu = Menu(
            *[
                MenuItem(
                    LAYOUT_LABELS[lid],
                    self._set_layout(lid),
                    checked=self._layout_checked(lid),
                    radio=True,
                )
                for lid in LAYOUT_ORDER
            ]
        )
        scale_menu = Menu(
            *[
                MenuItem(
                    SCALE_LABELS[sid],
                    self._set_scale(sid),
                    checked=self._scale_checked(sid),
                    radio=True,
                )
                for sid in SCALE_ORDER
            ]
        )
        root_menu = Menu(
            *[
                MenuItem(
                    name,
                    self._set_root(name),
                    checked=self._root_checked(name),
                    radio=True,
                )
                for name in ROOT_NAMES
            ]
        )

        return Menu(
            MenuItem(self._mute_label, self._toggle_mute, default=True),
            MenuItem("Volume +", self._volume_delta(0.05)),
            MenuItem("Volume −", self._volume_delta(-0.05)),
            Menu.SEPARATOR,
            MenuItem("Layout", layout_menu),
            MenuItem("Instrument", instrument_menu),
            MenuItem("Scale", scale_menu),
            MenuItem("Root note", root_menu),
            MenuItem(
                self._octave_label,
                Menu(
                    MenuItem("Octave +", self._octave_delta(1)),
                    MenuItem("Octave −", self._octave_delta(-1)),
                ),
            ),
            Menu.SEPARATOR,
            MenuItem("Quit", self._quit),
        )

    def start(self) -> None:
        import pystray

        self._icon = pystray.Icon(
            "organ-bg",
            self._current_image(),
            self._title(),
            self._build_menu(),
        )

        def _run() -> None:
            assert self._icon is not None
            log.info("tray icon ready (click for menu)")
            self._icon.run()

        self._thread = threading.Thread(target=_run, name="organ-tray", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
