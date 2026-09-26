"""Local embedding model.

Embeddings run in-process (ONNX, no GPU) so CV text is never sent to a third
party just to be vectorised. The e5 family is asymmetric: queries and passages
need different prefixes, otherwise similarity scores degrade noticeably.
"""

from collections.abc import Sequence
from functools import cached_property
from pathlib import Path

from fastembed import TextEmbedding


class Embedder:
    def __init__(self, model_name: str, cache_dir: Path) -> None:
        self.model_name = model_name
        self._cache_dir = cache_dir
        self._asymmetric = "e5" in model_name.lower()

    @cached_property
    def _model(self) -> TextEmbedding:
        return TextEmbedding(self.model_name, cache_dir=str(self._cache_dir))

    def _prefixed(self, texts: Sequence[str], prefix: str) -> list[str]:
        return [f"{prefix}: {t}" for t in texts] if self._asymmetric else list(texts)

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(self._prefixed(texts, "passage"))]

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(self._prefixed(texts, "query"))]
