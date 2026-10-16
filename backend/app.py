"""FastAPI backend for the Pascal Code desktop app.

Replaces ui.py's pywebview Api with HTTP + SSE so a React frontend (served by
Vite in dev, by Electron from dist/ in prod) can drive the same SQLite store
and the same llama.cpp models.

Run:  python -m backend.app            -> http://127.0.0.1:8000
       PASCAL_PORT=8001 python -m backend.app
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend import config
from backend.model import manager
from backend.store import Store

log = logging.getLogger("pascal.backend")

app = FastAPI(title="Pascal Code backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # desktop app on localhost; tightened in prod builds
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = Store()
_state_lock = threading.Lock()
_project = str(config.WORKSPACE)
store.ensure_project(_project)
_conversation: int | None = store.newest(_project)
_model_name = config.DEFAULT_MODEL
manager.select(_model_name)


# --- schemas ---------------------------------------------------------------

class OpenProjectBody(BaseModel):
    path: str


class DeleteProjectBody(BaseModel):
    path: str


class ChatBody(BaseModel):
    content: str


class SelectModelBody(BaseModel):
    name: str


class SettingBody(BaseModel):
    value: Any


# --- helpers ---------------------------------------------------------------

def _get_project() -> str:
    with _state_lock:
        return _project


def _get_conversation() -> int | None:
    with _state_lock:
        return _conversation


def _set_project(path: str) -> int | None:
    global _project, _conversation
    store.ensure_project(path)
    newest = store.newest(path)
    with _state_lock:
        _project = path
        _conversation = newest
    return newest


def _ensure_conversation() -> int:
    global _conversation
    with _state_lock:
        conv = _conversation
        project = _project
    if conv is None:
        conv = store.new_conversation(project)
        with _state_lock:
            _conversation = conv
    return conv


def _setting(key: str, default):
    stored = store.setting(key)
    return default if stored is None else json.loads(stored)


# --- routes ----------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/models")
def get_models() -> dict:
    status = manager.status()
    return {"current": status["current"], "tiers": status["tiers"],
            "running": status["running"], "loading": status["loading"],
            "mock": status["mock"]}


@app.post("/api/models/select")
def select_model(body: SelectModelBody) -> dict:
    try:
        return manager.select(body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/models/load")
def load_model() -> dict:
    """Warm up the current model in the background (first load is slow)."""
    return manager.load_in_background()


@app.get("/api/models/library")
def get_library() -> dict:
    """Every tier plus hand-placed GGUFs, with sizes, current, and load state."""
    from backend import download as download_mod

    status = manager.status()
    entries = download_mod.library()
    for entry in entries:
        if not entry["downloaded"]:
            entry["remote_bytes"] = download_mod.remote_size(entry["id"])
    return {
        "current": status["current"],
        "running": status["running"],
        "loading": status["loading"],
        "mock": status["mock"],
        "models": entries,
    }


@app.post("/api/models/download")
def start_model_download(body: SelectModelBody) -> dict:
    from backend import download as download_mod

    try:
        return download_mod.start_download(body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/models/download/progress")
def download_progress() -> dict:
    from backend import download as download_mod

    return {"downloads": download_mod.download_progress()}


@app.delete("/api/models/library/{model_id:path}")
def delete_model(model_id: str) -> dict:
    from backend import download as download_mod

    if model_id == manager.status()["current"]:
        raise HTTPException(status_code=400, detail="Cannot delete the active model")
    if not download_mod.delete(model_id):
        raise HTTPException(status_code=404, detail="Model file not found")
    return {"deleted": model_id}


@app.get("/api/projects")
def get_projects() -> dict:
    project = _get_project()
    return {
        "current": project,
        "workspace": str(config.WORKSPACE),
        "projects": [
            {"path": path, "name": Path(path).name or path}
            for path in store.projects()
        ],
    }


@app.post("/api/projects/open")
def open_project(body: OpenProjectBody) -> dict:
    _set_project(body.path)
    return {"current": body.path, "conversation": _get_conversation()}


@app.post("/api/projects/delete")
def delete_project(body: DeleteProjectBody) -> dict:
    if body.path == str(config.WORKSPACE):
        raise HTTPException(status_code=400, detail="The workspace folder cannot be deleted")
    store.delete_project(body.path)
    if body.path == _get_project():
        _set_project(str(config.WORKSPACE))
    return {"current": _get_project()}


@app.get("/api/history")
def get_history() -> dict:
    conv = _get_conversation()
    if conv is None:
        return {"messages": [], "conversation": None}
    return {"messages": store.load(conv), "conversation": conv}


@app.get("/api/conversations")
def get_conversations() -> dict:
    return {"current": _get_conversation(), "chats": store.summaries()}


@app.post("/api/conversations/new")
def new_chat() -> dict:
    global _conversation
    with _state_lock:
        _conversation = None
    return {"conversation": None}


@app.post("/api/conversations/{conversation_id}/open")
def open_chat(conversation_id: int) -> dict:
    global _conversation, _project
    with _state_lock:
        _conversation = conversation_id
    project = store.project_of(conversation_id)
    if project is not None:
        with _state_lock:
            _project = project
    return {"conversation": conversation_id, "project": _get_project()}


@app.delete("/api/conversations/{conversation_id}")
def delete_chat(conversation_id: int) -> dict:
    global _conversation
    store.delete_conversation(conversation_id)
    with _state_lock:
        if conversation_id == _conversation:
            _conversation = None
        current = _conversation
    return {"conversation": current}


@app.get("/api/settings")
def get_settings() -> dict:
    return {"confirm_delete": _setting("confirm_delete", True)}


@app.put("/api/settings/{key}")
def put_setting(key: str, body: SettingBody) -> dict:
    store.set_setting(key, json.dumps(body.value))
    return {"key": key, "value": body.value}


@app.post("/api/chat")
def chat(body: ChatBody) -> dict:
    """Non-streaming fallback: full reply as JSON (tests, curl, scripting)."""
    text = body.content.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message")
    conv = _ensure_conversation()
    store.append(conv, {"role": "user", "content": text})
    model = manager.ensure()
    loop = asyncio.new_event_loop()
    try:
        if hasattr(model, "_llm") or type(model).__name__ == "Model":
            # llama_cpp streams synchronously; collect in a worker thread.
            parts: list[str] = []
            def _run():
                for tok in model.send_message(text):
                    parts.append(tok)
            t = threading.Thread(target=_run, daemon=True)
            t.start()
            t.join()
            reply = "".join(parts)
        else:
            reply = "".join(model.send_message(text))
    finally:
        loop.close()
    store.append(conv, {"role": "assistant", "content": reply})
    return {"reply": reply, "conversation": conv}


@app.post("/api/chat/stream")
def chat_stream(body: ChatBody):
    """SSE stream: `data: {\"token\": ...}` events, then `data: [DONE]`."""
    text = body.content.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message")
    conv = _ensure_conversation()
    store.append(conv, {"role": "user", "content": text})

    def event_stream():
        model = manager.ensure()
        parts: list[str] = []
        try:
            for token in model.send_message(text):
                parts.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as exc:  # stream the error so the UI can show it
            log.exception("chat stream failed")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            full = "".join(parts)
            if full:
                try:
                    store.append(conv, {"role": "assistant", "content": full})
                except Exception:
                    log.exception("could not persist assistant reply")
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def main() -> None:
    import multiprocessing

    import uvicorn

    multiprocessing.freeze_support()  # no-op unless frozen (PyInstaller on Windows)
    print(f"Pascal Code backend on http://127.0.0.1:{config.PORT}", flush=True)
    # Pass the app object (not an import string) so frozen executables,
    # which have no normal import system, can still serve.
    uvicorn.run(app, host="127.0.0.1", port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()
