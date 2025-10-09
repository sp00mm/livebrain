# LiveBrain Deployment Guide

## Architecture

The app is split into three parts:
1. **Binary** (main executable) - Updates frequently, small (~50MB)
2. **Models** (embeddings) - Downloaded once from S3, large (~600MB)
3. **Database** (user data) - Persists locally, grows with usage

**User Data Location (macOS):**
```
~/Library/Application Support/LiveBrain/
├── models/
│   └── embeddinggemma-onnx/     # Downloaded models
└── livebrain.db                  # User's indexed documents
```

All user data persists across updates and app reinstalls.

## Initial Release Workflow

### 1. Build App (without models)
```bash
chmod +x build.sh
./build.sh
```

This creates `LiveBrain-1.0.0.dmg` (~50MB) with:
- Compiled binary
- All dependencies
- NO models (downloaded separately)

### 2. Prepare Models for S3
```bash
chmod +x prepare_models.sh
./prepare_models.sh
```

This creates `embeddinggemma-onnx.zip` (~600MB)

### 3. Upload to S3
```bash
aws s3 cp embeddinggemma-onnx.zip s3://yourbucket/ --acl public-read
```

### 4. Update MODEL_URL in updater.py
```python
MODEL_URL = "https://yourbucket.s3.amazonaws.com/embeddinggemma-onnx.zip"
```

### 5. Upload App to Server
```
yourdomain.com/livebrain/
├── LiveBrain-1.0.0.dmg        # App installer (~50MB)
├── version.json                # Update manifest
└── updates/
    └── LiveBrain-1.0.1.dmg    # Future updates
```

### 6. Create version.json
```json
{
  "version": "1.0.0",
  "url": "https://yourdomain.com/livebrain/LiveBrain-1.0.0.dmg",
  "notes": "Initial release"
}
```

## First Run Experience

1. User downloads and installs `LiveBrain-1.0.0.dmg` (~50MB)
2. On first launch, app checks for models in `~/Library/Application Support/LiveBrain/`
3. If not found, prompts to download models from S3 (~600MB)
4. Models are downloaded once and persist forever
5. App is ready to use

## Update Workflow

When you need to push an update (code changes only):

### 1. Update Version
- Change `CURRENT_VERSION` in `updater.py`
- Change version in `main.py` window title
- Change `VERSION` in `build.sh`

### 2. Build Update
```bash
./build.sh
```

This builds a new DMG with only the binary (~50MB)

### 3. Upload to Server
```bash
# Upload to your server
scp LiveBrain-1.0.1.dmg user@yourdomain.com:/path/to/livebrain/updates/
```

### 4. Update version.json on Server
```json
{
  "version": "1.0.1",
  "url": "https://yourdomain.com/livebrain/updates/LiveBrain-1.0.1.dmg",
  "notes": "Bug fixes and improvements"
}
```

### 5. App Auto-Updates
- On launch, app checks `version.json`
- If new version available, prompts user
- User downloads DMG (~50MB), replaces app
- Models remain in `~/Library/Application Support/LiveBrain/` untouched

## Updating Models (Rare)

If you need to update the embedding model:

1. Prepare new model zip:
```bash
./prepare_models.sh
```

2. Upload to S3 with versioned name:
```bash
aws s3 cp embeddinggemma-onnx.zip s3://yourbucket/embeddinggemma-onnx-v2.zip --acl public-read
```

3. Update `MODEL_URL` in `updater.py` to new version
4. Users will be prompted to download new models on next launch

## Size Breakdown

**Initial Install:**
- App DMG: ~50MB
- Models (downloaded on first run): ~600MB
- Total: ~650MB

**Updates:**
- App DMG: ~50MB only
- Models: Not re-downloaded

## Distribution Options

1. **Self-hosted**: Upload DMG to your server
2. **GitHub Releases**: Free hosting for releases
3. **CDN**: CloudFront, Cloudflare R2 for fast downloads
4. **Mac App Store**: Full distribution (requires notarization)

## Notarization (Required for macOS)

To avoid "unidentified developer" warnings:
```bash
# Sign the app
codesign --force --deep --sign "Developer ID Application: Your Name" main.app

# Notarize
xcrun notarytool submit LiveBrain-1.0.0.dmg --wait

# Staple notarization
xcrun stapler staple main.app
```

Requires Apple Developer account ($99/year).

