#!/bin/bash

VERSION="1.0.0"

echo "Building LiveBrain v${VERSION}..."

# Clean up previous build
echo "Cleaning up previous build..."
rm -rf main.app main.dist main.build LiveBrain-*.dmg 2>/dev/null

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
  --macos-app-name="LiveBrain" \
  --macos-app-version="${VERSION}" \
  --nofollow-import-to=models \
  main.py

# Check if build succeeded
if [ ! -d "main.app" ]; then
    echo ""
    echo "❌ Build failed! Make sure:"
    echo "  1. Virtual environment is activated: source venv/bin/activate"
    echo "  2. Nuitka is installed: pip install nuitka"
    echo "  3. PySide6 is installed: pip install PySide6"
    exit 1
fi

# Remove models from the built app if they were included
echo "Removing models from bundle..."
rm -rf main.app/Contents/MacOS/models 2>/dev/null || true

echo "Creating DMG (without models)..."
hdiutil create -volname "LiveBrain" -srcfolder main.app -ov -format UDZO "LiveBrain-${VERSION}.dmg"

echo ""
echo "✅ Build complete: LiveBrain-${VERSION}.dmg"
echo "DMG size: $(du -h LiveBrain-${VERSION}.dmg | cut -f1)"
echo ""
echo "Next steps:"
echo "  cd ../scripts && ./deploy-app.sh"
echo ""
echo "Note: Models are already uploaded to Oracle Object Storage"
echo "Users will download models on first launch from:"
echo "  https://objectstorage.us-chicago-1.oraclecloud.com/n/axa3tfnfy6dd/b/livebrain-models/o/embeddinggemma-onnx.zip"

