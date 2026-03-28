"""
build.py — Kalanaris' Music Player packager
============================================
Packages music_overlay.py into a standalone Windows .exe using PyInstaller.

Run with:
    python build.py

Output will be in:
    dist/KalanarisPlayer/KalanarisPlayer.exe

Everything the app needs is bundled — no Python installation required
on the target machine (as long as the Visual C++ redistributable is present,
which it almost certainly is on any modern Windows install).

Notes:
- First run installs PyInstaller automatically if it isn't present.
- The build takes 30–90 seconds. This is normal. Grab a coffee.
- The output folder is about 60–80 MB. Also normal. PyInstaller bundles Python itself.
- If your antivirus flags the .exe, that's a false positive. PyInstaller exes
  trip heuristics because they unpack themselves on launch. Add an exclusion.
  (Yes, this is an extremely 2010 problem. No, it hasn't been fixed.)
"""

import subprocess
import sys
import os
from pathlib import Path

HERE = Path(__file__).parent
SCRIPT = HERE / 'music_overlay.py'
APP_NAME = 'KalanarisPlayer'


def run(cmd, **kwargs):
    print(f'\n>>> {" ".join(str(c) for c in cmd)}\n')
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f'\n[ERROR] Command failed with exit code {result.returncode}')
        sys.exit(result.returncode)
    return result


def ensure_pyinstaller():
    try:
        import PyInstaller
        print(f'[OK] PyInstaller {PyInstaller.__version__} already installed.')
    except ImportError:
        print('[INFO] PyInstaller not found. Installing...')
        run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])


def build():
    print('=' * 60)
    print("  Kalanaris' Music Player — build script")
    print('=' * 60)

    if not SCRIPT.exists():
        print(f'[ERROR] Cannot find {SCRIPT}')
        print('        Make sure build.py is in the same folder as music_overlay.py')
        sys.exit(1)

    ensure_pyinstaller()

    # Clean previous build artifacts so we start fresh.
    # Like resetting to a save point before the final boss.
    dist_dir  = HERE / 'dist'
    build_dir = HERE / 'build'
    spec_file = HERE / f'{APP_NAME}.spec'

    print('\n[INFO] Building...')

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name',         APP_NAME,
        '--onedir',                      # folder mode — instant startup, zip the folder to share
        '--windowed',                    # no console window (we're a GUI app)
        '--noconfirm',                   # overwrite previous dist without asking
        '--clean',                       # wipe PyInstaller cache before building
        '--distpath',     str(dist_dir),
        '--workpath',     str(build_dir),
        '--specpath',     str(HERE),

        # Hidden imports that PyInstaller sometimes misses with pygame/mutagen
        '--hidden-import', 'pygame',
        '--hidden-import', 'pygame.mixer',
        '--hidden-import', 'mutagen',
        '--hidden-import', 'mutagen.id3',
        '--hidden-import', 'mutagen.mp3',
        '--hidden-import', 'mutagen.flac',
        '--hidden-import', 'mutagen.oggvorbis',
        '--hidden-import', 'PIL',
        '--hidden-import', 'PIL.Image',
        '--hidden-import', 'PIL.ImageTk',
        '--hidden-import', 'pynput',
        '--hidden-import', 'pynput.keyboard',
        '--hidden-import', 'pynput.keyboard._win32',
        '--hidden-import', 'pystray',

        str(SCRIPT),
    ]

    run(cmd)

    exe_path = dist_dir / APP_NAME / f'{APP_NAME}.exe'

    print('\n' + '=' * 60)
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f'  [OK] Build successful!')
        print(f'       {exe_path}')
        print(f'       Size: {size_mb:.1f} MB')
        print()
        print('  To distribute:')
        print(f'       Zip up the entire  dist/{APP_NAME}/  folder.')
        print(f'       The .exe only works alongside the other files in that folder.')
        print()
        print('  Data files (playlists, settings, hotkeys) will be created in:')
        print(f'       dist/{APP_NAME}/KalanarisPlayer/')
        print('       (created automatically on first launch)')
    else:
        print('  [ERROR] Build appeared to succeed but .exe not found.')
        print(f'          Expected: {exe_path}')
    print('=' * 60)


if __name__ == '__main__':
    build()
