#!/bin/bash

VERSION="1.0.0"

echo "Building LiveBrain v${VERSION}..."

python -m nuitka --standalone \
  --macos-create-app-bundle \
  --enable-plugin=pyside6 \
  --macos-app-name="LiveBrain" \
  --macos-app-version="${VERSION}" \
  main.py

echo "Creating DMG (without models)..."
hdiutil create -volname "LiveBrain" -srcfolder main.app -ov -format UDZO "LiveBrain-${VERSION}.dmg"

echo "Build complete: LiveBrain-${VERSION}.dmg"
echo "DMG size: $(du -h LiveBrain-${VERSION}.dmg | cut -f1)"
echo ""
echo "Next steps:"
echo "1. Upload LiveBrain-${VERSION}.dmg to your server"
echo "2. Zip models folder and upload to S3:"
echo "   cd models && zip -r ../embeddinggemma-onnx.zip embeddinggemma-onnx/"
echo "   aws s3 cp embeddinggemma-onnx.zip s3://yourbucket/"

