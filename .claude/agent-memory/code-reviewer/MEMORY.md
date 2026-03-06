# Code Reviewer Memory

## Project Conventions (confirmed)
- Single quotes for all strings
- No try/except, no defensive coding — let failures be loud
- Dict lookups should use `[]` not `.get()` with fallback unless None is a valid expected value
- No hardcoded hex colors — always use constants from `ui/styles.py`
- All used style constants must be explicitly imported from `ui.styles`
- `mousePressEvent` override via lambda assignment is acceptable (seen in live_view.py)
- No docstrings or comments unless non-obvious

## Style Constants Reference
- `BG_PRIMARY = '#1e1e1e'`
- `BG_SECONDARY = '#2a2a2a'`
- `BG_CARD = '#252525'`
- `FEED_DIVIDER = '#3a3a3a'`
- `ERROR_COLOR = '#ff6b6b'`
- `TEXT_SECONDARY = '#888888'`
- `AUDIT_STEP_COLOR = '#888888'`

## Common Regression Pattern
When a worktree is based on an older branch snapshot, `styles.py` can drift backward.
Always diff `styles.py` against main — QComboBox polish (`outline: none`, `::item` selector) was added post-initial and can be silently reverted.

## Key Files
- `app/ui/styles.py` — all color/style constants
- `app/ui/widgets/audit_view.py` — audit window widget
- `app/services/database.py` — all repositories
- `app/models/__init__.py` — all dataclasses/enums
