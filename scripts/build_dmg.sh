#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "==> Cleaning previous build artifacts..."
rm -rf build dist *.dmg

echo "==> Building SonicVideo.app with py2app..."
python setup_app.py py2app

if [ ! -d "dist/SonicVideo.app" ]; then
    echo "ERROR: py2app build failed — dist/SonicVideo.app not found."
    exit 1
fi

echo "==> Creating DMG..."
DMG_NAME="SonicVideo.dmg"
hdiutil create \
    -volname "SonicVideo" \
    -srcfolder "dist/SonicVideo.app" \
    -ov \
    -format UDZO \
    "dist/$DMG_NAME"

echo "==> Done! DMG created at dist/$DMG_NAME"
