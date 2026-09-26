from curator.privacy.pseudonymizer import Pseudonymizer, redact


def test_redact_contact_data() -> None:
    text = (
        "Fale com ana@corp.com ou +55 11 91234-5678, CPF 123.456.789-09, "
        "perfil https://linkedin.com/in/ana"
    )
    result = redact(text)
    assert "ana@corp.com" not in result.text
    assert "91234-5678" not in result.text
    assert "123.456.789-09" not in result.text
    assert "linkedin.com/in/ana" not in result.text
    assert result.redactions == 4


def test_redact_keeps_professional_numbers() -> None:
    text = "15 anos de experiência, equipes de +500 pessoas, Series B e C."
    assert redact(text).text == text


def test_pseudonymizer_round_trip() -> None:
    p = Pseudonymizer({"b": "Bruno Costa", "a": "Ana Silva"})
    assert p.alias("a") == "CANDIDATO_01"
    assert p.candidate_id("CANDIDATO_02") == "b"
    assert p.reidentify("CANDIDATO_01 supera CANDIDATO_02") == "Ana Silva supera Bruno Costa"


def test_pseudonymizer_scrubs_known_names() -> None:
    p = Pseudonymizer({"a": "Ana Silva"})
    result = p.anonymize("Indicação: Ana Silva (ana@x.com). Silva tem MBA.")
    assert "Ana" not in result.text and "Silva" not in result.text
    assert "ana@x.com" not in result.text
