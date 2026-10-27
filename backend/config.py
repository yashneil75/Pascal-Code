"""Shared paths and model catalogue for the Pascal Code backend.

Same values as the old top-level config.py; now importable as backend.config
so both the FastAPI app and the model/store helpers share one source of truth.
"""

from __future__ import annotations

import os
from pathlib import Path

from llama_cpp import llama_cpp

MODEL_DIR = Path(os.environ.get("PASCAL_MODEL_DIR", Path.home() / ".pascal_code"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Where chats go when no project folder has been picked.
WORKSPACE = MODEL_DIR / "workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)

# Port the API listens on. Electron spawns the backend with a free port and
# passes it as PASCAL_PORT; `python -m backend.app` falls back to 8000.
PORT = int(os.environ.get("PASCAL_PORT", "8000"))

# When true, chat replies use a canned mock instead of loading GGUF weights.
# Useful for UI work without a multi-GB download. Automatically enabled when
# the selected model file is not on disk (unless PASCAL_STRICT=1).
MOCK_ENV = os.environ.get("PASCAL_MOCK", "").lower() in ("1", "true", "yes")
STRICT_ENV = True # no longer used so just set to True(no canned responses), but kept for backwards compatibility with old env vars

MODELS = {
    "lite": {
        "repo": "bartowski/Ling-3.0-tiny-GGUF",
        "file": "Ling-3.0-tiny-Q4_K_M.gguf",
        "temp": 0.7,
        "ctx": 100000,
        "kv_quant": llama_cpp.GGML_TYPE_Q4_0,
        "flash_attn": True,
        "description": "100K ctx • 8GB VRAM or 12GB RAM • Fastest for general work",
    },
    "medium": {
        "repo": "ConwayResearch/Underdog-Saluki-27B-1.0",
        "file": "Underdog-Saluki-27B-1.0-IQ2-mix.gguf",
        "temp": 0.7,
        "ctx": 100000,
        "kv_quant": llama_cpp.GGML_TYPE_Q4_0, 
        "flash_attn": True,
        "description": "100K ctx • 12GB VRAM or 16GB RAM • Strong performance for demanding tasks",
    },
    "pro": {
        "repo": "ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF",
        "file": "Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf",
        "temp": 0.7,
        "ctx": 200000,
        "kv_quant": llama_cpp.GGML_TYPE_Q8_0,
        "flash_attn": True,
        "description": "200K ctx • At least 16GB VRAM or 20GB RAM • Highest performance for the most demanding tasks",
    },
}

DEFAULT_MODEL = "lite"
