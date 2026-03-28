#!/usr/bin/env python3
# ┌─────────────────────────────────────────────────────────────┐
# │            Kalanaris' Music Player  —  music_overlay.py     │
# │                                                             │
# │  A Touhou-inspired music player with a slide-in overlay,    │
# │  album art, playlists, themes, global hotkeys, and a        │
# │  system tray icon. Built in Python / tkinter.               │
# │                                                             │
# │  This file is one big 2900-line Python script.              │
# │  I am not proud of this and I am also not sorry.            │
# │  It works, and that's more than I can say for the           │
# │  first three attempts at this.                              │
# └─────────────────────────────────────────────────────────────┘
"""
Kalanaris' Music Player
=======================
A desktop music player with a slide-in "Now Playing" notification
in the bottom-left corner of your screen, inspired by Touhou.

Made by KalanarisMusic, feel free to use and modify!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run this in command prompt (not the one that opens when opening the script,
just the command prompt on it's own):

    pip install pygame-ce mutagen pynput pillow pystray

  • pygame-ce  — audio playback (MP3, FLAC, OGG, WAV)
  • mutagen    — reads tags (title, artist) and album art from files
  • pynput     — global hotkeys that work even when not focused
  • pillow     — scales album art for the overlay
  • pystray    — system tray icon (minimize to tray)

This is for the python script itself, but if ur reading this I probably made it an
executable.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SUPPORTED FORMATS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  MP3, FLAC, OGG, WAV

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 USAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    python music_overlay.py
    python music_overlay.py "C:\\Users\\you\\Music"

The last-used folder and playlist are saved and auto-loaded on next launch.
"""

import os
import sys
import io
import json
import math
import random
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from pathlib import Path

# ── Audio backend ─────────────────────────────────────────────────────────────
# I have tried four different audio libraries.
# pygame crashed on Python 3.14. miniaudio needed a C compiler.
# sounddevice refused to acknowledge MP3s exist
try:
    import pygame
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.mixer.init()
    HAS_PYGAME = True
except Exception as e:
    HAS_PYGAME = False
    print(f'[ERROR] pygame init failed: {e}')
    print('       Install with: pip install pygame-ce')

HAS_MINIAUDIO = False   # not used; pygame-ce handles all formats

# ── Tag / art reading ─────────────────────────────────────────────────────────
# mutagen: reads your MP3 tags so the overlay shows "Prism" instead of
# "02 - track02_final_FINAL_v3_USE THIS ONE.mp3"
# Named after the latin word for 'change', which is appropriate because
# every time I update it something different breaks.
try:
    import mutagen
    from mutagen.id3 import ID3
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False
    print('[WARNING] mutagen not installed — pip install mutagen')

# ── Album art scaling ─────────────────────────────────────────────────────────
# Pillow used for scaling album art.
# If you don't install it, the overlay shows a bouncing ♪ instead.
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print('[INFO] pillow not installed — album art disabled. pip install pillow')

# ── Global hotkeys ────────────────────────────────────────────────────────────
# pynput: intercepts your keypresses globally.
# It is essentially a keylogger that we pinky-promise only uses its power for good. Kind of, maybe, idk
try:
    from pynput import keyboard as pynput_keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False
    print('[WARNING] pynput not installed — global hotkeys disabled. pip install pynput')

# ── System tray ───────────────────────────────────────────────────────────────
# pystray: puts the app in the system tray so it doesn't clutter your taskbar.
# Like a certain white-haired android who quietly disappears after doing their job.
try:
    import pystray
    from pystray import MenuItem as TrayItem
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False
    print('[INFO] pystray not installed — tray icon disabled. pip install pystray')


# ─── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR     = Path(__file__).parent
PLAYLISTS_FILE = SCRIPT_DIR / 'playlists.json'
HOTKEYS_FILE   = SCRIPT_DIR / 'hotkeys.json'
SETTINGS_FILE  = SCRIPT_DIR / 'settings.json'

AUDIO_EXTS = {'.mp3', '.flac', '.ogg', '.wav', '.m4a', '.aac'}


# ─── Settings ─────────────────────────────────────────────────────────────────

def load_settings():
    # Reads settings.json and returns a dict.
    # If the file is corrupted, missing, or somehow contains hieroglyphics,
    # we silently return {} and start fresh.
    try:
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}

def save_settings(data):
    try:
        SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')
    except Exception as e:
        print(f'[ERROR] Could not save settings: {e}')


# ─── Monitor detection ────────────────────────────────────────────────────────

# Windows-only monitor detection using ctypes black magic.
# The ctypes approach requires writing C structs in Python which feels
# It works though. Somehow. DO NOT TOUCH
def get_monitors():
    monitors = []
    try:
        import ctypes
        from ctypes import wintypes

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_ulong, ctypes.c_ulong,
            ctypes.POINTER(wintypes.RECT), ctypes.c_double
        )

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ('cbSize',    ctypes.c_ulong),
                ('rcMonitor', wintypes.RECT),
                ('rcWork',    wintypes.RECT),
                ('dwFlags',   ctypes.c_ulong),
            ]

        def _cb(hMon, _hdc, _lprc, _data):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            ctypes.windll.user32.GetMonitorInfoW(hMon, ctypes.byref(info))
            r, rw = info.rcMonitor, info.rcWork
            monitors.append({
                'x': r.left,  'y': r.top,
                'w': r.right  - r.left, 'h': r.bottom - r.top,
                'wx': rw.left, 'wy': rw.top,
                'ww': rw.right - rw.left, 'wh': rw.bottom - rw.top,
            })
            return True

        ctypes.windll.user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_cb), 0)
    except Exception:
        pass

    if not monitors:
        import tkinter as _tk
        _r = _tk.Tk(); _r.withdraw()
        w, h = _r.winfo_screenwidth(), _r.winfo_screenheight()
        monitors = [{'x':0,'y':0,'w':w,'h':h,'wx':0,'wy':0,'ww':w,'wh':h}]
        _r.destroy()
    return monitors


# ─── Theme system ─────────────────────────────────────────────────────────────

CHROMA_KEY = '#010203'
NOTIF_W    = 430
NOTIF_H    = 92
SCREEN_PAD = 28
ART_SIZE   = 60
ART_PAD    = 10   # padding around album art / note icon from left wall

# All themes. Each defines a complete palette.
# Keys used throughout the UI, change ACTIVE_THEME to switch.
# Some of them look great. Some of them look like the inside of a submarine.
# I'm not telling you which is which. That's for you to discover.
# (It's Void).
THEMES = {
    'Touhou Gold': {
        'bg_deep':   '#0d0618', 'bg_mid':    '#1a0a2e', 'bg_card':   '#150a25',
        'bg_btn':    '#1e0d38', 'bg_active': '#2e1d55', 'bg_list':   '#100520',
        'ov_panel':  '#120820', 'ov_panel2': '#1c0f35',
        'accent':    '#d4a030', 'accent_hi': '#ffcc55',
        'text':      '#f0f0f0', 'text_dim':  '#9988bb', 'text_dim2': '#6655aa',
        'text_list': '#ccbbee', 'separator': '#d4a030',
    },
    'Midnight': {
        'bg_deep':   '#050d1a', 'bg_mid':    '#0a1a30', 'bg_card':   '#0d1f38',
        'bg_btn':    '#0f2444', 'bg_active': '#1a3a66', 'bg_list':   '#081525',
        'ov_panel':  '#060f20', 'ov_panel2': '#0c1c38',
        'accent':    '#2a9fd6', 'accent_hi': '#5bc8f5',
        'text':      '#e8f4ff', 'text_dim':  '#6a9fbf', 'text_dim2': '#4a7a9b',
        'text_list': '#a0c8e8', 'separator': '#2a9fd6',
    },
    'Sakura': {
        'bg_deep':   '#1a0a12', 'bg_mid':    '#2e1020', 'bg_card':   '#261018',
        'bg_btn':    '#3a1428', 'bg_active': '#5a2040', 'bg_list':   '#1e0c18',
        'ov_panel':  '#180810', 'ov_panel2': '#2a1020',
        'accent':    '#d4607a', 'accent_hi': '#ff9eb5',
        'text':      '#ffe8f0', 'text_dim':  '#b87a8a', 'text_dim2': '#8a5060',
        'text_list': '#e0aaba', 'separator': '#d4607a',
    },
    'Forest': {
        'bg_deep':   '#050f08', 'bg_mid':    '#0a1e10', 'bg_card':   '#0c1e12',
        'bg_btn':    '#102818', 'bg_active': '#1a4228', 'bg_list':   '#081408',
        'ov_panel':  '#060e08', 'ov_panel2': '#0e2014',
        'accent':    '#3aad5a', 'accent_hi': '#6ddf8a',
        'text':      '#e8ffe0', 'text_dim':  '#6aaf7a', 'text_dim2': '#4a8058',
        'text_list': '#a0d8b0', 'separator': '#3aad5a',
    },
    'Crimson': {
        'bg_deep':   '#120505', 'bg_mid':    '#220808', 'bg_card':   '#1e0808',
        'bg_btn':    '#300a0a', 'bg_active': '#501010', 'bg_list':   '#180505',
        'ov_panel':  '#100404', 'ov_panel2': '#200808',
        'accent':    '#cc2020', 'accent_hi': '#ff5555',
        'text':      '#ffe8e8', 'text_dim':  '#b06060', 'text_dim2': '#804040',
        'text_list': '#d8a0a0', 'separator': '#cc2020',
    },
    'Void': {
        'bg_deep':   '#080808', 'bg_mid':    '#121212', 'bg_card':   '#111111',
        'bg_btn':    '#1c1c1c', 'bg_active': '#303030', 'bg_list':   '#0e0e0e',
        'ov_panel':  '#060606', 'ov_panel2': '#101010',
        'accent':    '#888888', 'accent_hi': '#dddddd',
        'text':      '#f0f0f0', 'text_dim':  '#777777', 'text_dim2': '#555555',
        'text_list': '#aaaaaa', 'separator': '#444444',
    },
    'Amber': {
        'bg_deep':   '#0f0a02', 'bg_mid':    '#1e1404', 'bg_card':   '#1a1204',
        'bg_btn':    '#281a06', 'bg_active': '#40280a', 'bg_list':   '#140e02',
        'ov_panel':  '#0c0802', 'ov_panel2': '#1c1204',
        'accent':    '#c07820', 'accent_hi': '#f0a840',
        'text':      '#fff5e0', 'text_dim':  '#a07840', 'text_dim2': '#7a5828',
        'text_list': '#d4b078', 'separator': '#c07820',
    },
    'Ocean': {
        'bg_deep':   '#030d10', 'bg_mid':    '#051820', 'bg_card':   '#06181e',
        'bg_btn':    '#082028', 'bg_active': '#103040', 'bg_list':   '#040e14',
        'ov_panel':  '#030c10', 'ov_panel2': '#071820',
        'accent':    '#20a8b8', 'accent_hi': '#50d8e8',
        'text':      '#e0f8ff', 'text_dim':  '#5a9aaa', 'text_dim2': '#3a7080',
        'text_list': '#90d0e0', 'separator': '#20a8b8',
    },
    'Neon': {
        'bg_deep':   '#040404', 'bg_mid':    '#0a0f0a', 'bg_card':   '#090e09',
        'bg_btn':    '#0e160e', 'bg_active': '#162016', 'bg_list':   '#060a06',
        'ov_panel':  '#030503', 'ov_panel2': '#080e08',
        'accent':    '#00cc44', 'accent_hi': '#44ff88',
        'text':      '#e8ffe8', 'text_dim':  '#44aa66', 'text_dim2': '#2a7744',
        'text_list': '#88dd99', 'separator': '#00cc44',
    },
    'Sunset': {
        'bg_deep':   '#0f0610', 'bg_mid':    '#200a18', 'bg_card':   '#1c0a14',
        'bg_btn':    '#2e1020', 'bg_active': '#4a1830', 'bg_list':   '#180810',
        'ov_panel':  '#0e0510', 'ov_panel2': '#1e0918',
        'accent':    '#cc5520', 'accent_hi': '#ff8844',
        'text':      '#fff0e0', 'text_dim':  '#aa6644', 'text_dim2': '#7a4430',
        'text_list': '#d8a080', 'separator': '#cc5520',
    },
    'Ice': {
        'bg_deep':   '#060c14', 'bg_mid':    '#0e1a28', 'bg_card':   '#0c1820',
        'bg_btn':    '#122030', 'bg_active': '#1e3248', 'bg_list':   '#080e18',
        'ov_panel':  '#050a10', 'ov_panel2': '#0c1820',
        'accent':    '#80c8e8', 'accent_hi': '#b8e8ff',
        'text':      '#eef8ff', 'text_dim':  '#6090b0', 'text_dim2': '#406880',
        'text_list': '#98c8e0', 'separator': '#80c8e8',
    },
    'Lavender': {
        'bg_deep':   '#0c0c14', 'bg_mid':    '#181820', 'bg_card':   '#14141e',
        'bg_btn':    '#20202e', 'bg_active': '#303048', 'bg_list':   '#101018',
        'ov_panel':  '#0a0a12', 'ov_panel2': '#161620',
        'accent':    '#9070d0', 'accent_hi': '#c0a0ff',
        'text':      '#f0eeff', 'text_dim':  '#8878aa', 'text_dim2': '#605878',
        'text_list': '#c0b0e0', 'separator': '#9070d0',
    },
}

# Active theme palette — mutable dict, updated by apply_theme()
T = dict(THEMES['Touhou Gold'])

# Derive convenience aliases that the rest of the code uses
def _sync_globals():
    global PANEL_BG, PANEL_BG2, BORDER_GOLD, TEXT_WHITE, TEXT_GOLD, TEXT_DIM
    PANEL_BG    = T['ov_panel']
    PANEL_BG2   = T['ov_panel2']
    BORDER_GOLD = T['accent']
    TEXT_WHITE  = T['text']
    TEXT_GOLD   = T['accent_hi']
    TEXT_DIM    = T['text_dim']

_sync_globals()

def _make_btn_dicts():
    global BTN, BTN_ICON, BTN_SM
    BTN = dict(
        bg=T['bg_btn'], fg=T['accent_hi'],
        activebackground=T['bg_active'], activeforeground=T['text'],
        relief='flat', bd=0, cursor='hand2',
        font=('Segoe UI', 10), padx=10, pady=5
    )
    BTN_ICON = dict(
        bg=T['bg_btn'], fg=T['text'],
        activebackground=T['bg_active'], activeforeground=T['accent_hi'],
        relief='flat', bd=0, cursor='hand2',
        font=('Segoe UI', 18), padx=12, pady=6
    )
    BTN_SM = dict(
        bg=T['bg_btn'], fg=T['accent_hi'],
        activebackground=T['bg_active'], activeforeground=T['text'],
        relief='flat', bd=0, cursor='hand2',
        font=('Segoe UI', 9), padx=8, pady=4
    )

_make_btn_dicts()
BTN = BTN; BTN_ICON = BTN_ICON; BTN_SM = BTN_SM  # forward-declare for clarity

ACTIVE_THEME_NAME = 'Touhou Gold'


def _pick_script_font(size):
    """Pick the best available handwritten/script font for the header.
    Priority: Segoe Script (Win Vista+ Messenger era) → Segoe Print →
    Lucida Handwriting → Mistral → Comic Sans MS → fallback bold.
    All very 2009 which is what im trying to evoke."""
    candidates = [
        'Mistral',
        'Segoe Script',
        'Segoe Print',
        'Lucida Handwriting',
        'Comic Sans MS',
    ]
    try:
        import tkinter.font as tkfont
        available = set(tkfont.families())
        for name in candidates:
            if name in available:
                return (name, size)
    except Exception:
        pass
    return ('Segoe UI', size, 'bold')


