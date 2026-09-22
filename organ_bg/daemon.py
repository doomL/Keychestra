"""Daemon orchestration: config, hotkeys, lifecycle."""

from __future__ import annotations

import logging
import signal
import sys
import threading
from pathlib import Path
from typing import Any

import yaml
from pynput import keyboard
from pynput.keyboard import Key, KeyCode

from organ_bg.fluid_engine import create_engine
from organ_bg.instruments import INSTRUMENTS, SynthConfig, apply_instrument
from organ_bg.keymap import (
    LAYOUT_LABELS,
    LAYOUT_ORDER,
    LAYOUT_PIANO,
    build_keymap,
    resolve_midi,
)
from organ_bg.listener import KeyboardOrganListener
from organ_bg.scales import ROOT_NAMES, SCALE_INTERVALS, ScaleSettings

log = logging.getLogger("organ_bg")

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or DEFAULT_CONFIG
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class OrganDaemon:
    def __init__(self, config_path: Path | None = None) -> None:
        raw = load_config(config_path)
        self.raw = raw
        self.config_path = config_path or DEFAULT_CONFIG

        instrument = str(raw.get("instrument", "piano"))
        if instrument not in INSTRUMENTS:
            instrument = "piano"

        scale = str(raw.get("scale", "major"))
        if scale not in SCALE_INTERVALS:
            scale = "major"
        root = str(raw.get("root", "C"))
        if root not in ROOT_NAMES:
            root = "C"
        octave = int(raw.get("octave", 3))

        layout = str(raw.get("layout", LAYOUT_PIANO))
        if layout not in LAYOUT_ORDER:
            layout = LAYOUT_PIANO
        self.layout = layout

        self.scale_settings = ScaleSettings(scale=scale, root=root, octave=octave)
        self.synth_cfg = apply_instrument(
            SynthConfig(
                sample_rate=int(raw.get("sample_rate", 44100)),
                volume=float(raw.get("volume", 0.22)),
            ),
            instrument,
        )

        self.keymap = build_keymap(layout=self.layout, settings=self.scale_settings)
        self.ignore_repeat = bool(raw.get("ignore_repeat", True))
        self.mute_hotkey = str(raw.get("mute_hotkey", "<ctrl>+<shift>+o"))
        self.quit_hotkey = str(raw.get("quit_hotkey", "<ctrl>+<shift>+q"))
        self.tray_enabled = bool(raw.get("tray", True))

        self.engine = create_engine(self.synth_cfg, soundfont_path=raw.get("soundfont"))
        self.listener: KeyboardOrganListener | None = None
        self._hotkeys: keyboard.GlobalHotKeys | None = None
        self._tray = None
        self._stop = threading.Event()

    def _rebuild_keymap(self) -> None:
        self.keymap = build_keymap(layout=self.layout, settings=self.scale_settings)
        self.engine.all_notes_off()

    def set_layout(self, layout: str) -> None:
        if layout not in LAYOUT_ORDER:
            return
        self.layout = layout
        self._rebuild_keymap()
        log.info("layout → %s", LAYOUT_LABELS[layout])
        if self._tray is not None:
            self._tray._refresh()

    def set_instrument(self, instrument_id: str) -> None:
        if instrument_id not in INSTRUMENTS:
            return
        self.engine.set_instrument(instrument_id)
        self.synth_cfg = self.engine.cfg
        log.info("instrument → %s", INSTRUMENTS[instrument_id].label)
        if self._tray is not None:
            self._tray._refresh()

    def set_scale(self, scale_id: str) -> None:
        if scale_id not in SCALE_INTERVALS:
            return
        self.scale_settings.scale = scale_id
        self._rebuild_keymap()
        log.info("scale → %s", self.scale_settings.label)
        if self._tray is not None:
            self._tray._refresh()

    def set_root(self, root: str) -> None:
        if root not in ROOT_NAMES:
            return
        self.scale_settings.root = root
        self._rebuild_keymap()
        log.info("root → %s", self.scale_settings.label)
        if self._tray is not None:
            self._tray._refresh()

    def set_octave(self, octave: int) -> None:
        self.scale_settings.octave = max(1, min(6, int(octave)))
        self._rebuild_keymap()
        log.info("octave → %d", self.scale_settings.octave)
        if self._tray is not None:
            self._tray._refresh()

    def _on_press(self, key: Key | KeyCode) -> None:
        midi = resolve_midi(self.keymap, key, self.scale_settings, layout=self.layout)
        if midi is None:
            return
        kid = KeyboardOrganListener._key_id(key)
        self.engine.note_on(kid, midi)

    def _on_release(self, key: Key | KeyCode) -> None:
        kid = KeyboardOrganListener._key_id(key)
        self.engine.note_off(kid)

    def _toggle_mute(self) -> None:
        muted = self.engine.toggle_mute()
        log.info("mute %s", "ON" if muted else "OFF")
        if self._tray is not None:
            self._tray._refresh()

    def request_stop(self) -> None:
        log.info("stopping…")
        self._stop.set()

    def run(self) -> int:
        log.info(
            "OrganBgWorker — %s / %s / %s. Mute: %s  Quit: %s",
            INSTRUMENTS[self.synth_cfg.instrument].label,
            self.scale_settings.label,
            LAYOUT_LABELS[self.layout],
            self.mute_hotkey,
            self.quit_hotkey,
        )

        self.listener = KeyboardOrganListener(
            on_press=self._on_press,
            on_release=self._on_release,
            ignore_repeat=self.ignore_repeat,
        )
        self.listener.start()

        self._hotkeys = keyboard.GlobalHotKeys(
            {
                self.mute_hotkey: self._toggle_mute,
                self.quit_hotkey: self.request_stop,
            }
        )
        self._hotkeys.start()

        if self.tray_enabled:
            try:
                from organ_bg.tray import TrayController

                self._tray = TrayController(self)
                self._tray.start()
            except Exception:
                log.exception("tray icon failed — continuing without it")
                self._tray = None

        def _sig(_signum: int, _frame: object) -> None:
            self.request_stop()

        signal.signal(signal.SIGINT, _sig)
        signal.signal(signal.SIGTERM, _sig)

        self._stop.wait()

        if self._tray is not None:
            self._tray.stop()
        if self._hotkeys is not None:
            self._hotkeys.stop()
        if self.listener is not None:
            self.listener.stop()
        self.engine.shutdown()
        log.info("stopped")
        return 0


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
