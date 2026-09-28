"""Business rules for adding CVs to the base: identity, id and the upload receipt."""

import hashlib
import re
import unicodedata

from curator.agent.graph import model_view
from curator.config import Settings
from curator.domain.models import CandidateIdentity, UploadReport
from curator.ingestion.chunking import chunk_text
from curator.ingestion.extraction import ExtractedCV
from curator.ingestion.loader import CandidateRepository, RawCandidate
from curator.privacy.gender_signals import find_gender_signals


class CandidateError(ValueError):
    """Invalid candidate operation (duplicate, missing name, protected record)."""


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:30]


def new_upload(cv: ExtractedCV, name: str | None, current_role: str | None) -> RawCandidate:
    """Build the record for an uploaded CV; the id is derived, never taken from input."""
    final_name = (name or cv.name or "").strip()
    if not final_name:
        raise CandidateError("não foi possível identificar o nome; informe-o no formulário")
    digest = hashlib.sha256(cv.body.encode()).hexdigest()[:6]
    return RawCandidate(
        identity=CandidateIdentity(
            candidate_id=f"up-{_slug(final_name)}-{digest}", name=final_name, contact=cv.contact
        ),
        current_role=(current_role or cv.current_role or "").strip(),
        body=cv.body,
        source="upload",
    )


def upload_receipt(
    raw: RawCandidate,
    cv: ExtractedCV,
    name_given: bool,
    repo: CandidateRepository,
    settings: Settings,
) -> UploadReport:
    """What the partner sees after an upload: what was separated and what the model reads."""
    candidate_id = raw.identity.candidate_id
    profile = repo.profile(candidate_id)
    return UploadReport(
        candidate_id=candidate_id,
        name=raw.identity.name,
        current_role=raw.current_role,
        name_detected=not name_given and cv.name is not None,
        source_format=cv.source_format,
        contacts_found=cv.contacts_found,
        # Name + contacts split off by extraction, plus anything scrubbed from the body.
        pii_removed=1 + len(cv.contacts_found) + repo.pseudonymizer.anonymize(cv.body).redactions,
        chunks_indexed=len(chunk_text(candidate_id, profile.summary)),
        gender_cues=[g.term for g in find_gender_signals(profile.summary)],
        indexed_text=model_view(profile.summary, settings),
    )