# This function generates a 128x128 noise tile and pastes it across the UI.
# Is it efficient? No.
# Does it look cool? Marginally.
# Did I spend 45 minutes on this instead of fixing the seek bug? Yes.
# The seek bug is still there. (It's fixed now. But the spirit of the comment remains.)
def _make_noise_image(w, h, hex_color, grain=14):
    """Return a Pillow ImageTk.PhotoImage with subtle grain over hex_color.
    Generates a 128x128 tile then tiles it up — fast even at full window size."""
    if not HAS_PIL or w <= 0 or h <= 0:
        return None
    try:
        r0 = int(hex_color[1:3], 16)
        g0 = int(hex_color[3:5], 16)
        b0 = int(hex_color[5:7], 16)
        tile_sz = 128
        tile = Image.new('RGB', (tile_sz, tile_sz))
        px   = tile.load()
        for y in range(tile_sz):
            for x in range(tile_sz):
                n = random.randint(-grain, grain)
                px[x, y] = (
                    max(0, min(255, r0 + n)),
                    max(0, min(255, g0 + n)),
                    max(0, min(255, b0 + n)),
                )
        full = Image.new('RGB', (w, h))
        for ty in range(0, h, tile_sz):
            for tx in range(0, w, tile_sz):
                full.paste(tile, (tx, ty))
        return ImageTk.PhotoImage(full)
    except Exception as e:
        print(f'[WARNING] Texture generation failed: {e}')
        return None


def apply_theme(name, root=None):
    """Switch to a named theme, recolor all live widgets, redraw overlay."""
    global ACTIVE_THEME_NAME
    if name not in THEMES:
        return
    old_t = dict(T)
    T.update(THEMES[name])
    ACTIVE_THEME_NAME = name
    _sync_globals()
    _make_btn_dicts()
    if root:
        _recolor_all(root, old_t, T)


def _recolor_all(widget, old, new):
    """Walk every widget and swap old theme colors for new ones.
    
    This works by mapping hex colors from the old theme to the new one.
    If any widget has a color that isn't in the theme palette (e.g. hardcoded somewhere
    I forgot about), it just doesn't change.
    """
    # Build a reverse mapping: old_hex -> new_hex for every palette key
    mapping = {}
    for k in old:
        if old[k] != new[k]:
            mapping[old[k].lower()] = new[k]

    _recolor_widget(widget, mapping)


def _recolor_widget(widget, mapping):
    KEYS = ('bg', 'fg', 'activebackground', 'activeforeground',
            'selectbackground', 'selectforeground', 'troughcolor',
            'insertbackground', 'highlightbackground', 'highlightcolor')
    for key in KEYS:
        try:
            val = widget.cget(key)
            if isinstance(val, str):
                low = val.lower()
                if low in mapping:
                    widget.configure(**{key: mapping[low]})
        except Exception:
            pass
    try:
        for child in widget.winfo_children():
            _recolor_widget(child, mapping)
    except Exception:
        pass


# ─── Song ─────────────────────────────────────────────────────────────────────

# ─── Song ─────────────────────────────────────────────────────────────────────
# Represents a single audio file. Reads its tags on construction.
# If mutagen isn't installed, everything is "Unknown Artist" and the filename.
# Which honestly is still better than what Winamp used to do.
class Song:
    def __init__(self, path):
        self.path     = path
        self.title    = Path(path).stem   # fallback if tags fail
        self.artist   = 'Unknown Artist'
        self.album    = ''
        self.duration = 0.0
        self.art_data = None   # raw bytes of embedded album art

        if HAS_MUTAGEN:
            self._load_tags()

    def _load_tags(self):
        # Reads ID3/FLAC/OGG/M4A tags from the file.
        # Each format stores metadata slightly differently because the audio
        # industry has never met a standard it didn't immediately fragment.
        # MP3 uses ID3. FLAC uses Vorbis comments. M4A uses iTunes atoms.
        # They all mean "title" and "artist". They are all different keys.
        # Truly, the Tower of Babel was an audio format committee.
        ext = Path(self.path).suffix.lower()
        try:
            if ext == '.mp3':
                tags = ID3(self.path)
                t  = tags.get('TIT2'); a = tags.get('TPE1'); al = tags.get('TALB')
                if t:  self.title  = str(t).strip()
                if a:  self.artist = str(a).strip()
                if al: self.album  = str(al).strip()
                # Album art
                for key in tags.keys():
                    if key.startswith('APIC'):
                        self.art_data = tags[key].data; break
                try: self.duration = MP3(self.path).info.length
                except Exception: pass

            elif ext == '.flac':
                audio = FLAC(self.path)
                t  = audio.get('title');  a = audio.get('artist'); al = audio.get('album')
                if t:  self.title  = t[0]
                if a:  self.artist = a[0]
                if al: self.album  = al[0]
                if audio.pictures:
                    self.art_data = audio.pictures[0].data
                try: self.duration = audio.info.length
                except Exception: pass

            elif ext in ('.ogg', '.opus'):
                audio = OggVorbis(self.path)
                t  = audio.get('title');  a = audio.get('artist'); al = audio.get('album')
                if t:  self.title  = t[0]
                if a:  self.artist = a[0]
                if al: self.album  = al[0]
                try: self.duration = audio.info.length
                except Exception: pass

            elif ext in ('.m4a', '.aac'):
                try:
                    af = mutagen.File(self.path)
                    if af:
                        t  = af.get('\xa9nam') or af.get('title')
                        a  = af.get('\xa9ART') or af.get('artist')
                        al = af.get('\xa9alb') or af.get('album')
                        if t:  self.title  = t[0] if isinstance(t, list) else str(t)
                        if a:  self.artist = a[0] if isinstance(a, list) else str(a)
                        if al: self.album  = al[0] if isinstance(al, list) else str(al)
                        # Album art in M4A
                        covr = af.get('covr')
                        if covr: self.art_data = bytes(covr[0])
                        if af.info: self.duration = af.info.length
                except Exception: pass

            elif ext == '.wav':
                try:
                    af = mutagen.File(self.path)
                    if af and af.info: self.duration = af.info.length
                except Exception: pass

        except Exception:
            pass

    def fmt_duration(self):
        m, s = divmod(int(self.duration), 60)
        return f'{m}:{s:02d}'

    def fmt_pos(self, seconds):
        m, s = divmod(int(max(0, seconds)), 60)
        return f'{m}:{s:02d}'

    def list_label(self):
        dur = f'  [{self.fmt_duration()}]' if self.duration > 0 else ''
        return f'  {self.title}  —  {self.artist}{dur}'


# Recursively walks your entire music folder.
# If you point this at C:\\ it will find every MP3 on your computer.
# Don't do that. Unless you want a 40,000 song queue.
# (That would be kind of incredible actually but you wouldnt like the load times)
def find_audio_files(folder):
    result = []
    for root, _, files in os.walk(folder):
        for f in files:
            if Path(f).suffix.lower() in AUDIO_EXTS:
                result.append(os.path.join(root, f))
    result.sort()
    return result


# ─── PlaylistStore ────────────────────────────────────────────────────────────

