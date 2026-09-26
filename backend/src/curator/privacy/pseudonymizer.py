"""PII controls applied before any text reaches the LLM, the vector store or the logs.

Two complementary mechanisms:

* Pattern redaction for free text we don't control (the job description, logs):
  e-mails, phones, CPF/CNPJ and profile URLs are replaced by typed placeholders.
* Deterministic pseudonyms for candidates: the model only ever sees
  ``CANDIDATO_NN``; names are restored at the presentation layer.

In production this module is the seam where Cloud DLP (or Presidio) plugs in
for NER-based detection of names in unstructured CVs.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

_PATTERNS: dict[str, re.Pattern[str]] = {
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "URL": re.compile(r"https?://\S+|www\.\S+|linkedin\.com/\S+", re.IGNORECASE),
    "CPF": re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
    "CNPJ": re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),
    "PHONE": re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b"),
}


@dataclass(frozen=True)
class RedactionResult:
    text: str
    redactions: int


def redact(text: str) -> RedactionResult:
    count = 0
    for label, pattern in _PATTERNS.items():
        text, n = pattern.subn(f"[{label}]", text)
        count += n
    return RedactionResult(text=text, redactions=count)


def alias_for(index: int) -> str:
    return f"CANDIDATO_{index:02d}"


class Pseudonymizer:
    """Bidirectional mapping between candidate ids, aliases and display names."""

    def __init__(self, names_by_id: Mapping[str, str]) -> None:
        ordered = sorted(names_by_id)
        self._alias_by_id = {cid: alias_for(i + 1) for i, cid in enumerate(ordered)}
        self._id_by_alias = {alias: cid for cid, alias in self._alias_by_id.items()}
        self._name_by_alias = {self._alias_by_id[cid]: names_by_id[cid] for cid in ordered}
        self._name_pattern = self._build_name_pattern(names_by_id.values())

    @staticmethod
    def _build_name_pattern(names: Iterable[str]) -> re.Pattern[str] | None:
        tokens = {part for name in names for part in name.split() if len(part) > 2}
        tokens |= set(names)
        if not tokens:
            return None
        alternation = "|".join(re.escape(t) for t in sorted(tokens, key=len, reverse=True))
        return re.compile(rf"\b(?:{alternation})\b")

    def alias(self, candidate_id: str) -> str:
        return self._alias_by_id[candidate_id]

    def candidate_id(self, alias: str) -> str | None:
        return self._id_by_alias.get(alias)

    def anonymize(self, text: str) -> RedactionResult:
        """Strip contact data and any known candidate name from free text."""
        result = redact(text)
        if self._name_pattern is None:
            return result
        scrubbed, n = self._name_pattern.subn("[NOME]", result.text)
        return RedactionResult(text=scrubbed, redactions=result.redactions + n)

    def reidentify(self, text: str) -> str:
        for alias, name in self._name_by_alias.items():
            text = text.replace(alias, name)
        return text
