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
STRICT_ENV = True

MODELS = {
    "lite": {
        "repo": "bartowski/Ling-3.0-tiny-GGUF",
        "file": "Ling-3.0-tiny-Q4_K_M.gguf",
        "temp": 0.7,
        "ctx": 100000,
        "kv_quant": llama_cpp.GGML_TYPE_Q4_0,
        "flash_attn": True,
        "description": "100K ctx • 8GB VRAM or 12GB RAM",
    },
    "medium": {
        "repo": "ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF",
        "file": "Qwen3.8-27B-GSQ-RCO-IQ2_S-mtp.gguf",
        "temp": 0.7,
        "ctx": 100000,
        "kv_quant": llama_cpp.GGML_TYPE_Q4_0,
        "flash_attn": True,
        "description": "100K ctx • 12GB VRAM or 16GB RAM",
    },
    "pro": {
        "repo": "unsloth/Qwen3.8-27B-GGUF",
        "file": "Qwen3.8-27B-UD-IQ3_XXS.gguf",
        "temp": 0.7,
        "ctx": 200000,
        "kv_quant": llama_cpp.GGML_TYPE_Q8_0,
        "flash_attn": True,
        "description": "200K ctx • At least 16GB VRAM or 20GB RAM",
    },
    "pro+": {
        "repo": "unsloth/Qwen3.8-27B-GGUF",
        "file": "Qwen3.8-27B-UD-Q4_K_M.gguf",
        "temp": 0.7,
        "ctx": 512000,
        "kv_quant": llama_cpp.GGML_TYPE_Q8_0,
        "flash_attn": True,
        "description": "512K ctx • At least 24GB VRAM or 28GB RAM",
    },
}

DEFAULT_MODEL = "lite"
