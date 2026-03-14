#!/bin/bash

SIGN=false
if [ "$1" = "--sign" ]; then
    SIGN=true
fi

# Read version from version.json (single source of truth)
VERSION=$(grep '"version"' version.json | cut -d'"' -f4)

echo "Building Livebrain v${VERSION}..."

# Clean up previous build (keep main.build for cache)
echo "Cleaning up previous build..."
rm -rf main.app Livebrain.app main.dist Livebrain-*.dmg 2>/dev/null

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
  --nofollow-import-to=models \
  --static-libpython=no \
  --include-data-files=version.json=version.json \
  --include-data-dir=resources=resources \
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

# Set LSUIElement to hide dock icon (menu bar app only)
echo "Setting LSUIElement for menu bar app..."
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" Livebrain.app/Contents/Info.plist 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :LSUIElement true" Livebrain.app/Contents/Info.plist

echo "Creating DMG (without models)..."
create-dmg \
  --volname "Livebrain" \
  --window-size 500 320 \
  --icon-size 80 \
  --icon "Livebrain.app" 125 160 \
  --app-drop-link 375 160 \
  "Livebrain-${VERSION}.dmg" \
  "Livebrain.app"

if [ "$SIGN" = true ]; then
    IDENTITY="Developer ID Application: Genfit LLC (VWVKXWHBS8)"

    echo "Signing all binaries inside app bundle..."
    find Livebrain.app -type f \( -name '*.so' -o -name '*.dylib' \) | while read f; do
        codesign --force --options runtime --timestamp --sign "$IDENTITY" "$f"
    done

    echo "Signing app bundle..."
    codesign --force --options runtime --timestamp --sign "$IDENTITY" Livebrain.app

    echo "Signing DMG..."
    codesign --force --timestamp --sign "$IDENTITY" "Livebrain-${VERSION}.dmg"

    # One-time setup: xcrun notarytool store-credentials "livebrain-notary" --apple-id YOUR_APPLE_ID --team-id VWVKXWHBS8
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
echo "Note: Models are already uploaded to Oracle Object Storage"
echo "Users will download models on first launch from:"
echo "  https://objectstorage.us-chicago-1.oraclecloud.com/n/axa3tfnfy6dd/b/livebrain-models/o/embeddinggemma-onnx.zip"