# PlaylistStore: saves your curated vibes to playlists.json.
# It's a JSON dict. There are no migrations. 
# ─── PlaylistStore ────────────────────────────────────────────────────────────
# Stores playlists as a simple JSON dict: { "Playlist Name": ["/path/to/song", ...] }
# No database, Just a JSON file.
# If you delete it, your playlists are gone. Back it up. I'm not your dad.
# (But seriously, back it up. I've lost a playlist it was really annoying I had ALOT there)
class PlaylistStore:
    def __init__(self):
        self._data = {}
        self._load()

    def _load(self):
        if PLAYLISTS_FILE.exists():
            try:
                with open(PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except Exception as e:
                print(f'[WARNING] Could not load playlists: {e}')

    def save(self):
        try:
            with open(PLAYLISTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f'[ERROR] Could not save playlists: {e}')

    def names(self):           return list(self._data.keys())
    def get_paths(self, name): return list(self._data.get(name, []))

    def create(self, name):
        if name not in self._data: self._data[name] = []; self.save()

    def delete(self, name):
        self._data.pop(name, None); self.save()

    def rename(self, old, new):
        if old in self._data and new not in self._data:
            self._data[new] = self._data.pop(old); self.save()

    def set_paths(self, name, paths):
        self._data[name] = paths; self.save()

    def add_path(self, name, path):
        if name in self._data and path not in self._data[name]:
            self._data[name].append(path); self.save()

    def remove_path(self, name, path):
        if name in self._data:
            try: self._data[name].remove(path); self.save()
            except ValueError: pass


# ─── HotkeyManager ────────────────────────────────────────────────────────────

DEFAULT_HOTKEYS = {
    'play_pause':        '<ctrl>+<alt>+<space>',
    'next':              '<ctrl>+<alt>+<right>',
    'prev':              '<ctrl>+<alt>+<left>',
    'add_to_playlist':   '<ctrl>+<alt>+a',
    'shuffle':           '<ctrl>+<alt>+s',
    'repeat':            '<ctrl>+<alt>+r',
    'preview':           '<ctrl>+<alt>+p',
}
HOTKEY_LABELS = {
    'play_pause':        'Play / Pause',
    'next':              'Next Song',
    'prev':              'Previous Song',
    'add_to_playlist':   'Add to Playlist',
    'shuffle':           'Toggle Shuffle',
    'repeat':            'Cycle Repeat Mode',
    'preview':           'Show Now Playing',
}


# HotkeyManager: lets you control the music from inside a game.
# Uses pynput to intercept keypresses globally, which means this code
# is running even when you're in the middle of game I believe.
# Ctrl+Alt+Space will pause your music mid-cutscene.
# I accept no responsibility for this.
class HotkeyManager:
    def __init__(self, player):
        self.player              = player
        self.bindings            = self._load()
        self._listener           = None
        self.on_add_to_playlist  = None   # set by ControlPanel after init
        self.on_shuffle          = None
        self.on_repeat           = None
        self.on_preview          = None
        self.start()

    def _load(self):
        if HOTKEYS_FILE.exists():
            try:
                saved = json.loads(HOTKEYS_FILE.read_text(encoding='utf-8'))
                return {k: saved.get(k, v) for k, v in DEFAULT_HOTKEYS.items()}
            except Exception:
                pass
        return DEFAULT_HOTKEYS.copy()

    def save(self):
        try:
            HOTKEYS_FILE.write_text(json.dumps(self.bindings, indent=2), encoding='utf-8')
        except Exception as e:
            print(f'[ERROR] Could not save hotkeys: {e}')

    def start(self):
        if not HAS_PYNPUT: return
        self.stop()
        actions = {
            'play_pause':      self.player.toggle_pause,
            'next':            self.player.next_song,
            'prev':            self.player.prev_song,
            'add_to_playlist': self.on_add_to_playlist,
            'shuffle':         self.on_shuffle,
            'repeat':          self.on_repeat,
            'preview':         self.on_preview,
        }
        # Only register bindings that have a non-None action
        hotkey_map = {
            self.bindings[k]: actions[k]
            for k in self.bindings
            if k in actions and actions[k] is not None
        }
        try:
            self._listener = pynput_keyboard.GlobalHotKeys(hotkey_map)
            self._listener.start()
        except Exception as e:
            print(f'[WARNING] Global hotkeys failed: {e}')

    def stop(self):
        if self._listener:
            try: self._listener.stop()
            except Exception: pass
            self._listener = None

    def update(self, new_bindings):
        self.bindings = new_bindings
        self.save()
        self.start()


# ─── Overlay Window ───────────────────────────────────────────────────────────

# Corner constants
CORNERS = ['bottom-left', 'bottom-right', 'top-left', 'top-right']
CORNER_LABELS = {
    'bottom-left':  '↙ Bot-Left',
    'bottom-right': '↘ Bot-Right',
    'top-left':     '↖ Top-Left',
    'top-right':    '↗ Top-Right',
}


# The overlay. The whole reason this project exists.
# A small window in the corner of your screen that tells you what's playing.
# Inspired by Touhou Mountain of Faith's now-playing UI.
# Does it need scanlines, grain, album art, and corner diamonds? No.
# Did I add them anyway? Yes, and I'd do it again. !!!!
# ─── Overlay Window ──────────────────────────────────────────────────────────
# This is the whole reason the app exists basically. A small Touhou-style notification
# that slides in from the corner of the screen when a song changes.
# It runs its own 60fps draw loop (self._loop) completely independently
# of the main window. This is either elegant architecture or a terrible idea.
# I choose to believe it's elegant.
class NowPlayingOverlay:
    def __init__(self, master):
        self.monitors    = get_monitors()
        self.monitor_idx = 0
        self.corner      = 'bottom-left'   # default

        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.wm_attributes('-topmost', True)
        self.win.configure(bg=CHROMA_KEY)
        self.win.title('KalanarisOverlay')

        try:
            self.win.wm_attributes('-transparentcolor', CHROMA_KEY)
        except tk.TclError:
            pass

        self._win_w = NOTIF_W + 20
        self._win_h = NOTIF_H + 20

        self.canvas = tk.Canvas(
            self.win, width=self._win_w, height=self._win_h,
            bg=CHROMA_KEY, highlightthickness=0
        )
        self.canvas.pack()

        self.x_shown  = 0.0
        self.x_hidden = float(-NOTIF_W - 20)
        self.cur_x    = self.x_hidden
        self.phase    = 'idle'
        self.song     = None
        self.tick     = 0
        self._hold_job      = None
        self._art_photo     = None   # keep reference to prevent GC
        self.show_texture   = True   # toggleable from Settings
        self.hold_ms        = 5500   # how long the popup stays visible (ms)
        self.auto_show      = True   # show popup automatically on song change
        self.player_ref     = None   # set by ControlPanel so _draw can read position

        self._reposition()
        self._loop()

    def _reposition(self):
        m = self.monitors[self.monitor_idx]
        c = self.corner
        if c == 'bottom-left':
            win_x = m['x']  + SCREEN_PAD
            win_y = m['wy'] + m['wh'] - self._win_h - SCREEN_PAD
        elif c == 'bottom-right':
            win_x = m['x']  + m['w']  - self._win_w - SCREEN_PAD
            win_y = m['wy'] + m['wh'] - self._win_h - SCREEN_PAD
        elif c == 'top-left':
            win_x = m['x']  + SCREEN_PAD
            win_y = m['wy'] + SCREEN_PAD
        else:  # top-right
            win_x = m['x']  + m['w']  - self._win_w - SCREEN_PAD
            win_y = m['wy'] + SCREEN_PAD
        self.win.geometry(f'{self._win_w}x{self._win_h}+{win_x}+{win_y}')

    def set_monitor(self, idx):
        self.monitor_idx = idx % len(self.monitors)
        self._reposition()

    def set_corner(self, corner):
        self.corner = corner
        self._reposition()

    def show(self, song):
        self.song  = song
        self.phase = 'slide_in'
        # For right-side corners, slide in from the right
        if self.corner in ('bottom-right', 'top-right'):
            self.x_shown  = 0.0
            self.x_hidden = float(NOTIF_W + 20)
        else:
            self.x_shown  = 0.0
            self.x_hidden = float(-NOTIF_W - 20)
        self.cur_x = self.x_hidden
        if self._hold_job:
            self.win.after_cancel(self._hold_job)
            self._hold_job = None
        # Pre-render album art
        self._art_photo = self._make_art(song)

    def _make_art(self, song):
        if not HAS_PIL or not song or not song.art_data:
            return None
        try:
            img = Image.open(io.BytesIO(song.art_data))
            img = img.convert('RGB').resize((ART_SIZE, ART_SIZE), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _loop(self):
        self.tick += 1
        self.canvas.delete('n')

        if self.phase == 'slide_in':
            self.cur_x += (self.x_shown - self.cur_x) * 0.17
            if abs(self.cur_x - self.x_shown) < 0.8:
                self.cur_x = self.x_shown
                self.phase = 'hold'
                self._hold_job = self.win.after(self.hold_ms, self._start_slide_out)
            self._draw()
        elif self.phase == 'hold':
            self._draw()
        elif self.phase == 'slide_out':
            self.cur_x += (self.x_hidden - self.cur_x) * 0.13
            if abs(self.cur_x - self.x_hidden) < 0.8:
                self.cur_x = self.x_hidden
                self.phase = 'idle'
            self._draw()

        self.win.after(16, self._loop)

    def _start_slide_out(self):
        if self.phase == 'hold':
            self.phase = 'slide_out'

    def _draw(self):
        # ┌──────────────────────────────────────────────────────────┐
        # │  DRAW LOOP — runs at ~60fps via root.after(16, _loop)    │
        # │                                                          │
        # │  Draw order (painter's algorithm, back to front):        │
        # │    1. Shadow (offset rectangle, stipple)                 │
        # │    2. Main panel background                              │
        # │    3. Header strip                                       │
        # │    4. Art zone background                                │
        # │    5. Album art OR bouncing ♪ note                       │
        # │    6. Divider line                                       │
        # │    7. Text (NOW PLAYING, title, artist, duration)        │
        # │    8. Scanlines + grain (if texture enabled)             │
        # │    9. Progress bar                                       │
        # │   10. Corner diamonds                                    │
        # └──────────────────────────────────────────────────────────┘
        # Called 60 times per second. Every. Single. Second.
        # If this function is slow, the whole overlay stutters.
        # I have not profiled it. I am living in ignorance
        # The scanlines alone draw ~28 lines per frame.
        c, tag = self.canvas, 'n'
        x, y   = int(self.cur_x), 5
        w, h, t = NOTIF_W, NOTIF_H, self.tick

        # Shadow
        c.create_rectangle(x+5, y+5, x+w+5, y+h+5,
            fill='#000000', outline='', stipple='gray50', tags=tag)

        # Main panel
        c.create_rectangle(x, y, x+w, y+h,
            fill=PANEL_BG, outline=BORDER_GOLD, width=2, tags=tag)
        c.create_rectangle(x+2, y+2, x+w-2, y+30,
            fill=PANEL_BG2, outline='', tags=tag)

        # Left art section background — ART_PAD breathing room from border
        art_zone_w = ART_PAD + ART_SIZE + ART_PAD
        c.create_rectangle(x+2, y+2, x+art_zone_w+2, y+h-2,
            fill=PANEL_BG2, outline='', tags=tag)

        # Album art or bouncing ♪ — centred within the art zone with padding
        if self._art_photo:
            art_x = x + ART_PAD + 2
            art_y = y + (h - ART_SIZE) // 2
            c.create_image(art_x, art_y, image=self._art_photo, anchor='nw', tags=tag)
        else:
            note_offset = int(math.sin(t * 0.07) * 2.5)
            nx = x + ART_PAD + 2 + ART_SIZE // 2
            ny = y + h // 2 + note_offset
            c.create_text(nx+1, ny+1, text='♪', fill='#000000',
                          font=('Arial', 28, 'bold'), tags=tag)
            c.create_text(nx, ny,   text='♪', fill=TEXT_GOLD,
                          font=('Arial', 28, 'bold'), tags=tag)

        # Divider
        div_x = x + art_zone_w + 4
        c.create_line(div_x, y+14, div_x, y+h-14,
                      fill=BORDER_GOLD, width=1, tags=tag)

        # Text
        if self.song:
            tx = div_x + 10
            title  = self._trunc(self.song.title,  30)
            artist = self._trunc(self.song.artist, 38)
            dur    = self.song.fmt_duration() if self.song.duration > 0 else ''

            c.create_text(tx, y+18, text='NOW PLAYING',
                fill=TEXT_DIM, font=('Courier New', 8, 'bold'), anchor='w', tags=tag)
            if dur:
                c.create_text(x+w-28, y+18, text=dur,
                    fill=TEXT_DIM, font=('Courier New', 8), anchor='e', tags=tag)
            c.create_text(tx+1, y+42, text=title,
                fill=TEXT_WHITE, font=('Segoe UI', 13, 'bold'), anchor='w', tags=tag)
            c.create_text(tx+1, y+65, text=artist,
                fill=TEXT_GOLD, font=('Segoe UI', 10), anchor='w', tags=tag)

        # Scanlines + grain — only when texture is enabled
        if self.show_texture:
            for ly in range(y+2, y+h-2, 3):
                c.create_line(x+2, ly, x+w-2, ly,
                    fill='#000000', stipple='gray25', tags=tag)
            rng = random.Random(t // 4)
            for _ in range(22):
                gx = x + rng.randint(2, w-2)
                gy = y + rng.randint(2, h-2)
                brightness = rng.choice(['#ffffff', BORDER_GOLD, PANEL_BG2])
                c.create_rectangle(gx, gy, gx+1, gy+1,
                    fill=brightness, outline='', stipple='gray50', tags=tag)

        # Progress bar — thin gold line at bottom of popup
        if self.player_ref and self.song and self.song.duration > 0:
            try:
                pos = self.player_ref.get_position()
                frac = max(0.0, min(1.0, pos / self.song.duration))
                bar_w = int((w - 4) * frac)
                if bar_w > 0:
                    # Background track
                    c.create_rectangle(x+2, y+h-5, x+w-2, y+h-2,
                        fill=PANEL_BG2, outline='', tags=tag)
                    # Filled portion
                    c.create_rectangle(x+2, y+h-5, x+2+bar_w, y+h-2,
                        fill=BORDER_GOLD, outline='', tags=tag)
            except Exception:
                pass

        # Corner diamonds
        self._diamond(c, x+w-12, y+12, tag)
        self._diamond(c, x+w-12, y+h-12, tag)

    def _diamond(self, c, cx, cy, tag, r=4):
        c.create_polygon(cx, cy-r, cx+r, cy, cx, cy+r, cx-r, cy,
                         fill=BORDER_GOLD, outline='', tags=tag)

    @staticmethod
    def _trunc(s, n):
        return s if len(s) <= n else s[:n-1] + '…'


# ─── Player ───────────────────────────────────────────────────────────────────

REPEAT_MODES = ['all', 'one', 'none']
REPEAT_LABELS = {
    'all':  '🔁  Repeat: All',
    'one':  '🔂  Repeat: One',
    'none': '➡  Repeat: Off',
}


# At various points this class has caused: audio gaps, phantom song advances,
# the seek bar lying about position, and one incident where it played
# the same 3 seconds of Gaur Plain on loop for like 20 minutes EVEN WHEN CLOSED
class Player:
    # The beating heart of the whole operation.
    # self.songs is the full list of Song objects.
    # self.queue is a list of INDICES into self.songs (shuffled or not).
    # self.q_pos is where we are in the queue.
    # This design means shuffling is free — just shuffle the index list,
    # the actual Song objects never move. Very elegant. I am proud of this one.
    # (There are maybe three things in this file I'm proud of. This is one.)
    def __init__(self):
        self.songs    = []
        self.queue    = []   # indices into self.songs
        self.q_pos    = 0
        self.playing  = False
        self.paused   = False
        self.shuffled = True
        self.repeat   = 'all'
        self._lock    = threading.Lock()

        self.on_song_change  = None
        self.on_state_change = None

        self._seek_offset = 0.0   # seconds seeked to on last play(start=)
        self._pause_pos   = 0.0   # position snapshotted when pausing

        if HAS_PYGAME:
            threading.Thread(target=self._pygame_watchdog, daemon=True).start()

    # ── Library loading ───────────────────────────────────────────────────────

    def load_folder(self, folder):
        paths = find_audio_files(folder)
        if not paths:
            return False
        self.songs = [Song(p) for p in paths]
        self._reset_queue_and_play()
        return True

    def load_song_list(self, songs):
        if not songs:
            return False
        self.songs = songs
        self._reset_queue_and_play()
        return True

    def _reset_queue_and_play(self):
        self.queue = list(range(len(self.songs)))
        if self.shuffled:
            random.shuffle(self.queue)
        self.q_pos = 0
        self._play_current()

    def _rebuild_queue(self):
        self.queue = list(range(len(self.songs)))
        if self.shuffled:
            random.shuffle(self.queue)

    # ── Playback ──────────────────────────────────────────────────────────────

    def _play_current(self):
        if not self.queue or not HAS_PYGAME:
            return
        idx  = self.queue[self.q_pos % len(self.queue)]
        song = self.songs[idx]
        try:
            pygame.mixer.music.load(song.path)
            pygame.mixer.music.play()
        except Exception as e:
            print(f'[ERROR] Cannot play {song.path}: {e}')
            self._advance(+1)
            return
        self._seek_offset = 0.0
        self.playing = True
        self.paused  = False
        if self.on_song_change:  self.on_song_change(song)
        if self.on_state_change: self.on_state_change(True, False)

    def next_song(self):  self._advance(+1)
    def prev_song(self):  self._advance(-1)

    def play_by_song_index(self, idx):
        try:
            q_idx = self.queue.index(idx)
            self.q_pos = q_idx
            self._play_current()
        except ValueError:
            pass

    def toggle_pause(self):
        # Pause or unpause. Simple in concept, surprisingly fragile in practice.
        # We snapshot position before pausing because pygame's get_pos() returns
        # 0 while paused, which would snap the progress bar to the start.
        # This caused a week of confusion. The fix is one line. lowkey I hate coding sometimes.
        if not self.songs or not HAS_PYGAME:
            return
        if self.paused:
            pygame.mixer.music.unpause()
            self.paused  = False
            self.playing = True
        else:
            self._pause_pos = self.get_position()   # snapshot position before pausing
            pygame.mixer.music.pause()
            self.paused  = True
        if self.on_state_change:
            self.on_state_change(self.playing, self.paused)

    def seek(self, seconds):
        """Seek to absolute position. Reloads + play(start=) for accuracy.
        
        Fun history: the first seek implementation used set_pos().
        set_pos() in pygame measures from the CURRENT decoder position, not absolute.
        So every seek drifted further and further into the wrong place.
        This version reloads the whole file. It's slower but it's correct.
        """
        if not self.queue or not HAS_PYGAME:
            return
        song = self.current_song()
        if not song:
            return
        was_paused = self.paused
        try:
            pygame.mixer.music.load(song.path)
            pygame.mixer.music.play(start=float(seconds))
            self._seek_offset = seconds
            self.playing = True
            self.paused  = False
            if was_paused:
                pygame.mixer.music.pause()
                self.paused = True
        except Exception as e:
            print(f'[WARNING] Seek failed: {e}')

    def get_position(self):
        # Returns elapsed seconds. Sounds simple.
        # Is simple. Was NOT simple before we tracked _pause_pos.
        # Previously, pausing returned 0 and the bar snapped to the start.
        if not HAS_PYGAME:
            return 0.0
        if self.paused:
            return self._pause_pos
        if not self.playing:
            return 0.0
        ms = pygame.mixer.music.get_pos()
        if ms < 0: return 0.0
        return self._seek_offset + ms / 1000.0

    def cycle_repeat(self):
        idx = REPEAT_MODES.index(self.repeat)
        self.repeat = REPEAT_MODES[(idx + 1) % len(REPEAT_MODES)]

    def toggle_shuffle(self):
        self.shuffled = not self.shuffled
        if not self.songs:
            return
        cur = self.queue[self.q_pos % len(self.queue)] if self.queue else 0
        self._rebuild_queue()
        try:    self.q_pos = self.queue.index(cur)
        except: self.q_pos = 0

    def set_volume(self, v):
        if HAS_PYGAME:
            pygame.mixer.music.set_volume(max(0.0, min(1.0, v)))

    def current_song(self):
        if not self.queue or not self.songs:
            return None
        return self.songs[self.queue[self.q_pos % len(self.queue)]]

    def _advance(self, delta):
        with self._lock:
            n = len(self.queue)
            if n == 0: return
            self.q_pos = (self.q_pos + delta) % n
        self._play_current()

    def _pygame_watchdog(self):
        """Detects natural end of song and applies repeat logic.
        
        Runs on a daemon thread, sleeping 0.5s at a time, checking if pygame
        stopped playing. This is the correct way to do it because pygame has no
        'song ended' event that works reliably on all platforms I think.
        """
        # We sleep 0.5s, check if pygame stopped, sleep another 0.4s to confirm
        # it wasn't just a momentary hiccup, then advance.
        # The double-check is because pygame.mixer.music.get_busy() can return
        # False for a single frame between tracks. Without it we'd skip songs
        # like a cursed broken record. Like Moebius playing the same fate loop.
        while True:
            time.sleep(0.5)
            if self.playing and not self.paused and HAS_PYGAME:
                if not pygame.mixer.music.get_busy():
                    time.sleep(0.4)  # confirm it's actually done, not a blip
                    if not pygame.mixer.music.get_busy() and self.playing and not self.paused:
                        if self.repeat == 'one':
                            self._play_current()
                        elif self.repeat == 'all':
                            self._advance(+1)
                        else:  # 'none'
                            if self.q_pos < len(self.queue) - 1:
                                self._advance(+1)
                            else:
                                self.playing = False
                                if self.on_state_change:
                                    self.on_state_change(False, False)


# ─── Hotkeys Window ───────────────────────────────────────────────────────────

# SettingsWindow: used to be called HotkeysWindow.
# Then we added overlay settings. Then corner position. Then hold duration.
# At what point does a hotkeys window become a settings window?
# Theseus would understand.
class SettingsWindow:
    """
    Tabbed settings window.
      ⌨ Hotkeys  — record global hotkey combos
      🎬 Overlay  — overlay appearance toggles

    This window has been rebuilt approximately four times.
    It started as a flat list of hotkeys. Then tabs were added.
    Then the overlay tab was added. Then it needed to scroll.
    At some point I considered whether a settings window that needs
    to scroll is a settings window that has too many settings.
    I added more settings anyway. Here we are.
    """

    def __init__(self, master, hk_manager, overlay, panel):
        self.hk      = hk_manager
        self.overlay = overlay
        self.panel   = panel
        self.win     = tk.Toplevel(master)
        self.win.title('⚙  Settings')
        self.win.geometry('480x480')
        self.win.minsize(480, 380)
        self.win.resizable(True, True)
        self.win.configure(bg=T['bg_deep'])
        self.win.grab_set()

        self._recording_key = None
        self._pressed       = set()
        self._vars          = {}
        self._listener      = None
        self._status_var    = tk.StringVar(value='')   # init before _build
        self._build()

    # ── Shell ─────────────────────────────────────────────────────────────────

    def _build(self):
        w = self.win

        # Header
        hdr = tk.Frame(w, bg=T['bg_mid'], height=46)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr, text='⚙  Settings',
            bg=T['bg_mid'], fg=T['accent_hi'], font=('Segoe UI', 13, 'bold')
        ).pack(side='left', padx=16, pady=8)
        tk.Frame(w, bg=T['accent'], height=2).pack(fill='x')

        # Tab bar
        tab_bar = tk.Frame(w, bg=T['bg_deep'])
        tab_bar.pack(fill='x', padx=0)
        self._tab_btns  = {}
        self._tab_pages = {}
        for tab_name in ('⌨  Hotkeys', '🎬  Overlay'):
            btn = tk.Button(tab_bar, text=tab_name,
                command=lambda n=tab_name: self._show_tab(n),
                bg=T['bg_btn'], fg=T['text_dim'],
                activebackground=T['bg_active'], activeforeground=T['accent_hi'],
                relief='flat', bd=0, cursor='hand2',
                font=('Segoe UI', 10), padx=14, pady=8
            )
            btn.pack(side='left')
            self._tab_btns[tab_name] = btn

        tk.Frame(w, bg=T['bg_btn'], height=1).pack(fill='x')

        # Page container
        self._page_container = tk.Frame(w, bg=T['bg_deep'])
        self._page_container.pack(fill='both', expand=True)

        # Build both pages
        self._build_hotkeys_page()
        self._build_overlay_page()

        # Bottom bar
        tk.Frame(w, bg=T['accent'], height=1).pack(fill='x')
        bot = tk.Frame(w, bg=T['bg_deep'])
        bot.pack(fill='x', padx=10, pady=6)
        self._bot_save_btn = tk.Button(bot, text='Save & Apply',
            command=self._save_hotkeys, **BTN)
        self._bot_save_btn.pack(side='left')
        self._bot_reset_btn = tk.Button(bot, text='Reset Hotkey Defaults',
            command=self._reset_hotkeys,
            bg=T['bg_btn'], fg=T['text_dim'],
            activebackground=T['bg_active'], activeforeground=T['text'],
            relief='flat', bd=0, cursor='hand2',
            font=('Segoe UI', 10), padx=10, pady=5
        )
        self._bot_reset_btn.pack(side='left', padx=6)
        tk.Button(bot, text='Close', command=self._close,
            bg=T['bg_btn'], fg=T['text_dim2'],
            activebackground=T['bg_active'], activeforeground=T['text'],
            relief='flat', bd=0, cursor='hand2',
            font=('Segoe UI', 10), padx=10, pady=5
        ).pack(side='right')

        tk.Label(bot, textvariable=self._status_var,
            bg=T['bg_deep'], fg=T['accent_hi'], font=('Segoe UI', 9)
        ).pack(side='left', padx=10)

        # Start on hotkeys tab
        self._show_tab('⌨  Hotkeys')

    def _show_tab(self, name):
        for n, page in self._tab_pages.items():
            page.pack_forget()
        # Hotkeys page is a plain Frame; Overlay page is a scrollable outer Frame.
        # Both pack the same way, the internal layout handles its own padding.
        if name == '⌨  Hotkeys':
            self._tab_pages[name].pack(fill='both', expand=True, padx=16, pady=12)
        else:
            self._tab_pages[name].pack(fill='both', expand=True)
        for n, btn in self._tab_btns.items():
            active = (n == name)
            btn.configure(
                bg=T['bg_active'] if active else T['bg_btn'],
                fg=T['accent_hi'] if active else T['text_dim']
            )
        # Show/hide the hotkey-specific bottom buttons
        is_hk = (name == '⌨  Hotkeys')
        if is_hk:
            self._bot_save_btn.pack(side='left')
            self._bot_reset_btn.pack(side='left', padx=6)
        else:
            self._bot_save_btn.pack_forget()
            self._bot_reset_btn.pack_forget()

    # ── Hotkeys page ─────────────────────────────────────────────────────────

    def _build_hotkeys_page(self):
        page = tk.Frame(self._page_container, bg=T['bg_deep'])
        self._tab_pages['⌨  Hotkeys'] = page

        if not HAS_PYNPUT:
            tk.Label(page, text='pynput not installed.\npip install pynput',
                bg=T['bg_deep'], fg='#ff6655', font=('Segoe UI', 11)
            ).pack(expand=True)
            return

        tk.Label(page, text='Click "Record", then press your key combination.',
            bg=T['bg_deep'], fg=T['text_dim'], font=('Segoe UI', 9)
        ).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0,10))

        last_row = 0
        for row_idx, (key, label) in enumerate(HOTKEY_LABELS.items(), start=1):
            tk.Label(page, text=label, bg=T['bg_deep'], fg=T['text'],
                font=('Segoe UI', 10), width=16, anchor='w'
            ).grid(row=row_idx, column=0, padx=(0,8), pady=5)
            var = tk.StringVar(value=self._fmt(self.hk.bindings.get(key, '')))
            self._vars[key] = var
            tk.Label(page, textvariable=var,
                bg=T['bg_card'], fg=T['accent_hi'],
                font=('Courier New', 10), width=22, anchor='w', padx=6
            ).grid(row=row_idx, column=1, padx=4)
            tk.Button(page, text='Record',
                command=lambda k=key: self._start_recording(k), **BTN_SM
            ).grid(row=row_idx, column=2, padx=4)
            last_row = row_idx

        tk.Label(page, textvariable=self._status_var,
            bg=T['bg_deep'], fg=T['accent_hi'], font=('Segoe UI', 9)
        ).grid(row=last_row+1, column=0, columnspan=3, pady=(12,0), sticky='w')

    # ── Overlay page ─────────────────────────────────────────────────────────

    def _build_overlay_page(self):
        # This page started as just one toggle.
        # Then someone (me) said 'what if there was also a hold duration setting'
        # and now there's a stepper widget and a section divider and I'm writing a
        # comment about it at what is now clearly too late at night.

        # Wrap in a scrollable canvas so nothing gets clipped when the window is small.
        # Yes, this is more complex than a plain Frame. No, there was no other way that I know.
        outer = tk.Frame(self._page_container, bg=T['bg_deep'])
        self._tab_pages['🎬  Overlay'] = outer

        canvas = tk.Canvas(outer, bg=T['bg_deep'], highlightthickness=0)
        scrollbar = tk.Scrollbar(outer, orient='vertical', command=canvas.yview,
            bg=T['bg_btn'], troughcolor=T['bg_deep'], relief='flat', bd=0)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        page = tk.Frame(canvas, bg=T['bg_deep'])
        page_id = canvas.create_window((0, 0), window=page, anchor='nw')

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox('all'))
        def _on_canvas_configure(e):
            canvas.itemconfig(page_id, width=e.width)
        page.bind('<Configure>', _on_frame_configure)
        canvas.bind('<Configure>', _on_canvas_configure)

        # Mouse wheel scrolling, ONLY when hovering over this canvas.
        # Previously used bind_all which is basically a global mousewheel takeover.
        # It worked great in the Settings window and catastrophically everywhere else.
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
        def _bind_wheel(e):
            canvas.bind('<MouseWheel>', _on_mousewheel)
        def _unbind_wheel(e):
            canvas.unbind('<MouseWheel>')
        canvas.bind('<Enter>', _bind_wheel)
        canvas.bind('<Leave>', _unbind_wheel)

        def section(text):
            tk.Label(page, text=text,
                bg=T['bg_deep'], fg=T['text_dim2'],
                font=('Courier New', 8, 'bold')
            ).pack(anchor='w', pady=(14,4))
            tk.Frame(page, bg=T['bg_btn'], height=1).pack(fill='x')

        def toggle_row(parent, label, desc, var):
            row = tk.Frame(parent, bg=T['bg_deep'])
            row.pack(fill='x', pady=6)
            text_col = tk.Frame(row, bg=T['bg_deep'])
            text_col.pack(side='left', fill='x', expand=True)
            tk.Label(text_col, text=label,
                bg=T['bg_deep'], fg=T['text'],
                font=('Segoe UI', 10, 'bold'), anchor='w'
            ).pack(anchor='w')
            tk.Label(text_col, text=desc,
                bg=T['bg_deep'], fg=T['text_dim'],
                font=('Segoe UI', 8), anchor='w', wraplength=300
            ).pack(anchor='w')
            # Pill-style checkbutton
            cb = tk.Checkbutton(row, variable=var,
                bg=T['bg_deep'],
                activebackground=T['bg_deep'],
                selectcolor=T['bg_btn'],
                fg=T['accent_hi'],
                font=('Segoe UI', 9),
                relief='flat', bd=0, cursor='hand2',
                text='ON / OFF'
            )
            cb.pack(side='right', padx=8)
            return cb

        # Add some padding since we lost the padx=16 from _show_tab
        tk.Frame(page, bg=T['bg_deep'], height=12).pack()
        pad = tk.Frame(page, bg=T['bg_deep'])
        pad.pack(fill='x', padx=16)

        # Redefine section and toggle_row to target pad instead of page
        def section(text):
            tk.Label(pad, text=text,
                bg=T['bg_deep'], fg=T['text_dim2'],
                font=('Courier New', 8, 'bold')
            ).pack(anchor='w', pady=(14,4))
            tk.Frame(pad, bg=T['bg_btn'], height=1).pack(fill='x')

        def toggle_row(parent, label, desc, var):
            row = tk.Frame(pad, bg=T['bg_deep'])
            row.pack(fill='x', pady=6)
            text_col = tk.Frame(row, bg=T['bg_deep'])
            text_col.pack(side='left', fill='x', expand=True)
            tk.Label(text_col, text=label,
                bg=T['bg_deep'], fg=T['text'],
                font=('Segoe UI', 10, 'bold'), anchor='w'
            ).pack(anchor='w')
            tk.Label(text_col, text=desc,
                bg=T['bg_deep'], fg=T['text_dim'],
                font=('Segoe UI', 8), anchor='w', wraplength=300
            ).pack(anchor='w')
            cb = tk.Checkbutton(row, variable=var,
                bg=T['bg_deep'], activebackground=T['bg_deep'],
                selectcolor=T['bg_btn'], fg=T['accent_hi'],
                font=('Segoe UI', 9), relief='flat', bd=0, cursor='hand2',
                text='ON / OFF'
            )
            cb.pack(side='right', padx=8)
            return cb

        section('NOTIFICATION POPUP')

        self._auto_show_var = tk.BooleanVar(value=self.overlay.auto_show)
        toggle_row(page,
            'Auto-show on song change',
            'Popup slides in automatically when a new song starts.',
            self._auto_show_var
        )
        self._auto_show_var.trace_add('write', self._on_auto_show_toggle)

        self._texture_var = tk.BooleanVar(value=self.overlay.show_texture)
        toggle_row(page,
            'Scanlines & Grain',
            'Adds CRT scanlines and animated grain dots to the overlay popup.',
            self._texture_var
        )
        self._texture_var.trace_add('write', self._on_texture_toggle)

        section('CORNER POSITION')

        corner_row = tk.Frame(pad, bg=T['bg_deep'])
        corner_row.pack(fill='x', pady=6)
        tk.Label(corner_row, text='Popup corner',
            bg=T['bg_deep'], fg=T['text'],
            font=('Segoe UI', 10, 'bold'), anchor='w', width=16
        ).pack(side='left')
        # Store reference on SettingsWindow so _set_corner can update them
        self.panel._corner_btns = {}
        cur_corner = self.overlay.corner
        for corner in CORNERS:
            btn = tk.Button(corner_row,
                text=CORNER_LABELS[corner],
                command=lambda c=corner: self.panel._set_corner(c),
                bg=T['bg_active'] if corner == cur_corner else T['bg_btn'],
                fg=T['accent_hi'] if corner == cur_corner else T['text_dim'],
                activebackground=T['bg_active'], activeforeground=T['text'],
                relief='flat', bd=0, cursor='hand2',
                font=('Segoe UI', 8), padx=7, pady=5
            )
            btn.pack(side='left', padx=2)
            self.panel._corner_btns[corner] = btn

        section('TIMING')

        hold_frame = tk.Frame(pad, bg=T['bg_deep'])
        hold_frame.pack(fill='x', pady=8)

        hold_text = tk.Frame(hold_frame, bg=T['bg_deep'])
        hold_text.pack(side='left', fill='x', expand=True)
        tk.Label(hold_text, text='Hold duration',
            bg=T['bg_deep'], fg=T['text'],
            font=('Segoe UI', 10, 'bold'), anchor='w'
        ).pack(anchor='w')
        tk.Label(hold_text, text='How long the popup stays visible before sliding out.',
            bg=T['bg_deep'], fg=T['text_dim'],
            font=('Segoe UI', 8), anchor='w', wraplength=240
        ).pack(anchor='w')

        stepper = tk.Frame(hold_frame, bg=T['bg_deep'])
        stepper.pack(side='right', padx=8)
        self._hold_var = tk.IntVar(value=getattr(self.overlay, 'hold_ms', 5500) // 1000)

        def _dec():
            self._hold_var.set(max(2, self._hold_var.get() - 1))
            self._on_hold_change()
        def _inc():
            self._hold_var.set(min(30, self._hold_var.get() + 1))
            self._on_hold_change()

        tk.Button(stepper, text='−', command=_dec,
            bg=T['bg_btn'], fg=T['accent_hi'],
            activebackground=T['bg_active'], activeforeground=T['text'],
            relief='flat', bd=0, cursor='hand2',
            font=('Segoe UI', 14, 'bold'), width=3, pady=6
        ).pack(side='left')
        tk.Label(stepper, textvariable=self._hold_var,
            bg=T['bg_card'], fg=T['accent_hi'],
            font=('Segoe UI', 13, 'bold'),
            width=3, anchor='center', padx=8, pady=4
        ).pack(side='left', padx=4)
        tk.Button(stepper, text='+', command=_inc,
            bg=T['bg_btn'], fg=T['accent_hi'],
            activebackground=T['bg_active'], activeforeground=T['text'],
            relief='flat', bd=0, cursor='hand2',
            font=('Segoe UI', 14, 'bold'), width=3, pady=6
        ).pack(side='left')
        tk.Label(stepper, text='sec',
            bg=T['bg_deep'], fg=T['text_dim'],
            font=('Segoe UI', 8)
        ).pack(side='left', padx=(4,0))

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_auto_show_toggle(self, *_):
        self.overlay.auto_show = bool(self._auto_show_var.get())

    def _on_texture_toggle(self, *_):
        self.overlay.show_texture = bool(self._texture_var.get())

    def _on_hold_change(self, *_):
        try:
            ms = max(2, min(30, self._hold_var.get())) * 1000
            self.overlay.hold_ms = ms
        except Exception:
            pass

    def _start_recording(self, key):
        self._recording_key = key
        self._pressed.clear()
        self._status_var.set(f'Recording "{HOTKEY_LABELS[key]}" — press your combo…')
        self._stop_listener()

        def on_press(k):   self._pressed.add(k)
        def on_release(k):
            if self._recording_key and self._pressed:
                combo = self._build_combo(self._pressed)
                if combo:
                    self._vars[self._recording_key].set(self._fmt(combo))
                    self.hk.bindings[self._recording_key] = combo
                    self._status_var.set(f'✓ Recorded: {self._fmt(combo)}')
                self._recording_key = None
                self._pressed.clear()
                self._stop_listener()

        self._listener = pynput_keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()

    def _build_combo(self, pressed):
        mod_names, main_key = [], None
        modifiers = {
            pynput_keyboard.Key.ctrl,  pynput_keyboard.Key.ctrl_l,  pynput_keyboard.Key.ctrl_r,
            pynput_keyboard.Key.alt,   pynput_keyboard.Key.alt_l,   pynput_keyboard.Key.alt_r,
            pynput_keyboard.Key.shift, pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r,
            pynput_keyboard.Key.cmd,
        }
        for k in pressed:
            if k in (pynput_keyboard.Key.ctrl, pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r):
                if '<ctrl>'  not in mod_names: mod_names.append('<ctrl>')
            elif k in (pynput_keyboard.Key.alt, pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r):
                if '<alt>'   not in mod_names: mod_names.append('<alt>')
            elif k in (pynput_keyboard.Key.shift, pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r):
                if '<shift>' not in mod_names: mod_names.append('<shift>')
            elif k == pynput_keyboard.Key.cmd:
                if '<cmd>'   not in mod_names: mod_names.append('<cmd>')
            elif k not in modifiers:
                main_key = k.char if (hasattr(k, 'char') and k.char) else f'<{str(k).replace("Key.", "")}>'
        return '+'.join(mod_names + [main_key]) if main_key else None

    def _stop_listener(self):
        if self._listener:
            try: self._listener.stop()
            except Exception: pass
            self._listener = None

    def _save_hotkeys(self):
        self.hk.update(self.hk.bindings)
        self._status_var.set('✓ Saved and applied!')

    def _reset_hotkeys(self):
        self.hk.bindings = DEFAULT_HOTKEYS.copy()
        for k, var in self._vars.items():
            var.set(self._fmt(self.hk.bindings[k]))
        self._status_var.set('Reset to defaults.')

    def _close(self):
        self._stop_listener()
        self.win.destroy()

    @staticmethod
    def _fmt(combo):
        if not combo: return '(none)'
        return (combo
            .replace('<ctrl>','Ctrl').replace('<alt>','Alt')
            .replace('<shift>','Shift').replace('<cmd>','Cmd')
            .replace('<space>','Space').replace('<left>','←')
            .replace('<right>','→').replace('<up>','↑').replace('<down>','↓')
            .replace('<','').replace('>','')
        )


# ─── Playlist Manager Window ──────────────────────────────────────────────────

# ─── Playlist Manager Window ─────────────────────────────────────────────────
# A two-panel window: playlists on the left, full library on the right.
# Songs flow left (← Add) from library into the selected playlist.
# Songs flow right (→ Remove) from playlist back into the void.
# The playlist panel also shows songs currently in the playlist with
# Up/Down reorder and Remove buttons.
#
# Missing file detection: ⚠ only appears if os.path.isfile() fails,
# NOT just because the song isn't in the currently loaded library.
# So playlist songs from a folder you haven't opened this session show
# up normally, the app trusts the path, not the library state.
class PlaylistManagerWindow:
    def __init__(self, master, store, player, library_songs, on_load_playlist):
        self.store            = store
        self.player           = player
        self.library          = library_songs
        self.on_load_playlist = on_load_playlist
        self._selected_playlist = None

        self.win = tk.Toplevel(master)
        self.win.title('📋  Playlist Manager')
        self.win.geometry('860x560')
        self.win.minsize(720, 480)
        self.win.configure(bg=T['bg_deep'])
        self.win.grab_set()
        self._build()
        self._refresh_playlists()

    def _build(self):
        w = self.win
        hdr = tk.Frame(w, bg=T['bg_mid'], height=46)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr, text='📋  Playlist Manager',
            bg=T['bg_mid'], fg=T['accent_hi'], font=('Segoe UI', 13, 'bold')
        ).pack(side='left', padx=16, pady=8)
        tk.Label(hdr, text='Double-click a playlist to load & play it',
            bg=T['bg_mid'], fg=T['text_dim2'], font=('Segoe UI', 9)
        ).pack(side='right', padx=16)
        tk.Frame(w, bg=T['accent'], height=2).pack(fill='x')

        body = tk.Frame(w, bg=T['bg_deep'])
        body.pack(fill='both', expand=True, padx=10, pady=8)

        # Left: playlists
        left = tk.Frame(body, bg=T['bg_deep'], width=260)
        left.pack(side='left', fill='both', expand=False)
        left.pack_propagate(False)

        tk.Label(left, text='PLAYLISTS', bg=T['bg_deep'], fg=T['text_dim2'],
            font=('Courier New', 8, 'bold')).pack(anchor='w', pady=(0,4))

        pl_btns = tk.Frame(left, bg=T['bg_deep'])
        pl_btns.pack(fill='x', pady=(0,4))
        tk.Button(pl_btns, text='＋ New',    command=self._new_playlist,    **BTN_SM).pack(side='left', padx=(0,3))
        tk.Button(pl_btns, text='✎ Rename', command=self._rename_playlist, **BTN_SM).pack(side='left', padx=3)
        tk.Button(pl_btns, text='✕ Delete', command=self._delete_playlist, **BTN_SM).pack(side='left', padx=3)

        pl_lf = tk.Frame(left, bg=T['bg_deep'])
        pl_lf.pack(fill='x')
        pl_sb = tk.Scrollbar(pl_lf, bg=T['bg_btn'], troughcolor=T['bg_deep'], relief='flat', bd=0)
        pl_sb.pack(side='right', fill='y')
        self.pl_listbox = tk.Listbox(pl_lf, height=6,
            bg=T['bg_deep'], fg=T['text_list'], selectbackground=T['bg_active'], selectforeground=T['accent_hi'],
            activestyle='none', font=('Segoe UI', 10), relief='flat', bd=0, yscrollcommand=pl_sb.set)
        self.pl_listbox.pack(fill='x')
        pl_sb.config(command=self.pl_listbox.yview)
        self.pl_listbox.bind('<<ListboxSelect>>', self._on_pl_select)
        self.pl_listbox.bind('<Double-1>', self._load_selected_playlist)

        tk.Frame(left, bg=T['separator'], height=1).pack(fill='x', pady=6)
        tk.Label(left, text='SONGS IN PLAYLIST', bg=T['bg_deep'], fg=T['text_dim2'],
            font=('Courier New', 8, 'bold')).pack(anchor='w')

        ps_btns = tk.Frame(left, bg=T['bg_deep'])
        ps_btns.pack(fill='x', pady=(2,4))
        tk.Button(ps_btns, text='▲ Up',     command=self._move_up,        **BTN_SM).pack(side='left', padx=(0,3))
        tk.Button(ps_btns, text='▼ Down',   command=self._move_down,      **BTN_SM).pack(side='left', padx=3)
        tk.Button(ps_btns, text='✕ Remove', command=self._remove_from_pl, **BTN_SM).pack(side='left', padx=3)

        ps_lf = tk.Frame(left, bg=T['bg_deep'])
        ps_lf.pack(fill='both', expand=True)
        ps_sb = tk.Scrollbar(ps_lf, bg=T['bg_btn'], troughcolor=T['bg_deep'], relief='flat', bd=0)
        ps_sb.pack(side='right', fill='y')
        self.pl_songs_listbox = tk.Listbox(ps_lf,
            bg=T['bg_card'], fg=T['text_list'], selectbackground=T['bg_active'], selectforeground=T['accent_hi'],
            activestyle='none', font=('Segoe UI', 9), relief='flat', bd=0, yscrollcommand=ps_sb.set)
        self.pl_songs_listbox.pack(fill='both', expand=True)
        ps_sb.config(command=self.pl_songs_listbox.yview)

        # Middle arrows
        mid = tk.Frame(body, bg=T['bg_deep'], width=60)
        mid.pack(side='left', fill='y')
        mid.pack_propagate(False)
        tk.Frame(mid, bg=T['bg_deep']).pack(expand=True)
        tk.Button(mid, text='←\nAdd',    command=self._add_to_playlist,
            bg=T['bg_btn'], fg=T['accent_hi'], activebackground=T['bg_active'], activeforeground=T['text'],
            relief='flat', bd=0, cursor='hand2', font=('Segoe UI', 9), padx=6, pady=8, width=5
        ).pack(pady=4)
        tk.Button(mid, text='→\nRemove', command=self._remove_from_pl,
            bg=T['bg_btn'], fg=T['text_dim'], activebackground=T['bg_active'], activeforeground=T['text'],
            relief='flat', bd=0, cursor='hand2', font=('Segoe UI', 9), padx=6, pady=8, width=5
        ).pack(pady=4)
        tk.Frame(mid, bg=T['bg_deep']).pack(expand=True)

        # Right: library
        right = tk.Frame(body, bg=T['bg_deep'])
        right.pack(side='left', fill='both', expand=True, padx=(4,0))

        lib_hdr = tk.Frame(right, bg=T['bg_deep'])
        lib_hdr.pack(fill='x', pady=(0,4))
        tk.Label(lib_hdr, text='LIBRARY', bg=T['bg_deep'], fg=T['text_dim2'],
            font=('Courier New', 8, 'bold')).pack(side='left')
        self.lib_count_var = tk.StringVar(value='')
        tk.Label(lib_hdr, textvariable=self.lib_count_var,
            bg=T['bg_deep'], fg=T['text_dim2'], font=('Courier New', 8)).pack(side='right')

        sf = tk.Frame(right, bg=T['bg_deep'])
        sf.pack(fill='x', pady=(0,4))
        tk.Label(sf, text='🔍', bg=T['bg_deep'], fg=T['text_dim2'], font=('Segoe UI', 10)).pack(side='left')
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', self._on_search)
        tk.Entry(sf, textvariable=self.search_var,
            bg=T['bg_btn'], fg=T['text'], insertbackground=T['accent_hi'],
            relief='flat', bd=4, font=('Segoe UI', 9)
        ).pack(side='left', fill='x', expand=True, padx=4)

        lib_lf = tk.Frame(right, bg=T['bg_deep'])
        lib_lf.pack(fill='both', expand=True)
        lib_sb = tk.Scrollbar(lib_lf, bg=T['bg_btn'], troughcolor=T['bg_deep'], relief='flat', bd=0)
        lib_sb.pack(side='right', fill='y')
        self.lib_listbox = tk.Listbox(lib_lf,
            bg=T['bg_deep'], fg=T['text_list'], selectbackground=T['bg_active'], selectforeground=T['accent_hi'],
            activestyle='none', font=('Segoe UI', 9), relief='flat', bd=0,
            yscrollcommand=lib_sb.set, selectmode='extended')
        self.lib_listbox.pack(fill='both', expand=True)
        lib_sb.config(command=self.lib_listbox.yview)
        self.lib_listbox.bind('<Double-1>', lambda _: self._add_to_playlist())

        tk.Frame(w, bg=T['separator'], height=1).pack(fill='x')
        bot = tk.Frame(w, bg=T['bg_deep'])
        bot.pack(fill='x', padx=10, pady=6)
        tk.Button(bot, text='▶  Load & Play Selected Playlist',
            command=self._load_selected_playlist, **BTN).pack(side='left')
        tk.Button(bot, text='Close', command=self.win.destroy,
            bg=T['bg_btn'], fg=T['text_dim2'], activebackground=T['bg_active'], activeforeground=T['text'],
            relief='flat', bd=0, cursor='hand2', font=('Segoe UI', 10), padx=10, pady=5
        ).pack(side='right')

        self._populate_library(self.library)

    def _populate_library(self, songs):
        self._lib_songs = songs
        self.lib_listbox.delete(0, tk.END)
        if not songs:
            self.lib_listbox.insert(tk.END, '  (no library loaded — use 📂 Open Folder)')
            self.lib_count_var.set('')
        else:
            for s in songs:
                self.lib_listbox.insert(tk.END, s.list_label())
            self.lib_count_var.set(f'{len(songs)} tracks')

    def _on_search(self, *_):
        q = self.search_var.get().lower()
        filtered = self.library if not q else [
            s for s in self.library if q in s.title.lower() or q in s.artist.lower()]
        self._populate_library(filtered)

    def _refresh_playlists(self):
        self.pl_listbox.delete(0, tk.END)
        for name in self.store.names():
            self.pl_listbox.insert(tk.END, f'  {name}')
        self._refresh_pl_songs()

    def _on_pl_select(self, _=None):
        name = self._get_selected_pl_name()
        if name:
            self._selected_playlist = name
            self._refresh_pl_songs()

    def _get_selected_pl_name(self):
        sel = self.pl_listbox.curselection()
        if not sel: return None
        return self.pl_listbox.get(sel[0]).strip()

    def _refresh_pl_songs(self):
        self.pl_songs_listbox.delete(0, tk.END)
        if not self._selected_playlist: return
        path_map = {s.path: s for s in self.library}
        for p in self.store.get_paths(self._selected_playlist):
            song  = path_map.get(p)
            if song:
                label = song.list_label()
            elif not os.path.isfile(p):
                label = f'  ⚠ Missing: {Path(p).name}'
            else:
                label = f'  {Path(p).stem}'  # file exists, just not in loaded library
            self.pl_songs_listbox.insert(tk.END, label)

    def _new_playlist(self):
        name = simpledialog.askstring('New Playlist',
            'Name your playlist (e.g. "Chill Vibes", "Hype OSTs"):', parent=self.win)
        if not name or not name.strip(): return
        name = name.strip()
        if name in self.store.names():
            messagebox.showwarning('Already Exists', f'"{name}" already exists.', parent=self.win); return
        self.store.create(name)
        self._refresh_playlists()
        idx = self.store.names().index(name)
        self.pl_listbox.selection_clear(0, tk.END)
        self.pl_listbox.selection_set(idx)
        self._selected_playlist = name

    def _rename_playlist(self):
        name = self._get_selected_pl_name()
        if not name:
            messagebox.showinfo('No Selection', 'Select a playlist to rename.', parent=self.win); return
        new_name = simpledialog.askstring('Rename', f'New name for "{name}":',
            initialvalue=name, parent=self.win)
        if not new_name or not new_name.strip() or new_name.strip() == name: return
        new_name = new_name.strip()
        if new_name in self.store.names():
            messagebox.showwarning('Already Exists', f'"{new_name}" already exists.', parent=self.win); return
        self.store.rename(name, new_name)
        self._selected_playlist = new_name
        self._refresh_playlists()

    def _delete_playlist(self):
        name = self._get_selected_pl_name()
        if not name:
            messagebox.showinfo('No Selection', 'Select a playlist to delete.', parent=self.win); return
        if not messagebox.askyesno('Delete', f'Delete "{name}"?\nSongs will not be deleted.',
                parent=self.win): return
        self.store.delete(name)
        self._selected_playlist = None
        self._refresh_playlists()

    def _add_to_playlist(self):
        if not self._selected_playlist:
            messagebox.showinfo('No Playlist', 'Select or create a playlist first.', parent=self.win); return
        sel = self.lib_listbox.curselection()
        if not sel: return
        for i in sel:
            self.store.add_path(self._selected_playlist, self._lib_songs[i].path)
        self._refresh_pl_songs()

    def _remove_from_pl(self):
        if not self._selected_playlist: return
        sel   = self.pl_songs_listbox.curselection()
        if not sel: return
        paths = self.store.get_paths(self._selected_playlist)
        for i in reversed(sel):
            if i < len(paths):
                self.store.remove_path(self._selected_playlist, paths[i])
        self._refresh_pl_songs()

    def _move_up(self):
        if not self._selected_playlist: return
        sel = self.pl_songs_listbox.curselection()
        if not sel or sel[0] == 0: return
        idx   = sel[0]
        paths = self.store.get_paths(self._selected_playlist)
        paths[idx-1], paths[idx] = paths[idx], paths[idx-1]
        self.store.set_paths(self._selected_playlist, paths)
        self._refresh_pl_songs()
        self.pl_songs_listbox.selection_set(idx-1)

    def _move_down(self):
        if not self._selected_playlist: return
        sel   = self.pl_songs_listbox.curselection()
        paths = self.store.get_paths(self._selected_playlist)
        if not sel or sel[0] >= len(paths) - 1: return
        idx = sel[0]
        paths[idx], paths[idx+1] = paths[idx+1], paths[idx]
        self.store.set_paths(self._selected_playlist, paths)
        self._refresh_pl_songs()
        self.pl_songs_listbox.selection_set(idx+1)

    def _load_selected_playlist(self, _=None):
        name = self._get_selected_pl_name()
        if not name:
            messagebox.showinfo('No Selection', 'Select a playlist to play.', parent=self.win); return
        path_map  = {s.path: s for s in self.library}
        songs, missing = [], []
        for p in self.store.get_paths(name):
            if p in path_map:   songs.append(path_map[p])
            elif os.path.isfile(p): songs.append(Song(p))
            else: missing.append(p)
        if missing:
            snippet = '\n'.join(f'  • {Path(p).name}' for p in missing[:5])
            extra   = f'\n  … and {len(missing)-5} more' if len(missing) > 5 else ''
            messagebox.showwarning('Some files missing',
                f'{len(missing)} song(s) skipped:\n{snippet}{extra}', parent=self.win)
        if not songs:
            messagebox.showwarning('Empty / Missing',
                f'"{name}" has no playable songs.', parent=self.win); return
        self.on_load_playlist(name, songs)
        self.win.destroy()


