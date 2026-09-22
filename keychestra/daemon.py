"""Daemon orchestration: config, hotkeys, lifecycle, persistence."""

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

from keychestra.fluid_engine import create_engine
from keychestra.instruments import INSTRUMENTS, SynthConfig, apply_instrument, is_drums
from keychestra.keymap import (
    LAYOUT_LABELS,
    LAYOUT_ORDER,
    LAYOUT_PIANO,
    LAYOUT_SCALE_ROWS,
    build_drum_keymap,
    build_keymap,
    resolve_midi,
    z_note_label,
)
from keychestra.controls_window import ControlsWindow
from keychestra.jam_window import JamWindow
from keychestra.listener import KeyboardOrganListener
from keychestra.notify import notify, notify_recording_saved
from keychestra.recorder import SessionRecorder
from keychestra.scales import ROOT_NAMES, SCALE_INTERVALS, ScaleSettings

log = logging.getLogger("keychestra")

REPO_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"
USER_CONFIG = Path.home() / ".config" / "keychestra" / "config.yaml"


def resolve_config_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    if USER_CONFIG.is_file():
        return USER_CONFIG
    return REPO_CONFIG


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = resolve_config_path(path)
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class OrganDaemon:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = resolve_config_path(config_path)
        # Always persist to the user config so settings survive reboot
        self.persist_path = USER_CONFIG if config_path is None else config_path
        raw = load_config(config_path)
        self.raw = raw

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

        self.ignore_repeat = bool(raw.get("ignore_repeat", True))
        self.mute_hotkey = str(raw.get("mute_hotkey", "<ctrl>+<shift>+o"))
        self.quit_hotkey = str(raw.get("quit_hotkey", "<ctrl>+<shift>+q"))
        self.panic_hotkey = str(raw.get("panic_hotkey", "<ctrl>+<shift>+p"))
        self.tray_enabled = bool(raw.get("tray", True))

        self._rebuild_keymap()
        self.engine = create_engine(self.synth_cfg, soundfont_path=raw.get("soundfont"))
        self.engine.set_tremolo_intensity(float(raw.get("tremolo_intensity", 0.45)))
        self.engine.set_tremolo_ramp(float(raw.get("tremolo_ramp_s", 1.0)))
        self.recorder = SessionRecorder(
            output_dir=Path(raw["record_dir"]).expanduser()
            if raw.get("record_dir")
            else None
        )
        self.jam_window = JamWindow(self)
        self.controls_window = ControlsWindow(self)
        self.listener: KeyboardOrganListener | None = None
        self._hotkeys: keyboard.GlobalHotKeys | None = None
        self._tray = None
        self._stop = threading.Event()
        self._persist_lock = threading.Lock()

        # Seed user config on first run so reboot always has a file
        if not USER_CONFIG.is_file() and config_path is None:
            self._persist()

    def _persist(self) -> None:
        """Write current settings so they survive app quit / reboot."""
        data = {
            "tray": self.tray_enabled,
            "instrument": self.synth_cfg.instrument,
            "layout": self.layout,
            "scale": self.scale_settings.scale,
            "root": self.scale_settings.root,
            "octave": self.scale_settings.octave,
            "volume": round(float(self.synth_cfg.volume), 3),
            "tremolo_intensity": round(float(self.engine.tremolo_intensity), 3),
            "tremolo_ramp_s": round(float(self.engine.tremolo_ramp_s), 3),
            "sample_rate": int(self.synth_cfg.sample_rate),
            "mute_hotkey": self.mute_hotkey,
            "quit_hotkey": self.quit_hotkey,
            "panic_hotkey": self.panic_hotkey,
            "ignore_repeat": self.ignore_repeat,
        }
        if self.raw.get("soundfont"):
            data["soundfont"] = self.raw["soundfont"]

        path = self.persist_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._persist_lock:
                tmp = path.with_suffix(".yaml.tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write("# Keychestra — auto-saved settings\n")
                    yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
                tmp.replace(path)
            log.debug("settings saved → %s", path)
        except Exception:
            log.exception("failed to save settings to %s", path)

    def _rebuild_keymap(self) -> None:
        if is_drums(self.synth_cfg.instrument):
            self.keymap = build_drum_keymap()
        else:
            self.keymap = build_keymap(layout=self.layout, settings=self.scale_settings)
            z = z_note_label(self.layout, self.scale_settings)
            log.info(
                "keymap %s · %s · Z → %s",
                LAYOUT_LABELS[self.layout],
                self.scale_settings.label,
                z,
            )

    def _announce_mapping(self) -> None:
        if is_drums(self.synth_cfg.instrument):
            return
        z = z_note_label(self.layout, self.scale_settings)
        if self.layout == LAYOUT_SCALE_ROWS:
            tip = f"Scale rows — Z = root → {z}"
        else:
            tip = f"Piano — Z = C fixed (now {z}); root only affects snap"
        notify("Keychestra", tip, urgency="low")

    def set_layout(self, layout: str) -> None:
        if layout not in LAYOUT_ORDER:
            return
        self.layout = layout
        self._rebuild_keymap()
        self.engine.all_notes_off()
        log.info("layout → %s", LAYOUT_LABELS[layout])
        self._announce_mapping()
        self._persist()
        if self._tray is not None:
            self._tray._refresh()

    def set_instrument(self, instrument_id: str) -> None:
        if instrument_id not in INSTRUMENTS:
            return
        self.engine.set_instrument(instrument_id)
        self.synth_cfg = self.engine.cfg
        self._rebuild_keymap()
        log.info("instrument → %s", INSTRUMENTS[instrument_id].label)
        self._persist()
        if self._tray is not None:
            self._tray._refresh()

    def set_scale(self, scale_id: str) -> None:
        if scale_id not in SCALE_INTERVALS:
            return
        self.scale_settings.scale = scale_id
        self._rebuild_keymap()
        self.engine.all_notes_off()
        log.info("scale → %s", self.scale_settings.label)
        self._announce_mapping()
        self._persist()
        if self._tray is not None:
            self._tray._refresh()

    def set_root(self, root: str) -> None:
        if root not in ROOT_NAMES:
            return
        self.scale_settings.root = root
        self._rebuild_keymap()
        self.engine.all_notes_off()
        log.info("root → %s", self.scale_settings.label)
        self._announce_mapping()
        self._persist()
        if self._tray is not None:
            self._tray._refresh()

    def set_octave(self, octave: int) -> None:
        self.scale_settings.octave = max(1, min(6, int(octave)))
        self._rebuild_keymap()
        self.engine.all_notes_off()
        log.info("octave → %d", self.scale_settings.octave)
        self._persist()
        if self._tray is not None:
            self._tray._refresh()

    def set_volume(self, volume: float) -> None:
        self.engine.set_volume(volume)
        self.synth_cfg = self.engine.cfg
        self._persist()

    def set_tremolo_intensity(self, intensity: float) -> None:
        self.engine.set_tremolo_intensity(intensity)
        self._persist()

    def set_tremolo_ramp(self, seconds: float) -> None:
        self.engine.set_tremolo_ramp(seconds)
        self._persist()

    def open_controls_window(self) -> None:
        self.controls_window.show()
        if self._tray is not None:
            self._tray._refresh()

    def _on_press(self, key: Key | KeyCode) -> None:
        if key == Key.space:
            self.engine.set_tremolo(True)
            return
        if is_drums(self.synth_cfg.instrument):
            midi = resolve_midi(self.keymap, key, settings=None, layout=LAYOUT_PIANO)
        else:
            midi = resolve_midi(
                self.keymap, key, self.scale_settings, layout=self.layout
            )
        if midi is None:
            return
        kid = KeyboardOrganListener._key_id(key)
        self.engine.note_on(kid, midi)

    def _on_release(self, key: Key | KeyCode) -> None:
        if key == Key.space:
            self.engine.set_tremolo(False)
            return
        kid = KeyboardOrganListener._key_id(key)
        self.engine.note_off(kid)

    def panic(self) -> None:
        self.engine.panic()
        notify("Keychestra", "Panic — all notes off", urgency="low")
        if self._tray is not None:
            self._tray._refresh()

    def open_jam_window(self) -> None:
        self.jam_window.show()
        if self._tray is not None:
            self._tray._refresh()

    def _toggle_mute(self) -> None:
        muted = self.engine.toggle_mute()
        log.info("mute %s", "ON" if muted else "OFF")
        if self._tray is not None:
            self._tray._refresh()

    def toggle_recording(self) -> bool:
        """Start/stop session capture of system audio (YouTube + Keychestra)."""
        if self.recorder.recording:
            path = self.recorder.stop()
            log.info("session saved: %s", path)
            notify_recording_saved(path)
            if self._tray is not None:
                self._tray._refresh()
            return False
        try:
            path = self.recorder.start()
            log.info("session recording: %s", path)
            notify("Recording…", f"Capturing system audio\n→ {path.parent}", urgency="low")
        except Exception as exc:
            log.exception("could not start session recording")
            notify("Recording failed", str(exc), urgency="critical")
            if self._tray is not None:
                self._tray._refresh()
            return False
        if self._tray is not None:
            self._tray._refresh()
        return True

    def request_stop(self) -> None:
        log.info("stopping…")
        if self.recorder.recording:
            path = self.recorder.stop()
            notify_recording_saved(path)
        self.engine.panic()
        self.jam_window.close()
        self.controls_window.close()
        self._persist()
        self._stop.set()

    def run(self) -> int:
        log.info(
            "Keychestra — %s / %s / %s. Config: %s",
            INSTRUMENTS[self.synth_cfg.instrument].label,
            self.scale_settings.label,
            LAYOUT_LABELS[self.layout],
            self.persist_path,
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
                self.panic_hotkey: self.panic,
            }
        )
        self._hotkeys.start()

        if self.tray_enabled:
            try:
                from keychestra.tray import TrayController

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
