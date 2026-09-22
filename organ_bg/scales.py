"""Musical scales, roots, and snap-to-scale."""

from __future__ import annotations

from dataclasses import dataclass

# Semitone steps between successive degrees (wraps each octave)
SCALE_INTERVALS: dict[str, tuple[int, ...]] = {
    "major": (2, 2, 1, 2, 2, 2, 1),
    "natural_minor": (2, 1, 2, 2, 1, 2, 2),
    "harmonic_minor": (2, 1, 2, 2, 1, 3, 1),
    "melodic_minor": (2, 1, 2, 2, 2, 2, 1),
    "dorian": (2, 1, 2, 2, 2, 1, 2),
    "phrygian": (1, 2, 2, 2, 1, 2, 2),
    "lydian": (2, 2, 2, 1, 2, 2, 1),
    "mixolydian": (2, 2, 1, 2, 2, 1, 2),
    "pentatonic_major": (2, 2, 3, 2, 3),
    "pentatonic_minor": (3, 2, 2, 3, 2),
    "blues": (3, 2, 1, 1, 3, 2),
    "whole_tone": (2, 2, 2, 2, 2, 2),
    "chromatic": (1,),
}

SCALE_LABELS: dict[str, str] = {
    "major": "Major",
    "natural_minor": "Natural minor",
    "harmonic_minor": "Harmonic minor",
    "melodic_minor": "Melodic minor",
    "dorian": "Dorian",
    "phrygian": "Phrygian",
    "lydian": "Lydian",
    "mixolydian": "Mixolydian",
    "pentatonic_major": "Pentatonic major",
    "pentatonic_minor": "Pentatonic minor",
    "blues": "Blues",
    "whole_tone": "Whole tone",
    "chromatic": "Chromatic",
}

SCALE_ORDER = tuple(SCALE_LABELS.keys())

ROOT_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
ROOT_TO_SEMITONE = {name: i for i, name in enumerate(ROOT_NAMES)}


@dataclass
class ScaleSettings:
    scale: str = "major"
    root: str = "C"
    octave: int = 3

    @property
    def c_midi(self) -> int:
        """Concert C for piano layout key Z (Do fisso)."""
        return 12 + self.octave * 12

    @property
    def base_midi(self) -> int:
        """Root note at the chosen octave — used by scale-rows layout."""
        return 12 + self.octave * 12 + ROOT_TO_SEMITONE[self.root]

    @property
    def intervals(self) -> tuple[int, ...]:
        return SCALE_INTERVALS.get(self.scale, SCALE_INTERVALS["major"])

    @property
    def label(self) -> str:
        return f"{self.root} {SCALE_LABELS.get(self.scale, self.scale)}"

    def pitch_classes(self) -> frozenset[int]:
        if self.scale == "chromatic":
            return frozenset(range(12))
        root_pc = ROOT_TO_SEMITONE[self.root]
        pcs: set[int] = set()
        acc = 0
        for step in self.intervals:
            pcs.add((root_pc + acc) % 12)
            acc += step
        return frozenset(pcs)


def degree_to_midi(base_midi: int, intervals: tuple[int, ...], degree: int) -> int:
    """Map scale degree index (0,1,2,…) to absolute MIDI note."""
    if not intervals:
        return base_midi + degree
    midi = base_midi
    for i in range(degree):
        midi += intervals[i % len(intervals)]
    return midi


def snap_to_scale(midi: int, settings: ScaleSettings) -> int:
    """
    If midi is already in the scale, return it.
    Otherwise return the nearest in-scale MIDI note (tie → lower note).
    """
    if settings.scale == "chromatic":
        return midi
    pcs = settings.pitch_classes()
    if (midi % 12) in pcs:
        return midi

    best = midi
    best_dist = 99
    for delta in range(0, 7):
        for candidate in (midi - delta, midi + delta):
            if candidate < 0 or candidate > 127:
                continue
            if (candidate % 12) not in pcs:
                continue
            dist = abs(candidate - midi)
            if dist < best_dist or (dist == best_dist and candidate < best):
                best_dist = dist
                best = candidate
        if best_dist == 0:
            break
    return best
