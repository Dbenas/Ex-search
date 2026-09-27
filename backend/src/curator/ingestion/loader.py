"""Reads raw CV files and splits them into identity (vault) and professional content."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from curator.domain.models import CandidateIdentity, CandidateProfile, ContactInfo
from curator.privacy.pseudonymizer import Pseudonymizer


class CandidateFileError(ValueError):
    pass


@dataclass(frozen=True)
class RawCandidate:
    identity: CandidateIdentity
    current_role: str
    body: str
    # "base" for the reference set, "upload" for CVs added through the interface.
    source: str = "base"


def parse_candidate_file(path: Path) -> RawCandidate:
    content = path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise CandidateFileError(f"{path.name}: missing YAML front matter")

    meta = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    missing = {"id", "name"} - meta.keys()
    if missing:
        raise CandidateFileError(f"{path.name}: missing fields {sorted(missing)}")
    if not body:
        raise CandidateFileError(f"{path.name}: empty profile")

    identity = CandidateIdentity(
        candidate_id=meta["id"],
        name=meta["name"],
        contact=ContactInfo(
            email=meta.get("email"), phone=meta.get("phone"), linkedin=meta.get("linkedin")
        ),
    )
    return RawCandidate(
        identity=identity,
        current_role=meta.get("current_role") or "",
        body=body,
        source=meta.get("source", "base"),
    )


def write_candidate_file(directory: Path, raw: RawCandidate) -> Path:
    """Persist a CV in the same format as the reference base.

    The file name derives from the generated id, never from user input.
    """
    meta = {
        "id": raw.identity.candidate_id,
        "name": raw.identity.name,
        "current_role": raw.current_role,
        "source": raw.source,
        **{k: v for k, v in raw.identity.contact.model_dump().items() if v},
    }
    path = directory / f"{raw.identity.candidate_id}.md"
    front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{front}---\n{raw.body}\n", encoding="utf-8")
    return path


def load_raw_candidates(directory: Path) -> list[RawCandidate]:
    files = sorted(directory.glob("*.md"))
    if not files:
        raise CandidateFileError(f"no candidate files found in {directory}")
    return [parse_candidate_file(f) for f in files]


class CandidateRepository:
    """In-memory view of the candidate base.

    Identities stay here (in production: a separate, access-controlled store);
    everything handed to retrieval and to the LLM goes through ``profiles``.
    """

    def __init__(self, raw: list[RawCandidate]) -> None:
        ids = [r.identity.candidate_id for r in raw]
        if len(ids) != len(set(ids)):
            raise CandidateFileError("duplicate candidate ids")

        self.pseudonymizer = Pseudonymizer({r.identity.candidate_id: r.identity.name for r in raw})
        self._identities = {r.identity.candidate_id: r.identity for r in raw}
        self._sources = {r.identity.candidate_id: r.source for r in raw}
        self._profiles = {
            r.identity.candidate_id: CandidateProfile(
                candidate_id=r.identity.candidate_id,
                alias=self.pseudonymizer.alias(r.identity.candidate_id),
                current_role=r.current_role,
                summary=self.pseudonymizer.anonymize(r.body).text,
            )
            for r in raw
        }

    @classmethod
    def from_directory(cls, directory: Path) -> "CandidateRepository":
        return cls(load_raw_candidates(directory))

    @property
    def profiles(self) -> list[CandidateProfile]:
        return list(self._profiles.values())

    def profile(self, candidate_id: str) -> CandidateProfile:
        return self._profiles[candidate_id]

    def identity(self, candidate_id: str) -> CandidateIdentity:
        return self._identities[candidate_id]

    def source(self, candidate_id: str) -> str:
        return self._sources[candidate_id]

    def __contains__(self, candidate_id: object) -> bool:
        return candidate_id in self._identities

    def __len__(self) -> int:
        return len(self._profiles)
