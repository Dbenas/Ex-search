from curator.agent.grounding import grounding_rate, verify_evidence
from curator.domain.models import Evidence
from curator.ingestion.chunking import chunk_text, split_sentences

PROFILE = (
    "12 anos em tech. CTO em startup de logística. Foco absoluto em Inteligência "
    "Artificial, dados e otimização de rotas. Hands-on, programa em Python e escala "
    "times ágeis do zero. Matemática (UFRJ)."
)


def test_sentences_keep_offsets() -> None:
    spans = split_sentences(PROFILE)
    assert len(spans) == 5
    assert all(PROFILE[s:e].strip() for s, e in spans)


def test_chunks_cover_text_and_overlap() -> None:
    chunks = chunk_text("c1", PROFILE, max_chars=90)
    assert len(chunks) > 1
    assert chunks[0].text.startswith("12 anos")
    assert chunks[-1].text.endswith("(UFRJ).")
    for c in chunks:
        assert PROFILE[c.start : c.end] == c.text
    # One-sentence overlap between consecutive chunks.
    assert chunks[1].start < chunks[0].end


def test_short_profile_is_single_chunk() -> None:
    assert len(chunk_text("c1", "Um único parágrafo curto.")) == 1


def _evidence(quote: str) -> Evidence:
    return Evidence(requirement="r", claim="c", quote=quote)


def test_verbatim_quote_is_verified_with_span() -> None:
    result = verify_evidence(_evidence("programa em Python"), PROFILE, threshold=85)
    assert result.verified
    assert result.start is not None and result.end is not None
    assert PROFILE[result.start : result.end].lower() == "programa em python"


def test_near_verbatim_quote_tolerates_punctuation() -> None:
    result = verify_evidence(_evidence('"Hands-on, programa em Python..."'), PROFILE, 85)
    assert result.verified


def test_fabricated_quote_is_rejected() -> None:
    result = verify_evidence(_evidence("Liderou IPO na Nasdaq"), PROFILE, threshold=85)
    assert not result.verified
    assert result.start is None


def test_grounding_rate() -> None:
    items = [
        verify_evidence(_evidence("CTO em startup de logística"), PROFILE, 85),
        verify_evidence(_evidence("Doutorado em Harvard"), PROFILE, 85),
    ]
    assert grounding_rate(items) == 0.5
    assert grounding_rate([]) == 0.0
