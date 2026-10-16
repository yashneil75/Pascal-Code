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


def should_mock(id: str) -> bool:
    if config.MOCK_ENV:
        return True
    if config.STRICT_ENV:
        return False
    try:
        return download_mod.resolve(id) is None
    except Exception:
        return True


def spec_for(id: str) -> dict:
    """Catalogue spec for a tier id; raises for anything else."""
    if id in config.MODELS:
        return config.MODELS[id]
    available = ", ".join(config.MODELS)
    raise ValueError(f"Unknown model {id!r}. Available: {available}")


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

    def get_history(self) -> list[dict]:
        return []

    def set_history(self, messages: list[dict]) -> None:
        return None

    def reset_history(self) -> None:
        return None

    def send_message(self, message: str) -> Iterator[str]:
        # Keep parity with Model: record nothing here; app.py owns history.
        reply = MOCK_REPLIES[self._n % len(MOCK_REPLIES)]
        self._n += 1
        for word in reply.split(" "):
            yield word + " "
            time.sleep(0.02)


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
                # Last resort: fetch the tier now (the settings popup is the
                # progressive path; this blocks a chat until bytes arrive).
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
        """Replace context, e.g. when opening an existing chat.

        Only plain turns survive: tool calls/results would be orphans without
        their counterparts, and llama.cpp rejects them.
        """
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
        """Forget context, e.g. on new chat."""
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
            # A chat switch mid-stream replaces history (bumping _gen); the
            # stale reply belongs to no open chat, so it is not kept.
            if gen == self._gen:
                self._messages.append({"role": "assistant", "content": "".join(parts)})


class ModelManager:
    """One current tier with lazy start and clean switching."""

    def __init__(self, name: str = config.DEFAULT_MODEL):
        self._lock = threading.Lock()
        self.name = name
        self._model: Model | MockModel | None = None
        self._loading = False
        # Desired context for the open conversation. The live model is
        # authoritative while it exists; this seeds fresh models and survives
        # switches made before first load.
        self._history: list[dict] = []

    def _build(self, name: str) -> Model | MockModel:
        if should_mock(name):
            return MockModel(name)
        return Model(name)

    def select(self, name: str) -> dict:
        spec_for(name)  # raises for unknown ids
        with self._lock:
            if self._model is not None and name == self.name:
                return self.status_locked()
            if self._model is not None:
                # Carry the live context over so switching tiers mid-chat
                # keeps it. An empty live history (e.g. a mock, or a reset
                # made before first load) leaves the recorded one alone.
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
        """Point the context at an existing conversation's turns."""
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
        """Forget the context, e.g. on new chat."""
        self.set_history([])

    def status_locked(self) -> dict:
        model = self._model
        return {
            "current": self.name,
            "running": bool(model is not None and model.is_running),
            "loading": self._loading,
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
                self._model.set_history(self._history)
            model = self._model
        # start() can block for seconds; run outside the manager lock.
        model.start()
        return model

    def load_in_background(self) -> dict:
        """Warm up the current model without blocking; see `loading` status."""
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
