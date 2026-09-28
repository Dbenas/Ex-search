import pytest
from fastapi.testclient import TestClient

from curator.api.app import create_app
from curator.config import Settings
from curator.ingestion.extraction import ExtractionError, extract_cv, pdf_to_text
from curator.service import CurationService
from tests.pdf_helpers import LINKEDIN_PROFILE, make_pdf

pytestmark = pytest.mark.slow

CV_TEXT = """Marina Lopes
Head de Dados, varejo digital
marina.lopes@example.com | +55 11 98765-4321 | https://linkedin.com/in/marina-lopes

Lidera a área de dados e IA de um marketplace com 40 milhões de clientes. Construiu do zero
a plataforma de machine learning e o time de 35 cientistas e engenheiros de dados. Perfil
hands-on, programa em Python, acostumada a ambientes de crescimento acelerado.
Estatística (USP) e mestrado em Ciência da Computação."""


def test_extracts_identity_and_keeps_professional_text() -> None:
    cv = extract_cv(CV_TEXT)
    assert cv.name == "Marina Lopes"
    assert cv.current_role == "Head de Dados, varejo digital"
    assert cv.contact.email == "marina.lopes@example.com"
    assert cv.contact.linkedin and "marina-lopes" in cv.contact.linkedin
    assert cv.contacts_found == ["e-mail", "telefone", "LinkedIn"]
    assert "Marina" not in cv.body and "@" not in cv.body and "98765" not in cv.body
    assert cv.body.startswith("Lidera a área de dados")


def test_rejects_cv_without_enough_professional_text() -> None:
    with pytest.raises(ExtractionError, match="curto"):
        extract_cv("Fulano de Tal\nfulano@example.com")


def test_reads_text_from_pdf() -> None:
    text = pdf_to_text(make_pdf(["Joao Almeida", "CFO de SaaS", "Conduziu IPO e duas rodadas."]))
    assert "Joao Almeida" in text and "Conduziu IPO" in text


def test_rejects_invalid_pdf() -> None:
    with pytest.raises(ExtractionError):
        pdf_to_text(b"not a pdf")


@pytest.fixture
def client(settings: Settings, service: CurationService) -> TestClient:
    return TestClient(create_app(settings, service_factory=lambda _: service))


def test_upload_indexes_candidate_without_pii_and_can_be_removed(
    client: TestClient, service: CurationService
) -> None:
    with client:
        response = client.post("/v1/candidates", data={"text": CV_TEXT})
        assert response.status_code == 201, response.text
        report = response.json()
        cid = report["candidate_id"]
        assert report["name"] == "Marina Lopes" and report["name_detected"]
        assert report["pii_removed"] >= 3
        assert report["gender_cues"] == ["acostumada"]
        indexed = report["indexed_text"]
        assert "acostumado" in indexed and "Marina" not in indexed and "@" not in indexed

        # The new profile is searchable right away.
        hits = service._deps.retriever.search(["plataforma de machine learning e time de dados"], 5)
        assert hits[0].candidate_id == cid

        listed = client.get("/v1/candidates").json()
        assert {c["candidate_id"]: c["source"] for c in listed}[cid] == "upload"

        assert client.post("/v1/candidates", data={"text": CV_TEXT}).status_code == 422  # duplicate
        assert client.delete(f"/v1/candidates/{cid}").status_code == 204
        assert cid not in service.repo
        assert client.delete("/v1/candidates/cand-ana-silva").status_code == 403


def test_upload_pdf_with_name_override(client: TestClient) -> None:
    pdf = make_pdf(
        [
            "Resumo profissional",
            "Vinte anos em financas corporativas em empresas de tecnologia, com duas rodadas",
            "de captacao Series C e um processo de venda concluido para fundo de private equity.",
        ]
    )
    with client:
        response = client.post(
            "/v1/candidates",
            files={"file": ("cv.pdf", pdf, "application/pdf")},
            data={"name": "Rafael Nunes", "current_role": "CFO"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Rafael Nunes" and not body["name_detected"]
        client.delete(f"/v1/candidates/{body['candidate_id']}")


def test_upload_requires_exactly_one_source(client: TestClient) -> None:
    with client:
        assert client.post("/v1/candidates", data={}).status_code == 422
        bad = client.post(
            "/v1/candidates", files={"file": ("cv.exe", b"MZ", "application/x-msdownload")}
        )
        assert bad.status_code == 422


def test_upload_linkedin_export(client: TestClient) -> None:
    with client:
        response = client.post(
            "/v1/candidates",
            files={"file": ("Profile.pdf", make_pdf(LINKEDIN_PROFILE), "application/pdf")},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["source_format"] == "linkedin"
        assert body["name"] == "Joana Prado" and body["name_detected"]
        assert body["current_role"] == "CFO | Tecnologia | Captação e M&A"
        assert body["contacts_found"] == ["e-mail", "LinkedIn"]
        assert "Joana" not in body["indexed_text"]
        # "Executiva", "Diretora" are neutralised in what the model reads.
        assert set(body["gender_cues"]) >= {"Executiva", "Diretora"}
        client.delete(f"/v1/candidates/{body['candidate_id']}")
