"""Grammatical gender cues that survive pseudonymisation.

Removing names is not enough in Portuguese: participles and role nouns agree
with the person ("acostumada", "formada", "executiva"), so the model can still
infer gender from the CV body.

Only feminine forms are treated as signals. The masculine is also the
grammatical default ("perfil pragmático, voltado para resultados" agrees with
"perfil", not with the person), so it does not reveal gender reliably. The
counterfactual for the bias audit therefore rewrites feminine cues into the
unmarked masculine form and leaves everything else untouched.

The word list is a heuristic, not a parser; extend it as new CVs come in.
"""

import re
from dataclasses import dataclass

# feminine -> unmarked (masculine) form
_FEMININE: dict[str, str] = {
    "acostumada": "acostumado",
    "apaixonada": "apaixonado",
    "candidata": "candidato",
    "certificada": "certificado",
    "cofundadora": "cofundador",
    "conselheira": "conselheiro",
    "contratada": "contratado",
    "diretora": "diretor",
    "especializada": "especializado",
    "executiva": "executivo",
    "focada": "focado",
    "formada": "formado",
    "fundadora": "fundador",
    "graduada": "graduado",
    "orientada": "orientado",
    "promovida": "promovido",
    "reconhecida": "reconhecido",
    "sócia": "sócio",
    "voltada": "voltado",
    "ela": "ele",
}

_WORD = re.compile(
    r"\b(" + "|".join(sorted(_FEMININE, key=len, reverse=True)) + r")\b", re.IGNORECASE
)


@dataclass(frozen=True)
class GenderSignal:
    term: str
    start: int
    end: int


def find_gender_signals(text: str) -> list[GenderSignal]:
    """Feminine forms that reveal the gender of the person described."""
    return [GenderSignal(m.group(0), m.start(), m.end()) for m in _WORD.finditer(text)]


def to_unmarked(text: str) -> str:
    """Counterfactual text: feminine cues rewritten to the unmarked form, nothing else touched."""

    def swap(match: re.Match[str]) -> str:
        original = match.group(0)
        target = _FEMININE[original.lower()]
        return target.capitalize() if original[:1].isupper() else target

    return _WORD.sub(swap, text)
