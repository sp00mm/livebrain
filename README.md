# Livebrain

Real-time AI for live conversations. A macOS menu bar app that transcribes meetings in real-time, answers questions about the conversation, and searches your files.

[Download](https://livebrain.app) | [Website](https://livebrain.app)

## Features

- **Live transcription** — Captures mic and system audio from any app (Zoom, Meet, Teams, Slack)
- **Ask questions** — Click presets or type your own. AI understands the full conversation context
- **Search your files** — Attach folders and search documents during conversations
- **On-device transcription** — Apple Speech runs locally. No audio leaves your Mac
- **5 built-in templates** — Interview, stand-up, sales call, debate, lecture
- **Menu bar native** — Lives in your status bar. No dock icon, no clutter

## Install

Download the latest DMG from [livebrain.app](https://livebrain.app). Requires macOS 14+.

On first launch, the app downloads embedding models (~160MB) for local file search.

## Development

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py
```

Run tests:
```bash
pytest tests/
```

Build DMG:
```bash
pip install nuitka
./build.sh
```

## How it works

1. Click the brain icon in your menu bar to open Livebrain
2. Select or create a brain (workspace) for your meeting type
3. Hit record — transcription starts immediately
4. Ask questions or click presets while recording
5. Attach folders to search your documents during the conversation

## User data

All data stays on your Mac:
```
~/Library/Application Support/Livebrain/
  models/          # AI embedding models
  livebrain.db     # Your data
  recordings/      # Audio files
```

API keys are stored in macOS Keychain.

## Requirements

- macOS 14.0+
- OpenAI API key (for AI responses)
- ~800MB free space (models + app)

## License

[MIT](LICENSE)
