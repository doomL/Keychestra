"""System tray icon (GNOME AppIndicator / StatusNotifier)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from keychestra.daemon import OrganDaemon

from keychestra.instruments import INSTRUMENT_ORDER, INSTRUMENTS
from keychestra.keymap import LAYOUT_LABELS, LAYOUT_ORDER
from keychestra.scales import ROOT_NAMES, SCALE_LABELS, SCALE_ORDER

log = logging.getLogger("keychestra")

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
        state = "muted" if self.daemon.engine.muted else "on"
        short = "piano" if self.daemon.layout == "piano" else "rows"
        rec = " · REC" if self.daemon.recorder.recording else ""
        return f"Keychestra — {inst} · {scale} · {short} ({state}){rec}"

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

    def _mute_label(self, _item=None) -> str:
        return "Unmute" if self.daemon.engine.muted else "Mute"

    def _record_label(self, _item=None) -> str:
        if self.daemon.recorder.recording:
            return "■ Stop recording"
        return "● Record session"

    def _toggle_record(self, _icon=None, _item=None) -> None:
        self.daemon.toggle_recording()
        self._refresh()

    def _open_jam(self, _icon=None, _item=None) -> None:
        self.daemon.open_jam_window()
        self._refresh()

    def _open_controls(self, _icon=None, _item=None) -> None:
        self.daemon.open_controls_window()
        self._refresh()

    def _panic(self, _icon=None, _item=None) -> None:
        self.daemon.panic()
        self._refresh()

    @staticmethod
    def _near(a: float, b: float, eps: float = 0.03) -> bool:
        return abs(a - b) <= eps

    def _set_volume(self, value: float) -> Callable:
        def _cb(_icon=None, _item=None) -> None:
            self.daemon.set_volume(value)
            self._refresh()

        return _cb

    def _volume_checked(self, value: float) -> Callable:
        def _checked(_item=None) -> bool:
            return self._near(self.daemon.engine.cfg.volume, value)

        return _checked

    def _set_tremolo_intensity(self, value: float) -> Callable:
        def _cb(_icon=None, _item=None) -> None:
            self.daemon.set_tremolo_intensity(value)
            self._refresh()

        return _cb

    def _tremolo_intensity_checked(self, value: float) -> Callable:
        def _checked(_item=None) -> bool:
            return self._near(self.daemon.engine.tremolo_intensity, value)

        return _checked

    def _set_tremolo_ramp(self, seconds: float) -> Callable:
        def _cb(_icon=None, _item=None) -> None:
            self.daemon.set_tremolo_ramp(seconds)
            self._refresh()

        return _cb

    def _tremolo_ramp_checked(self, seconds: float) -> Callable:
        def _checked(_item=None) -> bool:
            return self._near(self.daemon.engine.tremolo_ramp_s, seconds, eps=0.08)

        return _checked

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

        volume_steps = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.65, 0.80, 1.00)
        tremolo_steps = (0.0, 0.15, 0.30, 0.45, 0.60, 0.75, 1.00)
        ramp_presets = (
            (0.0, "Instant (full now)"),
            (0.35, "Fast"),
            (1.0, "Medium"),
            (2.0, "Slow"),
        )

        volume_menu = Menu(
            *[
                MenuItem(
                    f"{int(v * 100)}%",
                    self._set_volume(v),
                    checked=self._volume_checked(v),
                    radio=True,
                )
                for v in volume_steps
            ],
            Menu.SEPARATOR,
            MenuItem("Fine slider…", self._open_controls),
        )
        tremolo_menu = Menu(
            *[
                MenuItem(
                    f"{int(v * 100)}%",
                    self._set_tremolo_intensity(v),
                    checked=self._tremolo_intensity_checked(v),
                    radio=True,
                )
                for v in tremolo_steps
            ],
            Menu.SEPARATOR,
            MenuItem("Fine slider…", self._open_controls),
        )
        ramp_menu = Menu(
            *[
                MenuItem(
                    label,
                    self._set_tremolo_ramp(secs),
                    checked=self._tremolo_ramp_checked(secs),
                    radio=True,
                )
                for secs, label in ramp_presets
            ]
        )

        return Menu(
            MenuItem(self._mute_label, self._toggle_mute, default=True),
            MenuItem("Panic (all notes off)", self._panic),
            MenuItem(self._record_label, self._toggle_record),
            MenuItem("Open jam window", self._open_jam),
            Menu.SEPARATOR,
            MenuItem("Volume", volume_menu),
            MenuItem("Tremolo intensity", tremolo_menu),
            MenuItem("Tremolo attack", ramp_menu),
            MenuItem("All sliders…", self._open_controls),
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
            "keychestra",
            self._current_image(),
            self._title(),
            self._build_menu(),
        )

        def _run() -> None:
            assert self._icon is not None
            log.info("tray icon ready (click for menu)")
            self._icon.run()

        self._thread = threading.Thread(target=_run, name="keychestra-tray", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
