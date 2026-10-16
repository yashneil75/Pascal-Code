"""Model catalogue helpers: local paths and HuggingFace downloads."""

from __future__ import annotations

from pathlib import Path

from huggingface_hub import hf_hub_download

from backend import config


def local_path(name: str) -> Path:
    return config.MODEL_DIR / config.MODELS[name]["file"]


def is_downloaded(name: str) -> bool:
    return local_path(name).exists()


def download(name: str) -> Path:
    if name not in config.MODELS:
        available = ", ".join(config.MODELS)
        raise ValueError(f"Unknown model {name!r}. Available: {available}")
    spec = config.MODELS[name]
    hf_hub_download(
        repo_id=spec["repo"],
        filename=spec["file"],
        local_dir=str(config.MODEL_DIR),
    )
    return local_path(name)


if __name__ == "__main__":
    import sys

    for name in sys.argv[1:] or [config.DEFAULT_MODEL]:
        print(f"{name}: {download(name)}")
