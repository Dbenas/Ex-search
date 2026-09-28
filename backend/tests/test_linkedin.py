from curator.ingestion.extraction import extract_pdf
from curator.ingestion.linkedin import parse_linkedin_pdf
from tests.pdf_helpers import LINKEDIN_PROFILE, make_pdf


def test_reads_identity_and_headline_from_layout() -> None:
    profile = parse_linkedin_pdf(make_pdf(LINKEDIN_PROFILE))
    assert profile.name == "Joana Prado"
    assert profile.headline == "CFO | Tecnologia | Captação e M&A"
    assert profile.contact.email == "joana.prado@example.com"
    # The profile URL wraps across two lines in the export and must be rejoined.
    assert profile.contact.linkedin == "www.linkedin.com/in/joana-prado-9f8e7d"
    assert profile.contacts_found == ["e-mail", "LinkedIn"]


def test_body_is_professional_text_only() -> None:
    body = parse_linkedin_pdf(make_pdf(LINKEDIN_PROFILE)).body
    assert body.startswith("Executiva de finanças com 17 anos em empresas de tecnologia.")
    # One sentence per role; the location line after the dates is dropped.
    assert "CFO na Nuvem Pagamentos, março de 2021 - Present (5 anos 6 meses)." in body
    assert "Diretora de Planejamento Financeiro na Grupo Horizonte" in body
    assert "Formação: Universidade de São Paulo: Economia · (2004 - 2008)." in body
    assert "Competências principais: Fusões e aquisições, Valuation." in body
    assert "Joana" not in body and "@" not in body and "linkedin.com" not in body


def test_pdf_router_flags_linkedin_exports() -> None:
    assert extract_pdf(make_pdf(LINKEDIN_PROFILE)).source_format == "linkedin"
    generic = make_pdf(
        [
            "Rafael Nunes",
            "CFO de SaaS",
            "Vinte anos em financas corporativas em empresas de tecnologia, com duas",
            "rodadas de captacao Series C e um processo de venda concluido.",
        ]
    )
    cv = extract_pdf(generic)
    assert cv.source_format == "pdf" and cv.name == "Rafael Nunes"
