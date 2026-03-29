# 🎵 Kalanaris' Music Player

A Touhou-inspired desktop music player with a slide-in "Now Playing" overlay, built for streamers in Python/tkinter.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- **Slide-in overlay** — Touhou Mountain of Faith-style popup in any corner of your screen, with animated theme-specific decorations
- **Album art** — shown in both the overlay and the main player card
- **24 themes** — 12 standard themes plus 12 special animated themes: Persona 4 Golden, Persona 3, Persona 5, NieR, Evangelion, Xenoblade 2, Windows Aero, Lo-Fi, Touhou Imperishable Night, Bloodborne, Chrono Trigger, Ultrakill
- **Animated overlays** — special themes have unique live animations: orbiting danmaku bullets, rotating Aegis star, Dark Hour clock hands, NERV scan lines, floating bubbles, falling rain, blood drips, spinning time gate, and more
- **Animated card decorations** — the now-playing card shows theme-specific animated details: kill counter, scan percentage, clock face, NERV/MAGI label, moon phases, etc.
- **Playlists** — create, rename, reorder, and load playlists from your library
- **Favourites** — right-click any song to favourite it; filter the queue to favourites only with one click
- **Global hotkeys** — control playback from inside any game (fully configurable)
- **System tray** — minimizes to tray, stays out of your taskbar
- **Queue search** — filter your queue by title or artist
- **Keyboard navigation** — arrow keys to browse the queue, Enter to play, Space to pause
- **Drag to reorder** — rearrange songs in the queue by dragging
- **Recent folders** — quickly reopen your last 8 music folders
- **Volume normalization** — ReplayGain tag support to even out loud and quiet songs (toggle in Settings)
- **Discord Rich Presence** — shows current song in your Discord status automatically
- **OBS integration** — window capture with chroma key support
- **Formats** — MP3, FLAC, OGG, WAV, M4A, AAC, Opus, WMA, APE, WavPack, TTA, MP2, MIDI

---

## Download (Windows .exe) — Recommended

Grab the latest release from the [Releases](../../releases) page, no Python required.

Unzip the folder, run `KalanarisPlayer.exe`. Your playlists, settings, and favourites are saved next to the exe.

---

## Running from source

### Requirements

```
pip install pygame-ce mutagen pynput pillow pystray
```

Optional (for Discord Rich Presence):

```
pip install pypresence
```

### Run

```bash
python music_overlay.py
```

Or pass a folder directly:

```bash
python music_overlay.py "C:\Users\you\Music"
```

---

## Building the exe yourself

Place `build.py`, `music_overlay.py`, and `icon.ico` in the same folder, then run:

```bash
pip install pyinstaller
python build.py
```

Output goes to `dist/KalanarisPlayer/`. Zip that folder to share.

---

## Default hotkeys

| Action | Hotkey |
|---|---|
| Play / Pause | `Ctrl+Alt+Space` |
| Next Song | `Ctrl+Alt+→` |
| Previous Song | `Ctrl+Alt+←` |
| Toggle Shuffle | `Ctrl+Alt+S` |
| Cycle Repeat | `Ctrl+Alt+R` |
| Show Now Playing | `Ctrl+Alt+P` |
| Add to Playlist | `Ctrl+Alt+A` |

All hotkeys are configurable in ⚙ Settings.

---

## OBS Setup

1. Add a **Window Capture** source → select `[python.exe]: KalanarisOverlay`
2. Add a **Chroma Key** filter → colour `#010203`, similarity 1–5
3. The overlay will appear transparently over your stream

---

## Discord Rich Presence

Install `pypresence` and the current song will automatically show in your Discord status.

```
pip install pypresence
```

---

## Data files

| File | Location | Contents |
|---|---|---|
| `settings.json` | Next to the exe / script | Theme, volume, corner, etc. |
| `playlists.json` | Next to the exe / script | Your saved playlists |
| `hotkeys.json` | Next to the exe / script | Custom hotkey bindings |
| `favourites.json` | Next to the exe / script | Your favourited songs |

---

## License

MIT, so do whatever you want with it. Credit is nice but not required.
