"""Turn an unstructured CV (pasted text or PDF) into identity + professional text.

Deterministic on purpose: contact data is found with patterns and the name
with a layout heuristic (CVs open with the person's name), so identifying
data is separated before any model sees the document. The partner can always
override the detected name and role.
"""

import io
import re
from dataclasses import dataclass, field, replace

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from curator.domain.models import ContactInfo
from curator.ingestion.linkedin import is_linkedin_export, parse_linkedin_pdf
from curator.privacy.pseudonymizer import find_all

MAX_PDF_PAGES = 10
MAX_TEXT_CHARS = 20_000
_CONNECTORS = {"da", "de", "do", "das", "dos", "e"}
_LABEL = re.compile(r"^\s*(nome|name|candidat[oa])\s*[:\-]\s*", re.IGNORECASE)
_PLACEHOLDERS_ONLY = re.compile(r"^[\s|·•,;/\-–—()]*$")


class ExtractionError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedCV:
    name: str | None
    current_role: str | None
    contact: ContactInfo
    body: str
    contacts_found: list[str] = field(default_factory=list)
    # "linkedin" when the file is a LinkedIn profile export, else "pdf" or "text".
    source_format: str = "text"


def pdf_to_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ExtractionError("o PDF está protegido por senha")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ExtractionError(f"o PDF tem mais de {MAX_PDF_PAGES} páginas")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except PdfReadError as exc:
        raise ExtractionError("não foi possível ler o PDF") from exc
    if not text.strip():
        raise ExtractionError("o PDF não tem texto selecionável (imagem escaneada?)")
    return text


def _looks_like_name(line: str) -> bool:
    words = line.split()
    if not 2 <= len(words) <= 5 or len(line) > 60:
        return False
    if any(ch.isdigit() or ch in "@/:|" for ch in line):
        return False
    return all(w[0].isupper() or w.lower() in _CONNECTORS for w in words)


def _looks_like_role(line: str) -> bool:
    return 3 <= len(line) <= 80 and not line.rstrip().endswith(".") and not find_all("EMAIL", line)


def extract_cv(raw: str) -> ExtractedCV:
    text = raw.replace("\r\n", "\n").strip()
    if len(text) > MAX_TEXT_CHARS:
        raise ExtractionError(f"o currículo excede {MAX_TEXT_CHARS} caracteres")

    email = next(iter(find_all("EMAIL", text)), None)
    phone = next(iter(find_all("PHONE", text)), None)
    linkedin = next((u for u in find_all("URL", text) if "linkedin" in u.lower()), None)
    contacts_found = [
        label
        for label, value in (("e-mail", email), ("telefone", phone), ("LinkedIn", linkedin))
        if value
    ]

    lines = [line.strip().lstrip("#").strip() for line in text.split("\n")]
    content = [i for i, line in enumerate(lines) if line]
    name = role = None
    consumed: set[int] = set()
    if content:
        first = _LABEL.sub("", lines[content[0]])
        if _looks_like_name(first):
            name = first
            consumed.add(content[0])
            if len(content) > 1 and _looks_like_role(lines[content[1]]):
                candidate = lines[content[1]]
                stripped = candidate
                for label in ("EMAIL", "PHONE", "URL"):
                    for value in find_all(label, stripped):
                        stripped = stripped.replace(value, "")
                if not _PLACEHOLDERS_ONLY.match(stripped):
                    role = candidate
                consumed.add(content[1])

    # Drop the header lines and lines that only carry contact data.
    body_lines = []
    for i, line in enumerate(lines):
        if i in consumed:
            continue
        stripped = line
        for label in ("EMAIL", "PHONE", "URL"):
            for value in find_all(label, stripped):
                stripped = stripped.replace(value, "")
        stripped = re.sub(
            r"(?i)\b(e-?mail|telefone|tel|celular|linkedin|contato)\b\s*:?", "", stripped
        )
        if line and _PLACEHOLDERS_ONLY.match(stripped):
            continue
        body_lines.append(line)
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(body_lines)).strip()
    if len(body) < 80:
        raise ExtractionError("o texto profissional do currículo é curto demais para avaliação")

    return ExtractedCV(
        name=name,
        current_role=role,
        contact=ContactInfo(email=email, phone=phone, linkedin=linkedin),
        body=body,
        contacts_found=contacts_found,
    )


def extract_pdf(data: bytes) -> ExtractedCV:
    """Route LinkedIn profile exports to the dedicated reader; other PDFs to the generic one."""
    text = pdf_to_text(data)
    if is_linkedin_export(text):
        profile = parse_linkedin_pdf(data)
        if len(profile.body) >= 80:
            return ExtractedCV(
                name=profile.name,
                current_role=profile.headline,
                contact=profile.contact,
                body=profile.body,
                contacts_found=profile.contacts_found,
                source_format="linkedin",
            )
    return replace(extract_cv(text), source_format="pdf")
