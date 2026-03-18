# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Livebrain is a macOS menu bar application (PySide6/Qt) that provides real-time AI assistance during live conversations. It transcribes audio (mic + system), answers questions with full conversation context, and searches user files locally using embeddings. Targets macOS 14.0+.

## Common Commands

### Development
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Testing
```bash
pytest tests/                              # all unit tests
pytest tests/test_database.py              # single test file
pytest tests/test_database.py::TestClass::test_method  # single test
pytest -m e2e                              # e2e tests (require OpenAI key in keychain + ONNX model on disk)
pytest -m "not e2e"                        # skip e2e tests
```

### Build & Release
```bash
./build.sh                    # Nuitka compile → .app bundle → DMG
./build.sh --sign             # with code signing + notarization
./release.sh --bump patch     # bump version, build, update website links
```

## Architecture

### Entry Point
`main.py` → `QApplication` → `MenuBarApp` (in `menubar/`) → initializes all services then UI.

### Layer Structure

**Services** (`services/`) — core business logic:
- `database.py` — LibSQL repository pattern (BrainRepository, SessionRepository, InteractionRepository, ResourceRepository, DocumentChunkRepository, etc.)
- `query_execution.py` — orchestrates user questions: builds context, calls LLM with tools, streams responses
- `llm/` — OpenAI provider abstraction (defaults to gpt-5-chat-latest), streaming via callbacks
- `tools.py` — tool registry for AI function calling (`search_files`, `read_file`)
- `prompt.py` — composable system prompt builder (SystemPromptBuilder, ToolContext)
- `embedder.py` — local ONNX embeddings (embeddinggemma, 768-dim vectors)
- `scanner.py` — text extraction from PDF, DOCX, XLSX, PPTX, TXT, code files
- `audio_service.py` — mic/system audio capture orchestration
- `whisper_service.py` — Whisper API fallback for batch transcription
- `conversation.py` — in-memory conversation context cache

**Audio** (`audio/`) — macOS audio pipeline:
- `capture/` — `MacOSMicCapture`, `MacOSSystemCapture` (PyObjC: AVFoundation, ScreenCaptureKit)
- `transcription/` — Apple Speech Recognition for real-time local transcription
- `storage.py` — audio file management

**UI** (`ui/`) — PySide6 interface:
- `widgets/` — views (LiveView, ChatFeed, BrainEditView, SessionHistoryView, SettingsView, etc.)
- `threads/` — QThread subclasses for async I/O (AudioThread, QueryThread, IndexThread, WhisperThread, ModelDownloadThread, UpdateThread)
- `styles.py` — shared styling
- `markdown_renderer.py` — markdown to HTML for chat display

**Data Models** (`models/__init__.py`) — dataclasses: Brain, Session, TranscriptEntry, Interaction, Resource, DocumentChunk, ToolCallRecord, ChatFeedItem

**Database** (`db/`):
- `schema.sql` — full schema definition
- `migrations/` — numbered SQL migrations (001_initial, 002_add_session_rating, etc.)

**Templates** (`templates.py`) — 5 built-in conversation templates (Interview, Stand-up, Sales Call, Live Debate, Lecture) with steps and preset questions

### Key Patterns
- **Repository pattern** for all data access through typed repositories in `database.py`
- **Qt signal/slot** for async communication between threads and UI
- **Streaming callbacks** — LLM responses streamed via `on_delta` callbacks
- **Tool calling** — OpenAI function calling with a custom tool registry; RAG search is forced before answering
- **Threading** — dedicated QThread subclasses for audio, queries, indexing, etc.

### Data Flow for User Questions
1. User submits question → `QueryThread` started
2. `QueryExecutionService` builds system prompt via `SystemPromptBuilder`
3. If brain has folders attached, seeds conversation with file citations from RAG
4. LLM called with tools (`search_files`, `read_file`) — tool calls executed in loop
5. Final response streamed back via callbacks → rendered in ChatFeed

### Version Management
Single source of truth: `version.json`. Updated automatically by `release.sh`.

### User Data (Runtime)
```
~/Library/Application Support/Livebrain/
├── livebrain.db                    # SQLite database
├── recordings/                     # Audio files
└── models/embeddinggemma-onnx/     # ONNX model (~160MB, downloaded on first launch)
```

### Secrets
OpenAI API key stored in macOS Keychain via `keyring` library (see `services/secrets.py`).
