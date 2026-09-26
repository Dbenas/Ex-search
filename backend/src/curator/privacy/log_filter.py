from collections.abc import MutableMapping
from typing import Any

from curator.privacy.pseudonymizer import redact


def scrub_pii(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """structlog processor: last line of defence so contact data never lands in logs."""
    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = redact(value).text
    return event_dict