# ─── Theme Window ────────────────────────────────────────────────────────────

# ThemeWindow: 12 color themes, each named and carefully crafted.
# The bug where switching themes recolored the theme preview cards
# in the active theme's colors took an embarrassingly long time to fix.
class ThemeWindow:
    """Grid of theme presets with live preview swatches.

    Each card shows a mini swatch strip (3 color blocks) and the theme name.
    Clicking applies the theme live via _recolor_all.

    THE INFAMOUS CARD CORRUPTION BUG, now fixed:
    _recolor_all walks the entire widget tree to swap colors, which meant
    it would also recolor these theme cards, mapping their hardcoded palette
    colors to the new theme's palette. 
    Fix: after recoloring, _restamp_cards() forcibly resets each card to its
    own theme's colors. Took embarrassingly long to figure out.
    It was, as always, obvious in retrospect.
    """

    def __init__(self, master, on_apply):
        self.on_apply = on_apply

        self.win = tk.Toplevel(master)
        self.win.title('🎨  Themes')
        self.win.resizable(False, False)
        self.win.configure(bg=T['bg_deep'])
        self.win.grab_set()

        self._build()

    def _build(self):
        w = self.win

        hdr = tk.Frame(w, bg=T['bg_mid'], height=46)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr, text='🎨  Themes',
            bg=T['bg_mid'], fg=T['accent_hi'], font=('Segoe UI', 13, 'bold')
        ).pack(side='left', padx=16, pady=8)
        tk.Label(hdr, text='Click a theme to apply it live',
            bg=T['bg_mid'], fg=T['text_dim2'], font=('Segoe UI', 9)
        ).pack(side='right', padx=16)

        tk.Frame(w, bg=T['accent'], height=2).pack(fill='x')

        body = tk.Frame(w, bg=T['bg_deep'], padx=16, pady=14)
        body.pack(fill='both', expand=True)

        self._btns = {}
        names = list(THEMES.keys())
        cols  = 3
        for i, name in enumerate(names):
            row, col = divmod(i, cols)
            t = THEMES[name]
            cell = tk.Frame(body,
                bg=t['bg_btn'],
                highlightbackground=t['accent'],
                highlightthickness=2 if name == ACTIVE_THEME_NAME else 0,
                cursor='hand2'
            )
            cell.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')

            # Mini swatch strip (3 color blocks)
            swatch = tk.Frame(cell, bg=t['bg_deep'], height=8)
            swatch.pack(fill='x')
            for clr in (t['bg_mid'], t['accent'], t['accent_hi']):
                tk.Frame(swatch, bg=clr, width=30, height=8).pack(side='left', fill='y')

            # Theme name label
            tk.Label(cell, text=name,
                bg=t['bg_btn'], fg=t['accent_hi'],
                font=('Segoe UI', 10, 'bold'), padx=10, pady=8
            ).pack(anchor='w')

            # Bind click on both frame and label
            for widget in (cell, swatch):
                widget.bind('<Button-1>', lambda e, n=name: self._select(n))
            for child in cell.winfo_children():
                child.bind('<Button-1>', lambda e, n=name: self._select(n))

            self._btns[name] = cell

        for c in range(cols):
            body.columnconfigure(c, weight=1)

        tk.Frame(w, bg=T['accent'], height=1).pack(fill='x')
        bot = tk.Frame(w, bg=T['bg_deep'])
        bot.pack(fill='x', padx=12, pady=8)
        tk.Button(bot, text='Close', command=self.win.destroy,
            bg=T['bg_btn'], fg=T['text_dim2'],
            activebackground=T['bg_active'], activeforeground=T['text'],
            relief='flat', bd=0, cursor='hand2',
            font=('Segoe UI', 10), padx=12, pady=5
        ).pack(side='right')

        # Centre window
        self.win.update_idletasks()
        self.win.geometry(f'+{self.win.winfo_screenwidth()//2 - self.win.winfo_width()//2}'
                          f'+{self.win.winfo_screenheight()//2 - self.win.winfo_height()//2}')

    def _select(self, name):
        self.on_apply(name)
        # Re-stamp every card with its own theme's colors.
        # _recolor_all walks the whole widget tree including these cards and
        # corrupts them — we just overwrite them back to their correct values.
        self._restamp_cards()

    def _restamp_cards(self):
        """Force every card back to its own theme palette, ignoring global recolor."""
        for n, cell in self._btns.items():
            t      = THEMES[n]
            active = (n == ACTIVE_THEME_NAME)
            cell.configure(
                bg=t['bg_btn'],
                highlightbackground=t['accent'],
                highlightthickness=2 if active else 0
            )
            children = cell.winfo_children()
            # First child is the swatch frame
            if children:
                swatch = children[0]
                swatch.configure(bg=t['bg_deep'])
                swatch_blocks = swatch.winfo_children()
                for i, clr in enumerate((t['bg_mid'], t['accent'], t['accent_hi'])):
                    if i < len(swatch_blocks):
                        swatch_blocks[i].configure(bg=clr)
            # Second child is the label
            if len(children) > 1:
                lbl = children[1]
                lbl.configure(bg=t['bg_btn'], fg=t['accent_hi'])


