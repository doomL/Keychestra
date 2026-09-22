# OrganBgWorker

### Your keyboard. Still a keyboard. Also a pipe organ.

<p align="center">
  <img alt="OrganBgWorker" src="https://img.shields.io/badge/status-ridiculously%20alive-8B1E1E?style=for-the-badge" />
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img alt="Linux" src="https://img.shields.io/badge/linux-X11-FCC624?style=for-the-badge&logo=linux&logoColor=black" />
  <img alt="License" src="https://img.shields.io/badge/license-MIT-0B7285?style=for-the-badge" />
</p>

<p align="center">
  <b>Type emails. Ship code. Compose accidental masterpieces.</b><br/>
  A background daemon that turns every keypress into real instrument sound —<br/>
  without stealing focus, without blocking typing, without asking permission from your productivity.
</p>

---

## Why does this exist?

Because sometimes you are deep in a terminal, and the universe whispers:

> *what if `Z` was Do, and `S` was Do♯, and Slack was just… accompaniment?*

**OrganBgWorker** is a passive keyboard → MIDI overlay for Linux.  
You keep working. The keys keep typing. And underneath, a SoundFont orchestra answers.

No virtual MIDI cable gymnastics. No “exclusive grab” that breaks your editor.  
Just a tray icon, a daemon, and the quiet joy of writing `git commit` in Mixolydian.

---

## Features that slap

| | |
|---|---|
| **Non-blocking listener** | Observes key events (`pynput`, `suppress=False`). Your apps still get every keystroke. |
| **Real instruments** | FluidSynth + FluidR3 GM SoundFont — piano, organ, strings, sax, choir, pads… |
| **Two layouts** | **Piano** (`Z`=Do, `S`=Do♯…) or **Scale rows** (one scale-octave per keyboard row). |
| **Snap-to-scale** | In piano mode, out-of-scale notes bend to the nearest in-scale pitch. |
| **Tray control center** | Mute, volume, instrument, layout, scale, root, octave — live, no restart. |
| **Always-on** | Run in foreground, daemonize, or install as a systemd user service. |

---

## Layouts

### Piano mode — the classic

```
   2 3   5 6 7   9 0
 Q W E R T Y U I O P
  A S D F G H J K L
   Z X C V B N M
   │
   └── Z = Do (C) · S = Do♯ · X = Re · …
```

Pick a scale (Major, Dorian, Blues, Pentatonic…).  
Press a “wrong” black key → it snaps to the nearest note that belongs.

### Scale rows — jam without fear

```
 q w e r t y u     ← octave +2 of the scale
 a s d f g h j     ← octave +1
 z x c v b n m     ← root octave
```

Every key is already in the scale. One octave per row. Pure dopamine.

---

## Quick start

```bash
git clone https://github.com/doomL/OrganBgWorker.git
cd OrganBgWorker

python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt

# SoundFont + tray (Ubuntu/GNOME)
sudo apt install fluidsynth fluid-soundfont-gm gir1.2-ayatanaappindicator3-0.1

./run.sh
```

Look up. There should be a tiny organ in your system tray.  
Click it. Change instrument to **Church Organ**. Type your name. Cry a little.

### Background / always on

```bash
./run.sh --daemonize

# or systemd user unit
mkdir -p ~/.config/systemd/user
cp organ-bg.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now organ-bg.service
```

---

## Tray menu (the cockpit)

```
Mute / Unmute
Volume ±
────────────
Layout          →  Piano  |  Scale rows
Instrument      →  Piano, Organ, Guitar, Strings, Sax, Pad…
Scale           →  Major, Minor, Modes, Blues, Pentatonic…
Root note       →  C … B
Octave ±
────────────
Quit
```

Hotkeys (configurable in `config.yaml`):

| Combo | Action |
|------:|--------|
| `Ctrl+Shift+O` | Mute toggle |
| `Ctrl+Shift+Q` | Quit |

---

## Architecture (short & honest)

```
┌─────────────┐     observe      ┌──────────────┐
│  Keyboard   │ ───────────────► │   Listener   │  (pynput, passive)
└─────────────┘                  └──────┬───────┘
                                        │ note on/off
                                        ▼
                                 ┌──────────────┐
                                 │  Key → MIDI  │  piano map / scale rows + snap
                                 └──────┬───────┘
                                        │
                                        ▼
                                 ┌──────────────┐
                                 │  FluidSynth  │  FluidR3_GM.sf2
                                 └──────────────┘
                                        │
                                 ┌──────────────┐
                                 │  Tray (GTK)  │  live controls
                                 └──────────────┘
```

Typing path and sound path are independent.  
If audio dies, your keyboard still works. Priorities matter.

---

## Config

See [`config.yaml`](./config.yaml):

```yaml
instrument: piano
layout: piano          # or scale_rows
scale: major
root: C
octave: 3
volume: 0.22
```

Optional SoundFont override:

```yaml
soundfont: /usr/share/sounds/sf2/FluidR3_GM.sf2
```

---

## Requirements

- Linux with **X11** (global listeners are painful on pure Wayland)
- Python 3.10+
- `fluidsynth` + a GM SoundFont (`fluid-soundfont-gm`)
- Tray: AppIndicator / Ayatana (typical on Ubuntu GNOME)

---

## Philosophy

> Productivity tools make you faster.  
> OrganBgWorker makes you *inevitable*.

Built for people who refuse to choose between shipping and vibing.

---

## License

MIT — steal it, fork it, play Bach in your IDE, dedicate it to your rubber duck.

---

<p align="center">
  <i>Made with caffeine, FluidR3, and one too many “wait, what if…” moments.</i>
</p>
