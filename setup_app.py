"""
py2app build configuration for SonicVideo.

Usage:
    python setup_app.py py2app --semi-standalone

Semi-standalone mode: the .app references the local Python environment
instead of bundling the full interpreter + all packages.  This avoids
modulegraph recursion issues with large packages (torch, whisper, etc.).
"""
import sys
from setuptools import setup

APP = ['launcher.py']

DATA_FILES = [
    ('app/static', [
        'app/static/index.html',
    ]),
    ('app/static/css', [
        'app/static/css/style.css',
    ]),
    ('app/static/js', [
        'app/static/js/main.js',
    ]),
]

OPTIONS = {
    'argv_emulation': False,
    'semi_standalone': True,
    'site_packages': True,
    'includes': [
        'fastapi',
        'uvicorn',
        'starlette',
        'webview',
        'PIL',
        'numpy',
        'cv2',
        'httpx',
        'dotenv',
        'openai',
        'google.generativeai',
    ],
    'packages': [
        'app',
        'app.core',
        'app.api',
    ],
    'excludes': [
        'PyInstaller',
        'pytest',
        'setuptools.tests',
        'distutils.tests',
        'tkinter',
        'matplotlib',
    ],
    'plist': {
        'CFBundleName': 'SonicVideo',
        'CFBundleDisplayName': 'SonicVideo',
        'CFBundleIdentifier': 'com.sonicvideo.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
    },
    'iconfile': None,
}

# Bump recursion limit for modulegraph scanning large packages
sys.setrecursionlimit(10000)

setup(
    app=APP,
    name='SonicVideo',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
