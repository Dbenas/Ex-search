"""Reader for the profile PDF that LinkedIn generates ("More > Save to PDF").

We deliberately do not fetch profiles from a URL: scraping breaks LinkedIn's
terms and collects executives' data without their knowledge. The partner
exports the PDF with their own access and uploads it here.

The export has a fixed typographic layout, which is more reliable than its
wording (it comes in several languages): the name is the largest text on the
first page, main sections (Summary, Experience, Education) use one size and
sidebar sections (Contact, Top Skills, Certifications) a smaller one. The
parser classifies lines by font size and only then by content.
"""

import io
import re
from dataclasses import dataclass, field
from typing import Any

from pypdf import PdfReader

from curator.domain.models import ContactInfo
from curator.privacy.pseudonymizer import find_all

_PAGE_FOOTER = re.compile(r"^\s*(Page|Página) \d+ (of|de) \d+\s*$")
_LINKEDIN_URL = re.compile(r"(?:https?://)?(?:[\w-]+\.)?linkedin\.com/in/[\w\-%]+", re.IGNORECASE)
# "maio de 2026 - Present (5 meses)", "Jan 2020 - Dec 2023 (4 years)"
_DATE_RANGE = re.compile(
    r"\s-\s.*\(\s*\d+\s+\w+|\s-\s(Present|Presente|o momento)\b", re.IGNORECASE
)

_SUMMARY = {"resumo", "summary", "sobre", "about"}
_EXPERIENCE = {"experiência", "experience", "experiencia"}
_EDUCATION = {"formação acadêmica", "formacao academica", "education"}
_CONTACT = {"contato", "contact"}
_SKILLS = {"principais competências", "top skills", "principais competencias"}
_CERTIFICATIONS = {"certifications", "certificações", "licenses & certifications"}
_LANGUAGES = {"languages", "idiomas"}


@dataclass
class _Layout:
    name: str | None = None
    main_headings: set[str] = field(default_factory=set)
    side_headings: set[str] = field(default_factory=set)


def _layout(reader: PdfReader) -> _Layout:
    """Classify headline texts by rendered font size."""
    sized: list[tuple[float, str]] = []

    def visit(text: str, cm: Any, tm: Any, font: Any, size: float) -> None:
        stripped = text.strip()
        if stripped:
            sized.append((round(size * abs(tm[0] or 1), 1), stripped))

    for page in reader.pages:
        page.extract_text(visitor_text=visit)
    if not sized:
        return _Layout()

    # The template uses three display sizes above running text:
    # name > main section headings > sidebar section headings.
    sizes = sorted({s for s, _ in sized}, reverse=True)
    if len(sizes) < 4:
        return _Layout()
    name_size, main_size, side_size = sizes[:3]
    layout = _Layout(name=next(t for s, t in sized if s == name_size))
    layout.main_headings = {t for s, t in sized if s == main_size}
    layout.side_headings = {t for s, t in sized if s == side_size}
    return layout


def is_linkedin_export(text: str) -> bool:
    has_footer = any(_PAGE_FOOTER.match(line) for line in text.splitlines())
    return has_footer and bool(_LINKEDIN_URL.search(text.replace("-\n", "-")))


def _reflow(lines: list[str]) -> str:
    """Join lines wrapped by the PDF layout into running text."""
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _experience(lines: list[str]) -> list[str]:
    """'Company / Title / dates [/ location]' blocks into one sentence per role."""
    dates = [i for i, line in enumerate(lines) if _DATE_RANGE.search(line)]
    if not dates:
        return [_reflow(lines)] if lines else []
    roles, start = [], 0
    for d in dates:
        block = lines[start:d]
        # A leftover line after the previous role's dates is that role's location.
        if len(block) >= 3:
            block = block[1:]
        if len(block) >= 2:
            company, title = _reflow(block[:-1]), block[-1]
            roles.append(f"{title} na {company}, {lines[d].strip()}.")
        elif block:
            roles.append(f"{block[0]}, {lines[d].strip()}.")
        start = d + 1
    return roles


def _education(lines: list[str]) -> list[str]:
    """'Institution / degree · (period)' entries; a closing parenthesis ends an entry."""
    entries, current = [], []
    for line in lines:
        current.append(line)
        if line.rstrip().endswith(")"):
            institution, *details = current
            entries.append(f"{institution}: {_reflow(details)}" if details else institution)
            current = []
    if current:
        entries.append(_reflow(current))
    return entries


@dataclass(frozen=True)
class LinkedInProfile:
    name: str | None
    headline: str | None
    contact: ContactInfo
    body: str
    contacts_found: list[str]


def parse_linkedin_pdf(data: bytes) -> LinkedInProfile:
    reader = PdfReader(io.BytesIO(data))
    layout = _layout(reader)
    lines = [
        line.strip()
        for page in reader.pages
        for line in (page.extract_text() or "").splitlines()
        if line.strip() and not _PAGE_FOOTER.match(line)
    ]

    sections: dict[str, list[str]] = {}
    current = "_preamble"
    header: list[str] = []
    for line in lines:
        key = line.lower()
        if line == layout.name:
            current = "_header"
            continue
        if line in layout.main_headings or line in layout.side_headings:
            current = key
            sections.setdefault(current, [])
            continue
        if current == "_header":
            header.append(line)
        else:
            sections.setdefault(current, []).append(line)

    def section(names: set[str]) -> list[str]:
        return next((v for k, v in sections.items() if k in names), [])

    # Header: headline (may wrap) followed by location, right before the first main section.
    headline = _reflow(header[:-1]) if len(header) > 1 else (header[0] if header else None)

    contact_text = "\n".join(section(_CONTACT)).replace("-\n", "-")
    email = next(iter(find_all("EMAIL", contact_text)), None)
    phone = next(iter(find_all("PHONE", contact_text)), None)
    linkedin_match = _LINKEDIN_URL.search(contact_text)
    linkedin = linkedin_match.group(0) if linkedin_match else None
    contacts_found = [
        label
        for label, value in (("e-mail", email), ("telefone", phone), ("LinkedIn", linkedin))
        if value
    ]

    parts = []
    if summary := section(_SUMMARY):
        parts.append(_reflow(summary))
    if roles := _experience(section(_EXPERIENCE)):
        parts.append("Experiência: " + " ".join(roles))
    if education := _education(section(_EDUCATION)):
        parts.append("Formação: " + "; ".join(education) + ".")
    if skills := section(_SKILLS):
        parts.append("Competências principais: " + ", ".join(skills) + ".")
    if certifications := section(_CERTIFICATIONS):
        parts.append("Certificações: " + _reflow(certifications) + ".")
    if languages := section(_LANGUAGES):
        parts.append("Idiomas: " + ", ".join(languages) + ".")

    return LinkedInProfile(
        name=layout.name,
        headline=headline[:120] if headline else None,
        contact=ContactInfo(email=email, phone=phone, linkedin=linkedin),
        body="\n\n".join(parts),
        contacts_found=contacts_found,
    )
