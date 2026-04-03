#!/bin/bash
set -e

SIGN=false
if [ "$1" = "--sign" ]; then
    SIGN=true
fi

# Read version from version.json (single source of truth)
VERSION=$(grep '"version"' version.json | cut -d'"' -f4)

echo "Building Livebrain v${VERSION}..."

# Clean up previous build (keep main.build for cache)
echo "Cleaning up previous build..."
rm -rf main.app Livebrain.app main.dist 2>/dev/null || true
rm -f Livebrain-*.dmg 2>/dev/null || true

# Use virtual environment Python directly
if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
    echo "Using virtual environment Python"
else
    PYTHON="python3"
    echo "Warning: Using system Python (venv not found)"
fi

# Build with nuitka, excluding models directory
$PYTHON -m nuitka --standalone \
  --macos-create-app-bundle \
  --enable-plugin=pyside6 \
  --macos-app-icon=resources/icon.icns \
  --macos-app-name="Livebrain" \
  --macos-app-version="${VERSION}" \
  --nofollow-import-to=AppKit \
  --nofollow-import-to=Foundation \
  --nofollow-import-to=CoreFoundation \
  --nofollow-import-to=objc \
  --nofollow-import-to=PyObjCTools \
  --nofollow-import-to=Cocoa \
  --nofollow-import-to=AVFoundation \
  --nofollow-import-to=AVFAudio \
  --nofollow-import-to=CoreAudio \
  --nofollow-import-to=CoreMedia \
  --nofollow-import-to=ScreenCaptureKit \
  --nofollow-import-to=Quartz \
  --nofollow-import-to=HIServices \
  --nofollow-import-to=Speech \
  --no-deployment-flag=excluded-module-usage \
  --static-libpython=no \
  --include-data-files=version.json=version.json \
  --include-data-dir=resources=resources \
  --include-data-dir=db=db \
  main.py

# Rename app bundle
mv main.app Livebrain.app

# Check if build succeeded
if [ ! -d "Livebrain.app" ]; then
    echo ""
    echo "❌ Build failed! Make sure:"
    echo "  1. Virtual environment is activated: source venv/bin/activate"
    echo "  2. Nuitka is installed: pip install nuitka"
    echo "  3. PySide6 is installed: pip install PySide6"
    exit 1
fi

# Remove models from the built app if they were included
echo "Removing models from bundle..."
rm -rf Livebrain.app/Contents/MacOS/models 2>/dev/null || true

# Copy PyObjC packages to Resources (excluded from compilation, needed at runtime)
echo "Bundling PyObjC frameworks..."
SITE_PACKAGES="venv/lib/$($PYTHON -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")')/site-packages"
PYOBJC_DIR="Livebrain.app/Contents/Resources/pyobjc"
mkdir -p "$PYOBJC_DIR"
for pkg in objc PyObjCTools AppKit Foundation CoreFoundation Cocoa AVFoundation AVFAudio CoreAudio CoreMedia ScreenCaptureKit Quartz HIServices Speech; do
    if [ -d "$SITE_PACKAGES/$pkg" ]; then
        cp -R "$SITE_PACKAGES/$pkg" "$PYOBJC_DIR/"
    fi
done
find "$PYOBJC_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Set LSUIElement to hide dock icon (menu bar app only)
echo "Setting LSUIElement for menu bar app..."
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" Livebrain.app/Contents/Info.plist 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :LSUIElement true" Livebrain.app/Contents/Info.plist

if [ "$SIGN" = true ]; then
    IDENTITY="${CODESIGN_IDENTITY:?Set CODESIGN_IDENTITY env var for code signing}"

    echo "Signing all Mach-O binaries inside app bundle..."
    find Livebrain.app -type f | while read f; do
        if file "$f" | grep -q 'Mach-O'; then
            codesign --force --options runtime --timestamp --entitlements entitlements.plist --sign "$IDENTITY" "$f"
        fi
    done

    echo "Signing app bundle..."
    codesign --deep --force --options runtime --timestamp --entitlements entitlements.plist --sign "$IDENTITY" Livebrain.app
fi

echo "Creating DMG..."
create-dmg \
  --volname "Livebrain Installer" \
  --window-size 500 320 \
  --icon-size 80 \
  --icon "Livebrain.app" 125 160 \
  --app-drop-link 375 160 \
  "Livebrain-${VERSION}.dmg" \
  "Livebrain.app"

if [ "$SIGN" = true ]; then
    echo "Signing DMG..."
    codesign --force --timestamp --sign "$IDENTITY" "Livebrain-${VERSION}.dmg"

    echo "Submitting for notarization..."
    xcrun notarytool submit "Livebrain-${VERSION}.dmg" --keychain-profile "livebrain-notary" --wait

    echo "Stapling notarization ticket..."
    xcrun stapler staple "Livebrain-${VERSION}.dmg"
fi

echo ""
echo "✅ Build complete: Livebrain-${VERSION}.dmg"
echo "DMG size: $(du -h Livebrain-${VERSION}.dmg | cut -f1)"
echo ""
echo "Next steps:"
echo "  cd ../scripts && ./deploy-app.sh"
echo ""
echo "Note: Models are hosted on Firebase Storage"
echo "Users download models on first launch automatically"

