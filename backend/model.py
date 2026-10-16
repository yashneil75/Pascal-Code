"""Local LLM wrapper with a mock fallback for UI work.

Real path mirrors the old top-level model.py: lazy-load the GGUF file for the
selected tier via llama_cpp and stream chat completions token by token.

Mock path is used when PASCAL_MOCK=1 or when the model file has not been
downloaded yet (unless PASCAL_STRICT=1). It yields the same canned replies the
old frontend used, word by word, so the React SSE pipeline works with no
multi-GB download.
"""

from __future__ import annotations

import threading
import time
from typing import Iterator

from backend import config
from backend import download as download_mod


MOCK_REPLIES = [
    "Here's how I'd approach that. Keep the parsing in one place so the rest of the code never sees raw file text, then validate at that boundary so bad input fails early with a clear message instead of surfacing three layers down.",
    "That's the guard, not the caller. The check runs on the trimmed value but the write uses the original, so trailing whitespace slips straight through. Trim once at the top and both paths agree.",
    "I'd split this in two steps: load and normalise the config first, then build the model from it. That way a bad config fails before you pay for anything expensive, and the picker reads the same list the loader does.",
]


def should_mock(name: str) -> bool:
    if config.MOCK_ENV:
        return True
    if config.STRICT_ENV:
        return False
    try:
        return not download_mod.is_downloaded(name)
    except Exception:
        return True


class MockModel:
    """Stand-in that streams canned replies word by word."""

    def __init__(self, name: str = config.DEFAULT_MODEL):
        self.name = name
        self._n = 0

    @property
    def is_running(self) -> bool:
        return True

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def send_message(self, message: str) -> Iterator[str]:
        # Keep parity with Model: record nothing here; app.py owns history.
        reply = MOCK_REPLIES[self._n % len(MOCK_REPLIES)]
        self._n += 1
        for word in reply.split(" "):
            yield word + " "
            time.sleep(0.02)


class Model:
    def __init__(self, name: str = config.DEFAULT_MODEL):
        if name not in config.MODELS:
            available = ", ".join(config.MODELS)
            raise ValueError(f"Unknown model {name!r}. Available: {available}")
        self.name = name
        self.spec = config.MODELS[name]
        self._llm = None
        self._messages: list[dict] = []
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._llm is not None

    def start(self) -> None:
        if self._llm is not None:
            return
        from llama_cpp import Llama

        model_path = download_mod.download(self.name)
        kv_quant = self.spec["kv_quant"]
        self._llm = Llama(
            model_path=str(model_path),
            n_ctx=self.spec["ctx"],
            n_gpu_layers=-1,
            flash_attn=self.spec["flash_attn"],
            type_k=kv_quant,
            type_v=kv_quant,
            verbose=False,
        )

    def stop(self) -> None:
        if self._llm is None:
            return
        self._llm.close()
        self._llm = None

    def send_message(self, message: str) -> Iterator[str]:
        if self._llm is None:
            raise RuntimeError("Model is not running. Call start() first.")
        with self._lock:
            self._messages.append({"role": "user", "content": message})
            history = list(self._messages)
        stream = self._llm.create_chat_completion(
            messages=history,
            temperature=self.spec["temp"],
            stream=True,
        )
        parts: list[str] = []
        for chunk in stream:
            delta = chunk["choices"][0]["delta"].get("content")
            if delta:
                parts.append(delta)
                yield delta
        with self._lock:
            self._messages.append({"role": "assistant", "content": "".join(parts)})


class ModelManager:
    """One current tier with lazy start and clean switching."""

    def __init__(self, name: str = config.DEFAULT_MODEL):
        self._lock = threading.Lock()
        self.name = name
        self._model: Model | MockModel | None = None
        self._mock_name: str | None = None

    def _build(self, name: str) -> Model | MockModel:
        if should_mock(name):
            return MockModel(name)
        return Model(name)

    def select(self, name: str) -> dict:
        if name not in config.MODELS:
            available = ", ".join(config.MODELS)
            raise ValueError(f"Unknown model {name!r}. Available: {available}")
        with self._lock:
            if self._model is not None and name == self.name:
                return self.status_locked()
            if self._model is not None:
                try:
                    self._model.stop()
                except Exception:
                    pass
                self._model = None
            self.name = name
            return self.status_locked()

    def status_locked(self) -> dict:
        model = self._model
        return {
            "current": self.name,
            "running": bool(model is not None and model.is_running),
            "mock": isinstance(model, MockModel)
            or (model is None and should_mock(self.name)),
            "tiers": [
                {"name": tier, "description": spec["description"]}
                for tier, spec in config.MODELS.items()
            ],
        }

    def status(self) -> dict:
        with self._lock:
            return self.status_locked()

    def ensure(self):
        """Return a started model, building/starting it on first use."""
        with self._lock:
            if self._model is None:
                self._model = self._build(self.name)
            model = self._model
        # start() can block for seconds; run outside the manager lock.
        model.start()
        return model


manager = ModelManager()
