import pytest

from curator.config import Settings
from curator.evaluation.retrieval import evaluate_retrieval
from curator.retrieval.embeddings import Embedder

pytestmark = pytest.mark.slow


def test_semantic_search_finds_the_expected_executive_among_distractors(
    settings: Settings,
) -> None:
    result = evaluate_retrieval(
        settings.candidates_dir,
        settings.eval_cases_path.parent / "retrieval.yaml",
        Embedder(settings.embedding_model, settings.embedding_cache_dir),
    )
    assert result["profiles_indexed"] == 20
    dense = result["summary"]["denso"]
    # Regression guard for the production retriever (semantic search).
    assert dense["recall_at_3"] == 1.0
    assert dense["hit_at_1"] >= 0.8
