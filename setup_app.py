"""
py2app build configuration for SonicVideo (fallback).

NOTE: The recommended build method is `make dmg` which uses
scripts/build_dmg.sh to create a shell-script-based .app bundle.
py2app has known issues with torch/whisper/CLIP (recursion limits
in modulegraph).  This file is kept for reference only.

Usage:
    python setup_app.py py2app --semi-standalone
"""
import sys
from setuptools import setup

APP = ['launcher.py']

DATA_FILES = [
    ('app/static', ['app/static/index.html']),
    ('app/static/css', ['app/static/css/style.css']),
    ('app/static/js', ['app/static/js/main.js']),
]

OPTIONS = {
    'argv_emulation': False,
    'semi_standalone': True,
    'site_packages': True,
    'includes': [
        'fastapi', 'uvicorn', 'starlette', 'webview',
        'PIL', 'numpy', 'cv2', 'httpx', 'dotenv',
        'openai', 'google.generativeai',
    ],
    'packages': ['app', 'app.core', 'app.api'],
    'excludes': [
        'PyInstaller', 'pytest', 'setuptools.tests',
        'distutils.tests', 'tkinter', 'matplotlib',
    ],
    'plist': {
        'CFBundleName': 'SonicVideo',
        'CFBundleDisplayName': 'SonicVideo',
        'CFBundleIdentifier': 'com.sonicvideo.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
    },
}

sys.setrecursionlimit(10000)

setup(
    app=APP,
    name='SonicVideo',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
