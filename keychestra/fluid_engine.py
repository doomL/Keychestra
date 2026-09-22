"""FluidSynth + SoundFont engine (required — no synth fallback)."""

from __future__ import annotations

import logging
import math
import threading
import time
from pathlib import Path

from keychestra.instruments import INSTRUMENTS, SynthConfig, apply_instrument, is_drums

log = logging.getLogger("keychestra")

MELODY_CH = 0
DRUM_CH = 9

# pyFluidsynth pitch_bend() takes a *signed* offset: 0 = center.
# Never pass absolute MIDI 0…16383 values (that detunes by ~4 semitones).
PITCH_BEND_CENTER = 0

SOUND_FONT_CANDIDATES = (
    Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
    Path("/usr/share/soundfonts/FluidR3_GM.sf2"),
    Path("/usr/share/sounds/sf2/default-GM.sf2"),
    Path("/usr/local/share/sounds/sf2/FluidR3_GM.sf2"),
)


def find_soundfont(explicit: str | None = None) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_file():
            return p
    for p in SOUND_FONT_CANDIDATES:
        if p.is_file():
            return p
    return None


class FluidEngine:
    backend_name = "fluidsynth"

    def __init__(self, cfg: SynthConfig, soundfont: Path, gain: float = 0.4) -> None:
        import fluidsynth

        self.cfg = cfg
        self._lock = threading.Lock()
        self._active: dict[object, tuple[int, int]] = {}
        self.muted = False
        self._tremolo = False
        self._tremolo_stop = threading.Event()
        self._tremolo_thread: threading.Thread | None = None
        # 0…1 → amplitude tremolo depth (Space). No pitch bend.
        self.tremolo_intensity = 0.45
        self.tremolo_ramp_s = 1.0

        self.fs = fluidsynth.Synth(samplerate=float(cfg.sample_rate))
        for driver in ("pulseaudio", "alsa"):
            try:
                self.fs.start(driver=driver)
                log.info("FluidSynth audio driver: %s", driver)
                break
            except Exception as exc:
                log.debug("FluidSynth driver %s failed: %s", driver, exc)
        else:
            self.fs.start()

        self._sfid = self.fs.sfload(str(soundfont))
        if self._sfid < 0:
            self.fs.delete()
            raise RuntimeError(f"Failed to load SoundFont: {soundfont}")

        self.fs.setting("synth.gain", float(gain))
        self._apply_program()
        self._set_gain_from_volume()
        self._reset_pitch_bend()
        log.info("SoundFont loaded: %s", soundfont)

    def _channel(self) -> int:
        return DRUM_CH if is_drums(self.cfg.instrument) else MELODY_CH

    def _base_gain(self) -> float:
        return max(0.05, min(1.2, self.cfg.volume * 2.2))

    def _apply_program(self) -> None:
        inst = INSTRUMENTS.get(self.cfg.instrument, INSTRUMENTS["piano"])
        if inst.is_drums:
            try:
                self.fs.program_select(DRUM_CH, self._sfid, 128, 0)
            except Exception:
                self.fs.program_select(DRUM_CH, self._sfid, 0, 0)
        else:
            self.fs.program_select(MELODY_CH, self._sfid, 0, int(inst.gm_program))
        self._reset_pitch_bend()

    def _set_gain_from_volume(self) -> None:
        if self._tremolo:
            return
        try:
            self.fs.setting("synth.gain", float(self._base_gain()))
        except Exception:
            pass

    def _reset_pitch_bend(self) -> None:
        for ch in (MELODY_CH, DRUM_CH):
            try:
                self.fs.pitch_bend(ch, PITCH_BEND_CENTER)
            except Exception:
                pass

    def _reset_expression(self) -> None:
        for ch in (MELODY_CH, DRUM_CH):
            try:
                self.fs.cc(ch, 11, 127)
            except Exception:
                pass

    def set_volume(self, volume: float) -> None:
        self.cfg.volume = float(max(0.0, min(1.0, volume)))
        self._set_gain_from_volume()

    def set_instrument(self, instrument_id: str) -> None:
        self.all_notes_off()
        self.cfg = apply_instrument(self.cfg, instrument_id)
        self._apply_program()

    def set_muted(self, muted: bool) -> None:
        self.muted = muted
        if muted:
            self.all_notes_off()

    def toggle_mute(self) -> bool:
        self.set_muted(not self.muted)
        return self.muted

    def set_tremolo_intensity(self, intensity: float) -> None:
        self.tremolo_intensity = float(max(0.0, min(1.0, intensity)))

    def set_tremolo_ramp(self, seconds: float) -> None:
        self.tremolo_ramp_s = float(max(0.0, min(4.0, seconds)))

    def set_tremolo(self, enabled: bool) -> None:
        """Hold Space → amplitude tremolo (volume only — never touches pitch)."""
        enabled = bool(enabled)
        if enabled == self._tremolo:
            return
        self._tremolo = enabled
        if enabled:
            self._tremolo_stop.clear()
            self._tremolo_thread = threading.Thread(
                target=self._tremolo_loop, name="keychestra-tremolo", daemon=True
            )
            self._tremolo_thread.start()
        else:
            self._tremolo_stop.set()
            if self._tremolo_thread is not None:
                self._tremolo_thread.join(timeout=0.5)
                self._tremolo_thread = None
            self._reset_expression()
            self._set_gain_from_volume()
            self._reset_pitch_bend()

    def _tremolo_loop(self) -> None:
        rate_hz = 4.5
        # Intensity 1.0 ≈ clear pulse without vanishing the note
        absolute_max_depth = 0.55
        ramp_s = max(0.0, self.tremolo_ramp_s)
        t0 = time.monotonic()
        while not self._tremolo_stop.is_set():
            elapsed = time.monotonic() - t0
            if ramp_s <= 0.001:
                ramp = 1.0
            else:
                ramp = 1.0 - math.exp(-elapsed / (ramp_s * 0.55))
            depth = absolute_max_depth * self.tremolo_intensity * min(1.0, ramp)
            phase = 2.0 * math.pi * rate_hz * elapsed
            mod = 0.5 * (1.0 + math.sin(phase))
            factor = 1.0 - depth + depth * mod
            try:
                self.fs.setting("synth.gain", float(self._base_gain() * factor))
                expr = int(round(127 * (0.30 + 0.70 * factor)))
                self.fs.cc(self._channel(), 11, max(1, min(127, expr)))
            except Exception:
                pass
            time.sleep(0.012)

    def note_on(self, key_id: object, midi: int) -> None:
        if self.muted:
            return
        midi = int(max(0, min(127, midi)))
        vel = int(max(40, min(110, 45 + self.cfg.volume * 130)))
        ch = self._channel()
        if not self._tremolo:
            self._reset_pitch_bend()
        with self._lock:
            old = self._active.pop(key_id, None)
            if old is not None:
                self.fs.noteoff(old[0], old[1])
            self._active[key_id] = (ch, midi)
        self.fs.noteon(ch, midi, vel)

    def note_off(self, key_id: object) -> None:
        with self._lock:
            pair = self._active.pop(key_id, None)
        if pair is not None:
            self.fs.noteoff(pair[0], pair[1])

    def panic(self) -> None:
        """Silence everything — stuck notes and tremolo."""
        self.set_tremolo(False)
        self.all_notes_off()
        log.info("panic — all notes off")

    def all_notes_off(self) -> None:
        with self._lock:
            notes = list(self._active.values())
            self._active.clear()
        for ch, midi in notes:
            self.fs.noteoff(ch, midi)
        for ch in (MELODY_CH, DRUM_CH):
            try:
                self.fs.cc(ch, 123, 0)
                self.fs.cc(ch, 120, 0)
            except Exception:
                pass
        self._reset_expression()
        self._reset_pitch_bend()

    def shutdown(self) -> None:
        self.set_tremolo(False)
        self.all_notes_off()
        try:
            self.fs.delete()
        except Exception:
            pass


def create_engine(cfg: SynthConfig, soundfont_path: str | None = None) -> FluidEngine:
    sf = find_soundfont(soundfont_path)
    if sf is None:
        raise RuntimeError(
            "SoundFont non trovato. Installa: sudo apt install fluid-soundfont-gm"
        )
    try:
        import fluidsynth  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "pyFluidsynth mancante. Nel venv: pip install pyFluidsynth "
            "e sul sistema: sudo apt install fluidsynth"
        ) from exc
    return FluidEngine(cfg, sf)
