"""
py2app build configuration for SonicVideo.

Usage:
    python setup_app.py py2app
"""
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
    'includes': [
        'fastapi',
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'starlette',
        'moviepy',
        'scenedetect',
        'whisper',
        'clip',
        'torch',
        'webview',
        'PIL',
        'numpy',
        'cv2',
        'librosa',
        'httpx',
        'dotenv',
        'openai',
        'google.generativeai',
    ],
    'packages': [
        'app',
        'app.core',
        'app.api',
        'torch',
        'whisper',
        'clip',
        'moviepy',
        'scenedetect',
        'webview',
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

setup(
    app=APP,
    name='SonicVideo',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
