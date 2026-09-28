"""Local embedding model.

Embeddings run in-process (ONNX, no GPU) so CV text is never sent to a third
party just to be vectorised. The e5 family is asymmetric: queries and passages
need different prefixes, otherwise similarity scores degrade noticeably.

The model is materialised as plain files in its own directory. Hugging Face's
default cache uses symlinks on Linux, which splits ``model.onnx`` and its
external weights across folders; recent onnxruntime versions reject that as a
path escape, so the cache layout would break the container and CI.
"""

from collections.abc import Sequence
from functools import cached_property
from pathlib import Path

from fastembed import TextEmbedding
from huggingface_hub import snapshot_download


def _hf_repo(model_name: str) -> str:
    for spec in TextEmbedding.list_supported_models():
        if spec["model"] == model_name:
            return str(spec["sources"]["hf"])
    raise ValueError(f"unsupported embedding model: {model_name}")


class Embedder:
    def __init__(self, model_name: str, cache_dir: Path) -> None:
        self.model_name = model_name
        self._model_dir = cache_dir / model_name.replace("/", "__")
        self._asymmetric = "e5" in model_name.lower()

    def download(self) -> Path:
        """Fetch the model once into a flat directory (idempotent)."""
        if not (self._model_dir / "model.onnx").exists():
            snapshot_download(_hf_repo(self.model_name), local_dir=self._model_dir)
        return self._model_dir

    @cached_property
    def _model(self) -> TextEmbedding:
        return TextEmbedding(self.model_name, specific_model_path=str(self.download()))

    def _prefixed(self, texts: Sequence[str], prefix: str) -> list[str]:
        return [f"{prefix}: {t}" for t in texts] if self._asymmetric else list(texts)

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(self._prefixed(texts, "passage"))]

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(self._prefixed(texts, "query"))]
