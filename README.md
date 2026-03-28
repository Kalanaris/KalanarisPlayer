# 🎵 Kalanaris' Music Player

A Touhou-inspired desktop music player with a slide-in "Now Playing" overlay, built for streamers in Python/tkinter.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- **Slide-in overlay** — Touhou Mountain of Faith-style popup in any corner of your screen
- **Album art** — shown in both the overlay and the main player card
- **12 themes** — Touhou Gold, Midnight, Sakura, Forest, Crimson, Void, Amber, Ocean, Neon, Sunset, Ice, Lavender
- **Playlists** — create, rename, reorder, and load playlists from your library
- **Global hotkeys** — control playback from inside any game (configurable)
- **System tray** — minimizes to tray, stays out of your taskbar
- **Queue search** — filter your queue by title or artist
- **Drag to reorder** — rearrange songs in the queue by dragging
- **Recent folders** — quickly reopen your last 8 music folders
- **OBS integration** — window capture with chroma key support
- **Formats** — MP3, FLAC, OGG, WAV, M4A, AAC

---

## Running from source

### Requirements

```
pip install pygame-ce mutagen pynput pillow pystray
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

## Download (Windows .exe)

Grab the latest release from the [Releases](../../releases) page — no Python required.

Unzip the folder, run `KalanarisPlayer.exe`. Your playlists and settings are saved in a `KalanarisPlayer/` folder next to the exe.

---

## Building the exe yourself

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

## Data files

| File | Location | Contents |
|---|---|---|
| `settings.json` | `KalanarisPlayer/` | Theme, volume, corner, etc. |
| `playlists.json` | `KalanarisPlayer/` | Your saved playlists |
| `hotkeys.json` | `KalanarisPlayer/` | Custom hotkey bindings |

---

## License

MIT — do whatever you want with it. Credit is nice but not required.
