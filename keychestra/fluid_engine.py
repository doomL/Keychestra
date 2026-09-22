"""FluidSynth + SoundFont engine (required — no synth fallback)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from keychestra.instruments import INSTRUMENTS, SynthConfig, apply_instrument

log = logging.getLogger("keychestra")

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
        self._active: dict[object, int] = {}
        self.muted = False

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
        log.info("SoundFont loaded: %s", soundfont)

    def _apply_program(self) -> None:
        inst = INSTRUMENTS.get(self.cfg.instrument, INSTRUMENTS["piano"])
        self.fs.program_select(0, self._sfid, 0, int(inst.gm_program))

    def _set_gain_from_volume(self) -> None:
        gain = max(0.05, min(1.2, self.cfg.volume * 2.2))
        try:
            self.fs.setting("synth.gain", float(gain))
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

    def note_on(self, key_id: object, midi: int) -> None:
        if self.muted:
            return
        midi = int(max(0, min(127, midi)))
        vel = int(max(40, min(100, 40 + self.cfg.volume * 120)))
        with self._lock:
            old = self._active.pop(key_id, None)
            if old is not None:
                self.fs.noteoff(0, old)
            self._active[key_id] = midi
        self.fs.noteon(0, midi, vel)

    def note_off(self, key_id: object) -> None:
        with self._lock:
            midi = self._active.pop(key_id, None)
        if midi is not None:
            self.fs.noteoff(0, midi)

    def all_notes_off(self) -> None:
        with self._lock:
            notes = list(self._active.values())
            self._active.clear()
        for midi in notes:
            self.fs.noteoff(0, midi)
        try:
            self.fs.cc(0, 123, 0)
        except Exception:
            pass

    def shutdown(self) -> None:
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
