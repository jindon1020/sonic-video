#!/bin/bash
#
# Build SonicVideo.app manually (no py2app).
#
# Strategy:  create a standard macOS .app bundle whose executable is a
# shell script that activates the bundled venv and runs launcher.py.
# The entire project source + venv are copied into Contents/Resources.
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_NAME="SonicVideo"
DIST_DIR="$PROJECT_DIR/dist"
APP_DIR="$DIST_DIR/$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

echo "==> Cleaning previous build..."
rm -rf "$DIST_DIR"
mkdir -p "$MACOS" "$RESOURCES"

# ── 1. Info.plist ──────────────────────────────────────────────────
cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>SonicVideo</string>
    <key>CFBundleDisplayName</key>
    <string>SonicVideo</string>
    <key>CFBundleIdentifier</key>
    <string>com.sonicvideo.app</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleExecutable</key>
    <string>SonicVideo</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
</dict>
</plist>
PLIST

# ── 2. Shell-script launcher (the actual executable) ──────────────
cat > "$MACOS/$APP_NAME" <<'LAUNCHER'
#!/bin/bash
# SonicVideo – macOS app launcher
DIR="$(cd "$(dirname "$0")/../Resources/project" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# Activate the bundled virtual-env
source "$DIR/venv/bin/activate"
cd "$DIR"

# Run the Python launcher
exec python launcher.py
LAUNCHER
chmod +x "$MACOS/$APP_NAME"

# ── 3. Copy project into Resources/project ────────────────────────
echo "==> Copying project files..."
PROJECT_DEST="$RESOURCES/project"
mkdir -p "$PROJECT_DEST"

# Source code & config
cp -R "$PROJECT_DIR/app"            "$PROJECT_DEST/app"
cp    "$PROJECT_DIR/launcher.py"    "$PROJECT_DEST/"
cp    "$PROJECT_DIR/run.py"         "$PROJECT_DEST/"
cp    "$PROJECT_DIR/requirements.txt" "$PROJECT_DEST/"
cp    "$PROJECT_DIR/.env.example"   "$PROJECT_DEST/"
[ -f "$PROJECT_DIR/.env" ] && cp "$PROJECT_DIR/.env" "$PROJECT_DEST/"

# Remove processed artifacts (not needed in bundle)
rm -rf "$PROJECT_DEST/app/static/processed"
mkdir -p "$PROJECT_DEST/app/static/processed/thumbnails"

# ── 4. Copy venv ──────────────────────────────────────────────────
echo "==> Copying virtual environment (this may take a while)..."
cp -R "$PROJECT_DIR/venv" "$PROJECT_DEST/venv"

# Fix venv shebang / pyvenv.cfg to be relocatable
# Replace the hard-coded home path in pyvenv.cfg
PYTHON_HOME="$(grep 'home = ' "$PROJECT_DEST/venv/pyvenv.cfg" | cut -d= -f2 | xargs)"
# We keep the original Python framework reference since it's a framework install

echo "==> Verifying bundle..."
if [ ! -x "$MACOS/$APP_NAME" ]; then
    echo "ERROR: Executable not found"; exit 1
fi
if [ ! -f "$PROJECT_DEST/launcher.py" ]; then
    echo "ERROR: launcher.py not found in bundle"; exit 1
fi
if [ ! -d "$PROJECT_DEST/venv/bin" ]; then
    echo "ERROR: venv not found in bundle"; exit 1
fi

echo "==> Built $APP_DIR"

# ── 5. Create DMG ─────────────────────────────────────────────────
echo "==> Creating DMG..."
DMG_PATH="$DIST_DIR/$APP_NAME.dmg"
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$APP_DIR" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

echo ""
echo "==> Done!  $DMG_PATH"
ls -lh "$DMG_PATH"