# ─── Control Panel ────────────────────────────────────────────────────────────

# ─── Control Panel ───────────────────────────────────────────────────────────
# The main window. Contains:
#   • Textured header with Mistral font title
#   • Now-playing card (album art + title + artist)
#   • Progress bar + transport controls (⏮ ⏸ ⏭)
#   • Toolbar 1: Open Folder ▾, Shuffle, Repeat, Display
#   • Toolbar 2: Playlists, Settings, Themes, Preview, Full Library
#   • Volume slider
#   • Queue list with search bar and drag-to-reorder
#
# The whole class is a bit large. This is because tkinter doesn't have
# component architecture, so everything lives in one God Class.
class ControlPanel:
    def __init__(self, root, player, overlay, store, hk_manager):
        self.root       = root
        self.player     = player
        self.overlay    = overlay
        self.store      = store
        self.hk_manager = hk_manager
        self.active_playlist_name = None
        self._seeking       = False
        self._prog_updating = False
        self._last_folder   = None
        self._library_songs = []   # always the full scanned library, never a playlist subset
        self._corner_btns   = {}   # populated by SettingsWindow when open

        root.title("♫  Kalanaris' Music Player")
        root.geometry('480x580')
        root.minsize(480, 520)
        root.configure(bg=T['bg_deep'])
        root.protocol('WM_DELETE_WINDOW', self._on_close)

        self._build()
        self._bind_player()
        self._poll_progress()
        # Wire the add-to-playlist hotkey now that self is available
        self.hk_manager.on_add_to_playlist = self._hotkey_add_to_playlist
        self.hk_manager.on_shuffle          = self._toggle_shuffle
        self.hk_manager.on_repeat           = self._cycle_repeat
        self.hk_manager.on_preview          = self._preview_notif
        self.hk_manager.start()   # restart with the new action registered
        # Draw textures once layout is resolved
        root.after(100, self.refresh_textures)

    def _build(self):
        r = self.root

        # Textured header — Canvas so we can draw noise behind the title
        self._hdr_canvas = tk.Canvas(r, height=52, highlightthickness=0,
            bg=T['bg_mid'])
        self._hdr_canvas.pack(fill='x')
        self._hdr_canvas.bind('<Configure>', self._on_hdr_resize)
        self._hdr_title_id = self._hdr_canvas.create_text(
            16, 28, text="♫  Kalanaris' Music Player",
            fill=T['accent_hi'], font=_pick_script_font(18), anchor='w'
        )
        self._hdr_img = None   # kept alive here
        self._draw_hdr_texture()

        tk.Frame(r, bg=T['accent'], height=2).pack(fill='x')

        # Now playing card — Canvas for textured background, Frame on top for labels
        card_outer = tk.Frame(r, bg=T['bg_deep'])
        card_outer.pack(fill='x', padx=12, pady=(10,4))

        self._card_canvas = tk.Canvas(card_outer, height=90, highlightthickness=0,
            bg=T['bg_card'])
        self._card_canvas.pack(fill='x')
        self._card_canvas.bind('<Configure>', self._on_card_resize)
        self._card_img = None   # kept alive

        # Frame on top of the canvas
        card = tk.Frame(card_outer, bg=T['bg_card'])
        card.place(relx=0, rely=0, relwidth=1, relheight=1)
        card.lift()

        # ── Album art thumbnail (left side of card) ──
        CARD_ART = 64
        self._card_art_label = tk.Label(card,
            bg=T['bg_card'], width=CARD_ART, height=CARD_ART,
            relief='flat', bd=0
        )
        self._card_art_label.pack(side='left', padx=(10, 0), pady=8)
        self._card_art_photo = None   # keep reference

        # ── Text (right of art) ──
        text_col = tk.Frame(card, bg=T['bg_card'])
        text_col.pack(side='left', fill='both', expand=True, padx=(10, 14))

        self.source_var = tk.StringVar(value='')
        tk.Label(text_col, textvariable=self.source_var,
            bg=T['bg_card'], fg=T['text_dim2'], font=('Courier New', 8, 'bold')
        ).pack(anchor='w', pady=(10,0))

        self.title_var  = tk.StringVar(value='No song loaded')
        self.artist_var = tk.StringVar(value='Open a folder to begin')
        self.dur_var    = tk.StringVar(value='')

        tk.Label(text_col, textvariable=self.title_var,
            bg=T['bg_card'], fg=T['text'], font=('Segoe UI', 12, 'bold'),
            wraplength=340, justify='left'
        ).pack(anchor='w', pady=(2,0))

        row = tk.Frame(text_col, bg=T['bg_card'])
        row.pack(fill='x', pady=(1,8))
        tk.Label(row, textvariable=self.artist_var,
            bg=T['bg_card'], fg=T['accent_hi'], font=('Segoe UI', 10)
        ).pack(side='left')
        tk.Label(row, textvariable=self.dur_var,
            bg=T['bg_card'], fg=T['text_dim2'], font=('Courier New', 9)
        ).pack(side='right')

        # Progress bar
        pf = tk.Frame(r, bg=T['bg_deep'])
        pf.pack(fill='x', padx=12, pady=(2,0))
        self.pos_var = tk.StringVar(value='0:00')
        self.len_var = tk.StringVar(value='0:00')
        tk.Label(pf, textvariable=self.pos_var,
            bg=T['bg_deep'], fg=T['text_dim'], font=('Courier New', 8), width=5
        ).pack(side='left')
        self.prog_var = tk.DoubleVar(value=0)
        self.prog_slider = tk.Scale(pf, variable=self.prog_var,
            from_=0, to=100, orient='horizontal',
            bg=T['bg_deep'], fg=T['accent'], troughcolor=T['bg_btn'],
            highlightthickness=0, bd=0, showvalue=False,
            command=self._on_prog_drag)
        self.prog_slider.pack(side='left', fill='x', expand=True, padx=4)
        self.prog_slider.bind('<ButtonRelease-1>', self._on_prog_release)
        tk.Label(pf, textvariable=self.len_var,
            bg=T['bg_deep'], fg=T['text_dim'], font=('Courier New', 8), width=5
        ).pack(side='left')

        # Transport controls
        ctrl = tk.Frame(r, bg=T['bg_deep'])
        ctrl.pack(pady=6)
        tk.Button(ctrl, text='⏮', command=self.player.prev_song,  **BTN_ICON).pack(side='left', padx=3)
        self.play_btn = tk.Button(ctrl, text='⏸', command=self.player.toggle_pause, **BTN_ICON)
        self.play_btn.pack(side='left', padx=3)
        tk.Button(ctrl, text='⏭', command=self.player.next_song,  **BTN_ICON).pack(side='left', padx=3)

        # Toolbar 1
        tb1 = tk.Frame(r, bg=T['bg_deep'])
        tb1.pack(fill='x', padx=12, pady=4)
        # Open Folder + Recent Folders dropdown
        folder_frame = tk.Frame(tb1, bg=T['bg_deep'])
        folder_frame.pack(side='left', padx=(3,0))
        tk.Button(folder_frame, text='📂  Open Folder', command=self._open_folder, **BTN).pack(side='left')
        tk.Button(folder_frame, text='▾', command=self._show_recent_folders,
            bg=T['bg_btn'], fg=T['text_dim'],
            activebackground=T['bg_active'], activeforeground=T['accent_hi'],
            relief='flat', bd=0, cursor='hand2',
            font=('Segoe UI', 10), padx=4, pady=5
        ).pack(side='left', padx=(1,3))
        self.shuf_btn = tk.Button(tb1, text='🔀  Shuffle: ON', command=self._toggle_shuffle, **BTN)
        self.shuf_btn.pack(side='left', padx=3)
        self.repeat_btn_var = tk.StringVar(value=REPEAT_LABELS[self.player.repeat])
        tk.Button(tb1, textvariable=self.repeat_btn_var,
            command=self._cycle_repeat, **BTN).pack(side='left', padx=3)

        n_monitors = len(self.overlay.monitors)
        self.display_btn_var = tk.StringVar(value='🖥  Display: 1')
        if n_monitors > 1:
            tk.Button(tb1, textvariable=self.display_btn_var,
                command=self._cycle_display, **BTN).pack(side='left', padx=3)

        # Toolbar 2
        tb2 = tk.Frame(r, bg=T['bg_deep'])
        tb2.pack(fill='x', padx=12, pady=(0,4))
        tk.Button(tb2, text='📋  Playlists', command=self._open_playlist_manager, **BTN).pack(side='left', padx=3)
        tk.Button(tb2, text='⚙  Settings',  command=self._open_settings,          **BTN).pack(side='left', padx=3)
        tk.Button(tb2, text='🎨  Themes',    command=self._open_themes,           **BTN).pack(side='left', padx=3)
        tk.Button(tb2, text='📣  Preview',   command=self._preview_notif,         **BTN).pack(side='left', padx=3)
        self.back_btn = tk.Button(tb2, text='🎵  Full Library',
            command=self._load_full_library, **BTN)

        # Volume
        vf = tk.Frame(r, bg=T['bg_deep'])
        vf.pack(fill='x', padx=16, pady=(2,6))
        tk.Label(vf, text='Vol', bg=T['bg_deep'], fg=T['text_dim2'], font=('Segoe UI', 9)).pack(side='left')
        self.vol_var = tk.IntVar(value=80)
        self.vol_slider = tk.Scale(vf, variable=self.vol_var,
            from_=0, to=100, orient='horizontal',
            bg=T['bg_deep'], fg=T['accent_hi'], troughcolor=T['bg_btn'],
            highlightthickness=0, bd=0, showvalue=False,
            command=self._on_vol_slider)
        self.vol_slider.pack(side='left', fill='x', expand=True, padx=6)
        self.vol_entry_var = tk.StringVar(value='80')
        vol_entry = tk.Entry(vf, textvariable=self.vol_entry_var,
            bg=T['bg_btn'], fg=T['accent_hi'], insertbackground=T['accent_hi'],
            relief='flat', bd=4, font=('Segoe UI', 9), width=4, justify='center')
        vol_entry.pack(side='left')
        vol_entry.bind('<Return>',   self._on_vol_entry)
        vol_entry.bind('<FocusOut>', self._on_vol_entry)

        # Queue list
        tk.Frame(r, bg=T['accent'], height=1).pack(fill='x', padx=12, pady=(4,0))
        ql_hdr = tk.Frame(r, bg=T['bg_deep'])
        ql_hdr.pack(fill='x', padx=14, pady=(4,2))
        self.queue_label_var = tk.StringVar(value='QUEUE')
        tk.Label(ql_hdr, textvariable=self.queue_label_var,
            bg=T['bg_deep'], fg=T['text_dim2'], font=('Courier New', 8, 'bold')
        ).pack(side='left')
        self.count_var = tk.StringVar(value='')
        tk.Label(ql_hdr, textvariable=self.count_var,
            bg=T['bg_deep'], fg=T['text_dim2'], font=('Courier New', 8)
        ).pack(side='right')

        # Queue search bar
        qsf = tk.Frame(r, bg=T['bg_deep'])
        qsf.pack(fill='x', padx=12, pady=(0,2))
        tk.Label(qsf, text='🔍', bg=T['bg_deep'], fg=T['text_dim'],
            font=('Segoe UI', 9)).pack(side='left')
        self.queue_search_var = tk.StringVar()
        self.queue_search_var.trace_add('write', self._on_queue_search)
        qse = tk.Entry(qsf, textvariable=self.queue_search_var,
            bg=T['bg_btn'], fg=T['text'], insertbackground=T['accent_hi'],
            relief='flat', bd=3, font=('Segoe UI', 9))
        qse.pack(side='left', fill='x', expand=True, padx=4)
        tk.Button(qsf, text='✕', command=lambda: self.queue_search_var.set(''),
            bg=T['bg_deep'], fg=T['text_dim'],
            activebackground=T['bg_deep'], activeforeground=T['accent_hi'],
            relief='flat', bd=0, cursor='hand2', font=('Segoe UI', 9)
        ).pack(side='left')

        lf = tk.Frame(r, bg=T['bg_deep'])
        lf.pack(fill='both', expand=True, padx=12, pady=(0,10))
        sb = tk.Scrollbar(lf, bg=T['bg_btn'], troughcolor=T['bg_deep'], relief='flat', bd=0)
        sb.pack(side='right', fill='y')
        self.listbox = tk.Listbox(lf,
            bg=T['bg_deep'], fg=T['text_list'], selectbackground=T['bg_active'], selectforeground=T['accent_hi'],
            activestyle='none', font=('Segoe UI', 9), relief='flat', bd=0, yscrollcommand=sb.set)
        self.listbox.pack(fill='both', expand=True)
        sb.config(command=self.listbox.yview)
        self.listbox.bind('<Double-1>',   self._on_listbox_double)
        self.listbox.bind('<Button-3>',   self._on_listbox_right_click)
        self.listbox.bind('<Button-1>',   self._on_drag_start)
        self.listbox.bind('<B1-Motion>',  self._on_drag_motion)
        self.listbox.bind('<ButtonRelease-1>', self._on_drag_release)
        self._drag_idx   = None
        self._drag_ghost = None

    # ── Queue drag-to-reorder ────────────────────────────────────────────────

    def _on_drag_start(self, event):
        # Record where the drag started. We don't actually begin reordering
        # until the mouse has moved 5px — this is the "threshold" that
        # prevents a single click from being eaten as a drag.
        # Learned this the hard way after double-click stopped working.
        self._drag_idx    = self.listbox.nearest(event.y)
        self._drag_start_y = event.y   # threshold: don't drag until moved 5px

    def _on_drag_motion(self, event):
        if self._drag_idx is None:
            return
        # Only start reordering after intentional movement — prevents eating double-clicks
        if abs(event.y - self._drag_start_y) < 5:
            return
        target = self.listbox.nearest(event.y)
        if target != self._drag_idx and 0 <= target < len(self.player.songs):
            # Swap in player.songs
            songs = self.player.songs
            songs[self._drag_idx], songs[target] = songs[target], songs[self._drag_idx]
            # Swap in queue indices too so playback order matches
            try:
                qi = self.player.queue.index(self._drag_idx)
                qj = self.player.queue.index(target)
                self.player.queue[qi], self.player.queue[qj] = self.player.queue[qj], self.player.queue[qi]
            except ValueError:
                pass
            # Refresh listbox around the two changed rows (faster than full repopulate)
            self.listbox.delete(self._drag_idx)
            self.listbox.insert(self._drag_idx, songs[self._drag_idx].list_label())
            self.listbox.delete(target)
            self.listbox.insert(target, songs[target].list_label())
            # Keep highlight on dragged item
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(target)
            self._drag_idx = target

    def _on_drag_release(self, event):
        self._drag_idx = None

    # ── Player bindings ───────────────────────────────────────────────────────

    # ── Texture helpers ──────────────────────────────────────────────────────

    def _draw_hdr_texture(self):
        """Render noise texture onto the header canvas."""
        c = self._hdr_canvas
        c.update_idletasks()
        w = c.winfo_width() or 480
        img = _make_noise_image(w, 52, T['bg_mid'], grain=10)
        if img:
            c.delete('tex')
            c.create_image(0, 0, image=img, anchor='nw', tags='tex')
            c.tag_lower('tex')   # keep text on top
            self._hdr_img = img
        # Ensure text color matches current theme
        c.itemconfig(self._hdr_title_id, fill=T['accent_hi'])

    def _draw_card_texture(self):
        """Render noise texture onto the card canvas."""
        c = self._card_canvas
        c.update_idletasks()
        w = c.winfo_width() or 480
        h = c.winfo_height() or 80
        img = _make_noise_image(w, h, T['bg_card'], grain=8)
        if img:
            c.delete('tex')
            c.create_image(0, 0, image=img, anchor='nw', tags='tex')
            self._card_img = img

    def _on_hdr_resize(self, event):
        self.root.after(50, self._draw_hdr_texture)

    def _on_card_resize(self, event):
        self.root.after(50, self._draw_card_texture)

    def refresh_textures(self):
        """Called after a theme change to redraw all textures."""
        self._hdr_canvas.configure(bg=T['bg_mid'])
        self._card_canvas.configure(bg=T['bg_card'])
        self._draw_hdr_texture()
        self._draw_card_texture()

    # ── Player bindings ───────────────────────────────────────────────────────

    def _bind_player(self):
        self.player.on_song_change  = lambda s: self.root.after(0, self._update_now_playing, s)
        self.player.on_state_change = lambda p, pa: self.root.after(0, self._update_state, p, pa)
        self.overlay.player_ref = self.player   # lets overlay draw progress bar
        self._tray_icon = None
        self._setup_tray()

    def _setup_tray(self):
        """Build and launch the system tray icon in a background thread.

        pystray runs its own event loop on a daemon thread.
        The tray icon stays alive as long as the app is running.
        When the user clicks X, we hide the window instead of closing —
        the tray icon is how they get it back.

        The icon itself is a tiny ♪ drawn with Pillow, in your theme's accent
        colour. It's not beautiful. It's 64x64 pixels of good intentions.
        2B would understand. Sometimes function is enough.
        """
        if not HAS_TRAY:
            return
        try:
            # Build a simple 64x64 icon using Pillow if available, else a plain color
            if HAS_PIL:
                img = Image.new('RGB', (64, 64), color=T['bg_mid'])
                # Draw a simple ♪ using a filled circle + stem as primitive art
                from PIL import ImageDraw
                draw = ImageDraw.Draw(img)
                r, g, b = (int(T['accent_hi'][i:i+2], 16) for i in (1, 3, 5))
                draw.ellipse([14, 38, 34, 54], fill=(r, g, b))
                draw.rectangle([30, 12, 38, 46], fill=(r, g, b))
                draw.ellipse([36, 8, 56, 24], fill=(r, g, b))
                draw.ellipse([38, 10, 54, 22], fill=(int(T['bg_mid'][1:3],16),
                    int(T['bg_mid'][3:5],16), int(T['bg_mid'][5:7],16)))
            else:
                img = None

            def _tray_show(icon, item):
                self.root.after(0, self._show_from_tray)
            def _tray_prev(icon, item):
                self.player.prev_song()
            def _tray_play(icon, item):
                self.player.toggle_pause()
            def _tray_next(icon, item):
                self.player.next_song()
            def _tray_quit(icon, item):
                icon.stop()
                self.root.after(0, self._on_close)

            menu = pystray.Menu(
                TrayItem('Show Player',  _tray_show, default=True),
                pystray.Menu.SEPARATOR,
                TrayItem('⏮ Previous',  _tray_prev),
                TrayItem('⏸ Play/Pause',_tray_play),
                TrayItem('⏭ Next',      _tray_next),
                pystray.Menu.SEPARATOR,
                TrayItem('Quit',         _tray_quit),
            )

            if img:
                self._tray_icon = pystray.Icon(
                    "KalanarisPlayer", img,
                    "Kalanaris' Music Player", menu
                )
                import threading
                t = threading.Thread(target=self._tray_icon.run, daemon=True)
                t.start()

            # Override close button to minimize to tray instead of quitting
            self.root.protocol('WM_DELETE_WINDOW', self._minimize_to_tray)

        except Exception as e:
            print(f'[WARNING] Tray setup failed: {e}')

    def _minimize_to_tray(self):
        """Hide the window to tray instead of closing."""
        if HAS_TRAY and self._tray_icon:
            self.root.withdraw()
        else:
            self._on_close()

    def _show_from_tray(self):
        """Restore window from tray."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    # ── Progress bar ──────────────────────────────────────────────────────────

    def _poll_progress(self):
        # Runs every 150ms to update the progress bar and timestamp.
        # 150ms is a good balance, fast enough to look smooth,
        # slow enough not to murder the CPU. (We already have a 60fps draw loop.
        # We don't need to be greedy.)
        # Note: we check `playing OR paused` because on_song_change fires just
        # before playing=True is set, so the first poll would see playing=False
        # and leave the bar stuck at 0:00. This drove me insane for two sessions.
        if not self._seeking:
            song = self.player.current_song()
            # Check playing OR pausedthe on_song_change callback fires
            # just before playing=True is set, so the first poll(s) would
            # see playing=False and leave the bar stuck at 0:00 forever.
            # Checking both states means we always update when there's a song.
            if song and song.duration > 0 and (self.player.playing or self.player.paused):
                pos = min(self.player.get_position(), song.duration)
                self._prog_updating = True
                self.prog_var.set(pos)
                self._prog_updating = False
                self.pos_var.set(song.fmt_pos(pos))
                self.len_var.set(song.fmt_duration())
                self.prog_slider.config(to=song.duration)
        self.root.after(150, self._poll_progress)   # 150ms for smooth bar

    def _on_prog_drag(self, _):
        if self._prog_updating: return
        self._seeking = True
        song = self.player.current_song()
        if song:
            self.pos_var.set(song.fmt_pos(self.prog_var.get()))

    def _on_prog_release(self, _):
        if self._seeking:
            self.player.seek(self.prog_var.get())
            self._seeking = False

    # ── Volume ────────────────────────────────────────────────────────────────

    def _on_vol_slider(self, val):
        v = int(float(val))
        self.vol_entry_var.set(str(v))
        self.player.set_volume(v / 100.0)
        self._schedule_save_volume()

    def _on_vol_entry(self, _=None):
        try:    v = max(0, min(100, int(self.vol_entry_var.get())))
        except: v = self.vol_var.get()
        self.vol_entry_var.set(str(v))
        self.vol_var.set(v)
        self.player.set_volume(v / 100.0)
        self._schedule_save_volume()

    def _schedule_save_volume(self):
        if hasattr(self, '_vol_save_job') and self._vol_save_job:
            self.root.after_cancel(self._vol_save_job)
        self._vol_save_job = self.root.after(800, self._save_session)

    # ── Right-click context menu on queue ─────────────────────────────────────

    def _on_listbox_right_click(self, event):
        idx = self.listbox.nearest(event.y)
        if idx < 0 or idx >= len(self.player.songs):
            return
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(idx)
        song = self.player.songs[idx]

        menu = tk.Menu(self.root, tearoff=0,
            bg='#1e0d38', fg='#ffcc55',
            activebackground='#2e1d55', activeforeground='#ffffff',
            font=('Segoe UI', 9)
        )
        menu.add_command(label='▶  Play now',
            command=lambda: self.player.play_by_song_index(idx))
        menu.add_separator()

        names = self.store.names()
        if names:
            sub = tk.Menu(menu, tearoff=0,
                bg='#1e0d38', fg='#ffcc55',
                activebackground='#2e1d55', activeforeground='#ffffff',
                font=('Segoe UI', 9)
            )
            for name in names:
                sub.add_command(label=f'  {name}',
                    command=lambda n=name, s=song: self._ctx_add_to_playlist(n, s))
            menu.add_cascade(label='Add to playlist  ▸', menu=sub)
        else:
            menu.add_command(label='Add to playlist  (none created yet)', state='disabled')

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _ctx_add_to_playlist(self, playlist_name, song):
        self.store.add_path(playlist_name, song.path)
        # Brief status flash in the queue label
        self.queue_label_var.set(f'✓ Added to "{playlist_name}"')
        self.root.after(2000, lambda: self.queue_label_var.set(
            f'PLAYLIST — {self.active_playlist_name}' if self.active_playlist_name else 'QUEUE'
        ))

    # ── Other callbacks ───────────────────────────────────────────────────────

    def _record_recent_folder(self, folder):
        """Keep a rolling list of the 8 most recently opened folders."""
        s = load_settings()
        recent = s.get('recent_folders', [])
        folder_str = str(folder)
        if folder_str in recent:
            recent.remove(folder_str)
        recent.insert(0, folder_str)
        s['recent_folders'] = recent[:8]
        save_settings(s)

    def _show_recent_folders(self):
        s = load_settings()
        recent = [f for f in s.get('recent_folders', []) if os.path.isdir(f)]
        if not recent:
            messagebox.showinfo('No Recent Folders', 'No recently opened folders yet. Open a folder first.')
            return
        menu = tk.Menu(self.root, tearoff=0,
            bg=T['bg_btn'], fg=T['accent_hi'],
            activebackground=T['bg_active'], activeforeground=T['text'],
            font=('Segoe UI', 9)
        )
        for folder in recent:
            # Show just the last two parts of the path so it fits
            parts = Path(folder).parts
            label = '  ' + ('/'.join(parts[-2:]) if len(parts) >= 2 else folder)
            menu.add_command(label=label,
                command=lambda f=folder: self._load_recent_folder(f))
        try:
            # Position below the ▾ button
            x = self.root.winfo_rootx() + 12
            y = self.root.winfo_rooty() + 130
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _load_recent_folder(self, folder):
        self.title_var.set('Loading…')
        self.artist_var.set('')
        self.root.update()
        if not self.player.load_folder(folder):
            messagebox.showwarning('No audio files found', f'No supported audio files found in: {folder}')
            self.title_var.set('No song loaded')
            self.artist_var.set('Try a different folder')
            return
        self._last_folder   = folder
        self._library_songs = list(self.player.songs)
        self.active_playlist_name = None
        self._record_recent_folder(folder)
        self._update_source_label()
        self._populate_queue()
        self.back_btn.pack_forget()
        self._save_session(playlist=None)

    def _open_folder(self):
        # Opens a folder picker, scans all audio files recursively,
        # creates Song objects (which read tags), loads them into the player.
        # If your music folder has 10,000 files this will take a moment.
        # Make tea. The app isn't frozen, it's just working very hard.
        folder = filedialog.askdirectory(title='Select Music Folder')
        if not folder: return
        self.title_var.set('Loading…')
        self.artist_var.set('')
        self.root.update()
        if not self.player.load_folder(folder):
            messagebox.showwarning('No audio files found',
                f'No supported audio files (.mp3, .flac, .ogg, .wav) found in:\n{folder}')
            self.title_var.set('No song loaded')
            self.artist_var.set('Try a different folder')
            return
        self._last_folder   = folder
        self._library_songs = list(self.player.songs)   # snapshot full library
        self.active_playlist_name = None
        self._record_recent_folder(folder)
        self._update_source_label()
        self._populate_queue()
        self.back_btn.pack_forget()
        self._save_session(playlist=None)

    def _load_full_library(self):
        if not self._library_songs: return
        self.player.load_song_list(self._library_songs)
        self.active_playlist_name = None
        self._update_source_label()
        self._populate_queue()
        self.back_btn.pack_forget()
        self._save_session(playlist=None)

    def _open_playlist_manager(self):
        # Always show the full library in the manager, not just the current playlist
        library = self._library_songs if self._library_songs else self.player.songs
        PlaylistManagerWindow(self.root, self.store, self.player,
            library, self._on_playlist_loaded)

    def _on_playlist_loaded(self, name, songs):
        self.player.load_song_list(songs)
        self.active_playlist_name = name
        self._update_source_label()
        self._populate_queue()
        self.back_btn.pack(side='left', padx=3)
        self._save_session(playlist=name)

    def _open_settings(self):
        SettingsWindow(self.root, self.hk_manager, self.overlay, self)

    def _open_themes(self):
        ThemeWindow(self.root, self._apply_theme)

    def _apply_theme(self, name):
        # Freeze rendering while we recolor everything so the user doesn't see
        # half-recolored widgets in a mid-transition state.
        # tkinter doesn't have a proper "suspend drawing" API, but calling
        # pack_propagate(False) on the root... just kidding, we use update() deferral.
        # The real trick: do everything, THEN let tkinter repaint once at the end.
        self.root.wm_attributes('-alpha', 0.0)   # invisible during recolor
        try:
            apply_theme(name, self.root)
            self.refresh_textures()
        finally:
            self.root.update_idletasks()           # flush all pending recolor ops
            self.root.wm_attributes('-alpha', 1.0) # reappear fully painted
        self._save_session()

    def _update_source_label(self):
        if self.active_playlist_name:
            self.source_var.set(f'PLAYLIST  ·  {self.active_playlist_name}')
            self.queue_label_var.set(f'PLAYLIST — {self.active_playlist_name}')
        else:
            self.source_var.set('FULL LIBRARY')
            self.queue_label_var.set('QUEUE')

    def _set_corner(self, corner):
        # Move the overlay to a new corner and update button highlights.
        # The buttons live in the Settings window (when open) so we keep
        # a reference to them on self._corner_btns to update from here.
        # When Settings is closed, _corner_btns is empty, which is fine.
        self.overlay.set_corner(corner)
        # Update the corner buttons wherever they live (Settings window)
        if hasattr(self, '_corner_btns') and self._corner_btns:
            for c, btn in self._corner_btns.items():
                active = (c == corner)
                btn.config(
                    bg=T['bg_active'] if active else T['bg_btn'],
                    fg=T['accent_hi'] if active else T['text_dim']
                )
        self._save_session()

    def _hotkey_add_to_playlist(self):
        """Called by global hotkey — pops a quick playlist picker dialog."""
        song = self.player.current_song()
        if not song: return
        names = self.store.names()
        if not names: return
        # Schedule on main thread (pynput callbacks run on a background thread)
        self.root.after(0, lambda: self._quick_add_dialog(song, names))

    def _quick_add_dialog(self, song, names):
        # Appears when you press Ctrl+Alt+A during a game.
        # A small window floats over everything with your playlist names.
        # It is the most useful feature in this app and I added it almost as an afterthought.
        win = tk.Toplevel(self.root)
        win.title('Add to Playlist')
        win.configure(bg='#0d0618')
        win.resizable(False, False)
        win.grab_set()
        win.focus_force()

        tk.Frame(win, bg='#d4a030', height=2).pack(fill='x')
        tk.Label(win, text=f'Add  "{self._trunc(song.title, 36)}"  to:',
            bg='#0d0618', fg='#f0f0f0', font=('Segoe UI', 10),
            padx=14, pady=10
        ).pack(anchor='w')

        for name in names:
            def _add(n=name):
                self.store.add_path(n, song.path)
                self.queue_label_var.set(f'✓ Added to "{n}"')
                self.root.after(2000, lambda: self.queue_label_var.set(
                    f'PLAYLIST — {self.active_playlist_name}' if self.active_playlist_name else 'QUEUE'
                ))
                win.destroy()
            tk.Button(win, text=f'  {name}',
                command=_add,
                bg='#0d0618', fg='#ccbbee',
                activebackground='#2e1d55', activeforeground='#ffcc55',
                relief='flat', bd=0, cursor='hand2',
                font=('Segoe UI', 10), anchor='w', padx=14, pady=6
            ).pack(fill='x')

        tk.Frame(win, bg='#1e0d38', height=1).pack(fill='x', pady=(4,0))
        tk.Button(win, text='Cancel', command=win.destroy,
            bg='#0d0618', fg='#6655aa',
            activebackground='#1e0d38', activeforeground='#ffffff',
            relief='flat', bd=0, cursor='hand2',
            font=('Segoe UI', 9), padx=10, pady=6
        ).pack(anchor='e', padx=10, pady=6)

        # Centre over main window
        self.root.update_idletasks()
        rx = self.root.winfo_x() + self.root.winfo_width()  // 2
        ry = self.root.winfo_y() + self.root.winfo_height() // 2
        win.update_idletasks()
        wx = rx - win.winfo_width()  // 2
        wy = ry - win.winfo_height() // 2
        win.geometry(f'+{wx}+{wy}')

    @staticmethod
    def _trunc(s, n):
        return s if len(s) <= n else s[:n-1] + '…'

    def _cycle_display(self):
        new_idx = (self.overlay.monitor_idx + 1) % len(self.overlay.monitors)
        self.overlay.set_monitor(new_idx)
        self.display_btn_var.set(f'🖥  Display: {new_idx + 1}')

    def _toggle_shuffle(self):
        self.player.toggle_shuffle()
        self.shuf_btn.config(text=f'🔀  Shuffle: {"ON" if self.player.shuffled else "OFF"}')
        self._populate_queue()
        self._save_session()

    def _cycle_repeat(self):
        self.player.cycle_repeat()
        self.repeat_btn_var.set(REPEAT_LABELS[self.player.repeat])

    def _preview_notif(self):
        song = self.player.current_song()
        if song: self.overlay.show(song)

    def _on_listbox_double(self, _):
        sel = self.listbox.curselection()
        if not sel: return
        label = self.listbox.get(sel[0])
        # When search is active the listbox is a subset, so match by label
        q = self.queue_search_var.get().strip() if hasattr(self, 'queue_search_var') else ''
        if q:
            for i, s in enumerate(self.player.songs):
                if s.list_label() == label:
                    self.player.play_by_song_index(i)
                    return
        else:
            self.player.play_by_song_index(sel[0])

    def _on_close(self):
        self.hk_manager.stop()
        if HAS_TRAY and hasattr(self, '_tray_icon') and self._tray_icon:
            try: self._tray_icon.stop()
            except Exception: pass
        if HAS_PYGAME:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except Exception: pass
        self.root.destroy()

    def _update_now_playing(self, song):
        self.title_var.set(song.title)
        self.artist_var.set(song.artist)
        self.dur_var.set(song.fmt_duration() if song.duration > 0 else '')
        self.len_var.set(song.fmt_duration() if song.duration > 0 else '0:00')
        self.prog_slider.config(to=max(1, song.duration))
        self.prog_var.set(0)
        self.pos_var.set('0:00')
        self._update_card_art(song)
        if self.overlay.auto_show:
            self.overlay.show(song)
        # Clear search so the advancing song is always visible in the queue
        if hasattr(self, 'queue_search_var') and self.queue_search_var.get():
            self.queue_search_var.set('')
        try:
            idx = self.player.songs.index(song)
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(idx)
            self.listbox.see(idx)
        except ValueError:
            pass

    def _update_card_art(self, song):
        """Update the album art thumbnail in the now-playing card."""
        CARD_ART = 64
        if HAS_PIL and song and song.art_data:
            try:
                img = Image.open(io.BytesIO(song.art_data))
                img = img.convert('RGB').resize((CARD_ART, CARD_ART), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._card_art_photo = photo
                self._card_art_label.configure(image=photo, width=CARD_ART, height=CARD_ART)
                return
            except Exception:
                pass
        # No art — clear the label fully so previous song's art doesn't linger
        self._card_art_photo = None
        self._card_art_label.configure(image='', text='♪',
            fg=T['accent_hi'], font=('Arial', 22, 'bold'),
            width=CARD_ART, height=CARD_ART, bg=T['bg_card'])

    def _update_state(self, playing, paused):
        self.play_btn.config(text='▶' if paused else '⏸')

    def _on_queue_search(self, *_):
        """Filter the visible queue list by the search term. Does not affect playback order."""
        q = self.queue_search_var.get().lower().strip()
        self.listbox.delete(0, tk.END)
        songs = self.player.songs
        if not q:
            for s in songs:
                self.listbox.insert(tk.END, s.list_label())
            self.count_var.set(f'{len(songs)} tracks')
        else:
            matches = [s for s in songs if q in s.title.lower() or q in s.artist.lower()]
            for s in matches:
                self.listbox.insert(tk.END, s.list_label())
            self.count_var.set(f'{len(matches)}/{len(songs)} tracks')

    def _populate_queue(self):
        # Clear search when populating so we always show the full list on load
        if hasattr(self, 'queue_search_var'):
            self.queue_search_var.set('')
        self.listbox.delete(0, tk.END)
        for s in self.player.songs:
            self.listbox.insert(tk.END, s.list_label())
        self.count_var.set(f'{len(self.player.songs)} tracks')

    # ── Session persistence ───────────────────────────────────────────────────

    def _save_session(self, playlist=...):
        """Save session state to settings.json.
        
        Called from approximately 8 different places.
        Volume changes, shuffle toggles, folder opens, corner moves, theme applies...
        If I missed one, your settings won't save from that action.
        """
        s = load_settings()
        if self._last_folder:
            s['last_folder'] = str(self._last_folder)
        if playlist is not ...:
            s['last_playlist'] = playlist
        s['volume']  = self.vol_var.get()
        s['shuffled'] = self.player.shuffled
        s['corner']   = self.overlay.corner
        s['theme']         = ACTIVE_THEME_NAME
        s['overlay_texture'] = self.overlay.show_texture
        s['overlay_hold_ms'] = self.overlay.hold_ms
        s['overlay_auto_show'] = self.overlay.auto_show
        save_settings(s)

    def restore_session(self):
        """Called 300ms after startup, once the UI is fully built.

        Restores: theme, volume, shuffle, overlay settings, corner position,
        last folder, and last playlist. In that order, theme must come first
        so widgets draw in the right colors, and folder must come before playlist
        so the library exists to filter against.

        If this function crashes silently (which it can, because every step
        touches disk, settings, or the player), you'll just see the default
        gold theme with no music loaded and no idea why.
        I have stared at this function at 1am more times than I care to admit.
        Ask me how I know. Go on. Ask me. OH WAIT YOU CANT THIS IS CODE. GOOD LUCK. HAHAHAHA.
        """
        s = load_settings()

        # Restore theme, pass self.root so _recolor_all recolors all live widgets.
        # T starts as the default (Touhou Gold) since we removed the premature
        # pre-apply in main(), so _recolor_all correctly maps default → saved theme.
        theme = s.get('theme', 'Touhou Gold')
        if theme in THEMES and theme != 'Touhou Gold':
            apply_theme(theme, self.root)
            self.refresh_textures()

        # Restore volume
        vol = s.get('volume', 80)
        self.vol_var.set(vol)
        self.vol_entry_var.set(str(vol))
        self.player.set_volume(vol / 100.0)

        # Restore shuffle
        shuffled = s.get('shuffled', True)
        self.player.shuffled = shuffled
        self.shuf_btn.config(text=f'🔀  Shuffle: {"ON" if shuffled else "OFF"}')

        # Restore overlay texture + hold duration + auto-show
        self.overlay.show_texture = s.get('overlay_texture', True)
        self.overlay.hold_ms      = s.get('overlay_hold_ms', 5500)
        self.overlay.auto_show    = s.get('overlay_auto_show', True)

        # Restore overlay corner
        corner = s.get('corner', 'bottom-left')
        if corner in CORNERS:
            self._set_corner(corner)

        # Restore folder
        folder = s.get('last_folder')
        if not folder or not os.path.isdir(folder):
            return

        self.title_var.set('Restoring last session…')
        self.artist_var.set('')
        self.root.update()

        if not self.player.load_folder(folder):
            self.title_var.set('No song loaded')
            self.artist_var.set('Open a folder to begin')
            return

        self._last_folder   = folder
        self._library_songs = list(self.player.songs)   # snapshot full library
        self.active_playlist_name = None

        # Restore last playlist
        last_pl = s.get('last_playlist')
        if last_pl and last_pl in self.store.names():
            path_map  = {song.path: song for song in self.player.songs}
            songs, missing = [], []
            for p in self.store.get_paths(last_pl):
                if p in path_map:       songs.append(path_map[p])
                elif os.path.isfile(p): songs.append(Song(p))
                else:                   missing.append(p)
            if songs:
                self.player.load_song_list(songs)
                self.active_playlist_name = last_pl
                self.back_btn.pack(side='left', padx=3)

        self._update_source_label()
        self._populate_queue()


# ─── Main ─────────────────────────────────────────────────────────────────────

# ─── Main ─────────────────────────────────────────────────────────────────────
# Entry point. Creates the root window and all major components,
# then hands off to tkinter's event loop which runs forever (or until closed).
#
# Component creation order matters:
#   1. root (tk.Tk) — must exist before any other widgets
#   2. PlaylistStore — pure data, no widgets needed
#   3. Player — audio backend, no widgets needed
#   4. NowPlayingOverlay — creates a Toplevel (needs root first)
#   5. HotkeyManager — starts listener thread immediately
#   6. ControlPanel — builds all UI, wires everything together
#
# Then 300ms later: restore_session() loads the last session.
# The delay gives tkinter time to fully render before we start
# loading files and changing colors. Without it, textures don't
# render correctly on first draw. I do not fully understand why.
# Some battles are not worth fighting.
def main():
    root = tk.Tk()

    store      = PlaylistStore()
    player     = Player()
    overlay    = NowPlayingOverlay(root)
    hk_manager = HotkeyManager(player)
    panel      = ControlPanel(root, player, overlay, store, hk_manager)

    player.set_volume(0.8)

    if len(sys.argv) > 1:
        folder = sys.argv[1]
        if os.path.isdir(folder):
            root.after(300, lambda: (
                player.load_folder(folder) and (
                    panel._populate_queue() or True
                )
            ))
        else:
            messagebox.showerror('Invalid Path', f'Not a directory:\n{folder}')
    else:
        # Auto-restore last session
        root.after(300, panel.restore_session)

    root.mainloop()


if __name__ == '__main__':
    main()
