"""GM SoundFont instrument catalog (FluidSynth only)."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass
class SynthConfig:
    sample_rate: int = 44100
    volume: float = 0.22
    attack_ms: float = 8.0
    release_ms: float = 180.0
    instrument: str = "piano"


@dataclass(frozen=True)
class Instrument:
    id: str
    label: str
    gm_program: int  # General MIDI program 0–127


INSTRUMENTS: dict[str, Instrument] = {
    "piano": Instrument("piano", "Acoustic Piano", 0),
    "epiano": Instrument("epiano", "Electric Piano", 4),
    "organ": Instrument("organ", "Drawbar Organ", 16),
    "church": Instrument("church", "Church Organ", 19),
    "accordion": Instrument("accordion", "Accordion", 21),
    "guitar": Instrument("guitar", "Nylon Guitar", 24),
    "eguitar": Instrument("eguitar", "Clean Electric Guitar", 27),
    "bass": Instrument("bass", "Finger Bass", 33),
    "strings": Instrument("strings", "String Ensemble", 48),
    "choir": Instrument("choir", "Choir Aahs", 52),
    "trumpet": Instrument("trumpet", "Trumpet", 56),
    "sax": Instrument("sax", "Alto Sax", 65),
    "flute": Instrument("flute", "Flute", 73),
    "clarinet": Instrument("clarinet", "Clarinet", 71),
    "bell": Instrument("bell", "Tubular Bells", 14),
    "marimba": Instrument("marimba", "Marimba", 12),
    "square": Instrument("square", "Lead Square", 80),
    "pad": Instrument("pad", "Warm Pad", 89),
    "atmosphere": Instrument("atmosphere", "Atmosphere", 99),
}

INSTRUMENT_ORDER = tuple(INSTRUMENTS.keys())


def apply_instrument(cfg: SynthConfig, instrument_id: str) -> SynthConfig:
    inst = INSTRUMENTS[instrument_id]
    return replace(cfg, instrument=inst.id)
