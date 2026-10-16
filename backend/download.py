"""Model library: catalogue tiers, local GGUF discovery, downloads, deletes.

Files may live anywhere under MODEL_DIR (the existing installs use per-tier
subfolders like `lite/...gguf`), so everything resolves by recursive filename
search, not by fixed path. New downloads go to `MODEL_DIR/<tier>/<file>`.

Downloads stream with progress into `_progress` so the settings popup can
poll `download_progress()`. Only catalogue tiers are listed; anything else on
disk is ignored.
"""

from __future__ import annotations

import threading
from pathlib import Path

import requests
from huggingface_hub import get_hf_file_metadata, hf_hub_download, hf_hub_url

from backend import config

# name/id -> {"downloaded": int, "total": int|None, "status": str, "error": str|None}
# status is one of queued/downloading/done/error.
_progress: dict[str, dict] = {}
_progress_lock = threading.Lock()

CUSTOM_CTX = 32768


def _tier_dir(name: str) -> Path:
    d = config.MODEL_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def local_path(name: str) -> Path:
    """Canonical destination for fresh downloads of a catalogue tier."""
    return _tier_dir(name) / config.MODELS[name]["file"]


def find_local(name: str) -> Path | None:
    """The on-disk GGUF for a catalogue tier, wherever it sits under MODEL_DIR."""
    if name not in config.MODELS:
        return None
    wanted = config.MODELS[name]["file"]
    for path in sorted(config.MODEL_DIR.rglob("*.gguf")):
        if ".cache" in path.parts:
            continue
        if path.name == wanted:
            return path
    return None


def is_downloaded(name: str) -> bool:
    return find_local(name) is not None


def library() -> list[dict]:
    """One entry per catalogue tier, with sizes and paths."""
    entries = []
    for tier, spec in config.MODELS.items():
        path = find_local(tier)
        entries.append(
            {
                "id": tier,
                "label": tier,
                "description": spec["description"],
                "downloaded": path is not None,
                "size_bytes": path.stat().st_size if path is not None else None,
                "path": str(path) if path is not None else None,
            }
        )
    return entries


_remote_cache: dict[str, int | None] = {}


def remote_size(name: str) -> int | None:
    """Published byte size of a catalogue tier, for pre-download display."""
    if name not in config.MODELS:
        return None
    if name in _remote_cache:
        return _remote_cache[name]
    spec = config.MODELS[name]
    try:
        meta = get_hf_file_metadata(spec["repo"], spec["file"])
        _remote_cache[name] = meta.size
    except Exception:
        _remote_cache[name] = None
    return _remote_cache[name]


def resolve(id: str) -> Path | None:
    """On-disk path for a catalogue tier id, else None."""
    if id in config.MODELS:
        return find_local(id)
    return None


def delete(id: str) -> bool:
    """Delete the GGUF behind an id. Returns True when a file was removed."""
    path = resolve(id)
    if path is None or not path.exists():
        return False
    path.unlink()
    return True


def download_progress() -> dict[str, dict]:
    with _progress_lock:
        return {k: dict(v) for k, v in _progress.items()}


def _set_progress(name: str, **fields) -> None:
    with _progress_lock:
        entry = _progress.setdefault(
            name, {"downloaded": 0, "total": None, "status": "queued", "error": None}
        )
        entry.update(fields)


def start_download(name: str) -> dict:
    """Begin a background download; poll download_progress() for bytes."""
    if name not in config.MODELS:
        available = ", ".join(config.MODELS)
        raise ValueError(f"Unknown model {name!r}. Available: {available}")
    if is_downloaded(name):
        _set_progress(name, status="done")
        return download_progress()[name]
    with _progress_lock:
        if _progress.get(name, {}).get("status") == "downloading":
            return dict(_progress[name])
    _set_progress(name, downloaded=0, total=None, status="queued", error=None)
    thread = threading.Thread(target=_download_worker, args=(name,), daemon=True)
    thread.start()
    return download_progress()[name]


def _download_worker(name: str) -> None:
    spec = config.MODELS[name]
    dest = local_path(name)
    tmp = dest.with_suffix(".gguf.part")
    try:
        _set_progress(name, status="downloading")
        total = remote_size(name)
        _set_progress(name, total=total)
        url = hf_hub_url(spec["repo"], spec["file"])
        with requests.get(url, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            if total is None:
                length = resp.headers.get("content-length")
                total = int(length) if length else None
                _set_progress(name, total=total)
            done = 0
            with open(tmp, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    done += len(chunk)
                    _set_progress(name, downloaded=done)
        tmp.replace(dest)
        _set_progress(name, downloaded=dest.stat().st_size, status="done")
    except Exception as exc:  # keep partial file out of the library
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        _set_progress(name, status="error", error=str(exc))


def download(name: str) -> Path:
    """Blocking download, used as a fallback when chat starts with no file.

    Prefers the recursive lookup so hand-placed files are honoured; only hits
    the network when nothing is on disk.
    """
    if name not in config.MODELS:
        available = ", ".join(config.MODELS)
        raise ValueError(f"Unknown model {name!r}. Available: {available}")
    found = find_local(name)
    if found is not None:
        return found
    spec = config.MODELS[name]
    dest = local_path(name)
    hf_hub_download(
        repo_id=spec["repo"],
        filename=spec["file"],
        local_dir=str(dest.parent),
    )
    return dest


if __name__ == "__main__":
    import sys

    for name in sys.argv[1:] or [config.DEFAULT_MODEL]:
        print(f"{name}: {download(name)}")
