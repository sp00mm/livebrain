# LiveBrain

A minimal document search application with local AI embeddings.

## Features

- Index local directories recursively
- Full-text search with semantic embeddings
- Supports text files, PDFs, and common formats
- All processing happens locally
- Fast vector similarity search

## Installation

Download the latest release from [yourdomain.com/livebrain](https://yourdomain.com/livebrain)

On first run, the app will download embedding models (~160MB) from Oracle Object Storage.

## Usage

1. Click "Select Directory" to choose a folder to index
2. Click "Index Directory" to scan and process all files
3. Use the search box to find documents semantically

## User Data

All user data is stored in:
```
~/Library/Application Support/LiveBrain/
├── models/                      # AI embedding models (600MB)
└── livebrain.db                 # Your indexed documents
```

### Backup Your Data

To backup your indexed documents:
```bash
cp ~/Library/Application\ Support/LiveBrain/livebrain.db ~/backup/
```

### Clear Cache

To remove all data and start fresh:
```bash
rm -rf ~/Library/Application\ Support/LiveBrain/
```

On next launch, the app will re-download models.

## Updates

The app checks for updates on launch. Updates only replace the binary (~50MB), your data and models remain untouched.

## Requirements

- macOS 14.0 or higher
- ~650MB free space for first install
- Internet connection for initial model download

## Development

See [DEVELOPMENT.md](../DEVELOPMENT.md) for build and deployment instructions.

## License

[Your License Here]

