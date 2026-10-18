"""Local LLM wrapper.

Real path mirrors the old top-level model.py: lazy-load the GGUF file for the
selected tier via llama_cpp and stream chat completions token by token.
"""

from __future__ import annotations

import threading
from typing import Iterator

from backend import config
from backend import download as download_mod


def spec_for(id: str) -> dict:
    """Catalogue spec for a tier id; raises for anything else."""
    if id in config.MODELS:
        return config.MODELS[id]
    available = ", ".join(config.MODELS)
    raise ValueError(f"Unknown model {id!r}. Available: {available}")


class Model:
    """A real GGUF behind a catalogue tier id."""

    def __init__(self, id: str = config.DEFAULT_MODEL):
        self.name = id
        self.spec = spec_for(id)
        self._llm = None
        self._messages: list[dict] = []
        self._gen = 0  # bumped whenever history is replaced; stale streams drop out
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._llm is not None

    def start(self) -> None:
        if self._llm is not None:
            return
        from llama_cpp import Llama

        path = download_mod.resolve(self.name)
        if path is None:
            if self.name in config.MODELS:
                path = download_mod.download(self.name)
            else:
                raise RuntimeError(f"Model file for {self.name!r} is not on disk")
        kv_quant = self.spec["kv_quant"]
        self._llm = Llama(
            model_path=str(path),
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

    def get_history(self) -> list[dict]:
        with self._lock:
            return list(self._messages)

    def set_history(self, messages: list[dict]) -> None:
        clean = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m.get("role") in ("system", "user", "assistant")
            and isinstance(m.get("content"), str)
        ]
        with self._lock:
            self._messages = clean
            self._gen += 1

    def reset_history(self) -> None:
        with self._lock:
            self._messages = []
            self._gen += 1

    def send_message(self, message: str) -> Iterator[str]:
        if self._llm is None:
            raise RuntimeError("Model is not running. Call start() first.")
        with self._lock:
            gen = self._gen
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
            if gen == self._gen:
                self._messages.append({"role": "assistant", "content": "".join(parts)})


class ModelManager:
    def __init__(self, name: str = config.DEFAULT_MODEL):
        self._lock = threading.Lock()
        self.name = name
        self._model: Model | None = None
        self._loading = False
        self._history: list[dict] = []

    def _build(self, name: str) -> Model:
        return Model(name)

    def select(self, name: str) -> dict:
        spec_for(name)
        with self._lock:
            if self._model is not None and name == self.name:
                return self.status_locked()
            if self._model is not None:
                carried = self._model.get_history()
                if carried:
                    self._history = carried
                try:
                    self._model.stop()
                except Exception:
                    pass
                self._model = None
            self.name = name
            return self.status_locked()

    def set_history(self, messages: list[dict]) -> None:
        with self._lock:
            self._history = [
                {"role": m["role"], "content": m["content"]}
                for m in messages
                if m.get("role") in ("system", "user", "assistant")
                and isinstance(m.get("content"), str)
            ]
            if self._model is not None:
                self._model.set_history(self._history)

    def reset_history(self) -> None:
        self.set_history([])

    def status_locked(self) -> dict:
        model = self._model
        return {
            "current": self.name,
            "running": bool(model is not None and model.is_running),
            "loading": self._loading,
            "mock": False,
            "tiers": [
                {"name": tier, "description": spec["description"]}
                for tier, spec in config.MODELS.items()
            ],
        }

    def status(self) -> dict:
        with self._lock:
            return self.status_locked()

    def ensure(self):
        with self._lock:
            if self._model is None:
                self._model = self._build(self.name)
                self._model.set_history(self._history)
            model = self._model
        model.start()
        return model

    def load_in_background(self) -> dict:
        with self._lock:
            if self._loading:
                return self.status_locked()
            if self._model is not None and self._model.is_running:
                return self.status_locked()
            self._loading = True

        def _run() -> None:
            try:
                self.ensure()
            except Exception:
                pass
            finally:
                with self._lock:
                    self._loading = False

        threading.Thread(target=_run, daemon=True).start()
        with self._lock:
            return self.status_locked()


manager = ModelManager()
