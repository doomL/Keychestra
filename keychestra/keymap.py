"""
Keyboard layouts:

- piano: classic virtual piano — Z=Do(C) fisso, S=Do♯, X=Re, … ; out-of-scale → snap
- scale_rows: each letter row is one octave of the chosen scale; Z = tonica
"""

from __future__ import annotations

from pynput.keyboard import Key, KeyCode

from keychestra.scales import ScaleSettings, degree_to_midi, snap_to_scale

LAYOUT_PIANO = "piano"
LAYOUT_SCALE_ROWS = "scale_rows"

LAYOUT_LABELS = {
    LAYOUT_PIANO: "Piano (Z=Do fisso)",
    LAYOUT_SCALE_ROWS: "Scale rows (Z=tonica)",
}

LAYOUT_ORDER = (LAYOUT_PIANO, LAYOUT_SCALE_ROWS)

# Classic virtual-piano semitone offsets from Z (= concert C / Do)
PIANO_OFFSETS: dict[str, int] = {
    "z": 0, "s": 1, "x": 2, "d": 3, "c": 4, "v": 5,
    "g": 6, "b": 7, "h": 8, "n": 9, "j": 10, "m": 11,
    "q": 12, "2": 13, "w": 14, "3": 15, "e": 16, "r": 17,
    "5": 18, "t": 19, "6": 20, "y": 21, "7": 22, "u": 23,
    "i": 24, "9": 25, "o": 26, "0": 27, "p": 28,
}

# One octave of scale degrees per row (7 keys ≈ diatonic octave)
SCALE_ROWS = (
    list("zxcvbnm"),  # octave 0
    list("asdfghj"),  # octave 1
    list("qwertyu"),  # octave 2
)

# GM percussion (channel 10) — finger drumming layout
DRUM_NOTES: dict[str, int] = {
    # Bottom row — core kit
    "z": 36,  # Bass Drum 1
    "x": 38,  # Acoustic Snare
    "c": 42,  # Closed Hi-Hat
    "v": 46,  # Open Hi-Hat
    "b": 41,  # Low Floor Tom
    "n": 45,  # Low Tom
    "m": 47,  # Low-Mid Tom
    # Home row — extras / hands
    "a": 37,  # Side Stick
    "s": 40,  # Electric Snare
    "d": 44,  # Pedal Hi-Hat
    "f": 43,  # High Floor Tom
    "g": 48,  # Hi-Mid Tom
    "h": 50,  # High Tom
    "j": 49,  # Crash Cymbal 1
    "k": 51,  # Ride Cymbal 1
    "l": 55,  # Splash Cymbal
    # Top row — toys / latin
    "q": 39,  # Hand Clap
    "w": 54,  # Tambourine
    "e": 56,  # Cowbell
    "r": 63,  # Open Hi Conga
    "t": 64,  # Low Conga
    "y": 75,  # Claves
    "u": 70,  # Maracas
    "i": 81,  # Open Triangle
    "o": 80,  # Mute Triangle
    "p": 69,  # Cabasa
    # Number row — crashes / rides
    "1": 35,  # Acoustic Bass Drum
    "2": 57,  # Crash Cymbal 2
    "3": 59,  # Ride Cymbal 2
    "4": 52,  # Chinese Cymbal
    "5": 53,  # Ride Bell
}


def build_drum_keymap() -> dict[str, int]:
    mapping: dict[str, int] = {}
    for ch, note in DRUM_NOTES.items():
        mapping[ch] = note
        if ch.isalpha():
            mapping[ch.upper()] = note
    return mapping


def _normalize_char(char: str | None) -> str | None:
    if not char or len(char) != 1:
        return None
    return char


def build_piano_keymap(c_midi: int = 48) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for ch, offset in PIANO_OFFSETS.items():
        midi = c_midi + offset
        if 0 <= midi <= 127:
            mapping[ch] = midi
            if ch.isalpha():
                mapping[ch.upper()] = midi
    return mapping


def build_scale_rows_keymap(settings: ScaleSettings) -> dict[str, int]:
    """Each row = successive scale degrees; Z / A / Q are always the tonica."""
    mapping: dict[str, int] = {}
    intervals = settings.intervals
    n_degrees = max(1, len(intervals))
    base = settings.base_midi  # tonica at chosen octave

    for row_i, row in enumerate(SCALE_ROWS):
        for key_i, ch in enumerate(row):
            # Walk the scale; each new row continues +1 octave of degrees
            absolute_degree = key_i + row_i * n_degrees
            midi = degree_to_midi(base, intervals, absolute_degree)
            if 0 <= midi <= 127:
                mapping[ch] = midi
                mapping[ch.upper()] = midi
    return mapping


def key_to_lookup(key: Key | KeyCode) -> str | None:
    if isinstance(key, KeyCode):
        return _normalize_char(key.char)
    return None


def build_keymap(
    layout: str = LAYOUT_PIANO,
    settings: ScaleSettings | None = None,
) -> dict[str, int]:
    settings = settings or ScaleSettings()
    if layout == LAYOUT_SCALE_ROWS:
        return build_scale_rows_keymap(settings)
    # Piano: Z is always concert Do (C); root only affects snap-to-scale
    return build_piano_keymap(settings.c_midi)


def z_note_label(layout: str, settings: ScaleSettings) -> str:
    """Human label for what Z plays in the current layout."""
    from keychestra.scales import midi_to_name

    km = build_keymap(layout=layout, settings=settings)
    midi = km.get("z")
    if midi is None:
        return "?"
    return midi_to_name(midi)


def resolve_midi(
    keymap: dict[str, int],
    key: Key | KeyCode,
    settings: ScaleSettings | None = None,
    layout: str = LAYOUT_PIANO,
) -> int | None:
    token = key_to_lookup(key)
    if token is None:
        return None
    midi = keymap.get(token)
    if midi is None:
        midi = keymap.get(token.lower())
    if midi is None:
        return None
    # Snap only in piano mode — scale_rows already lands on scale degrees
    if settings is not None and layout == LAYOUT_PIANO:
        return snap_to_scale(midi, settings)
    return midi
