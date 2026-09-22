# Keychestra

### Type. Work. Jam over whatever’s playing.

<p align="center">
  <img alt="Keychestra" src="https://img.shields.io/badge/vibe-enabled-8B1E1E?style=for-the-badge" />
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img alt="Linux" src="https://img.shields.io/badge/linux-X11-FCC624?style=for-the-badge&logo=linux&logoColor=black" />
  <img alt="License" src="https://img.shields.io/badge/license-MIT-0B7285?style=for-the-badge" />
</p>

<p align="center">
  <b>Your keyboard stays a keyboard.<br/>It also becomes the instrument you jam with — over the track in your headphones.</b>
</p>

---

## The use case (aka why this exists)

You’re at work. There’s a track looping. You’re in the zone.

You don’t open a DAW. You don’t grab a MIDI controller.  
You just keep typing — and **Keychestra** lets you *play on top of the music* at the same time.

Emails still send. Code still compiles.  
`Z` is still `z` for your editor — and C for your solo.

> Low volume. Mute in one click when the standup starts.  
> Scales that keep you in key when you’re improvising half-distracted.  
> Real SoundFont instruments, not toy beeps.

**Productivity overlay meets desk jam session.**

---

## What you get

| | |
|---|---|
| **Non-blocking** | Listens passively. Never steals keys from the focused app. |
| **Real timbres** | FluidSynth + FluidR3 GM — piano, organ, guitar, **drums**, strings, sax, choir, pads… |
| **Jam window** | Tray → **Open jam window** and keep it focused — keys play music but don’t type into Slack/Chrome/your editor. |
| **Panic** | Tray → **Panic** or `Ctrl+Shift+P` — kills stuck notes and tremolo. |
| **Space = tremolo** | Hold **Space** while notes ring; intensity/attack from the tray (volume only). |
| **Record notify** | Desktop notification when a session file is saved (and when recording starts). |
| **Session record** | Tray → **Record session** captures *what you hear* (YouTube + Keychestra) into your XDG Music folder (`~/Musica/Keychestra` on Italian desktops). |
| **Settings stick** | Everything you change in the tray is saved to `~/.config/keychestra/config.yaml` (survives quit & reboot). |
| **Two layouts** | **Piano** (`Z`=C fixed, snap to scale) or **Scale rows** (`Z`=root, one scale-octave per row). |
| **Snap-to-scale** | In piano mode, out-of-scale keys bend to the nearest in-key pitch. Perfect for vibing over a track. |
| **Tray cockpit** | Instrument, layout, scale, root, octave, mute, volume — live. |
| **Always on** | Foreground, daemon, or systemd user service. |

---

## Layouts

### Piano — classic desk keyboard (Z = C fixed)

```
   2 3   5 6 7   9 0
 Q W E R T Y U I O P
  A S D F G H J K L
   Z X C V B N M
   │
   └── Z = C always · S = C♯ · X = D · …
```

Root/scale only control **snap-to-scale** (wrong keys bend into the key).  
Want `Z` = root? Use **Scale rows**.

### Scale rows — Z = root

```
 q w e r t y u     ← root +2 octaves
 a s d f g h j     ← root +1 octave
 z x c v b n m     ← root … 7th (e.g. D minor → Z=D)
```

One octave of the scale per row. Every key is safe.  
Ideal when the YouTube tab is carrying the harmony and you’re just adding color.

---

## Playing without typing into other apps

Keychestra listens **globally**, so sound always works.  
Where the *characters* go depends on window focus:

1. Tray → **Open jam window**
2. Click that window (keep it focused)
3. Play — notes sound, Slack/Chrome/your IDE don’t receive the keys

Hold **Space** while notes are ringing for tremolo (volume pulse, not pitch).  
(Space still inserts spaces if another app has focus — that’s why the jam window exists.)

---

## Quick start

```bash
git clone https://github.com/doomL/Keychestra.git
cd Keychestra   # or whatever you named the folder

python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt

sudo apt install fluidsynth fluid-soundfont-gm gir1.2-ayatanaappindicator3-0.1

./run.sh
```

Put a track on. Open the tray. Choose **Scale rows** + a matching scale.  
Type nonsense. Become the third instrument in the room.

### Background

```bash
./run.sh --daemonize

mkdir -p ~/.config/systemd/user
cp keychestra.service ~/.config/systemd/user/
# edit WorkingDirectory / ExecStart if your path differs
systemctl --user daemon-reload
systemctl --user enable --now keychestra.service
```

---

## Tray menu

```
Mute / Unmute
● Record session
Open jam window
Volume & tremolo…  ← real sliders (tray menus can’t host them)
────────────
Layout / Instrument / Scale / Root / Octave
────────────
Quit

**Hold Space** while notes are down → tremolo (volume).
```

| Hotkey | Action |
|-------:|--------|
| `Ctrl+Shift+O` | Mute (boss / meeting mode) |
| `Ctrl+Shift+Q` | Quit |

---

## How it works

```
Keyboard ──observe──► Listener (pynput, passive)
                           │
                           ▼
                     Key → MIDI  (piano map or scale rows + snap)
                           │
                           ▼
                     FluidSynth + FluidR3_GM.sf2
                           │
                     System tray (live controls)
```

Sound and typing are independent paths.  
If audio glitches, your keyboard still works. As it should.

---

## Config

[`config.yaml`](./config.yaml):

```yaml
instrument: piano
layout: piano          # or scale_rows
scale: major
root: C
octave: 3
volume: 0.22           # keep it under the track
```

---

## Requirements

- Linux **X11** (global key listen on pure Wayland is a different beast)
- Python 3.10+
- `fluidsynth` + GM SoundFont (`fluid-soundfont-gm`)
- AppIndicator / Ayatana for the tray (Ubuntu GNOME usually has this)

---

## Name

**Keychestra** = keyboard + orchestra.  
Not an organ-only toy — a whole desk ensemble for people who refuse to choose between shipping and vibing.

---

## License

MIT. Fork it. Jam in Mixolydian during standups. Blame us for the earworms.

---

<p align="center">
  <i>Built for the sacred ritual of “one more track” at 5pm.</i>
</p>
