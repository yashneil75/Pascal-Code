# Pascal Code Desktop — React + Python hybrid

Desktop chat app. React (Vite) frontend, Python (FastAPI + llama.cpp) backend,
Electron frameless shell.

```
Pascal-Code-Desktop/
  backend/          Python API: app.py (FastAPI), config.py, store.py,
                    model.py, download.py, requirements.txt
    test_store.py   SQLite store tests (15 tests)
  backend_main.py   PyInstaller entry point (freezes backend/ to an exe)
  frontend/         React + Vite app (src/, public/fonts/, dist/ after build)
  electron/         main.cjs (window + backend sidecar), preload.cjs (bridge)
  dist-backend/     Frozen backend (build artifact, not in git)
  release/          Installer + portable exe (build artifact, not in git)
```

## The real desktop app (installer / portable exe)

No browser, no localhost tabs. One command builds everything:

```
npm run dist
```

That does three steps: `frontend:build` (React → `frontend/dist/`),
`backend:build` (PyInstaller freezes Python → `dist-backend/pascal-backend/`),
then electron-builder packages both into `release/`:

- `Pascal-Code-0.1.0-setup.exe` — installer (Start Menu shortcut, uninstaller)
- `Pascal-Code-0.1.0-portable.exe` — single file, runs anywhere

Double-click either: one Pascal Code window opens, the frozen backend starts
silently beside it and is killed on quit. Single-instance: launching again
just focuses the existing window.

Model weights are NOT bundled (they are GBs). On first run the app uses the
mock model; download weights once per machine and restart:

```
python -m backend.download lite
```

Weights and chats live in `%USERPROFILE%\.pascal_code`, shared by dev and
packaged runs.

## Dev (browser-free too)

`npm run dev` opens the Electron window, not a browser tab: it starts the
Python backend, the Vite server, then Electron pointed at Vite. The
`frontend:dev` script alone is the only thing that serves localhost for
plain-browser debugging.

Real model replies: download weights once (`python -m backend.download lite`),
then run without `PASCAL_MOCK`. Without weights (or with `PASCAL_MOCK=1`) the
backend streams the same canned replies the old frontend used, and the UI
shows a "mock model" badge.

## API

- `GET /api/health`, `GET /api/models`, `POST /api/models/select`
- `GET /api/projects`, `POST /api/projects/open`, `POST /api/projects/delete`
- `GET /api/history`, `GET /api/conversations`, `POST /api/conversations/new`
- `POST /api/conversations/{id}/open`, `DELETE /api/conversations/{id}`
- `GET /api/settings`, `PUT /api/settings/{key}`
- `POST /api/chat` (full JSON reply), `POST /api/chat/stream` (SSE tokens + `[DONE]`)

Folder picking lives in Electron (`dialog:open-folder`); the Python
`browse()` from the pywebview days is gone. Window controls go through the
preload bridge (`window.electron`), and the drag region uses `-webkit-app-region`.

## Notes vs the old app

- `ui.py` Api methods map 1:1 to REST endpoints; the write-ordering queue the
  old JS kept is unnecessary now — the backend persists user/assistant turns.
- Streaming pause/resume became Stop (abort): a real LLM cannot resume a
  cancelled generation, so the button aborts the SSE fetch instead.
- Model switching now hits the backend (`POST /api/models/select`); the old
  picker only changed a label.
- `frontend/index.html` single-file build was split into `App.jsx` +
  `components/` + `hooks/` + `styles.css` with identical class names.
